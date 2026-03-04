#!/usr/bin/env python3
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.validation.artifact_contract_validator import validate_artifact_contract


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/validate_artifact_contract.py <artifact_path>")
        return 1

    artifact_path = Path(sys.argv[1]).resolve()
    project_root = Path(__file__).resolve().parents[1]

    try:
        workspace_path = artifact_path
        while workspace_path.name != "cases" and workspace_path.parent != workspace_path:
            workspace_path = workspace_path.parent
        if workspace_path.name == "cases":
            workspace_path = artifact_path
            while workspace_path.parent.name != "cases" and workspace_path.parent != workspace_path:
                workspace_path = workspace_path.parent
            if workspace_path.parent.name != "cases":
                workspace_path = None
        else:
            workspace_path = None
    except Exception:
        workspace_path = None

    result = validate_artifact_contract(
        project_root=project_root,
        artifact_path=artifact_path,
        workspace_path=workspace_path,
    )
    payload = {
        "artifact": str(artifact_path),
        "is_valid": result.is_valid,
        "issues": [issue.__dict__ for issue in result.issues],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.is_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
