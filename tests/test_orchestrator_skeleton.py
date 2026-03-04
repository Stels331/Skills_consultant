import json
import tempfile
import unittest
from pathlib import Path

from app.router.orchestrator import StageOrchestrator


ARTIFACT_TEXT = """---
id: art_stage_intake
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
next_expected_artifacts: []
created_at: 2026-03-03T12:00:00+00:00
updated_at: 2026-03-03T12:00:00+00:00
---
content
"""


class OrchestratorSkeletonTests(unittest.TestCase):
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

        self.workspace_id = "case_20260303_001"
        self.workspace = self.root / "cases" / self.workspace_id
        (self.workspace / "governance" / "stage_artifacts").mkdir(parents=True, exist_ok=True)

        (self.workspace / "governance" / "stage_artifacts" / "intake.md").write_text(
            ARTIFACT_TEXT,
            encoding="utf-8",
        )

        self.orchestrator = StageOrchestrator(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_run_stage_pass_writes_decision_log(self):
        result = self.orchestrator.run_stage(self.workspace_id, "intake")
        self.assertEqual(result.gate_result, "pass")
        self.assertEqual(result.previous_state, "draft")
        self.assertEqual(result.new_state, "shaped")

        log_path = self.workspace / "governance" / "decision_log.jsonl"
        self.assertTrue(log_path.is_file())
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        payload = json.loads(lines[-1])
        self.assertEqual(payload["gate_result"], "pass")
        self.assertIn("semantic_judge", payload["checks_applied"])
        self.assertIn("semantic_judge", payload)

    def test_block_result_on_invalid_contract(self):
        bad = (self.workspace / "governance" / "stage_artifacts" / "intake.md")
        bad.write_text("---\nid: only\n---\n", encoding="utf-8")

        result = self.orchestrator.run_stage(self.workspace_id, "intake")
        self.assertEqual(result.gate_result, "block")

    def test_degrade_requires_rationale(self):
        with self.assertRaises(ValueError):
            self.orchestrator.run_stage(
                self.workspace_id,
                "intake",
                signals={"force_degrade": True},
            )

    def test_solution_factory_guard_requires_problem_artifacts(self):
        # no problems/SelectedProblemCard.md or problems/ComparisonAcceptanceSpec.md
        result = self.orchestrator.run_stage(self.workspace_id, "solution_factory")
        self.assertEqual(result.gate_result, "block")

        log_path = self.workspace / "governance" / "decision_log.jsonl"
        payload = json.loads(log_path.read_text(encoding="utf-8").strip().splitlines()[-1])
        self.assertTrue(
            any(v.get("message") == "MISSING_REQUIRED_PROBLEM_ARTIFACTS" for v in payload["violations"])
        )


if __name__ == "__main__":
    unittest.main()
