import tempfile
import unittest
from pathlib import Path

from app.pipeline.epistemic_debug import render_graph_summary


class EpistemicDebugTests(unittest.TestCase):
    def test_summary_handles_missing_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "epistemic_graph.json"
            summary = render_graph_summary(path)
        self.assertIn("empty", summary.lower())

    def test_corrupted_graph_raises_readable_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "epistemic_graph.json"
            path.write_text("{not-json", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "CORRUPTED_EPISTEMIC_GRAPH"):
                render_graph_summary(path)


if __name__ == "__main__":
    unittest.main()
