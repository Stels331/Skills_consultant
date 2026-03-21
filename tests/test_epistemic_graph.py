import tempfile
import unittest
from pathlib import Path

from app.pipeline.epistemic_graph import (
    build_edge,
    build_node,
    extract_claims_from_artifact,
    default_graph,
    load_graph,
    merge_graph_entities,
    save_graph,
    validate_graph,
)


class EpistemicGraphTests(unittest.TestCase):
    def test_graph_serializer_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "epistemic_graph.json"
            graph = default_graph("case_1")
            node = build_node(
                artifact_rel="characterization/CharacterizationPassport.md",
                node_type="source_fact",
                statement="viewpoint summary exists",
                source_refs=["viewpoints/conflicts_index.md:L1"],
                epistemic_status="observed",
                stage="characterization",
                owner="analyst",
                index=1,
            )
            graph["nodes"].append(node)
            save_graph(path, graph)
            loaded = load_graph(path, "case_1")

        self.assertEqual(loaded["workspace_id"], "case_1")
        self.assertEqual(len(loaded["nodes"]), 1)
        self.assertEqual(loaded["nodes"][0]["node_type"], "source_fact")

    def test_invalid_node_is_rejected(self):
        graph = default_graph("case_1")
        graph["nodes"].append({"id": "n1", "node_type": "source_fact"})
        with self.assertRaisesRegex(ValueError, "INVALID_EPISTEMIC_NODE_MISSING_FIELDS"):
            validate_graph(graph)

    def test_dangling_edge_is_rejected(self):
        graph = default_graph("case_1")
        node = build_node(
            artifact_rel="problems/SelectedProblemCard.md",
            node_type="problem",
            statement="strategic mismatch",
            source_refs=["problems/ProblemPortfolio.md:L1"],
            epistemic_status="inferred",
            stage="problem_factory",
            owner="analyst",
            index=1,
        )
        graph["nodes"].append(node)
        graph["edges"].append(build_edge("DERIVED_FROM", str(node["id"]), "missing_node", "test"))
        with self.assertRaisesRegex(ValueError, "INVALID_EPISTEMIC_EDGE_DANGLING_REFERENCE"):
            validate_graph(graph)

    def test_assumption_node_type_is_allowed(self):
        graph = default_graph("case_1")
        node = build_node(
            artifact_rel="problems/ComparisonAcceptanceSpec.md",
            node_type="assumption",
            statement="budget remains unconfirmed",
            source_refs=["problems/ComparisonAcceptanceSpec.md:L1"],
            epistemic_status="hypothesis",
            stage="problem_factory",
            owner="analyst",
            index=1,
        )
        graph["nodes"].append(node)
        validate_graph(graph)

    def test_comparison_acceptance_spec_extracts_assumptions_as_assumption_nodes(self):
        nodes, edges = extract_claims_from_artifact(
            artifact_rel="problems/ComparisonAcceptanceSpec.md",
            artifact_type="comparison_acceptance_spec",
            stage="problem_factory",
            frontmatter={"source_refs": ["problems/ComparisonAcceptanceSpec.md:L1"], "owner_role": "analyst"},
            body=(
                "## indicators\n"
                "- throughput delta\n\n"
                "## hard_constraints\n"
                "- do not break baseline\n\n"
                "## assumptions_to_confirm\n"
                "- budget remains available\n"
            ),
        )
        assumption_nodes = [node for node in nodes if node["node_type"] == "assumption"]
        self.assertEqual(len(assumption_nodes), 1)
        self.assertEqual(assumption_nodes[0]["epistemic_status"], "hypothesis")
        self.assertTrue(any(edge["from"] == assumption_nodes[0]["id"] for edge in edges))

    def test_merge_graph_entities_returns_field_level_diff_trail(self):
        graph = default_graph("case_1")
        original = build_node(
            artifact_rel="characterization/CharacterizationPassport.md",
            node_type="source_fact",
            statement="initial baseline",
            source_refs=["raw/case_input.md:L1"],
            epistemic_status="observed",
            stage="characterization",
            owner="analyst",
            index=1,
        )
        graph["nodes"].append(original)
        updated = dict(original)
        updated["statement"] = "updated baseline"
        updated["epistemic_status"] = "tested"
        updated["updated_at"] = "2026-03-20T00:00:00+00:00"

        merged, previous_nodes, current_nodes, node_diffs = merge_graph_entities(graph, [updated], [])
        self.assertEqual(previous_nodes[original["id"]]["statement"], "initial baseline")
        self.assertEqual(current_nodes[original["id"]]["statement"], "updated baseline")
        self.assertEqual(len(merged["nodes"]), 1)
        self.assertEqual(node_diffs[0]["change_type"], "updated")
        self.assertIn("statement", node_diffs[0]["changed_fields"])
        self.assertEqual(node_diffs[0]["changed_fields"]["statement"]["before"], "initial baseline")
        self.assertEqual(node_diffs[0]["changed_fields"]["statement"]["after"], "updated baseline")

    def test_merge_graph_entities_remaps_legacy_statement_based_id(self):
        graph = default_graph("case_1")
        legacy = build_node(
            artifact_rel="characterization/CharacterizationPassport.md",
            node_type="source_fact",
            statement="initial baseline",
            source_refs=["raw/case_input.md:L1"],
            epistemic_status="observed",
            stage="characterization",
            owner="analyst",
            index=1,
        )
        legacy["id"] = "characterization/CharacterizationPassport.md::source_fact::001::initial_baseline"
        graph["nodes"].append(legacy)
        graph["edges"].append(build_edge("SUPPORTS", legacy["id"], legacy["id"], "test"))

        updated = build_node(
            artifact_rel="characterization/CharacterizationPassport.md",
            node_type="source_fact",
            statement="updated baseline",
            source_refs=["raw/case_input.md:L1"],
            epistemic_status="observed",
            stage="characterization",
            owner="analyst",
            index=1,
        )

        merged, _, current_nodes, _ = merge_graph_entities(graph, [updated], [])
        self.assertIn("characterization/CharacterizationPassport.md::source_fact::001", current_nodes)
        self.assertNotIn(legacy["id"], current_nodes)
        self.assertEqual(merged["edges"][0]["from"], "characterization/CharacterizationPassport.md::source_fact::001")
        self.assertEqual(merged["edges"][0]["to"], "characterization/CharacterizationPassport.md::source_fact::001")


if __name__ == "__main__":
    unittest.main()
