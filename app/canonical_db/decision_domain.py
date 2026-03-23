from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
import sqlite3
from typing import Sequence

from app.canonical_db.domain import (
    Claim,
    DecisionComparison,
    DecisionDraft,
    DecisionEvidenceLink,
    DecisionOption,
    DecisionOutcome,
    DecisionRecord,
    DecisionReview,
    GovernanceEvent,
    ProblemFrame,
)
from app.canonical_db.repositories import ConnectionFactory, GovernanceEventRepository, TransactionManager


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dumps(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _loads_list(payload: str | None) -> list:
    if not payload:
        return []
    return json.loads(payload)


def _loads_dict(payload: str | None) -> dict:
    if not payload:
        return {}
    return json.loads(payload)


def _event_id(prefix: str, key: str) -> str:
    return f"{prefix}:{key}:{abs(hash((prefix, key))) % 1000000}"


class SqliteProblemFrameRepository:
    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def upsert(self, frame: ProblemFrame) -> ProblemFrame:
        with self._connection_factory() as connection:
            connection.execute(
                """
                INSERT INTO problem_frames (
                    id, organization_id, workspace_id, workspace_version_id, root_problem,
                    scope_boundary, success_criteria_json, active_constraints_json,
                    unresolved_unknowns_json, status, invalidation_reason, correlation_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    workspace_version_id = excluded.workspace_version_id,
                    root_problem = excluded.root_problem,
                    scope_boundary = excluded.scope_boundary,
                    success_criteria_json = excluded.success_criteria_json,
                    active_constraints_json = excluded.active_constraints_json,
                    unresolved_unknowns_json = excluded.unresolved_unknowns_json,
                    status = excluded.status,
                    invalidation_reason = excluded.invalidation_reason,
                    correlation_id = excluded.correlation_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    frame.id,
                    frame.organization_id,
                    frame.workspace_id,
                    frame.workspace_version_id,
                    frame.root_problem,
                    frame.scope_boundary,
                    _dumps(frame.success_criteria),
                    _dumps(frame.active_constraints),
                    _dumps(frame.unresolved_unknowns),
                    frame.status,
                    frame.invalidation_reason,
                    frame.correlation_id,
                ),
            )
        return frame

    def get(self, frame_id: str) -> ProblemFrame | None:
        with self._connection_factory() as connection:
            row = connection.execute(
                """
                SELECT id, organization_id, workspace_id, workspace_version_id, root_problem,
                       scope_boundary, success_criteria_json, active_constraints_json,
                       unresolved_unknowns_json, status, invalidation_reason, correlation_id
                FROM problem_frames WHERE id = ?
                """,
                (frame_id,),
            ).fetchone()
        return None if row is None else _row_to_problem_frame(row)

    def list_for_workspace(self, workspace_id: str) -> list[ProblemFrame]:
        with self._connection_factory() as connection:
            rows = connection.execute(
                """
                SELECT id, organization_id, workspace_id, workspace_version_id, root_problem,
                       scope_boundary, success_criteria_json, active_constraints_json,
                       unresolved_unknowns_json, status, invalidation_reason, correlation_id
                FROM problem_frames WHERE workspace_id = ?
                ORDER BY created_at, id
                """,
                (workspace_id,),
            ).fetchall()
        return [_row_to_problem_frame(row) for row in rows]

    def set_status(self, frame_id: str, *, status: str, invalidation_reason: str = "") -> None:
        with self._connection_factory() as connection:
            connection.execute(
                """
                UPDATE problem_frames
                SET status = ?, invalidation_reason = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, invalidation_reason, frame_id),
            )


class SqliteDecisionOptionRepository:
    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def upsert(self, option: DecisionOption) -> DecisionOption:
        with self._connection_factory() as connection:
            connection.execute(
                """
                INSERT INTO decision_options (
                    id, organization_id, workspace_id, workspace_version_id, problem_frame_id,
                    option_key, title, summary_text, status, assumptions_json,
                    confidence_in_assumptions, benefits_json, costs_json, risks_json,
                    prerequisites_json, historical_value_score, reuse_success_score,
                    negative_outcome_count, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    workspace_version_id = excluded.workspace_version_id,
                    title = excluded.title,
                    summary_text = excluded.summary_text,
                    status = excluded.status,
                    assumptions_json = excluded.assumptions_json,
                    confidence_in_assumptions = excluded.confidence_in_assumptions,
                    benefits_json = excluded.benefits_json,
                    costs_json = excluded.costs_json,
                    risks_json = excluded.risks_json,
                    prerequisites_json = excluded.prerequisites_json,
                    historical_value_score = excluded.historical_value_score,
                    reuse_success_score = excluded.reuse_success_score,
                    negative_outcome_count = excluded.negative_outcome_count,
                    metadata_json = excluded.metadata_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    option.id,
                    option.organization_id,
                    option.workspace_id,
                    option.workspace_version_id,
                    option.problem_frame_id,
                    option.option_key,
                    option.title,
                    option.summary_text,
                    option.status,
                    _dumps(option.assumptions),
                    option.confidence_in_assumptions,
                    _dumps(option.benefits),
                    _dumps(option.costs),
                    _dumps(option.risks),
                    _dumps(option.prerequisites),
                    option.historical_value_score,
                    option.reuse_success_score,
                    option.negative_outcome_count,
                    _dumps(option.metadata),
                ),
            )
        return option

    def list_for_frame(self, problem_frame_id: str) -> list[DecisionOption]:
        with self._connection_factory() as connection:
            rows = connection.execute(
                """
                SELECT id, organization_id, workspace_id, workspace_version_id, problem_frame_id,
                       option_key, title, summary_text, status, assumptions_json,
                       confidence_in_assumptions, benefits_json, costs_json, risks_json,
                       prerequisites_json, historical_value_score, reuse_success_score,
                       negative_outcome_count, metadata_json
                FROM decision_options
                WHERE problem_frame_id = ?
                ORDER BY option_key, id
                """,
                (problem_frame_id,),
            ).fetchall()
        return [_row_to_decision_option(row) for row in rows]

    def set_status_for_frame(self, problem_frame_id: str, *, status: str) -> None:
        with self._connection_factory() as connection:
            connection.execute(
                "UPDATE decision_options SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE problem_frame_id = ?",
                (status, problem_frame_id),
            )


class SqliteDecisionComparisonRepository:
    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def upsert(self, comparison: DecisionComparison) -> DecisionComparison:
        with self._connection_factory() as connection:
            connection.execute(
                """
                INSERT INTO decision_comparisons (
                    id, organization_id, workspace_id, workspace_version_id, problem_frame_id,
                    selected_option_id, status, comparison_dimensions_json, option_scores_json,
                    rejected_option_ids_json, tradeoffs_json, blockers_json,
                    rationale_notes_json, correlation_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    selected_option_id = excluded.selected_option_id,
                    status = excluded.status,
                    comparison_dimensions_json = excluded.comparison_dimensions_json,
                    option_scores_json = excluded.option_scores_json,
                    rejected_option_ids_json = excluded.rejected_option_ids_json,
                    tradeoffs_json = excluded.tradeoffs_json,
                    blockers_json = excluded.blockers_json,
                    rationale_notes_json = excluded.rationale_notes_json,
                    correlation_id = excluded.correlation_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    comparison.id,
                    comparison.organization_id,
                    comparison.workspace_id,
                    comparison.workspace_version_id,
                    comparison.problem_frame_id,
                    comparison.selected_option_id,
                    comparison.status,
                    _dumps(comparison.comparison_dimensions),
                    _dumps(comparison.option_scores),
                    _dumps(comparison.rejected_option_ids),
                    _dumps(comparison.tradeoffs),
                    _dumps(comparison.blockers),
                    _dumps(comparison.rationale_notes),
                    comparison.correlation_id,
                ),
            )
        return comparison

    def get(self, comparison_id: str) -> DecisionComparison | None:
        with self._connection_factory() as connection:
            row = connection.execute(
                """
                SELECT id, organization_id, workspace_id, workspace_version_id, problem_frame_id,
                       selected_option_id, status, comparison_dimensions_json, option_scores_json,
                       rejected_option_ids_json, tradeoffs_json, blockers_json,
                       rationale_notes_json, correlation_id
                FROM decision_comparisons WHERE id = ?
                """,
                (comparison_id,),
            ).fetchone()
        return None if row is None else _row_to_decision_comparison(row)

    def list_for_workspace(self, workspace_id: str) -> list[DecisionComparison]:
        with self._connection_factory() as connection:
            rows = connection.execute(
                """
                SELECT id, organization_id, workspace_id, workspace_version_id, problem_frame_id,
                       selected_option_id, status, comparison_dimensions_json, option_scores_json,
                       rejected_option_ids_json, tradeoffs_json, blockers_json,
                       rationale_notes_json, correlation_id
                FROM decision_comparisons WHERE workspace_id = ?
                ORDER BY created_at, id
                """,
                (workspace_id,),
            ).fetchall()
        return [_row_to_decision_comparison(row) for row in rows]

    def set_status_for_frame(self, problem_frame_id: str, *, status: str) -> None:
        with self._connection_factory() as connection:
            connection.execute(
                "UPDATE decision_comparisons SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE problem_frame_id = ?",
                (status, problem_frame_id),
            )


class SqliteDecisionDraftRepository:
    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def upsert(self, draft: DecisionDraft) -> DecisionDraft:
        with self._connection_factory() as connection:
            connection.execute(
                """
                INSERT INTO decision_drafts (
                    id, organization_id, workspace_id, workspace_version_id, problem_frame_id,
                    comparison_id, selected_option_id, status, missing_basis_json,
                    uncertainty_markers_json, rationale_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    selected_option_id = excluded.selected_option_id,
                    status = excluded.status,
                    missing_basis_json = excluded.missing_basis_json,
                    uncertainty_markers_json = excluded.uncertainty_markers_json,
                    rationale_json = excluded.rationale_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    draft.id,
                    draft.organization_id,
                    draft.workspace_id,
                    draft.workspace_version_id,
                    draft.problem_frame_id,
                    draft.comparison_id,
                    draft.selected_option_id,
                    draft.status,
                    _dumps(draft.missing_basis),
                    _dumps(draft.uncertainty_markers),
                    _dumps(draft.rationale),
                ),
            )
        return draft

    def get(self, draft_id: str) -> DecisionDraft | None:
        with self._connection_factory() as connection:
            row = connection.execute(
                """
                SELECT id, organization_id, workspace_id, workspace_version_id, problem_frame_id,
                       comparison_id, selected_option_id, status, missing_basis_json,
                       uncertainty_markers_json, rationale_json
                FROM decision_drafts WHERE id = ?
                """,
                (draft_id,),
            ).fetchone()
        return None if row is None else _row_to_decision_draft(row)

    def set_status_for_frame(self, problem_frame_id: str, *, status: str) -> None:
        with self._connection_factory() as connection:
            connection.execute(
                "UPDATE decision_drafts SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE problem_frame_id = ?",
                (status, problem_frame_id),
            )


class SqliteDecisionRecordRepository:
    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def upsert(self, record: DecisionRecord) -> DecisionRecord:
        with self._connection_factory() as connection:
            connection.execute(
                """
                INSERT INTO decision_records (
                    id, organization_id, workspace_id, workspace_version_id, problem_frame_id,
                    comparison_id, draft_id, selected_option_id, status, decision_basis_json,
                    rejected_option_ids_json, review_due, limitations_json,
                    historical_value_score, last_outcome_status, last_outcome_at,
                    missing_basis_json, uncertainty_markers_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    draft_id = excluded.draft_id,
                    selected_option_id = excluded.selected_option_id,
                    status = excluded.status,
                    decision_basis_json = excluded.decision_basis_json,
                    rejected_option_ids_json = excluded.rejected_option_ids_json,
                    review_due = excluded.review_due,
                    limitations_json = excluded.limitations_json,
                    historical_value_score = excluded.historical_value_score,
                    last_outcome_status = excluded.last_outcome_status,
                    last_outcome_at = excluded.last_outcome_at,
                    missing_basis_json = excluded.missing_basis_json,
                    uncertainty_markers_json = excluded.uncertainty_markers_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    record.id,
                    record.organization_id,
                    record.workspace_id,
                    record.workspace_version_id,
                    record.problem_frame_id,
                    record.comparison_id,
                    record.draft_id,
                    record.selected_option_id,
                    record.status,
                    _dumps(record.decision_basis),
                    _dumps(record.rejected_option_ids),
                    record.review_due,
                    _dumps(record.limitations),
                    record.historical_value_score,
                    record.last_outcome_status,
                    record.last_outcome_at,
                    _dumps(record.missing_basis),
                    _dumps(record.uncertainty_markers),
                ),
            )
        return record

    def get(self, record_id: str) -> DecisionRecord | None:
        with self._connection_factory() as connection:
            row = connection.execute(
                """
                SELECT id, organization_id, workspace_id, workspace_version_id, problem_frame_id,
                       comparison_id, draft_id, selected_option_id, status, decision_basis_json,
                       rejected_option_ids_json, review_due, limitations_json,
                       historical_value_score, last_outcome_status, last_outcome_at,
                       missing_basis_json, uncertainty_markers_json
                FROM decision_records WHERE id = ?
                """,
                (record_id,),
            ).fetchone()
        return None if row is None else _row_to_decision_record(row)

    def list_for_workspace(self, workspace_id: str) -> list[DecisionRecord]:
        with self._connection_factory() as connection:
            rows = connection.execute(
                """
                SELECT id, organization_id, workspace_id, workspace_version_id, problem_frame_id,
                       comparison_id, draft_id, selected_option_id, status, decision_basis_json,
                       rejected_option_ids_json, review_due, limitations_json,
                       historical_value_score, last_outcome_status, last_outcome_at,
                       missing_basis_json, uncertainty_markers_json
                FROM decision_records WHERE workspace_id = ?
                ORDER BY created_at, id
                """,
                (workspace_id,),
            ).fetchall()
        return [_row_to_decision_record(row) for row in rows]

    def set_review_required_for_frame(self, problem_frame_id: str) -> list[DecisionRecord]:
        records = []
        for record in self.list_for_problem_frame(problem_frame_id):
            if record.status == "retired":
                continue
            updated = replace(record, status="review_required")
            self.upsert(updated)
            records.append(updated)
        return records

    def list_for_problem_frame(self, problem_frame_id: str) -> list[DecisionRecord]:
        with self._connection_factory() as connection:
            rows = connection.execute(
                """
                SELECT id, organization_id, workspace_id, workspace_version_id, problem_frame_id,
                       comparison_id, draft_id, selected_option_id, status, decision_basis_json,
                       rejected_option_ids_json, review_due, limitations_json,
                       historical_value_score, last_outcome_status, last_outcome_at,
                       missing_basis_json, uncertainty_markers_json
                FROM decision_records WHERE problem_frame_id = ?
                ORDER BY created_at, id
                """,
                (problem_frame_id,),
            ).fetchall()
        return [_row_to_decision_record(row) for row in rows]


class SqliteDecisionEvidenceLinkRepository:
    def __init__(
        self,
        connection_factory: ConnectionFactory,
        transaction_manager: TransactionManager | None = None,
    ):
        self._connection_factory = connection_factory
        self._transactions = transaction_manager or TransactionManager(connection_factory)

    def replace_for_record(self, record_id: str, links: Sequence[DecisionEvidenceLink]) -> None:
        with self._transactions.transaction() as connection:
            connection.execute("DELETE FROM decision_evidence_links WHERE decision_record_id = ?", (record_id,))
            self._insert_many(connection, links)

    def list_for_record(self, record_id: str) -> list[DecisionEvidenceLink]:
        with self._connection_factory() as connection:
            rows = connection.execute(
                """
                SELECT id, organization_id, workspace_id, workspace_version_id, decision_record_id,
                       decision_option_id, link_type, link_strength, link_direction, source_ref,
                       criticality, claim_id, artifact_id, projection_snapshot_id, metadata_json
                FROM decision_evidence_links WHERE decision_record_id = ?
                ORDER BY created_at, id
                """,
                (record_id,),
            ).fetchall()
        return [_row_to_decision_evidence_link(row) for row in rows]

    def _insert_many(self, connection: sqlite3.Connection, links: Sequence[DecisionEvidenceLink]) -> None:
        connection.executemany(
            """
            INSERT INTO decision_evidence_links (
                id, organization_id, workspace_id, workspace_version_id, decision_record_id,
                decision_option_id, link_type, link_strength, link_direction, source_ref,
                criticality, claim_id, artifact_id, projection_snapshot_id, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    link.id,
                    link.organization_id,
                    link.workspace_id,
                    link.workspace_version_id,
                    link.decision_record_id,
                    link.decision_option_id,
                    link.link_type,
                    link.link_strength,
                    link.link_direction,
                    link.source_ref,
                    link.criticality,
                    link.claim_id,
                    link.artifact_id,
                    link.projection_snapshot_id,
                    _dumps(link.metadata),
                )
                for link in links
            ],
        )


class SqliteDecisionReviewRepository:
    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def upsert(self, review: DecisionReview) -> DecisionReview:
        with self._connection_factory() as connection:
            connection.execute(
                """
                INSERT INTO decision_reviews (
                    id, organization_id, workspace_id, workspace_version_id, decision_record_id,
                    status, opened_by, closed_by, close_reason, notes_json, correlation_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    closed_by = excluded.closed_by,
                    close_reason = excluded.close_reason,
                    notes_json = excluded.notes_json,
                    correlation_id = excluded.correlation_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    review.id,
                    review.organization_id,
                    review.workspace_id,
                    review.workspace_version_id,
                    review.decision_record_id,
                    review.status,
                    review.opened_by,
                    review.closed_by,
                    review.close_reason,
                    _dumps(review.notes),
                    review.correlation_id,
                ),
            )
        return review

    def list_for_record(self, record_id: str) -> list[DecisionReview]:
        with self._connection_factory() as connection:
            rows = connection.execute(
                """
                SELECT id, organization_id, workspace_id, workspace_version_id, decision_record_id,
                       status, opened_by, closed_by, close_reason, notes_json, correlation_id
                FROM decision_reviews WHERE decision_record_id = ?
                ORDER BY created_at, id
                """,
                (record_id,),
            ).fetchall()
        return [_row_to_decision_review(row) for row in rows]

    def get_open_for_record(self, record_id: str) -> DecisionReview | None:
        with self._connection_factory() as connection:
            row = connection.execute(
                """
                SELECT id, organization_id, workspace_id, workspace_version_id, decision_record_id,
                       status, opened_by, closed_by, close_reason, notes_json, correlation_id
                FROM decision_reviews
                WHERE decision_record_id = ? AND status = 'open'
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (record_id,),
            ).fetchone()
        return None if row is None else _row_to_decision_review(row)


class SqliteDecisionOutcomeRepository:
    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def append(self, outcome: DecisionOutcome) -> DecisionOutcome:
        with self._connection_factory() as connection:
            connection.execute(
                """
                INSERT INTO decision_outcomes (
                    id, organization_id, workspace_id, workspace_version_id, decision_record_id,
                    outcome_type, outcome_score, source, evidence_json, recorded_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    outcome_type = excluded.outcome_type,
                    outcome_score = excluded.outcome_score,
                    source = excluded.source,
                    evidence_json = excluded.evidence_json,
                    recorded_at = excluded.recorded_at
                """,
                (
                    outcome.id,
                    outcome.organization_id,
                    outcome.workspace_id,
                    outcome.workspace_version_id,
                    outcome.decision_record_id,
                    outcome.outcome_type,
                    outcome.outcome_score,
                    outcome.source,
                    _dumps(outcome.evidence),
                    outcome.recorded_at,
                ),
            )
        return outcome

    def list_for_record(self, record_id: str) -> list[DecisionOutcome]:
        with self._connection_factory() as connection:
            rows = connection.execute(
                """
                SELECT id, organization_id, workspace_id, workspace_version_id, decision_record_id,
                       outcome_type, outcome_score, source, evidence_json, recorded_at
                FROM decision_outcomes WHERE decision_record_id = ?
                ORDER BY recorded_at, id
                """,
                (record_id,),
            ).fetchall()
        return [_row_to_decision_outcome(row) for row in rows]


class ProblemFrameBuilder:
    def __init__(
        self,
        frames: SqliteProblemFrameRepository,
        options: SqliteDecisionOptionRepository,
        comparisons: SqliteDecisionComparisonRepository,
        drafts: SqliteDecisionDraftRepository,
        records: SqliteDecisionRecordRepository,
        reviews: SqliteDecisionReviewRepository,
        governance: GovernanceEventRepository,
    ):
        self._frames = frames
        self._options = options
        self._comparisons = comparisons
        self._drafts = drafts
        self._records = records
        self._reviews = reviews
        self._governance = governance

    def build(
        self,
        *,
        organization_id: str,
        workspace_id: str,
        workspace_version_id: str,
        root_problem: str,
        supporting_claims: Sequence[Claim],
        unresolved_unknowns: Sequence[str],
        active_constraints: Sequence[str],
        success_criteria: Sequence[str],
        scope_boundary: str,
        correlation_id: str = "",
    ) -> ProblemFrame:
        frame = ProblemFrame(
            id=f"pf:{workspace_id}:{workspace_version_id}:{abs(hash((root_problem, scope_boundary))) % 100000}",
            organization_id=organization_id,
            workspace_id=workspace_id,
            workspace_version_id=workspace_version_id,
            root_problem=root_problem,
            scope_boundary=scope_boundary,
            success_criteria=list(success_criteria),
            active_constraints=list(active_constraints),
            unresolved_unknowns=list(unresolved_unknowns),
            status="active",
            invalidation_reason="",
            correlation_id=correlation_id,
        )
        self._frames.upsert(frame)
        self._governance.append(
            GovernanceEvent(
                id=_event_id("governance", frame.id + ":built"),
                organization_id=organization_id,
                workspace_id=workspace_id,
                event_type="problem_frame_built",
                payload={
                    "problem_frame_id": frame.id,
                    "supporting_claim_ids": [claim.id for claim in supporting_claims],
                    "correlation_id": correlation_id,
                },
                actor_type="system",
                actor_id="problem_frame_builder",
            )
        )
        return frame

    def invalidate(
        self,
        *,
        problem_frame_id: str,
        reason: str,
        actor_id: str = "system",
        correlation_id: str = "",
    ) -> ProblemFrame:
        frame = self._frames.get(problem_frame_id)
        if frame is None:
            raise KeyError(problem_frame_id)
        invalidated = replace(frame, status="invalidated", invalidation_reason=reason)
        self._frames.upsert(invalidated)
        self._options.set_status_for_frame(problem_frame_id, status="stale")
        self._comparisons.set_status_for_frame(problem_frame_id, status="stale")
        self._drafts.set_status_for_frame(problem_frame_id, status="stale")
        affected_records = self._records.set_review_required_for_frame(problem_frame_id)
        for record in affected_records:
            if self._reviews.get_open_for_record(record.id) is None:
                self._reviews.upsert(
                    DecisionReview(
                        id=f"drv:{record.id}:open",
                        organization_id=record.organization_id,
                        workspace_id=record.workspace_id,
                        workspace_version_id=record.workspace_version_id,
                        decision_record_id=record.id,
                        status="open",
                        opened_by=actor_id,
                        notes=[reason],
                        correlation_id=correlation_id,
                    )
                )
            self._governance.append(
                GovernanceEvent(
                    id=_event_id("governance", record.id + ":review_due"),
                    organization_id=record.organization_id,
                    workspace_id=record.workspace_id,
                    event_type="decision_review_due",
                    payload={
                        "decision_record_id": record.id,
                        "problem_frame_id": problem_frame_id,
                        "reason": reason,
                        "correlation_id": correlation_id,
                    },
                    actor_type="system",
                    actor_id=actor_id,
                )
            )
        self._governance.append(
            GovernanceEvent(
                id=_event_id("governance", problem_frame_id + ":invalidated"),
                organization_id=frame.organization_id,
                workspace_id=frame.workspace_id,
                event_type="problem_frame_invalidated",
                payload={
                    "problem_frame_id": problem_frame_id,
                    "reason": reason,
                    "correlation_id": correlation_id,
                },
                actor_type="system",
                actor_id=actor_id,
            )
        )
        return invalidated


class DecisionOptionEngine:
    def __init__(self, options: SqliteDecisionOptionRepository, governance: GovernanceEventRepository):
        self._options = options
        self._governance = governance

    def materialize(
        self,
        *,
        organization_id: str,
        workspace_id: str,
        workspace_version_id: str,
        problem_frame_id: str,
        option_key: str,
        title: str,
        summary_text: str,
        assumptions: Sequence[str],
        confidence_in_assumptions: float,
        benefits: Sequence[str],
        costs: Sequence[str],
        risks: Sequence[str],
        prerequisites: Sequence[str],
        correlation_id: str = "",
    ) -> DecisionOption:
        option = DecisionOption(
            id=f"do:{workspace_id}:{problem_frame_id}:{option_key}",
            organization_id=organization_id,
            workspace_id=workspace_id,
            workspace_version_id=workspace_version_id,
            problem_frame_id=problem_frame_id,
            option_key=option_key,
            title=title,
            summary_text=summary_text,
            status="candidate",
            assumptions=list(assumptions),
            confidence_in_assumptions=confidence_in_assumptions,
            benefits=list(benefits),
            costs=list(costs),
            risks=list(risks),
            prerequisites=list(prerequisites),
        )
        self._options.upsert(option)
        self._governance.append(
            GovernanceEvent(
                id=_event_id("governance", option.id + ":created"),
                organization_id=organization_id,
                workspace_id=workspace_id,
                event_type="decision_option_created",
                payload={
                    "decision_option_id": option.id,
                    "problem_frame_id": problem_frame_id,
                    "option_key": option_key,
                    "correlation_id": correlation_id,
                },
                actor_type="system",
                actor_id="decision_option_engine",
            )
        )
        return option


class DecisionComparisonService:
    BASE_DIMENSIONS = ("feasibility", "cost", "risk", "reversibility", "strategic_fit", "operational_load")

    def __init__(self, comparisons: SqliteDecisionComparisonRepository, governance: GovernanceEventRepository):
        self._comparisons = comparisons
        self._governance = governance

    def compare(
        self,
        *,
        organization_id: str,
        workspace_id: str,
        workspace_version_id: str,
        problem_frame_id: str,
        options: Sequence[DecisionOption],
        domain_dimensions: Sequence[str] = (),
        selected_option_id: str | None = None,
        tradeoffs: Sequence[str] = (),
        blockers: Sequence[str] = (),
        rationale_notes: Sequence[str] = (),
        correlation_id: str = "",
    ) -> DecisionComparison:
        dimensions = list(self.BASE_DIMENSIONS) + [item for item in domain_dimensions if item not in self.BASE_DIMENSIONS]
        option_scores: dict[str, dict[str, float]] = {}
        for option in options:
            risk_penalty = min(0.4, len(option.risks) * 0.05)
            option_scores[option.id] = {
                "feasibility": max(0.1, min(1.0, 0.5 + option.confidence_in_assumptions * 0.4)),
                "cost": max(0.1, 1.0 - min(0.8, len(option.costs) * 0.1)),
                "risk": max(0.1, 1.0 - risk_penalty),
                "reversibility": 0.8 if "rollback" in option.summary_text.lower() else 0.6,
                "strategic_fit": 0.7,
                "operational_load": max(0.1, 1.0 - min(0.7, len(option.prerequisites) * 0.08)),
            }
            for dimension in domain_dimensions:
                option_scores[option.id][dimension] = 0.6
        rejected_option_ids = [option.id for option in options if selected_option_id and option.id != selected_option_id]
        comparison = DecisionComparison(
            id=f"cmp:{workspace_id}:{problem_frame_id}:{len(options)}",
            organization_id=organization_id,
            workspace_id=workspace_id,
            workspace_version_id=workspace_version_id,
            problem_frame_id=problem_frame_id,
            selected_option_id=selected_option_id,
            status="completed" if selected_option_id else "draft",
            comparison_dimensions=dimensions,
            option_scores=option_scores,
            rejected_option_ids=rejected_option_ids,
            tradeoffs=list(tradeoffs),
            blockers=list(blockers),
            rationale_notes=list(rationale_notes),
            correlation_id=correlation_id,
        )
        self._comparisons.upsert(comparison)
        self._governance.append(
            GovernanceEvent(
                id=_event_id("governance", comparison.id + ":compared"),
                organization_id=organization_id,
                workspace_id=workspace_id,
                event_type="decision_compared",
                payload={
                    "decision_comparison_id": comparison.id,
                    "selected_option_id": selected_option_id,
                    "rejected_option_ids": rejected_option_ids,
                    "correlation_id": correlation_id,
                },
                actor_type="system",
                actor_id="decision_comparison_service",
            )
        )
        for option_id in rejected_option_ids:
            self._governance.append(
                GovernanceEvent(
                    id=_event_id("governance", option_id + ":rejected"),
                    organization_id=organization_id,
                    workspace_id=workspace_id,
                    event_type="decision_rejected",
                    payload={
                        "decision_comparison_id": comparison.id,
                        "decision_option_id": option_id,
                        "correlation_id": correlation_id,
                    },
                    actor_type="system",
                    actor_id="decision_comparison_service",
                )
            )
        return comparison


class DecisionReviewService:
    def __init__(self, reviews: SqliteDecisionReviewRepository, records: SqliteDecisionRecordRepository):
        self._reviews = reviews
        self._records = records

    def open_review(self, *, record: DecisionRecord, opened_by: str, reason: str, correlation_id: str = "") -> DecisionReview:
        existing = self._reviews.get_open_for_record(record.id)
        if existing is not None:
            return existing
        review = DecisionReview(
            id=f"drv:{record.id}:{abs(hash((opened_by, reason))) % 100000}",
            organization_id=record.organization_id,
            workspace_id=record.workspace_id,
            workspace_version_id=record.workspace_version_id,
            decision_record_id=record.id,
            status="open",
            opened_by=opened_by,
            notes=[reason],
            correlation_id=correlation_id,
        )
        self._reviews.upsert(review)
        return review

    def close_review(self, review: DecisionReview, *, closed_by: str, close_reason: str, next_record_status: str = "closed") -> DecisionReview:
        updated_review = replace(review, status="closed", closed_by=closed_by, close_reason=close_reason)
        self._reviews.upsert(updated_review)
        record = self._records.get(review.decision_record_id)
        if record is None:
            raise KeyError(review.decision_record_id)
        self._records.upsert(replace(record, status=next_record_status))
        return updated_review


class DecisionContractService:
    def __init__(
        self,
        drafts: SqliteDecisionDraftRepository,
        records: SqliteDecisionRecordRepository,
        evidence_links: SqliteDecisionEvidenceLinkRepository,
        outcomes: SqliteDecisionOutcomeRepository,
        reviews: DecisionReviewService,
        governance: GovernanceEventRepository,
    ):
        self._drafts = drafts
        self._records = records
        self._evidence_links = evidence_links
        self._outcomes = outcomes
        self._reviews = reviews
        self._governance = governance

    def create_draft(
        self,
        *,
        organization_id: str,
        workspace_id: str,
        workspace_version_id: str,
        frame: ProblemFrame,
        comparison: DecisionComparison,
        evidence_links: Sequence[DecisionEvidenceLink],
        rationale: Sequence[str],
    ) -> DecisionDraft:
        missing_basis: list[str] = []
        uncertainty_markers: list[str] = []
        status = "ready"
        if comparison.selected_option_id is None:
            status = "block"
            missing_basis.append("selected_option")
        if not evidence_links:
            if status == "block":
                uncertainty_markers.append("no_supporting_evidence")
            else:
                status = "degrade"
                missing_basis.append("supporting_evidence")
                uncertainty_markers.append("partial_decision_basis")
        draft = DecisionDraft(
            id=f"dd:{workspace_id}:{comparison.id}",
            organization_id=organization_id,
            workspace_id=workspace_id,
            workspace_version_id=workspace_version_id,
            problem_frame_id=frame.id,
            comparison_id=comparison.id,
            selected_option_id=comparison.selected_option_id,
            status=status,
            missing_basis=missing_basis,
            uncertainty_markers=uncertainty_markers,
            rationale=list(rationale),
        )
        self._drafts.upsert(draft)
        return draft

    def promote(
        self,
        *,
        draft: DecisionDraft,
        comparison: DecisionComparison,
        evidence_links: Sequence[DecisionEvidenceLink],
        decision_basis: Sequence[str],
        limitations: Sequence[str],
        review_due: str | None,
        actor_id: str,
        correlation_id: str = "",
    ) -> DecisionRecord:
        if draft.status not in {"ready", "degrade"}:
            raise ValueError("Draft is not promotable")
        if draft.selected_option_id is None:
            raise ValueError("Draft has no selected option")
        record = DecisionRecord(
            id=f"dr:{draft.workspace_id}:{draft.comparison_id}",
            organization_id=draft.organization_id,
            workspace_id=draft.workspace_id,
            workspace_version_id=draft.workspace_version_id,
            problem_frame_id=draft.problem_frame_id,
            comparison_id=draft.comparison_id,
            draft_id=draft.id,
            selected_option_id=draft.selected_option_id,
            status="selected" if draft.status == "ready" else "degrade",
            decision_basis=list(decision_basis),
            rejected_option_ids=list(comparison.rejected_option_ids),
            review_due=review_due,
            limitations=list(limitations),
            historical_value_score=0.0,
            last_outcome_status="",
            last_outcome_at=None,
            missing_basis=list(draft.missing_basis),
            uncertainty_markers=list(draft.uncertainty_markers),
        )
        self._records.upsert(record)
        if evidence_links:
            normalized_links = [
                replace(link, decision_record_id=record.id, workspace_version_id=record.workspace_version_id)
                for link in evidence_links
            ]
            self._evidence_links.replace_for_record(record.id, normalized_links)
        self._governance.append(
            GovernanceEvent(
                id=_event_id("governance", record.id + ":selected"),
                organization_id=record.organization_id,
                workspace_id=record.workspace_id,
                event_type="decision_selected",
                payload={
                    "decision_record_id": record.id,
                    "selected_option_id": record.selected_option_id,
                    "decision_comparison_id": comparison.id,
                    "correlation_id": correlation_id,
                },
                actor_type="system",
                actor_id=actor_id,
            )
        )
        return record

    def mark_review_required(self, *, record_id: str, reason: str, actor_id: str = "system", correlation_id: str = "") -> DecisionRecord:
        record = self._records.get(record_id)
        if record is None:
            raise KeyError(record_id)
        updated = replace(record, status="review_required")
        self._records.upsert(updated)
        self._reviews.open_review(record=updated, opened_by=actor_id, reason=reason, correlation_id=correlation_id)
        self._governance.append(
            GovernanceEvent(
                id=_event_id("governance", record_id + ":review"),
                organization_id=record.organization_id,
                workspace_id=record.workspace_id,
                event_type="decision_review_due",
                payload={
                    "decision_record_id": record_id,
                    "reason": reason,
                    "correlation_id": correlation_id,
                },
                actor_type="system",
                actor_id=actor_id,
            )
        )
        return updated

    def record_outcome(
        self,
        *,
        record_id: str,
        outcome_type: str,
        outcome_score: float,
        source: str,
        evidence: dict,
        correlation_id: str = "",
    ) -> DecisionOutcome:
        record = self._records.get(record_id)
        if record is None:
            raise KeyError(record_id)
        outcome = DecisionOutcome(
            id=f"out:{record_id}:{abs(hash((outcome_type, source, outcome_score))) % 100000}",
            organization_id=record.organization_id,
            workspace_id=record.workspace_id,
            workspace_version_id=record.workspace_version_id,
            decision_record_id=record.id,
            outcome_type=outcome_type,
            outcome_score=outcome_score,
            source=source,
            evidence=evidence,
            recorded_at=_utc_now(),
        )
        self._outcomes.append(outcome)
        all_outcomes = self._outcomes.list_for_record(record_id)
        historical_value_score = sum(item.outcome_score for item in all_outcomes) / len(all_outcomes)
        updated_record = replace(
            record,
            historical_value_score=historical_value_score,
            last_outcome_status=outcome.outcome_type,
            last_outcome_at=outcome.recorded_at,
        )
        self._records.upsert(updated_record)
        self._governance.append(
            GovernanceEvent(
                id=_event_id("governance", outcome.id + ":outcome"),
                organization_id=record.organization_id,
                workspace_id=record.workspace_id,
                event_type="decision_outcome_recorded",
                payload={
                    "decision_record_id": record.id,
                    "outcome_type": outcome_type,
                    "outcome_score": outcome_score,
                    "source": source,
                    "correlation_id": correlation_id,
                },
                actor_type="system",
                actor_id="decision_outcome_resolver",
            )
        )
        return outcome


def _row_to_problem_frame(row: sqlite3.Row) -> ProblemFrame:
    return ProblemFrame(
        id=row["id"],
        organization_id=row["organization_id"],
        workspace_id=row["workspace_id"],
        workspace_version_id=row["workspace_version_id"],
        root_problem=row["root_problem"],
        scope_boundary=row["scope_boundary"],
        success_criteria=_loads_list(row["success_criteria_json"]),
        active_constraints=_loads_list(row["active_constraints_json"]),
        unresolved_unknowns=_loads_list(row["unresolved_unknowns_json"]),
        status=row["status"],
        invalidation_reason=row["invalidation_reason"],
        correlation_id=row["correlation_id"],
    )


def _row_to_decision_option(row: sqlite3.Row) -> DecisionOption:
    return DecisionOption(
        id=row["id"],
        organization_id=row["organization_id"],
        workspace_id=row["workspace_id"],
        workspace_version_id=row["workspace_version_id"],
        problem_frame_id=row["problem_frame_id"],
        option_key=row["option_key"],
        title=row["title"],
        summary_text=row["summary_text"],
        status=row["status"],
        assumptions=_loads_list(row["assumptions_json"]),
        confidence_in_assumptions=row["confidence_in_assumptions"],
        benefits=_loads_list(row["benefits_json"]),
        costs=_loads_list(row["costs_json"]),
        risks=_loads_list(row["risks_json"]),
        prerequisites=_loads_list(row["prerequisites_json"]),
        historical_value_score=row["historical_value_score"],
        reuse_success_score=row["reuse_success_score"],
        negative_outcome_count=row["negative_outcome_count"],
        metadata=_loads_dict(row["metadata_json"]),
    )


def _row_to_decision_comparison(row: sqlite3.Row) -> DecisionComparison:
    return DecisionComparison(
        id=row["id"],
        organization_id=row["organization_id"],
        workspace_id=row["workspace_id"],
        workspace_version_id=row["workspace_version_id"],
        problem_frame_id=row["problem_frame_id"],
        selected_option_id=row["selected_option_id"],
        status=row["status"],
        comparison_dimensions=_loads_list(row["comparison_dimensions_json"]),
        option_scores=_loads_dict(row["option_scores_json"]),
        rejected_option_ids=_loads_list(row["rejected_option_ids_json"]),
        tradeoffs=_loads_list(row["tradeoffs_json"]),
        blockers=_loads_list(row["blockers_json"]),
        rationale_notes=_loads_list(row["rationale_notes_json"]),
        correlation_id=row["correlation_id"],
    )


def _row_to_decision_draft(row: sqlite3.Row) -> DecisionDraft:
    return DecisionDraft(
        id=row["id"],
        organization_id=row["organization_id"],
        workspace_id=row["workspace_id"],
        workspace_version_id=row["workspace_version_id"],
        problem_frame_id=row["problem_frame_id"],
        comparison_id=row["comparison_id"],
        selected_option_id=row["selected_option_id"],
        status=row["status"],
        missing_basis=_loads_list(row["missing_basis_json"]),
        uncertainty_markers=_loads_list(row["uncertainty_markers_json"]),
        rationale=_loads_list(row["rationale_json"]),
    )


def _row_to_decision_record(row: sqlite3.Row) -> DecisionRecord:
    return DecisionRecord(
        id=row["id"],
        organization_id=row["organization_id"],
        workspace_id=row["workspace_id"],
        workspace_version_id=row["workspace_version_id"],
        problem_frame_id=row["problem_frame_id"],
        comparison_id=row["comparison_id"],
        draft_id=row["draft_id"],
        selected_option_id=row["selected_option_id"],
        status=row["status"],
        decision_basis=_loads_list(row["decision_basis_json"]),
        rejected_option_ids=_loads_list(row["rejected_option_ids_json"]),
        review_due=row["review_due"],
        limitations=_loads_list(row["limitations_json"]),
        historical_value_score=row["historical_value_score"],
        last_outcome_status=row["last_outcome_status"],
        last_outcome_at=row["last_outcome_at"],
        missing_basis=_loads_list(row["missing_basis_json"]),
        uncertainty_markers=_loads_list(row["uncertainty_markers_json"]),
    )


def _row_to_decision_evidence_link(row: sqlite3.Row) -> DecisionEvidenceLink:
    return DecisionEvidenceLink(
        id=row["id"],
        organization_id=row["organization_id"],
        workspace_id=row["workspace_id"],
        workspace_version_id=row["workspace_version_id"],
        decision_record_id=row["decision_record_id"],
        decision_option_id=row["decision_option_id"],
        link_type=row["link_type"],
        link_strength=row["link_strength"],
        link_direction=row["link_direction"],
        source_ref=row["source_ref"],
        criticality=row["criticality"],
        claim_id=row["claim_id"],
        artifact_id=row["artifact_id"],
        projection_snapshot_id=row["projection_snapshot_id"],
        metadata=_loads_dict(row["metadata_json"]),
    )


def _row_to_decision_review(row: sqlite3.Row) -> DecisionReview:
    return DecisionReview(
        id=row["id"],
        organization_id=row["organization_id"],
        workspace_id=row["workspace_id"],
        workspace_version_id=row["workspace_version_id"],
        decision_record_id=row["decision_record_id"],
        status=row["status"],
        opened_by=row["opened_by"],
        closed_by=row["closed_by"],
        close_reason=row["close_reason"],
        notes=_loads_list(row["notes_json"]),
        correlation_id=row["correlation_id"],
    )


def _row_to_decision_outcome(row: sqlite3.Row) -> DecisionOutcome:
    return DecisionOutcome(
        id=row["id"],
        organization_id=row["organization_id"],
        workspace_id=row["workspace_id"],
        workspace_version_id=row["workspace_version_id"],
        decision_record_id=row["decision_record_id"],
        outcome_type=row["outcome_type"],
        outcome_score=row["outcome_score"],
        source=row["source"],
        evidence=_loads_dict(row["evidence_json"]),
        recorded_at=row["recorded_at"],
    )
