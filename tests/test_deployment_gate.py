"""The CI structural gate must not duplicate its preceding full test step."""

from types import SimpleNamespace

from scripts import deployment_gate


def test_structural_gate_skips_only_its_duplicate_pytest_run(monkeypatch, capsys) -> None:
    calls = []

    def fake_run(command, **kwargs):
        calls.append(tuple(command))
        if command[:2] == ["git", "ls-files"]:
            return SimpleNamespace(stdout=b"")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(deployment_gate.subprocess, "run", fake_run)
    deployment_gate.main(structural_only=True)
    assert calls == [("git", "ls-files", "-z")]
    assert "repository structural gate" in capsys.readouterr().out

    calls.clear()
    deployment_gate.main()
    assert calls[0] == ("git", "ls-files", "-z")
    assert calls[1][-3:] == ("-m", "pytest", "-q")
    assert "repository quality gate" in capsys.readouterr().out
