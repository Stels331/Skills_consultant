import json
import tempfile
import unittest
from pathlib import Path

from app.pipeline.domain_profiler import build_domain_profile


class DomainProfilerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "cases" / "case_20260319_701"
        (self.workspace / "raw").mkdir(parents=True, exist_ok=True)
        (self.workspace / "intake").mkdir(parents=True, exist_ok=True)
        (self.workspace / "layers").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_build_domain_profile_scores_mixed_case(self):
        (self.workspace / "raw" / "case_input.md").write_text(
            (
                "Factory board lost trust after CAPEX drift.\n"
                "Need better client funnel and market validation.\n"
                "Operations bottleneck hurts throughput and delivery SLA.\n"
            ),
            encoding="utf-8",
        )

        profile = build_domain_profile(self.root, "case_20260319_701")

        self.assertEqual(profile["workspace_id"], "case_20260319_701")
        axes = {item["axis"] for item in profile["domain_axes"]}
        self.assertIn("industrial_transformation", axes)
        self.assertIn("governance_crisis", axes)
        self.assertIn("market_validation", axes)
        self.assertIn("operations_bottleneck", axes)
        self.assertEqual(profile["reasoning_scope"], "mixed")

    def test_build_domain_profile_falls_back_for_diffuse_input(self):
        (self.workspace / "raw" / "case_input.md").write_text(
            "Need help. Situation is complicated. More details later.\n",
            encoding="utf-8",
        )

        profile = build_domain_profile(self.root, "case_20260319_701")

        self.assertEqual(profile["domain_axes"][0]["axis"], "general_business_case")
        self.assertEqual(profile["reasoning_scope"], "single")

        persisted = json.loads((self.workspace / "analysis" / "domain_profile.json").read_text(encoding="utf-8"))
        self.assertEqual(persisted["domain_axes"][0]["axis"], "general_business_case")


if __name__ == "__main__":
    unittest.main()
