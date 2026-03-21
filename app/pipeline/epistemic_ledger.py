from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


VALID_EVENT_TYPES = {
    "claim_created",
    "claim_promoted",
    "claim_degraded",
    "constraint_compiled",
    "conflict_marked",
    "projection_emitted",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_event(event: Dict[str, object]) -> None:
    required = ["event_type", "timestamp", "workspace_id", "stage", "target_id", "payload"]
    missing = [key for key in required if key not in event]
    if missing:
        raise ValueError(f"INVALID_EPISTEMIC_EVENT_MISSING_FIELDS: {missing}")
    if str(event["event_type"]) not in VALID_EVENT_TYPES:
        raise ValueError(f"INVALID_EPISTEMIC_EVENT_TYPE: {event['event_type']}")
    if not isinstance(event["payload"], dict):
        raise ValueError("INVALID_EPISTEMIC_EVENT_PAYLOAD")


def append_event(path: Path, event: Dict[str, object]) -> None:
    validate_event(event)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def build_event(
    *,
    event_type: str,
    workspace_id: str,
    stage: str,
    target_id: str,
    payload: Dict[str, object],
) -> Dict[str, object]:
    event = {
        "event_type": event_type,
        "timestamp": _utc_now_iso(),
        "workspace_id": workspace_id,
        "stage": stage,
        "target_id": target_id,
        "payload": payload,
    }
    validate_event(event)
    return event


def replay_events(path: Path) -> List[Dict[str, object]]:
    if not path.is_file():
        return []
    events: List[Dict[str, object]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        event = json.loads(raw)
        validate_event(event)
        events.append(event)
    return events
