import json
import tempfile
import unittest
from pathlib import Path

from app.pipeline.characterization import run_characterization
from app.pipeline.intake_parser import run_intake_parser
from app.pipeline.layer_builder import build_layers
from app.pipeline.problem_factory import run_problem_factory
from app.pipeline.reporting import _augment_analytical_report, run_reporting
from app.pipeline.solution_factory import run_solution_factory
from app.pipeline.viewpoint_runner import run_viewpoints
from app.router.orchestrator import StageOrchestrator
from app.state.workspace_manager import WorkspaceManager
from app.validation.artifact_contract_validator import read_frontmatter_document, validate_artifact_contract


class ReportingGatePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

        schema_src = Path(__file__).resolve().parents[1] / "schemas" / "artifact_frontmatter.schema.json"
        schema_dst = self.root / "schemas"
        schema_dst.mkdir(parents=True, exist_ok=True)
        (schema_dst / "artifact_frontmatter.schema.json").write_text(
            schema_src.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        skills_src = Path(__file__).resolve().parents[1] / ".agent" / "skills"
        skills_dst = self.root / ".agent" / "skills"
        skills_dst.mkdir(parents=True, exist_ok=True)
        for p in skills_src.glob("*/SKILL.md"):
            target = skills_dst / p.parent.name
            target.mkdir(parents=True, exist_ok=True)
            (target / "SKILL.md").write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

        self.manager = WorkspaceManager(self.root)
        self.ref = self.manager.create_workspace("case_20260303_601")

        (self.ref.path / "raw" / "case_input.md").write_text(
            (
                "Business model has strategic mismatch and delivery friction.\n"
                "Need high-confidence decision with rollback option.\n"
            ),
            encoding="utf-8",
        )

        run_intake_parser(self.root, self.ref.workspace_id)
        build_layers(self.root, self.ref.workspace_id, llm_mode="local")
        run_viewpoints(self.root, self.ref.workspace_id, llm_mode="local")
        run_characterization(self.root, self.ref.workspace_id, llm_mode="local")
        run_problem_factory(self.root, self.ref.workspace_id, llm_mode="local")
        run_solution_factory(self.root, self.ref.workspace_id, llm_mode="local")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_s6_t1_t2_reporting_composer_sections(self):
        out = run_reporting(self.root, self.ref.workspace_id)
        self.assertIn("analytical_full_report", out)
        self.assertIn("executive_summary", out)

        analytical = self.ref.path / "reports" / "Analytical_Full_Report.md"
        executive = self.ref.path / "reports" / "Executive_Summary.md"
        self.assertTrue(analytical.is_file())
        self.assertTrue(executive.is_file())

        a_body = read_frontmatter_document(analytical).body
        e_body = read_frontmatter_document(executive).body

        for i in range(1, 20):
            self.assertIn(f"## {i}.", a_body)
        for i in range(1, 11):
            self.assertIn(f"## {i}.", e_body)

        banned = ["chain-of-thought", "reasoning dump", "thought process"]
        for token in banned:
            self.assertNotIn(token, a_body.lower())
            self.assertNotIn(token, e_body.lower())

        self.assertNotIn("artifact_type:", a_body)
        self.assertNotIn("```markdown", a_body)
        self.assertNotIn("[truncated]", e_body)
        self.assertNotIn("```markdown", e_body)
        self.assertNotIn("artifact_type:", e_body)
        self.assertIn("**Факты:**", a_body)
        self.assertIn("**Интерпретации:**", a_body)
        self.assertIn("**Гипотезы / следующий шаг:**", a_body)
        self.assertTrue(
            "Подтвержденное действие" in e_body
            or "Гипотеза пилота" in e_body
            or "Предварительная рекомендация" in e_body
        )
        for token in ["BANT", "Shadow Mode", "CPQ", "пресейл -> ручная оценка -> производство"]:
            self.assertNotIn(token, a_body)
            self.assertNotIn(token, e_body)

        self.assertTrue(validate_artifact_contract(self.root, analytical, self.ref.path).is_valid)
        self.assertTrue(validate_artifact_contract(self.root, executive, self.ref.path).is_valid)

    def test_s6_t1_partial_data_marks_gaps(self):
        target = self.ref.path / "problems" / "ProblemArchive.md"
        if target.exists():
            target.unlink()

        run_reporting(self.root, self.ref.workspace_id)
        a_body = read_frontmatter_document(self.ref.path / "reports" / "Analytical_Full_Report.md").body
        self.assertIn("GAP: source artifact missing or empty", a_body)

    def test_s6_t1_parity_section_expands_short_solution_ids(self):
        body = """# Аналитический полный отчет

## 13. Parity Plan/Report
- source: `solutions/ParityReport.md`

Оценка решений показала:
* `sol_00` проваливает все целевые метрики.
* `sol_02` сходится с ограничениями.

## 14. Tradeoff Resolution
- source: `solutions/ConflictRecords.md`
"""
        artifacts = {
            "solutions/ParityReport.md": """## sol_00_status_quo
Text

## sol_02_it_historical_exploit_cpq
Text
"""
        }

        augmented = _augment_analytical_report(body, artifacts)

        self.assertIn("`sol_00` (`sol_00_status_quo`)", augmented)
        self.assertIn("`sol_02` (`sol_02_it_historical_exploit_cpq`)", augmented)
        self.assertIn("## 14. Tradeoff Resolution", augmented)

    def test_s6_t1_reporting_marks_deferred_decision(self):
        (self.ref.path / "solutions" / "SelectedSolutions.md").write_text(
            """---
id: deferred_selected
artifact_type: selected_solutions
stage: solution_factory
state: draft
parent_refs: []
source_refs: ["solutions/ParityReport.md:L1"]
evidence_refs: ["solutions/ConflictRecords.md:L1"]
viewpoints: []
epistemic_status: hypothesis
assurance_level: medium
valid_until: 2026-12-31
owner_role: analyst
gate_status: pending
violated_principles: []
next_expected_artifacts: []
created_at: 2026-03-03T12:00:00+00:00
updated_at: 2026-03-03T12:00:00+00:00
---
## Decision Status

- deferred_pending_data_collection
""",
            encoding="utf-8",
        )
        (self.ref.path / "decisions" / "ADR-001.md").write_text(
            """---
id: deferred_adr
artifact_type: adr_record
stage: solution_factory
state: draft
parent_refs: []
source_refs: ["solutions/SelectedSolutions.md:L1"]
evidence_refs: ["solutions/ConflictRecords.md:L1"]
viewpoints: []
epistemic_status: hypothesis
assurance_level: medium
valid_until: 2026-12-31
owner_role: analyst
gate_status: pending
violated_principles: []
next_expected_artifacts: []
created_at: 2026-03-03T12:00:00+00:00
updated_at: 2026-03-03T12:00:00+00:00
---
# ADR-001: Decision Deferred Pending Clarification
""",
            encoding="utf-8",
        )
        run_reporting(self.root, self.ref.workspace_id)

        analytical = read_frontmatter_document(self.ref.path / "reports" / "Analytical_Full_Report.md").body
        executive = read_frontmatter_document(self.ref.path / "reports" / "Executive_Summary.md").body

        self.assertIn("controlled deferral", analytical.lower())
        self.assertIn("Гипотеза пилота", executive)
        self.assertIn("Гипотеза пилота", executive)
        self.assertIn("требуется добавить следующие данные", analytical.lower())

    def test_s6_t3_validation_matrix_hard_fail(self):
        workspace_id = "case_20260303_602"
        ws = self.root / "cases" / workspace_id
        (ws / "governance" / "stage_artifacts").mkdir(parents=True, exist_ok=True)
        (ws / "governance" / "stage_artifacts" / "intake.md").write_text(
            """---\nid: a\n---\n""",
            encoding="utf-8",
        )

        orch = StageOrchestrator(self.root)
        result = orch.run_stage(workspace_id, "intake")
        self.assertEqual(result.gate_result, "block")

        payload = json.loads((ws / "governance" / "decision_log.jsonl").read_text(encoding="utf-8").strip().splitlines()[-1])
        self.assertEqual(payload["validation_matrix"]["outcome"], "block")

    def test_s6_t3_waive_requires_policy_and_can_pass_warnings(self):
        workspace_id = "case_20260303_603"
        ws = self.root / "cases" / workspace_id
        (ws / "governance" / "stage_artifacts").mkdir(parents=True, exist_ok=True)

        artifact = ws / "governance" / "stage_artifacts" / "intake.md"
        artifact.write_text(
            """---
id: art_stage_intake
artifact_type: normalized_case
stage: intake
state: draft
parent_refs: []
source_refs: [\"raw/case_input.md:L1\"]
evidence_refs: []
viewpoints: []
epistemic_status: observed
assurance_level: medium
valid_until: 2026-03-06
owner_role: analyst
gate_status: pending
violated_principles: []
next_expected_artifacts: []
created_at: 2026-03-03T12:00:00+00:00
updated_at: 2026-03-03T12:00:00+00:00
---
- observed value
""",
            encoding="utf-8",
        )

        orch = StageOrchestrator(self.root)

        blocked = orch.run_stage(workspace_id, "intake", signals={"force_waive": True})
        self.assertEqual(blocked.gate_result, "block")

        passed = orch.run_stage(
            workspace_id,
            "intake",
            signals={
                "force_waive": True,
                "waive_policy_id": "POL-06",
                "waive_owner": "chief_arch",
                "waive_rationale": "bounded commitment",
            },
        )
        self.assertEqual(passed.gate_result, "pass")

        doc = read_frontmatter_document(artifact)
        self.assertEqual(doc.frontmatter.get("state"), "waived")

    def test_s6_t3_feedback_loop_reentry_trigger(self):
        run_reporting(self.root, self.ref.workspace_id)

        (self.ref.path / "operation" / "ImpactMeasurement.json").write_text(
            json.dumps(
                {
                    "effect_achieved": False,
                    "reentry_stage": "solution_factory",
                    "reason": "kpi below threshold",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        orch = StageOrchestrator(self.root)
        result = orch.run_stage(self.ref.workspace_id, "reporting")
        self.assertEqual(result.gate_result, "degrade")

        payload = json.loads(
            (self.ref.path / "governance" / "decision_log.jsonl").read_text(encoding="utf-8").strip().splitlines()[-1]
        )
        self.assertEqual(payload["validation_matrix"]["reentry_trigger"], "impact_target_not_achieved")
        self.assertEqual(payload["recheck_trigger"], "impact_target_not_achieved")
        self.assertEqual(payload["incoming_recheck_trigger"], "")
        self.assertEqual(payload["computed_recheck_trigger"], "impact_target_not_achieved")

    def test_reporting_surfaces_rejected_alternative_classes(self):
        selected = self.ref.path / "solutions" / "SelectedSolutions.md"
        selected.write_text(
            """---
id: selected
artifact_type: selected_solutions
stage: solution_factory
state: draft
parent_refs: []
source_refs: ["solutions/ParityReport.md:L1"]
evidence_refs: ["solutions/ConflictRecords.md:L1"]
viewpoints: []
epistemic_status: decision_grade
assurance_level: medium
valid_until: 2026-12-31
owner_role: analyst
gate_status: pending
violated_principles: []
next_expected_artifacts: []
created_at: 2026-03-03T12:00:00+00:00
updated_at: 2026-03-03T12:00:00+00:00
---
## Selected Solutions

- sol_03_architecture_slice

## Recommendation Status

- confirmed_action: sol_03_architecture_slice

## Rejected Alternatives

- sol_01_local_gatekeeping: rollout_relevant_not_primary
- reason: sol_01_local_gatekeeping (kept as rollout-relevant fallback, but weaker than the selected pair)
- sol_04_policy_reset: dominated_or_constraint_failing
- reason: sol_04_policy_reset (higher risk exposure under current horizon)
""",
            encoding="utf-8",
        )
        run_reporting(self.root, self.ref.workspace_id)
        analytical = read_frontmatter_document(self.ref.path / "reports" / "Analytical_Full_Report.md").body
        executive = read_frontmatter_document(self.ref.path / "reports" / "Executive_Summary.md").body
        self.assertIn("rollout-relevant but not primary", analytical)
        self.assertIn("dominated", executive.lower())

    def test_reporting_expands_weak_and_medium_interventions(self):
        (self.ref.path / "solutions" / "SolutionPortfolio.md").write_text(
            """---
id: portfolio
artifact_type: solution_portfolio
stage: solution_factory
state: draft
parent_refs: []
source_refs: ["problems/ComparisonAcceptanceSpec.md:L1"]
evidence_refs: ["problems/SelectedProblemCard.md:L1"]
viewpoints: []
epistemic_status: observed
assurance_level: medium
valid_until: 2026-12-31
owner_role: analyst
gate_status: pending
violated_principles: []
next_expected_artifacts: []
created_at: 2026-03-03T12:00:00+00:00
updated_at: 2026-03-03T12:00:00+00:00
---
## sol_01_intake_brief_and_triage
- type: process
- assurance_level: high
- intervention_force: weak
- expected_effects: removes noisy requests before expert escalation

## sol_02_shadow_mode_matrix
- type: process
- assurance_level: medium
- intervention_force: medium
- expected_effects: externalizes part of expert knowledge into a controlled matrix

## sol_03_cpq_portal
- type: architecture
- assurance_level: low
- intervention_force: strong
- expected_effects: automates standard pricing through a portal
""",
            encoding="utf-8",
        )
        run_reporting(self.root, self.ref.workspace_id)
        analytical = read_frontmatter_document(self.ref.path / "reports" / "Analytical_Full_Report.md").body
        self.assertIn("Weak interventions", analytical)
        self.assertIn("Medium interventions", analytical)
        self.assertIn("Это слабое решение", analytical)
        self.assertIn("Это среднее решение", analytical)

    def test_reporting_marks_unconfirmed_constraints_as_assumptions(self):
        (self.ref.path / "problems" / "ComparisonAcceptanceSpec.md").write_text(
            """---
id: spec
artifact_type: comparison_acceptance_spec
stage: problem_factory
state: draft
parent_refs: []
source_refs: ["problems/SelectedProblemCard.md:L1"]
evidence_refs: []
viewpoints: []
epistemic_status: observed
assurance_level: medium
valid_until: 2026-12-31
owner_role: analyst
gate_status: pending
violated_principles: []
next_expected_artifacts: []
created_at: 2026-03-03T12:00:00+00:00
updated_at: 2026-03-03T12:00:00+00:00
---
# Comparison & Acceptance Spec

## hard_constraints
- budget_limit: fixed
- time_horizon_days: 30
""",
            encoding="utf-8",
        )
        (self.ref.path / "solutions" / "ParityReport.md").write_text(
            """---
id: parity
artifact_type: parity_report
stage: solution_factory
state: draft
parent_refs: []
source_refs: ["solutions/SolutionPortfolio.md:L1"]
evidence_refs: []
viewpoints: []
epistemic_status: observed
assurance_level: medium
valid_until: 2026-12-31
owner_role: analyst
gate_status: pending
violated_principles: []
next_expected_artifacts: []
created_at: 2026-03-03T12:00:00+00:00
updated_at: 2026-03-03T12:00:00+00:00
---
# Parity Report

- comparison frame: same budget, same 30-day window
""",
            encoding="utf-8",
        )
        run_reporting(self.root, self.ref.workspace_id)
        analytical = read_frontmatter_document(self.ref.path / "reports" / "Analytical_Full_Report.md").body
        self.assertIn("рабочие предположения", analytical)
        self.assertIn("подтвержденные входные данные", analytical)


if __name__ == "__main__":
    unittest.main()
