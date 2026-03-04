#!/usr/bin/env python3
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.typization.typization_engine import TypizationEngine


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/run_typization.py <workspace_id>")
        return 1

    workspace_id = sys.argv[1]
    project_root = Path(__file__).resolve().parents[1]

    engine = TypizationEngine(project_root)
    result = engine.run_for_workspace(workspace_id)

    print(
        json.dumps(
            {
                "workspace_id": workspace_id,
                "claims": result.claims_count,
                "entities": result.entities_count,
                "type_proposals": result.proposals_count,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
