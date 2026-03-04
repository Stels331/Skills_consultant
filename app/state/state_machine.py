from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


ARTIFACT_STATES = {
    "draft",
    "shaped",
    "evidence_linked",
    "accepted_for_next_stage",
    "rework_required",
    "waived",
    "deprecated",
    "expired",
}


ALLOWED_TRANSITIONS = {
    "draft": {"shaped", "rework_required", "waived"},
    "shaped": {"evidence_linked", "rework_required", "waived"},
    "evidence_linked": {"accepted_for_next_stage", "rework_required", "waived"},
    "accepted_for_next_stage": {"deprecated", "expired", "rework_required"},
    "rework_required": {"shaped", "waived", "deprecated"},
    "waived": {"rework_required", "deprecated", "expired"},
    "deprecated": set(),
    "expired": {"shaped", "deprecated"},
}


class StateTransitionError(ValueError):
    pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_valid_state(state: str) -> bool:
    return state in ARTIFACT_STATES


def can_transition(from_state: str, to_state: str) -> bool:
    return to_state in ALLOWED_TRANSITIONS.get(from_state, set())


def suggest_next_state(current_state: str, gate_result: str) -> str:
    if gate_result == "block":
        if current_state == "expired":
            return "expired"
        return "rework_required"
    if gate_result in {"pass", "degrade"}:
        if current_state == "draft":
            return "shaped"
        if current_state == "shaped":
            return "evidence_linked"
        if current_state == "evidence_linked":
            return "accepted_for_next_stage"
    return current_state


def apply_transition(
    artifact: Dict[str, Any],
    to_state: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    context = context or {}
    from_state = artifact.get("state")

    if not is_valid_state(str(from_state)):
        raise StateTransitionError(f"Unknown source state: {from_state!r}")
    if not is_valid_state(to_state):
        raise StateTransitionError(f"Unknown target state: {to_state!r}")
    if not can_transition(str(from_state), to_state):
        raise StateTransitionError(f"Invalid transition: {from_state} -> {to_state}")

    if to_state == "waived":
        required = {"policy_id", "owner", "rationale"}
        missing = sorted(k for k in required if not context.get(k))
        if missing:
            raise StateTransitionError(
                f"Waive transition requires context fields: {', '.join(missing)}"
            )

    if to_state == "accepted_for_next_stage":
        gate_result = context.get("gate_result")
        if gate_result not in {"pass", "degrade"}:
            raise StateTransitionError(
                "accepted_for_next_stage requires gate_result in {'pass','degrade'}"
            )

    artifact["state"] = to_state
    artifact["updated_at"] = _utc_now_iso()
    return artifact
