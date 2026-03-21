from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from app.pipeline.characterization import run_characterization
from app.pipeline.intake_parser import run_intake_parser
from app.pipeline.layer_builder import build_layers
from app.pipeline.problem_factory import run_problem_factory
from app.pipeline.reporting import run_reporting
from app.pipeline.solution_factory import run_solution_factory
from app.pipeline.viewpoint_runner import run_viewpoints
from app.router.orchestrator import StageOrchestrator
from app.state.workspace_manager import WorkspaceManager
from app.testing.acceptance_checklist import run_acceptance_checklist
from app.validation.artifact_contract_validator import read_frontmatter_document, validate_workspace_artifact_contracts


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    status: str
    hard_fail_detected: bool
    completeness: float
    coherence: float
    evidence_strength: float
    actionability: float
    notes: str


def _fixture_cases(fixtures_dir: Path) -> List[Path]:
    return sorted(p for p in fixtures_dir.glob("*.md") if p.is_file())


def _compute_metrics(workspace: Path) -> Dict[str, float]:
    required = [
        "intake/normalized_case.md",
        "layers/layer_1_business_model.md",
        "layers/layer_2_requirements.md",
        "layers/layer_3_functional_model.md",
        "layers/layer_4_allocation_model.md",
        "viewpoints/strategist.md",
        "viewpoints/analyst.md",
        "viewpoints/operator.md",
        "viewpoints/architect.md",
        "viewpoints/critic.md",
        "viewpoints/client.md",
        "characterization/CharacterizationPassport.md",
        "problems/SelectedProblemCard.md",
        "solutions/SelectedSolutions.md",
        "decisions/ADR-001.md",
        "operation/Runbook.md",
        "operation/RollbackPlan.md",
        "reports/Analytical_Full_Report.md",
        "reports/Executive_Summary.md",
    ]
    present = sum(1 for rel in required if (workspace / rel).is_file())
    completeness = present / len(required)

    coherence = 0.0
    selected = workspace / "solutions" / "SelectedSolutions.md"
    if selected.is_file():
        body = read_frontmatter_document(selected).body.lower()
        coherence = 1.0 if "traceability" in body else 0.6

    evidence_strength = 0.0
    ev = workspace / "evidence" / "evidence_graph.json"
    if ev.is_file():
        data = json.loads(ev.read_text(encoding="utf-8"))
        claims = len(data.get("claims", []))
        edges = len(data.get("edges", []))
        evidence_strength = min(1.0, (claims + edges) / 40.0)

    actionability = 0.0
    if (workspace / "operation" / "Runbook.md").is_file() and (workspace / "operation" / "RollbackPlan.md").is_file():
        actionability = 1.0
    elif (workspace / "operation" / "Runbook.md").is_file():
        actionability = 0.6

    return {
        "completeness": round(completeness, 3),
        "coherence": round(coherence, 3),
        "evidence_strength": round(evidence_strength, 3),
        "actionability": round(actionability, 3),
    }


def _run_positive_case(project_root: Path, manager: WorkspaceManager, case_name: str, content: str) -> CaseResult:
    workspace_id = manager.generate_workspace_id("20260303")
    ref = manager.create_workspace(workspace_id)
    (ref.path / "raw" / "case_input.md").write_text(content, encoding="utf-8")

    run_intake_parser(project_root, workspace_id)
    build_layers(project_root, workspace_id, llm_mode="local")
    run_viewpoints(project_root, workspace_id, llm_mode="local")
    run_characterization(project_root, workspace_id, llm_mode="local")
    run_problem_factory(project_root, workspace_id, llm_mode="local")
    run_solution_factory(project_root, workspace_id, llm_mode="local")
    run_reporting(project_root, workspace_id)
    orch = StageOrchestrator(project_root)
    for stage in [
        "intake",
        "layers",
        "viewpoints",
        "characterization",
        "problem_factory",
        "solution_factory",
        "reporting",
    ]:
        orch.run_stage(
            workspace_id,
            stage,
            signals={"allow_reuse": True},
            rationale="integration_suite",
        )

    c = _compute_metrics(ref.path)
    notes = "ok"
    status = "ok"

    contracts = validate_workspace_artifact_contracts(project_root, ref.path)
    if any(not r.is_valid for r in contracts.values()):
        status = "fail"
        notes = "contract validation failed"
    acceptance = run_acceptance_checklist(project_root, ref.path)
    if not acceptance["acceptance_pass"]:
        status = "fail"
        notes = "acceptance checklist failed"

    return CaseResult(
        case_id=workspace_id,
        status=status,
        hard_fail_detected=False,
        completeness=c["completeness"],
        coherence=c["coherence"],
        evidence_strength=c["evidence_strength"],
        actionability=c["actionability"],
        notes=notes,
    )


def _run_negative_case(project_root: Path, manager: WorkspaceManager, case_name: str, content: str) -> CaseResult:
    # Deliberately malformed artifact to verify hard-fail detection.
    workspace_id = manager.generate_workspace_id("20260303")
    ref = manager.create_workspace(workspace_id)
    (ref.path / "governance" / "stage_artifacts").mkdir(parents=True, exist_ok=True)
    (ref.path / "governance" / "stage_artifacts" / "intake.md").write_text("---\nid: only\n---\n", encoding="utf-8")

    from app.router.orchestrator import StageOrchestrator

    orch = StageOrchestrator(project_root)
    result = orch.run_stage(workspace_id, "intake")

    hard_detected = result.gate_result == "block"
    status = "ok" if hard_detected else "fail"
    return CaseResult(
        case_id=workspace_id,
        status=status,
        hard_fail_detected=hard_detected,
        completeness=0.0,
        coherence=0.0,
        evidence_strength=0.0,
        actionability=0.0,
        notes="negative hard-fail detection",
    )


def run_integration_suite(project_root: Path) -> Dict[str, object]:
    fixtures_dir = project_root / "tests" / "integration" / "fixtures"
    manager = WorkspaceManager(project_root)

    cases = _fixture_cases(fixtures_dir)
    results: List[CaseResult] = []
    for fx in cases:
        content = fx.read_text(encoding="utf-8")
        if fx.stem.startswith("neg_"):
            results.append(_run_negative_case(project_root, manager, fx.stem, content))
        else:
            results.append(_run_positive_case(project_root, manager, fx.stem, content))

    total = len(results)
    ok_cases = sum(1 for r in results if r.status == "ok")
    silent_failures = total - ok_cases

    negatives = [r for r in results if r.notes.startswith("negative")]
    detected = sum(1 for r in negatives if r.hard_fail_detected)
    hard_fail_detection_rate = detected / len(negatives) if negatives else 1.0

    positives = [r for r in results if not r.notes.startswith("negative")]
    avg = lambda key: round(sum(getattr(r, key) for r in positives) / len(positives), 3) if positives else 0.0

    payload = {
        "total_cases": total,
        "ok_cases": ok_cases,
        "silent_failures": silent_failures,
        "hard_fail_detection_rate": round(hard_fail_detection_rate, 3),
        "avg_completeness": avg("completeness"),
        "avg_coherence": avg("coherence"),
        "avg_evidence_strength": avg("evidence_strength"),
        "avg_actionability": avg("actionability"),
        "cases": [r.__dict__ for r in results],
    }

    reports_dir = project_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "integration_quality_report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Integration Quality Report",
        "",
        f"- total_cases: {payload['total_cases']}",
        f"- ok_cases: {payload['ok_cases']}",
        f"- silent_failures: {payload['silent_failures']}",
        f"- hard_fail_detection_rate: {payload['hard_fail_detection_rate']}",
        f"- avg_completeness: {payload['avg_completeness']}",
        f"- avg_coherence: {payload['avg_coherence']}",
        f"- avg_evidence_strength: {payload['avg_evidence_strength']}",
        f"- avg_actionability: {payload['avg_actionability']}",
        "",
        "## Cases",
    ]
    for item in payload["cases"]:
        lines.append(
            f"- {item['case_id']} | status={item['status']} | completeness={item['completeness']} | coherence={item['coherence']} | evidence={item['evidence_strength']} | actionability={item['actionability']} | notes={item['notes']}"
        )

    (reports_dir / "integration_quality_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload
