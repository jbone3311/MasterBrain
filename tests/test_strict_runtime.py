"""Security parser behavior, positive rule effects and loud startup regressions."""

import email.utils
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from packaging.specifiers import SpecifierSet

from email_brain.rules import active
from masterbrain.runtime import STRICT_EMAIL_PARSER_AVAILABLE, require_strict_email_parser

ROOT = Path(__file__).resolve().parents[1]
ENTRY = {
    "proposal_id": "synthetic-rule",
    "version": 2,
    "payload": {
        "kind": "rule",
        "sender_domain": "example.invalid",
        "category": "investment",
        "canonical_mailbox": "review",
    },
}


def test_interpreter_explicitly_supports_strict_parsing():
    assert STRICT_EMAIL_PARSER_AVAILABLE is True
    assert getattr(email.utils, "supports_strict_parsing", False) is True
    require_strict_email_parser()


@pytest.mark.parametrize("sender", ["a@example.invalid", "Alice <a@EXAMPLE.INVALID>"])
def test_valid_sender_has_exact_effects_not_just_success(sender):
    assert active.classify([ENTRY], 7, sender) == {
        "rules_revision": 7,
        "effects": {"category": "investment", "canonical_mailbox": "review"},
        "matched_rule_versions": ["synthetic-rule:v2"],
        "virtual_only": True,
    }


@pytest.mark.parametrize(
    "sender",
    [
        "",
        "a@example.invalid,b@evil.invalid",
        "a@example.invalid<evil",
        "a@example.invalid)",
        "a@example.invalid>",
        "a@example.invalid; b@evil.invalid",
        "<a@example.invalid> <b@evil.invalid>",
        "a@example.invalid (unfinished",
    ],
)
def test_strict_rejections_are_empty_tuples_and_never_match(sender):
    # These are CPython strict-mode rejection cases, not a claim of full RFC validation.
    assert email.utils.parseaddr(sender, strict=True) == ("", "")
    result = active.classify([ENTRY], 7, sender)
    assert result["effects"] == {}
    assert result["matched_rule_versions"] == []


def test_per_message_value_error_fails_closed(monkeypatch):
    def malformed(*args, **kwargs):
        raise ValueError("synthetic malformed sender")

    monkeypatch.setattr(active, "parseaddr", malformed)
    assert active.classify([ENTRY], 7, "a@example.invalid")["effects"] == {}


def test_per_message_type_error_is_not_swallowed(monkeypatch):
    def broken(*args, **kwargs):
        raise TypeError("synthetic interpreter or programming defect")

    monkeypatch.setattr(active, "parseaddr", broken)
    with pytest.raises(TypeError, match="programming defect"):
        active.classify([ENTRY], 7, "a@example.invalid")


@pytest.mark.parametrize("marker", [False, None])
def test_missing_capability_refuses_without_calling_a_legacy_parser(monkeypatch, marker):
    if marker is None:
        monkeypatch.delattr(email.utils, "supports_strict_parsing")
    else:
        monkeypatch.setattr(email.utils, "supports_strict_parsing", marker)

    def forbidden(*args, **kwargs):
        pytest.fail("No permissive fallback is allowed")

    monkeypatch.setattr(email.utils, "parseaddr", forbidden)
    with pytest.raises(RuntimeError, match="security-patched"):
        require_strict_email_parser()


def test_falsely_advertised_capability_refuses_without_fallback(monkeypatch):
    calls = []

    def unsupported(address, *, strict=True):
        calls.append(strict)
        raise TypeError("unsupported keyword")

    monkeypatch.setattr(email.utils, "supports_strict_parsing", True)
    monkeypatch.setattr(email.utils, "parseaddr", unsupported)
    with pytest.raises(RuntimeError, match="Upgrade Python"):
        require_strict_email_parser()
    assert calls == [True]


def test_broken_valid_address_probe_refuses(monkeypatch):
    monkeypatch.setattr(email.utils, "parseaddr", lambda *args, **kwargs: ("", ""))
    with pytest.raises(RuntimeError, match="security-patched"):
        require_strict_email_parser()


@pytest.mark.parametrize("package", ["masterbrain", "email_brain"])
def test_both_package_startups_refuse_before_serving(package):
    code = (
        "import email.utils\n"
        "email.utils.supports_strict_parsing = False\n"
        f"import {package}\n"
        "print('UNSAFE_STARTUP_SUCCEEDED')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode != 0
    assert "requires security-patched" in result.stderr
    assert "UNSAFE_STARTUP_SUCCEEDED" not in result.stdout


def test_both_package_imports_automatically_probe_only_once():
    code = """
import email.utils
original = email.utils.parseaddr
calls = []
def counted(*args, **kwargs):
    calls.append(kwargs)
    return original(*args, **kwargs)
email.utils.parseaddr = counted
import masterbrain
import email_brain
assert calls == [{'strict': True}], calls
"""
    subprocess.run(
        [sys.executable, "-c", code],
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )


def test_package_and_lock_exclude_every_known_unsupported_patch():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    requirement = SpecifierSet(project["project"]["requires-python"])
    assert requirement == SpecifierSet(lock["requires-python"])
    for version in ["3.10.99", "3.11.0", "3.11.9", *(f"3.12.{n}" for n in range(6))]:
        assert version not in requirement, version
    for version in ["3.11.10", "3.11.16", "3.12.6", "3.12.14", "3.13.0", "3.14.0"]:
        assert version in requirement, version
