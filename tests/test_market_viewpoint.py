import tempfile
import unittest
from pathlib import Path

from app.pipeline.characterization import run_characterization
from app.pipeline.intake_parser import run_intake_parser
from app.pipeline.layer_builder import build_layers
from app.pipeline.reporting import _coverage_note, _viewpoint_coverage_policy, run_reporting
from app.pipeline.viewpoint_runner import run_viewpoints
from app.state.workspace_manager import WorkspaceManager
from app.validation.artifact_contract_validator import read_frontmatter_document


class MarketViewpointTests(unittest.TestCase):
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

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_market_skill_contains_required_sections_without_case_patches(self):
        skill = (
            Path(__file__).resolve().parents[1]
            / ".agent"
            / "skills"
            / "ec-vp-market"
            / "SKILL.md"
        ).read_text(encoding="utf-8")

        for section in [
            "Market reality",
            "Demand gaps",
            "Funnel failure points",
            "Current alternatives",
            "Status quo defense",
            "Proof requirements",
            "Market-side risks",
        ]:
            self.assertIn(section, skill)

        for forbidden in ["500 куб", "термодерева", "SKU", "сухую доску"]:
            self.assertNotIn(forbidden, skill)

    def test_market_relevant_case_creates_market_viewpoint_and_reporting_mentions_it(self):
        ref = self.manager.create_workspace("case_20260319_801")
        (ref.path / "raw" / "case_input.md").write_text(
            (
                "Need market validation, client funnel clarity and demand proof.\n"
                "Sales channel is weak and buyer structure is unclear.\n"
            ),
            encoding="utf-8",
        )

        run_intake_parser(self.root, ref.workspace_id)
        build_layers(self.root, ref.workspace_id, llm_mode="local")
        vp = run_viewpoints(self.root, ref.workspace_id, llm_mode="local")
        self.assertTrue(vp["market_required"])
        self.assertEqual(vp["viewpoint_count"], 7)
        self.assertTrue((ref.path / "viewpoints" / "market.md").is_file())

        run_characterization(self.root, ref.workspace_id, llm_mode="local")
        run_reporting(self.root, ref.workspace_id, llm_mode="local")
        analytical = read_frontmatter_document(ref.path / "reports" / "Analytical_Full_Report.md").body
        self.assertIn("рынок", analytical.lower())
        self.assertNotIn("Отсутствуют обязательные точки зрения: market", analytical)

    def test_market_required_missing_viewpoint_is_reported_as_quality_defect(self):
        ref = self.manager.create_workspace("case_20260319_802")
        (ref.path / "raw" / "case_input.md").write_text(
            (
                "Need market validation and funnel repair before launch.\n"
                "Client demand and current alternatives are not confirmed.\n"
            ),
            encoding="utf-8",
        )

        run_intake_parser(self.root, ref.workspace_id)
        build_layers(self.root, ref.workspace_id, llm_mode="local")
        run_viewpoints(self.root, ref.workspace_id, llm_mode="local")
        market_path = ref.path / "viewpoints" / "market.md"
        self.assertTrue(market_path.is_file())
        market_path.unlink()
        run_characterization(self.root, ref.workspace_id, llm_mode="local")
        run_reporting(self.root, ref.workspace_id, llm_mode="local")

        analytical = read_frontmatter_document(ref.path / "reports" / "Analytical_Full_Report.md").body
        executive = read_frontmatter_document(ref.path / "reports" / "Executive_Summary.md").body
        self.assertIn("Отсутствуют обязательные точки зрения: market", analytical)
        self.assertIn("Отсутствуют обязательные точки зрения: market", executive)

    def test_non_market_case_treats_market_as_optional(self):
        ref = self.manager.create_workspace("case_20260319_803")
        (ref.path / "raw" / "case_input.md").write_text(
            "Internal governance conflict with unclear owners and execution discipline.\n",
            encoding="utf-8",
        )

        run_intake_parser(self.root, ref.workspace_id)
        build_layers(self.root, ref.workspace_id, llm_mode="local")
        run_viewpoints(self.root, ref.workspace_id, llm_mode="local")

        policy = _viewpoint_coverage_policy(ref.path)
        self.assertNotIn("market", policy["required"])
        self.assertIn("market", policy["optional"])
        note = _coverage_note(
            {
                "analysis/domain_profile.json": (ref.path / "analysis" / "domain_profile.json").read_text(encoding="utf-8"),
                "viewpoints/strategist.md": "ok",
                "viewpoints/analyst.md": "ok",
                "viewpoints/operator.md": "ok",
                "viewpoints/architect.md": "ok",
                "viewpoints/critic.md": "ok",
                "viewpoints/client.md": "ok",
                "viewpoints/market.md": "",
            }
        )
        self.assertIn("optional-точки зрения", note)
        self.assertNotIn("обязательные точки зрения: market", note)

    def test_client_and_strategist_skills_are_clean_of_market_case_patches(self):
        client_skill = (
            Path(__file__).resolve().parents[1] / ".agent" / "skills" / "ec-vp-client" / "SKILL.md"
        ).read_text(encoding="utf-8")
        strategist_skill = (
            Path(__file__).resolve().parents[1] / ".agent" / "skills" / "ec-vp-strategist" / "SKILL.md"
        ).read_text(encoding="utf-8")

        for forbidden in ["500 куб", "термодерева", "сухую доску", "поддоны", "FSC"]:
            self.assertNotIn(forbidden, client_skill)
            self.assertNotIn(forbidden, strategist_skill)


if __name__ == "__main__":
    unittest.main()
