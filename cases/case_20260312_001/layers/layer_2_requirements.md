---
id: case_20260312_001__layer_2_requirements
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
created_at: 2026-03-12T10:11:31.551140+00:00
updated_at: 2026-03-12T10:11:31.551140+00:00
---
```markdown
---
id: layer_2_requirements
artifact_type: layer_model
stage: analysis
layer: 2
name: Requirements Model
---

# Layer 2: Requirements Model

## 1. Stakeholder Requirements

*   **REQ-SH-01 (Sales Manager):** Requires prompt receipt of order evaluations (feasibility, volume, price, timeline) to negotiate contracts and close deals with clients. 
    *   *Traceability:* `["Технічний директор має оцінити замовлення... після чого повернути оцінку менеджеру"]`
*   **REQ-SH-02 (Technical Director):** Requires minimization of time spent on evaluating non-converting sales requests to focus on primary operational duties and KPIs (production volume, quality, equipment setup).
    *   *Traceability:* `["Технічний директор часто висловлює невдоволення... завантажений виробництвом", "у техничного директора в KPI показники повязані з обсягу виробництва"]`
*   **REQ-SH-03 (Clients):** Require timely responses to manufacturing requests to proceed with orders.
    *   *Traceability:* `["відповіді клієнту надаються із затримкою 7–10 днів", "Через затримки клієнти незадоволені"]`

## 2. Process & Functional Requirements

*   **REQ-PR-01 (Evaluation Scope):** The evaluation process must determine order feasibility, production volumes, pricing, and delivery timelines.
    *   *Traceability:* `["оцінити замовлення: виконуваність, обсяги, ціну та терміни"]`
*   **REQ-PR-02 (Lead Time Reduction):** The process must significantly reduce the turnaround time for order evaluations from the current 7-10 days to prevent client churn.
    *   *Traceability:* `["відповіді клієнту надаються із затримкою 7–10 днів", "частина з них переходить до конкурентів"]`
*   **REQ-PR-03 (Waste Reduction):** The process must efficiently handle requests that have a low probability of conversion without overloading key production personnel.
    *   *Traceability:* `["Значна частина таких оцінок не переходить у реальні замовлення"]`

## 3. Constraints

*   **CON-01 (Regulatory/Organizational):** Current internal standards, regulations, and job descriptions explicitly mandate the Technical Director's participation in contract preparation and order evaluation. Any process change must address this documentation.
    *   *Traceability:* `["існує внутрішній стандарт/регламент, а також відповідні положення в посадовій інструкції, де зазначено, що технічний директор бере участь"]`
*   **CON-02 (KPI Misalignment):** The Technical Director's KPIs are strictly tied to production volume and quality, creating a structural conflict with the requirement to spend time on sales evaluations.
    *   *Traceability:* `["у техничного директора в KPI показники повязані з обсягу виробництва та якості продукції"]`

## 4. Gaps (Missing Information)

*   **GAP-01 (Target SLA):** The acceptable target time (SLA) for processing an order evaluation is not defined (it is only stated that 7-10 days is unacceptable).
*   **GAP-02 (Order Complexity):** There is no data on the ratio of standard vs. custom orders. It is unclear if a portion of these requests could be standardized and evaluated without the Technical Director's deep expertise.
*   **GAP-03 (Evaluation Tooling):** The current tools, formulas, or data sources used by the Technical Director to calculate price, volume, and timelines are not specified.
*   **GAP-04 (Conversion Rate):** The exact conversion rate of evaluated requests to actual orders is unknown ("Значна частина" is not quantified).
```
