"""MasterBrain product package.

The legacy ``email_brain`` package remains the internal Email source capability.
New shared capabilities are introduced under this package as they pass donor parity.
"""

from masterbrain.runtime import STRICT_EMAIL_PARSER_AVAILABLE as STRICT_EMAIL_PARSER_AVAILABLE

__version__ = "0.2.0a2"

__all__ = ["datacore"]
