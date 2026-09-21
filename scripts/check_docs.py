"""Offline inventory/link checks for the repository's documented Markdown subset."""

import html
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PACK = (
    "README",
    "PRD",
    "ARCHITECTURE",
    "SECURITY",
    "DATA_MODEL",
    "API_MCP_SPEC",
    "RULES_AND_FEEDBACK",
    "EMAIL_PROVIDER_CONNECTORS",
    "AI_MODEL_STRATEGY",
    "OSS_EVALUATION",
    "DEPLOYMENT",
    "ROADMAP",
    "TESTING_AND_EVALS",
    "OPERATIONS_RUNBOOK",
    "DECISIONS",
    "FACTORY_HANDOFF",
)
GUIDES = ("GAME_PLAN", "FEATURES_AND_METHODS", "CODE_MAP", "TEST_MAILBOX_PLAN")
REQUIRED = (
    "README.md",
    "AGENTS.md",
    "PRODUCT.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "docs/README.md",
    "docs/PRODUCT_WALKTHROUGH.md",
    "docs/METHODS_GUIDE.md",
    "docs/DOCUMENTATION_STANDARD.md",
    "docs/IMPLEMENTATION_STATUS.md",
    "docs/BUILD_RECEIPT.md",
    "docs/RELEASE_ACCEPTANCE.md",
    "docs/DOCUMENT_PROCESSING.md",
    "docs/DOCUMENT_CONTROLLER.md",
    ".github/ISSUE_TEMPLATE/build.md",
    ".github/ISSUE_TEMPLATE/decision.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
)
REPOSITORY_DOC_URL = "https://github.com/jbone3311/CW-EmailBrain/blob/main/"
DESTINATION = r"(<[^>\n]+>|[^\s()]+(?:\([^()\n]*\)[^\s()]*)*)"
INLINE_LINK = re.compile(r"!?\[[^\]\n]*\]\(\s*" + DESTINATION + r'(?:\s+"[^"\n]*")?\s*\)')
REFERENCE = re.compile(r"^ {0,3}\[([^\]\n]+)\]:\s*" + DESTINATION, re.MULTILINE)


def prose(text: str) -> str:
    """Remove frontmatter/comments/fences, preserving line boundaries."""
    text = re.sub(r"\A---\n.*?\n---(?:\n|$)", "", text, count=1, flags=re.DOTALL)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    lines = []
    fence = ""
    for line in text.splitlines():
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence:
            if re.fullmatch(
                r" {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*", line
            ):
                fence = ""
            lines.append("")
        elif marker:
            fence = marker[1]
            lines.append("")
        else:
            lines.append(line)
    return "\n".join(lines)


def heading_ids(text: str) -> set[str]:
    """GitHub-style IDs for our ATX/setext headings; not a full Markdown renderer."""
    visible = prose(text)
    headings = []
    lines = visible.splitlines()
    for index, line in enumerate(lines):
        atx = re.match(r"^ {0,3}#{1,6}\s+(.+?)\s*$", line)
        if atx:
            headings.append(re.sub(r"\s+#+\s*$", "", atx[1]))
        elif index and re.fullmatch(r" {0,3}(?:=+|-+)\s*", line) and lines[index - 1].strip():
            headings.append(lines[index - 1].strip())
    ids: set[str] = set()
    for heading in headings:
        heading = re.sub(r"!?\[([^\]]+)\]\([^)]*\)", r"\1", heading)
        heading = html.unescape(re.sub(r"<[^>]*>", "", heading)).lower()
        # Formatting markers do not appear in the rendered heading.
        heading = heading.replace("`", "").replace("*", "")
        slug = "".join(
            char for char in heading if char in "-_ " or unicodedata.category(char)[0] in "LNM"
        ).replace(" ", "-")
        candidate, suffix = slug, 0
        while candidate in ids:
            suffix += 1
            candidate = f"{slug}-{suffix}"
        ids.add(candidate)
    ids.update(re.findall(r'<a\s+(?:id|name)=["\']([^"\']+)["\']', visible))
    return ids


def destinations(text: str) -> list[str]:
    visible = re.sub(r"(`+).*?\1", "", prose(text), flags=re.DOTALL)
    return [match[1].strip("<>") for match in INLINE_LINK.finditer(visible)] + [
        match[2].strip("<>") for match in REFERENCE.finditer(visible)
    ]


def check(root: Path) -> tuple[list[str], int, int]:
    root = root.resolve()
    errors: list[str] = []
    required = {*REQUIRED, *(f"docs/{name}.md" for name in (*PACK, *GUIDES))}
    for name in sorted(required):
        if not (root / name).is_file():
            errors.append(f"Missing document: {name}")
    paths = sorted(
        {*root.glob("*.md"), *(root / "docs").rglob("*.md"), *(root / ".github").rglob("*.md")}
    )
    contents: dict[Path, str] = {}
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            errors.append(f"{path.relative_to(root)}: documentation symlink/escape")
            continue
        try:
            contents[path] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            errors.append(f"{path.relative_to(root)}: unreadable UTF-8 document")
    anchors = {path: heading_ids(content) for path, content in contents.items()}
    local_links = 0
    for path, content in contents.items():
        for target in destinations(content):
            original = target
            base = path.parent
            if target.startswith(REPOSITORY_DOC_URL):
                target, base = target.removeprefix(REPOSITORY_DOC_URL), root
            try:
                parsed = urlsplit(target)
            except ValueError:
                errors.append(f"{path.relative_to(root)}: malformed link {original}")
                continue
            if parsed.scheme or parsed.netloc:
                continue
            local_links += 1
            relative = unquote(parsed.path)
            destination = (base / relative).resolve() if relative else path
            label = f"{path.relative_to(root)}: {original}"
            if Path(relative).is_absolute() or not destination.is_relative_to(root):
                errors.append(f"{label}: destination escapes repository")
            elif not destination.exists():
                errors.append(f"{label}: broken local link")
            elif parsed.fragment and destination.suffix == ".md":
                if destination not in anchors:
                    errors.append(f"{label}: Markdown target is outside checked documentation")
                elif unquote(parsed.fragment) not in anchors[destination]:
                    errors.append(f"{label}: broken heading fragment")
    return errors, len(contents), local_links


def main() -> None:
    errors, documents, links = check(ROOT)
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"PASS: required inventory; {documents} Markdown files; {links} local paths/fragments")


if __name__ == "__main__":
    main()
