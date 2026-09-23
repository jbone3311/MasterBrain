"""Local runs exclude every durability guarantee; say so, out loud, at the end.

WHY THIS EXISTS. `pytest -q` on a developer machine prints `2,211 passed` and nothing
else. The 392 tests that did not run are exactly the ones covering persistence, row-level
security, immutability triggers and index generations — i.e. every guarantee the product
is built on. The skip reasons print only under `-rs`, which nobody types.

CI is already honest: `tests/test_postgres.py` turns a missing DSN into `pytest.fail` when
`CI` is set, so the durability tier cannot silently evaporate there. This closes the local
half, and it only prints — it never changes an exit code, because a developer without
Docker should still be able to run the suite.
"""

from __future__ import annotations

import os


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    skipped = len(terminalreporter.stats.get("skipped", []))
    if not skipped:
        return
    if os.environ.get("EMAIL_BRAIN_TEST_ADMIN_DSN"):
        return          # the durability tier ran; the denominator is not missing
    passed = len(terminalreporter.stats.get("passed", []))
    terminalreporter.write_sep("=", "DENOMINATOR", red=True)
    terminalreporter.write_line(
        f"{passed} passed, but {skipped} test(s) DID NOT RUN (no "
        f"EMAIL_BRAIN_TEST_ADMIN_DSN). This green covers no persistence, RLS, "
        f"immutability or index-generation guarantee.",
        red=True,
    )
    terminalreporter.write_line(
        "  Run them with: EMAIL_BRAIN_TEST_ADMIN_DSN=postgresql://... uv run pytest -q",
        red=True,
    )
