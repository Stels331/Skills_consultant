# Dialogue Retrieval Architecture

## 1. Purpose

Define the target retrieval architecture for the future dialogue layer so that:

- answers are grounded in the case model, not in free-text guessing;
- retrieval remains isolated per workspace;
- freshness is preserved after re-entry and model updates;
- FPF epistemic discipline is preserved in every answer.

This document is a working architecture note for the dialogue layer, not yet an implementation spec.

## 2. Core Principles

The dialogue retrieval layer must satisfy four non-negotiable requirements:

1. `epistemic typing`
   Every primary grounding unit must preserve whether it is:
   - `source_fact`
   - `derived_metric`
   - `decision_constraint`
   - `normative_target`
   - `interpretation`
   - `hypothesis`
   - other graph-native types

2. `workspace isolation`
   Retrieval must be scoped strictly to one `workspace_id`.
   No cross-case retrieval is permitted.

3. `freshness`
   After clarification, re-entry, or model update, stale grounding must not be reused.

4. `graph-first reasoning`
   The dialogue layer must reason over the structured case model first.
   Text retrieval is supplementary and must never silently replace typed claims.

## 3. High-Level Flow

```text
User question
    |
    v
QuestionRouter.classify()
    -> constraint_query
    -> problem_query
    -> solution_query
    -> report_query
    -> evidence_query
    -> clarification_needed
    |
    +--> clarification_needed -> ModelUpdateEngine
    |
    v
typed_graph_retrieval()          <- always primary
    |
    +--> enough typed claims -> proceed
    |
    +--> too few typed claims -> optional BM25 supplementary retrieval
    |
    v
GroundingBundle
    |
    v
FPF-structured prompt
    |
    v
LLM response
    |
    v
FPFResponseValidator
    |
    v
GroundedAnswer
```

## 4. Question Router

`QuestionRouter` is a dedicated classification layer and must not be merged into retrieval.

Its job is to classify the user question into one of:

- `constraint_query`
- `problem_query`
- `solution_query`
- `report_query`
- `evidence_query`
- `clarification_needed`

### 4.1 Clarification Is Not Retrieval

If the user message is actually a case update or a clarification, the system must not run retrieval first.

Examples:

- "what if budget is 500k?"
- "assume diesel cost grows by 20%"
- "we can move the deadline by one month"

Such inputs must be routed to `ModelUpdateEngine` / `question_queue`, not to `DialogueRetriever`.

### 4.2 Router Fallback

Router misclassification is a system risk.
If router confidence is low, the fallback policy should prefer:

- `evidence_query`, or
- `clarification_needed`

over an overly narrow domain class.

## 5. Primary Retrieval: Typed Graph Retrieval

The primary dialogue retrieval mechanism must read from the current epistemic graph.

This is the preferred layer because it is:

- typed;
- traceable;
- workspace-scoped;
- naturally refreshed after re-entry.

### 5.1 Dialogue Projection

Add a dialogue-oriented projection type, for example:

```python
def build_dialogue_projection(
    workspace_path: Path,
    question_class: str,
    top_k: int = 20,
) -> DialogueProjection:
    ...
```

This is not vector search.
It is a structured query over graph nodes and edges based on `question_class`.

### 5.2 Examples

`constraint_query`
- retrieve `decision_constraint`
- plus `DERIVED_FROM` support chain
- plus supporting `source_fact`

`problem_query`
- retrieve selected problem nodes
- plus supporting interpretations
- plus hypotheses to validate

`solution_query`
- retrieve solution-related nodes
- plus lawful constraints
- plus rejection rationale / conflict rationale

`evidence_query`
- retrieve evidence-bearing claims and their source lineage

## 6. Secondary Retrieval: BM25 Over Workspace Sections

If typed retrieval returns too little context, the system may use BM25 as a supplementary layer.

This layer is for artifact text, not for primary reasoning.

### 6.1 Unit of Indexing

Do not index whole markdown files as single documents.

Index by section:

```python
@dataclass
class SectionDoc:
    workspace_id: str
    artifact_rel: str
    artifact_type: str
    section_title: str
    section_body: str
    epistemic_status: str
    stage: str
    source_refs: list[str]
```

This preserves structural context and prevents epistemically different sections from being mixed into one retrieval unit.

### 6.2 Why BM25

BM25 is preferred here over pgvector or PageIndex for the first implementation because:

- no embedding dependency;
- no model-specific indexing cost;
- fast workspace rebuild after re-entry;
- good fit for structured markdown artifacts with strong headings.

## 7. Retrieval Policy

The policy must be strict:

- typed graph retrieval is always primary;
- BM25 is supplementary only;
- BM25 must never silently replace typed graph retrieval;
- text fragments must not be treated as claim-grade evidence unless separately bound to claims.

### 7.1 Zero Typed Claims Rule

If typed graph retrieval returns `0` relevant claims:

- do not answer from BM25 alone;
- return one of:
  - `needs_clarification`
  - `out_of_scope_for_model`
  - `insufficient_modeled_evidence`

BM25 may be used only when typed claims exist but need textual context expansion.

## 8. Grounding Bundle

The dialogue layer should pass a structured grounding object into generation.

```python
@dataclass
class GroundingBundle:
    typed_claims: list[dict]
    text_fragments: list[SectionDoc]
    workspace_id: str
    graph_version: str
    workspace_version: int
```

### 8.1 Trust Hierarchy

`typed_claims`
- primary
- epistemically typed
- traceable
- claim-grade grounding

`text_fragments`
- secondary
- supplementary only
- not claim-grade by default

### 8.2 Prompt Structure

The prompt must explicitly separate them:

```text
VERIFIED CLAIMS (from epistemic graph):
  [decision_constraint, status=observed] ...
  [hypothesis, status=hypothesis] ...

SUPPORTING TEXT (from workspace artifacts, supplementary only):
  CharacterizationPassport / ## hard_constraints
  ...
```

This separation is necessary so the model does not silently promote text fragments to fact-grade evidence.

## 9. Versioning and Freshness

Timestamp alone is not sufficient.

The dialogue system must track:

- `graph_version`
- `workspace_version`

Every generated dialogue answer must store the workspace version used at generation time.

This allows the system to say:

- this answer was generated before the latest clarification;
- this answer is based on workspace version `N`.

This must later map to:

- `workspace_versions`
- `dialogue_messages.workspace_version_id`

## 10. FPF-Aware Answer Generation

The model must receive structured epistemic rules with the grounding:

- do not present `hypothesis` as fact;
- do not use information outside the grounding bundle;
- if evidence is insufficient, return `needs_clarification`;
- do not promote supplementary text into primary evidence.

## 11. FPF Response Validation

After generation, a dedicated response validator must verify:

- citations reference typed claims for answer-grade assertions;
- text fragments are used only as supplementary context;
- no unlawful promotion from `hypothesis` to `observed/fact`;
- no workspace leakage occurred.

## 12. Role of PageIndex

`PageIndex` is not the primary retrieval architecture for this project.

It may still be useful for one narrow case:

- user uploads a large raw source document;
- the user asks document-level questions before the case pipeline has produced typed claims.

That is an intake-level helper, not the main dialogue retrieval substrate.

## 13. Implementation Direction

Recommended implementation order:

1. `QuestionRouter`
2. `dialogue_projection` in graph/projection layer
3. `SectionDoc` extraction and BM25 indexer
4. `GroundingBundle`
5. `FPF-structured prompt builder`
6. `FPFResponseValidator`
7. `workspace_version` binding in dialogue messages

## 14. Summary

The correct architecture for this project is:

- `graph-first`
- `workspace-scoped`
- `version-aware`
- `FPF-aware`
- `BM25 supplementary only`

This keeps dialogue aligned with the existing epistemic model instead of degrading into generic document RAG.
