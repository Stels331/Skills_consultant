from __future__ import annotations

import sys
from pathlib import Path

from app.pipeline.epistemic_debug import render_graph_summary


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/epistemic_graph_summary.py <workspace_or_graph_path>")
        return 2

    target = Path(sys.argv[1])
    graph_path = target
    if target.is_dir():
        graph_path = target / "analysis" / "epistemic_graph.json"
    print(render_graph_summary(graph_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
