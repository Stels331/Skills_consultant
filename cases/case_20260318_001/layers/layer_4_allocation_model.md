---
id: case_20260318_001__layer_4_allocation_model
artifact_type: allocation_model_layer
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
created_at: 2026-03-18T12:17:19.102387+00:00
updated_at: 2026-03-18T12:17:19.102387+00:00
---
```markdown
---
id: case_20260318_001__layer_4_allocation_model
artifact_type: layer_4_allocation_model
stage: analysis
state: draft
parent_refs:
  - case_20260318_001__normalized_case
source_refs:
  - raw/Технический директор_input.md
---

# Layer 4: Allocation Model

## 1. Actors and Roles
*   **Sales Manager** (*Менеджер із продажів*): Responsible for client-facing activities and order initiation.
*   **Technical Director** (*Технічний директор*): Responsible for production operations and technical estimation of incoming requests.
*   **Client** (*Клієнт*): External actor submitting requests and approving contracts.

## 2. Task-to-Role Allocation
### Sales Manager
*   **Client Acquisition & Intake:** Finds clients and receives production requests. [Source: *Менеджер із продажів знаходить клієнта та приймає від нього заявку...*]
*   **Handoff:** Transfers the request to the Technical Director. [Source: *Далі менеджер передає заявку технічному директору.*]
*   **Negotiation & Launch:** Negotiates the contract with the client based on the estimate and launches the order into production. [Source: *На підставі цієї оцінки менеджер погоджує з клієнтом договір і запускає замовлення у виробництво.*]

### Technical Director
*   **Pre-sales Estimation:** Evaluates order feasibility, scope, price, and deadlines. [Source: *Технічний директор має оцінити замовлення: виконуваність, обсяги, ціну та терміни...*]
*   **Core Operations:** Manages production, urgent tasks, supply/procurement, and equipment setup. [Source: *завантажений виробництвом, терміновими задачами, постачанням, налаштуванням обладнання...*]

## 3. Resource & KPI Alignment
*   **Formal Allocation:** The Technical Director's participation in contract preparation and order estimation is formally mandated by internal standards/regulations and their job description. [Source: *існує внутрішній стандарт/регламент, а також відповідні положення в посадовій інструкції...*]
*   **KPI Misalignment:** The Technical Director's KPIs are strictly tied to production volume and product quality, not sales support or estimation turnaround time. [Source: *у техничного директора в KPI показники повязані з обсягу виробництва та якості продукції.*]
*   **Resource Conflict (Bottleneck):** The Technical Director is overloaded with operational tasks, causing a severe bottleneck in the pre-sales process (7-10 day delays or completely ignored requests). [Source: *відповіді клієнту надаються із затримкою 7–10 днів, а частину заявок технічний директор може взагалі не опрацювати.*]

## 4. Systems and Infrastructure
*   **GAP:** No IT systems, CRM, or estimation tools are mentioned for tracking requests, managing handoffs, or calculating costs.
*   **GAP:** It is unclear how the communication (handoffs) between the Sales Manager and Technical Director is currently executed (e.g., email, paper, verbal).

## 5. Identified Gaps (GAP Statements)
*   **GAP [Resource Delegation]:** The case does not specify if the Technical Director has any subordinates (e.g., estimators, technologists, production assistants) to whom estimation or operational tasks could be delegated.
*   **GAP [System Allocation]:** Explicit lack of information regarding the software or tools used to allocate and track the estimation queue.
*   **GAP [Capacity Data]:** No data on the actual volume of requests per week/month versus the Technical Director's available capacity for non-production tasks.
```
