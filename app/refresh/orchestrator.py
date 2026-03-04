from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from app.validation.artifact_contract_validator import FrontmatterDocument, read_frontmatter_document, write_frontmatter_document

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _refresh_target(stage_name: str) -> str:
    stage = stage_name.lower()
    if stage in {"intake", "layers", "viewpoints", "characterization"}:
        return "characterization"
    if stage == "problem_factory":
        return "problem_factory"
    if stage in {"solution_factory", "reporting"}:
        return "solution_factory"
    return stage


def register_refresh_event(
    workspace_path: Path,
    stage_name: str,
    artifact_rel_path: str,
    reason: str,
    trigger: str,
) -> Dict[str, str]:
    evidence_dir = workspace_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    now = _utc_now_iso()
    target_stage = _refresh_target(stage_name)

    index_path = evidence_dir / "refresh_index.json"
    if index_path.is_file():
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    else:
        data = {}

    events = list(data.get("events", []))
    event = {
        "timestamp": now,
        "stage_name": stage_name,
        "artifact_path": artifact_rel_path,
        "reason": reason,
        "trigger": trigger,
        "refresh_target_stage": target_stage,
    }
    events.append(event)

    data = {
        "workspace_id": workspace_path.name,
        "updated_at": now,
        "events": events,
    }
    index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report_path = evidence_dir / "refresh_report.md"
    created_at = now
    report_body = "# Refresh Report\n\n"
    if report_path.is_file():
        try:
            old = read_frontmatter_document(report_path)
            report_body = old.body.rstrip() + "\n\n"
            created_at = str(old.frontmatter.get("created_at") or now)
        except Exception:
            report_body = report_path.read_text(encoding="utf-8").rstrip() + "\n\n"

    report_body += (
        f"## Refresh Event {len(events):03d}\n"
        f"- timestamp: {now}\n"
        f"- stage_name: {stage_name}\n"
        f"- artifact_path: {artifact_rel_path}\n"
        f"- reason: {reason}\n"
        f"- trigger: {trigger}\n"
        f"- refresh_target_stage: {target_stage}\n"
    )
    fm = {
        "id": f"{workspace_path.name}__refresh_report",
        "artifact_type": "refresh_report",
        "stage": "evidence",
        "state": "evidence_linked",
        "parent_refs": [artifact_rel_path],
        "source_refs": [artifact_rel_path],
        "evidence_refs": [],
        "viewpoints": [],
        "epistemic_status": "observed",
        "assurance_level": "medium",
        "valid_until": "2026-12-31",
        "owner_role": "analyst",
        "gate_status": "pending",
        "violated_principles": [],
        "next_expected_artifacts": [],
        "created_at": created_at,
        "updated_at": now,
    }
    write_frontmatter_document(report_path, FrontmatterDocument(frontmatter=fm, body=report_body))

    return {
        "refresh_report": str(report_path.relative_to(workspace_path)),
        "refresh_index": str(index_path.relative_to(workspace_path)),
        "refresh_target_stage": target_stage,
        "reason": reason,
        "trigger": trigger,
    }
