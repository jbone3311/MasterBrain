"""Conservative RFC 5545 source-text extraction, never a calendar/action engine.

Reference: https://www.rfc-editor.org/rfc/rfc5545.html
Unfold bytes before UTF-8 decoding (§3.1); do not evaluate source schedules.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime

MAX_BYTES = 256 * 1024
MAX_PHYSICAL_LINES = 4096
MAX_PHYSICAL_LINE_BYTES = 4096
MAX_UNFOLDED_LINE_BYTES = 16384
MAX_COMPONENTS = 128
MAX_PROPERTIES = 1024
MAX_DEPTH = 4
MAX_EVENTS = 32
MAX_PARAMETERS = 16
MAX_OUTPUT_CHARS = 20000


class CalendarUnsupported(ValueError):
    """Recognizable source requires an unsupported component/encoding/version."""


class CalendarInvalid(ValueError):
    """Malformed or over-budget source; never return partial successful output."""


@dataclass
class _Property:
    name: str
    parameters: dict[str, tuple[str, ...]]
    value: str


@dataclass
class _Component:
    name: str
    properties: list[_Property] = field(default_factory=list)
    children: list[_Component] = field(default_factory=list)


def _lines(raw: bytes) -> list[str]:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BYTES:
        raise CalendarInvalid("calendar byte budget or input invalid")
    # Accept uniform LF as a compatibility variant; bare CR/mixed newline styles fail.
    if b"\r" in raw:
        if b"\r" in raw.replace(b"\r\n", b"") or b"\n" in raw.replace(b"\r\n", b""):
            raise CalendarInvalid("invalid calendar line endings")
        raw = raw.replace(b"\r\n", b"\n")
    if not raw.endswith(b"\n"):
        raise CalendarInvalid("unterminated calendar content line")
    physical = raw[:-1].split(b"\n")
    if len(physical) > MAX_PHYSICAL_LINES:
        raise CalendarInvalid("calendar physical line budget exceeded")
    unfolded: list[bytes] = []
    for line in physical:
        if not line or len(line) > MAX_PHYSICAL_LINE_BYTES:
            raise CalendarInvalid("invalid or oversized calendar physical line")
        if line[:1] in {b" ", b"\t"}:
            if not unfolded:
                raise CalendarInvalid("calendar folding without preceding line")
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
        if len(unfolded[-1]) > MAX_UNFOLDED_LINE_BYTES:
            raise CalendarInvalid("calendar unfolded line budget exceeded")
    try:
        lines = [line.decode("utf-8", errors="strict") for line in unfolded]
    except UnicodeError:
        raise CalendarInvalid("calendar is not strict UTF-8") from None
    if any(
        any(ord(char) < 32 and char != "\t" or ord(char) == 127 for char in line) for line in lines
    ):
        raise CalendarInvalid("calendar contains prohibited control characters")
    return lines


def _split(text: str, separator: str, *, once: bool = False) -> list[str]:
    quoted = False
    start = 0
    parts: list[str] = []
    for index, char in enumerate(text):
        if char == '"':
            quoted = not quoted
        elif char == separator and not quoted:
            parts.append(text[start:index])
            if once:
                return [*parts, text[index + 1 :]]
            start = index + 1
    if quoted:
        raise CalendarInvalid("unclosed calendar parameter quote")
    return [*parts, text[start:]]


def _name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", value):
        raise CalendarInvalid("invalid calendar property or component name")
    return value.upper()


def _property(line: str) -> _Property:
    parts = _split(line, ":", once=True)
    if len(parts) != 2:
        raise CalendarInvalid("calendar content line missing value delimiter")
    left, value = parts
    fields = _split(left, ";")
    name = _name(fields[0])
    if len(fields) - 1 > MAX_PARAMETERS:
        raise CalendarInvalid("calendar parameter budget exceeded")
    parameters: dict[str, tuple[str, ...]] = {}
    for field_value in fields[1:]:
        if "=" not in field_value:
            raise CalendarInvalid("calendar parameter missing assignment")
        key, parameter = field_value.split("=", 1)
        key = _name(key)
        if key in parameters:
            raise CalendarInvalid("duplicate calendar parameter")
        values: list[str] = []
        for item in _split(parameter, ","):
            if item.startswith('"') and item.endswith('"') and len(item) >= 2:
                item = item[1:-1]
                if '"' in item:
                    raise CalendarInvalid("invalid quoted calendar parameter")
            elif any(char in item for char in '";:,'):
                raise CalendarInvalid("invalid unquoted calendar parameter")
            values.append(item)
        parameters[key] = tuple(values)
    return _Property(name, parameters, value)


def _tree(lines: list[str]) -> _Component:
    roots: list[_Component] = []
    stack: list[_Component] = []
    components = properties = 0
    for line in lines:
        prop = _property(line)
        if prop.name == "BEGIN":
            if prop.parameters:
                raise CalendarInvalid("component delimiter parameters denied")
            name = _name(prop.value)
            component = _Component(name)
            components += 1
            if components > MAX_COMPONENTS or len(stack) >= MAX_DEPTH:
                raise CalendarInvalid("calendar component or depth budget exceeded")
            if stack:
                stack[-1].children.append(component)
            else:
                roots.append(component)
            stack.append(component)
        elif prop.name == "END":
            if prop.parameters or not stack or _name(prop.value) != stack[-1].name:
                raise CalendarInvalid("mismatched calendar component end")
            stack.pop()
        else:
            properties += 1
            if not stack or properties > MAX_PROPERTIES:
                raise CalendarInvalid("calendar property outside component or budget exceeded")
            stack[-1].properties.append(prop)
    if stack or len(roots) != 1 or roots[0].name != "VCALENDAR":
        raise CalendarInvalid("one complete VCALENDAR envelope required")
    return roots[0]


_TEXT = {
    "UID",
    "SUMMARY",
    "DESCRIPTION",
    "LOCATION",
    "PRODID",
    "COMMENT",
    "CONTACT",
    "CATEGORIES",
    "RESOURCES",
    "TZID",
    "TZNAME",
}
_DATES = {"DTSTART", "DTEND", "DTSTAMP", "RECURRENCE-ID", "CREATED", "LAST-MODIFIED"}
_SINGLE_EVENT = {
    "UID",
    "SUMMARY",
    "DESCRIPTION",
    "LOCATION",
    "DTSTART",
    "DTEND",
    "DTSTAMP",
    "RECURRENCE-ID",
    "RRULE",
    "STATUS",
    "ORGANIZER",
    "SEQUENCE",
    "DURATION",
}


def _text(value: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\\":
            index += 1
            if index >= len(value) or value[index] not in "\\,;nN":
                raise CalendarInvalid("invalid calendar TEXT escape")
            char = "\n" if value[index] in "nN" else value[index]
        result.append(char)
        index += 1
    return "".join(result)


def _parameter(prop: _Property, name: str, default: str = "") -> str:
    values = prop.parameters.get(name, (default,))
    if len(values) != 1 or not values[0]:
        raise CalendarInvalid("invalid single-value calendar parameter")
    return values[0]


def _date(prop: _Property) -> None:
    kind = _parameter(prop, "VALUE", "DATE-TIME").upper()
    if kind not in {"DATE", "DATE-TIME"}:
        raise CalendarUnsupported("unsupported calendar date value type")
    value = prop.value
    if kind == "DATE":
        if "TZID" in prop.parameters or not re.fullmatch(r"[0-9]{8}", value):
            raise CalendarInvalid("invalid source calendar DATE")
        pattern = "%Y%m%d"
    else:
        if not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z?", value):
            raise CalendarInvalid("invalid source calendar DATE-TIME")
        if "TZID" in prop.parameters:
            _parameter(prop, "TZID")
            if value.endswith("Z"):
                raise CalendarInvalid("UTC source date cannot also have TZID")
        # Leap-second handling is not implemented; preserve no partial interpretation.
        if value[13:15] == "60":
            raise CalendarUnsupported("calendar leap seconds are unsupported")
        pattern = "%Y%m%dT%H%M%SZ" if value.endswith("Z") else "%Y%m%dT%H%M%S"
    if prop.name in {"DTSTAMP", "CREATED", "LAST-MODIFIED"} and (
        kind != "DATE-TIME" or not value.endswith("Z")
    ):
        raise CalendarInvalid("calendar timestamp must be UTC DATE-TIME")
    try:
        datetime.strptime(value, pattern)
    except ValueError:
        raise CalendarInvalid("invalid source calendar date fields") from None


def _validate(component: _Component, method_present: bool, parent: str = "") -> int:
    allowed = {
        "": {"VCALENDAR"},
        "VCALENDAR": {"VEVENT", "VTIMEZONE"},
        "VEVENT": {"VALARM"},
        "VTIMEZONE": {"STANDARD", "DAYLIGHT"},
        "STANDARD": set(),
        "DAYLIGHT": set(),
        "VALARM": set(),
    }
    if component.name not in allowed:
        raise CalendarUnsupported("non-event or unknown calendar component")
    if component.name not in allowed[parent]:
        raise CalendarInvalid("invalid calendar component nesting")
    seen: set[str] = set()
    for prop in component.properties:
        if "ENCODING" in prop.parameters or _parameter(prop, "VALUE", "TEXT").upper() == "BINARY":
            raise CalendarUnsupported("inline calendar encoding is unsupported")
        if component.name == "VEVENT" and prop.name in _SINGLE_EVENT and prop.name in seen:
            raise CalendarInvalid("duplicate single event property")
        if (
            component.name == "VCALENDAR"
            and prop.name in {"VERSION", "PRODID", "METHOD", "CALSCALE"}
            and prop.name in seen
        ):
            raise CalendarInvalid("duplicate single calendar property")
        seen.add(prop.name)
        if prop.name in _TEXT:
            _text(prop.value)
        if prop.name in _DATES:
            _date(prop)
        if prop.name in {"UID", "PRODID"} and not prop.value:
            raise CalendarInvalid("empty required calendar identifier")
        if prop.name == "METHOD":
            _name(prop.value)
        if (
            component.name == "VEVENT"
            and prop.name == "STATUS"
            and prop.value.upper() not in {"TENTATIVE", "CONFIRMED", "CANCELLED"}
        ):
            raise CalendarInvalid("invalid source event status")
    if component.name == "VCALENDAR":
        if not {"VERSION", "PRODID"}.issubset(seen):
            raise CalendarInvalid("calendar VERSION and PRODID required")
        version = next(prop for prop in component.properties if prop.name == "VERSION")
        if version.value != "2.0":
            raise CalendarUnsupported("unsupported calendar version")
    if component.name == "VEVENT":
        if not {"UID", "DTSTAMP"}.issubset(seen) or (not method_present and "DTSTART" not in seen):
            raise CalendarInvalid("required event source property missing")
        if {"DTEND", "DURATION"}.issubset(seen):
            raise CalendarInvalid("event cannot specify both DTEND and DURATION")
    return (component.name == "VEVENT") + sum(
        _validate(child, method_present, component.name) for child in component.children
    )


def extract_calendar(raw: bytes, *, mime_method: str | None = None) -> str:
    """Return bounded quoted source evidence; never a schedule, RSVP or obligation."""
    root = _tree(_lines(raw))
    if mime_method is not None:
        methods = [prop.value for prop in root.properties if prop.name == "METHOD"]
        if (
            not isinstance(mime_method, str)
            or not re.fullmatch(r"[A-Za-z0-9-]+", mime_method)
            or len(methods) != 1
            or methods[0].upper() != mime_method.upper()
        ):
            raise CalendarInvalid("MIME method disagrees with calendar METHOD")
    count = _validate(root, any(prop.name == "METHOD" for prop in root.properties))
    if not count:
        raise CalendarUnsupported("calendar has no supported events")
    if count > MAX_EVENTS:
        raise CalendarInvalid("calendar event budget exceeded")
    output = [
        "UNTRUSTED CALENDAR SOURCE EVIDENCE — not an accepted invitation or obligation.",
        "Dates/TZID/recurrence are source values only: "
        "no timezone conversion or recurrence expansion.",
        "DTEND is an exclusive source end; cancellation/METHOD are claims, not mailbox state.",
        "Organizer/attendees are unauthenticated. "
        "No RSVP, URL fetch, or alarm action is performed.",
    ]

    def render(component: _Component, path: str) -> None:
        label = " (inert source only; not executed)" if component.name == "VALARM" else ""
        output.append(f"Source component {path}{label}")
        for prop in component.properties:
            value = _text(prop.value) if prop.name in _TEXT else prop.value
            parameters = (
                " parameters=" + json.dumps(prop.parameters, ensure_ascii=False, sort_keys=True)
                if prop.parameters
                else ""
            )
            output.append(
                f"Source {prop.name}{parameters}: " + json.dumps(value, ensure_ascii=False)
            )
        for index, child in enumerate(component.children, 1):
            render(child, f"{path}/{child.name}[{index}]")

    render(root, "VCALENDAR")
    text = "\n".join(output)
    if len(text) > MAX_OUTPUT_CHARS:
        raise CalendarInvalid("calendar extracted-text budget exceeded")
    return text
