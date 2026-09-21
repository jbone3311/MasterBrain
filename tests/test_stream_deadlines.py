"""Transport fragmentation must not postpone application response budgets."""

from collections.abc import Iterator
from functools import partial
from types import SimpleNamespace

import httpx
import pytest

from email_brain import local_model
from email_brain.connectors import fastmail, gmail, graph


class FragmentedStream(httpx.SyncByteStream):
    def __init__(self, mode: str, clock: list[float], deadline: int) -> None:
        self.mode = mode
        self.clock = clock
        self.deadline = deadline
        self.closed = False

    def __iter__(self) -> Iterator[bytes]:
        if self.mode == "slow":
            self.clock[0] = 1
            yield b"{"
            self.clock[0] = self.deadline + 1
            yield b'"'
            raise AssertionError("read beyond expired deadline while buffering")
        if self.mode == "empty":
            self.clock[0] = self.deadline + 1
            return
        for byte in b'{"ok":true}':
            yield bytes([byte])

    def close(self) -> None:
        self.closed = True


@pytest.mark.parametrize("adapter", ["fastmail", "gmail", "graph", "ollama"])
@pytest.mark.parametrize("mode", ["slow", "empty", "valid", "overflow"])
def test_fragmented_response_budgets(
    adapter: str, mode: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = [0.0]
    module = {"fastmail": fastmail, "gmail": gmail, "graph": graph, "ollama": local_model}[
        adapter
    ]
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    stream = FragmentedStream(mode, clock, 60 if adapter == "ollama" else 30)
    transport = httpx.MockTransport(lambda _: httpx.Response(200, stream=stream))
    token = "fictional-test-credential"
    limit = 4 if mode == "overflow" else 1024
    client = None
    try:
        if adapter == "fastmail":
            client = fastmail.FastmailReadClient(token, transport=transport)
            call = partial(client._request, "GET", fastmail.SESSION, byte_limit=limit)
            unavailable, rejected = fastmail.ProviderUnavailable, fastmail.ProtocolError
        elif adapter == "gmail":
            monkeypatch.setattr(gmail, "MAX_JSON_BYTES", limit)
            client = gmail.GmailReadClient(token, "owner@example.test", transport=transport)
            call = partial(client._get, "profile")
            unavailable, rejected = gmail.GmailUnavailable, gmail.GmailProtocolError
        elif adapter == "graph":
            monkeypatch.setattr(graph, "MAX_RAW_BYTES", limit)
            client = graph.GraphReadClient("synthetic", token, transport=transport)
            path = "/v1.0/users/synthetic/messages"
            call = partial(client._get, graph.ORIGIN + path, path)
            unavailable, rejected = fastmail.ProviderUnavailable, graph.ProtocolError
        else:
            monkeypatch.setattr(local_model, "MAX_RESPONSE_BYTES", limit)
            config = local_model.LocalModelConfig("synthetic:fixture", "a" * 64, True)
            client = local_model.OllamaLocalClassifier(config, transport=transport)
            call = partial(client._request, "tags", 0)
            unavailable, rejected = (
                local_model.LocalModelUnavailable,
                local_model.LocalModelRejected,
            )
        if mode in {"slow", "empty"}:
            with pytest.raises(unavailable, match="deadline"):
                call()
        elif mode == "overflow":
            with pytest.raises(rejected, match="exceeds"):
                call()
        else:
            expected = b'{"ok":true}' if adapter in {"fastmail", "graph"} else {"ok": True}
            assert call() == expected
        assert stream.closed
    finally:
        if client is not None:
            client.close()
