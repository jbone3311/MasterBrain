"""All legacy Email operator commands forward the explicit login fence."""

import sys
from unittest.mock import Mock

import pytest

from email_brain import cli


@pytest.mark.parametrize(
    "command,controller,extra",
    (
        ("sync-read", "run_read_controller", ("--allow-provider-read",)),
        ("process-jobs", "run_controller", ()),
        ("process-documents", "run_document_controller", ()),
    ),
)
@pytest.mark.parametrize("bound", (False, True))
def test_cli_forwards_tenant_bound_option(command, controller, extra, bound, monkeypatch):
    run = Mock(return_value={"attention_required": False})
    monkeypatch.setattr(cli, controller, run)
    monkeypatch.setenv("EMAIL_BRAIN_DSN", "synthetic")
    argv = ["email-brain", command, "--config", "/fictional/operator.json", *extra]
    if bound:
        argv.append("--tenant-bound-db")
    monkeypatch.setattr(sys, "argv", argv)
    cli.main()
    assert run.call_args.kwargs["tenant_bound_db"] is bound
