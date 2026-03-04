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
from app.release.pilot import run_pilot
from app.release.release_package import close_risks, prepare_release_package
from app.state.workspace_manager import WorkspaceManager


class PilotReleaseHardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

        schema_src = Path(__file__).resolve().parents[1] / "schemas" / "artifact_frontmatter.schema.json"
        schema_dst = self.root / "schemas"
        schema_dst.mkdir(parents=True, exist_ok=True)
        (schema_dst / "artifact_frontmatter.schema.json").write_text(schema_src.read_text(encoding="utf-8"), encoding="utf-8")

        skills_src = Path(__file__).resolve().parents[1] / ".agent" / "skills"
        skills_dst = self.root / ".agent" / "skills"
        skills_dst.mkdir(parents=True, exist_ok=True)
        for p in skills_src.glob("*/SKILL.md"):
            t = skills_dst / p.parent.name
            t.mkdir(parents=True, exist_ok=True)
            (t / "SKILL.md").write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

        self.manager = WorkspaceManager(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _build_full_case(self, workspace_id: str) -> None:
        ref = self.manager.create_workspace(workspace_id)
        (ref.path / "raw" / "case_input.md").write_text(
            "Strategy mismatch and delivery bottlenecks require reversible, evidence-linked change.\n",
            encoding="utf-8",
        )
        run_intake_parser(self.root, workspace_id)
        build_layers(self.root, workspace_id, llm_mode="local")
        run_viewpoints(self.root, workspace_id, llm_mode="local")
        run_characterization(self.root, workspace_id, llm_mode="local")
        run_problem_factory(self.root, workspace_id, llm_mode="local")
        run_solution_factory(self.root, workspace_id, llm_mode="local")
        run_reporting(self.root, workspace_id)

    def test_s8_t1_pilot_gap_register(self):
        self._build_full_case("case_20260303_801")
        self.manager.create_workspace("case_20260303_802")

        out = run_pilot(self.root, ["case_20260303_801", "case_20260303_802"])
        self.assertEqual(out["pilot_case_count"], 2)
        self.assertTrue((self.root / "governance" / "pilot_gap_register.md").is_file())
        self.assertTrue((self.root / "cases" / "case_20260303_801" / "reports" / "pilot_report.md").is_file())
        self.assertTrue((self.root / "cases" / "case_20260303_802" / "reports" / "pilot_report.md").is_file())

        reg = json.loads((self.root / "governance" / "pilot_gap_register.json").read_text(encoding="utf-8"))
        if reg["gaps"]:
            sample = reg["gaps"][0]
            self.assertIn("owner", sample)
            self.assertIn("priority", sample)

    def test_s8_t2_risk_closure(self):
        self.manager.create_workspace("case_20260303_803")
        run_pilot(self.root, ["case_20260303_803"])

        out = close_risks(self.root)
        self.assertTrue((self.root / "governance" / "risk_register.md").is_file())
        self.assertTrue((self.root / "governance" / "risk_register.json").is_file())
        self.assertIn("risk_count", out)

    def test_s8_t3_release_package(self):
        # Prepare required evidence for go/no-go computation.
        gov = self.root / "governance"
        gov.mkdir(parents=True, exist_ok=True)
        (gov / "pilot_gap_register.json").write_text(
            json.dumps({"summary": {"pilot_case_count": 10}, "gaps": []}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (gov / "risk_register.json").write_text(
            json.dumps({"blockers_open": 0, "risks": []}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        reports = self.root / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "integration_quality_report.json").write_text(
            json.dumps(
                {
                    "total_cases": 10,
                    "silent_failures": 0,
                    "hard_fail_detection_rate": 1.0,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        out = prepare_release_package(self.root)
        self.assertEqual(out["go_no_go"], "GO")
        for rel in [
            "RELEASE_NOTES_v3.md",
            "OPERATIONS_RUNBOOK.md",
            "GO_NO_GO_CHECKLIST.md",
            "POST_RELEASE_IMPROVEMENTS.md",
            "governance/GO_NO_GO_DECISION.json",
        ]:
            self.assertTrue((self.root / rel).is_file(), rel)


if __name__ == "__main__":
    unittest.main()
