from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class MatrixFinding:
    code: str
    severity: str  # hard_fail|warning
    message: str
    path: str
    waivable: bool = False


@dataclass(frozen=True)
class MatrixResult:
    outcome: str  # pass|degrade|block
    findings: List[MatrixFinding]
    waive_used: bool
    waive_note: str
    reentry_trigger: str
    reentry_target_stage: str


def _parse_valid_until(raw: str) -> Optional[datetime]:
    txt = str(raw or "").strip()
    if not txt:
        return None
    try:
        if len(txt) == 10:
            return datetime.fromisoformat(txt + "T00:00:00+00:00")
        dt = datetime.fromisoformat(txt.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _near_expiry(valid_until: str, now: datetime) -> bool:
    dt = _parse_valid_until(valid_until)
    if not dt:
        return False
    return now <= dt <= now + timedelta(days=7)


def _stage_required_artifacts(stage_name: str) -> List[str]:
    stage = stage_name.lower()
    if stage == "solution_factory":
        return [
            "problems/SelectedProblemCard.md",
            "problems/ComparisonAcceptanceSpec.md",
        ]
    if stage == "reporting":
        return [
            "solutions/SelectedSolutions.md",
            "decisions/ADR-001.md",
            "operation/Runbook.md",
            "operation/RollbackPlan.md",
        ]
    return []


def _impact_reentry(workspace_path: Path) -> tuple[str, str]:
    p = workspace_path / "operation" / "ImpactMeasurement.json"
    if not p.is_file():
        return "", ""
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return "impact_measurement_invalid", "problem_factory"

    achieved = bool(payload.get("effect_achieved", False))
    if achieved:
        return "", ""

    requested = str(payload.get("reentry_stage", "solution_factory")).strip().lower()
    if requested not in {"problem_factory", "solution_factory"}:
        requested = "solution_factory"
    return "impact_target_not_achieved", requested


def evaluate_validation_matrix(
    *,
    workspace_path: Path,
    stage_name: str,
    artifact_path: Path,
    frontmatter: Dict[str, object],
    structural_issues: List[Dict[str, str]],
    semantic_issues: List[Dict[str, str]],
    assurance_issues: List[Dict[str, str]],
    signals: Dict[str, object],
) -> MatrixResult:
    now = datetime.now(timezone.utc)
    findings: List[MatrixFinding] = []

    for issue in structural_issues:
        findings.append(
            MatrixFinding(
                code=str(issue.get("message") or "STRUCTURAL_FAILURE"),
                severity="hard_fail",
                message=str(issue.get("message") or "structural contract issue"),
                path=str(issue.get("path") or "$.contract"),
            )
        )

    for issue in semantic_issues:
        sev = str(issue.get("severity") or "medium").lower()
        findings.append(
            MatrixFinding(
                code=str(issue.get("code") or "SEMANTIC_ISSUE"),
                severity="hard_fail" if sev == "high" else "warning",
                message=str(issue.get("message") or "semantic issue"),
                path="$.semantic",
                waivable=sev != "high",
            )
        )

    for issue in assurance_issues:
        sev = str(issue.get("severity") or "medium").lower()
        code = str(issue.get("code") or "ASSURANCE_ISSUE")
        force_hard = code in {"MISSING_EVIDENCE_REFS", "EXPIRED_ARTIFACT"}
        findings.append(
            MatrixFinding(
                code=code,
                severity="hard_fail" if force_hard or sev == "high" else "warning",
                message=str(issue.get("message") or "assurance issue"),
                path="$.assurance",
                waivable=not force_hard,
            )
        )

    for rel in _stage_required_artifacts(stage_name):
        if not (workspace_path / rel).is_file():
            findings.append(
                MatrixFinding(
                    code="MISSING_MANDATORY_ARTIFACT",
                    severity="hard_fail",
                    message=f"missing mandatory artifact for stage: {rel}",
                    path=f"$.stage.{stage_name}",
                )
            )

    if stage_name.lower() == "solution_factory":
        portfolio = workspace_path / "solutions" / "SolutionPortfolio.md"
        if portfolio.is_file():
            txt = portfolio.read_text(encoding="utf-8")
            if txt.lower().count("## sol_") < 4:
                findings.append(
                    MatrixFinding(
                        code="INSUFFICIENT_ALTERNATIVES",
                        severity="hard_fail",
                        message="less than 3 alternatives + status quo in solution portfolio",
                        path="$.solution_portfolio",
                    )
                )

    if stage_name.lower() == "reporting":
        sel = workspace_path / "solutions" / "SelectedSolutions.md"
        if sel.is_file() and not (workspace_path / "decisions" / "ADR-001.md").is_file():
            findings.append(
                MatrixFinding(
                    code="MISSING_ADR_FOR_SELECTED_SOLUTION",
                    severity="hard_fail",
                    message="ADR is required for selected solution",
                    path="$.reporting.inputs",
                )
            )
        if sel.is_file() and not (workspace_path / "operation" / "RollbackPlan.md").is_file():
            findings.append(
                MatrixFinding(
                    code="MISSING_ROLLBACK_PLAN",
                    severity="hard_fail",
                    message="RollbackPlan is required for selected solution",
                    path="$.reporting.inputs",
                )
            )

    valid_until = str(frontmatter.get("valid_until") or "")
    if _near_expiry(valid_until, now):
        findings.append(
            MatrixFinding(
                code="VALID_UNTIL_NEAR_EXPIRY",
                severity="warning",
                message="artifact valid_until is close to expiry",
                path="$.valid_until",
                waivable=True,
            )
        )

    reentry_trigger, reentry_target = _impact_reentry(workspace_path)
    if reentry_trigger:
        findings.append(
            MatrixFinding(
                code="IMPACT_REENTRY_TRIGGER",
                severity="warning",
                message="impact target not achieved; re-entry is required",
                path="$.operation.impact",
                waivable=False,
            )
        )

    hard_fails = [f for f in findings if f.severity == "hard_fail"]
    warnings = [f for f in findings if f.severity == "warning"]

    waive_used = False
    waive_note = ""

    if hard_fails:
        outcome = "block"
    elif warnings:
        outcome = "degrade"
    else:
        outcome = "pass"

    if signals.get("force_waive"):
        policy_id = str(signals.get("waive_policy_id") or "")
        owner = str(signals.get("waive_owner") or "")
        rationale = str(signals.get("waive_rationale") or "")
        if not (policy_id and owner and rationale):
            findings.append(
                MatrixFinding(
                    code="WAIVE_POLICY_FIELDS_MISSING",
                    severity="hard_fail",
                    message="waive requires waive_policy_id, waive_owner, waive_rationale",
                    path="$.waive",
                )
            )
            outcome = "block"
        elif outcome == "degrade" and warnings and all(f.waivable for f in warnings):
            outcome = "pass"
            waive_used = True
            waive_note = f"policy={policy_id}; owner={owner}; rationale={rationale}"
        elif outcome == "block":
            findings.append(
                MatrixFinding(
                    code="WAIVE_REJECTED_FOR_HARD_FAIL",
                    severity="hard_fail",
                    message="waive cannot override hard fail findings",
                    path="$.waive",
                )
            )

    return MatrixResult(
        outcome=outcome,
        findings=findings,
        waive_used=waive_used,
        waive_note=waive_note,
        reentry_trigger=reentry_trigger,
        reentry_target_stage=reentry_target,
    )
