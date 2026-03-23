from __future__ import annotations

from dataclasses import dataclass
import json

from app.canonical_db.domain import Claim, MaterializedArtifactIndexEntry, ProjectionSnapshot
from app.canonical_db.repositories import (
    ClaimRepository,
    MaterializedArtifactIndexRepository,
    ProjectionSnapshotRepository,
)


@dataclass(frozen=True)
class ProjectionDescriptor:
    projection_type: str
    claim_types: tuple[str, ...]
    consuming_stages: tuple[str, ...]
    materialized_outputs: tuple[str, ...]


DEFAULT_DESCRIPTORS = (
    ProjectionDescriptor(
        projection_type="viewpoint_projection",
        claim_types=("source_fact", "interpretation", "hypothesis"),
        consuming_stages=("viewpoint", "characterization"),
        materialized_outputs=("analysis/projections/viewpoint_projection.json",),
    ),
    ProjectionDescriptor(
        projection_type="characterization_projection",
        claim_types=("interpretation", "hypothesis", "derived_metric"),
        consuming_stages=("characterization", "problem_factory"),
        materialized_outputs=("analysis/projections/characterization_projection.json",),
    ),
    ProjectionDescriptor(
        projection_type="problem_factory_projection",
        claim_types=("source_fact", "derived_metric", "decision_constraint", "normative_target"),
        consuming_stages=("problem_factory",),
        materialized_outputs=("analysis/projections/problem_factory_projection.json", "problems/SelectedProblemCard.md"),
    ),
    ProjectionDescriptor(
        projection_type="solution_factory_projection",
        claim_types=("decision_constraint", "source_fact", "derived_metric", "interpretation"),
        consuming_stages=("solution_factory", "selection"),
        materialized_outputs=("analysis/projections/solution_factory_projection.json", "solutions/SolutionPortfolio.md"),
    ),
    ProjectionDescriptor(
        projection_type="selection_projection",
        claim_types=("decision_constraint", "source_fact", "derived_metric"),
        consuming_stages=("selection", "reporting"),
        materialized_outputs=("analysis/projections/selection_projection.json", "solutions/SelectedSolutions.md"),
    ),
    ProjectionDescriptor(
        projection_type="reporting_projection",
        claim_types=("source_fact", "derived_metric", "decision_constraint", "normative_target", "interpretation"),
        consuming_stages=("reporting",),
        materialized_outputs=("analysis/projections/reporting_projection.json", "reports/FinalReport.md"),
    ),
)


class ProjectionRegistry:
    def __init__(self, descriptors: tuple[ProjectionDescriptor, ...] = DEFAULT_DESCRIPTORS):
        self._descriptors = descriptors

    def all_projection_types(self) -> list[str]:
        return [descriptor.projection_type for descriptor in self._descriptors]

    def projection_types_for_claim_type(self, claim_type: str) -> list[str]:
        return [
            descriptor.projection_type
            for descriptor in self._descriptors
            if claim_type in descriptor.claim_types
        ]

    def descriptor_for_projection(self, projection_type: str) -> ProjectionDescriptor:
        for descriptor in self._descriptors:
            if descriptor.projection_type == projection_type:
                return descriptor
        raise KeyError(f"Unknown projection type: {projection_type}")


def legacy_validator_outcome(claims: list[Claim]) -> dict[str, object]:
    claims_by_type = sorted((claim.claim_type, claim.claim_key) for claim in claims)
    return {
        "claim_count": len(claims),
        "types": [item[0] for item in claims_by_type],
        "keys": [item[1] for item in claims_by_type],
    }


class ProjectionService:
    def __init__(
        self,
        claims: ClaimRepository,
        snapshots: ProjectionSnapshotRepository,
        registry: ProjectionRegistry,
    ):
        self._claims = claims
        self._snapshots = snapshots
        self._registry = registry

    def rebuild_workspace_projections(
        self,
        *,
        organization_id: str,
        workspace_id: str,
        workspace_version_id: str,
    ) -> list[ProjectionSnapshot]:
        claims = sorted(self._claims.list_for_workspace(workspace_id), key=lambda claim: (claim.claim_type, claim.claim_key, claim.id))
        versions = {
            claim.id: self._claims.list_versions(claim.id)[-1].id
            for claim in claims
            if self._claims.list_versions(claim.id)
        }
        snapshots: list[ProjectionSnapshot] = []
        for projection_type in self._registry.all_projection_types():
            descriptor = self._registry.descriptor_for_projection(projection_type)
            relevant_claims = [claim for claim in claims if claim.claim_type in descriptor.claim_types]
            payload = {
                "projection_type": projection_type,
                "claim_ids": [claim.id for claim in relevant_claims],
                "claims": [
                    {
                        "id": claim.id,
                        "claim_key": claim.claim_key,
                        "claim_type": claim.claim_type,
                        "statement": claim.statement,
                    }
                    for claim in relevant_claims
                ],
                "validator_outcome": legacy_validator_outcome(relevant_claims),
            }
            metadata = {
                "version_context": {"workspace_version_id": workspace_version_id},
                "freshness_context": {
                    "source_claim_count": len(relevant_claims),
                    "source_claim_version_ids": [versions[claim.id] for claim in relevant_claims if claim.id in versions],
                },
            }
            snapshots.append(
                ProjectionSnapshot(
                    id=f"{workspace_id}:{projection_type}",
                    organization_id=organization_id,
                    workspace_id=workspace_id,
                    workspace_version_id=workspace_version_id,
                    projection_type=projection_type,
                    freshness_status="fresh",
                    source_claim_version_ids=metadata["freshness_context"]["source_claim_version_ids"],
                    payload=payload,
                    metadata=metadata,
                )
            )
        self._snapshots.upsert_many(snapshots)
        return snapshots

    def mark_stale_for_claim_type(self, workspace_id: str, claim_type: str) -> list[str]:
        projection_types = self._registry.projection_types_for_claim_type(claim_type)
        self._snapshots.mark_stale(workspace_id, projection_types)
        return projection_types

    def validator_outcome_from_db(self, workspace_id: str, projection_type: str) -> dict[str, object]:
        snapshots = self._snapshots.list_for_workspace(workspace_id)
        for snapshot in snapshots:
            if snapshot.projection_type == projection_type:
                return dict(snapshot.payload.get("validator_outcome") or {})
        raise KeyError(f"Projection not found: {projection_type}")


class MaterializedArtifactIndex:
    def __init__(
        self,
        registry: ProjectionRegistry,
        repository: MaterializedArtifactIndexRepository,
    ):
        self._registry = registry
        self._repository = repository

    def rebuild(self, *, organization_id: str, workspace_id: str) -> list[MaterializedArtifactIndexEntry]:
        entries: list[MaterializedArtifactIndexEntry] = []
        for descriptor in sorted(self._registry._descriptors, key=lambda item: item.projection_type):
            for stage_name in descriptor.consuming_stages:
                for output_key in descriptor.materialized_outputs:
                    entries.append(
                        MaterializedArtifactIndexEntry(
                            id=f"{workspace_id}:{descriptor.projection_type}:{stage_name}:{output_key}",
                            organization_id=organization_id,
                            workspace_id=workspace_id,
                            projection_type=descriptor.projection_type,
                            stage_name=stage_name,
                            output_key=output_key,
                            metadata={
                                "claim_types": list(descriptor.claim_types),
                                "dependency_contract": {
                                    "projection_type": descriptor.projection_type,
                                    "stage_name": stage_name,
                                },
                            },
                        )
                    )
        self._repository.replace_for_workspace(workspace_id, entries)
        return entries

    def affected_outputs(self, workspace_id: str, projection_type: str) -> dict[str, list[str]]:
        entries = [
            entry
            for entry in self._repository.list_for_workspace(workspace_id)
            if entry.projection_type == projection_type
        ]
        stages = sorted({entry.stage_name for entry in entries})
        outputs = sorted({entry.output_key for entry in entries})
        return {"stages": stages, "outputs": outputs}

    def stable_graph(self, workspace_id: str) -> str:
        entries = self._repository.list_for_workspace(workspace_id)
        normalized = [
            {
                "projection_type": entry.projection_type,
                "stage_name": entry.stage_name,
                "output_key": entry.output_key,
                "metadata": entry.metadata,
            }
            for entry in entries
        ]
        return json.dumps(normalized, ensure_ascii=False, sort_keys=True)
