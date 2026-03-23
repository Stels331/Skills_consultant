from __future__ import annotations

from dataclasses import dataclass
import json
import sqlite3
from typing import Sequence

from app.canonical_db.decision_assurance import SqliteDecisionAssuranceSnapshotRepository, assurance_payload
from app.canonical_db.decision_domain import (
    SqliteDecisionComparisonRepository,
    SqliteDecisionOutcomeRepository,
    SqliteDecisionRecordRepository,
    SqliteDecisionReviewRepository,
)
from app.canonical_db.dialogue_backend import _tokenize
from app.canonical_db.domain import DecisionReview, GovernanceEvent, Workspace
from app.canonical_db.repositories import ConnectionFactory, GovernanceEventRepository


MODE_RANK = {
    "suggestion-only": 0,
    "comparison-hint": 1,
    "prefilled-option": 2,
}


@dataclass(frozen=True)
class RetrievedDecisionPattern:
    decision_record_id: str
    source_workspace_id: str
    source_workspace_version_id: str
    selected_option_id: str
    problem_frame_id: str
    reuse_mode: str
    reuse_eligibility: str
    similarity_score: float
    assurance_score: float
    historical_value_score: float
    final_score: float
    similarity_rationale: dict[str, float | str]
    historical_outcome_summary: dict[str, object]
    provenance: dict[str, str]
    conflict: bool
    penalty_marker: str | None


class DecisionPatternRetrievalService:
    def __init__(
        self,
        connection_factory: ConnectionFactory,
        records: SqliteDecisionRecordRepository,
        comparisons: SqliteDecisionComparisonRepository,
        snapshots: SqliteDecisionAssuranceSnapshotRepository,
        outcomes: SqliteDecisionOutcomeRepository,
        governance: GovernanceEventRepository,
    ):
        self._connection_factory = connection_factory
        self._records = records
        self._comparisons = comparisons
        self._snapshots = snapshots
        self._outcomes = outcomes
        self._governance = governance

    def retrieve(
        self,
        *,
        organization_id: str,
        workspace: Workspace,
        question: str,
        reuse_mode: str,
        limit: int = 5,
    ) -> list[RetrievedDecisionPattern]:
        query_tokens = set(_tokenize(question))
        candidates = self._list_org_records(organization_id)
        results: list[RetrievedDecisionPattern] = []
        for row in candidates:
            if row["workspace_id"] == workspace.id:
                source_scope = "workspace"
            else:
                source_scope = "organization"
            if row["organization_id"] != organization_id:
                self._governance.append(
                    GovernanceEvent(
                        id=f"decision_retrieval_blocked:{workspace.id}:{row['id']}",
                        organization_id=organization_id,
                        workspace_id=workspace.id,
                        event_type="decision_retrieval_blocked",
                        payload={"decision_record_id": row["id"], "reason": "cross_tenant"},
                        actor_type="system",
                        actor_id="decision_pattern_retrieval",
                    )
                )
                continue
            source_text = " ".join(
                [
                    row["root_problem"] or "",
                    row["decision_basis_text"] or "",
                    row["selected_option_title"] or "",
                    row["selected_option_summary"] or "",
                ]
            )
            source_tokens = set(_tokenize(source_text))
            if not source_tokens:
                continue
            overlap = len(query_tokens & source_tokens)
            structural_overlap = overlap / max(1, len(query_tokens))
            domain_tag_bonus = 0.15 if workspace.case_type == row["case_type"] else 0.0
            vector_component = 0.0
            similarity_score = round(min(1.0, structural_overlap * 0.75 + domain_tag_bonus + vector_component), 4)
            if similarity_score <= 0.0:
                continue
            snapshot = self._snapshots.get(row["id"])
            assurance_score = snapshot.assurance_score if snapshot else 0.0
            historical_value_score = float(row["historical_value_score"] or 0.0)
            penalty_marker = None
            reuse_eligibility = "active"
            if row["record_status"] in {"retired", "review_required"}:
                reuse_eligibility = "downgraded"
                penalty_marker = row["record_status"]
            elif snapshot and snapshot.assurance_status != "pass":
                reuse_eligibility = "downgraded"
                penalty_marker = snapshot.assurance_status
            conflict = bool(row["has_conflict"])
            if conflict:
                reuse_eligibility = "blocked"
                penalty_marker = "conflict"
            final_score = similarity_score * 0.55 + assurance_score * 0.25 + max(0.0, historical_value_score) * 0.2
            if reuse_eligibility == "downgraded":
                final_score *= 0.6
            if conflict:
                final_score *= 0.2
            results.append(
                RetrievedDecisionPattern(
                    decision_record_id=row["id"],
                    source_workspace_id=row["workspace_id"],
                    source_workspace_version_id=row["workspace_version_id"],
                    selected_option_id=row["selected_option_id"],
                    problem_frame_id=row["problem_frame_id"],
                    reuse_mode=reuse_mode,
                    reuse_eligibility=reuse_eligibility,
                    similarity_score=similarity_score,
                    assurance_score=assurance_score,
                    historical_value_score=historical_value_score,
                    final_score=round(final_score, 4),
                    similarity_rationale={
                        "structural_overlap": round(structural_overlap, 4),
                        "domain_tags": round(domain_tag_bonus, 4),
                        "vector_similarity": vector_component,
                        "fallback_mode": "text_only",
                        "source_scope": source_scope,
                    },
                    historical_outcome_summary={
                        "count": int(row["outcome_count"] or 0),
                        "average_score": historical_value_score,
                        "last_outcome_status": row["last_outcome_status"] or "",
                    },
                    provenance={
                        "source_workspace_id": row["workspace_id"],
                        "source_decision_id": row["id"],
                    },
                    conflict=conflict,
                    penalty_marker=penalty_marker,
                )
            )
        results.sort(key=lambda item: (-item.final_score, item.decision_record_id))
        return results[:limit]

    def _list_org_records(self, organization_id: str) -> list[sqlite3.Row]:
        with self._connection_factory() as connection:
            return connection.execute(
                """
                SELECT
                    dr.id,
                    dr.organization_id,
                    dr.workspace_id,
                    dr.workspace_version_id,
                    dr.problem_frame_id,
                    dr.selected_option_id,
                    dr.status AS record_status,
                    dr.historical_value_score,
                    dr.last_outcome_status,
                    w.case_type,
                    pf.root_problem,
                    do.title AS selected_option_title,
                    do.summary_text AS selected_option_summary,
                    (SELECT GROUP_CONCAT(value, ' ')
                       FROM json_each(dr.decision_basis_json)
                    ) AS decision_basis_text,
                    (SELECT COUNT(*) FROM decision_outcomes dout WHERE dout.decision_record_id = dr.id) AS outcome_count,
                    EXISTS(
                        SELECT 1
                        FROM decision_evidence_links del
                        WHERE del.decision_record_id = dr.id
                          AND del.link_direction = 'contradicts'
                    ) AS has_conflict
                FROM decision_records dr
                JOIN workspaces w ON w.id = dr.workspace_id
                JOIN problem_frames pf ON pf.id = dr.problem_frame_id
                JOIN decision_options do ON do.id = dr.selected_option_id
                WHERE dr.organization_id = ?
                ORDER BY dr.updated_at DESC, dr.id DESC
                """,
                (organization_id,),
            ).fetchall()


class DecisionReusePolicy:
    def resolve_mode(self, *, organization_metadata: dict, workspace_metadata: dict, requested_mode: str | None = None) -> str:
        org_mode = str(organization_metadata.get("decision_reuse_mode") or "comparison-hint")
        workspace_mode = str(workspace_metadata.get("decision_reuse_mode") or org_mode)
        effective_rank = min(MODE_RANK.get(org_mode, 1), MODE_RANK.get(workspace_mode, 1))
        if requested_mode:
            effective_rank = min(effective_rank, MODE_RANK.get(requested_mode, effective_rank))
        for mode, rank in MODE_RANK.items():
            if rank == effective_rank:
                return mode
        return "comparison-hint"


class DecisionAnswerComposer:
    def __init__(
        self,
        records: SqliteDecisionRecordRepository,
        comparisons: SqliteDecisionComparisonRepository,
        snapshots: SqliteDecisionAssuranceSnapshotRepository,
    ):
        self._records = records
        self._comparisons = comparisons
        self._snapshots = snapshots

    def compose(self, *, workspace_id: str, patterns: Sequence[RetrievedDecisionPattern]) -> dict:
        records = self._records.list_for_workspace(workspace_id)
        if not records:
            return {}
        record = records[-1]
        comparison = self._comparisons.get(record.comparison_id)
        snapshot = self._snapshots.get(record.id)
        return {
            "problem_frame_id": record.problem_frame_id,
            "selected_decision_id": record.id,
            "selected_option_id": record.selected_option_id,
            "rejected_option_ids": list(record.rejected_option_ids),
            "decision_basis": list(record.decision_basis),
            "review_conditions": {
                "review_due": record.review_due,
                "status": record.status,
            },
            "assurance": assurance_payload(snapshot),
            "historical_patterns": [self._pattern_payload(item) for item in patterns],
            "comparison": None
            if comparison is None
            else {
                "comparison_id": comparison.id,
                "dimensions": comparison.comparison_dimensions,
                "tradeoffs": comparison.tradeoffs,
                "blockers": comparison.blockers,
            },
        }

    @staticmethod
    def _pattern_payload(pattern: RetrievedDecisionPattern) -> dict:
        return {
            "decision_record_id": pattern.decision_record_id,
            "source_workspace_id": pattern.source_workspace_id,
            "source_workspace_version_id": pattern.source_workspace_version_id,
            "selected_option_id": pattern.selected_option_id,
            "reuse_mode": pattern.reuse_mode,
            "reuse_eligibility": pattern.reuse_eligibility,
            "similarity_score": pattern.similarity_score,
            "similarity_rationale": pattern.similarity_rationale,
            "historical_value_score": pattern.historical_value_score,
            "historical_outcome_summary": pattern.historical_outcome_summary,
            "provenance": pattern.provenance,
            "conflict": pattern.conflict,
            "penalty_marker": pattern.penalty_marker,
        }


class DecisionReviewWorkflow:
    def __init__(
        self,
        records: SqliteDecisionRecordRepository,
        reviews: SqliteDecisionReviewRepository,
        governance: GovernanceEventRepository,
    ):
        self._records = records
        self._reviews = reviews
        self._governance = governance

    def apply_action(
        self,
        *,
        decision_record_id: str,
        action: str,
        actor_id: str,
        expected_status: str | None = None,
        notes: Sequence[str] = (),
    ) -> DecisionReview:
        record = self._records.get(decision_record_id)
        if record is None:
            raise KeyError(decision_record_id)
        if expected_status and record.status != expected_status:
            raise ValueError("decision review version conflict")
        review = self._reviews.get_open_for_record(decision_record_id)
        if review is None:
            review = DecisionReview(
                id=f"drv:{decision_record_id}:{abs(hash((action, actor_id))) % 100000}",
                organization_id=record.organization_id,
                workspace_id=record.workspace_id,
                workspace_version_id=record.workspace_version_id,
                decision_record_id=decision_record_id,
                status="open",
                opened_by=actor_id,
                notes=list(notes),
            )
        next_status = {
            "approve": "closed",
            "request_revision": "review_required",
            "retire": "retired",
        }.get(action, record.status)
        updated_review = DecisionReview(
            id=review.id,
            organization_id=review.organization_id,
            workspace_id=review.workspace_id,
            workspace_version_id=review.workspace_version_id,
            decision_record_id=review.decision_record_id,
            status="closed" if action == "approve" else "open",
            opened_by=review.opened_by,
            closed_by=actor_id if action == "approve" else None,
            close_reason=action if action == "approve" else "",
            notes=[*review.notes, *notes],
            correlation_id=review.correlation_id,
        )
        self._reviews.upsert(updated_review)
        self._records.upsert(
            type(record)(
                id=record.id,
                organization_id=record.organization_id,
                workspace_id=record.workspace_id,
                workspace_version_id=record.workspace_version_id,
                problem_frame_id=record.problem_frame_id,
                comparison_id=record.comparison_id,
                draft_id=record.draft_id,
                selected_option_id=record.selected_option_id,
                status=next_status,
                decision_basis=record.decision_basis,
                rejected_option_ids=record.rejected_option_ids,
                review_due=record.review_due,
                limitations=record.limitations,
                historical_value_score=record.historical_value_score,
                last_outcome_status=record.last_outcome_status,
                last_outcome_at=record.last_outcome_at,
                missing_basis=record.missing_basis,
                uncertainty_markers=record.uncertainty_markers,
            )
        )
        self._governance.append(
            GovernanceEvent(
                id=f"decision_review_action:{decision_record_id}:{action}",
                organization_id=record.organization_id,
                workspace_id=record.workspace_id,
                event_type="decision_review_action",
                payload={"decision_record_id": decision_record_id, "action": action, "notes": list(notes)},
                actor_type="user",
                actor_id=actor_id,
            )
        )
        return updated_review
