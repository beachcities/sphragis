"""Regression tests.

Covers three fixed regressions plus root spec-version checking:

1. Strict posture must require EVERY gate of a multi-gate operation to be
   explicitly true (e.g. ``rag_permitted`` alone must not allow ``rag_index``).
2. Documents using the official DocLang default namespace must parse, while
   foreign-namespace elements must NOT be read as governance declarations.
3. Declared prohibitions (e.g. ``rag_caching_allowed`` = false) must be
   surfaced as constraints, not silently dropped — while a requirement
   declared false (``*_audit_required`` = false) must impose nothing.
4. The root ``version`` attribute is surfaced and validated (spec version,
   e.g. ``0.7`` — distinct from the reference-toolkit release, e.g. v0.7.3).
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sphragis import (
    DOCLANG_NAMESPACE,
    Operation,
    SUPPORTED_SPEC_VERSIONS,
    UnsupportedSpecVersionError,
    Verdict,
    evaluate,
    parse_governance,
)
from sphragis.cli import main as cli_main


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
    """Regression 2: the official DocLang namespace must parse; foreign
    namespaces must not be read as governance declarations."""

    NAMESPACED = f"""
    <doclang xmlns="{DOCLANG_NAMESPACE}" version="0.7">
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

    FOREIGN = """
    <doclang xmlns="urn:not-doclang">
      <head>
        <rag_permitted>true</rag_permitted>
        <rag_indexing_allowed>true</rag_indexing_allowed>
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
        self.assertIn("extraction_scope=tables_only", d.constraints)

    def test_foreign_namespace_is_not_governance(self):
        gov = _parse(self.FOREIGN)
        self.assertEqual(gov.elements, {})
        d = evaluate(gov, Operation.RAG_INDEX, strict=True)
        self.assertEqual(d.verdict, Verdict.DENY)


class ProhibitionSurfacedTests(unittest.TestCase):
    """Regression 3: prohibitions surface as constraints; a requirement
    declared false imposes nothing."""

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

    NOT_REQUIRED = """
    <doclang>
      <head>
        <extraction_permitted>true</extraction_permitted>
        <extraction_audit_required>false</extraction_audit_required>
      </head>
    </doclang>
    """

    GRANTED = """
    <doclang>
      <head>
        <rag_permitted>true</rag_permitted>
        <rag_indexing_allowed>true</rag_indexing_allowed>
        <rag_caching_allowed>true</rag_caching_allowed>
      </head>
    </doclang>
    """

    def test_false_prohibition_is_a_constraint(self):
        gov = _parse(self.XML)
        d = evaluate(gov, Operation.RAG_INDEX, strict=True)
        self.assertEqual(d.verdict, Verdict.ALLOW_WITH_OBLIGATIONS)
        self.assertIn("rag_caching_allowed=false", d.constraints)
        self.assertIn("rag_audit_required", d.obligations)
        self.assertNotIn("rag_caching_allowed=false", d.obligations)

    def test_requirement_false_imposes_nothing(self):
        gov = _parse(self.NOT_REQUIRED)
        d = evaluate(gov, Operation.EXTRACT, strict=True)
        self.assertEqual(d.verdict, Verdict.ALLOW)
        self.assertEqual(d.obligations, [])
        self.assertEqual(d.constraints, [])

    def test_permission_true_imposes_nothing(self):
        gov = _parse(self.GRANTED)
        d = evaluate(gov, Operation.RAG_INDEX, strict=True)
        self.assertEqual(d.verdict, Verdict.ALLOW)
        self.assertEqual(d.obligations, [])
        self.assertEqual(d.constraints, [])


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

    def test_cli_reports_unsupported_version_without_traceback(self):
        import contextlib
        import io

        with tempfile.NamedTemporaryFile(
            "w", suffix=".dclg", delete=False, encoding="utf-8"
        ) as fh:
            fh.write('<doclang version="9.9"><head/></doclang>')
            name = fh.name
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr):
                code = cli_main(["inspect", name])
        finally:
            Path(name).unlink(missing_ok=True)
        self.assertEqual(code, 2)
        self.assertIn('"error"', stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
