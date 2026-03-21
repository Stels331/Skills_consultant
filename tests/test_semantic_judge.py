import unittest
import tempfile
from pathlib import Path

from app.principles.library import Principle
from app.validation.semantic_judge import (
    SemanticIssue,
    _has_unanchored_numeric_claims,
    _recommendation_from_issues,
    _score_from_issues,
    run_semantic_judge,
)


class SemanticJudgeTests(unittest.TestCase):
    def test_structural_and_principle_scoring_are_separated(self):
        issues = [
            SemanticIssue("BODY_TOO_SHORT", "too short", "medium"),
            SemanticIssue("ANTI_GOODHART_MISSING", "missing anti-goodhart section", "medium"),
        ]
        self.assertEqual(_recommendation_from_issues(issues), "degrade")
        self.assertLess(_score_from_issues(issues), 0.9)

    def test_local_semantic_block_for_missing_source_refs(self):
        result = run_semantic_judge(
            stage_name="intake",
            artifact_path=Path("/tmp/x.md"),
            frontmatter={
                "epistemic_status": "observed",
                "source_refs": [],
                "evidence_refs": [],
            },
            body_text="normal content",
            principles=[
                Principle(
                    principle_id="A10_EVIDENCE_GRAPH",
                    title="Evidence",
                    scope_stages=["intake"],
                    description="",
                    checklist=[],
                    source_path="/tmp/p.md",
                )
            ],
            mode="local",
        )
        self.assertEqual(result.recommendation, "block")
        self.assertTrue(any(i.code == "MISSING_SOURCE_REFS" for i in result.issues))

    def test_local_semantic_pass(self):
        result = run_semantic_judge(
            stage_name="intake",
            artifact_path=Path("/tmp/x.md"),
            frontmatter={
                "epistemic_status": "observed",
                "source_refs": ["raw/doc.md:L1"],
                "evidence_refs": [],
            },
            body_text="valid content for semantic gate",
            principles=[],
            mode="local",
        )
        self.assertEqual(result.recommendation, "pass")

    def test_viewpoint_blocks_unanchored_numeric_claims(self):
        result = run_semantic_judge(
            stage_name="viewpoints",
            artifact_path=Path("/tmp/viewpoint.md"),
            frontmatter={
                "epistemic_status": "inferred",
                "source_refs": ["layers/layer_1_business_model.md:L1"],
                "evidence_refs": [],
            },
            body_text="Бункеры переполнятся за 3-5 дней, а банкротство наступит через несколько недель.",
            principles=[],
            mode="local",
        )
        self.assertEqual(result.recommendation, "block")
        self.assertTrue(any(i.code == "UNANCHORED_NUMERIC_CLAIMS" for i in result.issues))

    def test_numeric_softener_in_other_paragraph_does_not_cancel_flag(self):
        body = (
            "Это hypothesis и rough estimate для ранней оценки.\n\n"
            "Бункеры переполнятся за 3-5 дней без дополнительных мер."
        )
        self.assertTrue(_has_unanchored_numeric_claims(body))

    def test_reporting_degrades_on_cross_case_contamination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "cases" / "case_20260319_703"
            (workspace / "analysis").mkdir(parents=True, exist_ok=True)
            artifact = workspace / "reports" / "Executive_Summary.md"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text("# summary\n", encoding="utf-8")
            (workspace / "analysis" / "domain_profile.json").write_text(
                """
{
  "workspace_id": "case_20260319_703",
  "domain_axes": [{"axis": "industrial_transformation", "score": 3, "confidence": 0.7}],
  "allowed_ontological_domains": ["industrial_transformation"],
  "forbidden_template_markers": ["BANT", "Shadow Mode", "CPQ"]
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            result = run_semantic_judge(
                stage_name="reporting",
                artifact_path=artifact,
                frontmatter={
                    "epistemic_status": "inferred",
                    "source_refs": ["reports/Analytical_Full_Report.md:L1"],
                    "evidence_refs": [],
                },
                body_text="Внедрить Shadow Mode, затем BANT-гейт и CPQ.",
                principles=[],
                mode="local",
            )

        self.assertEqual(result.recommendation, "degrade")
        self.assertTrue(any(i.code == "CROSS_CASE_CONTAMINATION" for i in result.issues))

    def test_reporting_degrades_on_boundary_soup(self):
        result = run_semantic_judge(
            stage_name="reporting",
            artifact_path=Path("/tmp/report.md"),
            frontmatter={
                "epistemic_status": "inferred",
                "source_refs": ["reports/Analytical_Full_Report.md:L1"],
                "evidence_refs": [],
            },
            body_text="The gate is legally required, must be enforced, and is accepted only with evidence_ref.",
            principles=[],
            mode="local",
        )
        self.assertEqual(result.recommendation, "degrade")
        self.assertTrue(any(i.code == "FPF_BOUNDARY_SOUP" for i in result.issues))

    def test_characteristic_target_as_fact_is_blocked(self):
        result = run_semantic_judge(
            stage_name="characterization",
            artifact_path=Path("/tmp/chr.md"),
            frontmatter={
                "epistemic_status": "inferred",
                "source_refs": ["characterization/CharacterizationPassport.md:L1"],
                "evidence_refs": [],
            },
            body_text="CHR-02-WASTE-ACCUM should be 0 and is currently a confirmed fact.",
            principles=[],
            mode="local",
        )
        self.assertEqual(result.recommendation, "block")
        self.assertTrue(any(i.code == "CHR_TARGET_PRESENTED_AS_FACT" for i in result.issues))


if __name__ == "__main__":
    unittest.main()
