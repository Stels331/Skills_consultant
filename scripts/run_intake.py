#!/usr/bin/env python3
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pipeline.intake_parser import run_intake_parser


def main() -> int:
    parser = argparse.ArgumentParser(description="Run intake parser for workspace")
    parser.add_argument("workspace_id")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    out = run_intake_parser(project_root=project_root, workspace_id=args.workspace_id)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
