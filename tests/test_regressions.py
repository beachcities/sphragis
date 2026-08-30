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
5. The root element itself is validated: only ``<doclang>`` in the empty or
   official namespace is accepted (``NotADocLangDocumentError`` otherwise).
6. TRAIN honors its PII elements as gates and surfaces reuse/sharing
   prohibitions as constraints; RAG_RETRIEVE surfaces
   ``rag_downstream_sharing_permitted=false`` as a constraint.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sphragis import (
    DOCLANG_NAMESPACE,
    NotADocLangDocumentError,
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

    def test_foreign_namespace_root_is_rejected(self):
        with self.assertRaises(NotADocLangDocumentError):
            _parse(self.FOREIGN)


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


class RootValidationTests(unittest.TestCase):
    """Regression 5: only <doclang> in an accepted namespace is a document."""

    WRONG_ROOT = """
    <not_doclang>
      <head>
        <rag_permitted>true</rag_permitted>
        <rag_indexing_allowed>true</rag_indexing_allowed>
      </head>
    </not_doclang>
    """

    MIXED = f"""
    <not_doclang>
      <head xmlns="{DOCLANG_NAMESPACE}">
        <rag_permitted>true</rag_permitted>
        <rag_indexing_allowed>true</rag_indexing_allowed>
      </head>
    </not_doclang>
    """

    def test_wrong_root_name_is_rejected(self):
        with self.assertRaises(NotADocLangDocumentError):
            _parse(self.WRONG_ROOT)

    def test_foreign_root_with_official_namespace_head_is_rejected(self):
        with self.assertRaises(NotADocLangDocumentError):
            _parse(self.MIXED)

    def test_official_namespace_root_is_accepted(self):
        gov = _parse(
            f'<doclang xmlns="{DOCLANG_NAMESPACE}"><head>'
            "<rag_permitted>true</rag_permitted></head></doclang>"
        )
        self.assertEqual(gov.get_bool("rag_permitted"), True)

    def test_cli_reports_wrong_root_without_traceback(self):
        import contextlib
        import io

        from sphragis.cli import main as cli_entry

        with tempfile.NamedTemporaryFile(
            "w", suffix=".dclg", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(self.WRONG_ROOT)
            name = fh.name
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr):
                code = cli_entry(["evaluate", name, "--op", "rag_index"])
        finally:
            Path(name).unlink(missing_ok=True)
        self.assertEqual(code, 2)
        self.assertIn('"error"', stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())


class TrainGovernanceTests(unittest.TestCase):
    """Regression 6: TRAIN honors its PII elements and reuse/sharing
    prohibitions; RAG_RETRIEVE surfaces downstream-sharing prohibition."""

    PII_EXCLUDED = """
    <doclang>
      <head>
        <training_permitted>true</training_permitted>
        <training_pii_included>false</training_pii_included>
        <training_sensitive_data_included>false</training_sensitive_data_included>
      </head>
    </doclang>
    """

    REUSE_FORBIDDEN = """
    <doclang>
      <head>
        <training_permitted>true</training_permitted>
        <training_dataset_reuse_allowed>false</training_dataset_reuse_allowed>
        <training_derivative_sharing_permitted>false</training_derivative_sharing_permitted>
      </head>
    </doclang>
    """

    RAG_NO_DOWNSTREAM = """
    <doclang>
      <head>
        <rag_permitted>true</rag_permitted>
        <rag_pii_exposure_allowed>true</rag_pii_exposure_allowed>
        <rag_sensitive_data_exposure_allowed>true</rag_sensitive_data_exposure_allowed>
        <rag_downstream_sharing_permitted>false</rag_downstream_sharing_permitted>
      </head>
    </doclang>
    """

    def test_train_with_pii_denied_when_pii_excluded(self):
        gov = _parse(self.PII_EXCLUDED)
        d = evaluate(gov, Operation.TRAIN, strict=True, involves_pii=True)
        self.assertEqual(d.verdict, Verdict.DENY)
        self.assertIn("training_pii_included is declared false", d.reasons[0])

    def test_train_with_pii_denied_in_strict_when_undeclared(self):
        gov = _parse(
            "<doclang><head>"
            "<training_permitted>true</training_permitted>"
            "</head></doclang>"
        )
        d = evaluate(gov, Operation.TRAIN, strict=True, involves_pii=True)
        self.assertEqual(d.verdict, Verdict.DENY)

    def test_train_without_pii_still_allowed(self):
        gov = _parse(self.PII_EXCLUDED)
        d = evaluate(gov, Operation.TRAIN, strict=True, involves_pii=False)
        self.assertEqual(d.verdict, Verdict.ALLOW)

    def test_reuse_and_sharing_prohibitions_surface_as_constraints(self):
        gov = _parse(self.REUSE_FORBIDDEN)
        d = evaluate(gov, Operation.TRAIN, strict=True)
        self.assertEqual(d.verdict, Verdict.ALLOW_WITH_OBLIGATIONS)
        self.assertIn("training_dataset_reuse_allowed=false", d.constraints)
        self.assertIn("training_derivative_sharing_permitted=false", d.constraints)

    def test_rag_retrieve_downstream_sharing_prohibition_surfaces(self):
        gov = _parse(self.RAG_NO_DOWNSTREAM)
        d = evaluate(gov, Operation.RAG_RETRIEVE, strict=True, involves_pii=True)
        self.assertEqual(d.verdict, Verdict.ALLOW_WITH_OBLIGATIONS)
        self.assertIn("rag_downstream_sharing_permitted=false", d.constraints)


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
