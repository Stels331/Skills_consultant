import tempfile
import unittest
from pathlib import Path

from app.pipeline.epistemic_ledger import append_event, build_event, replay_events


class EpistemicLedgerTests(unittest.TestCase):
    def test_append_only_ledger_preserves_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "epistemic_ledger.jsonl"
            append_event(
                path,
                build_event(
                    event_type="claim_created",
                    workspace_id="case_1",
                    stage="characterization",
                    target_id="node_1",
                    payload={"node_type": "source_fact"},
                ),
            )
            append_event(
                path,
                build_event(
                    event_type="claim_promoted",
                    workspace_id="case_1",
                    stage="problem_factory",
                    target_id="node_1",
                    payload={"from_status": "inferred", "to_status": "observed"},
                ),
            )
            lines = path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(lines), 2)

    def test_replay_preserves_event_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "epistemic_ledger.jsonl"
            first = build_event(
                event_type="claim_created",
                workspace_id="case_1",
                stage="characterization",
                target_id="node_1",
                payload={"node_type": "source_fact"},
            )
            second = build_event(
                event_type="constraint_compiled",
                workspace_id="case_1",
                stage="problem_factory",
                target_id="node_2",
                payload={"node_type": "decision_constraint"},
            )
            append_event(path, first)
            append_event(path, second)
            events = replay_events(path)

        self.assertEqual(events[0]["event_type"], "claim_created")
        self.assertEqual(events[1]["event_type"], "constraint_compiled")

    def test_invalid_event_payload_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "epistemic_ledger.jsonl"
            with self.assertRaisesRegex(ValueError, "INVALID_EPISTEMIC_EVENT_PAYLOAD"):
                append_event(
                    path,
                    {
                        "event_type": "claim_created",
                        "timestamp": "2026-03-19T00:00:00+00:00",
                        "workspace_id": "case_1",
                        "stage": "characterization",
                        "target_id": "node_1",
                        "payload": "bad",
                    },
                )

    def test_conflict_resolved_event_is_supported(self):
        event = build_event(
            event_type="conflict_resolved",
            workspace_id="case_1",
            stage="solution_factory",
            target_id="conflict_1",
            payload={"resolution": "selected_solution_changed"},
        )
        self.assertEqual(event["event_type"], "conflict_resolved")

    def test_claim_updated_event_is_supported(self):
        event = build_event(
            event_type="claim_updated",
            workspace_id="case_1",
            stage="characterization",
            target_id="node_1",
            payload={"changed_fields": {"statement": {"before": "a", "after": "b"}}},
        )
        self.assertEqual(event["event_type"], "claim_updated")


if __name__ == "__main__":
    unittest.main()
