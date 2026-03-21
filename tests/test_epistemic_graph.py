import tempfile
import unittest
from pathlib import Path

from app.pipeline.epistemic_graph import (
    build_edge,
    build_node,
    default_graph,
    load_graph,
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


if __name__ == "__main__":
    unittest.main()
