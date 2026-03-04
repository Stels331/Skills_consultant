import unittest

from app.state.state_machine import (
    StateTransitionError,
    apply_transition,
    can_transition,
    suggest_next_state,
)


class StateMachineTests(unittest.TestCase):
    def test_valid_transition_path(self):
        artifact = {"state": "draft"}
        next_state = suggest_next_state("draft", "pass")
        self.assertEqual(next_state, "shaped")

        apply_transition(artifact, next_state, context={"gate_result": "pass"})
        self.assertEqual(artifact["state"], "shaped")

        apply_transition(artifact, "evidence_linked", context={"gate_result": "pass"})
        self.assertEqual(artifact["state"], "evidence_linked")

        apply_transition(artifact, "accepted_for_next_stage", context={"gate_result": "pass"})
        self.assertEqual(artifact["state"], "accepted_for_next_stage")

    def test_invalid_transition_rejected(self):
        self.assertFalse(can_transition("draft", "accepted_for_next_stage"))
        with self.assertRaises(StateTransitionError):
            apply_transition({"state": "draft"}, "accepted_for_next_stage", context={"gate_result": "pass"})

    def test_waive_requires_policy_context(self):
        with self.assertRaises(StateTransitionError):
            apply_transition({"state": "draft"}, "waived", context={})

        out = apply_transition(
            {"state": "draft"},
            "waived",
            context={"policy_id": "P-01", "owner": "arch", "rationale": "explicit"},
        )
        self.assertEqual(out["state"], "waived")


if __name__ == "__main__":
    unittest.main()
