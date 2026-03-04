from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.validation.artifact_contract_validator import FrontmatterDocument, write_frontmatter_document


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_frontmatter(
    artifact_id: str,
    artifact_type: str,
    stage: str,
    state: str = "draft",
    parent_refs: Optional[List[str]] = None,
    source_refs: Optional[List[str]] = None,
    evidence_refs: Optional[List[str]] = None,
    viewpoints: Optional[List[str]] = None,
    epistemic_status: str = "observed",
    assurance_level: str = "medium",
    valid_until: str = "2026-12-31",
    owner_role: str = "analyst",
    gate_status: str = "pending",
    violated_principles: Optional[List[str]] = None,
    next_expected_artifacts: Optional[List[str]] = None,
) -> Dict[str, object]:
    now = _now_iso()
    return {
        "id": artifact_id,
        "artifact_type": artifact_type,
        "stage": stage,
        "state": state,
        "parent_refs": parent_refs or [],
        "source_refs": source_refs or [],
        "evidence_refs": evidence_refs or [],
        "viewpoints": viewpoints or [],
        "epistemic_status": epistemic_status,
        "assurance_level": assurance_level,
        "valid_until": valid_until,
        "owner_role": owner_role,
        "gate_status": gate_status,
        "violated_principles": violated_principles or [],
        "next_expected_artifacts": next_expected_artifacts or [],
        "created_at": now,
        "updated_at": now,
    }


def write_markdown_artifact(path: Path, frontmatter: Dict[str, object], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_frontmatter_document(path, FrontmatterDocument(frontmatter=frontmatter, body=body))
