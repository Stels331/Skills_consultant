from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.canonical_db.repositories import (
    ArtifactRepository,
    ClaimRepository,
    GovernanceEventRepository,
    WorkspaceRepository,
)
from app.state.workspace_manager import REQUIRED_DIRS


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


class WorkspaceMaterializer:
    def __init__(
        self,
        workspace_repo: WorkspaceRepository,
        artifact_repo: ArtifactRepository,
        claim_repo: ClaimRepository,
        governance_repo: GovernanceEventRepository,
    ):
        self._workspace_repo = workspace_repo
        self._artifact_repo = artifact_repo
        self._claim_repo = claim_repo
        self._governance_repo = governance_repo

    def materialize(self, workspace_id: str, export_root: Path) -> dict[str, str]:
        workspace = self._workspace_repo.get(workspace_id)
        if workspace is None:
            raise FileNotFoundError(f"Workspace not found in canonical DB: {workspace_id}")
        artifacts = self._artifact_repo.list_for_workspace(workspace_id)
        claims = self._claim_repo.list_for_workspace(workspace_id)
        events = self._governance_repo.list_for_workspace(workspace_id)
        workspace_dir = export_root / workspace.workspace_key
        workspace_dir.mkdir(parents=True, exist_ok=True)
        for rel in REQUIRED_DIRS:
            (workspace_dir / rel).mkdir(parents=True, exist_ok=True)

        desired_files = {
            "workspace_metadata.json": {
                "workspace_id": workspace.id,
                "title": workspace.title,
                "case_type": workspace.case_type,
                "state": workspace.status.upper(),
                "current_stage": workspace.current_stage,
                "active_model_version": workspace.active_model_version,
                "reentry_status": workspace.reentry_status,
                "metadata": workspace.metadata,
            },
            "state/session_state.json": {
                "workspace_id": workspace.id,
                "current_phase": workspace.current_stage.upper(),
                "last_phase": None,
            },
            "state/version_changelog.json": {
                "workspace_id": workspace.id,
                "events": [event.payload for event in events],
            },
            "model/model_version.json": {
                "workspace_id": workspace.id,
                "current_version": workspace.active_model_version,
            },
            "model/case_model.json": {
                "workspace_id": workspace.id,
                "claims": [claim.attributes for claim in claims],
                "relations": [],
            },
            "dialogue/question_queue.json": {
                "workspace_id": workspace.id,
                "questions": [],
            },
        }

        for artifact in artifacts:
            if artifact.format == "json":
                desired_files[artifact.file_path] = artifact.payload
            elif artifact.format == "text":
                desired_files[artifact.file_path] = artifact.payload

        fingerprints: dict[str, str] = {}
        for rel_path, payload in sorted(desired_files.items()):
            destination = workspace_dir / rel_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            content = (
                _canonical_json(payload)
                if isinstance(payload, dict)
                else json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
            )
            if destination.exists():
                existing = destination.read_text(encoding="utf-8")
                if existing != content:
                    self._governance_repo.append(
                        event=_sync_error_event(workspace.organization_id, workspace.id, rel_path)
                    )
            destination.write_text(content, encoding="utf-8")
            fingerprints[rel_path] = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return fingerprints


def _sync_error_event(organization_id: str, workspace_id: str, rel_path: str):
    from app.canonical_db.domain import GovernanceEvent

    return GovernanceEvent(
        id=f"{workspace_id}:sync:{rel_path}",
        organization_id=organization_id,
        workspace_id=workspace_id,
        event_type="sync_error",
        payload={"file_path": rel_path},
        actor_type="system",
        actor_id="materializer",
    )
