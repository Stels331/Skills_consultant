---
id: case_20260318_003__layer_3_functional_model
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
created_at: 2026-03-18T20:30:40.965940+00:00
updated_at: 2026-03-18T20:30:40.965940+00:00
---
```markdown
# Layer 3: Functional Model

## 1. System Context
The "TOM GEAR" system is designed as a closed-loop, self-sustaining wood processing complex. Its primary functional paradigm is to convert raw roundwood into finished wood products while utilizing the generated wood waste to produce the electricity and heat required for the entire manufacturing process. 

*Note: The energy generation function is currently postponed, altering the functional loop.* [Source: TOM GEAR_input.md]

## 2. Core Functional Blocks

### 2.1. Primary Wood Processing (Sawing)
*   **Function:** Convert raw roundwood into primary lumber and wood waste.
*   **Throughput Capacity:** 1500 m³ of roundwood per month (operating 22-24 shifts).
*   **Inputs:** Roundwood.
*   **Outputs:** Raw lumber, Wood waste (chips).

### 2.2. Wood Drying and Treatment
*   **Function:** Reduce moisture content and improve durability of the wood.
*   **Processes:** Vacuum press drying, thermal modification (thermo-wood), and impregnation.
*   **Throughput Capacity:** Up to 1000 m³ per month (operating 30 calendar days).
*   **Inputs:** Raw lumber, Heat energy (intended from power generation).
*   **Outputs:** Dried and treated lumber.

### 2.3. Finishing and Molding
*   **Function:** Manufacture clean, finished wood products.
*   **Products:** Lining (вагонка), clean blanks, planking, floorboards, terrace boards.
*   **Throughput Capacity:** Up to 500 m³ per month (operating 22-24 shifts).
*   **Inputs:** Dried lumber.
*   **Outputs:** Finished wood products.

### 2.4. Auxiliary Production (Small Mechanization)
*   **Function:** Utilize dry and wet wood for secondary products via small-scale mechanization.
*   **Products:** Simple pallets, glued moldings.
*   **Inputs:** Dry and wet wood offcuts/lumber.
*   **Outputs:** Secondary wood products.

### 2.5. Energy Generation (Gasification) - *[Currently Postponed]*
*   **Function:** Convert wood waste into combustible gas via a gasification reactor.
*   **Inputs:** Wood waste (chips) from the primary processing block.
*   **Outputs:** Combustible gas.

### 2.6. Power Generation and Distribution - *[Currently Postponed]*
*   **Function:** Generate electricity and heat from gas, and safely distribute it across the complex.
*   **Capacity:** 700 kW of electricity per hour.
*   **Inputs:** Combustible gas.
*   **Outputs:** Electricity (distributed to all machinery), Heat energy (distributed to drying/treatment block).

## 3. Material and Energy Flows (Target State)
1.  **Material Flow:** Roundwood $\rightarrow$ Primary Processing $\rightarrow$ Raw Lumber $\rightarrow$ Drying/Treatment $\rightarrow$ Dried Lumber $\rightarrow$ Finishing $\rightarrow$ End Products.
2.  **Waste-to-Energy Flow:** Primary Processing $\rightarrow$ Wood Waste (Chips) $\rightarrow$ Gasification Reactor $\rightarrow$ Gas $\rightarrow$ Power Generators $\rightarrow$ Electricity + Heat.
3.  **Energy Feedback Loop:** Electricity + Heat $\rightarrow$ Powers Primary Processing, Drying/Treatment, and Finishing blocks.

## 4. Identified Gaps (GAP Statements)
*   **GAP (Alternative Energy Source):** With the gasification and power generation functions postponed, the functional model lacks the definition of the interim power supply function (e.g., grid connection, external generators) required to operate the active sections.
*   **GAP (Waste Management):** Since waste is not currently being consumed by the gasification reactor, there is no defined function for waste storage, removal, or alternative utilization.
*   **GAP (Control Systems):** The functional logic for the "Power generation and safe distribution control node" is mentioned but lacks detailed functional specifications (e.g., load balancing, failovers, synchronization).
*   **GAP (Heat Transfer Mechanism):** The functional mechanism for capturing heat from the power generators and transferring it to the vacuum press/drying kilns is not specified.
*   **GAP (Material Handling):** Functions related to internal logistics, conveying systems between the three main processing sections, and buffer storage are undefined.
```
