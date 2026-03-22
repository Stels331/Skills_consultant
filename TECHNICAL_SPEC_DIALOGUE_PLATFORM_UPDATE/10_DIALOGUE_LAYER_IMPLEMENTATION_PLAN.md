# Dialogue Layer Implementation Plan

## 1. Purpose

This document translates the dialogue retrieval architecture into an implementation sequence.

Goal:

- add a case-grounded dialogue layer without breaking the current analytical pipeline;
- preserve FPF epistemic discipline;
- keep multi-workspace isolation strict from the first implementation stage.

## 2. Implementation Principles

The dialogue layer must be introduced in this order:

1. classification before retrieval;
2. graph-first retrieval before text retrieval;
3. grounding before generation;
4. validation after generation;
5. model update flow separate from ordinary Q&A.

The system must not begin as a generic chat UI with later “hardening”.
The first usable version must already be:

- workspace-scoped;
- claim-grounded;
- version-aware;
- FPF-validated.

## 3. Target Modules

Recommended new modules:

- `app/dialogue/question_router.py`
- `app/dialogue/dialogue_projection.py`
- `app/dialogue/section_indexer.py`
- `app/dialogue/bm25_retriever.py`
- `app/dialogue/grounding_bundle.py`
- `app/dialogue/prompt_builder.py`
- `app/dialogue/response_validator.py`
- `app/dialogue/model_update_engine.py`
- `app/dialogue/session_store.py`

Recommended schemas/contracts:

- `schemas/dialogue_message.schema.json`
- `schemas/grounding_bundle.schema.json`
- `contracts/dialogue_answer.contract.json`

## 4. Phase Plan

### Phase 1. Router and Dialogue Projection

Purpose:

- separate question classification from retrieval;
- make the graph usable as the primary dialogue retrieval substrate.

Tasks:

- implement `QuestionRouter.classify()`
- define question classes:
  - `constraint_query`
  - `problem_query`
  - `solution_query`
  - `report_query`
  - `evidence_query`
  - `clarification_needed`
- add dialogue-oriented projection rules over the epistemic graph

Outputs:

- `question_router.py`
- `dialogue_projection.py`

Acceptance criteria:

- every question is assigned a class with confidence;
- low-confidence routing falls back safely;
- `clarification_needed` does not enter retrieval flow.

### Phase 2. Section Indexing and BM25

Purpose:

- create a supplementary retrieval layer over workspace artifacts.

Tasks:

- define `SectionDoc`
- parse workspace markdown into section-level retrieval units
- extract frontmatter metadata:
  - `artifact_type`
  - `stage`
  - `epistemic_status`
  - `source_refs`
- build per-workspace BM25 index

Outputs:

- `section_indexer.py`
- `bm25_retriever.py`

Acceptance criteria:

- indexing is section-based, not file-based;
- retrieval is strict by `workspace_id`;
- index can be rebuilt after re-entry.

### Phase 3. Grounding Bundle

Purpose:

- unify graph claims and supplementary text into one structured object.

Tasks:

- define `GroundingBundle`
- combine:
  - typed claims
  - supplementary text fragments
  - `graph_version`
  - `workspace_version`
- encode trust hierarchy into the bundle

Outputs:

- `grounding_bundle.py`
- `grounding_bundle.schema.json`

Acceptance criteria:

- typed claims and text fragments are clearly separated;
- bundle carries version information;
- zero-claim cases are handled explicitly, not hidden.

### Phase 4. Prompt Builder and Answer Contract

Purpose:

- ensure the LLM receives structured, trust-aware input.

Tasks:

- build FPF-aware prompt sections:
  - `VERIFIED CLAIMS`
  - `SUPPORTING TEXT`
  - `EPISTEMIC RULES`
- define structured answer contract

Outputs:

- `prompt_builder.py`
- `dialogue_answer.contract.json`

Acceptance criteria:

- supplementary text cannot be mistaken for verified claims in prompt format;
- prompt always includes explicit epistemic rules;
- answer format is machine-validated.

### Phase 5. Response Validation

Purpose:

- prevent unlawful promotion and unsupported answers.

Tasks:

- validate citations
- ensure answer-grade assertions reference typed claims
- detect:
  - hypothesis promoted to fact
  - unsupported conclusions
  - out-of-workspace leakage
  - missing clarification escalation

Outputs:

- `response_validator.py`

Acceptance criteria:

- invalid responses are downgraded, blocked, or converted to `needs_clarification`;
- validator is independent from the generation prompt.

### Phase 6. Dialogue Session and Version Binding

Purpose:

- make each answer auditable against a concrete model version.

Tasks:

- add session/message persistence
- bind each answer to:
  - `workspace_id`
  - `workspace_version_id`
  - `graph_version`
- ensure workspace switch resets active reasoning context

Outputs:

- `session_store.py`
- persistence/API integration

Acceptance criteria:

- answers remain attributable to exact model versions;
- cross-workspace memory leakage is structurally prevented.

### Phase 7. Clarification and Model Update Flow

Purpose:

- let the dialogue layer extend the model instead of only reading it.

Tasks:

- route `clarification_needed` to model update path
- convert accepted user clarifications into structured model updates
- trigger controlled re-entry for affected stages only

Outputs:

- `model_update_engine.py`
- dialogue-to-reentry integration

Acceptance criteria:

- clarification is not mixed with ordinary Q&A;
- accepted updates mutate the model in a traceable way;
- downstream answers use the new workspace version.

## 5. UI Integration Sequence

Recommended UI rollout:

1. single-workspace dialogue tab
2. answer panel with claim citations
3. workspace version badge
4. clarification prompt UX
5. multi-workspace switcher with hard session isolation

Do not begin with free chat history only.
The first UI must already show:

- active workspace
- active model version
- claim-grounded answer basis

## 6. Database Alignment

The dialogue layer must align with the DB specs already defined in this package.

It should integrate with:

- `workspaces`
- `workspace_versions`
- `dialogue_sessions`
- `dialogue_messages`
- `claims`
- `artifacts`
- `validation_runs`
- `governance_events`

Every answer record should store:

- `workspace_id`
- `workspace_version_id`
- `question_class`
- `grounding_bundle_ref` or serialized grounding metadata
- validator result

## 7. Testing Strategy

Testing should be introduced phase by phase.

### Unit tests

- question classification
- graph dialogue projection
- section indexing
- BM25 retrieval isolation
- prompt building
- response validation

### Integration tests

- question -> router -> grounding bundle
- question -> answer -> response validator
- clarification -> model update -> workspace version increment
- workspace switch -> no session contamination

### Regression tests

- no answer from BM25-only when graph returns zero typed claims
- no cross-workspace retrieval
- no hypothesis promotion to fact
- no stale answer after workspace version change

## 8. Rollout Order

Recommended rollout order:

1. internal backend-only prototype
2. CLI or dev console dialogue run
3. validator-hardened backend API
4. UI integration
5. clarification update flow
6. multi-workspace production mode

This order minimizes the chance of shipping a generic chat shell before the epistemic controls are in place.

## 9. Definition of Done

The dialogue layer is considered ready for the first production-grade iteration only if:

- it is graph-first;
- BM25 is supplementary only;
- every answer is workspace-scoped;
- every answer is bound to workspace version;
- citations point to typed claims for answer-grade assertions;
- clarification updates are routed outside ordinary retrieval;
- response validation can block unlawful promotion.

## 10. Summary

The correct implementation path is:

- build retrieval on top of the existing case model;
- add text retrieval only as a supporting layer;
- keep classification, retrieval, generation, validation, and model update as separate responsibilities;
- ship dialogue as an auditable analytical interface, not as generic chat.
