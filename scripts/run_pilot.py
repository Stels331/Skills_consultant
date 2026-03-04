#!/usr/bin/env python3
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.release.pilot import run_pilot


def main() -> int:
    parser = argparse.ArgumentParser(description="Run pilot over selected workspaces")
    parser.add_argument("workspace_ids", nargs="*", help="Optional explicit workspace IDs")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    out = run_pilot(root, workspace_ids=args.workspace_ids or None)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
