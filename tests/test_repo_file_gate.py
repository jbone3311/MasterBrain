"""The CI structural gate must not duplicate its preceding full test step."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace


def load_gate():
    path = Path(__file__).resolve().parents[1] / "scripts" / "repo_file_gate.py"
    spec = importlib.util.spec_from_file_location("repo_file_gate_for_test", path)
    assert spec is not None and spec.loader is not None
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    return gate


def test_structural_gate_skips_only_its_duplicate_pytest_run(monkeypatch, capsys) -> None:
    repo_file_gate = load_gate()
    calls = []

    def fake_run(command, **kwargs):
        calls.append(tuple(command))
        if command[:2] == ["git", "ls-files"]:
            return SimpleNamespace(stdout=b"")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(repo_file_gate.subprocess, "run", fake_run)
    repo_file_gate.main(structural_only=True)
    assert calls == [("git", "ls-files", "-z")]
    assert "repository structural gate" in capsys.readouterr().out

    calls.clear()
    repo_file_gate.main()
    assert calls[0] == ("git", "ls-files", "-z")
    assert calls[1][-3:] == ("-m", "pytest", "-q")
    assert "repository quality gate" in capsys.readouterr().out
