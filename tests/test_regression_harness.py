import json
import tempfile
import unittest
from pathlib import Path

from app.pipeline.characterization import run_characterization
from app.pipeline.conflict_router import run_conflict_router
from app.pipeline.intake_parser import run_intake_parser
from app.pipeline.layer_builder import build_layers
from app.pipeline.parity_tradeoff import run_parity_tradeoff
from app.pipeline.problem_factory import run_problem_factory
from app.pipeline.reporting import run_reporting
from app.pipeline.solution_factory import run_solution_factory
from app.pipeline.solution_portfolio import run_solution_portfolio
from app.pipeline.viewpoint_runner import run_viewpoints
from app.state.workspace_manager import WorkspaceManager
from app.validation.artifact_contract_validator import read_frontmatter_document
from app.validation.cross_case_markers import check_cross_case_markers


def _copy_project_support(test_root: Path) -> None:
    schema_src = Path(__file__).resolve().parents[1] / "schemas" / "artifact_frontmatter.schema.json"
    schema_dst = test_root / "schemas"
    schema_dst.mkdir(parents=True, exist_ok=True)
    (schema_dst / "artifact_frontmatter.schema.json").write_text(schema_src.read_text(encoding="utf-8"), encoding="utf-8")

    skills_src = Path(__file__).resolve().parents[1] / ".agent" / "skills"
    skills_dst = test_root / ".agent" / "skills"
    skills_dst.mkdir(parents=True, exist_ok=True)
    for p in skills_src.glob("*/SKILL.md"):
        target = skills_dst / p.parent.name
        target.mkdir(parents=True, exist_ok=True)
        (target / "SKILL.md").write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

    contracts_src = Path(__file__).resolve().parents[1] / "contracts"
    contracts_dst = test_root / "contracts"
    contracts_dst.mkdir(parents=True, exist_ok=True)
    for p in contracts_src.glob("*.json"):
        (contracts_dst / p.name).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")


class RegressionHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        _copy_project_support(self.root)
        self.manager = WorkspaceManager(self.root)
        self.fixtures = Path(__file__).resolve().parents[1] / "tests" / "integration" / "fixtures"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run_case(self, workspace_id: str, fixture_name: str) -> Path:
        ref = self.manager.create_workspace(workspace_id)
        content = (self.fixtures / fixture_name).read_text(encoding="utf-8")
        (ref.path / "raw" / "case_input.md").write_text(content, encoding="utf-8")
        run_intake_parser(self.root, ref.workspace_id)
        build_layers(self.root, ref.workspace_id, llm_mode="local")
        run_viewpoints(self.root, ref.workspace_id, llm_mode="local")
        run_characterization(self.root, ref.workspace_id, llm_mode="local")
        run_problem_factory(self.root, ref.workspace_id, llm_mode="local")
        run_solution_factory(self.root, ref.workspace_id, llm_mode="local")
        run_reporting(self.root, ref.workspace_id)
        return ref.path

    def test_industrial_case_does_not_receive_presales_narrative(self):
        workspace = self._run_case("case_20260319_701", "industrial_transformation.md")
        analytical = read_frontmatter_document(workspace / "reports" / "Analytical_Full_Report.md").body
        executive = read_frontmatter_document(workspace / "reports" / "Executive_Summary.md").body
        for token in ["BANT", "CPQ", "Shadow Mode", "presales"]:
            self.assertNotIn(token, analytical)
            self.assertNotIn(token, executive)

    def test_presales_case_does_not_receive_plant_energy_reasoning(self):
        workspace = self._run_case("case_20260319_702", "presales_bottleneck.md")
        analytical = read_frontmatter_document(workspace / "reports" / "Analytical_Full_Report.md").body.lower()
        self.assertNotIn("gasifier", analytical)
        self.assertNotIn("kiln", analytical)
        self.assertNotIn("plant energy", analytical)

    def test_mixed_case_preserves_multiple_domains(self):
        workspace = self._run_case("case_20260319_703", "mixed_case.md")
        profile = json.loads((workspace / "analysis" / "domain_profile.json").read_text(encoding="utf-8"))
        axes = {item["axis"] for item in profile.get("domain_axes", [])}
        self.assertIn("industrial_transformation", axes)
        self.assertIn("governance_crisis", axes)
        self.assertTrue(len(axes) >= 2)

    def test_injected_foreign_template_is_caught(self):
        workspace = self._run_case("case_20260319_704", "industrial_transformation.md")
        analytical_path = workspace / "reports" / "Analytical_Full_Report.md"
        doc = read_frontmatter_document(analytical_path)
        contaminated = doc.body + "\nВнедрить BANT и Shadow Mode.\n"
        issues = check_cross_case_markers(analytical_path, contaminated)
        self.assertTrue(issues)


if __name__ == "__main__":
    unittest.main()
