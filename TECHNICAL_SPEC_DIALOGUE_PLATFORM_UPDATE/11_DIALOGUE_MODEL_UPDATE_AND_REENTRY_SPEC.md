# Dialogue Model Update And Re-entry Spec

## 1. Purpose

This document defines how the dialogue layer must behave when the user provides missing or updated case information during conversation.

Goal:

- treat user-provided clarifications as controlled model updates, not as plain chat text;
- preserve FPF lawful promotion rules;
- trigger only the necessary recalculation scope;
- keep dialogue honest while async re-entry is still running.

## 2. Core Rule

If the user provides new case information, the system must decide first:

- is this a normal question, or
- is this a model update / clarification input?

This decision must happen before retrieval.

## 3. Entry Decision

The first dialogue decision is:

```text
QuestionRouter.classify()
    -> ordinary question classes
    -> clarification_provided
```

If the result is `clarification_provided`, the system must not enter ordinary retrieval flow.
It must enter `ModelUpdateEngine`.

## 4. Controlled Update Pipeline

The update path must follow this sequence:

```text
classify input
    ->
input_acceptance_check
    ->
write to graph
    ->
plan re-entry
    ->
run partial async re-entry
    ->
publish new workspace version
```

This sequence prevents raw user statements from bypassing epistemic controls.

## 5. Input Classification

### 5.1 Typed Input Classifier

User input must first be classified into a provisional type.

Possible user-origin input types:

- `user_asserted_fact`
- `user_declared_constraint`
- `user_hypothesis`
- `user_normative_target`

These are not yet equivalent to final graph-native production types.

### 5.2 Why Intermediate User Types Are Required

The system must preserve the distinction between:

- what the user asserted;
- what the system accepted as lawful, typed case knowledge.

Without this distinction, user input would bypass lawful promotion through a hidden shortcut.

## 6. Input Acceptance Check

The result of `typed_input_classifier` must not be trusted immediately.

The system must perform `input_acceptance_check` before writing anything to the graph.

### 6.1 Required Checks

`input_acceptance_check` should verify:

- the message is not actually a question disguised as a statement;
- the message is not conditional in a way that invalidates fact-grade treatment;
- the message does not directly contradict stable existing claims without escalation;
- the message is concrete enough to become a typed node;
- the message can be attached to a lawful epistemic category.

### 6.2 Examples

This must not become `source_fact`:

```text
if budget is 800k then we can consider sol_03
```

This is conditional and must remain hypothesis-grade unless further accepted and confirmed.

### 6.3 Failure Handling

If acceptance fails:

- do not write to graph;
- return a clarification request to the user;
- preserve audit trail that input was rejected or deferred.

## 7. Writing To Graph

Only accepted inputs are written to the graph.

The initial write should use the intermediate user-origin type.

Examples:

- `user_asserted_fact`
- `user_declared_constraint`
- `user_hypothesis`

The graph write must include provenance such as:

- actor: `user`
- source kind: `dialogue_clarification`
- timestamp
- workspace version context

## 8. Lawful Promotion Of User Inputs

Intermediate user-origin types may later be promoted.

Examples:

- `user_asserted_fact -> source_fact`
- `user_declared_constraint -> decision_constraint`
- `user_hypothesis -> confirmed_assumption`

Only lawful validation or support-chain confirmation may trigger these promotions.

### 8.1 Ledger Examples

The ledger should show:

```text
claim_created: user_asserted_fact
claim_promoted: user_asserted_fact -> source_fact
```

This is superior to writing a final `source_fact` immediately with no visible validation path.

## 9. Re-entry Planning

After graph write, the system must calculate affected recomputation scope.

### 9.1 No Hardcoded Stage Mapping

Re-entry planning must not rely only on:

```python
if node_type == decision_constraint -> stages = ...
```

That approach is too brittle.

### 9.2 Artifact Lineage Traversal

Re-entry must be planned through actual dependencies:

1. find dependent projections that use the updated node;
2. find stages that depend on those projections;
3. find materialized outputs now stale because of those stages.

Illustrative form:

```python
def plan_reentry(updated_node, graph, projection_registry, materialized_artifacts):
    dependent_projections = projection_registry.find_by_node(node_id=updated_node.id)
    affected_stages = []
    for projection in dependent_projections:
        affected_stages.extend(
            materialized_artifacts.find_stages_using(
                projection_type=projection.projection_type
            )
        )
    stale_outputs = materialized_artifacts.find_outputs_for(
        stages=affected_stages
    )
    ...
```

### 9.3 Reentry Plan Contents

`ReentryPlan` should contain:

- `trigger_node`
- `dependent_projections`
- `affected_stages`
- `stale_outputs`
- `potentially_stale_nodes`

## 10. Async Partial Re-entry

Re-entry must run asynchronously through a worker.

The dialogue layer must not block while recomputation is happening.

Only affected stages should be recomputed.

This is required both for:

- user experience;
- cost control;
- model consistency.

## 11. Version-Aware Dialogue During Re-entry

The system must distinguish between:

- `current_published_version`
- `pending_version`

Suggested state object:

```python
@dataclass
class WorkspaceVersionState:
    current_published_version: int
    pending_version: int | None
    reentry_status: str
    reentry_started_at: datetime | None
    affected_stages: list[str]
```

### 11.1 Dialogue Behavior

If `reentry_status == in_progress`:

- answer using `current_published_version`;
- add explicit disclaimer that recomputation is still underway.

Example:

```text
This answer is based on workspace version 3.
Currently recalculating: solution_factory, reporting.
The answer may change after the update completes.
```

If `reentry_status == idle`:

- answer normally from the current published version;
- no disclaimer needed.

### 11.2 Publish Transition

When worker finishes successfully:

- `pending_version` becomes `current_published_version`;
- updated projections become active;
- user receives update notification.

## 12. Ledger And Diff

User-visible diff should be derived from ledger events between:

- previous published version;
- current published version.

### 12.1 Event Types Relevant To Diff

Required event types:

- `claim_created`
- `claim_updated`
- `claim_promoted`
- `claim_degraded`
- `projection_refreshed`
- `stage_recomputed`

### 12.2 User-Facing Diff

Example:

```text
Model updated to version 4

Added:
  [user_asserted_fact -> source_fact] budget: 800k UAH

Changed:
  assumption "budget sufficient for sol_03" -> confirmed_assumption

Recomputed:
  solution_factory
  reporting

Refreshed projections:
  selection_projection
  reporting_projection
```

This diff should be generated from ledger/event history, not from ad hoc UI state.

## 13. Complete Target Behavior

The intended sequence is:

```text
0. Router decides this is clarification_provided, not ordinary Q&A.
1. User provides missing information.
2. typed_input_classifier -> input_acceptance_check -> graph write
   using intermediate user_* type.
3. Graph and ledger are updated.
4. ReentryPlanner finds dependent projections, affected stages, stale outputs.
5. Async worker runs partial re-entry.
6. Dialogue continues against current_published_version
   with disclaimer if re-entry is still in progress.
7. When re-entry completes, pending version is published
   and user sees a version diff.
```

## 14. Required Components

To support this behavior, the architecture must include:

- `typed_input_classifier`
- `input_acceptance_check`
- `ModelUpdateEngine`
- `ReentryPlanner`
- async re-entry worker
- version state tracking
- ledger-based diff generator

## 15. Summary

The correct behavior is:

- user clarification updates the model;
- update first enters the graph in a controlled intermediate user-origin form;
- only affected reasoning layers are recomputed;
- dialogue remains version-aware while recomputation is pending;
- the user sees exactly what changed after the new version is published.
