#!/usr/bin/env python3
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pipeline.solution_portfolio import run_solution_portfolio


def main() -> int:
    parser = argparse.ArgumentParser(description="Run solution portfolio stage")
    parser.add_argument("workspace_id")
    parser.add_argument("--mode", default="local", choices=["local", "openai", "antigravity"])
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    out = run_solution_portfolio(project_root=project_root, workspace_id=args.workspace_id, llm_mode=args.mode)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
