import json
import tempfile
import unittest
from pathlib import Path

from app.validation.cross_case_contamination_validator import validate_cross_case_contamination


class CrossCaseContaminationValidatorTests(unittest.TestCase):
    def test_validator_flags_semantically_alien_domain(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "cases" / "case_20260319_5001"
            (workspace / "analysis").mkdir(parents=True, exist_ok=True)
            artifact = workspace / "reports" / "Executive_Summary.md"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text("report", encoding="utf-8")
            (workspace / "analysis" / "domain_profile.json").write_text(
                json.dumps(
                    {
                        "workspace_id": workspace.name,
                        "domain_axes": [{"axis": "industrial_transformation", "score": 4, "confidence": 0.9}],
                        "allowed_ontological_domains": ["industrial_transformation"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            issues = validate_cross_case_contamination(artifact, "Need BANT and CPQ before lead qualification.")
            self.assertTrue(any(issue.code == "SEMANTIC_DOMAIN_DRIFT" for issue in issues))

    def test_validator_allows_mixed_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "cases" / "case_20260319_5002"
            (workspace / "analysis").mkdir(parents=True, exist_ok=True)
            artifact = workspace / "reports" / "Executive_Summary.md"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text("report", encoding="utf-8")
            (workspace / "analysis" / "domain_profile.json").write_text(
                json.dumps(
                    {
                        "workspace_id": workspace.name,
                        "domain_axes": [
                            {"axis": "industrial_transformation", "score": 4, "confidence": 0.9},
                            {"axis": "market_validation", "score": 2, "confidence": 0.5},
                        ],
                        "allowed_ontological_domains": ["industrial_transformation", "market_validation"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            issues = validate_cross_case_contamination(artifact, "Pricing and buyers must align with throughput.")
            self.assertEqual(issues, [])

    def test_alien_vocabulary_triggers_high_severity(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "cases" / "case_20260319_5003"
            (workspace / "analysis").mkdir(parents=True, exist_ok=True)
            artifact = workspace / "reports" / "Executive_Summary.md"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text("report", encoding="utf-8")
            (workspace / "analysis" / "domain_profile.json").write_text(
                json.dumps(
                    {
                        "workspace_id": workspace.name,
                        "domain_axes": [{"axis": "industrial_transformation", "score": 4, "confidence": 0.9}],
                        "allowed_ontological_domains": ["industrial_transformation"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            issues = validate_cross_case_contamination(artifact, "Need BANT, CPQ, presales and sales funnel redesign.")
            self.assertEqual(issues[0].severity, "high")


if __name__ == "__main__":
    unittest.main()
