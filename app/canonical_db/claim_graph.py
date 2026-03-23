from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import re

from app.canonical_db.domain import Claim, ClaimRelation
from app.canonical_db.repositories import ClaimRepository


GRAPH_NATIVE_TYPES = {
    "source_fact",
    "derived_metric",
    "decision_constraint",
    "normative_target",
    "interpretation",
    "hypothesis",
}


@dataclass(frozen=True)
class GraphConflictSummary:
    conflict_cases: list[dict[str, object]]
    duplicate_clusters: list[dict[str, object]]


def _normalize_key(claim: Claim) -> str:
    statement = re.sub(r"\d+(?:[.,]\d+)?", "#", claim.statement.lower())
    statement = re.sub(r"\b(not|no|cannot|нет|нельзя|запрещ\w*)\b", " ", statement, flags=re.IGNORECASE)
    statement = re.sub(r"[^a-zа-я0-9#]+", " ", statement, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", statement).strip()
    return normalized or claim.claim_key.strip().lower()


def _polarity(statement: str) -> str:
    text = f" {statement.lower()} "
    if any(marker in text for marker in (" not ", " no ", " cannot ", " нельзя ", " нет ", " запрещ")):
        return "negative"
    return "positive"


class ClaimGraphService:
    def __init__(
        self,
        claims: ClaimRepository,
        mark_projections_stale: Callable[[str, str], object] | None = None,
    ):
        self._claims = claims
        self._mark_projections_stale = mark_projections_stale

    def create_claim(self, claim: Claim, *, changed_by_actor: str, change_reason: str) -> Claim:
        self._validate_claim_type(claim.claim_type)
        return self._claims.create_claim(
            claim,
            changed_by_actor=changed_by_actor,
            change_reason=change_reason,
        )

    def update_claim(self, claim_id: str, **kwargs) -> Claim:
        self._validate_claim_type(kwargs["claim_type"])
        updated = self._claims.update_claim(claim_id, **kwargs)
        if self._mark_projections_stale is not None:
            self._mark_projections_stale(updated.workspace_id, updated.claim_type)
        return updated

    def add_relation(self, relation: ClaimRelation) -> ClaimRelation:
        return self._claims.add_relation(relation)

    def summarize_conflicts(self, workspace_id: str) -> GraphConflictSummary:
        claims = self._claims.list_for_workspace(workspace_id)
        groups: dict[str, list[Claim]] = {}
        for claim in claims:
            groups.setdefault(_normalize_key(claim), []).append(claim)

        conflicts: list[dict[str, object]] = []
        duplicates: list[dict[str, object]] = []
        for normalized_key, candidates in sorted(groups.items()):
            if len(candidates) < 2:
                continue
            statements = {candidate.statement.strip().lower() for candidate in candidates}
            polarities = {_polarity(candidate.statement) for candidate in candidates}
            if len(polarities) > 1:
                conflicts.append(
                    {
                        "conflict_id": f"conflict::{normalized_key}",
                        "claim_key": normalized_key,
                        "node_ids": [claim.id for claim in sorted(candidates, key=lambda item: item.id)],
                    }
                )
            elif len(statements) > 1:
                duplicates.append(
                    {
                        "duplicate_id": f"duplicate::{normalized_key}",
                        "claim_key": normalized_key,
                        "node_ids": [claim.id for claim in sorted(candidates, key=lambda item: item.id)],
                    }
                )
        return GraphConflictSummary(conflict_cases=conflicts, duplicate_clusters=duplicates)

    def _validate_claim_type(self, claim_type: str) -> None:
        if claim_type not in GRAPH_NATIVE_TYPES:
            raise ValueError(f"Unsupported claim type: {claim_type}")
