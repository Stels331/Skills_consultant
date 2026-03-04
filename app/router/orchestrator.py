from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from pathlib import Path
from typing import Dict, List, Optional

from app.evidence.graph import build_and_persist_evidence_graph
from app.principles.library import Principle, load_principles_for_stage
from app.refresh.orchestrator import register_refresh_event
from app.state.state_machine import apply_transition, suggest_next_state
from app.validation.artifact_contract_validator import (
    FrontmatterDocument,
    read_frontmatter_document,
    validate_artifact_contract,
    write_frontmatter_document,
)
from app.validation.assurance_engine import evaluate_assurance
from app.validation.semantic_judge import run_semantic_judge
from app.validation.validation_matrix import evaluate_validation_matrix


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_valid_until_expired(raw: str) -> bool:
    if not raw:
        return False
    txt = str(raw).strip()
    now = datetime.now(timezone.utc)
    try:
        if len(txt) == 10:
            dt = datetime.fromisoformat(txt + "T00:00:00+00:00")
        else:
            dt = datetime.fromisoformat(txt.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return dt < now
    except ValueError:
        return False


@dataclass(frozen=True)
class StageRunResult:
    workspace_id: str
    stage_name: str
    artifact_id: str
    artifact_path: str
    previous_state: str
    new_state: str
    gate_result: str
    decision_log_path: str


class StageOrchestrator:
    """Sprint-01 skeleton orchestrator with DecisionLog emission."""

    STAGE_ARTIFACT_MAP = {
        "intake": "intake/normalized_case.md",
        "layers": "layers/layer_1_business_model.md",
        "viewpoints": "viewpoints/strategist.md",
        "characterization": "characterization/CharacterizationPassport.md",
        "problem_factory": "problems/SelectedProblemCard.md",
        "solution_factory": "solutions/SolutionPortfolio.md",
        "reporting": "reports/Analytical_Full_Report.md",
    }

    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()

    def _workspace_path(self, workspace_id: str) -> Path:
        return self.project_root / "cases" / workspace_id

    def _decision_log_path(self, workspace_id: str) -> Path:
        return self._workspace_path(workspace_id) / "governance" / "decision_log.jsonl"

    def _stage_events_path(self, workspace_id: str) -> Path:
        return self._workspace_path(workspace_id) / "governance" / "stage_events.jsonl"

    def _resolve_artifact_path(self, workspace_id: str, stage_name: str) -> Path:
        ws = self._workspace_path(workspace_id)
        local_stage = stage_name.lower()

        candidate = ws / "governance" / "stage_artifacts" / f"{local_stage}.md"
        if candidate.is_file():
            return candidate

        mapped = self.STAGE_ARTIFACT_MAP.get(local_stage)
        if mapped:
            return ws / mapped

        return ws / f"{local_stage}.md"

    def _stage_specific_violations(self, workspace_id: str, stage_name: str) -> List[Dict[str, str]]:
        ws = self._workspace_path(workspace_id)
        stage = stage_name.lower()
        violations: List[Dict[str, str]] = []

        if stage == "solution_factory":
            required = [
                ("problems/SelectedProblemCard.md", "selected problem card"),
                ("problems/ComparisonAcceptanceSpec.md", "comparison acceptance spec"),
            ]
            missing = [rel for rel, _ in required if not (ws / rel).is_file()]
            if missing:
                violations.append(
                    {
                        "path": "$.stage_guard.solution_factory",
                        "expected": "required problem factory artifacts present",
                        "actual": f"missing: {missing}",
                        "message": "MISSING_REQUIRED_PROBLEM_ARTIFACTS",
                    }
                )
        return violations

    def _append_decision_log(self, workspace_id: str, payload: Dict[str, object]) -> Path:
        out = self._decision_log_path(workspace_id)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return out

    def _append_stage_event(self, workspace_id: str, payload: Dict[str, object]) -> Path:
        out = self._stage_events_path(workspace_id)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return out

    def _run_gate(
        self,
        contract_ok: bool,
        semantic_result: Optional[str],
        assurance_result: Optional[str],
        matrix_outcome: str,
        freshness_expired: bool,
        has_recheck_trigger: bool,
        signals: Dict[str, object],
        rationale: Optional[str],
    ) -> str:
        if signals.get("force_block"):
            return "block"
        if not contract_ok:
            return "block"
        if matrix_outcome == "block":
            return "block"
        if freshness_expired:
            return "block"
        if semantic_result == "block":
            return "block"
        if assurance_result == "block":
            return "block"
        if signals.get("force_degrade"):
            if not rationale:
                raise ValueError("degrade requires explicit rationale")
            return "degrade"
        if semantic_result == "degrade":
            if not rationale:
                raise ValueError("degrade requires explicit rationale")
            return "degrade"
        if assurance_result == "degrade":
            return "degrade"
        if matrix_outcome == "degrade":
            return "degrade"
        if has_recheck_trigger:
            return "degrade"
        return "pass"

    def run_stage(
        self,
        workspace_id: str,
        stage_name: str,
        signals: Optional[Dict[str, object]] = None,
        checks_applied: Optional[List[str]] = None,
        rationale: Optional[str] = None,
    ) -> StageRunResult:
        started_at = perf_counter()
        signals = signals or {}
        checks_applied = checks_applied or [
            "artifact_contract_validation",
            "semantic_judge",
            "evidence_graph",
            "assurance_engine",
            "freshness_policy",
            "validation_matrix",
        ]

        workspace_path = self._workspace_path(workspace_id)
        artifact_path = self._resolve_artifact_path(workspace_id, stage_name)

        validation = validate_artifact_contract(
            project_root=self.project_root,
            artifact_path=artifact_path,
            workspace_path=workspace_path,
        )
        stage_guard_violations: List[Dict[str, str]] = []
        contract_ok = validation.is_valid
        doc: Optional[FrontmatterDocument] = None
        if artifact_path.is_file():
            doc = read_frontmatter_document(artifact_path)
        principles: List[Principle] = load_principles_for_stage(self.project_root, stage_name)

        # Fast-path reuse: accepted and fresh artifacts can skip expensive checks.
        if (
            doc is not None
            and validation.is_valid
            and str(doc.frontmatter.get("state") or "") == "accepted_for_next_stage"
            and not _is_valid_until_expired(str(doc.frontmatter.get("valid_until") or ""))
            and not signals.get("recheck_trigger")
            and not signals.get("force_block")
            and not signals.get("force_degrade")
            and bool(signals.get("allow_reuse", True))
        ):
            artifact = dict(doc.frontmatter)
            payload = {
                "gate_id": f"gate::{stage_name.lower()}",
                "artifact_id": artifact.get("id", "unknown"),
                "active_profile": "default",
                "checks_applied": ["artifact_reuse_short_circuit"],
                "checks_abstained": checks_applied,
                "gate_result": "pass",
                "violations": [],
                "rationale": "artifact reused from accepted_for_next_stage",
                "timestamp": _utc_now_iso(),
                "freshness_basis": artifact.get("valid_until", ""),
                "recheck_trigger": "",
                "stage_name": stage_name,
                "workspace_id": workspace_id,
                "artifact_path": str(artifact_path.relative_to(workspace_path)),
                "from_state": "accepted_for_next_stage",
                "to_state": "accepted_for_next_stage",
                "principles_loaded": [p.principle_id for p in principles],
                "semantic_judge": {"provider": "abstain", "score": None, "recommendation": "abstain", "issues": []},
                "evidence_graph": {"claims": 0, "edges": 0, "graph_path": "", "index_path": "", "inherited_epistemic_status": artifact.get("epistemic_status", "")},
                "assurance_engine": {"level": artifact.get("assurance_level", "medium"), "score": None, "recommendation": "abstain", "issues": []},
                "freshness": {"is_expired": False, "refresh": {}},
                "validation_matrix": {
                    "outcome": "pass",
                    "waive_used": False,
                    "waive_note": "",
                    "reentry_trigger": "",
                    "reentry_target_stage": "",
                    "findings": [],
                },
                "reused_artifact": True,
            }
            log_path = self._append_decision_log(workspace_id, payload)
            self._append_stage_event(
                workspace_id,
                {
                    "timestamp": _utc_now_iso(),
                    "workspace_id": workspace_id,
                    "stage_name": stage_name,
                    "artifact_path": str(artifact_path.relative_to(workspace_path)),
                    "gate_result": "pass",
                    "from_state": "accepted_for_next_stage",
                    "to_state": "accepted_for_next_stage",
                    "duration_ms": round((perf_counter() - started_at) * 1000, 3),
                    "reused_artifact": True,
                    "reason": "artifact_reuse_short_circuit",
                },
            )
            return StageRunResult(
                workspace_id=workspace_id,
                stage_name=stage_name,
                artifact_id=str(artifact.get("id", "unknown")),
                artifact_path=str(artifact_path),
                previous_state="accepted_for_next_stage",
                new_state="accepted_for_next_stage",
                gate_result="pass",
                decision_log_path=str(log_path),
            )

        evidence_claims = 0
        evidence_edges = 0
        evidence_graph_path = ""
        evidence_index_path = ""
        inherited_epistemic_status = ""
        freshness_expired = False
        refresh_info: Dict[str, str] = {}
        if doc is not None and validation.is_valid:
            graph = build_and_persist_evidence_graph(
                workspace_path=workspace_path,
                artifact_path=artifact_path,
                frontmatter=doc.frontmatter,
                body_text=doc.body,
            )
            evidence_claims = graph.claim_count
            evidence_edges = graph.edge_count
            evidence_graph_path = graph.graph_markdown_path
            evidence_index_path = graph.graph_index_path
            inherited_epistemic_status = graph.inferred_epistemic_status
            if graph.untraceable_decision_claims > 0:
                stage_guard_violations.append(
                    {
                        "path": "$.evidence.claims",
                        "expected": "decision_grade claim traceable to refs",
                        "actual": f"untraceable_decision_claims={graph.untraceable_decision_claims}",
                        "message": "UNTRACEABLE_DECISION_CLAIMS",
                    }
                )

            current_epi = str(doc.frontmatter.get("epistemic_status") or "")
            if inherited_epistemic_status and inherited_epistemic_status != current_epi:
                doc.frontmatter["epistemic_status"] = inherited_epistemic_status

            if _is_valid_until_expired(str(doc.frontmatter.get("valid_until") or "")):
                freshness_expired = True
                doc.frontmatter["state"] = "expired"
                doc.frontmatter["updated_at"] = _utc_now_iso()
                doc.frontmatter["gate_status"] = "block"

            if freshness_expired or bool(signals.get("recheck_trigger")):
                refresh_info = register_refresh_event(
                    workspace_path=workspace_path,
                    stage_name=stage_name,
                    artifact_rel_path=str(artifact_path.relative_to(workspace_path)),
                    reason="valid_until expired" if freshness_expired else "context recheck trigger",
                    trigger=str(signals.get("recheck_trigger") or ("expired_valid_until" if freshness_expired else "manual")),
                )

            write_frontmatter_document(artifact_path, doc)

        stage_guard_violations = self._stage_specific_violations(workspace_id, stage_name) + stage_guard_violations
        contract_ok = validation.is_valid and not stage_guard_violations

        assurance_level = ""
        assurance_score = None
        assurance_result = None
        assurance_issues: List[Dict[str, str]] = []
        if doc is not None:
            assr = evaluate_assurance(doc.frontmatter)
            assurance_level = assr.level
            assurance_score = assr.score
            assurance_result = assr.recommendation
            freshness_expired = freshness_expired or assr.is_expired
            assurance_issues = [
                {"code": i.code, "message": i.message, "severity": i.severity} for i in assr.issues
            ]

        semantic_result = None
        semantic_issues: List[Dict[str, str]] = []
        semantic_provider = ""
        semantic_score = None
        if doc is not None and not signals.get("skip_semantic_checks"):
            sem = run_semantic_judge(
                stage_name=stage_name,
                artifact_path=artifact_path,
                frontmatter=doc.frontmatter,
                body_text=doc.body,
                principles=principles,
                mode=str(signals.get("semantic_judge_mode") or ""),
            )
            semantic_result = sem.recommendation
            semantic_provider = sem.provider
            semantic_score = sem.score
            semantic_issues = [
                {"code": i.code, "message": i.message, "severity": i.severity} for i in sem.issues
            ]

        matrix = evaluate_validation_matrix(
            workspace_path=workspace_path,
            stage_name=stage_name,
            artifact_path=artifact_path,
            frontmatter=(doc.frontmatter if doc is not None else {}),
            structural_issues=[
                {
                    "path": issue.path,
                    "expected": issue.expected,
                    "actual": issue.actual,
                    "message": issue.message,
                }
                for issue in validation.issues
            ]
            + stage_guard_violations,
            semantic_issues=semantic_issues,
            assurance_issues=assurance_issues,
            signals=signals,
        )
        if matrix.reentry_trigger and not signals.get("recheck_trigger"):
            signals = dict(signals)
            signals["recheck_trigger"] = matrix.reentry_trigger
            refresh_info = register_refresh_event(
                workspace_path=workspace_path,
                stage_name=stage_name,
                artifact_rel_path=str(artifact_path.relative_to(workspace_path)),
                reason="impact re-entry trigger",
                trigger=matrix.reentry_trigger,
            )

        gate_result = self._run_gate(
            contract_ok=contract_ok,
            semantic_result=semantic_result,
            assurance_result=assurance_result,
            matrix_outcome=matrix.outcome,
            freshness_expired=freshness_expired,
            has_recheck_trigger=bool(signals.get("recheck_trigger")),
            signals=signals,
            rationale=rationale,
        )

        artifact = dict(doc.frontmatter) if doc is not None else {}
        prev_state = str(artifact.get("state") or "draft")

        if validation.is_valid:
            next_state = suggest_next_state(prev_state, gate_result)
        else:
            # Keep invalid artifacts unchanged and only emit gate block in DecisionLog.
            next_state = prev_state

        if validation.is_valid and doc is not None and matrix.waive_used:
            apply_transition(
                artifact,
                "waived",
                context={
                    "policy_id": str(signals.get("waive_policy_id") or ""),
                    "owner": str(signals.get("waive_owner") or ""),
                    "rationale": str(signals.get("waive_rationale") or matrix.waive_note),
                },
            )
            artifact["gate_status"] = "waived"
            doc = FrontmatterDocument(frontmatter=artifact, body=doc.body)
            write_frontmatter_document(artifact_path, doc)
            next_state = "waived"
        elif validation.is_valid and doc is not None and next_state != prev_state:
            apply_transition(artifact, next_state, context={"gate_result": gate_result})
            artifact["gate_status"] = gate_result
            doc = FrontmatterDocument(frontmatter=artifact, body=doc.body)
            write_frontmatter_document(artifact_path, doc)

        violations = [
            {
                "path": issue.path,
                "expected": issue.expected,
                "actual": issue.actual,
                "message": issue.message,
            }
            for issue in validation.issues
        ]
        violations.extend(stage_guard_violations)
        violations.extend(
            {
                "path": "$.assurance",
                "expected": "assurance policy compliance",
                "actual": issue["code"],
                "message": issue["message"],
            }
            for issue in assurance_issues
            if issue["severity"] in {"high", "medium"}
        )
        violations.extend(
            {
                "path": f.path,
                "expected": "validation matrix pass/degrade/waive policy",
                "actual": f.code,
                "message": f.message,
            }
            for f in matrix.findings
            if f.severity in {"hard_fail", "warning"}
        )
        checks_abstained: List[str] = []

        if signals.get("skip_semantic_checks"):
            checks_abstained.append("semantic_judge")

        payload = {
            "gate_id": f"gate::{stage_name.lower()}",
            "artifact_id": artifact.get("id", "unknown"),
            "active_profile": "default",
            "checks_applied": checks_applied,
            "checks_abstained": checks_abstained,
            "gate_result": gate_result,
            "violations": violations,
            "rationale": rationale or "",
            "timestamp": _utc_now_iso(),
            "freshness_basis": artifact.get("valid_until", ""),
            "recheck_trigger": signals.get("recheck_trigger", ""),
            "stage_name": stage_name,
            "workspace_id": workspace_id,
            "artifact_path": str(artifact_path.relative_to(workspace_path)),
            "from_state": prev_state,
            "to_state": next_state,
            "principles_loaded": [p.principle_id for p in principles],
            "semantic_judge": {
                "provider": semantic_provider,
                "score": semantic_score,
                "recommendation": semantic_result or "abstain",
                "issues": semantic_issues,
            },
            "evidence_graph": {
                "claims": evidence_claims,
                "edges": evidence_edges,
                "graph_path": evidence_graph_path,
                "index_path": evidence_index_path,
                "inherited_epistemic_status": inherited_epistemic_status or artifact.get("epistemic_status", ""),
            },
            "assurance_engine": {
                "level": assurance_level,
                "score": assurance_score,
                "recommendation": assurance_result or "abstain",
                "issues": assurance_issues,
            },
            "freshness": {
                "is_expired": freshness_expired,
                "refresh": refresh_info,
            },
            "validation_matrix": {
                "outcome": matrix.outcome,
                "waive_used": matrix.waive_used,
                "waive_note": matrix.waive_note,
                "reentry_trigger": matrix.reentry_trigger,
                "reentry_target_stage": matrix.reentry_target_stage,
                "findings": [
                    {
                        "code": f.code,
                        "severity": f.severity,
                        "message": f.message,
                        "path": f.path,
                        "waivable": f.waivable,
                    }
                    for f in matrix.findings
                ],
            },
        }
        log_path = self._append_decision_log(workspace_id, payload)
        self._append_stage_event(
            workspace_id,
            {
                "timestamp": _utc_now_iso(),
                "workspace_id": workspace_id,
                "stage_name": stage_name,
                "artifact_path": str(artifact_path.relative_to(workspace_path)),
                "gate_result": gate_result,
                "from_state": prev_state,
                "to_state": next_state,
                "duration_ms": round((perf_counter() - started_at) * 1000, 3),
                "reused_artifact": False,
                "recheck_trigger": signals.get("recheck_trigger", ""),
                "waive_used": matrix.waive_used,
            },
        )

        return StageRunResult(
            workspace_id=workspace_id,
            stage_name=stage_name,
            artifact_id=str(artifact.get("id", "unknown")),
            artifact_path=str(artifact_path),
            previous_state=prev_state,
            new_state=next_state,
            gate_result=gate_result,
            decision_log_path=str(log_path),
        )
