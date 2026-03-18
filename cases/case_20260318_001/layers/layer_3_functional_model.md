---
id: case_20260318_001__layer_3_functional_model
artifact_type: functional_model_layer
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
created_at: 2026-03-18T12:16:59.927163+00:00
updated_at: 2026-03-18T12:16:59.927163+00:00
---
# Layer 3: Functional Model

## 1. Functional Architecture (Processes & Sub-processes)
*   **Sales Process** `[Source: raw/Технический директор_input.md]`
    *   **Client Intake:** Sourcing clients and receiving initial requests for production.
    *   **Contract Negotiation:** Agreeing on terms with the client based on the provided estimate.
    *   **Production Launch:** Releasing the finalized order into the manufacturing pipeline.
*   **Estimation Sub-process** `[Source: raw/Технический директор_input.md]`
    *   **Feasibility Assessment:** Evaluating if the requested product can be manufactured.
    *   **Volume & Cost Calculation:** Determining the scope of work and pricing.
    *   **Scheduling:** Estimating lead times and production deadlines.
*   **Production & Operations Process** `[Source: raw/Технический директор_input.md]`
    *   **Production Management:** Overseeing manufacturing to meet volume and quality KPIs.
    *   **Supply Chain Management:** Handling procurement and material supply.
    *   **Equipment Maintenance:** Setting up and maintaining manufacturing equipment.
    *   **Urgent Issue Resolution:** Handling day-to-day operational emergencies.

## 2. Functional Roles
*   **Sales Manager:** Executes the Sales Process (Intake, Negotiation, Launch). Acts as the primary interface between the Client and the internal Estimation function.
*   **Technical Director:** Executes both the Estimation Sub-process and the Production & Operations Process. Acts as the sole bottleneck for technical and financial order evaluation.

## 3. Information & Control Flows
*   **Flow 1 (Request Intake):** Client -> `Production Request` -> Sales Manager.
*   **Flow 2 (Estimation Request):** Sales Manager -> `Production Request` -> Technical Director.
*   **Flow 3 (Estimation Delivery):** Technical Director -> `Order Estimate (Feasibility, Volume, Price, Deadlines)` -> Sales Manager. *(Note: Currently experiencing a 7-10 day latency or complete failure to deliver).*
*   **Flow 4 (Contracting & Launch):** Sales Manager -> `Contract Terms` -> Client -> `Approved Order` -> Production.

## 4. Identified Gaps (GAP)
*   **GAP [Pre-qualification]:** There is no triage or pre-qualification function to filter out low-probability requests before they consume the Technical Director's time.
*   **GAP [Estimation Tooling]:** The functional mechanisms, algorithms, or tools used to generate the estimates (price, volume, deadlines) are completely undefined. It is unclear if this requires specialized engineering knowledge or just standard pricing matrices.
*   **GAP [Feedback Loop]:** There is no function to capture and analyze the reasons for client rejections (e.g., price too high, deadlines too long) to improve future estimations.
*   **GAP [Delegation/Routing]:** There is no alternative routing or delegation function for estimations when the Technical Director is unavailable or overloaded with operational tasks.
