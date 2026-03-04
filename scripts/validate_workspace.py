#!/usr/bin/env python3
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.validation.artifact_contract_validator import validate_workspace_artifact_contracts
from app.validation.schema_validator import validate_workspace


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/validate_workspace.py <workspace_id>")
        return 1

    workspace_id = sys.argv[1]
    project_root = Path(__file__).resolve().parents[1]
    workspace = project_root / "cases" / workspace_id

    schema_results = validate_workspace(project_root, workspace)
    contract_results = validate_workspace_artifact_contracts(project_root, workspace)

    payload = {
        "schema_validation": {},
        "artifact_contract_validation": {},
    }
    has_errors = False
    for rel, result in schema_results.items():
        payload["schema_validation"][rel] = {
            "is_valid": result.is_valid,
            "issues": [issue.__dict__ for issue in result.issues],
        }
        has_errors = has_errors or (not result.is_valid)

    for rel, result in contract_results.items():
        payload["artifact_contract_validation"][rel] = {
            "is_valid": result.is_valid,
            "issues": [issue.__dict__ for issue in result.issues],
        }
        has_errors = has_errors or (not result.is_valid)

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
