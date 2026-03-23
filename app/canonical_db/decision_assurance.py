from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
import sqlite3
from typing import Sequence

from app.canonical_db.decision_domain import (
    SqliteDecisionEvidenceLinkRepository,
    SqliteDecisionOutcomeRepository,
    SqliteDecisionRecordRepository,
    SqliteDecisionReviewRepository,
)
from app.canonical_db.domain import (
    DecisionAssuranceSnapshot,
    DecisionOutcome,
    DecisionRecord,
    DecisionReview,
    DecisionWaiver,
    GovernanceEvent,
    ReentryJobRecord,
)
from app.canonical_db.repositories import ConnectionFactory, GovernanceEventRepository


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


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _event_id(prefix: str, key: str) -> str:
    return f"{prefix}:{key}:{abs(hash((prefix, key))) % 1000000}"


class SqliteDecisionAssuranceSnapshotRepository:
    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def upsert(self, snapshot: DecisionAssuranceSnapshot) -> DecisionAssuranceSnapshot:
        with self._connection_factory() as connection:
            connection.execute(
                """
                INSERT INTO decision_assurance_snapshots (
                    id, organization_id, workspace_id, workspace_version_id, decision_record_id,
                    assurance_score, assurance_status, weakest_link_ref, decay_penalty,
                    review_required, staleness_flags_json, waiver_active,
                    historical_outcome_modifier, breakdown_json, invalidated,
                    recompute_scope, policy_class
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(decision_record_id) DO UPDATE SET
                    id = excluded.id,
                    assurance_score = excluded.assurance_score,
                    assurance_status = excluded.assurance_status,
                    weakest_link_ref = excluded.weakest_link_ref,
                    decay_penalty = excluded.decay_penalty,
                    review_required = excluded.review_required,
                    staleness_flags_json = excluded.staleness_flags_json,
                    waiver_active = excluded.waiver_active,
                    historical_outcome_modifier = excluded.historical_outcome_modifier,
                    breakdown_json = excluded.breakdown_json,
                    invalidated = excluded.invalidated,
                    recompute_scope = excluded.recompute_scope,
                    policy_class = excluded.policy_class,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    snapshot.id,
                    snapshot.organization_id,
                    snapshot.workspace_id,
                    snapshot.workspace_version_id,
                    snapshot.decision_record_id,
                    snapshot.assurance_score,
                    snapshot.assurance_status,
                    snapshot.weakest_link_ref,
                    snapshot.decay_penalty,
                    1 if snapshot.review_required else 0,
                    _dumps(snapshot.staleness_flags),
                    1 if snapshot.waiver_active else 0,
                    snapshot.historical_outcome_modifier,
                    _dumps(snapshot.breakdown),
                    1 if snapshot.invalidated else 0,
                    snapshot.recompute_scope,
                    snapshot.policy_class,
                ),
            )
        return snapshot

    def get(self, decision_record_id: str) -> DecisionAssuranceSnapshot | None:
        with self._connection_factory() as connection:
            row = connection.execute(
                """
                SELECT id, organization_id, workspace_id, workspace_version_id, decision_record_id,
                       assurance_score, assurance_status, weakest_link_ref, decay_penalty,
                       review_required, staleness_flags_json, waiver_active,
                       historical_outcome_modifier, breakdown_json, invalidated,
                       recompute_scope, policy_class
                FROM decision_assurance_snapshots
                WHERE decision_record_id = ?
                """,
                (decision_record_id,),
            ).fetchone()
        return None if row is None else _row_to_snapshot(row)

    def list_for_workspace(self, workspace_id: str) -> list[DecisionAssuranceSnapshot]:
        with self._connection_factory() as connection:
            rows = connection.execute(
                """
                SELECT id, organization_id, workspace_id, workspace_version_id, decision_record_id,
                       assurance_score, assurance_status, weakest_link_ref, decay_penalty,
                       review_required, staleness_flags_json, waiver_active,
                       historical_outcome_modifier, breakdown_json, invalidated,
                       recompute_scope, policy_class
                FROM decision_assurance_snapshots
                WHERE workspace_id = ?
                ORDER BY updated_at, id
                """,
                (workspace_id,),
            ).fetchall()
        return [_row_to_snapshot(row) for row in rows]


class SqliteDecisionWaiverRepository:
    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def upsert(self, waiver: DecisionWaiver) -> DecisionWaiver:
        with self._connection_factory() as connection:
            connection.execute(
                """
                INSERT INTO decision_waivers (
                    id, organization_id, workspace_id, workspace_version_id, decision_record_id,
                    status, scope, justification, residual_risk, renewal_policy,
                    expires_at, actor_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    scope = excluded.scope,
                    justification = excluded.justification,
                    residual_risk = excluded.residual_risk,
                    renewal_policy = excluded.renewal_policy,
                    expires_at = excluded.expires_at,
                    actor_id = excluded.actor_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    waiver.id,
                    waiver.organization_id,
                    waiver.workspace_id,
                    waiver.workspace_version_id,
                    waiver.decision_record_id,
                    waiver.status,
                    waiver.scope,
                    waiver.justification,
                    waiver.residual_risk,
                    waiver.renewal_policy,
                    waiver.expires_at,
                    waiver.actor_id,
                ),
            )
        return waiver

    def list_for_record(self, decision_record_id: str) -> list[DecisionWaiver]:
        with self._connection_factory() as connection:
            rows = connection.execute(
                """
                SELECT id, organization_id, workspace_id, workspace_version_id, decision_record_id,
                       status, scope, justification, residual_risk, renewal_policy,
                       expires_at, actor_id
                FROM decision_waivers
                WHERE decision_record_id = ?
                ORDER BY created_at, id
                """,
                (decision_record_id,),
            ).fetchall()
        return [_row_to_waiver(row) for row in rows]

    def get_active(self, decision_record_id: str) -> DecisionWaiver | None:
        with self._connection_factory() as connection:
            row = connection.execute(
                """
                SELECT id, organization_id, workspace_id, workspace_version_id, decision_record_id,
                       status, scope, justification, residual_risk, renewal_policy,
                       expires_at, actor_id
                FROM decision_waivers
                WHERE decision_record_id = ? AND status = 'active'
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (decision_record_id,),
            ).fetchone()
        return None if row is None else _row_to_waiver(row)


class DecisionAssuranceEngine:
    CRITICALITY_WEIGHT = {
        "critical": 1.0,
        "standard": 0.75,
        "supporting": 0.55,
    }

    def __init__(
        self,
        records: SqliteDecisionRecordRepository,
        links: SqliteDecisionEvidenceLinkRepository,
        outcomes: SqliteDecisionOutcomeRepository,
        snapshots: SqliteDecisionAssuranceSnapshotRepository,
        waivers: SqliteDecisionWaiverRepository,
        reviews: SqliteDecisionReviewRepository,
        governance: GovernanceEventRepository,
    ):
        self._records = records
        self._links = links
        self._outcomes = outcomes
        self._snapshots = snapshots
        self._waivers = waivers
        self._reviews = reviews
        self._governance = governance

    def recompute(
        self,
        *,
        decision_record_id: str,
        now: str | None = None,
        recompute_scope: str = "full",
        policy_class: str = "standard",
        trigger: str = "manual",
    ) -> DecisionAssuranceSnapshot:
        record = self._records.get(decision_record_id)
        if record is None:
            raise KeyError(decision_record_id)
        current_time = _parse_dt(now) or datetime.now(timezone.utc)
        links = self._links.list_for_record(decision_record_id)
        outcomes = self._outcomes.list_for_record(decision_record_id)
        waiver = self._waivers.get_active(decision_record_id)
        waiver_active = False
        waiver_expired = False
        if waiver is not None:
            expires_at = _parse_dt(waiver.expires_at)
            if expires_at is not None and expires_at <= current_time:
                waiver = replace(waiver, status="expired")
                self._waivers.upsert(waiver)
                waiver_expired = True
                self._governance.append(
                    GovernanceEvent(
                        id=_event_id("governance", waiver.id + ":expired"),
                        organization_id=waiver.organization_id,
                        workspace_id=waiver.workspace_id,
                        event_type="waiver_expired",
                        payload={"decision_record_id": waiver.decision_record_id, "renewal_policy": waiver.renewal_policy},
                        actor_type="system",
                        actor_id="decision_assurance_scheduler",
                    )
                )
            else:
                waiver_active = True

        base_score = 1.0
        weakest_score = 1.0
        weakest_ref = ""
        penalties: list[float] = []
        staleness_flags: list[str] = []
        breakdown_links: list[dict[str, object]] = []

        for link in links:
            criticality = link.criticality or "standard"
            weight = self.CRITICALITY_WEIGHT.get(criticality, self.CRITICALITY_WEIGHT["standard"])
            link_score = max(0.0, min(1.0, link.link_strength * weight))
            freshness_mode = str(link.metadata.get("freshness_mode") or "")
            valid_until = str(link.metadata.get("valid_until") or "")
            expiry = _parse_dt(valid_until)
            if freshness_mode == "hard" and expiry is not None and expiry <= current_time:
                link_score *= 0.05
                penalties.append(0.9)
                staleness_flags.append(f"hard_expiry:{link.id}")
                self._governance.append(
                    GovernanceEvent(
                        id=_event_id("governance", link.id + ":hard_expiry"),
                        organization_id=record.organization_id,
                        workspace_id=record.workspace_id,
                        event_type="evidence_expired",
                        payload={"decision_record_id": record.id, "link_id": link.id, "mode": "hard"},
                        actor_type="system",
                        actor_id="decision_assurance_engine",
                    )
                )
            elif freshness_mode == "soft" and expiry is not None and expiry <= current_time:
                link_score *= 0.65
                penalties.append(0.2)
                staleness_flags.append(f"soft_staleness:{link.id}")
            if link.link_direction == "contradicts":
                penalties.append(0.35)
                link_score *= 0.4
            weakest_score, weakest_ref = min((weakest_score, weakest_ref), (link_score, link.id), key=lambda item: item[0])
            breakdown_links.append(
                {
                    "link_id": link.id,
                    "score": round(link_score, 4),
                    "criticality": criticality,
                    "direction": link.link_direction,
                }
            )

        multiplicative_penalty = 1.0
        for penalty in penalties:
            multiplicative_penalty *= max(0.0, 1.0 - penalty)
        decay_penalty = round(1.0 - multiplicative_penalty, 4)

        if record.missing_basis:
            multiplicative_penalty *= 0.8
            decay_penalty = round(1.0 - multiplicative_penalty, 4)
            staleness_flags.append("missing_basis")

        historical_modifier = self._historical_modifier(outcomes)
        assurance_score = max(0.0, min(1.0, (base_score * multiplicative_penalty * weakest_score) + historical_modifier))

        floor = 0.35 if policy_class in {"critical", "compliance", "safety"} else 0.2
        review_required = bool(record.status == "review_required" or staleness_flags or assurance_score < 0.6 or waiver_expired)
        if assurance_score < floor:
            assurance_status = "block"
            updated_record = replace(record, status="retired")
            self._records.upsert(updated_record)
            self._governance.append(
                GovernanceEvent(
                    id=_event_id("governance", record.id + ":downgraded"),
                    organization_id=record.organization_id,
                    workspace_id=record.workspace_id,
                    event_type="decision_downgraded",
                    payload={"decision_record_id": record.id, "assurance_status": "block", "floor": floor},
                    actor_type="system",
                    actor_id="decision_assurance_engine",
                )
            )
        elif assurance_score < 0.6:
            assurance_status = "degrade"
        else:
            assurance_status = "pass"

        snapshot = DecisionAssuranceSnapshot(
            id=f"das:{record.id}",
            organization_id=record.organization_id,
            workspace_id=record.workspace_id,
            workspace_version_id=record.workspace_version_id,
            decision_record_id=record.id,
            assurance_score=round(assurance_score, 4),
            assurance_status=assurance_status,
            weakest_link_ref=weakest_ref,
            decay_penalty=decay_penalty,
            review_required=review_required,
            staleness_flags=sorted(set(staleness_flags)),
            waiver_active=waiver_active,
            historical_outcome_modifier=historical_modifier,
            breakdown={
                "links": breakdown_links,
                "penalties": penalties,
                "waiver_expired": waiver_expired,
                "trigger": trigger,
            },
            invalidated=False,
            recompute_scope=recompute_scope,
            policy_class=policy_class,
        )
        self._snapshots.upsert(snapshot)
        self._governance.append(
            GovernanceEvent(
                id=_event_id("governance", record.id + f":assurance:{snapshot.assurance_status}:{trigger}"),
                organization_id=record.organization_id,
                workspace_id=record.workspace_id,
                event_type="decision_assurance_recomputed",
                payload={
                    "decision_record_id": record.id,
                    "assurance_score": snapshot.assurance_score,
                    "assurance_status": snapshot.assurance_status,
                    "weakest_link_ref": snapshot.weakest_link_ref,
                    "recompute_scope": recompute_scope,
                    "trigger": trigger,
                },
                actor_type="system",
                actor_id="decision_assurance_engine",
            )
        )
        if historical_modifier != 0.0:
            self._governance.append(
                GovernanceEvent(
                    id=_event_id("governance", record.id + f":outcome_modifier:{trigger}"),
                    organization_id=record.organization_id,
                    workspace_id=record.workspace_id,
                    event_type="decision_outcome_applied_to_assurance",
                    payload={
                        "decision_record_id": record.id,
                        "historical_outcome_modifier": historical_modifier,
                        "trigger": trigger,
                    },
                    actor_type="system",
                    actor_id="decision_assurance_engine",
                )
            )
        return snapshot

    def invalidate(self, decision_record_id: str, *, trigger: str) -> DecisionAssuranceSnapshot | None:
        snapshot = self._snapshots.get(decision_record_id)
        if snapshot is None:
            return None
        invalidated = replace(snapshot, invalidated=True)
        self._snapshots.upsert(invalidated)
        self._governance.append(
            GovernanceEvent(
                id=_event_id("governance", decision_record_id + f":invalidated:{trigger}"),
                organization_id=invalidated.organization_id,
                workspace_id=invalidated.workspace_id,
                event_type="decision_review_due",
                payload={"decision_record_id": decision_record_id, "trigger": trigger},
                actor_type="system",
                actor_id="decision_assurance_engine",
            )
        )
        return invalidated

    @staticmethod
    def _historical_modifier(outcomes: Sequence[DecisionOutcome]) -> float:
        if not outcomes:
            return 0.0
        average = sum(item.outcome_score for item in outcomes) / len(outcomes)
        return round(max(-0.2, min(0.1, average * 0.2)), 4)


class DecisionOutcomeResolver:
    EVENT_SCORE_MAP = {
        "decision_selected": ("operator_confirmed", 0.1),
        "decision_downgraded": ("retired_due_to_assurance_floor", -1.0),
        "decision_review_due": ("caused_reentry", -0.6),
        "stage_recomputed": ("stable_after_reentry_window", 0.4),
    }

    def __init__(self, outcomes: SqliteDecisionOutcomeRepository, governance: GovernanceEventRepository):
        self._outcomes = outcomes
        self._governance = governance

    def resolve_workspace(self, *, workspace_id: str, record_id: str, workspace_version_id: str, organization_id: str) -> list[DecisionOutcome]:
        result: list[DecisionOutcome] = []
        for event in self._governance.list_for_workspace(workspace_id):
            if event.event_type not in self.EVENT_SCORE_MAP:
                continue
            if event.payload.get("decision_record_id") not in {None, record_id} and event.event_type != "stage_recomputed":
                continue
            outcome_type, outcome_score = self.EVENT_SCORE_MAP[event.event_type]
            outcome = DecisionOutcome(
                id=f"out:{record_id}:{event.id}",
                organization_id=organization_id,
                workspace_id=workspace_id,
                workspace_version_id=workspace_version_id,
                decision_record_id=record_id,
                outcome_type=outcome_type,
                outcome_score=outcome_score,
                source=event.event_type,
                evidence={"governance_event_id": event.id},
                recorded_at=_utc_now(),
            )
            self._outcomes.append(outcome)
            result.append(outcome)
        return result


class DecisionAssuranceScheduler:
    def __init__(
        self,
        records: SqliteDecisionRecordRepository,
        snapshots: SqliteDecisionAssuranceSnapshotRepository,
        engine: DecisionAssuranceEngine,
    ):
        self._records = records
        self._snapshots = snapshots
        self._engine = engine

    def run_workspace(self, *, workspace_id: str, now: str | None = None) -> list[DecisionAssuranceSnapshot]:
        result: list[DecisionAssuranceSnapshot] = []
        for record in self._records.list_for_workspace(workspace_id):
            snapshot = self._snapshots.get(record.id)
            if snapshot is not None and not snapshot.invalidated and snapshot.assurance_status == "pass":
                # Still rerun only if soft staleness exists in stored flags; deterministic event ids keep this idempotent.
                if not any(flag.startswith(("soft_staleness:", "hard_expiry:")) for flag in snapshot.staleness_flags):
                    continue
            result.append(self._engine.recompute(decision_record_id=record.id, now=now, recompute_scope="incremental", trigger="scheduler"))
        return result


class DecisionWaiverService:
    def __init__(self, waivers: SqliteDecisionWaiverRepository, governance: GovernanceEventRepository):
        self._waivers = waivers
        self._governance = governance

    def apply(
        self,
        *,
        record: DecisionRecord,
        scope: str,
        justification: str,
        residual_risk: str,
        renewal_policy: str,
        expires_at: str,
        actor_id: str,
    ) -> DecisionWaiver:
        waiver = DecisionWaiver(
            id=f"waiver:{record.id}:{abs(hash((scope, expires_at, actor_id))) % 100000}",
            organization_id=record.organization_id,
            workspace_id=record.workspace_id,
            workspace_version_id=record.workspace_version_id,
            decision_record_id=record.id,
            status="active",
            scope=scope,
            justification=justification,
            residual_risk=residual_risk,
            renewal_policy=renewal_policy,
            expires_at=expires_at,
            actor_id=actor_id,
        )
        self._waivers.upsert(waiver)
        self._governance.append(
            GovernanceEvent(
                id=_event_id("governance", waiver.id + ":applied"),
                organization_id=waiver.organization_id,
                workspace_id=waiver.workspace_id,
                event_type="waiver_applied",
                payload={
                    "decision_record_id": waiver.decision_record_id,
                    "scope": waiver.scope,
                    "renewal_policy": waiver.renewal_policy,
                },
                actor_type="user",
                actor_id=actor_id,
            )
        )
        return waiver


def _row_to_snapshot(row: sqlite3.Row) -> DecisionAssuranceSnapshot:
    return DecisionAssuranceSnapshot(
        id=row["id"],
        organization_id=row["organization_id"],
        workspace_id=row["workspace_id"],
        workspace_version_id=row["workspace_version_id"],
        decision_record_id=row["decision_record_id"],
        assurance_score=row["assurance_score"],
        assurance_status=row["assurance_status"],
        weakest_link_ref=row["weakest_link_ref"],
        decay_penalty=row["decay_penalty"],
        review_required=bool(row["review_required"]),
        staleness_flags=_loads_list(row["staleness_flags_json"]),
        waiver_active=bool(row["waiver_active"]),
        historical_outcome_modifier=row["historical_outcome_modifier"],
        breakdown=_loads_dict(row["breakdown_json"]),
        invalidated=bool(row["invalidated"]),
        recompute_scope=row["recompute_scope"],
        policy_class=row["policy_class"],
    )


def _row_to_waiver(row: sqlite3.Row) -> DecisionWaiver:
    return DecisionWaiver(
        id=row["id"],
        organization_id=row["organization_id"],
        workspace_id=row["workspace_id"],
        workspace_version_id=row["workspace_version_id"],
        decision_record_id=row["decision_record_id"],
        status=row["status"],
        scope=row["scope"],
        justification=row["justification"],
        residual_risk=row["residual_risk"],
        renewal_policy=row["renewal_policy"],
        expires_at=row["expires_at"],
        actor_id=row["actor_id"],
    )


def assurance_payload(snapshot: DecisionAssuranceSnapshot | None, waiver: DecisionWaiver | None = None) -> dict:
    if snapshot is None:
        return {}
    return {
        "assurance_score": snapshot.assurance_score,
        "assurance_status": snapshot.assurance_status,
        "weakest_link_ref": snapshot.weakest_link_ref,
        "decay_penalty": snapshot.decay_penalty,
        "review_required": snapshot.review_required,
        "staleness_flags": snapshot.staleness_flags,
        "waiver_active": snapshot.waiver_active,
        "historical_outcome_modifier": snapshot.historical_outcome_modifier,
        "historical_outcome_summary": {
            "modifier": snapshot.historical_outcome_modifier,
            "status": snapshot.assurance_status,
        },
        "waiver": None
        if waiver is None
        else {
            "scope": waiver.scope,
            "renewal_policy": waiver.renewal_policy,
            "expires_at": waiver.expires_at,
            "residual_risk": waiver.residual_risk,
        },
    }


def recompute_scope_from_reentry(job: ReentryJobRecord) -> str:
    return "incremental" if len(job.dependent_projections) <= 2 and len(job.stale_outputs) <= 3 else "full"
