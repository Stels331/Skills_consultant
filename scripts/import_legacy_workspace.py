#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.canonical_db import (
    DatabaseConfig,
    LegacyWorkspaceImporter,
    SqliteArtifactRepository,
    SqliteClaimRepository,
    SqliteGovernanceEventRepository,
    SqliteWorkspaceRepository,
    TransactionManager,
    connect,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import a legacy file workspace into canonical DB")
    parser.add_argument("workspace_root")
    parser.add_argument("--organization-id", required=True)
    parser.add_argument("--created-by-user-id", required=True)
    args = parser.parse_args()

    config = DatabaseConfig.from_env()

    def factory():
        return connect(config)

    importer = LegacyWorkspaceImporter(
        workspace_repo=SqliteWorkspaceRepository(factory),
        artifact_repo=SqliteArtifactRepository(factory),
        claim_repo=SqliteClaimRepository(factory, TransactionManager(factory)),
        governance_repo=SqliteGovernanceEventRepository(factory),
    )
    report = importer.import_workspace(
        Path(args.workspace_root),
        organization_id=args.organization_id,
        created_by_user_id=args.created_by_user_id,
    )
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
