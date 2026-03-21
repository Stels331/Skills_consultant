import tempfile
import unittest
from pathlib import Path

from app.pipeline.epistemic_graph import save_graph
from app.validation.conflict_validator import materialize_conflicts, validate_unresolved_conflicts


class ConflictValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name) / "cases" / "case_20260319_4001"
        (self.workspace / "analysis").mkdir(parents=True, exist_ok=True)
        (self.workspace / "governance").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_contradictory_claims_are_linked_via_conflict_case(self):
        save_graph(
            self.workspace / "analysis" / "epistemic_graph.json",
            {
                "workspace_id": self.workspace.name,
                "version": 1,
                "updated_at": "2026-03-19T00:00:00+00:00",
                "nodes": [
                    {
                        "id": "f1",
                        "node_type": "source_fact",
                        "statement": "throughput can increase under current setup",
                        "source_refs": ["raw/case_input.md:L1"],
                        "epistemic_status": "observed",
                        "stage": "characterization",
                        "owner": "analyst",
                        "created_at": "2026-03-19T00:00:00+00:00",
                        "updated_at": "2026-03-19T00:00:00+00:00",
                        "claim_key": "throughput_claim",
                    },
                    {
                        "id": "f2",
                        "node_type": "source_fact",
                        "statement": "throughput cannot increase under current setup",
                        "source_refs": ["raw/case_input.md:L2"],
                        "epistemic_status": "observed",
                        "stage": "characterization",
                        "owner": "analyst",
                        "created_at": "2026-03-19T00:00:00+00:00",
                        "updated_at": "2026-03-19T00:00:00+00:00",
                        "claim_key": "throughput_claim",
                    },
                ],
                "edges": [],
            },
        )

        graph = materialize_conflicts(self.workspace)
        self.assertTrue(any(node["node_type"] == "conflict_case" for node in graph["nodes"]))
        self.assertTrue(any(edge["edge_type"] == "CONTRADICTS" for edge in graph["edges"]))

    def test_unresolved_contradiction_blocks_selection(self):
        save_graph(
            self.workspace / "analysis" / "epistemic_graph.json",
            {
                "workspace_id": self.workspace.name,
                "version": 1,
                "updated_at": "2026-03-19T00:00:00+00:00",
                "nodes": [
                    {
                        "id": "conflict_1",
                        "node_type": "conflict_case",
                        "statement": "Conflict on throughput",
                        "source_refs": ["raw/case_input.md:L1"],
                        "epistemic_status": "disputed",
                        "stage": "validation",
                        "owner": "validator",
                        "created_at": "2026-03-19T00:00:00+00:00",
                        "updated_at": "2026-03-19T00:00:00+00:00",
                        "resolution_status": "open",
                    }
                ],
                "edges": [],
            },
        )
        issues = validate_unresolved_conflicts(self.workspace)
        self.assertTrue(any(issue.code == "UNRESOLVED_SELECTION_CONFLICT" for issue in issues))

    def test_resolved_contradiction_does_not_block(self):
        save_graph(
            self.workspace / "analysis" / "epistemic_graph.json",
            {
                "workspace_id": self.workspace.name,
                "version": 1,
                "updated_at": "2026-03-19T00:00:00+00:00",
                "nodes": [
                    {
                        "id": "conflict_1",
                        "node_type": "conflict_case",
                        "statement": "Conflict on throughput",
                        "source_refs": ["raw/case_input.md:L1"],
                        "epistemic_status": "disputed",
                        "stage": "validation",
                        "owner": "validator",
                        "created_at": "2026-03-19T00:00:00+00:00",
                        "updated_at": "2026-03-19T00:00:00+00:00",
                        "resolution_status": "resolved",
                    }
                ],
                "edges": [],
            },
        )
        issues = validate_unresolved_conflicts(self.workspace)
        self.assertEqual(issues, [])

    def test_compatible_type_pair_creates_duplicate_cluster_not_conflict(self):
        save_graph(
            self.workspace / "analysis" / "epistemic_graph.json",
            {
                "workspace_id": self.workspace.name,
                "version": 1,
                "updated_at": "2026-03-21T00:00:00+00:00",
                "nodes": [
                    {
                        "id": "n1",
                        "node_type": "normative_target",
                        "statement": "target diesel dependence below 30%",
                        "source_refs": ["characterization/CharacterizationPassport.md:L10"],
                        "epistemic_status": "target",
                        "stage": "characterization",
                        "owner": "analyst",
                        "created_at": "2026-03-21T00:00:00+00:00",
                        "updated_at": "2026-03-21T00:00:00+00:00",
                        "claim_key": "diesel_dependence_target",
                    },
                    {
                        "id": "n2",
                        "node_type": "derived_metric",
                        "statement": "diesel dependence should remain under 30%",
                        "source_refs": ["characterization/IndicatorSet.md:L8"],
                        "epistemic_status": "derived",
                        "stage": "characterization",
                        "owner": "analyst",
                        "created_at": "2026-03-21T00:00:00+00:00",
                        "updated_at": "2026-03-21T00:00:00+00:00",
                        "claim_key": "diesel_dependence_target",
                    },
                ],
                "edges": [],
            },
        )

        graph = materialize_conflicts(self.workspace)
        self.assertTrue(any(node["node_type"] == "duplicate_claim_cluster" for node in graph["nodes"]))
        self.assertFalse(any(node["node_type"] == "conflict_case" for node in graph["nodes"]))
        self.assertEqual(validate_unresolved_conflicts(self.workspace), [])

    def test_compatible_type_pair_with_opposite_polarity_is_conflict(self):
        save_graph(
            self.workspace / "analysis" / "epistemic_graph.json",
            {
                "workspace_id": self.workspace.name,
                "version": 1,
                "updated_at": "2026-03-21T00:00:00+00:00",
                "nodes": [
                    {
                        "id": "n1",
                        "node_type": "normative_target",
                        "statement": "diesel dependence can remain under 30%",
                        "source_refs": ["characterization/CharacterizationPassport.md:L10"],
                        "epistemic_status": "target",
                        "stage": "characterization",
                        "owner": "analyst",
                        "created_at": "2026-03-21T00:00:00+00:00",
                        "updated_at": "2026-03-21T00:00:00+00:00",
                        "claim_key": "diesel_dependence_target",
                    },
                    {
                        "id": "n2",
                        "node_type": "derived_metric",
                        "statement": "diesel dependence cannot remain under 30%",
                        "source_refs": ["characterization/IndicatorSet.md:L8"],
                        "epistemic_status": "derived",
                        "stage": "characterization",
                        "owner": "analyst",
                        "created_at": "2026-03-21T00:00:00+00:00",
                        "updated_at": "2026-03-21T00:00:00+00:00",
                        "claim_key": "diesel_dependence_target",
                    },
                ],
                "edges": [],
            },
        )

        graph = materialize_conflicts(self.workspace)
        self.assertTrue(any(node["node_type"] == "conflict_case" for node in graph["nodes"]))
        self.assertTrue(any(issue.code == "UNRESOLVED_SELECTION_CONFLICT" for issue in validate_unresolved_conflicts(self.workspace)))

    def test_shared_negative_constraint_does_not_become_conflict(self):
        save_graph(
            self.workspace / "analysis" / "epistemic_graph.json",
            {
                "workspace_id": self.workspace.name,
                "version": 1,
                "updated_at": "2026-03-21T00:00:00+00:00",
                "nodes": [
                    {
                        "id": "n1",
                        "node_type": "normative_target",
                        "statement": 'Do not use "zero energy cost" in the margin calculation.',
                        "source_refs": ["characterization/CharacterizationPassport.md:L10"],
                        "epistemic_status": "target",
                        "stage": "characterization",
                        "owner": "analyst",
                        "created_at": "2026-03-21T00:00:00+00:00",
                        "updated_at": "2026-03-21T00:00:00+00:00",
                        "claim_key": "margin_calc_rule",
                    },
                    {
                        "id": "n2",
                        "node_type": "derived_metric",
                        "statement": 'Do not use "zero energy cost" when calculating gross margin.',
                        "source_refs": ["characterization/IndicatorSet.md:L8"],
                        "epistemic_status": "derived",
                        "stage": "characterization",
                        "owner": "analyst",
                        "created_at": "2026-03-21T00:00:00+00:00",
                        "updated_at": "2026-03-21T00:00:00+00:00",
                        "claim_key": "margin_calc_rule",
                    },
                ],
                "edges": [],
            },
        )

        graph = materialize_conflicts(self.workspace)
        self.assertTrue(any(node["node_type"] == "duplicate_claim_cluster" for node in graph["nodes"]))
        self.assertFalse(any(node["node_type"] == "conflict_case" for node in graph["nodes"]))
        self.assertEqual(validate_unresolved_conflicts(self.workspace), [])


if __name__ == "__main__":
    unittest.main()
