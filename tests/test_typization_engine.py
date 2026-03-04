import json
import tempfile
import unittest
from pathlib import Path

from app.state.workspace_manager import WorkspaceManager
from app.typization.typization_engine import TypizationEngine


class TypizationEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

        # bootstrap Type registry
        src_type = Path(__file__).resolve().parents[1] / "Type"
        dst_type = self.root / "Type"
        dst_type.mkdir(parents=True, exist_ok=True)
        for p in src_type.glob("*.json"):
            (dst_type / p.name).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

        self.manager = WorkspaceManager(self.root)
        self.ref = self.manager.create_workspace("case_20260228_001")
        (self.ref.path / "parsed" / "sample.txt").write_text(
            "Лісопильний комплекс 1500 м куб в місяць\n"
            "Втрата довіри в команді\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_typization_creates_artifacts(self):
        engine = TypizationEngine(self.root)
        result = engine.run_for_workspace("case_20260228_001")

        self.assertGreaterEqual(result.claims_count, 2)
        self.assertGreaterEqual(result.entities_count, 1)

        self.assertTrue((self.ref.path / "extracted" / "entities.json").is_file())
        self.assertTrue((self.ref.path / "extracted" / "claims.json").is_file())
        self.assertTrue((self.ref.path / "analysis" / "typed_entities.json").is_file())
        self.assertTrue((self.ref.path / "analysis" / "type_proposals.json").is_file())
        self.assertTrue((self.ref.path / "analysis" / "case_types_report.json").is_file())
        self.assertTrue((self.ref.path / "analysis" / "fpf_type_compliance.json").is_file())
        self.assertTrue((self.ref.path / "analysis" / "candidate_normalization.json").is_file())
        self.assertTrue((self.ref.path / "reports" / "case_types_report.md").is_file())
        self.assertTrue((self.ref.path / "reports" / "fpf_type_compliance.md").is_file())
        self.assertTrue((self.ref.path / "reports" / "candidate_normalization.md").is_file())

    def test_fact_interpretation_classification(self):
        engine = TypizationEngine(self.root)
        engine.run_for_workspace("case_20260228_001")

        claims = json.loads((self.ref.path / "extracted" / "claims.json").read_text(encoding="utf-8"))["claims"]
        kinds = {c["kind"] for c in claims}
        self.assertIn("FACT", kinds)
        self.assertIn("INTERPRETATION", kinds)

    def test_fpf_compliance_demotes_generic_process(self):
        engine = TypizationEngine(self.root)
        engine.run_for_workspace("case_20260228_001")

        entities = json.loads(
            (self.ref.path / "extracted" / "entities.json").read_text(encoding="utf-8")
        )["entities"]

        found = [e for e in entities if e["name"].lower() == "комплекс"]
        if found:
            self.assertEqual(found[0]["type"], "CandidateType")


if __name__ == "__main__":
    unittest.main()
