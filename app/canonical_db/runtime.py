from __future__ import annotations

from pathlib import Path

from app.canonical_db.config import DatabaseConfig, connect
from app.canonical_db.decision_assurance import (
    SqliteDecisionAssuranceSnapshotRepository,
    SqliteDecisionWaiverRepository,
)
from app.canonical_db.decision_domain import (
    SqliteDecisionComparisonRepository,
    SqliteDecisionDraftRepository,
    SqliteDecisionEvidenceLinkRepository,
    SqliteDecisionOptionRepository,
    SqliteDecisionOutcomeRepository,
    SqliteDecisionRecordRepository,
    SqliteDecisionReviewRepository,
    SqliteProblemFrameRepository,
)
from app.canonical_db.domain import Workspace, WorkspaceVersion
from app.canonical_db.dialogue_backend import (
    SqliteDialogueMessageRepository,
    SqliteEmbeddingJobRepository,
    SqliteQuotaLedgerRepository,
    SqliteRetrievalChunkRepository,
)
from app.canonical_db.model_updates import SqliteQuestionQueueRepository, SqliteReentryJobRepository
from app.canonical_db.materializer import WorkspaceMaterializer
from app.canonical_db.repositories import (
    SqliteArtifactRepository,
    SqliteAuthSessionRepository,
    SqliteClaimRepository,
    SqliteDialogueSessionRepository,
    SqliteGovernanceEventRepository,
    SqliteMaterializedArtifactIndexRepository,
    SqliteMembershipRepository,
    SqliteOrganizationRepository,
    SqliteProjectionSnapshotRepository,
    SqliteUserRepository,
    SqliteUserProfileRepository,
    SqliteWorkspaceRepository,
    TransactionManager,
)
from app.canonical_db.service import DualWriteWorkspaceService


def repository_bundle(environment: str | None = None) -> dict[str, object]:
    config = DatabaseConfig.from_env(environment)

    def factory():
        return connect(config)

    artifacts = SqliteArtifactRepository(factory)
    claims = SqliteClaimRepository(factory, TransactionManager(factory))
    governance = SqliteGovernanceEventRepository(factory)
    workspaces = SqliteWorkspaceRepository(factory)
    return {
        "config": config,
        "factory": factory,
        "users": SqliteUserRepository(factory),
        "user_profiles": SqliteUserProfileRepository(factory),
        "organizations": SqliteOrganizationRepository(factory),
        "memberships": SqliteMembershipRepository(factory),
        "workspaces": workspaces,
        "artifacts": artifacts,
        "claims": claims,
        "dialogue_sessions": SqliteDialogueSessionRepository(factory),
        "dialogue_messages": SqliteDialogueMessageRepository(factory),
        "retrieval_chunks": SqliteRetrievalChunkRepository(factory, TransactionManager(factory)),
        "embedding_jobs": SqliteEmbeddingJobRepository(factory),
        "quota_ledger": SqliteQuotaLedgerRepository(factory),
        "question_queue": SqliteQuestionQueueRepository(factory),
        "reentry_jobs": SqliteReentryJobRepository(factory, TransactionManager(factory)),
        "auth_sessions": SqliteAuthSessionRepository(factory),
        "projection_snapshots": SqliteProjectionSnapshotRepository(factory),
        "materialized_artifact_index": SqliteMaterializedArtifactIndexRepository(factory, TransactionManager(factory)),
        "problem_frames": SqliteProblemFrameRepository(factory),
        "decision_options": SqliteDecisionOptionRepository(factory),
        "decision_comparisons": SqliteDecisionComparisonRepository(factory),
        "decision_drafts": SqliteDecisionDraftRepository(factory),
        "decision_records": SqliteDecisionRecordRepository(factory),
        "decision_evidence_links": SqliteDecisionEvidenceLinkRepository(factory, TransactionManager(factory)),
        "decision_reviews": SqliteDecisionReviewRepository(factory),
        "decision_outcomes": SqliteDecisionOutcomeRepository(factory),
        "decision_assurance_snapshots": SqliteDecisionAssuranceSnapshotRepository(factory),
        "decision_waivers": SqliteDecisionWaiverRepository(factory),
        "governance": governance,
        "materializer": WorkspaceMaterializer(workspaces, artifacts, claims, governance),
    }


def dual_write_service(environment: str | None = None) -> DualWriteWorkspaceService:
    bundle = repository_bundle(environment)
    return DualWriteWorkspaceService(
        workspace_repo=bundle["workspaces"],
        governance_repo=bundle["governance"],
        materializer=bundle["materializer"],
    )


def create_workspace_dual_write(
    workspace: Workspace,
    version: WorkspaceVersion,
    export_root: Path,
    environment: str | None = None,
) -> dict[str, str]:
    service = dual_write_service(environment)
    return service.create_workspace(workspace, version, export_root)
