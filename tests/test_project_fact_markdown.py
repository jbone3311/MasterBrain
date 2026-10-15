"""Pure, fictional output-safety checks for the fact Markdown fragment."""

from masterbrain.project_facts import (
    _EXPORT_FIELD_BYTES,
    _fact_markdown_line,
    _markdown_json_text,
)


def test_untrusted_text_cannot_create_markdown_or_html():
    malicious = "hello\n# forged heading [click](https://bad.invalid) <script>x</script> `ticks`"
    row = {
        "id": "pfact_" + "1" * 32,
        "predicate": "deal.note",
        "assertion_status": "asserted",
        "value": malicious,
        "source_quote": malicious,
        "quote_evidence_id": "evidence_" + "2" * 32,
    }
    line = _fact_markdown_line(row)
    assert line.count("\n") == 1
    assert "\n# forged" not in line
    assert "<script>" not in line
    assert "[click](https://bad.invalid)" not in line
    assert "&lt;script&gt;" in line
    assert "evidence_" + "2" * 32 in line
    assert _fact_markdown_line(row) == line


def test_quote_prefix_is_bounded_at_utf8_boundary_and_labelled():
    quote = "é" * (_EXPORT_FIELD_BYTES + 10)
    row = {
        "id": "pfact_" + "1" * 32,
        "predicate": "deal.note",
        "assertion_status": "asserted",
        "value": "fictional value",
        "source_quote": quote,
        "quote_evidence_id": "evidence_" + "2" * 32,
    }
    line = _fact_markdown_line(row)
    assert "quote prefix" in line
    assert "exact quote" not in line
    assert "\\u00e9" in line
    assert len(line.encode("utf-8")) < 2_000


def test_json_escaped_single_line_represents_control_characters():
    escaped = _markdown_json_text("one\ntwo\tthree")
    assert "\n" not in escaped
    assert "\\\\n" in escaped
    assert "\\\\t" in escaped
