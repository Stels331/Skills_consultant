import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.llm.client import generate_markdown_with_skill as local_generate
from app.pipeline.characterization import run_characterization
from app.pipeline.epistemic_graph import default_graph, save_graph
from app.pipeline.epistemic_projection import build_projection, emit_projection, validate_projection
from app.pipeline.intake_parser import run_intake_parser
from app.pipeline.layer_builder import build_layers
from app.pipeline.problem_factory import run_problem_factory
from app.pipeline.reporting import compose_analytical_full_report
from app.pipeline.solution_portfolio import run_solution_portfolio
from app.pipeline.viewpoint_runner import run_viewpoints
from app.state.workspace_manager import WorkspaceManager


class EpistemicProjectionTests(unittest.TestCase):
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

        skills_src = Path(__file__).resolve().parents[1] / ".agent" / "skills"
        skills_dst = self.root / ".agent" / "skills"
        skills_dst.mkdir(parents=True, exist_ok=True)
        for p in skills_src.glob("*/SKILL.md"):
            target = skills_dst / p.parent.name
            target.mkdir(parents=True, exist_ok=True)
            (target / "SKILL.md").write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

        self.manager = WorkspaceManager(self.root)
        self.ref = self.manager.create_workspace("case_20260319_901")
        (self.ref.path / "raw" / "case_input.md").write_text(
            (
                "Market validation and buyer proof are weak.\n"
                "Project has strategic mismatch and governance friction.\n"
            ),
            encoding="utf-8",
        )
        run_intake_parser(self.root, self.ref.workspace_id)
        build_layers(self.root, self.ref.workspace_id, llm_mode="local")
        run_viewpoints(self.root, self.ref.workspace_id, llm_mode="local")
        run_characterization(self.root, self.ref.workspace_id, llm_mode="local")
        run_problem_factory(self.root, self.ref.workspace_id, llm_mode="local")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_projection_builder_returns_expected_slice(self):
        projection = build_projection(self.ref.path, "solution_factory_projection")
        self.assertEqual(projection["projection_type"], "solution_factory_projection")
        payload = projection["projection_payload"]
        self.assertIn("lawful_constraints", payload)
        self.assertIn("rejected_constraints", payload)
        self.assertIn("relevant_claims", payload)
        self.assertTrue(all(node["node_type"] != "hypothesis" for node in payload["lawful_constraints"]))

    def test_projection_rejects_missing_source_graph_version(self):
        with self.assertRaisesRegex(ValueError, "INVALID_PROJECTION_SOURCE_GRAPH_VERSION"):
            validate_projection(
                {
                    "projection_id": "p1",
                    "projection_type": "selection_projection",
                    "source_graph_version": "",
                    "included_node_ids": [],
                    "included_edge_ids": [],
                    "projection_payload": {},
                }
            )

    def test_selection_projection_excludes_unresolved_nodes(self):
        graph = default_graph(self.ref.workspace_id)
        graph["updated_at"] = "2026-03-19T00:00:00+00:00"
        graph["nodes"] = [
            {
                "id": "n1",
                "artifact_rel": "problems/ComparisonAcceptanceSpec.md",
                "node_type": "decision_constraint",
                "statement": "keep blast radius bounded",
                "source_refs": ["problems/SelectedProblemCard.md:L1"],
                "epistemic_status": "inferred",
                "stage": "problem_factory",
                "owner": "analyst",
                "created_at": "2026-03-19T00:00:00+00:00",
                "updated_at": "2026-03-19T00:00:00+00:00",
            },
            {
                "id": "n2",
                "artifact_rel": "problems/SelectedProblemCard.md",
                "node_type": "interpretation",
                "statement": "disputed market claim",
                "source_refs": ["problems/ProblemPortfolio.md:L1"],
                "epistemic_status": "disputed",
                "stage": "problem_factory",
                "owner": "analyst",
                "created_at": "2026-03-19T00:00:00+00:00",
                "updated_at": "2026-03-19T00:00:00+00:00",
            },
        ]
        save_graph(self.ref.path / "analysis" / "epistemic_graph.json", graph)

        projection = build_projection(self.ref.path, "selection_projection")
        ids = {node["id"] for node in projection["projection_payload"]["relevant_claims"]}
        self.assertIn("n1", ids)
        self.assertNotIn("n2", ids)

    def test_selection_projection_keeps_only_lawful_constraints(self):
        graph = default_graph(self.ref.workspace_id)
        graph["updated_at"] = "2026-03-19T00:00:00+00:00"
        graph["nodes"] = [
            {
                "id": "fact_1",
                "artifact_rel": "characterization/CharacterizationPassport.md",
                "node_type": "source_fact",
                "statement": "validated throughput baseline",
                "source_refs": ["raw/case_input.md:L1"],
                "epistemic_status": "observed",
                "stage": "characterization",
                "owner": "analyst",
                "created_at": "2026-03-19T00:00:00+00:00",
                "updated_at": "2026-03-19T00:00:00+00:00",
            },
            {
                "id": "target_1",
                "artifact_rel": "characterization/CharacterizationPassport.md",
                "node_type": "normative_target",
                "statement": "preserve throughput",
                "source_refs": ["characterization/CharacterizationPassport.md:L1"],
                "epistemic_status": "inferred",
                "stage": "characterization",
                "owner": "analyst",
                "created_at": "2026-03-19T00:00:00+00:00",
                "updated_at": "2026-03-19T00:00:00+00:00",
            },
            {
                "id": "constraint_safe",
                "artifact_rel": "problems/ComparisonAcceptanceSpec.md",
                "node_type": "decision_constraint",
                "statement": "do not break throughput baseline",
                "source_refs": ["problems/ComparisonAcceptanceSpec.md:L1"],
                "epistemic_status": "inferred",
                "stage": "problem_factory",
                "owner": "analyst",
                "created_at": "2026-03-19T00:00:00+00:00",
                "updated_at": "2026-03-19T00:00:00+00:00",
            },
            {
                "id": "hyp_1",
                "artifact_rel": "problems/ProblemPortfolio.md",
                "node_type": "hypothesis",
                "statement": "maybe emergency capex is needed",
                "source_refs": ["problems/ProblemPortfolio.md:L1"],
                "epistemic_status": "hypothesis",
                "stage": "problem_factory",
                "owner": "analyst",
                "created_at": "2026-03-19T00:00:00+00:00",
                "updated_at": "2026-03-19T00:00:00+00:00",
            },
            {
                "id": "constraint_bad",
                "artifact_rel": "problems/ComparisonAcceptanceSpec.md",
                "node_type": "decision_constraint",
                "statement": "force unverified capex limit",
                "source_refs": ["problems/ComparisonAcceptanceSpec.md:L1"],
                "epistemic_status": "inferred",
                "stage": "problem_factory",
                "owner": "analyst",
                "created_at": "2026-03-19T00:00:00+00:00",
                "updated_at": "2026-03-19T00:00:00+00:00",
            },
        ]
        graph["edges"] = [
            {"edge_type": "DERIVED_FROM", "from": "target_1", "to": "fact_1", "provenance": "test"},
            {"edge_type": "CONSTRAINS", "from": "constraint_safe", "to": "target_1", "provenance": "test"},
            {"edge_type": "CONSTRAINS", "from": "constraint_bad", "to": "target_1", "provenance": "test"},
            {"edge_type": "RELATES_TO", "from": "hyp_1", "to": "constraint_bad", "provenance": "test"},
        ]
        save_graph(self.ref.path / "analysis" / "epistemic_graph.json", graph)

        projection = build_projection(self.ref.path, "selection_projection")
        lawful_ids = {node["id"] for node in projection["projection_payload"]["lawful_constraints"]}
        rejected_ids = {item["node"]["id"] for item in projection["projection_payload"]["rejected_constraints"]}
        self.assertEqual(lawful_ids, {"constraint_safe"})
        self.assertIn("constraint_bad", rejected_ids)

    def test_reporting_projection_excludes_disputed_claims(self):
        graph = default_graph(self.ref.workspace_id)
        graph["updated_at"] = "2026-03-19T00:00:00+00:00"
        graph["nodes"] = [
            {
                "id": "safe_1",
                "artifact_rel": "problems/SelectedProblemCard.md",
                "node_type": "problem",
                "statement": "validated strategic mismatch",
                "source_refs": ["problems/ProblemPortfolio.md:L1"],
                "epistemic_status": "inferred",
                "stage": "problem_factory",
                "owner": "analyst",
                "created_at": "2026-03-19T00:00:00+00:00",
                "updated_at": "2026-03-19T00:00:00+00:00",
            },
            {
                "id": "unsafe_1",
                "artifact_rel": "problems/ProblemArchive.md",
                "node_type": "interpretation",
                "statement": "disputed technical catastrophe",
                "source_refs": ["problems/ProblemArchive.md:L1"],
                "epistemic_status": "disputed",
                "stage": "problem_factory",
                "owner": "analyst",
                "created_at": "2026-03-19T00:00:00+00:00",
                "updated_at": "2026-03-19T00:00:00+00:00",
            },
        ]
        save_graph(self.ref.path / "analysis" / "epistemic_graph.json", graph)

        projection = build_projection(self.ref.path, "reporting_projection")
        ids = {node["id"] for node in projection["projection_payload"]["human_facing_claims"]}
        self.assertIn("safe_1", ids)
        self.assertNotIn("unsafe_1", ids)

    def test_problem_factory_and_solution_factory_receive_projection_payloads(self):
        captured_problem = []
        captured_solution = []

        def capture_problem(system_skill_prompt, user_payload, mode="local"):
            captured_problem.append(user_payload)
            return local_generate(system_skill_prompt, user_payload, mode=mode)

        def capture_solution(system_skill_prompt, user_payload, mode="local"):
            captured_solution.append(user_payload)
            return local_generate(system_skill_prompt, user_payload, mode=mode)

        with patch("app.pipeline.problem_factory.generate_markdown_with_skill", side_effect=capture_problem):
            run_problem_factory(self.root, self.ref.workspace_id, llm_mode="local")
        with patch("app.pipeline.solution_portfolio.generate_markdown_with_skill", side_effect=capture_solution):
            run_solution_portfolio(self.root, self.ref.workspace_id, llm_mode="local")

        self.assertTrue(all("projection" in payload for payload in captured_problem))
        self.assertTrue(all(payload["projection"]["projection_type"] == "problem_factory_projection" for payload in captured_problem))
        self.assertTrue(all("projection" in payload for payload in captured_solution))
        self.assertTrue(all(payload["projection"]["projection_type"] == "solution_factory_projection" for payload in captured_solution))

    def test_reporting_uses_projection_and_emits_audit(self):
        captured = []

        def capture_reporting(system_skill_prompt, user_payload, mode="local"):
            captured.append(user_payload)
            return local_generate(system_skill_prompt, user_payload, mode=mode)

        with patch("app.pipeline.reporting.generate_markdown_with_skill", side_effect=capture_reporting):
            compose_analytical_full_report(self.root, self.ref.workspace_id, llm_mode="local")

        self.assertTrue(captured)
        self.assertIn("reporting_projection", captured[0])
        self.assertEqual(captured[0]["reporting_projection"]["projection_type"], "reporting_projection")

        audit_path = self.ref.path / "governance" / "contract_audit.jsonl"
        ledger_path = self.ref.path / "governance" / "epistemic_ledger.jsonl"
        self.assertTrue(audit_path.is_file())
        self.assertTrue(ledger_path.is_file())
        self.assertIn("projection_emitted", audit_path.read_text(encoding="utf-8"))
        self.assertIn("projection_emitted", ledger_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
