#!/bin/sh
# cc_session_banner.sh — a Product's SessionStart hook: name the session kind before anything else.
#
# Owner, 2026-10-23: "when I'm running a background session or a master brain session, that you
# say ... we are currently in a factory session or some sort of". The Factory's own boot hook
# already prints "🏭 FACTORY SESSION"; a Product printed nothing until `Q: Start` ran the bind.
# This runs at every session open (startup, resume, clear, compact), prints the Factory's
# session-kind banner for this Product, and tells Claude to lead its first reply with that line.
#
# Installed by the Factory (`factory_launch.py install-hooks`) from
# CW-Factory/_SYSTEM/templates/product_session_banner.sh — never edit the Product copy; propose
# a change to the template. Read-only: it writes nothing. It never fails the session: a missing
# Factory or Python still prints a plain banner and exits 0.
root="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
tool="$root/../CW-Factory/_SYSTEM/tools/session_intent.py"
banner=""
if [ -f "$tool" ] && command -v python3 >/dev/null 2>&1; then
  banner="$(python3 "$tool" banner --product "$root" 2>/dev/null | head -1)"
fi
if [ -z "$banner" ]; then
  name="$(python3 -c 'import json,sys; m=json.load(open(sys.argv[1])); print(m.get("display_name") or m.get("system_name") or m.get("system_id") or "")' "$root/MANIFEST.json" 2>/dev/null)"
  [ -z "$name" ] && name="$(basename "$root")"
  banner="📦 ${name#CW-} PRODUCT SESSION — the Factory was not found beside this repo; Q: Start will say why"
fi
echo "SESSION KIND: $banner"
echo "Lead your FIRST reply of this session with this line, as it reads, before anything else"
echo "(FACTORY.md §3, Session kind). Say it once; do not repeat it on later turns."
exit 0
