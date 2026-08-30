"""sphragis: deterministic evaluation of DocLang governance metadata."""

from .model import Decision, Governance, Operation, Verdict
from .parser import (
    DOCLANG_NAMESPACE,
    SPEC_VERSION,
    SUPPORTED_SPEC_VERSIONS,
    NotADocLangDocumentError,
    UnsupportedSpecVersionError,
    parse_governance,
)
from .policy import evaluate

__all__ = [
    "DOCLANG_NAMESPACE",
    "SPEC_VERSION",
    "SUPPORTED_SPEC_VERSIONS",
    "Decision",
    "Governance",
    "NotADocLangDocumentError",
    "Operation",
    "UnsupportedSpecVersionError",
    "Verdict",
    "evaluate",
    "parse_governance",
]
__version__ = "0.0.2"
