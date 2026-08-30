"""sphragis: deterministic evaluation of DocLang governance metadata."""

from .model import Decision, Governance, Operation, Verdict
from .parser import (
    SPEC_VERSION,
    SUPPORTED_SPEC_VERSIONS,
    UnsupportedSpecVersionError,
    parse_governance,
)
from .policy import evaluate

__all__ = [
    "Decision",
    "Governance",
    "Operation",
    "Verdict",
    "SPEC_VERSION",
    "SUPPORTED_SPEC_VERSIONS",
    "UnsupportedSpecVersionError",
    "parse_governance",
    "evaluate",
]
__version__ = "0.0.2"
