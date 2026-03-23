from __future__ import annotations

from pathlib import Path

from app.canonical_db.domain import GovernanceEvent, Workspace, WorkspaceVersion
from app.canonical_db.materializer import WorkspaceMaterializer
from app.canonical_db.repositories import GovernanceEventRepository, WorkspaceRepository


class DualWriteWorkspaceService:
    def __init__(
        self,
        workspace_repo: WorkspaceRepository,
        governance_repo: GovernanceEventRepository,
        materializer: WorkspaceMaterializer,
    ):
        self._workspace_repo = workspace_repo
        self._governance_repo = governance_repo
        self._materializer = materializer

    def create_workspace(
        self,
        workspace: Workspace,
        version: WorkspaceVersion,
        export_root: Path,
    ) -> dict[str, str]:
        self._workspace_repo.upsert(workspace, version)
        self._governance_repo.append(
            GovernanceEvent(
                id=f"{workspace.id}:gov:workspace-created",
                organization_id=workspace.organization_id,
                workspace_id=workspace.id,
                event_type="workspace_created",
                payload={"workspace_version_id": version.id},
                actor_type="system",
                actor_id="dual-write-service",
            )
        )
        return self._materializer.materialize(workspace.id, export_root)
