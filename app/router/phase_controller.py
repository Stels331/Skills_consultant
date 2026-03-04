from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from app.router.context_budget_enforcer import ContextBudgetEnforcer
from app.router.transition_logic import can_transition, is_valid_phase, suggest_next_phase
from app.validation.schema_validator import validate_workspace


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, payload: Dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(path)


@dataclass(frozen=True)
class TransitionResult:
    from_phase: str
    to_phase: str
    transition_at: str
    warning: bool
    compression_required: bool
    effective_tokens: int


class PhaseController:
    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.enforcer = ContextBudgetEnforcer()

    def _workspace_path(self, workspace_id: str) -> Path:
        return self.project_root / "cases" / workspace_id

    def _session_path(self, workspace_id: str) -> Path:
        return self._workspace_path(workspace_id) / "state" / "session_state.json"

    def _changelog_path(self, workspace_id: str) -> Path:
        return self._workspace_path(workspace_id) / "state" / "version_changelog.json"

    def get_current_phase(self, workspace_id: str) -> str:
        session = _read_json(self._session_path(workspace_id))
        return session["current_phase"]

    def _guard_artifacts(self, workspace_id: str, target_phase: str) -> None:
        if target_phase in {"EPISTEMIC_ANALYSIS", "PROBLEM_FACTORY", "SOLUTION_FACTORY", "REPORTING"}:
            workspace = self._workspace_path(workspace_id)
            results = validate_workspace(self.project_root, workspace)
            invalid = [name for name, result in results.items() if not result.is_valid]
            if invalid:
                raise ValueError(f"Schema guard failed before {target_phase}: {invalid}")

    def _guard_evidence(self, target_phase: str, signals: Dict[str, bool]) -> None:
        if target_phase == "SOLUTION_FACTORY" and not signals.get("evidence_ready", False):
            raise ValueError("Evidence gate failed: evidence_ready=false")

    def _budget_enforcer_for_workspace(self, workspace_id: str) -> ContextBudgetEnforcer:
        metadata_path = self._workspace_path(workspace_id) / "workspace_metadata.json"
        metadata = _read_json(metadata_path)
        cfg = metadata.get("context_budget", {})
        max_tokens = cfg.get("max_context_tokens")
        warning = cfg.get("warning_threshold")
        if max_tokens is None and warning is None:
            return self.enforcer
        return ContextBudgetEnforcer(max_context_tokens=max_tokens, warning_threshold=warning)

    def _append_transition_event(self, workspace_id: str, old: str, new: str) -> None:
        changelog_path = self._changelog_path(workspace_id)
        log = _read_json(changelog_path)
        events = log.setdefault("events", [])
        events.append(
            {
                "event_type": "ROUTER_PHASE_CHANGED",
                "timestamp": _utc_now_iso(),
                "details": {"from": old, "to": new},
            }
        )
        log["updated_at"] = _utc_now_iso()
        _write_json(changelog_path, log)

    def transition(
        self,
        workspace_id: str,
        next_phase: Optional[str] = None,
        signals: Optional[Dict[str, bool]] = None,
        required_tokens: int = 0,
    ) -> TransitionResult:
        signals = signals or {}
        session_path = self._session_path(workspace_id)
        session = _read_json(session_path)

        current = session["current_phase"]
        target = next_phase or suggest_next_phase(current, signals)

        if not is_valid_phase(target):
            raise ValueError(f"Unknown phase: {target}")
        if not can_transition(current, target):
            raise ValueError(f"Invalid transition: {current} -> {target}")

        self._guard_artifacts(workspace_id, target)
        self._guard_evidence(target, signals)

        enforcer = self._budget_enforcer_for_workspace(workspace_id)
        budget = enforcer.check_budget(required_tokens)

        now = _utc_now_iso()
        session["last_phase"] = current
        session["current_phase"] = target
        session["phase_updated_at"] = now
        session["context_budget"] = {
            "requested_tokens": budget.requested_tokens,
            "effective_tokens": budget.effective_tokens,
            "warning": budget.warning,
            "compression_required": budget.compression_required,
        }

        _write_json(session_path, session)
        self._append_transition_event(workspace_id, current, target)

        return TransitionResult(
            from_phase=current,
            to_phase=target,
            transition_at=now,
            warning=budget.warning,
            compression_required=budget.compression_required,
            effective_tokens=budget.effective_tokens,
        )
