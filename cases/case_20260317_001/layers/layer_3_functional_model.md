---
id: case_20260317_001__layer_3_functional_model
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
created_at: 2026-03-17T18:46:09.301978+00:00
updated_at: 2026-03-17T18:46:09.301978+00:00
---
```yaml
---
id: layer_3_functional_model
artifact_type: layer_model
stage: analysis
state: draft
parent_refs:
  - case_20260317_001__normalized_case
source_refs:
  - "raw/Технический директор_input.md"
viewpoints:
  - functional_architecture
  - process_flow
epistemic_status: inferred
assurance_level: medium
valid_until: 2026-12-31
owner_role: analyst
---
```

# Layer 3: Functional Model

## 1. Functional Architecture & Processes

### 1.1. Sales & Order Processing
*   **Request Intake:** Receiving initial manufacturing requests from clients. Performed by Sales Manager. [Source: `Менеджер із продажів знаходить клієнта та приймає від нього заявку`]
*   **Order Estimation:** Evaluating the request for feasibility, production volume, pricing, and deadlines. Currently performed by the Technical Director (TD). [Source: `Технічний директор має оцінити замовлення: виконуваність, обсяги, ціну та терміни`]
*   **Contract Negotiation & Launch:** Agreeing on terms with the client based on the estimate and initiating production. Performed by Sales Manager. [Source: `менеджер погоджує з клієнтом договір і запускає замовлення у виробництво`]

### 1.2. Production & Operations
*   **Production Management:** Core operational function managing manufacturing output and quality. Performed by TD. [Source: `завантажений виробництвом... показники повязані з обсягу виробництва та якості продукції`]
*   **Supply Management:** Managing procurement and supply chains. Performed by TD. [Source: `постачанням`]
*   **Equipment Maintenance:** Configuring and maintaining manufacturing equipment. Performed by TD. [Source: `налаштуванням обладнання`]

## 2. Information Flows
1.  **Client Request Flow:** Client $\rightarrow$ Sales Manager $\rightarrow$ Technical Director.
2.  **Estimation Flow:** Technical Director $\rightarrow$ Estimate Data (Feasibility, Volume, Price, Time) $\rightarrow$ Sales Manager.
3.  **Contract Flow:** Sales Manager $\rightarrow$ Contract Proposal $\rightarrow$ Client $\rightarrow$ Approval/Rejection.
4.  **Production Trigger:** Sales Manager $\rightarrow$ Approved Order $\rightarrow$ Production.

## 3. Functional Bottlenecks & Conflicts
*   **Resource Contention:** The "Order Estimation" function competes directly for resources with "Production Management", "Supply Management", and "Equipment Maintenance" functions, as all are routed through a single node (the Technical Director). [Source: `він завантажений виробництвом, терміновими задачами, постачанням, налаштуванням обладнання`]
*   **High Waste Processing:** The estimation function processes a high volume of requests that do not convert into the "Contract Launch" function, resulting in wasted functional capacity of the TD. [Source: `Значна частина таких оцінок не переходить у реальні замовлення`]
*   **Latency:** The functional overload at the estimation node introduces a severe latency of 7–10 days, degrading the overall performance of the Sales process. [Source: `відповіді клієнту надаються із затримкою 7–10 днів`]

## 4. GAPs (Missing Functions & Capabilities)
*   **GAP [Pre-qualification Function]:** There is no functional step for filtering, pre-qualifying, or rough-estimating requests before they consume the high-value technical estimation resources.
*   **GAP [Standardized Estimation Capability]:** There is no mention of automated or standardized estimation tools/models that would allow Sales Managers to perform basic pricing and deadline estimations independently.
*   **GAP [Feedback Loop]:** There is no functional mechanism to analyze why estimates are rejected (e.g., price too high, deadlines too long) to optimize future estimations or filter out incompatible clients earlier in the process.
