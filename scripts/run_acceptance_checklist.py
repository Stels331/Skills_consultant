from __future__ import annotations

import json
import sys
from pathlib import Path

from app.testing.acceptance_checklist import run_acceptance_checklist


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python3 scripts/run_acceptance_checklist.py <workspace_id>")
        return 2
    project_root = Path(__file__).resolve().parents[1]
    workspace_id = sys.argv[1]
    workspace = project_root / "cases" / workspace_id
    result = run_acceptance_checklist(project_root, workspace)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["acceptance_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
