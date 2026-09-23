"""Make the disposable-PostgreSQL test denominator visible in local and CI runs."""

from typing import Any

_postgres_tests: set[str] = set()


def pytest_collection_modifyitems(items: list[Any]) -> None:
    _postgres_tests.clear()
    _postgres_tests.update(
        item.nodeid for item in items if item.get_closest_marker("postgres") is not None
    )


def pytest_terminal_summary(terminalreporter: Any) -> None:
    executed = {
        report.nodeid
        for category in ("passed", "failed")
        for report in terminalreporter.stats.get(category, ())
        if report.when == "call" and report.nodeid in _postgres_tests
    }
    skipped = {
        report.nodeid
        for report in terminalreporter.stats.get("skipped", ())
        if report.nodeid in _postgres_tests
    }
    terminalreporter.write_line(
        "PostgreSQL-marked tests: "
        f"{len(_postgres_tests)} collected, {len(executed)} executed, "
        f"{len(skipped)} skipped (skips are not passes)"
    )
