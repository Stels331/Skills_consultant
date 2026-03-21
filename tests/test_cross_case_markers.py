import json
import tempfile
import unittest
from pathlib import Path

from app.validation.cross_case_markers import check_cross_case_markers


class CrossCaseMarkersTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "cases" / "case_20260319_702"
        (self.workspace / "analysis").mkdir(parents=True, exist_ok=True)
        (self.workspace / "reports").mkdir(parents=True, exist_ok=True)
        self.artifact = self.workspace / "reports" / "Executive_Summary.md"
        self.artifact.write_text("# report\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_checker_flags_forbidden_markers_when_presales_domain_absent(self):
        (self.workspace / "analysis" / "domain_profile.json").write_text(
            json.dumps(
                {
                    "workspace_id": "case_20260319_702",
                    "domain_axes": [{"axis": "industrial_transformation", "score": 3, "confidence": 0.7}],
                    "allowed_ontological_domains": ["industrial_transformation"],
                    "forbidden_template_markers": ["BANT", "Shadow Mode", "CPQ"],
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        issues = check_cross_case_markers(
            self.artifact,
            "Пилот построен как Shadow Mode, затем BANT-гейт и CPQ для клиента.",
        )

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].code, "CROSS_CASE_CONTAMINATION")
        self.assertIn("BANT", issues[0].markers)

    def test_checker_skips_when_presales_domain_is_explicitly_active(self):
        (self.workspace / "analysis" / "domain_profile.json").write_text(
            json.dumps(
                {
                    "workspace_id": "case_20260319_702",
                    "domain_axes": [{"axis": "commercial_presales_bottleneck", "score": 4, "confidence": 0.8}],
                    "allowed_ontological_domains": ["commercial_presales_bottleneck"],
                    "forbidden_template_markers": ["BANT", "Shadow Mode", "CPQ"],
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        issues = check_cross_case_markers(
            self.artifact,
            "Пилот построен как Shadow Mode, затем BANT-гейт и CPQ для клиента.",
        )

        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
