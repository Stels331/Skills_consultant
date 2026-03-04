import tempfile
import unittest
from pathlib import Path

from app.validation.artifact_contract_validator import validate_artifact_contract


FRONTMATTER = """---
id: art_001
artifact_type: normalized_case
stage: intake
state: draft
parent_refs: []
source_refs: [\"raw/case_input.md:L1\"]
evidence_refs: []
viewpoints: []
epistemic_status: observed
assurance_level: medium
valid_until: 2026-12-31
owner_role: analyst
gate_status: pending
violated_principles: []
next_expected_artifacts: [\"layers/layer_1_business_model.md\"]
created_at: 2026-03-03T12:00:00+00:00
updated_at: 2026-03-03T12:00:00+00:00
---
Body
"""


class ArtifactContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

        schema_src = Path(__file__).resolve().parents[1] / "schemas" / "artifact_frontmatter.schema.json"
        schema_dst = self.root / "schemas"
        schema_dst.mkdir(parents=True, exist_ok=True)
        (schema_dst / "artifact_frontmatter.schema.json").write_text(
            schema_src.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        self.workspace = self.root / "cases" / "case_20260303_001"
        (self.workspace / "intake").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_valid_frontmatter(self):
        artifact = self.workspace / "intake" / "normalized_case.md"
        artifact.write_text(FRONTMATTER, encoding="utf-8")

        result = validate_artifact_contract(self.root, artifact, self.workspace)
        self.assertTrue(result.is_valid)

    def test_missing_required_field_is_rejected(self):
        artifact = self.workspace / "intake" / "normalized_case.md"
        broken = FRONTMATTER.replace("artifact_type: normalized_case\n", "")
        artifact.write_text(broken, encoding="utf-8")

        result = validate_artifact_contract(self.root, artifact, self.workspace)
        self.assertFalse(result.is_valid)
        paths = [issue.path for issue in result.issues]
        self.assertIn("$.artifact_type", paths)

    def test_duplicate_id_in_workspace_is_rejected(self):
        a1 = self.workspace / "intake" / "normalized_case.md"
        a2_dir = self.workspace / "problems"
        a2_dir.mkdir(parents=True, exist_ok=True)
        a2 = a2_dir / "problem.md"

        a1.write_text(FRONTMATTER, encoding="utf-8")
        a2.write_text(FRONTMATTER.replace("stage: intake", "stage: problem_factory"), encoding="utf-8")

        result = validate_artifact_contract(self.root, a2, self.workspace)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("Duplicate artifact id" in i.message for i in result.issues))


if __name__ == "__main__":
    unittest.main()
