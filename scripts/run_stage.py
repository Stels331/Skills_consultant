#!/usr/bin/env python3
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.router.orchestrator import StageOrchestrator


def main() -> int:
    parser = argparse.ArgumentParser(description="Run orchestrator stage (Sprint-01 skeleton)")
    parser.add_argument("workspace_id")
    parser.add_argument("stage")
    parser.add_argument("--degrade", action="store_true")
    parser.add_argument("--block", action="store_true")
    parser.add_argument("--rationale", default="")
    args = parser.parse_args()

    orchestrator = StageOrchestrator(Path(__file__).resolve().parents[1])
    result = orchestrator.run_stage(
        workspace_id=args.workspace_id,
        stage_name=args.stage,
        signals={"force_degrade": args.degrade, "force_block": args.block},
        rationale=args.rationale or None,
    )

    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
