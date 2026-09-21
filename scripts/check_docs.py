"""Verify local Markdown links and the requested document-pack inventory."""

import re
from pathlib import Path

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


def main() -> None:
    errors = []
    for name in (*PACK, *GUIDES):
        if not (ROOT / "docs" / f"{name}.md").is_file():
            errors.append(f"Missing document: {name}")
    for path in [*ROOT.glob("*.md"), *(ROOT / "docs").rglob("*.md")]:
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
            if "://" in target or target.startswith("#"):
                continue
            relative = target.split("#", 1)[0].strip("<>")
            if relative and not (path.parent / relative).exists():
                errors.append(f"{path.relative_to(ROOT)}: broken local link {target}")
    if errors:
        raise SystemExit("\n".join(errors))
    print("PASS: all 16 pack documents, 4 product guides and local Markdown links")


if __name__ == "__main__":
    main()
