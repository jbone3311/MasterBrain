import hashlib

import pytest
from test_sync import query

from email_brain.attachments import receive_attachments
from email_brain.connectors.jmap import ProtocolError
from email_brain.normalize import MAX_TEXT_CHARS, normalize
from email_brain.store import prepare_mime
from email_brain.synthetic import CATEGORIES, fake_email


@pytest.mark.parametrize("index", range(32))
def test_generated_email_roundtrip(index):
    raw = fake_email(index)
    assert raw == fake_email(index)
    normalized, attachments, quarantined = prepare_mime(raw)
    assert not quarantined and normalized
    assert f"marker{index:05d}" in normalized.text
    assert normalized.raw_sha256 == hashlib.sha256(raw).hexdigest()
    assert normalized.sender.endswith("@example.invalid")
    assert CATEGORIES[index % 8] in normalized.subject
    if index % 8 == 7:
        assert [part.status for part in attachments] == ["extracted", "deferred"]
        assert attachments[0].safe_filename == "report.csv"
        assert attachments[1].text == ""
    else:
        assert not attachments


@pytest.mark.parametrize("index", [-1, 100000, True, "1"])
def test_synthetic_generator_is_bounded(index):
    with pytest.raises(ValueError):
        fake_email(index)


def test_injection_stays_untrusted_text_not_an_action():
    normalized, attachments, quarantined = prepare_mime(fake_email(4))
    assert normalized and "IGNORE ALL RULES" in normalized.text
    assert not attachments and not quarantined
    assert not hasattr(normalized, "actions")


def test_projection_removes_nul_but_hash_preserves_exact_input():
    raw = (
        b"To: someone\x00@example.invalid\r\nMessage-ID: <id\x00@example.invalid>\r\n"
        b"Subject: nul\x00case\r\n\r\nbody\x00text"
    )
    normalized, _, quarantined = prepare_mime(raw)
    assert normalized and not quarantined
    assert "\x00" not in repr(normalized).replace("\\x00", "\x00")
    assert normalized.raw_sha256 == hashlib.sha256(raw).hexdigest()


def test_large_body_is_explicitly_truncated():
    result = normalize(b"Subject: large\r\n\r\n" + b"a" * (MAX_TEXT_CHARS + 1))
    assert result.truncated and len(result.text) == MAX_TEXT_CHARS


def test_malformed_is_quarantined_but_oversize_is_not_silently_accepted():
    assert prepare_mime(b"") == (None, [], True)
    assert prepare_mime(None) == (None, [], False)
    with pytest.raises(ValueError, match="storage limit"):
        prepare_mime(b"x" * 1048577)


def test_attachment_filename_nul_never_reaches_database_text():
    raw = (
        b"Content-Type: text/plain\r\nContent-Disposition: attachment; "
        b'filename="bad\x00.txt"\r\n\r\nhello'
    )
    assert "\x00" not in receive_attachments(raw)[0].original_filename


@pytest.mark.parametrize("limit", [0, 101, True, -1])
def test_provider_batch_limits_reject_invalid_settings(limit):
    with pytest.raises(ValueError):
        query().query_page(limit=limit)
    with pytest.raises(ValueError):
        query().changes("s", limit=limit)


def test_provider_cannot_exceed_requested_batch_size():
    with pytest.raises(ProtocolError):
        query().query_page(limit=1)
