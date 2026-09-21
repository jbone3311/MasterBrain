"""Synthetic documentation trees; no network, real mail or GitHub credentials."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_docs.py"
SPEC = importlib.util.spec_from_file_location("check_docs", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    for name in {*checker.REQUIRED, *(f"docs/{x}.md" for x in (*checker.PACK, *checker.GUIDES))}:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Overview\n", encoding="utf-8")
    return tmp_path


def test_repository_documents_pass() -> None:
    assert checker.check(SCRIPT.parents[1])[0] == []


def test_required_inventory(tree: Path) -> None:
    errors, documents, links = checker.check(tree)
    assert errors == [] and documents > 20 and links == 0


@pytest.mark.parametrize(
    "missing",
    [
        "docs/PRD.md",
        "docs/METHODS_GUIDE.md",
        "CONTRIBUTING.md",
        ".github/PULL_REQUEST_TEMPLATE.md",
        ".github/ISSUE_TEMPLATE/build.md",
    ],
)
def test_missing_required_guide_or_template(tree: Path, missing: str) -> None:
    (tree / missing).unlink()
    assert checker.check(tree)[0] == [f"Missing document: {missing}"]


@pytest.mark.parametrize(
    "link",
    [
        "docs/PRD.md#overview",
        "#overview",
        "docs/%50RD.md#over%76iew",
        "<docs/PRD.md#overview>",
        'docs/PRD.md#overview "Title"',
        "docs/",
    ],
)
def test_local_paths_and_fragments(tree: Path, link: str) -> None:
    (tree / "README.md").write_text(f"# Overview\n[Read]({link})\n", encoding="utf-8")
    assert checker.check(tree)[0] == []
    assert checker.check(tree)[2] == 1


@pytest.mark.parametrize(
    ("link", "reason"),
    [
        ("docs/missing.md", "broken local link"),
        ("docs/PRD.md#missing", "broken heading fragment"),
        ("#missing", "broken heading fragment"),
        ("../outside.md", "escapes repository"),
        ("%2e%2e/outside.md", "escapes repository"),
        ("/etc/passwd", "escapes repository"),
    ],
)
def test_invalid_links_fail(tree: Path, link: str, reason: str) -> None:
    (tree / "README.md").write_text(f"[Read]({link})\n", encoding="utf-8")
    assert len(checker.check(tree)[0]) == 1
    assert reason in checker.check(tree)[0][0]


def test_hidden_templates_and_same_repository_absolute_links(tree: Path) -> None:
    path = tree / ".github" / "PULL_REQUEST_TEMPLATE.md"
    path.write_text(f"[Read]({checker.REPOSITORY_DOC_URL}docs/PRD.md#overview)\n")
    assert checker.check(tree)[0] == []
    path.write_text(f"[Read]({checker.REPOSITORY_DOC_URL}docs/PRD.md#missing)\n")
    assert "broken heading fragment" in checker.check(tree)[0][0]


def test_relative_template_link_is_resolved_from_template(tree: Path) -> None:
    path = tree / ".github" / "ISSUE_TEMPLATE" / "build.md"
    path.write_text("[Read](../../docs/PRD.md#overview)\n")
    assert checker.check(tree)[0] == []


def test_external_links_are_not_claimed_verified(tree: Path) -> None:
    (tree / "README.md").write_text(
        "[URL](https://example.invalid/no-page#missing) [Mail](mailto:owner@example.invalid)\n"
    )
    assert checker.check(tree)[0] == []
    assert checker.check(tree)[2] == 0


def test_code_comments_frontmatter_do_not_create_links_or_headings(tree: Path) -> None:
    (tree / "README.md").write_text(
        "---\nfield: '[Read](missing.md)'\n---\n# Overview\n"
        "<!-- [Read](missing.md) -->\n`[Read](missing.md)`\n"
        "````markdown\n```\n# Hidden\n[Read](missing.md)\n````\n"
        "~~~text\n[Read](missing.md)\n~~~\n[Read](#overview)\n"
    )
    assert checker.check(tree)[0] == []
    assert checker.check(tree)[2] == 1
    assert checker.heading_ids((tree / "README.md").read_text()) == {"overview"}


def test_reference_destinations(tree: Path) -> None:
    path = tree / "README.md"
    path.write_text('[Read][guide]\n\n[guide]: docs/PRD.md#overview "Title"\n')
    assert checker.check(tree)[0] == []
    assert checker.check(tree)[2] == 1
    path.write_text("[Read][guide]\n\n[guide]: docs/PRD.md#missing\n")
    assert "broken heading fragment" in checker.check(tree)[0][0]


def test_encoded_spaces_and_parentheses_in_paths(tree: Path) -> None:
    (tree / "docs" / "With space (one).md").write_text("# Heading\n")
    (tree / "README.md").write_text(
        "[Read](<docs/With space (one).md#heading>)\n[Read](docs/With%20space%20(one).md#heading)\n"
    )
    assert checker.check(tree)[0] == []
    assert checker.check(tree)[2] == 2


def test_headings_duplicate_collisions_unicode_and_formatting() -> None:
    assert checker.heading_ids(
        "# Hello\n## Hello\n## Hello-1\n## What “learning” means\n"
        "## `Code` **first** &amp; [evidence](target.md) ###\n"
        'Café résumé\n===\n<a id="explicit-anchor"></a>\n'
    ) == {
        "hello",
        "hello-1",
        "hello-1-1",
        "what-learning-means",
        "code-first--evidence",
        "café-résumé",
        "explicit-anchor",
    }


def test_invalid_utf8_reported(tree: Path) -> None:
    (tree / "docs" / "PRD.md").write_bytes(b"\xff")
    assert "unreadable UTF-8" in checker.check(tree)[0][0]


def test_outside_symlink_is_not_read(tree: Path, tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside.md"
    outside.write_text("# Outside\n")
    (tree / "docs" / "outside.md").symlink_to(outside)
    (tree / "README.md").write_text("[Read](docs/outside.md)\n")
    errors = checker.check(tree)[0]
    assert len(errors) == 2
    assert any("symlink/escape" in error for error in errors)
    assert any("escapes repository" in error for error in errors)
