import json
import tempfile
import unittest
from pathlib import Path

from app.router.orchestrator import StageOrchestrator
from app.validation.artifact_contract_validator import read_frontmatter_document


def _artifact_text(
    *,
    epistemic_status: str = "observed",
    assurance_level: str = "medium",
    valid_until: str = "2026-12-31",
    source_refs: str = "[\"raw/case_input.md:L1\"]",
    evidence_refs: str = "[]",
    body: str = "- observed fact from intake\n",
) -> str:
    return f"""---
id: art_stage_intake
artifact_type: normalized_case
stage: intake
state: draft
parent_refs: []
source_refs: {source_refs}
evidence_refs: {evidence_refs}
viewpoints: []
epistemic_status: {epistemic_status}
assurance_level: {assurance_level}
valid_until: {valid_until}
owner_role: analyst
gate_status: pending
violated_principles: []
next_expected_artifacts: []
created_at: 2026-03-03T12:00:00+00:00
updated_at: 2026-03-03T12:00:00+00:00
---
{body}
"""


class EvidenceAssuranceRefreshTests(unittest.TestCase):
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

        self.workspace_id = "case_20260303_501"
        self.workspace = self.root / "cases" / self.workspace_id
        (self.workspace / "governance" / "stage_artifacts").mkdir(parents=True, exist_ok=True)

        self.orchestrator = StageOrchestrator(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_s5_t1_evidence_graph_and_claim_classification(self):
        artifact = self.workspace / "governance" / "stage_artifacts" / "intake.md"
        artifact.write_text(
            _artifact_text(
                epistemic_status="observed",
                body=(
                    "- observed metric drift in current process\n"
                    "- hypothesis: priority policy may create queue explosion\n"
                ),
            ),
            encoding="utf-8",
        )

        result = self.orchestrator.run_stage(self.workspace_id, "intake")
        self.assertIn(result.gate_result, {"pass", "degrade"})

        graph_json = self.workspace / "evidence" / "evidence_graph.json"
        graph_md = self.workspace / "evidence" / "evidence_graph.md"
        self.assertTrue(graph_json.is_file())
        self.assertTrue(graph_md.is_file())

        data = json.loads(graph_json.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(data.get("claims", [])), 2)
        self.assertGreaterEqual(len(data.get("edges", [])), 2)
        claim_classes = {c.get("claim_class") for c in data.get("claims", [])}
        self.assertIn("observed", claim_classes)
        self.assertIn("hypothesis", claim_classes)

        doc = read_frontmatter_document(artifact)
        # inheritance degradation: observed + hypothesis => hypothesis
        self.assertEqual(doc.frontmatter.get("epistemic_status"), "hypothesis")

    def test_s5_t2_high_assurance_without_evidence_blocks(self):
        artifact = self.workspace / "governance" / "stage_artifacts" / "intake.md"
        artifact.write_text(
            _artifact_text(
                epistemic_status="decision_grade",
                assurance_level="high",
                source_refs='["raw/case_input.md:L1"]',
                evidence_refs="[]",
                body="- decision: choose architecture slice\n",
            ),
            encoding="utf-8",
        )

        result = self.orchestrator.run_stage(self.workspace_id, "intake")
        self.assertEqual(result.gate_result, "block")

        log_path = self.workspace / "governance" / "decision_log.jsonl"
        payload = json.loads(log_path.read_text(encoding="utf-8").strip().splitlines()[-1])
        self.assertEqual(payload["assurance_engine"]["recommendation"], "block")
        self.assertTrue(
            any(i.get("code") == "MISSING_EVIDENCE_REFS" for i in payload["assurance_engine"]["issues"])
        )

    def test_s5_t3_expired_artifact_triggers_refresh(self):
        artifact = self.workspace / "governance" / "stage_artifacts" / "intake.md"
        artifact.write_text(
            _artifact_text(
                valid_until="2020-01-01",
                body="- observed stale context artifact\n",
            ),
            encoding="utf-8",
        )

        result = self.orchestrator.run_stage(self.workspace_id, "intake")
        self.assertEqual(result.gate_result, "block")

        doc = read_frontmatter_document(artifact)
        self.assertEqual(doc.frontmatter.get("state"), "expired")

        refresh_report = self.workspace / "evidence" / "refresh_report.md"
        refresh_index = self.workspace / "evidence" / "refresh_index.json"
        self.assertTrue(refresh_report.is_file())
        self.assertTrue(refresh_index.is_file())

        idx = json.loads(refresh_index.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(idx.get("events", [])), 1)
        self.assertEqual(idx["events"][-1]["reason"], "valid_until expired")

    def test_s5_t3_context_change_recheck_degrades_and_logs_trigger(self):
        artifact = self.workspace / "governance" / "stage_artifacts" / "intake.md"
        artifact.write_text(_artifact_text(), encoding="utf-8")

        result = self.orchestrator.run_stage(
            self.workspace_id,
            "intake",
            signals={"recheck_trigger": "constraints_changed"},
        )
        self.assertEqual(result.gate_result, "degrade")

        log_path = self.workspace / "governance" / "decision_log.jsonl"
        payload = json.loads(log_path.read_text(encoding="utf-8").strip().splitlines()[-1])
        self.assertEqual(payload.get("recheck_trigger"), "constraints_changed")
        self.assertEqual(payload.get("freshness", {}).get("refresh", {}).get("trigger"), "constraints_changed")


if __name__ == "__main__":
    unittest.main()
