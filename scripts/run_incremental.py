#!/usr/bin/env python3
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pipeline.dependencies import affected_stages
from app.router.orchestrator import StageOrchestrator


def main() -> int:
    parser = argparse.ArgumentParser(description="Run incremental stage checks from changed stage")
    parser.add_argument("workspace_id")
    parser.add_argument("changed_stage", choices=["intake", "layers", "viewpoints", "characterization", "problem_factory", "solution_factory", "reporting"])
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    orch = StageOrchestrator(root)

    stages = affected_stages(args.changed_stage)
    results = []
    for stage in stages:
        res = orch.run_stage(
            args.workspace_id,
            stage,
            signals={"allow_reuse": True},
            rationale="incremental_recheck",
        )
        results.append(res.__dict__)

    print(json.dumps({"workspace_id": args.workspace_id, "stages": stages, "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
