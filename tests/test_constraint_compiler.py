import tempfile
import unittest
from pathlib import Path

from app.pipeline.constraint_compiler import compile_lawful_constraints
from app.pipeline.epistemic_graph import save_graph


class ConstraintCompilerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name) / "cases" / "case_20260319_2001"
        (self.workspace / "analysis").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_lawful_source_chain_compiles_constraint(self):
        save_graph(
            self.workspace / "analysis" / "epistemic_graph.json",
            {
                "workspace_id": self.workspace.name,
                "version": 1,
                "updated_at": "2026-03-19T12:00:00+00:00",
                "nodes": [
                    {
                        "id": "fact_1",
                        "node_type": "source_fact",
                        "statement": "confirmed throughput",
                        "source_refs": ["raw/case_input.md:L1"],
                        "epistemic_status": "observed",
                        "stage": "characterization",
                        "owner": "analyst",
                        "created_at": "2026-03-19T12:00:00+00:00",
                        "updated_at": "2026-03-19T12:00:00+00:00",
                    },
                    {
                        "id": "target_1",
                        "node_type": "normative_target",
                        "statement": "preserve throughput",
                        "source_refs": ["characterization/CharacterizationPassport.md:L1"],
                        "epistemic_status": "inferred",
                        "stage": "characterization",
                        "owner": "analyst",
                        "created_at": "2026-03-19T12:00:00+00:00",
                        "updated_at": "2026-03-19T12:00:00+00:00",
                    },
                    {
                        "id": "constraint_1",
                        "node_type": "decision_constraint",
                        "statement": "do not reduce throughput below baseline",
                        "source_refs": ["problems/ComparisonAcceptanceSpec.md:L1"],
                        "epistemic_status": "inferred",
                        "stage": "problem_factory",
                        "owner": "analyst",
                        "created_at": "2026-03-19T12:00:00+00:00",
                        "updated_at": "2026-03-19T12:00:00+00:00",
                    },
                ],
                "edges": [
                    {"edge_type": "DERIVED_FROM", "from": "target_1", "to": "fact_1", "provenance": "test"},
                    {"edge_type": "CONSTRAINS", "from": "constraint_1", "to": "target_1", "provenance": "test"},
                ],
            },
        )

        compiled = compile_lawful_constraints(self.workspace)
        self.assertEqual([node["id"] for node in compiled.lawful_constraints], ["constraint_1"])
        self.assertEqual(compiled.rejected_constraints, [])

    def test_unlawful_source_chain_is_rejected(self):
        save_graph(
            self.workspace / "analysis" / "epistemic_graph.json",
            {
                "workspace_id": self.workspace.name,
                "version": 1,
                "updated_at": "2026-03-19T12:00:00+00:00",
                "nodes": [
                    {
                        "id": "fact_1",
                        "node_type": "source_fact",
                        "statement": "confirmed throughput",
                        "source_refs": ["raw/case_input.md:L1"],
                        "epistemic_status": "observed",
                        "stage": "characterization",
                        "owner": "analyst",
                        "created_at": "2026-03-19T12:00:00+00:00",
                        "updated_at": "2026-03-19T12:00:00+00:00",
                    },
                    {
                        "id": "target_1",
                        "node_type": "normative_target",
                        "statement": "preserve throughput",
                        "source_refs": ["characterization/CharacterizationPassport.md:L1"],
                        "epistemic_status": "inferred",
                        "stage": "characterization",
                        "owner": "analyst",
                        "created_at": "2026-03-19T12:00:00+00:00",
                        "updated_at": "2026-03-19T12:00:00+00:00",
                    },
                    {
                        "id": "hyp_1",
                        "node_type": "hypothesis",
                        "statement": "maybe this should be hard constrained",
                        "source_refs": ["problems/ProblemPortfolio.md:L1"],
                        "epistemic_status": "hypothesis",
                        "stage": "problem_factory",
                        "owner": "analyst",
                        "created_at": "2026-03-19T12:00:00+00:00",
                        "updated_at": "2026-03-19T12:00:00+00:00",
                    },
                    {
                        "id": "constraint_2",
                        "node_type": "decision_constraint",
                        "statement": "force immediate throughput guarantee",
                        "source_refs": ["problems/ComparisonAcceptanceSpec.md:L1"],
                        "epistemic_status": "inferred",
                        "stage": "problem_factory",
                        "owner": "analyst",
                        "created_at": "2026-03-19T12:00:00+00:00",
                        "updated_at": "2026-03-19T12:00:00+00:00",
                    },
                ],
                "edges": [
                    {"edge_type": "DERIVED_FROM", "from": "target_1", "to": "fact_1", "provenance": "test"},
                    {"edge_type": "CONSTRAINS", "from": "constraint_2", "to": "target_1", "provenance": "test"},
                    {"edge_type": "RELATES_TO", "from": "hyp_1", "to": "constraint_2", "provenance": "test"},
                ],
            },
        )

        compiled = compile_lawful_constraints(self.workspace)
        self.assertEqual(compiled.lawful_constraints, [])
        self.assertEqual(compiled.rejected_constraints[0]["node"]["id"], "constraint_2")
        self.assertIn(
            "hypothesis_to_decision_constraint_forbidden",
            compiled.rejected_constraints[0]["reasons"],
        )


if __name__ == "__main__":
    unittest.main()
