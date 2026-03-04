import json
import tempfile
import unittest
from pathlib import Path

from app.observability.audit import build_audit_trail
from app.router.orchestrator import StageOrchestrator
from app.state.workspace_manager import WorkspaceManager
from app.testing.integration_suite import run_integration_suite
from app.validation.artifact_contract_validator import read_frontmatter_document


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
- observed content
"""


class NFROverviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

        schema_src = Path(__file__).resolve().parents[1] / "schemas" / "artifact_frontmatter.schema.json"
        schema_dst = self.root / "schemas"
        schema_dst.mkdir(parents=True, exist_ok=True)
        (schema_dst / "artifact_frontmatter.schema.json").write_text(schema_src.read_text(encoding="utf-8"), encoding="utf-8")

        skills_src = Path(__file__).resolve().parents[1] / ".agent" / "skills"
        skills_dst = self.root / ".agent" / "skills"
        skills_dst.mkdir(parents=True, exist_ok=True)
        for p in skills_src.glob("*/SKILL.md"):
            t = skills_dst / p.parent.name
            t.mkdir(parents=True, exist_ok=True)
            (t / "SKILL.md").write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

        fixtures_src = Path(__file__).resolve().parents[1] / "tests" / "integration" / "fixtures"
        fixtures_dst = self.root / "tests" / "integration" / "fixtures"
        fixtures_dst.mkdir(parents=True, exist_ok=True)
        for p in fixtures_src.glob("*.md"):
            (fixtures_dst / p.name).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

        self.manager = WorkspaceManager(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_s7_t1_audit_trail_generation(self):
        ref = self.manager.create_workspace("case_20260303_701")
        (ref.path / "governance" / "stage_artifacts").mkdir(parents=True, exist_ok=True)
        artifact = ref.path / "governance" / "stage_artifacts" / "intake.md"
        artifact.write_text(ARTIFACT_TEXT, encoding="utf-8")

        orch = StageOrchestrator(self.root)
        orch.run_stage(ref.workspace_id, "intake")

        summary = build_audit_trail(ref.path)
        self.assertGreaterEqual(summary["decision_log_entries"], 1)
        self.assertGreaterEqual(summary["stage_event_entries"], 1)
        self.assertTrue((ref.path / "reports" / "audit_trail.md").is_file())

    def test_s7_t2_reuse_short_circuit(self):
        ref = self.manager.create_workspace("case_20260303_702")
        (ref.path / "governance" / "stage_artifacts").mkdir(parents=True, exist_ok=True)
        artifact = ref.path / "governance" / "stage_artifacts" / "intake.md"
        artifact.write_text(ARTIFACT_TEXT, encoding="utf-8")

        orch = StageOrchestrator(self.root)
        first = orch.run_stage(ref.workspace_id, "intake")
        self.assertIn(first.gate_result, {"pass", "degrade"})

        doc = read_frontmatter_document(artifact)
        doc.frontmatter["state"] = "accepted_for_next_stage"
        from app.validation.artifact_contract_validator import write_frontmatter_document

        write_frontmatter_document(artifact, doc)

        second = orch.run_stage(ref.workspace_id, "intake", signals={"allow_reuse": True})
        self.assertEqual(second.gate_result, "pass")

        latest = json.loads((ref.path / "governance" / "decision_log.jsonl").read_text(encoding="utf-8").strip().splitlines()[-1])
        self.assertTrue(latest.get("reused_artifact", False))

    def test_s7_t3_integration_suite_quality_report(self):
        out = run_integration_suite(self.root)
        self.assertGreaterEqual(out["total_cases"], 10)
        self.assertEqual(out["silent_failures"], 0)
        self.assertGreaterEqual(out["hard_fail_detection_rate"], 0.9)
        self.assertTrue((self.root / "reports" / "integration_quality_report.md").is_file())


if __name__ == "__main__":
    unittest.main()
