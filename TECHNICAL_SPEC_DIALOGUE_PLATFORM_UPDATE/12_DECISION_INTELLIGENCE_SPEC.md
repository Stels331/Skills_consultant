# Decision Intelligence Layer Spec

## 1. Purpose

This document defines the internal decision-intelligence layer for `Electronic Consultant v3`.

Goal:

- make solution search operate on explicit decision structures, not only on free-form answer text;
- preserve traceability from `problem frame -> options -> comparison -> selected decision`;
- keep decision artifacts fully grounded in claims, evidence, projections and governance events;
- make historical solutions reusable for future case-grounded reasoning without cross-case contamination.

This layer is implemented inside `Electronic Consultant`, not as an external dependency.

## 2. Core Idea

The system must distinguish between:

- facts and interpretations about a case;
- candidate solutions;
- the explicit decision contract that explains why one option is preferred over others.

The current platform already models:

- claims;
- evidence and artifacts;
- projections;
- dialogue and clarification;
- model update and re-entry.

The new layer adds first-class objects for decision reasoning.

## 3. Required First-Class Entities

The canonical model must introduce:

- `ProblemFrame`
- `DecisionOption`
- `DecisionComparison`
- `DecisionRecord`
- `DecisionEvidenceLink`
- `DecisionReview`
- `DecisionOutcome`

### 3.1 ProblemFrame

Represents the normalized problem statement for the current workspace.

Must contain:

- problem statement;
- scope boundary;
- symptoms vs root-cause distinction;
- decision context;
- accepted success criteria;
- unresolved unknowns.

### 3.2 DecisionOption

Represents one candidate solution or intervention.

Must contain:

- option id and label;
- option description;
- applicable scope;
- assumptions;
- expected benefits;
- expected costs;
- expected risks;
- implementation prerequisites.

### 3.3 DecisionComparison

Represents a structured comparison across options.

Must contain:

- compared option ids;
- comparison dimensions;
- per-dimension score or judgment;
- trade-offs;
- blockers;
- rationale notes.

### 3.4 DecisionRecord

Represents the selected or recommended decision.

Must contain:

- selected option id;
- rejected alternatives;
- explicit rationale;
- supporting evidence refs;
- known limitations;
- implementation notes;
- review_due timestamp or rule.

### 3.5 DecisionEvidenceLink

Represents linkage between a decision and its support base.

Must support references to:

- claim ids;
- artifact ids;
- projection snapshot ids;
- governance event ids;
- source sections or retrieval chunks.

### 3.6 DecisionReview

Represents later reassessment of the decision.

Must contain:

- review status;
- reviewer actor;
- trigger reason;
- change summary;
- outcome: keep, revise, downgrade, retire.

### 3.7 DecisionOutcome

Represents an explicit historical result of using, reviewing or invalidating a decision.

Must contain:

- linked `decision_id`;
- `outcome_type`;
- normalized `outcome_score`;
- source of the outcome signal;
- supporting evidence refs;
- recorded timestamp.

Examples:

- `operator_confirmed`
- `implemented_successfully`
- `stable_after_reentry_window`
- `rejected_after_review`
- `caused_reentry`
- `retired_due_to_assurance_floor`

## 4. Relation To Existing Platform

The decision-intelligence layer must be built on top of:

- canonical claims;
- projection snapshots;
- dialogue outputs;
- validation outputs;
- governance ledger.

Outcome signals must also be derived from existing platform events rather than from free-form narrative only:

- governance events;
- review actions;
- re-entry transitions;
- assurance downgrades and retirements.

It must not create a parallel reasoning model disconnected from the existing `canonical_db`.

## 5. Decision Contract

Every recommendation returned by the system must be representable as a `DecisionRecord`.

This means the system must be able to answer:

- what problem is being solved;
- what options were considered;
- why the selected option is preferred;
- what evidence supports the choice;
- what assumptions or unknowns remain;
- when the decision must be reviewed again.

If the system cannot build this contract, the recommendation must be degraded or blocked.

## 6. Retrieval Implications

Solution retrieval must evolve from simple claim/artifact grounding to decision-aware retrieval.

The system should support:

- similar `ProblemFrame` lookup;
- retrieval of historical `DecisionOption` patterns;
- retrieval of prior accepted and rejected options;
- consequence-aware lookup of prior `DecisionRecord` objects.
- outcome-aware reranking of historical options and decisions.

This retrieval must remain:

- workspace-scoped by default;
- tenant-scoped for any organization-level reuse;
- explicit and auditable when historical decision patterns are reused.

Cross-case transfer must never be silent.

Historical reuse must not rely on similarity alone. It should be able to account for:

- freshness of historical decisions;
- assurance state of historical decisions;
- normalized positive and negative outcome history.

## 7. Required Projections

The system should introduce:

- `problem_frame_projection`
- `solution_options_projection`
- `decision_contract_projection`

### 7.1 problem_frame_projection

Summarizes:

- the current root problem;
- boundaries and assumptions;
- decision criteria;
- unresolved unknowns.

### 7.2 solution_options_projection

Summarizes:

- available options;
- option clusters;
- constraints and risk markers;
- feasibility notes.

### 7.3 decision_contract_projection

Summarizes:

- preferred option;
- rejected options;
- comparison rationale;
- evidence links;
- assurance breakdown;
- review triggers.

## 8. API Expectations

The dialogue and decision APIs should eventually expose:

- `recommended_options`
- `decision_basis`
- `decision_contract`
- `comparison_dimensions`
- `review_due`
- `historical_outcome_summary`
- `historical_value_score`

These responses must remain grounded in canonical entities rather than only in generated prose.

## 9. Governance Requirements

The epistemic ledger must support new event types:

- `decision_option_created`
- `decision_compared`
- `decision_selected`
- `decision_rejected`
- `decision_review_due`
- `decision_retired`
- `decision_outcome_recorded`
- `decision_outcome_recomputed`

These events must remain append-only and traceable to actors and workspace versions.

## 10. Acceptance Criteria

- the system can represent a decision separately from raw answer text;
- every selected solution can be traced to supporting claims, artifacts and projections;
- decision retrieval can reuse prior patterns without hidden cross-case contamination;
- historical decision reuse can account for explicit positive and negative outcomes rather than pure similarity only;
- the UI/API can expose why a solution is recommended, not only what is recommended;
- decisions can later be reviewed, revised or retired through explicit governance events.
