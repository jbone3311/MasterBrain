"""The coherent mailbox's actual bytes through existing provider contract drivers."""

from types import SimpleNamespace

import pytest
from test_attachment_provider_formats import (
    test_realistic_attachment_bytes_survive_gmail_raw_wrapper as check_gmail,
)
from test_attachment_provider_formats import (
    test_realistic_attachment_bytes_survive_graph_mime_endpoint as check_graph,
)
from test_attachment_provider_formats import (
    test_realistic_attachment_bytes_survive_imap_literal as check_imap,
)
from test_attachment_provider_formats import (
    test_realistic_attachment_bytes_survive_jmap_blob_download as check_jmap,
)

from email_brain.synthetic_mailbox import project_events


@pytest.mark.parametrize(
    "event", [e for e in project_events(42, 0) if e.kind == "created"], ids=lambda e: e.filename
)
@pytest.mark.parametrize(
    "driver",
    [check_gmail, check_graph, check_imap, check_jmap],
    ids=["gmail", "graph", "imap", "jmap"],
)
def test_coherent_source_bytes_survive_mock_provider(event, driver):
    driver(SimpleNamespace(raw=event.item.raw, name=event.filename))
