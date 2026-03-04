#!/usr/bin/env python3
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.observability.audit import build_audit_trail


def main() -> int:
    parser = argparse.ArgumentParser(description="Build audit trail report for a workspace")
    parser.add_argument("workspace_id")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    ws = root / "cases" / args.workspace_id
    out = build_audit_trail(ws)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
