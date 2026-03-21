import json
import tempfile
import unittest
from pathlib import Path

from app.pipeline.epistemic_store import sync_artifact_to_epistemic_store


class EpistemicStoreTests(unittest.TestCase):
    def test_sync_emits_claim_updated_with_changed_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "cases" / "case_1"
            (workspace / "analysis").mkdir(parents=True, exist_ok=True)
            (workspace / "governance").mkdir(parents=True, exist_ok=True)

            frontmatter = {
                "artifact_type": "characterization_passport",
                "stage": "characterization",
                "source_refs": ["raw/case_input.md:L1"],
                "owner_role": "analyst",
                "epistemic_status": "inferred",
            }
            first_body = (
                "## source_summary\n"
                "- baseline exists\n\n"
                "## optimization_goals\n"
                "- keep throughput\n\n"
                "## hard_constraints\n"
                "- do not break baseline\n\n"
                "## risk_signals\n"
                "- weak governance\n"
            )
            second_body = first_body.replace("baseline exists", "baseline materially changed")

            sync_artifact_to_epistemic_store(
                workspace_path=workspace,
                artifact_rel="characterization/CharacterizationPassport.md",
                frontmatter=frontmatter,
                body=first_body,
            )
            sync_artifact_to_epistemic_store(
                workspace_path=workspace,
                artifact_rel="characterization/CharacterizationPassport.md",
                frontmatter=frontmatter,
                body=second_body,
            )

            events = [
                json.loads(line)
                for line in (workspace / "governance" / "epistemic_ledger.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        updated_events = [event for event in events if event["event_type"] == "claim_updated"]
        self.assertEqual(len(updated_events), 1)
        changed_fields = updated_events[0]["payload"]["changed_fields"]
        self.assertIn("statement", changed_fields)
        self.assertEqual(changed_fields["statement"]["before"], "baseline exists")
        self.assertEqual(changed_fields["statement"]["after"], "baseline materially changed")


if __name__ == "__main__":
    unittest.main()
