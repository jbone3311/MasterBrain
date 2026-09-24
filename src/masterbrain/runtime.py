"""Dependency-free interpreter preflight; never downgrade security parsing."""

from __future__ import annotations

import email.utils
import sys


def require_strict_email_parser() -> None:
    """Refuse unsupported/broken runtimes before loading API or CLI capabilities."""
    message = (
        "MasterBrain requires security-patched email.utils strict parsing "
        "(Python 3.11.10+, 3.12.6+, or a supported newer release). "
        f"Current interpreter: {sys.version.split()[0]}. "
        "Upgrade Python and recreate the environment; permissive parsing is not supported."
    )
    if getattr(email.utils, "supports_strict_parsing", False) is not True:
        raise RuntimeError(message)
    try:
        result = email.utils.parseaddr("Runtime Probe <probe@example.invalid>", strict=True)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(message) from exc
    if result != ("Runtime Probe", "probe@example.invalid"):
        raise RuntimeError(message)


# Import caching performs this automatic probe once per process. Both public
# package initializers import this module before application/worker dependencies.
require_strict_email_parser()
STRICT_EMAIL_PARSER_AVAILABLE = True
