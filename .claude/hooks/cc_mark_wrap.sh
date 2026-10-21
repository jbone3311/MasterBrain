#!/usr/bin/env bash
# Stamp "a real wrap happened at this exact commit". Run as the LAST step of Q: End,
# after the commit+push. cc_precompact_wrap.sh refuses a manual /compact unless the
# stamped sha == current HEAD, so a moved HEAD means the wrap is stale.
# Also installed, byte-identical, into every Product as .claude/hooks/cc_mark_wrap.sh by
# `factory_launch.py install-hooks` (ALL-PRODUCTS-011): there the root resolves to the
# Product, and its stamp is the token session_spine's once-per-session guard reads.
set -uo pipefail
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$ROOT" 2>/dev/null || exit 0
STATE="$ROOT/.claude/state"; mkdir -p "$STATE" 2>/dev/null

# REFUSE to stamp a DIRTY tree (S163 fix). A stamp records "the wrap was saved at
# this exact commit"; if TRACKED files are still uncommitted, the stamp captures a
# HEAD that EXCLUDES them, and the follow-up commit that saves them moves HEAD past
# the stamp — which is exactly the desync cc_precompact_wrap.sh then blocks on.
# The terminal pass (run --kind end --terminal) regenerates ACTIVE_ACTORS.md + the
# greeting, so this bit repeatedly: commit-then-stamp with a file left behind.
# Untracked files (gitignored generated *.html, scratch) do NOT block — only tracked
# modifications, because only those belong in the wrap commit.
DIRTY="$(git status --porcelain --untracked-files=no 2>/dev/null)"
if [ -n "$DIRTY" ]; then
    echo "🛑 wrap NOT stamped — the tree has uncommitted TRACKED changes:" >&2
    echo "$DIRTY" | sed 's/^/     /' | head -20 >&2
    echo "   A stamp over a dirty tree records a HEAD that excludes these files; the" >&2
    echo "   commit that saves them then moves HEAD past the stamp and re-blocks /compact." >&2
    echo "   Fix: commit the wrap-generated files (git add -u + commit), THEN re-run this." >&2
    exit 1
fi

SHA="$(git rev-parse HEAD 2>/dev/null || echo none)"
printf '%s %s\n' "$SHA" "$(date -u +%FT%TZ)" > "$STATE/last-wrap"
rm -f "$STATE/UNFINISHED.md" 2>/dev/null
echo "✓ wrap stamped at ${SHA:0:7} — /compact is now unblocked."
