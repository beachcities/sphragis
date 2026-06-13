import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sphragis import Operation, Verdict, evaluate, parse_governance

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


class OpenMinimalTests(unittest.TestCase):
    def setUp(self):
        self.gov = parse_governance(EXAMPLES / "open_minimal.dclg.xml")

    def test_extract_allowed_with_audit_obligation(self):
        d = evaluate(self.gov, Operation.EXTRACT)
        self.assertEqual(d.verdict, Verdict.ALLOW_WITH_OBLIGATIONS)
        self.assertIn("extraction_audit_required", d.obligations)

    def test_training_allowed_with_provenance(self):
        d = evaluate(self.gov, Operation.TRAIN)
        self.assertEqual(d.verdict, Verdict.ALLOW_WITH_OBLIGATIONS)
        self.assertIn("training_provenance_required", d.obligations)

    def test_share_downstream_denied_in_strict_when_unspecified(self):
        d = evaluate(self.gov, Operation.SHARE_DOWNSTREAM, strict=True)
        self.assertEqual(d.verdict, Verdict.DENY)

    def test_share_downstream_unspecified_in_permissive(self):
        d = evaluate(self.gov, Operation.SHARE_DOWNSTREAM, strict=False)
        self.assertEqual(d.verdict, Verdict.UNSPECIFIED)


class RestrictedCaseTests(unittest.TestCase):
    def setUp(self):
        self.gov = parse_governance(EXAMPLES / "restricted_case.dclg.xml")

    def test_rag_denied(self):
        d = evaluate(self.gov, Operation.RAG_INDEX)
        self.assertEqual(d.verdict, Verdict.DENY)

    def test_training_denied(self):
        d = evaluate(self.gov, Operation.TRAIN)
        self.assertEqual(d.verdict, Verdict.DENY)

    def test_extract_without_pii_allowed_with_obligations(self):
        d = evaluate(self.gov, Operation.EXTRACT, involves_pii=False)
        self.assertEqual(d.verdict, Verdict.ALLOW_WITH_OBLIGATIONS)
        self.assertIn("extraction_scope=tables_only", d.obligations)
        self.assertIn("human_in_the_loop_required", d.obligations)

    def test_extract_involving_pii_denied(self):
        d = evaluate(self.gov, Operation.EXTRACT, involves_pii=True)
        self.assertEqual(d.verdict, Verdict.DENY)
        self.assertIn("pii_extraction_allowed is declared false", d.reasons[0])


if __name__ == "__main__":
    unittest.main()
