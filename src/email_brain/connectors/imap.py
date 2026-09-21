"""Injected IMAPClient-compatible read contract; never opens sockets or logs in."""

from __future__ import annotations

import imaplib
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID, uuid4

from email_brain.normalize import MAX_RAW_BYTES

MAX_UID = 2**32 - 1
UID_WINDOW = 1000
MAX_INVENTORY_UIDS = 10000
MAX_SCAN_WINDOWS = 4096


class ImapProtocolError(Exception):
    pass


class ImapUidValidityChanged(Exception):
    pass


class ImapUnavailable(Exception):
    pass


class ImapMessageUnavailable(Exception):
    """A missing FETCH row is not an authorized tombstone."""


class ImapSession(Protocol):
    use_uid: bool

    def select_folder(self, folder: str, readonly: bool = False) -> Any: ...
    def folder_status(self, folder: str, what: Sequence[str]) -> Any: ...
    def search(self, criteria: Sequence[str]) -> Any: ...
    def fetch(self, messages: Sequence[int], data: Sequence[str]) -> Any: ...


def _uid(value: Any) -> int:
    if type(value) is not int or not 1 <= value <= MAX_UID:
        raise ImapProtocolError("invalid IMAP UID integer")
    return value


def _folder(value: str) -> str:
    if not 1 <= len(value) <= 1024 or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ImapProtocolError("invalid IMAP folder")
    return value


@dataclass(frozen=True)
class UidReference:
    folder: str
    uidvalidity: int
    uid: int


@dataclass(frozen=True)
class InventoryCursor:
    folder: str
    uidvalidity: int
    high_water_uid: int
    next_uid: int
    generation: UUID


@dataclass(frozen=True)
class CompleteInventory:
    folder: str
    uidvalidity: int
    high_water_uid: int
    generation: UUID
    uids: tuple[int, ...] = field(repr=False)


@dataclass(frozen=True)
class InventoryPage:
    uids: tuple[int, ...]
    next_cursor: InventoryCursor | None
    complete: CompleteInventory | None


@dataclass(frozen=True)
class MimeEvidence:
    reference: UidReference
    raw: bytes = field(repr=False)
    flags: tuple[bytes, ...]


class ImapReadClient:
    """Caller exclusively owns approved TLS/session/account binding and wire limits."""

    def __init__(self, session: ImapSession) -> None:
        self._session = session
        self.reset()

    def reset(self) -> None:
        """Forget local state after disconnect; never CLOSE/EXPUNGE the session."""
        self._selection: InventoryCursor | None = None
        self._cursor: InventoryCursor | None = None
        self._complete: CompleteInventory | None = None
        self._seen: list[int] = []
        self._windows = 0

    @contextmanager
    def _guard(self) -> Iterator[None]:
        try:
            if self._session.use_uid is not True:
                raise ImapProtocolError("UID-mode session required")
            yield
        except (ImapProtocolError, ImapUidValidityChanged):
            self.reset()
            raise
        except (OSError, EOFError, imaplib.IMAP4.error):
            self.reset()
            raise ImapUnavailable("IMAP session unavailable; reselect required") from None

    def select(self, folder: str) -> InventoryCursor:
        self.reset()
        with self._guard():
            name = _folder(folder)
            data = self._session.select_folder(name, readonly=True)
            if not isinstance(data, dict) or data.get(b"READ-WRITE", False) is not False:
                raise ImapProtocolError("read-only IMAP selection required")
            validity = _uid(data.get(b"UIDVALIDITY"))
            next_uid = _uid(data.get(b"UIDNEXT"))
            self._selection = self._cursor = InventoryCursor(
                name, validity, next_uid - 1, 1, uuid4()
            )
            return self._selection

    def _verify_selection(self) -> InventoryCursor:
        selected = self._selection
        if selected is None:
            raise ImapProtocolError("select a read-only folder first")
        status = self._session.folder_status(selected.folder, ["UIDVALIDITY", "UIDNEXT"])
        if not isinstance(status, dict):
            raise ImapProtocolError("invalid IMAP folder status")
        if _uid(status.get(b"UIDVALIDITY")) != selected.uidvalidity:
            raise ImapUidValidityChanged("IMAP UIDVALIDITY changed; full folder rebuild required")
        if _uid(status.get(b"UIDNEXT")) <= selected.high_water_uid:
            raise ImapProtocolError("IMAP UIDNEXT moved backwards")
        return selected

    def inventory_page(self, cursor: InventoryCursor) -> InventoryPage:
        with self._guard():
            selected = self._verify_selection()
            if cursor != self._cursor or self._complete is not None:
                raise ImapProtocolError("stale or foreign inventory cursor")
            if self._windows >= MAX_SCAN_WINDOWS:
                raise ImapProtocolError("IMAP scan window budget exceeded")
            low = cursor.next_uid
            high = min(low + UID_WINDOW - 1, selected.high_water_uid)
            if low <= high:
                values = self._session.search(["UID", f"{low}:{high}"])
                if not isinstance(values, (list, tuple)) or len(values) > UID_WINDOW:
                    raise ImapProtocolError("invalid bounded IMAP search response")
                ids = tuple(sorted(_uid(value) for value in values))
                if len(set(ids)) != len(ids) or any(not low <= uid <= high for uid in ids):
                    raise ImapProtocolError("IMAP search escaped UID window")
            else:
                ids = ()  # Empty selected folder: never issue the reversed range 1:0.
            self._verify_selection()
            if len(self._seen) + len(ids) > MAX_INVENTORY_UIDS:
                raise ImapProtocolError("IMAP inventory budget exceeded")
            self._seen.extend(ids)
            self._windows += 1
            if high >= selected.high_water_uid:
                self._cursor = None
                self._complete = CompleteInventory(
                    selected.folder,
                    selected.uidvalidity,
                    selected.high_water_uid,
                    selected.generation,
                    tuple(self._seen),
                )
                return InventoryPage(ids, None, self._complete)
            self._cursor = InventoryCursor(
                selected.folder,
                selected.uidvalidity,
                selected.high_water_uid,
                high + 1,
                selected.generation,
            )
            return InventoryPage(ids, self._cursor, None)

    def absent_uids(
        self, known: Sequence[UidReference], complete: CompleteInventory
    ) -> tuple[UidReference, ...]:
        with self._guard():
            selected = self._verify_selection()
            if complete is not self._complete or len(known) > MAX_INVENTORY_UIDS:
                raise ImapProtocolError("current complete inventory certificate required")
            seen = set(complete.uids)
            missing: list[UidReference] = []
            checked: set[int] = set()
            for reference in known:
                uid = _uid(reference.uid)
                _uid(reference.uidvalidity)
                if (
                    reference.folder != selected.folder
                    or reference.uidvalidity != selected.uidvalidity
                    or uid in checked
                ):
                    raise ImapProtocolError("foreign or duplicate known IMAP UID")
                checked.add(uid)
                if uid <= complete.high_water_uid and uid not in seen:
                    missing.append(reference)
            return tuple(missing)

    def _row(self, data: Any, uid: int) -> dict[bytes, Any]:
        if not isinstance(data, dict) or any(type(key) is not int or key != uid for key in data):
            raise ImapProtocolError("IMAP fetch returned unexpected UID")
        if uid not in data:
            raise ImapMessageUnavailable("IMAP message unavailable; reconcile inventory")
        row = data[uid]
        # IMAPClient consumes the UID token into the outer key in UID mode.
        # Compatible sessions may also retain it; reject a contradictory copy.
        if not isinstance(row, dict) or (b"UID" in row and _uid(row[b"UID"]) != uid):
            raise ImapProtocolError("IMAP fetch UID mismatch")
        return row

    def fetch_mime(self, reference: UidReference) -> MimeEvidence:
        with self._guard():
            selected = self._verify_selection()
            uid = _uid(reference.uid)
            _uid(reference.uidvalidity)
            if reference.folder != selected.folder or reference.uidvalidity != selected.uidvalidity:
                raise ImapProtocolError("foreign IMAP message reference")
            info = self._row(self._session.fetch([uid], ["UID", "RFC822.SIZE"]), uid)
            size = info.get(b"RFC822.SIZE")
            if type(size) is not int or not 0 <= size <= MAX_RAW_BYTES:
                raise ImapProtocolError("IMAP message exceeds raw byte limit")
            self._verify_selection()
            # An extra byte detects a server whose size preflight was inaccurate.
            row = self._row(
                self._session.fetch([uid], ["UID", "FLAGS", f"BODY.PEEK[]<0.{MAX_RAW_BYTES + 1}>"]),
                uid,
            )
            self._verify_selection()
            raw = row.get(b"BODY[]<0>")
            flags = row.get(b"FLAGS")
            if not isinstance(raw, bytes) or len(raw) != size or len(raw) > MAX_RAW_BYTES:
                raise ImapProtocolError("incomplete or oversized IMAP MIME")
            if (
                not isinstance(flags, (list, tuple))
                or len(flags) > 64
                or any(
                    not isinstance(flag, bytes)
                    or not 1 <= len(flag) <= 128
                    or any(byte < 33 or byte > 126 for byte in flag)
                    for flag in flags
                )
            ):
                raise ImapProtocolError("invalid bounded IMAP flags")
            return MimeEvidence(reference, raw, tuple(flags))
