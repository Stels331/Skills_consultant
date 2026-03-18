---
id: case_20260318_001__layer_2_requirements
artifact_type: requirements_layer
stage: layers
state: draft
parent_refs: ["intake/normalized_case.md"]
source_refs: ["intake/normalized_case.md:L1"]
evidence_refs: []
viewpoints: []
epistemic_status: observed
assurance_level: medium
valid_until: 2026-12-31
owner_role: analyst
gate_status: pending
violated_principles: []
next_expected_artifacts: ["viewpoints/strategist.md"]
created_at: 2026-03-18T12:16:38.525262+00:00
updated_at: 2026-03-18T12:16:38.525262+00:00
---
```markdown
---
id: case_20260318_001__layer_2_requirements
artifact_type: layer_model
stage: analysis
layer: 2_requirements
workspace_id: case_20260318_001
---

# Layer 2: Requirements Model

## 1. Business Requirements (BR)
*   **BR-01: Reduce Estimation Lead Time:** The business must significantly reduce the time required to estimate order feasibility, volume, price, and terms (currently delayed by 7–10 days) [Source: Технический директор_input.md].
*   **BR-02: Improve Client Retention:** The business must eliminate client churn and reputation damage caused by delayed responses to manufacturing requests [Source: Технический директор_input.md].
*   **BR-03: Optimize Resource Allocation:** The business must reduce the operational bottleneck on the Technical Director to ensure production, supply, and equipment setup are not compromised [Source: Технический директор_input.md].

## 2. User Requirements (UR)
*   **UR-01 (Sales Manager):** Requires timely and accurate order estimates to successfully negotiate contracts and launch production without losing the client's interest [Source: Технический директор_input.md].
*   **UR-02 (Technical Director):** Requires a reduction in time spent evaluating non-converting requests ("Значна частина таких оцінок не переходить у реальні замовлення") to focus on primary production duties [Source: Технический директор_input.md].

## 3. Process & Functional Requirements (PR/FR)
*   **PR-01: Request Pre-qualification:** The sales process must include a mechanism to filter or pre-qualify requests before routing them to the Technical Director to minimize wasted estimation effort.
*   **PR-02: SLA Enforcement:** The process must enforce a Service Level Agreement (SLA) for order estimations to prevent requests from being ignored or delayed indefinitely.
*   **PR-03: KPI Alignment:** The performance evaluation system must align the Technical Director's KPIs (currently focused only on production volume and quality) with their mandated responsibilities in the sales estimation process [Source: Технический директор_input.md].

## 4. Constraints & Business Rules (CR)
*   **CR-01: Regulatory Constraint:** Internal standards, regulations, and job descriptions explicitly mandate that the Technical Director must participate in contract preparation and order estimation [Source: Технический директор_input.md].
*   **CR-02: KPI Constraint:** The Technical Director's current KPIs are strictly tied to production volume and product quality, creating a conflict of interest with sales estimation tasks [Source: Технический директор_input.md].

## 5. Identified Gaps (GAP)
*   **GAP-01:** The target acceptable SLA (Service Level Agreement) for order estimation is not defined (e.g., 24 hours, 48 hours).
*   **GAP-02:** There is no data on the ratio of standard vs. custom orders, which is necessary to determine if estimations can be standardized/automated without the Technical Director.
*   **GAP-03:** The exact reasons for low conversion rates are not quantified (e.g., what percentage fails due to the 7-10 day delay vs. uncompetitive pricing/terms).
```
