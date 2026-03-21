from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from app.pipeline.constraint_compiler import compile_lawful_constraints
from app.validation.artifact_contract_validator import read_frontmatter_document


@dataclass(frozen=True)
class ContractIssue:
    code: str
    severity: str  # hard_fail|warning
    message: str
    path: str
    action: str  # fail|degrade|sanitize


@dataclass(frozen=True)
class ContractValidationResult:
    is_valid: bool
    issues: List[ContractIssue]


STAGE_INPUT_CONTRACTS = {
    "solution_factory": [
        "problems/SelectedProblemCard.md",
        "problems/ComparisonAcceptanceSpec.md",
    ],
    "reporting": [
        "solutions/SelectedSolutions.md",
        "decisions/ADR-001.md",
        "operation/Runbook.md",
        "operation/RollbackPlan.md",
    ],
}


def _audit(workspace_path: Path, payload: Dict[str, object]) -> None:
    path = workspace_path / "governance" / "contract_audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _load_contract(project_root: Path, name: str) -> Dict[str, object]:
    path = project_root / "contracts" / f"{name}.contract.json"
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact_contract_name(artifact_path: Path, frontmatter: Dict[str, object] | None = None) -> str:
    rel = f"{artifact_path.parent.name}/{artifact_path.name}"
    path_contracts = {
        "problems/SelectedProblemCard.md": "selected_problem_card",
        "problems/ComparisonAcceptanceSpec.md": "comparison_acceptance_spec",
        "characterization/CharacterizationPassport.md": "characterization_passport",
        "solutions/SolutionPortfolio.md": "solution_portfolio",
        "solutions/SelectedSolutions.md": "selected_solutions",
        "reports/Analytical_Full_Report.md": "analytical_full_report",
        "reports/Executive_Summary.md": "executive_summary",
    }
    if rel in path_contracts:
        return path_contracts[rel]
    if artifact_path.name == "domain_profile.json":
        return "domain_profile"
    if artifact_path.name == "epistemic_graph.json":
        return "epistemic_graph"
    if artifact_path.suffix == ".json" and artifact_path.parent.name == "projections":
        return "projection"
    artifact_type = str((frontmatter or {}).get("artifact_type") or "")
    if artifact_type == "viewpoint_report" and artifact_path.name == "market.md":
        return "market_viewpoint_report"
    return artifact_type


def _validate_json_contract(contract: Dict[str, object], artifact_path: Path) -> List[ContractIssue]:
    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [
            ContractIssue(
                code="INVALID_JSON_CONTRACT_PAYLOAD",
                severity="hard_fail",
                message=str(exc),
                path=str(artifact_path),
                action="fail",
            )
        ]
    issues: List[ContractIssue] = []
    for field in contract.get("required_json_fields", []):
        if field not in payload:
            issues.append(
                ContractIssue(
                    code="CONTRACT_REQUIRED_FIELD_MISSING",
                    severity="hard_fail",
                    message=f"Missing required field: {field}",
                    path=f"$.{field}",
                    action="fail",
                )
            )
    return issues


def _validate_markdown_contract(contract: Dict[str, object], artifact_path: Path) -> List[ContractIssue]:
    doc = read_frontmatter_document(artifact_path)
    issues: List[ContractIssue] = []
    parse_metadata = doc.frontmatter.get("parse_metadata") or {}

    expected_type = str(contract.get("artifact_type") or "")
    expected_stage = str(contract.get("expected_stage") or "")
    if expected_type and str(doc.frontmatter.get("artifact_type") or "") != expected_type:
        issues.append(
            ContractIssue(
                code="CONTRACT_ARTIFACT_TYPE_MISMATCH",
                severity="hard_fail",
                message=f"Expected artifact_type={expected_type}",
                path="$.artifact_type",
                action="fail",
            )
        )
    if expected_stage and str(doc.frontmatter.get("stage") or "") != expected_stage:
        issues.append(
            ContractIssue(
                code="CONTRACT_STAGE_MISMATCH",
                severity="hard_fail",
                message=f"Expected stage={expected_stage}",
                path="$.stage",
                action="fail",
            )
        )
    for section in contract.get("required_sections", []):
        if section not in doc.body:
            issues.append(
                ContractIssue(
                    code="CONTRACT_REQUIRED_SECTION_MISSING",
                    severity="warning",
                    message=f"Missing required section: {section}",
                    path="$.body",
                    action="degrade",
                )
            )
    for term in contract.get("forbidden_terms", []):
        if str(term) in doc.body:
            issues.append(
                ContractIssue(
                    code="CONTRACT_FORBIDDEN_TERM_PRESENT",
                    severity="warning",
                    message=f"Forbidden term present: {term}",
                    path="$.body",
                    action="sanitize",
                )
            )

    quality = str(parse_metadata.get("parse_quality", "clean"))
    inferred = parse_metadata.get("inferred_fields", {})
    if str(parse_metadata.get("artifact_trust_level") or "") == "degraded":
        issues.append(
            ContractIssue(
                code="DEGRADED_ARTIFACT_IN_PIPELINE",
                severity="hard_fail",
                message="Artifact marked degraded after retry and cannot proceed as trusted pipeline input",
                path="$.parse_metadata.artifact_trust_level",
                action="fail",
            )
        )
    elif expected_type == "solution_portfolio":
        if quality == "failed":
            issues.append(ContractIssue(
                code="SOLUTION_PORTFOLIO_PARSE_FAILED",
                severity="hard_fail",
                message="Portfolio built from fallback — no LLM output was parseable",
                path="$.parse_metadata.parse_quality",
                action="fail",
            ))
        elif quality == "inferred" or inferred:
            issues.append(ContractIssue(
                code="SOLUTION_PORTFOLIO_INFERRED_FIELDS",
                severity="warning",
                message=f"Fields inferred by parser, not from LLM: {list(inferred.keys()) if inferred else []}",
                path="$.parse_metadata.inferred_fields",
                action="degrade",
            ))

    return issues


def validate_artifact_against_contract(
    project_root: Path,
    workspace_path: Path,
    artifact_path: Path,
) -> ContractValidationResult:
    if not artifact_path.exists():
        return ContractValidationResult(
            is_valid=False,
            issues=[
                ContractIssue(
                    code="CONTRACT_ARTIFACT_MISSING",
                    severity="hard_fail",
                    message="Artifact missing for contract validation",
                    path=str(artifact_path),
                    action="fail",
                )
            ],
        )

    frontmatter = None
    if artifact_path.suffix == ".md":
        try:
            frontmatter = read_frontmatter_document(artifact_path).frontmatter
        except Exception as exc:
            return ContractValidationResult(
                is_valid=False,
                issues=[
                    ContractIssue(
                        code="CONTRACT_INVALID_FRONTMATTER",
                        severity="hard_fail",
                        message=str(exc),
                        path=str(artifact_path),
                        action="fail",
                    )
                ],
            )

    contract_name = _artifact_contract_name(artifact_path, frontmatter)
    if not contract_name:
        return ContractValidationResult(is_valid=True, issues=[])
    try:
        contract = _load_contract(project_root, contract_name)
    except FileNotFoundError:
        _audit(
            workspace_path,
            {
                "event": "artifact_contract_validation_skipped",
                "artifact_path": str(artifact_path.relative_to(workspace_path)),
                "contract_name": contract_name,
                "reason": "contract_not_defined",
            },
        )
        return ContractValidationResult(is_valid=True, issues=[])

    if contract.get("format") == "json":
        issues = _validate_json_contract(contract, artifact_path)
    else:
        issues = _validate_markdown_contract(contract, artifact_path)

    if contract_name == "comparison_acceptance_spec":
        compiled = compile_lawful_constraints(workspace_path)
        if compiled.rejected_constraints:
            issues.append(
                ContractIssue(
                    code="UNLAWFUL_CONSTRAINT_PROMOTION",
                    severity="warning",
                    message="ComparisonAcceptanceSpec includes constraints without lawful source chain",
                    path="$.hard_constraints",
                    action="degrade",
                )
            )

    _audit(
        workspace_path,
        {
            "event": "artifact_contract_validation",
            "artifact_path": str(artifact_path.relative_to(workspace_path)),
            "contract_name": contract_name,
            "issues": [issue.__dict__ for issue in issues],
        },
    )
    return ContractValidationResult(is_valid=not any(i.severity == "hard_fail" for i in issues), issues=issues)


def validate_stage_input_contract(
    project_root: Path,
    workspace_path: Path,
    stage_name: str,
) -> ContractValidationResult:
    issues: List[ContractIssue] = []
    for rel in STAGE_INPUT_CONTRACTS.get(stage_name.lower(), []):
        if not (workspace_path / rel).is_file():
            issues.append(
                ContractIssue(
                    code="STAGE_INPUT_CONTRACT_MISSING_ARTIFACT",
                    severity="hard_fail",
                    message=f"Missing required input artifact: {rel}",
                    path=f"$.stage_inputs.{stage_name}",
                    action="fail",
                )
            )
    _audit(
        workspace_path,
        {
            "event": "stage_input_contract_validation",
            "stage_name": stage_name,
            "issues": [issue.__dict__ for issue in issues],
        },
    )
    return ContractValidationResult(is_valid=not any(i.severity == "hard_fail" for i in issues), issues=issues)


def route_contract_status(issues: List[ContractIssue]) -> str:
    if any(issue.action == "fail" or issue.severity == "hard_fail" for issue in issues):
        return "fail"
    if any(issue.action == "degrade" for issue in issues):
        return "degrade"
    if any(issue.action == "sanitize" for issue in issues):
        return "sanitize"
    return "pass"
