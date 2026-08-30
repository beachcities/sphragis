"""Regression tests.

Covers three fixed regressions plus root spec-version checking:

1. Strict posture must require EVERY gate of a multi-gate operation to be
   explicitly true (e.g. ``rag_permitted`` alone must not allow ``rag_index``).
2. Documents using a default XML namespace must parse.
3. Declared prohibitions in obligation slots (e.g. ``rag_caching_allowed``
   = false) must be surfaced in the decision, not silently dropped.
4. The root ``version`` attribute is surfaced and validated (spec version,
   e.g. ``0.7`` — distinct from the reference-toolkit release, e.g. v0.7.3).
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sphragis import (
    Operation,
    SUPPORTED_SPEC_VERSIONS,
    UnsupportedSpecVersionError,
    Verdict,
    evaluate,
    parse_governance,
)


def _parse(xml: str):
    with tempfile.NamedTemporaryFile(
        "w", suffix=".dclg", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(xml)
        name = fh.name
    try:
        return parse_governance(name)
    finally:
        Path(name).unlink(missing_ok=True)


class StrictMultiGateTests(unittest.TestCase):
    """Regression 1: one true gate out of several must not allow in strict."""

    PARTIAL = """
    <doclang>
      <head>
        <rag_permitted>true</rag_permitted>
      </head>
    </doclang>
    """

    FULL = """
    <doclang>
      <head>
        <rag_permitted>true</rag_permitted>
        <rag_indexing_allowed>true</rag_indexing_allowed>
      </head>
    </doclang>
    """

    def test_partial_gates_denied_in_strict(self):
        gov = _parse(self.PARTIAL)
        d = evaluate(gov, Operation.RAG_INDEX, strict=True)
        self.assertEqual(d.verdict, Verdict.DENY)
        self.assertTrue(
            any("rag_indexing_allowed" in r for r in d.reasons),
            d.reasons,
        )

    def test_partial_gates_still_allowed_in_permissive(self):
        gov = _parse(self.PARTIAL)
        d = evaluate(gov, Operation.RAG_INDEX, strict=False)
        self.assertEqual(d.verdict, Verdict.ALLOW)

    def test_all_gates_true_allowed_in_strict(self):
        gov = _parse(self.FULL)
        d = evaluate(gov, Operation.RAG_INDEX, strict=True)
        self.assertEqual(d.verdict, Verdict.ALLOW)


class NamespaceTests(unittest.TestCase):
    """Regression 2: default-namespaced DocLang XML must parse."""

    NAMESPACED = """
    <doclang xmlns="https://doclang.example/ns" version="0.7">
      <head>
        <licenses>
          <license>https://www.apache.org/licenses/LICENSE-2.0</license>
        </licenses>
        <rag_permitted>true</rag_permitted>
        <rag_indexing_allowed>true</rag_indexing_allowed>
        <extraction_permitted>true</extraction_permitted>
        <extraction_scope>tables_only</extraction_scope>
      </head>
    </doclang>
    """

    def test_namespaced_elements_are_read(self):
        gov = _parse(self.NAMESPACED)
        self.assertEqual(gov.get_bool("rag_permitted"), True)
        self.assertEqual(gov.get_bool("rag_indexing_allowed"), True)
        self.assertEqual(
            gov.elements["licenses"],
            ["https://www.apache.org/licenses/LICENSE-2.0"],
        )

    def test_namespaced_document_evaluates(self):
        gov = _parse(self.NAMESPACED)
        d = evaluate(gov, Operation.RAG_INDEX, strict=True)
        self.assertEqual(d.verdict, Verdict.ALLOW)
        d = evaluate(gov, Operation.EXTRACT, strict=True)
        self.assertEqual(d.verdict, Verdict.ALLOW_WITH_OBLIGATIONS)
        self.assertIn("extraction_scope=tables_only", d.obligations)


class ProhibitionSurfacedTests(unittest.TestCase):
    """Regression 3: declared-false constraints must appear in the decision."""

    XML = """
    <doclang>
      <head>
        <rag_permitted>true</rag_permitted>
        <rag_indexing_allowed>true</rag_indexing_allowed>
        <rag_caching_allowed>false</rag_caching_allowed>
        <rag_audit_required>true</rag_audit_required>
      </head>
    </doclang>
    """

    def test_false_constraint_is_surfaced(self):
        gov = _parse(self.XML)
        d = evaluate(gov, Operation.RAG_INDEX, strict=True)
        self.assertEqual(d.verdict, Verdict.ALLOW_WITH_OBLIGATIONS)
        self.assertIn("rag_caching_allowed=false", d.obligations)
        self.assertIn("rag_audit_required", d.obligations)


class SpecVersionTests(unittest.TestCase):
    """Root spec-version checking (spec 0.7; toolkit v0.7.3 is separate)."""

    def test_supported_version_is_surfaced(self):
        gov = _parse('<doclang version="0.7"><head/></doclang>')
        self.assertEqual(gov.spec_version, "0.7")

    def test_missing_version_is_tolerated(self):
        gov = _parse("<doclang><head/></doclang>")
        self.assertIsNone(gov.spec_version)

    def test_unsupported_version_is_rejected(self):
        with self.assertRaises(UnsupportedSpecVersionError):
            _parse('<doclang version="9.9"><head/></doclang>')

    def test_supported_set_covers_unchanged_appendix_range(self):
        self.assertEqual(
            SUPPORTED_SPEC_VERSIONS, frozenset({"0.4", "0.5", "0.6", "0.7"})
        )


if __name__ == "__main__":
    unittest.main()
