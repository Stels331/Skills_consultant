---
id: case_20260318_001__layer_1_business_model
artifact_type: business_model_layer
stage: layers
state: shaped
parent_refs: ["intake/normalized_case.md"]
source_refs: ["intake/normalized_case.md:L1"]
evidence_refs: []
viewpoints: []
epistemic_status: inferred
assurance_level: medium
valid_until: 2026-12-31
owner_role: analyst
gate_status: pass
violated_principles: []
next_expected_artifacts: ["viewpoints/strategist.md"]
created_at: 2026-03-18T12:16:20.397102+00:00
updated_at: 2026-03-18T12:32:03.035311+00:00
---
```markdown
---
id: layer_1_business_model__case_20260318_001
artifact_type: layer_1_business_model
stage: analysis
state: draft
parent_refs: ["case_20260318_001__normalized_case"]
source_refs: ["raw/Технический директор_input.md"]
---

# Layer 1: Business Model

## 1. Business Context
*   **Organization Type:** Small manufacturing company [Source: Технический директор_input.md].
*   **Core Activity:** Custom manufacturing based on client requests, requiring upfront estimation of feasibility, volume, price, and deadlines.

## 2. Actors and Roles
*   **Client (Клієнт):** Submits requests for manufacturing, negotiates contracts, and accepts or rejects estimates.
*   **Sales Manager (Менеджер із продажів):** Finds clients, receives requests, acts as an intermediary for estimates, negotiates contracts, and launches orders into production.
*   **Technical Director (Технічний директор):** Responsible for production, urgent tasks, supply, and equipment setup. Also tasked with evaluating client requests (feasibility, volume, price, time).

## 3. Business Process: Sales & Order Estimation (As-Is)
1.  **Request Intake:** Sales Manager finds a client and receives a manufacturing request.
2.  **Handoff for Estimation:** Sales Manager passes the request to the Technical Director.
3.  **Estimation:** Technical Director evaluates the order for feasibility, work volume, price, and deadlines.
4.  **Return Estimate:** Technical Director returns the evaluation to the Sales Manager.
5.  **Negotiation & Launch:** Sales Manager negotiates the contract with the Client based on the estimate. If agreed, the order is launched into production. If not (due to price, time, or other conditions), the order is cancelled.

## 4. Business Rules & KPIs
*   **Technical Director KPIs:** Tied strictly to production volume and product quality [Source: Технический директор_input.md].
*   **Internal Regulations:** Internal standards and the Technical Director's job description explicitly mandate their participation in contract preparation and order estimation [Source: Технический директор_input.md].
*   **Conflict of Interest:** The Technical Director's KPIs (production focus) conflict with their regulatory duties (sales estimation focus).

## 5. Pain Points & Consequences
*   **Low Conversion:** A significant portion of estimates do not convert into real orders because clients reject the price, deadlines, or conditions.
*   **Resource Bottleneck:** The Technical Director is overloaded with operational production tasks, causing frustration and deprioritization of estimates.
*   **Severe Delays:** Responses to clients are delayed by 7–10 days, and some requests are completely ignored.
*   **Business Impact:** Client dissatisfaction, loss of clients to competitors, and deterioration of the company's reputation.

## 6. Identified Gaps (GAP)
*   **GAP 1 (Metrics):** Missing data on the exact volume of incoming requests per week/month.
*   **GAP 2 (Metrics):** Missing the current conversion rate from request to signed contract.
*   **GAP 3 (Financials):** Missing the financial impact (lost revenue) caused by the 7-10 day delays and abandoned requests.
*   **GAP 4 (Process):** Missing details on the tools or methodologies the Technical Director currently uses to calculate price and deadlines (e.g., Excel, ERP, manual calculation).
*   **GAP 5 (Process):** Missing information on whether the Sales Manager does any preliminary filtering or qualification of leads before passing them to the Technical Director.
```
