from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from app.pipeline.constraint_compiler import compile_lawful_constraints
from app.validation.artifact_contract_validator import read_frontmatter_document, validate_workspace_artifact_contracts
from app.validation.conflict_validator import validate_unresolved_conflicts
from app.validation.cross_case_contamination_validator import validate_cross_case_contamination


def _projection_paths(workspace_path: Path) -> List[Path]:
    proj_dir = workspace_path / "analysis" / "projections"
    if not proj_dir.is_dir():
        return []
    return sorted(proj_dir.glob("*.json"))


def run_acceptance_checklist(project_root: Path, workspace_path: Path) -> Dict[str, object]:
    contracts = validate_workspace_artifact_contracts(project_root, workspace_path)
    contract_failures = [rel for rel, result in contracts.items() if not result.is_valid]
    required_artifacts = [
        "analysis/domain_profile.json",
        "analysis/epistemic_graph.json",
        "solutions/SelectedSolutions.md",
        "decisions/ADR-001.md",
        "operation/Runbook.md",
        "operation/RollbackPlan.md",
        "reports/Analytical_Full_Report.md",
        "reports/Executive_Summary.md",
    ]
    for rel in required_artifacts:
        if not (workspace_path / rel).exists():
            contract_failures.append(rel)

    selected_path = workspace_path / "solutions" / "SelectedSolutions.md"
    analytical_path = workspace_path / "reports" / "Analytical_Full_Report.md"
    executive_path = workspace_path / "reports" / "Executive_Summary.md"

    contamination_hits: List[Dict[str, object]] = []
    for artifact in [analytical_path, executive_path]:
        if not artifact.is_file():
            continue
        body = read_frontmatter_document(artifact).body
        for issue in validate_cross_case_contamination(artifact, body):
            contamination_hits.append(
                {
                    "artifact": str(artifact.relative_to(workspace_path)),
                    "code": issue.code,
                    "severity": issue.severity,
                    "matched_terms": issue.matched_terms,
                }
            )
    hard_contamination_hits = [item for item in contamination_hits if str(item.get("severity")) == "high"]

    lawful = compile_lawful_constraints(workspace_path)
    selection_projection_path = workspace_path / "analysis" / "projections" / "selection_projection.json"
    leaked_rejected_constraints: List[str] = []
    if selection_projection_path.is_file():
        payload = json.loads(selection_projection_path.read_text(encoding="utf-8"))
        lawful_ids = {
            str(node.get("id"))
            for node in payload.get("projection_payload", {}).get("lawful_constraints", [])
            if isinstance(node, dict)
        }
        rejected_ids = {
            str(item.get("node", {}).get("id"))
            for item in payload.get("projection_payload", {}).get("rejected_constraints", [])
            if isinstance(item, dict)
        }
        leaked_rejected_constraints = sorted(lawful_ids & rejected_ids)

    unresolved = validate_unresolved_conflicts(workspace_path)

    projections = [str(path.relative_to(workspace_path)) for path in _projection_paths(workspace_path)]
    ledger_path = workspace_path / "governance" / "epistemic_ledger.jsonl"
    ledger_entries = 0
    if ledger_path.is_file():
        ledger_entries = len([ln for ln in ledger_path.read_text(encoding="utf-8").splitlines() if ln.strip()])

    payload = {
        "workspace_id": workspace_path.name,
        "contracts_pass": not contract_failures,
        "contract_failures": contract_failures,
        "contamination_absent": not hard_contamination_hits,
        "contamination_hits": contamination_hits,
        "lawful_promotion_enforced": not leaked_rejected_constraints,
        "rejected_constraints": lawful.rejected_constraints,
        "rejected_constraints_leaked": leaked_rejected_constraints,
        "unresolved_disputes_absent": not unresolved,
        "unresolved_disputes": [issue.__dict__ for issue in unresolved],
        "projections_emitted": bool(projections),
        "projection_files": projections,
        "ledger_populated": ledger_entries > 0,
        "ledger_entries": ledger_entries,
        "acceptance_pass": not contract_failures and not hard_contamination_hits and not leaked_rejected_constraints and not unresolved and bool(projections) and ledger_entries > 0,
    }

    reports_dir = workspace_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "acceptance_checklist.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Acceptance Checklist",
        "",
        f"- contracts_pass: {payload['contracts_pass']}",
        f"- contamination_absent: {payload['contamination_absent']}",
        f"- lawful_promotion_enforced: {payload['lawful_promotion_enforced']}",
        f"- unresolved_disputes_absent: {payload['unresolved_disputes_absent']}",
        f"- projections_emitted: {payload['projections_emitted']}",
        f"- ledger_populated: {payload['ledger_populated']}",
        f"- acceptance_pass: {payload['acceptance_pass']}",
    ]
    (reports_dir / "acceptance_checklist.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload
