from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


JsonDict = dict[str, Any]


@dataclass(frozen=True)
class User:
    id: str
    email: str
    password_hash: str
    display_name: str
    status: str = "active"


@dataclass(frozen=True)
class UserProfile:
    user_id: str
    active_organization_id: str | None = None
    settings: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class Organization:
    id: str
    name: str
    slug: str
    owner_user_id: str
    status: str = "active"
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class Membership:
    id: str
    organization_id: str
    user_id: str
    role: str
    status: str = "active"
    invited_by_user_id: str | None = None
    joined_at: str | None = None


@dataclass(frozen=True)
class Workspace:
    id: str
    organization_id: str
    workspace_key: str
    title: str
    case_type: str
    status: str
    current_stage: str
    active_model_version: int
    created_by_user_id: str
    metadata: JsonDict = field(default_factory=dict)
    reentry_status: str = "idle"


@dataclass(frozen=True)
class WorkspaceVersion:
    id: str
    organization_id: str
    workspace_id: str
    version_no: int
    version_label: str
    change_reason: str
    created_by: str


@dataclass(frozen=True)
class Artifact:
    id: str
    organization_id: str
    workspace_id: str
    workspace_version_id: str
    artifact_type: str
    stage_name: str
    artifact_key: str
    status: str
    format: str
    payload: JsonDict
    file_path: str
    summary_text: str = ""


@dataclass(frozen=True)
class Claim:
    id: str
    organization_id: str
    workspace_id: str
    workspace_version_id: str
    claim_key: str
    claim_type: str
    statement: str
    epistemic_status: str
    confidence_score: float
    source_kind: str
    source_ref: str
    attributes: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class ClaimVersion:
    id: str
    organization_id: str
    workspace_id: str
    claim_id: str
    version_no: int
    claim_type: str
    statement: str
    epistemic_status: str
    confidence_score: float
    source_kind: str
    source_ref: str
    attributes: JsonDict = field(default_factory=dict)
    change_reason: str = ""
    changed_by_actor: str = ""


@dataclass(frozen=True)
class ClaimRelation:
    id: str
    organization_id: str
    workspace_id: str
    from_claim_id: str
    to_claim_id: str
    relation_type: str
    weight: float = 1.0
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class AuthSession:
    id: str
    user_id: str
    organization_id: str | None
    status: str
    expires_at: str
    last_seen_at: str
    invalidated_at: str | None = None


@dataclass(frozen=True)
class DialogueSession:
    id: str
    organization_id: str
    workspace_id: str
    created_by_user_id: str
    status: str
    active_workspace_version_id: str
    title: str


@dataclass(frozen=True)
class DialogueMessage:
    id: str
    organization_id: str
    workspace_id: str
    session_id: str
    workspace_version_id: str
    actor_type: str
    actor_user_id: str | None
    question_class: str
    message_type: str
    content_text: str
    grounding_bundle_ref: str | None = None
    validator_result: str | None = None
    graph_version: str | None = None


@dataclass(frozen=True)
class GovernanceEvent:
    id: str
    organization_id: str
    workspace_id: str
    event_type: str
    payload: JsonDict
    actor_type: str
    actor_id: str


@dataclass(frozen=True)
class ProjectionSnapshot:
    id: str
    organization_id: str
    workspace_id: str
    workspace_version_id: str
    projection_type: str
    freshness_status: str
    source_claim_version_ids: list[str] = field(default_factory=list)
    payload: JsonDict = field(default_factory=dict)
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class MaterializedArtifactIndexEntry:
    id: str
    organization_id: str
    workspace_id: str
    projection_type: str
    stage_name: str
    output_key: str
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalChunk:
    id: str
    organization_id: str
    workspace_id: str
    artifact_id: str | None
    claim_id: str | None
    chunk_key: str
    chunk_text: str
    section_title: str | None
    status: str
    retrieval_revision: int = 1
    source_revision: str = ""
    freshness_status: str = "fresh"
    is_active: bool = True


@dataclass(frozen=True)
class EmbeddingJob:
    id: str
    organization_id: str
    workspace_id: str
    retrieval_chunk_id: str | None
    status: str
    provider: str
    model_key: str
    source_revision: str = ""
    attempt_count: int = 0
    last_error: str = ""


@dataclass(frozen=True)
class QuotaLedgerEntry:
    id: str
    organization_id: str
    workspace_id: str | None
    user_id: str | None
    metric_key: str
    delta: float
    unit: str
    source_event: str


@dataclass(frozen=True)
class QuestionQueueItem:
    id: str
    organization_id: str
    workspace_id: str
    session_id: str | None
    question_class: str
    status: str
    question_text: str
    priority: int = 100
    reason_code: str = ""
    influence_area: str = ""
    impact_preview: str = ""
    rationale: str = ""
    classifier_confidence: float = 0.0


@dataclass(frozen=True)
class ReentryJobRecord:
    id: str
    organization_id: str
    workspace_id: str
    workspace_version_id: str | None
    status: str
    trigger_claim_id: str | None
    dependent_projections: list[str] = field(default_factory=list)
    affected_stages: list[str] = field(default_factory=list)
    stale_outputs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProblemFrame:
    id: str
    organization_id: str
    workspace_id: str
    workspace_version_id: str
    root_problem: str
    scope_boundary: str
    success_criteria: list[str] = field(default_factory=list)
    active_constraints: list[str] = field(default_factory=list)
    unresolved_unknowns: list[str] = field(default_factory=list)
    status: str = "active"
    invalidation_reason: str = ""
    correlation_id: str = ""


@dataclass(frozen=True)
class DecisionOption:
    id: str
    organization_id: str
    workspace_id: str
    workspace_version_id: str
    problem_frame_id: str
    option_key: str
    title: str
    summary_text: str
    status: str = "candidate"
    assumptions: list[str] = field(default_factory=list)
    confidence_in_assumptions: float = 0.0
    benefits: list[str] = field(default_factory=list)
    costs: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    historical_value_score: float = 0.0
    reuse_success_score: float = 0.0
    negative_outcome_count: int = 0
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class DecisionComparison:
    id: str
    organization_id: str
    workspace_id: str
    workspace_version_id: str
    problem_frame_id: str
    selected_option_id: str | None
    status: str
    comparison_dimensions: list[str] = field(default_factory=list)
    option_scores: JsonDict = field(default_factory=dict)
    rejected_option_ids: list[str] = field(default_factory=list)
    tradeoffs: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    rationale_notes: list[str] = field(default_factory=list)
    correlation_id: str = ""


@dataclass(frozen=True)
class DecisionDraft:
    id: str
    organization_id: str
    workspace_id: str
    workspace_version_id: str
    problem_frame_id: str
    comparison_id: str
    selected_option_id: str | None
    status: str
    missing_basis: list[str] = field(default_factory=list)
    uncertainty_markers: list[str] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DecisionRecord:
    id: str
    organization_id: str
    workspace_id: str
    workspace_version_id: str
    problem_frame_id: str
    comparison_id: str
    draft_id: str | None
    selected_option_id: str
    status: str
    decision_basis: list[str] = field(default_factory=list)
    rejected_option_ids: list[str] = field(default_factory=list)
    review_due: str | None = None
    limitations: list[str] = field(default_factory=list)
    historical_value_score: float = 0.0
    last_outcome_status: str = ""
    last_outcome_at: str | None = None
    missing_basis: list[str] = field(default_factory=list)
    uncertainty_markers: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DecisionEvidenceLink:
    id: str
    organization_id: str
    workspace_id: str
    workspace_version_id: str
    decision_record_id: str | None
    decision_option_id: str | None
    link_type: str
    link_strength: float
    link_direction: str
    source_ref: str
    criticality: str = "standard"
    claim_id: str | None = None
    artifact_id: str | None = None
    projection_snapshot_id: str | None = None
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class DecisionReview:
    id: str
    organization_id: str
    workspace_id: str
    workspace_version_id: str
    decision_record_id: str
    status: str
    opened_by: str
    closed_by: str | None = None
    close_reason: str = ""
    notes: list[str] = field(default_factory=list)
    correlation_id: str = ""


@dataclass(frozen=True)
class DecisionOutcome:
    id: str
    organization_id: str
    workspace_id: str
    workspace_version_id: str
    decision_record_id: str
    outcome_type: str
    outcome_score: float
    source: str
    evidence: JsonDict = field(default_factory=dict)
    recorded_at: str = ""


@dataclass(frozen=True)
class DecisionAssuranceSnapshot:
    id: str
    organization_id: str
    workspace_id: str
    workspace_version_id: str
    decision_record_id: str
    assurance_score: float
    assurance_status: str
    weakest_link_ref: str
    decay_penalty: float
    review_required: bool
    staleness_flags: list[str] = field(default_factory=list)
    waiver_active: bool = False
    historical_outcome_modifier: float = 0.0
    breakdown: JsonDict = field(default_factory=dict)
    invalidated: bool = False
    recompute_scope: str = "full"
    policy_class: str = "standard"


@dataclass(frozen=True)
class DecisionWaiver:
    id: str
    organization_id: str
    workspace_id: str
    workspace_version_id: str
    decision_record_id: str
    status: str
    scope: str
    justification: str
    residual_risk: str
    renewal_policy: str
    expires_at: str
    actor_id: str
