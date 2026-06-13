"""sphragis: deterministic evaluation of DocLang governance metadata."""

from .model import Decision, Governance, Operation, Verdict
from .parser import parse_governance
from .policy import evaluate

__all__ = ["Decision", "Governance", "Operation", "Verdict", "parse_governance", "evaluate"]
__version__ = "0.0.1"
