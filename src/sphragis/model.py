"""Data model for governance decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Operation(str, Enum):
    """Operations a downstream AI system may attempt on a document."""

    EXTRACT = "extract"
    RAG_INDEX = "rag_index"
    RAG_RETRIEVE = "rag_retrieve"
    TRAIN = "train"
    SHARE_DOWNSTREAM = "share_downstream"


class Verdict(str, Enum):
    ALLOW = "allow"
    ALLOW_WITH_OBLIGATIONS = "allow_with_obligations"
    DENY = "deny"
    UNSPECIFIED = "unspecified"


@dataclass
class Governance:
    """Flat view of governance elements found in a DocLang ``<head>``.

    Values are stored as strings exactly as they appear in the document.
    Elements with a ``unit`` attribute are stored as ``"<value> <unit>"``.
    Repeated elements (e.g. ``<license>``) are stored as lists.
    """

    elements: dict[str, object] = field(default_factory=dict)

    def get(self, name: str) -> str | None:
        value = self.elements.get(name)
        if isinstance(value, list):
            return value[0] if value else None
        return value

    def get_bool(self, name: str) -> bool | None:
        value = self.get(name)
        if value is None:
            return None
        v = value.strip().lower()
        if v in ("true", "yes", "1"):
            return True
        if v in ("false", "no", "0"):
            return False
        return None


@dataclass
class Decision:
    """Outcome of evaluating one operation against one document."""

    operation: Operation
    verdict: Verdict
    reasons: list[str] = field(default_factory=list)
    obligations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "operation": self.operation.value,
            "verdict": self.verdict.value,
            "reasons": self.reasons,
            "obligations": self.obligations,
        }
