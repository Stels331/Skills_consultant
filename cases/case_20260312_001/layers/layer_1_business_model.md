---
id: case_20260312_001__layer_1_business_model
artifact_type: business_model_layer
stage: layers
state: rework_required
parent_refs: ["intake/normalized_case.md"]
source_refs: ["intake/normalized_case.md:L1"]
evidence_refs: []
viewpoints: []
epistemic_status: inferred
assurance_level: medium
valid_until: 2026-12-31
owner_role: analyst
gate_status: block
violated_principles: []
next_expected_artifacts: ["viewpoints/strategist.md"]
created_at: 2026-03-12T10:11:11.261684+00:00
updated_at: 2026-03-12T10:28:00.142362+00:00
---
```markdown
---
id: layer_1_business_model
artifact_type: layer_model
stage: analysis
state: draft
parent_refs: ["case_20260312_001__normalized_case"]
source_refs: ["raw/Технический директор_input.md"]
---

# Layer 1: Business Model

## 1. Business Context
*   **Organization Type:** Small manufacturing company.
*   **Core Activity:** Custom production based on client requests, requiring upfront estimation of feasibility, volume, price, and deadlines.
*   **Traceability:** *"Кейс: невелика виробнича компанія"* [Source: Технический директор_input.md]

## 2. Key Actors & Stakeholders
*   **Client (Клієнт):** Submits requests for production; makes the final decision based on price and deadlines.
*   **Sales Manager (Менеджер із продажів):** Responsible for finding clients, receiving requests, negotiating contracts, and launching orders into production.
*   **Technical Director (Технічний директор):** Responsible for production, urgent tasks, supply, and equipment setup. Also tasked with estimating incoming sales requests.

## 3. As-Is Business Process (Sales & Estimation)
1.  **Request Intake:** Sales Manager finds a client and accepts a production request.
2.  **Handoff for Estimation:** Sales Manager transfers the request to the Technical Director.
3.  **Estimation:** Technical Director evaluates the order for feasibility, work volume, price, and deadlines.
4.  **Return Estimate:** Technical Director sends the evaluation back to the Sales Manager.
5.  **Negotiation:** Sales Manager negotiates the contract with the Client based on the provided estimate.
6.  **Production Launch:** If agreed, the order is launched into production.
*   **Traceability:** *"Процес продажів включає підпроцес оцінювання... Менеджер із продажів знаходить клієнта... передає заявку технічному директору..."* [Source: Технический директор_input.md]

## 4. Business Problems & Pain Points
*   **Process Bottleneck & Delays:** The Technical Director is overloaded with operational tasks (production, supply, equipment). Consequently, estimates are delayed by 7–10 days, and some requests are completely ignored.
*   **Low Conversion Rate:** A significant portion of estimates do not convert into real orders because clients reject the price, deadlines, or other conditions.
*   **KPI Misalignment:** The Technical Director's KPIs are tied strictly to production volume and product quality. However, internal regulations and job descriptions mandate their participation in order estimation, creating a conflict of priorities.
*   **Business Impact:** Delays lead to client dissatisfaction, loss of clients to competitors, and deterioration of the company's reputation.
*   **Traceability:** *"відповіді клієнту надаються із затримкою 7–10 днів... у техничного директора в KPI показники повязані з обсягу виробництва та якості... клієнти незадоволені, частина з них переходить до конкурентів"* [Source: Технический директор_input.md]

## 5. Identified Gaps (GAP)
*   **GAP 01 (Metrics):** No data provided on the actual volume of incoming requests (e.g., per week/month) or the exact conversion rate from request to signed contract.
*   **GAP 02 (Estimation Methodology):** It is unknown how the Technical Director calculates feasibility, price, and time. There is no information on whether this logic is documented, standardized, or relies entirely on tacit expert knowledge.
*   **GAP 03 (Tooling):** No information on the current IT systems or tools used for tracking requests, communicating between Sales and the Technical Director, or calculating estimates.
*   **GAP 04 (Sales KPIs):** No information provided regarding the Sales Manager's KPIs and how the 7-10 day delay impacts their performance metrics.
```
