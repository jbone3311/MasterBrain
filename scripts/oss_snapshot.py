"""Refresh public GitHub project-health evidence; never reads private repositories or tokens.

Uses the existing gh login. Only aggregate public metadata is written to the report.
Commit counts cover the default branch in the trailing 90 days, capped at 1,000.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPOSITORIES = (
    "queelius/mail-memex",
    "notmuch/notmuch",
    "mailgun/talon",
    "mjs/imapclient",
    "ikvk/imap_tools",
    "asg017/sqlite-vec",
    "pgvector/pgvector",
    "ollama/ollama",
    "ggml-org/llama.cpp",
    "getzep/graphiti",
    "elie222/inbox-zero",
    "Mail-0/Zero",
)


def get(path: str):
    result = subprocess.run(
        ["gh", "api", path], capture_output=True, text=True, timeout=45, check=True
    )
    return json.loads(result.stdout)


def inspect(repo: str) -> dict:
    metadata = get(f"repos/{repo}")
    if metadata.get("private"):
        raise ValueError("This report only permits public repositories")
    since = (datetime.now(UTC) - timedelta(days=90)).isoformat()
    latest = get(f"repos/{repo}/commits?per_page=1")
    count = 0
    capped = False
    for page in range(1, 11):
        commits = get(f"repos/{repo}/commits?per_page=100&page={page}&since={since}")
        count += len(commits)
        if len(commits) < 100:
            break
        if page == 10:
            capped = True
    commit = latest[0] if latest else None
    return {
        "repository": repo,
        "url": metadata["html_url"],
        "stars": metadata["stargazers_count"],
        "forks": metadata["forks_count"],
        "subscribers": metadata["subscribers_count"],
        "archived": metadata["archived"],
        "default_branch": metadata["default_branch"],
        "license_metadata": (metadata.get("license") or {}).get("spdx_id"),
        "latest_commit_at": commit["commit"]["committer"]["date"] if commit else None,
        "latest_commit_sha": commit["sha"] if commit else None,
        "commits_last_90_days": count,
        "count_is_lower_bound": capped,
        "activity_note": (
            "Default-branch commits include bots/merges; not an adoption or quality score."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(inspect, REPOSITORIES))
    report = {"observed_at": datetime.now(UTC).isoformat(), "window_days": 90, "repositories": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
