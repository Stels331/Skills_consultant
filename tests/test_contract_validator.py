import json
import tempfile
import unittest
from pathlib import Path

from app.pipeline.epistemic_graph import save_graph
from app.validation.contract_validator import (
    route_contract_status,
    validate_artifact_against_contract,
    validate_stage_input_contract,
)


FRONTMATTER = """---
id: case__selected_problem
artifact_type: selected_problem_card
stage: problem_factory
state: draft
parent_refs: []
source_refs: ["problems/ProblemPortfolio.md:L1"]
evidence_refs: []
viewpoints: []
epistemic_status: inferred
assurance_level: medium
valid_until: 2026-12-31
owner_role: analyst
gate_status: pending
violated_principles: []
next_expected_artifacts: []
created_at: 2026-03-19T12:00:00+00:00
updated_at: 2026-03-19T12:00:00+00:00
---
## facts
- a fact
## chr_targets
- a target
## derived_thresholds
- a threshold
## anti_goodhart_conditions
- an anti-goodhart condition
## hypotheses_to_validate
- a hypothesis
"""


class ContractValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "cases" / "case_20260319_1001"
        (self.workspace / "problems").mkdir(parents=True, exist_ok=True)
        (self.workspace / "contracts").mkdir(parents=True, exist_ok=True)

        contracts_src = Path(__file__).resolve().parents[1] / "contracts"
        contracts_dst = self.root / "contracts"
        contracts_dst.mkdir(parents=True, exist_ok=True)
        for path in contracts_src.glob("*.json"):
            (contracts_dst / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_valid_artifact_passes_contract(self):
        artifact = self.workspace / "problems" / "SelectedProblemCard.md"
        artifact.write_text(FRONTMATTER, encoding="utf-8")

        result = validate_artifact_against_contract(self.root, self.workspace, artifact)
        self.assertTrue(result.is_valid)

    def test_wrong_artifact_type_is_rejected(self):
        artifact = self.workspace / "problems" / "SelectedProblemCard.md"
        artifact.write_text(FRONTMATTER.replace("selected_problem_card", "comparison_acceptance_spec", 1), encoding="utf-8")

        result = validate_artifact_against_contract(self.root, self.workspace, artifact)
        self.assertFalse(result.is_valid)
        self.assertTrue(any(issue.code == "CONTRACT_ARTIFACT_TYPE_MISMATCH" for issue in result.issues))

    def test_stage_input_contract_fails_when_required_input_missing(self):
        result = validate_stage_input_contract(self.root, self.workspace, "solution_factory")
        self.assertFalse(result.is_valid)
        self.assertTrue(any(issue.code == "STAGE_INPUT_CONTRACT_MISSING_ARTIFACT" for issue in result.issues))

    def test_missing_required_section_degrades_contract(self):
        artifact = self.workspace / "reports" / "Analytical_Full_Report.md"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(
            FRONTMATTER.replace("selected_problem_card", "analytical_full_report", 1)
            .replace("problem_factory", "reporting", 1)
            .replace("## facts", "## Notes", 1),
            encoding="utf-8",
        )

        result = validate_artifact_against_contract(self.root, self.workspace, artifact)
        self.assertTrue(result.is_valid)
        self.assertTrue(any(issue.code == "CONTRACT_REQUIRED_SECTION_MISSING" for issue in result.issues))

    def test_artifact_without_defined_contract_is_skipped(self):
        artifact = self.workspace / "intake" / "normalized_case.md"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(
            FRONTMATTER.replace("selected_problem_card", "normalized_case", 1)
            .replace("problem_factory", "intake", 1),
            encoding="utf-8",
        )

        result = validate_artifact_against_contract(self.root, self.workspace, artifact)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.issues, [])

    def test_unlawful_constraint_chain_degrades_comparison_acceptance_spec(self):
        artifact = self.workspace / "problems" / "ComparisonAcceptanceSpec.md"
        artifact.write_text(
            """---
id: case__acceptance_spec
artifact_type: comparison_acceptance_spec
stage: problem_factory
state: draft
parent_refs: []
source_refs: ["problems/ProblemPortfolio.md:L1"]
evidence_refs: []
viewpoints: []
epistemic_status: inferred
assurance_level: medium
valid_until: 2026-12-31
owner_role: analyst
gate_status: pending
violated_principles: []
next_expected_artifacts: []
created_at: 2026-03-19T12:00:00+00:00
updated_at: 2026-03-19T12:00:00+00:00
---
## indicators
- CHR-01
## hard_constraints
- keep loss under control
## assumptions_to_confirm
- confirm budget
## selection_policy
- minimize blast radius
## reversibility
- reversible within 30 days
""",
            encoding="utf-8",
        )
        save_graph(
            self.workspace / "analysis" / "epistemic_graph.json",
            {
                "workspace_id": self.workspace.name,
                "version": 1,
                "updated_at": "2026-03-19T12:00:00+00:00",
                "nodes": [
                    {
                        "id": "fact_1",
                        "node_type": "source_fact",
                        "statement": "observed process loss",
                        "source_refs": ["raw/case_input.md:L1"],
                        "epistemic_status": "observed",
                        "stage": "characterization",
                        "owner": "analyst",
                        "created_at": "2026-03-19T12:00:00+00:00",
                        "updated_at": "2026-03-19T12:00:00+00:00",
                    },
                    {
                        "id": "target_1",
                        "node_type": "normative_target",
                        "statement": "keep loss below target",
                        "source_refs": ["characterization/CharacterizationPassport.md:L1"],
                        "epistemic_status": "inferred",
                        "stage": "characterization",
                        "owner": "analyst",
                        "created_at": "2026-03-19T12:00:00+00:00",
                        "updated_at": "2026-03-19T12:00:00+00:00",
                    },
                    {
                        "id": "interp_1",
                        "node_type": "interpretation",
                        "statement": "this should be hard constrained",
                        "source_refs": ["problems/ProblemPortfolio.md:L1"],
                        "epistemic_status": "inferred",
                        "stage": "problem_factory",
                        "owner": "analyst",
                        "created_at": "2026-03-19T12:00:00+00:00",
                        "updated_at": "2026-03-19T12:00:00+00:00",
                    },
                    {
                        "id": "constraint_1",
                        "node_type": "decision_constraint",
                        "statement": "keep loss under control",
                        "source_refs": ["problems/ComparisonAcceptanceSpec.md:L1"],
                        "epistemic_status": "inferred",
                        "stage": "problem_factory",
                        "owner": "analyst",
                        "created_at": "2026-03-19T12:00:00+00:00",
                        "updated_at": "2026-03-19T12:00:00+00:00",
                    },
                ],
                "edges": [
                    {"edge_type": "DERIVED_FROM", "from": "target_1", "to": "fact_1", "provenance": "test"},
                    {"edge_type": "CONSTRAINS", "from": "constraint_1", "to": "target_1", "provenance": "test"},
                    {"edge_type": "RELATES_TO", "from": "interp_1", "to": "constraint_1", "provenance": "test"},
                ],
            },
        )

        result = validate_artifact_against_contract(self.root, self.workspace, artifact)
        self.assertTrue(result.is_valid)
        self.assertTrue(any(issue.code == "UNLAWFUL_CONSTRAINT_PROMOTION" for issue in result.issues))

        audit_path = self.workspace / "governance" / "contract_audit.jsonl"
        self.assertTrue(audit_path.is_file())
        self.assertIn("comparison_acceptance_spec", audit_path.read_text(encoding="utf-8"))

    def test_contract_route_maps_actions(self):
        route = route_contract_status(
            [
                type("Issue", (), {"action": "sanitize", "severity": "warning"})(),
                type("Issue", (), {"action": "degrade", "severity": "warning"})(),
            ]
        )
        self.assertEqual(route, "degrade")

    def test_degraded_artifact_hard_fails_contract_validation(self):
        artifact = self.workspace / "solutions" / "SolutionPortfolio.md"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(
            """---
id: case__solution_portfolio
artifact_type: solution_portfolio
stage: solution_factory
state: draft
parent_refs: []
source_refs: ["problems/ComparisonAcceptanceSpec.md:L1"]
evidence_refs: ["problems/SelectedProblemCard.md:L1"]
viewpoints: []
epistemic_status: hypothesis
assurance_level: medium
valid_until: 2026-12-31
owner_role: analyst
gate_status: pending
violated_principles: []
next_expected_artifacts: []
parse_metadata: {"parse_quality": "failed", "artifact_trust_level": "degraded", "retry_attempted": true, "retry_outcome": "failed", "missing_fields": {"sol_01_fix": ["intervention_force"]}, "inferred_fields": {}}
created_at: 2026-03-19T12:00:00+00:00
updated_at: 2026-03-19T12:00:00+00:00
---
# Solution Space Meta-Model
""",
            encoding="utf-8",
        )

        result = validate_artifact_against_contract(self.root, self.workspace, artifact)
        self.assertFalse(result.is_valid)
        self.assertTrue(any(issue.code == "DEGRADED_ARTIFACT_IN_PIPELINE" for issue in result.issues))


if __name__ == "__main__":
    unittest.main()
