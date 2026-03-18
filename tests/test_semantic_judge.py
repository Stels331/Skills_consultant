import unittest
from pathlib import Path

from app.principles.library import Principle
from app.validation.semantic_judge import run_semantic_judge


class SemanticJudgeTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
