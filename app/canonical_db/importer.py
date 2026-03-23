from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from app.canonical_db.domain import Artifact, Claim, ClaimRelation, GovernanceEvent, Workspace, WorkspaceVersion
from app.canonical_db.repositories import (
    ArtifactRepository,
    ClaimRepository,
    GovernanceEventRepository,
    WorkspaceRepository,
)


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@dataclass
class ImportReport:
    workspace_id: str
    source_path: str
    created: bool
    stats: dict[str, int] = field(default_factory=dict)
    partial_failures: list[str] = field(default_factory=list)
    skipped_sections: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "source_path": self.source_path,
            "created": self.created,
            "stats": self.stats,
            "partial_failures": self.partial_failures,
            "skipped_sections": self.skipped_sections,
        }


class LegacyWorkspaceImporter:
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

    def import_workspace(
        self,
        workspace_root: Path,
        organization_id: str,
        created_by_user_id: str,
    ) -> ImportReport:
        metadata = _read_json(workspace_root / "workspace_metadata.json")
        workspace_id = metadata["workspace_id"]
        workspace_key = workspace_id
        source_path = str(workspace_root.resolve())
        created = self._workspace_repo.get(workspace_id) is None

        workspace = Workspace(
            id=workspace_id,
            organization_id=organization_id,
            workspace_key=workspace_key,
            title=metadata.get("title", workspace_id),
            case_type=metadata.get("case_type", "legacy"),
            status=metadata.get("state", "ACTIVE").lower(),
            current_stage=metadata.get("current_stage", "intake"),
            active_model_version=int(_read_json(workspace_root / "model" / "model_version.json").get("current_version", 0)),
            created_by_user_id=created_by_user_id,
            metadata={
                "migrated_from": source_path,
                "legacy_metadata": metadata,
            },
            reentry_status=metadata.get("reentry_status", "idle"),
        )
        version = WorkspaceVersion(
            id=f"{workspace_id}:v{workspace.active_model_version}",
            organization_id=organization_id,
            workspace_id=workspace_id,
            version_no=workspace.active_model_version,
            version_label=f"legacy-v{workspace.active_model_version}",
            change_reason="legacy_import",
            created_by=created_by_user_id,
        )
        self._workspace_repo.upsert(workspace, version)

        artifacts: list[Artifact] = []
        claims: list[Claim] = []
        relations: list[ClaimRelation] = []
        events: list[GovernanceEvent] = []
        report = ImportReport(
            workspace_id=workspace_id,
            source_path=source_path,
            created=created,
            stats={"artifacts": 0, "claims": 0, "relations": 0, "governance_events": 0},
        )

        for file_path in sorted(workspace_root.rglob("*")):
            if not file_path.is_file():
                continue
            rel_path = file_path.relative_to(workspace_root).as_posix()
            if rel_path.endswith(".tmp"):
                continue
            try:
                if file_path.suffix == ".json":
                    payload = _read_json(file_path)
                    fmt = "json"
                else:
                    payload = {"text": file_path.read_text(encoding="utf-8")}
                    fmt = "text"
            except Exception as exc:
                report.partial_failures.append(f"{rel_path}: {exc}")
                continue

            artifacts.append(
                Artifact(
                    id=f"{workspace_id}:artifact:{rel_path}",
                    organization_id=organization_id,
                    workspace_id=workspace_id,
                    workspace_version_id=version.id,
                    artifact_type=_artifact_type_for(rel_path),
                    stage_name=rel_path.split("/", 1)[0],
                    artifact_key=rel_path,
                    status="active",
                    format=fmt,
                    payload=payload,
                    file_path=rel_path,
                    summary_text=rel_path,
                )
            )
            report.stats["artifacts"] += 1

        case_model_path = workspace_root / "model" / "case_model.json"
        if case_model_path.exists():
            case_model = _read_json(case_model_path)
            for raw_claim in case_model.get("claims", []):
                claim_id = raw_claim.get("claim_id") or f"{workspace_id}:claim:{raw_claim.get('claim_key', len(claims)+1)}"
                claims.append(
                    Claim(
                        id=claim_id,
                        organization_id=organization_id,
                        workspace_id=workspace_id,
                        workspace_version_id=version.id,
                        claim_key=raw_claim.get("claim_key", claim_id),
                        claim_type=raw_claim.get("claim_type", "source_fact"),
                        statement=raw_claim.get("statement", ""),
                        epistemic_status=raw_claim.get("epistemic_status", "accepted"),
                        confidence_score=float(raw_claim.get("confidence_score", 1.0)),
                        source_kind=raw_claim.get("source_kind", "legacy_workspace"),
                        source_ref=raw_claim.get("source_ref", "model/case_model.json"),
                        attributes=raw_claim,
                    )
                )
            for raw_relation in case_model.get("relations", []):
                relations.append(
                    ClaimRelation(
                        id=raw_relation.get("relation_id") or f"{workspace_id}:relation:{len(relations)+1}",
                        organization_id=organization_id,
                        workspace_id=workspace_id,
                        from_claim_id=raw_relation["from_claim_id"],
                        to_claim_id=raw_relation["to_claim_id"],
                        relation_type=raw_relation.get("relation_type", "supports"),
                        weight=float(raw_relation.get("weight", 1.0)),
                        metadata=raw_relation,
                    )
                )

        changelog_path = workspace_root / "state" / "version_changelog.json"
        if changelog_path.exists():
            changelog = _read_json(changelog_path)
            for index, raw_event in enumerate(changelog.get("events", []), start=1):
                events.append(
                    GovernanceEvent(
                        id=f"{workspace_id}:gov:{index}",
                        organization_id=organization_id,
                        workspace_id=workspace_id,
                        event_type=raw_event.get("event_type", "legacy_event"),
                        payload=raw_event,
                        actor_type="system",
                        actor_id="legacy-importer",
                    )
                )
        else:
            report.skipped_sections.append("state/version_changelog.json")

        self._artifact_repo.upsert_many(artifacts)
        self._claim_repo.replace_workspace_claims(workspace_id, claims, relations)
        for event in events:
            self._governance_repo.append(event)

        report.stats["claims"] = len(claims)
        report.stats["relations"] = len(relations)
        report.stats["governance_events"] = len(events)
        return report


def _artifact_type_for(rel_path: str) -> str:
    if rel_path.endswith("workspace_metadata.json"):
        return "workspace_metadata"
    if rel_path.endswith("question_queue.json"):
        return "question_queue"
    if rel_path.endswith("case_model.json"):
        return "case_model"
    return rel_path.split("/", 1)[0].replace("/", "_")
