#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if ! command -v uv >/dev/null 2>&1; then
  echo "Install uv, then reopen this launcher. Docker Desktop or PostgreSQL 17 is also required."
  read -r -p "Press Return to close. " _
  exit 1
fi
uv sync --locked --extra dev --python '>=3.13,<3.15' --no-editable --reinstall-package masterbrain
uv run --no-sync python tests/cross_source_preview.py --synthetic-preview "$@"
