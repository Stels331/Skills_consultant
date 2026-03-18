---
id: case_20260317_001__layer_1_business_model
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
created_at: 2026-03-17T18:45:26.502518+00:00
updated_at: 2026-03-17T19:00:07.290140+00:00
---
```markdown
---
id: layer_1_business_model
artifact_type: layer_model
stage: analysis
state: draft
parent_refs: ["case_20260317_001__normalized_case"]
source_refs: ["raw/Технический директор_input.md"]
---

# Layer 1: Business Model

## 1.1 Business Context
*   **Organization Type:** Small manufacturing company (*"невелика виробнича компанія"*).
*   **Core Domain:** Manufacturing, Sales, and Pre-sales estimation.

## 1.2 Business Actors & Roles
*   **Client (*Клієнт*):** Submits requests for production, negotiates terms, and makes the final decision to proceed or cancel.
*   **Sales Manager (*Менеджер із продажів*):** Finds clients, receives requests, acts as an intermediary for estimation, negotiates contracts, and launches orders into production.
*   **Technical Director (*Технічний директор*):** Responsible for production operations (supply, equipment setup, urgent tasks) and is currently tasked with estimating the feasibility, scope, price, and deadlines of incoming sales requests.

## 1.3 Business Processes
**Process: Sales & Order Estimation**
1.  Sales Manager finds a client and receives a production request.
2.  Sales Manager passes the request to the Technical Director.
3.  Technical Director evaluates the order (feasibility, scope, price, deadlines).
4.  Technical Director returns the estimation to the Sales Manager.
5.  Sales Manager negotiates the contract with the Client based on the estimation.
6.  If agreed, the Sales Manager launches the order into production.
*(Source: "Процес продажів включає підпроцес оцінювання...")*

## 1.4 Business Problems & Pain Points
*   **Process Bottleneck:** The Technical Director is overloaded with core operational tasks (production, supply, equipment setup), causing a conflict of priorities.
*   **Severe Delays:** Client responses are delayed by 7–10 days. Some requests are completely ignored/unprocessed by the Technical Director.
*   **Low Conversion Rate:** A significant portion of estimations do not convert into real orders because clients reject the price, deadlines, or other conditions.
*   **Business Impact:** Client dissatisfaction, loss of clients to competitors, and deterioration of the company's reputation.

## 1.5 Business Goals & Metrics (KPIs)
*   **Technical Director KPIs:** Tied strictly to production volume (*обсяг виробництва*) and product quality (*якість продукції*). Note: These KPIs do not align with the pre-sales estimation duties, creating a motivational conflict.
*   **Implicit Business Goals:** Reduce estimation turnaround time, improve client retention, and protect company reputation.

## 1.6 Business Rules & Policies
*   **Regulatory Constraint:** Internal company standards/regulations and the Technical Director's job description explicitly mandate their participation in contract preparation and order estimation. *(Source: "існує внутрішній стандарт/регламент, а також відповідні положення в посадовій інструкції...")*

## 1.7 Identified Gaps (GAP)
*   **GAP 1 (Metrics):** The exact current conversion rate of requests to orders is unknown, as is the target acceptable conversion rate.
*   **GAP 2 (SLAs):** The target acceptable response time (SLA) for providing an estimate to the client is not defined (currently 7-10 days, but what is the goal?).
*   **GAP 3 (Tooling):** It is unknown what tools, software, or data the Technical Director currently uses to calculate feasibility, scope, price, and deadlines.
*   **GAP 4 (Organizational):** It is unclear if the company is open to changing the internal regulations/job descriptions to delegate the estimation task to a dedicated role (e.g., an Estimator or Pre-sales Engineer) to resolve the KPI conflict.
```
