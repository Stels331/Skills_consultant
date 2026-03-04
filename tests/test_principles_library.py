import tempfile
import unittest
from pathlib import Path

from app.principles.library import load_principles_for_stage


PRINCIPLE = """principle_id: GOLDILOCKS_PROBLEM
title: Goldilocks
scope_stages: problem_factory

Description:
Test principle.

Checklist:
- check one
- check two
"""


class PrinciplesLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        pdir = self.root / ".agent" / "principles"
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / "Goldilocks_Problem.md").write_text(PRINCIPLE, encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_load_principles_by_stage(self):
        ps = load_principles_for_stage(self.root, "problem_factory")
        self.assertEqual(len(ps), 1)
        self.assertEqual(ps[0].principle_id, "GOLDILOCKS_PROBLEM")
        self.assertEqual(ps[0].checklist, ["check one", "check two"])

    def test_stage_filtering(self):
        ps = load_principles_for_stage(self.root, "solution_factory")
        self.assertEqual(ps, [])


if __name__ == "__main__":
    unittest.main()
