# Decision Assurance And Refresh Spec

## 1. Purpose

This document defines how `Electronic Consultant v3` must evaluate the reliability of decisions and detect when a previously acceptable recommendation has become weak, stale or review-required.

Goal:

- make decision quality depend on evidence quality, freshness and consistency;
- identify weakest links instead of hiding low-quality support behind a single averaged score;
- surface review triggers before outdated recommendations continue to look trustworthy;
- connect stale decision logic to the existing re-entry model.

## 2. Core Rule

The platform must not treat all grounded decisions as equally reliable.

Decision assurance must account for:

- evidence freshness;
- support strength;
- contradictions or unresolved unknowns;
- dependency quality across the decision chain.
- historical outcome signals from prior use or review of similar or linked decisions.

## 3. Assurance Object

Every `DecisionRecord` should have an attached assurance object with at least:

- `assurance_score`
- `assurance_status`
- `weakest_link_ref`
- `decay_penalty`
- `review_required`
- `staleness_flags`
- `historical_outcome_modifier`

## 4. Freshness And Decay

Evidence linked to a decision may age out.

The system should support:

- explicit `valid_until` or equivalent review horizon;
- freshness windows per evidence category;
- automatic decay after expiry or review horizon;
- immediate degradation when critical evidence becomes stale.

The platform must not silently keep a high-confidence recommendation after critical evidence has expired.

## 5. Weakest-Link Principle

Decision assurance must not be a naive average.

If a key dependency is weak, contradictory or stale:

- the entire decision contract must reflect that weakness;
- the weakest supporting node must be visible to the user and to governance logs.

This is especially important for:

- hard constraints;
- regulatory assumptions;
- cost or risk baselines;
- root-cause evidence.

## 6. Congruence And Dependency Penalties

The system should apply additional penalties when:

- linked evidence points in conflicting directions;
- assumptions are unresolved but the decision is presented as firm;
- the comparison model is incomplete;
- multiple critical supports remain hypothesis-grade.

This does not always require a full block.

Possible outcomes:

- `pass`
- `degrade`
- `review_required`
- `block`

Positive or negative historical outcomes may influence assurance, but only as a bounded secondary factor.
Historical outcome signals must never override hard evidence expiry, contradiction or floor policy.

## 7. Review Triggers

Decision review must be triggered by events such as:

- evidence expired;
- critical claim updated;
- supporting projection recomputed with material change;
- contradiction introduced;
- user override or waiver expired;
- re-entry changed assumptions or affected stages.

## 8. Relation To Re-entry

Decision assurance must integrate with the existing re-entry flow.

Examples:

- if a supporting claim changes, the affected `DecisionRecord` should be marked stale before recompute completes;
- during `reentry_status = in_progress`, the user should see that the current published decision may soon change;
- after successful re-entry, the decision contract and assurance must be recalculated.

Decision assurance should also integrate with explicit decision outcomes:

- stable confirmed use can produce a bounded positive modifier;
- repeated retirements, review rejections or re-entry invalidations can produce a bounded negative modifier.

## 9. Waivers And Overrides

The platform may allow controlled waivers, but only explicitly.

Waivers must contain:

- justification;
- actor;
- expiry;
- scope;
- accepted residual risk.

Waivers must never silently erase degraded assurance.

## 10. API Expectations

Decision-facing APIs should eventually expose:

- `assurance_score`
- `assurance_status`
- `weakest_link_ref`
- `review_due`
- `staleness_flags`
- `waiver_active`
- `historical_outcome_summary`
- `historical_outcome_modifier`

This data must be machine-readable.

## 11. Governance Requirements

The ledger should support assurance-related event types:

- `decision_assurance_recomputed`
- `evidence_expired`
- `decision_review_due`
- `decision_downgraded`
- `waiver_applied`
- `waiver_expired`
- `decision_outcome_applied_to_assurance`

## 12. Acceptance Criteria

- decision confidence drops when critical evidence becomes stale;
- the weakest supporting element can be identified for a degraded recommendation;
- review-required decisions are visible before users rely on them blindly;
- re-entry updates decision assurance after model changes;
- historical outcome signals affect ranking and assurance only within explicitly bounded policy limits;
- waivers are explicit, auditable and time-bounded.
