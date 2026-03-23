from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import sqlite3
from typing import Sequence

from app.canonical_db.domain import (
    Claim,
    GovernanceEvent,
    QuestionQueueItem,
    ReentryJobRecord,
    WorkspaceVersion,
)
from app.canonical_db.projections import MaterializedArtifactIndex, ProjectionService, ProjectionRegistry
from app.canonical_db.repositories import (
    ClaimRepository,
    ConnectionFactory,
    GovernanceEventRepository,
    MaterializedArtifactIndexRepository,
    ProjectionSnapshotRepository,
    TransactionManager,
    WorkspaceRepository,
)


PROVISIONAL_TYPE_MAP = {
    "user_asserted_fact": "hypothesis",
    "user_declared_constraint": "decision_constraint",
    "user_hypothesis": "hypothesis",
    "user_normative_target": "normative_target",
}

QUEUE_STATUS_TO_DB = {
    "open": "active",
    "answered": "completed",
    "rejected": "failed",
    "obsolete": "archived",
}
QUEUE_STATUS_FROM_DB = {value: key for key, value in QUEUE_STATUS_TO_DB.items()}

REENTRY_STATUS_TO_DB = {
    "queued": "queued",
    "in_progress": "running",
    "completed": "completed",
    "failed": "failed",
}
REENTRY_STATUS_FROM_DB = {value: key for key, value in REENTRY_STATUS_TO_DB.items()}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class TypedInputClassification:
    provisional_type: str
    confidence: float
    rationale: str
    route: str


@dataclass(frozen=True)
class AcceptanceDecision:
    status: str
    reason_code: str | None
    explanation: str


@dataclass(frozen=True)
class ReentryPlan:
    workspace_id: str
    trigger_claim_id: str
    dependent_projections: list[str]
    affected_stages: list[str]
    stale_outputs: list[str]


class SqliteQuestionQueueRepository:
    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def upsert(self, item: QuestionQueueItem) -> QuestionQueueItem:
        with self._connection_factory() as connection:
            connection.execute(
                """
                INSERT INTO question_queue (
                    id, organization_id, workspace_id, session_id, question_class, status,
                    question_text, priority, reason_code, influence_area, impact_preview, rationale, classifier_confidence
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    session_id = excluded.session_id,
                    question_class = excluded.question_class,
                    status = excluded.status,
                    question_text = excluded.question_text,
                    priority = excluded.priority,
                    reason_code = excluded.reason_code,
                    influence_area = excluded.influence_area,
                    impact_preview = excluded.impact_preview,
                    rationale = excluded.rationale,
                    classifier_confidence = excluded.classifier_confidence
                """,
                (
                    item.id,
                    item.organization_id,
                    item.workspace_id,
                    item.session_id,
                    item.question_class,
                    QUEUE_STATUS_TO_DB.get(item.status, item.status),
                    item.question_text,
                    item.priority,
                    item.reason_code,
                    item.influence_area,
                    item.impact_preview,
                    item.rationale,
                    item.classifier_confidence,
                ),
            )
        return item

    def list_for_workspace(self, workspace_id: str, *, include_closed: bool = False) -> list[QuestionQueueItem]:
        query = """
            SELECT id, organization_id, workspace_id, session_id, question_class, status, question_text, priority,
                   reason_code, influence_area, impact_preview, rationale, classifier_confidence
            FROM question_queue
            WHERE workspace_id = ?
        """
        params: list[object] = [workspace_id]
        if not include_closed:
            query += " AND status NOT IN ('archived', 'failed', 'completed')"
        query += " ORDER BY priority ASC, created_at ASC, id ASC"
        with self._connection_factory() as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            QuestionQueueItem(
                id=row["id"],
                organization_id=row["organization_id"],
                workspace_id=row["workspace_id"],
                session_id=row["session_id"],
                question_class=row["question_class"],
                status=QUEUE_STATUS_FROM_DB.get(row["status"], row["status"]),
                question_text=row["question_text"],
                priority=row["priority"],
                reason_code=row["reason_code"],
                influence_area=row["influence_area"],
                impact_preview=row["impact_preview"],
                rationale=row["rationale"],
                classifier_confidence=row["classifier_confidence"],
            )
            for row in rows
        ]


    def get(self, item_id: str) -> QuestionQueueItem | None:
        with self._connection_factory() as connection:
            row = connection.execute(
                """
                SELECT id, organization_id, workspace_id, session_id, question_class, status, question_text, priority,
                       reason_code, influence_area, impact_preview, rationale, classifier_confidence
                FROM question_queue
                WHERE id = ?
                """,
                (item_id,),
            ).fetchone()
        if row is None:
            return None
        return QuestionQueueItem(
            id=row["id"],
            organization_id=row["organization_id"],
            workspace_id=row["workspace_id"],
            session_id=row["session_id"],
            question_class=row["question_class"],
            status=QUEUE_STATUS_FROM_DB.get(row["status"], row["status"]),
            question_text=row["question_text"],
            priority=row["priority"],
            reason_code=row["reason_code"],
            influence_area=row["influence_area"],
            impact_preview=row["impact_preview"],
            rationale=row["rationale"],
            classifier_confidence=row["classifier_confidence"],
        )


class SqliteReentryJobRepository:
    def __init__(
        self,
        connection_factory: ConnectionFactory,
        transaction_manager: TransactionManager | None = None,
    ):
        self._connection_factory = connection_factory
        self._transactions = transaction_manager or TransactionManager(connection_factory)

    def upsert(self, job: ReentryJobRecord) -> ReentryJobRecord:
        with self._connection_factory() as connection:
            connection.execute(
                """
                INSERT INTO reentry_jobs (
                    id, organization_id, workspace_id, workspace_version_id, status, trigger_claim_id,
                    dependent_projections_json, affected_stages_json, stale_outputs_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    workspace_version_id = excluded.workspace_version_id,
                    status = excluded.status,
                    trigger_claim_id = excluded.trigger_claim_id,
                    dependent_projections_json = excluded.dependent_projections_json,
                    affected_stages_json = excluded.affected_stages_json,
                    stale_outputs_json = excluded.stale_outputs_json
                """,
                (
                    job.id,
                    job.organization_id,
                    job.workspace_id,
                    job.workspace_version_id,
                    REENTRY_STATUS_TO_DB.get(job.status, job.status),
                    job.trigger_claim_id,
                    json.dumps(job.dependent_projections, ensure_ascii=False),
                    json.dumps(job.affected_stages, ensure_ascii=False),
                    json.dumps(job.stale_outputs, ensure_ascii=False),
                ),
            )
        return job

    def list_for_workspace(self, workspace_id: str) -> list[ReentryJobRecord]:
        with self._connection_factory() as connection:
            rows = connection.execute(
                """
                SELECT id, organization_id, workspace_id, workspace_version_id, status, trigger_claim_id,
                       dependent_projections_json, affected_stages_json, stale_outputs_json
                FROM reentry_jobs
                WHERE workspace_id = ?
                ORDER BY created_at, id
                """,
                (workspace_id,),
            ).fetchall()
        return [
            ReentryJobRecord(
                id=row["id"],
                organization_id=row["organization_id"],
                workspace_id=row["workspace_id"],
                workspace_version_id=row["workspace_version_id"],
                status=REENTRY_STATUS_FROM_DB.get(row["status"], row["status"]),
                trigger_claim_id=row["trigger_claim_id"],
                dependent_projections=json.loads(row["dependent_projections_json"] or "[]"),
                affected_stages=json.loads(row["affected_stages_json"] or "[]"),
                stale_outputs=json.loads(row["stale_outputs_json"] or "[]"),
            )
            for row in rows
        ]

    def get(self, job_id: str) -> ReentryJobRecord | None:
        with self._connection_factory() as connection:
            row = connection.execute(
                """
                SELECT id, organization_id, workspace_id, workspace_version_id, status, trigger_claim_id,
                       dependent_projections_json, affected_stages_json, stale_outputs_json
                FROM reentry_jobs
                WHERE id = ?
                """,
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return ReentryJobRecord(
            id=row["id"],
            organization_id=row["organization_id"],
            workspace_id=row["workspace_id"],
            workspace_version_id=row["workspace_version_id"],
            status=REENTRY_STATUS_FROM_DB.get(row["status"], row["status"]),
            trigger_claim_id=row["trigger_claim_id"],
            dependent_projections=json.loads(row["dependent_projections_json"] or "[]"),
            affected_stages=json.loads(row["affected_stages_json"] or "[]"),
            stale_outputs=json.loads(row["stale_outputs_json"] or "[]"),
        )

    def try_lock_workspace(self, workspace_id: str) -> bool:
        with self._transactions.transaction() as connection:
            row = connection.execute(
                "SELECT reentry_status FROM workspaces WHERE id = ?",
                (workspace_id,),
            ).fetchone()
            if row is None:
                raise KeyError(workspace_id)
            if row["reentry_status"] == "in_progress":
                return False
            connection.execute(
                "UPDATE workspaces SET reentry_status = 'in_progress', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (workspace_id,),
            )
        return True

    def release_workspace(self, workspace_id: str, *, status: str) -> None:
        with self._connection_factory() as connection:
            connection.execute(
                "UPDATE workspaces SET reentry_status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, workspace_id),
            )


class ClarificationEngine:
    def __init__(self, queue: SqliteQuestionQueueRepository):
        self._queue = queue

    def open_question(
        self,
        *,
        organization_id: str,
        workspace_id: str,
        session_id: str | None,
        reason: str,
        missing_knowledge: str,
        impact_preview: str,
    ) -> QuestionQueueItem:
        item = QuestionQueueItem(
            id=f"qq:{workspace_id}:{abs(hash((reason, missing_knowledge, impact_preview))) % 100000}",
            organization_id=organization_id,
            workspace_id=workspace_id,
            session_id=session_id,
            question_class="clarification_needed",
            status="open",
            question_text=missing_knowledge,
            priority=10,
            reason_code=reason,
            influence_area=impact_preview,
            impact_preview=impact_preview,
            rationale=f"Need clarification for {reason}",
        )
        return self._queue.upsert(item)

    def mark_answered(self, item: QuestionQueueItem) -> QuestionQueueItem:
        return self._queue.upsert(
            QuestionQueueItem(
                id=item.id,
                organization_id=item.organization_id,
                workspace_id=item.workspace_id,
                session_id=item.session_id,
                question_class=item.question_class,
                status="answered",
                question_text=item.question_text,
                priority=item.priority,
                reason_code=item.reason_code,
                influence_area=item.influence_area,
                impact_preview=item.impact_preview,
                rationale=item.rationale,
                classifier_confidence=item.classifier_confidence,
            )
        )

    def mark_obsolete(self, item: QuestionQueueItem) -> QuestionQueueItem:
        return self._queue.upsert(
            QuestionQueueItem(
                id=item.id,
                organization_id=item.organization_id,
                workspace_id=item.workspace_id,
                session_id=item.session_id,
                question_class=item.question_class,
                status="obsolete",
                question_text=item.question_text,
                priority=item.priority,
                reason_code=item.reason_code,
                influence_area=item.influence_area,
                impact_preview=item.impact_preview,
                rationale=item.rationale,
                classifier_confidence=item.classifier_confidence,
            )
        )

    def mark_rejected(self, item: QuestionQueueItem, *, rationale: str) -> QuestionQueueItem:
        return self._queue.upsert(
            QuestionQueueItem(
                id=item.id,
                organization_id=item.organization_id,
                workspace_id=item.workspace_id,
                session_id=item.session_id,
                question_class=item.question_class,
                status="rejected",
                question_text=item.question_text,
                priority=item.priority,
                reason_code=item.reason_code,
                influence_area=item.influence_area,
                impact_preview=item.impact_preview,
                rationale=rationale,
                classifier_confidence=item.classifier_confidence,
            )
        )


class TypedInputClassifier:
    def classify(self, text: str) -> TypedInputClassification:
        raw = text.strip().lower()
        if raw.endswith("?"):
            return TypedInputClassification("user_hypothesis", 0.35, "question_form_detected", "ordinary_question")
        if any(marker in raw for marker in ("must", "should", "нужно", "должен", "обязан")):
            return TypedInputClassification("user_declared_constraint", 0.81, "normative_constraint_markers", "model_update")
        if any(marker in raw for marker in ("target", "goal", "цель", "должны достигнуть")):
            return TypedInputClassification("user_normative_target", 0.76, "target_markers", "model_update")
        if any(marker in raw for marker in ("maybe", "might", "может быть", "предполож")):
            return TypedInputClassification("user_hypothesis", 0.72, "hypothesis_markers", "clarification_provided")
        return TypedInputClassification("user_asserted_fact", 0.67, "default_assertion", "clarification_provided")


class InputAcceptanceCheck:
    def __init__(self, claims: ClaimRepository):
        self._claims = claims

    def evaluate(
        self,
        *,
        workspace_id: str,
        text: str,
        classification: TypedInputClassification,
    ) -> AcceptanceDecision:
        raw = text.strip()
        lower = raw.lower()
        if raw.endswith("?"):
            return AcceptanceDecision("rejected", "QUESTION_AS_STATEMENT", "Input is still a question and cannot be accepted as a claim.")
        if lower.startswith("if ") or lower.startswith("если "):
            return AcceptanceDecision("rejected", "CONDITIONAL_INPUT", "Conditional statements cannot become fact-grade claims directly.")
        if len(raw) < 12:
            return AcceptanceDecision("deferred", "INSUFFICIENT_CONCRETENESS", "Input is too vague for direct model update.")
        stable_claims = self._claims.list_for_workspace(workspace_id)
        for claim in stable_claims:
            if claim.epistemic_status == "accepted" and claim.claim_type == "source_fact":
                normalized_claim = " ".join(claim.statement.lower().split())
                claim_without_not = normalized_claim.replace(" not ", " ")
                normalized_input = " ".join(lower.split())
                input_without_not = normalized_input.replace(" not ", " ")
                if normalized_input != normalized_claim and (
                    normalized_input == claim_without_not
                    or input_without_not == normalized_claim
                    or ("not" in normalized_input and claim_without_not in normalized_input)
                    or ("not" in normalized_claim and input_without_not in normalized_claim)
                ):
                    return AcceptanceDecision("deferred", "CONFLICTS_WITH_STABLE_CLAIM", "Input conflicts with a stable claim and needs review.")
        if classification.provisional_type == "user_asserted_fact":
            return AcceptanceDecision("accepted", None, "Accepted as intermediate user-origin claim.")
        return AcceptanceDecision("accepted", None, "Accepted for controlled model update.")


class ModelUpdateEngine:
    def __init__(
        self,
        claims: ClaimRepository,
        governance: GovernanceEventRepository,
        projection_service: ProjectionService,
    ):
        self._claims = claims
        self._governance = governance
        self._projection_service = projection_service

    def create_intermediate_claim(
        self,
        *,
        organization_id: str,
        workspace_id: str,
        workspace_version_id: str,
        user_id: str,
        source_text: str,
        classification: TypedInputClassification,
    ) -> Claim:
        provisional_type = PROVISIONAL_TYPE_MAP[classification.provisional_type]
        claim = Claim(
            id=f"user-claim:{workspace_id}:{abs(hash((source_text, user_id, workspace_version_id))) % 100000}",
            organization_id=organization_id,
            workspace_id=workspace_id,
            workspace_version_id=workspace_version_id,
            claim_key=f"user_update_{abs(hash(source_text)) % 100000}",
            claim_type=provisional_type,
            statement=source_text,
            epistemic_status="provisional_user_input",
            confidence_score=classification.confidence,
            source_kind="dialogue_clarification",
            source_ref=f"user:{user_id}",
            attributes={
                "actor": "user",
                "provisional_type": classification.provisional_type,
                "classification_rationale": classification.rationale,
                "workspace_version_context": workspace_version_id,
                "created_at": _utc_now(),
            },
        )
        created = self._claims.create_claim(
            claim,
            change_reason="clarification_accepted",
            changed_by_actor=user_id,
        )
        self._governance.append(
            GovernanceEvent(
                id=f"gov:{created.id}:claim_created",
                organization_id=organization_id,
                workspace_id=workspace_id,
                event_type="claim_created",
                payload={"claim_id": created.id, "provisional_type": classification.provisional_type},
                actor_type="user",
                actor_id=user_id,
            )
        )
        self._projection_service.mark_stale_for_claim_type(workspace_id, created.claim_type)
        return created

    def promote_claim(
        self,
        *,
        claim_id: str,
        target_type: str,
        workspace_version_id: str,
        actor_id: str,
    ) -> Claim:
        current_versions = self._claims.list_versions(claim_id)
        current = self._claims.update_claim(
            claim_id,
            workspace_version_id=workspace_version_id,
            claim_type=target_type,
            statement=current_versions[-1].statement,
            epistemic_status="accepted",
            confidence_score=current_versions[-1].confidence_score,
            source_kind=current_versions[-1].source_kind,
            source_ref=current_versions[-1].source_ref,
            attributes={**current_versions[-1].attributes, "promoted_to": target_type},
            change_reason="lawful_promotion",
            changed_by_actor=actor_id,
        )
        self._governance.append(
            GovernanceEvent(
                id=f"gov:{claim_id}:claim_promoted",
                organization_id=current.organization_id,
                workspace_id=current.workspace_id,
                event_type="claim_promoted",
                payload={"claim_id": claim_id, "target_type": target_type},
                actor_type="system",
                actor_id=actor_id,
            )
        )
        return current


class ReentryPlanner:
    def __init__(
        self,
        registry: ProjectionRegistry,
        artifact_index: MaterializedArtifactIndex,
        snapshots: ProjectionSnapshotRepository,
    ):
        self._registry = registry
        self._artifact_index = artifact_index
        self._snapshots = snapshots

    def plan(self, *, workspace_id: str, claim: Claim) -> ReentryPlan:
        dependent = self._registry.projection_types_for_claim_type(claim.claim_type)
        affected_stages: set[str] = set()
        stale_outputs: set[str] = set()
        for projection_type in dependent:
            affected = self._artifact_index.affected_outputs(workspace_id, projection_type)
            affected_stages.update(affected["stages"])
            stale_outputs.update(affected["outputs"])
        self._snapshots.mark_stale(workspace_id, dependent)
        return ReentryPlan(
            workspace_id=workspace_id,
            trigger_claim_id=claim.id,
            dependent_projections=sorted(dependent),
            affected_stages=sorted(affected_stages),
            stale_outputs=sorted(stale_outputs),
        )


class ReentryWorker:
    def __init__(
        self,
        jobs: SqliteReentryJobRepository,
        workspaces: WorkspaceRepository,
        projection_service: ProjectionService,
        governance: GovernanceEventRepository,
    ):
        self._jobs = jobs
        self._workspaces = workspaces
        self._projection_service = projection_service
        self._governance = governance

    def submit(self, *, organization_id: str, workspace_id: str, pending_version: WorkspaceVersion, plan: ReentryPlan) -> ReentryJobRecord:
        job = ReentryJobRecord(
            id=f"reentry:{workspace_id}:{pending_version.id}",
            organization_id=organization_id,
            workspace_id=workspace_id,
            workspace_version_id=pending_version.id,
            status="queued",
            trigger_claim_id=plan.trigger_claim_id,
            dependent_projections=plan.dependent_projections,
            affected_stages=plan.affected_stages,
            stale_outputs=plan.stale_outputs,
        )
        return self._jobs.upsert(job)

    def execute(self, job_id: str) -> ReentryJobRecord:
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        if not self._jobs.try_lock_workspace(job.workspace_id):
            raise PermissionError("workspace lock already held")
        try:
            queued = ReentryJobRecord(
                id=job.id,
                organization_id=job.organization_id,
                workspace_id=job.workspace_id,
                workspace_version_id=job.workspace_version_id,
                status="in_progress",
                trigger_claim_id=job.trigger_claim_id,
                dependent_projections=job.dependent_projections,
                affected_stages=job.affected_stages,
                stale_outputs=job.stale_outputs,
            )
            self._jobs.upsert(queued)
            workspace = self._workspaces.get(job.workspace_id)
            if workspace is None or job.workspace_version_id is None:
                raise KeyError(job.workspace_id)
            published_version = int(job.workspace_version_id.rsplit(":v", 1)[-1])
            self._projection_service.rebuild_workspace_projections(
                organization_id=job.organization_id,
                workspace_id=job.workspace_id,
                workspace_version_id=job.workspace_version_id,
            )
            next_workspace = WorkspaceVersion(
                id=job.workspace_version_id,
                organization_id=job.organization_id,
                workspace_id=job.workspace_id,
                version_no=published_version,
                version_label=f"v{published_version}",
                change_reason="reentry_publish",
                created_by=workspace.created_by_user_id,
            )
            self._workspaces.upsert(
                type(workspace)(
                    id=workspace.id,
                    organization_id=workspace.organization_id,
                    workspace_key=workspace.workspace_key,
                    title=workspace.title,
                    case_type=workspace.case_type,
                    status=workspace.status,
                    current_stage=workspace.current_stage,
                    active_model_version=published_version,
                    created_by_user_id=workspace.created_by_user_id,
                    metadata=workspace.metadata,
                    reentry_status="idle",
                ),
                next_workspace,
            )
            for projection_type in job.dependent_projections:
                self._governance.append(
                    GovernanceEvent(
                        id=f"gov:{job.id}:{projection_type}:projection_refreshed",
                        organization_id=job.organization_id,
                        workspace_id=job.workspace_id,
                        event_type="projection_refreshed",
                        payload={"projection_type": projection_type},
                        actor_type="system",
                        actor_id="reentry-worker",
                    )
                )
            for stage_name in job.affected_stages:
                self._governance.append(
                    GovernanceEvent(
                        id=f"gov:{job.id}:{stage_name}:stage_recomputed",
                        organization_id=job.organization_id,
                        workspace_id=job.workspace_id,
                        event_type="stage_recomputed",
                        payload={"stage_name": stage_name},
                        actor_type="system",
                        actor_id="reentry-worker",
                    )
                )
            completed = ReentryJobRecord(
                id=job.id,
                organization_id=job.organization_id,
                workspace_id=job.workspace_id,
                workspace_version_id=job.workspace_version_id,
                status="completed",
                trigger_claim_id=job.trigger_claim_id,
                dependent_projections=job.dependent_projections,
                affected_stages=job.affected_stages,
                stale_outputs=job.stale_outputs,
            )
            self._jobs.upsert(completed)
            self._jobs.release_workspace(job.workspace_id, status="idle")
            return completed
        except Exception:
            failed = ReentryJobRecord(
                id=job.id,
                organization_id=job.organization_id,
                workspace_id=job.workspace_id,
                workspace_version_id=job.workspace_version_id,
                status="failed",
                trigger_claim_id=job.trigger_claim_id,
                dependent_projections=job.dependent_projections,
                affected_stages=job.affected_stages,
                stale_outputs=job.stale_outputs,
            )
            self._jobs.upsert(failed)
            self._jobs.release_workspace(job.workspace_id, status="failed")
            raise


def build_diff_panel(governance: GovernanceEventRepository, workspace_id: str) -> list[dict[str, object]]:
    allowed = {
        "claim_created",
        "claim_updated",
        "claim_promoted",
        "claim_degraded",
        "projection_refreshed",
        "stage_recomputed",
    }
    events = governance.list_for_workspace(workspace_id)
    return [
        {
            "event_type": event.event_type,
            "actor_type": event.actor_type,
            "actor_id": event.actor_id,
            "payload": event.payload,
        }
        for event in events
        if event.event_type in allowed
    ]
