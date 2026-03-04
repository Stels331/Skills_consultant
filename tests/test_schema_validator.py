import json
import tempfile
import unittest
from pathlib import Path

from app.state.workspace_manager import WorkspaceManager
from app.validation.schema_validator import (
    validate_artifact,
    validate_workspace,
)


class SchemaValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        # copy schemas from project into temp root for isolated tests
        src_schemas = Path(__file__).resolve().parents[1] / "schemas"
        dst_schemas = self.root / "schemas"
        dst_schemas.mkdir(parents=True, exist_ok=True)
        for p in src_schemas.glob("*.schema.json"):
            (dst_schemas / p.name).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

        self.manager = WorkspaceManager(self.root)
        self.ref = self.manager.create_workspace("case_20260228_001")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_validate_workspace_positive(self):
        results = validate_workspace(self.root, self.ref.path)
        self.assertTrue(all(r.is_valid for r in results.values()))

    def test_validate_artifact_negative_reports_path(self):
        card = self.ref.path / "analysis" / "problem_card.json"
        payload = json.loads(card.read_text(encoding="utf-8"))
        payload["acceptance_criteria"] = "wrong-type"
        card.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        result = validate_artifact(self.root, card, "problem_card")
        self.assertFalse(result.is_valid)
        self.assertTrue(any(issue.path.endswith("acceptance_criteria") for issue in result.issues))
        self.assertTrue(any(issue.expected == "array" for issue in result.issues))

    def test_validate_workspace_detects_missing_file(self):
        (self.ref.path / "quality" / "quality_metrics.json").unlink()
        results = validate_workspace(self.root, self.ref.path)
        self.assertFalse(results["quality/quality_metrics.json"].is_valid)


if __name__ == "__main__":
    unittest.main()
