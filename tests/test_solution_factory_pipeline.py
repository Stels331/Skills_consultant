import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.pipeline.characterization import run_characterization
from app.pipeline.conflict_router import run_conflict_router
from app.pipeline.intake_parser import run_intake_parser
from app.pipeline.layer_builder import build_layers
from app.pipeline.parity_tradeoff import run_parity_tradeoff
from app.pipeline.problem_factory import run_problem_factory
from app.pipeline.selection_engine import run_selection_engine
from app.pipeline.solution_factory import run_solution_factory
from app.pipeline.solution_portfolio import run_solution_portfolio
from app.pipeline.viewpoint_runner import run_viewpoints
from app.state.workspace_manager import WorkspaceManager
from app.validation.artifact_contract_validator import read_frontmatter_document, validate_artifact_contract


class SolutionFactoryPipelineTests(unittest.TestCase):
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

        # copy all skills needed by local llm wrappers
        skills_src = Path(__file__).resolve().parents[1] / ".agent" / "skills"
        skills_dst = self.root / ".agent" / "skills"
        skills_dst.mkdir(parents=True, exist_ok=True)
        for p in skills_src.glob("*/SKILL.md"):
            target = skills_dst / p.parent.name
            target.mkdir(parents=True, exist_ok=True)
            (target / "SKILL.md").write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

        self.manager = WorkspaceManager(self.root)
        self.ref = self.manager.create_workspace("case_20260303_401")

        (self.ref.path / "raw" / "case_input.md").write_text(
            (
                "Company has strategy mismatch with operations and weak evidence-driven governance.\n"
                "Architecture decisions conflict with delivery speed targets.\n"
                "Team must improve decision confidence in a 30-day pilot window.\n"
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

    def test_s4_t1_solution_portfolio_contract_and_diversity(self):
        out = run_solution_portfolio(self.root, self.ref.workspace_id, llm_mode="local")
        p = self.ref.path / "solutions" / "SolutionPortfolio.md"
        self.assertTrue(p.is_file())
        txt = p.read_text(encoding="utf-8")

        self.assertIn("sol_00_status_quo", txt)
        self.assertGreaterEqual(len(re.findall(r"^##\s+sol_", txt, flags=re.MULTILINE)), 4)

        solution_types = set(re.findall(r"^- type:\s*(.+)$", txt, flags=re.MULTILINE))
        self.assertGreaterEqual(len(solution_types), 3)

        contract = validate_artifact_contract(self.root, p, self.ref.path)
        self.assertTrue(contract.is_valid)
        self.assertIn("solution_portfolio", out)

    def test_s4_t1_fails_on_insufficient_portfolio(self):
        bad_md = "# Solution Portfolio\n\n## sol_01_single\n- type: process\n- assurance_level: medium\n"
        with patch("app.pipeline.solution_portfolio.generate_markdown_with_skill", return_value=bad_md):
            with self.assertRaisesRegex(ValueError, "INVALID_SOLUTION_PORTFOLIO_MINIMUM_REQUIREMENTS"):
                run_solution_portfolio(self.root, self.ref.workspace_id, llm_mode="local")

    def test_s4_t2_parity_outputs_are_deterministic(self):
        run_solution_portfolio(self.root, self.ref.workspace_id, llm_mode="local")

        out1 = run_parity_tradeoff(self.root, self.ref.workspace_id, llm_mode="local")
        rep1 = read_frontmatter_document(self.ref.path / "solutions" / "ParityReport.md").body

        out2 = run_parity_tradeoff(self.root, self.ref.workspace_id, llm_mode="local")
        rep2 = read_frontmatter_document(self.ref.path / "solutions" / "ParityReport.md").body

        self.assertEqual(rep1, rep2)
        self.assertIn("unknown", (self.ref.path / "solutions" / "ParityPlan.md").read_text(encoding="utf-8").lower())

        for rel in ["ParityPlan.md", "ParityReport.md", "TradeoffTable.md"]:
            p = self.ref.path / "solutions" / rel
            self.assertTrue(p.is_file())
            self.assertTrue(validate_artifact_contract(self.root, p, self.ref.path).is_valid)

        self.assertIn("parity_report", out1)
        self.assertIn("tradeoff_table", out2)

    def test_s4_t3_conflict_router_fallback_for_unsupported_type(self):
        run_solution_portfolio(self.root, self.ref.workspace_id, llm_mode="local")
        run_parity_tradeoff(self.root, self.ref.workspace_id, llm_mode="local")

        (self.ref.path / "viewpoints" / "conflicts_index.md").write_text(
            "# Conflicts\n\n- bizarre quantum conflict without taxonomy marker\n",
            encoding="utf-8",
        )
        run_conflict_router(self.root, self.ref.workspace_id, llm_mode="local")
        txt = (self.ref.path / "solutions" / "ConflictRecords.md").read_text(encoding="utf-8")
        self.assertIn("method_selected: Delphi", txt)
        self.assertIn("controlled fallback", txt)

    def test_s4_t4_selection_requires_parity_and_conflicts(self):
        run_solution_portfolio(self.root, self.ref.workspace_id, llm_mode="local")
        with self.assertRaisesRegex(ValueError, "SELECTION_REQUIRES_PARITY_AND_CONFLICTS"):
            run_selection_engine(self.root, self.ref.workspace_id, llm_mode="local")

    def test_s4_t4_selection_blocks_if_assurance_missing(self):
        run_solution_portfolio(self.root, self.ref.workspace_id, llm_mode="local")

        portfolio = self.ref.path / "solutions" / "SolutionPortfolio.md"
        txt = portfolio.read_text(encoding="utf-8")
        txt = txt.replace("- assurance_level: medium\n", "", 1)
        portfolio.write_text(txt, encoding="utf-8")

        run_parity_tradeoff(self.root, self.ref.workspace_id, llm_mode="local")
        run_conflict_router(self.root, self.ref.workspace_id, llm_mode="local")

        with self.assertRaisesRegex(ValueError, "SELECTION_MISSING_ASSURANCE_LEVEL"):
            run_selection_engine(self.root, self.ref.workspace_id, llm_mode="local")

    def test_s4_end_to_end_solution_factory_outputs(self):
        out = run_solution_factory(self.root, self.ref.workspace_id, llm_mode="local")
        expected = [
            "solutions/SolutionPortfolio.md",
            "solutions/ParityPlan.md",
            "solutions/ParityReport.md",
            "solutions/TradeoffTable.md",
            "solutions/ConflictRecords.md",
            "solutions/SelectedSolutions.md",
            "decisions/ADR-001.md",
            "operation/Runbook.md",
            "operation/RollbackPlan.md",
        ]
        for rel in expected:
            p = self.ref.path / rel
            self.assertTrue(p.is_file(), rel)
            self.assertTrue(validate_artifact_contract(self.root, p, self.ref.path).is_valid, rel)

        selected_txt = read_frontmatter_document(self.ref.path / "solutions" / "SelectedSolutions.md").body
        selected_block = selected_txt.split("Rejected:")[0]
        selected_count = len(re.findall(r"^-\s+sol_", selected_block, flags=re.MULTILINE))
        self.assertGreaterEqual(selected_count, 1)
        self.assertLessEqual(selected_count, 3)
        self.assertIn("traceability", selected_txt.lower())

        self.assertIn("adr", out)
        self.assertIn("runbook", out)
        self.assertIn("rollback", out)


if __name__ == "__main__":
    unittest.main()
