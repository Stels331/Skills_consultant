import json
import tempfile
import unittest
from pathlib import Path

from app.pipeline.characterization import run_characterization
from app.pipeline.intake_parser import run_intake_parser
from app.pipeline.layer_builder import build_layers
from app.pipeline.problem_factory import run_problem_factory
from app.pipeline.reporting import run_reporting
from app.pipeline.solution_factory import run_solution_factory
from app.pipeline.viewpoint_runner import run_viewpoints
from app.state.workspace_manager import WorkspaceManager
from app.testing.acceptance_checklist import run_acceptance_checklist


def _copy_support(test_root: Path) -> None:
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


class AcceptanceChecklistTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        _copy_support(self.root)
        self.manager = WorkspaceManager(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _build_good_workspace(self, workspace_id: str) -> Path:
        ref = self.manager.create_workspace(workspace_id)
        (ref.path / "raw" / "case_input.md").write_text(
            "Factory launch has market proof gaps, governance friction, and throughput instability.\n",
            encoding="utf-8",
        )
        run_intake_parser(self.root, ref.workspace_id)
        build_layers(self.root, ref.workspace_id, llm_mode="local")
        run_viewpoints(self.root, ref.workspace_id, llm_mode="local")
        run_characterization(self.root, ref.workspace_id, llm_mode="local")
        run_problem_factory(self.root, ref.workspace_id, llm_mode="local")
        run_solution_factory(self.root, ref.workspace_id, llm_mode="local")
        run_reporting(self.root, ref.workspace_id)
        return ref.path

    def test_acceptance_checklist_passes_on_good_workspace(self):
        workspace = self._build_good_workspace("case_20260319_801")
        result = run_acceptance_checklist(self.root, workspace)
        self.assertTrue(result["acceptance_pass"])
        self.assertTrue((workspace / "reports" / "acceptance_checklist.md").is_file())

    def test_acceptance_checklist_fails_on_broken_workspace(self):
        workspace = self._build_good_workspace("case_20260319_802")
        (workspace / "solutions" / "SelectedSolutions.md").unlink()
        result = run_acceptance_checklist(self.root, workspace)
        self.assertFalse(result["acceptance_pass"])
        self.assertFalse(result["contracts_pass"])


if __name__ == "__main__":
    unittest.main()
