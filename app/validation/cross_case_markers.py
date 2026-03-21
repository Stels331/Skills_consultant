from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class CrossCaseMarkerIssue:
    code: str
    message: str
    severity: str  # low|medium|high
    markers: List[str]


def _find_workspace_root(artifact_path: Path) -> Optional[Path]:
    current = artifact_path.resolve().parent
    for candidate in [current, *current.parents]:
        if (candidate / "analysis" / "domain_profile.json").is_file():
            return candidate
    return None


def _load_domain_profile(workspace_path: Path) -> Dict[str, object]:
    path = workspace_path / "analysis" / "domain_profile.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def check_cross_case_markers(artifact_path: Path, body_text: str) -> List[CrossCaseMarkerIssue]:
    workspace_path = _find_workspace_root(artifact_path)
    if workspace_path is None:
        return []

    profile = _load_domain_profile(workspace_path)
    markers = [str(x) for x in profile.get("forbidden_template_markers", []) if str(x).strip()]
    allowed = {str(x) for x in profile.get("allowed_ontological_domains", []) if str(x).strip()}
    axes = {
        str(item.get("axis"))
        for item in profile.get("domain_axes", [])
        if isinstance(item, dict) and str(item.get("axis") or "").strip()
    }
    active_domains = allowed | axes

    # If presales domain is explicitly active, do not treat its terminology as contamination.
    if "commercial_presales_bottleneck" in active_domains:
        return []

    low = body_text.lower()
    matched = [marker for marker in markers if marker.lower() in low]
    if not matched:
        return []

    return [
        CrossCaseMarkerIssue(
            code="CROSS_CASE_CONTAMINATION",
            message="Detected domain markers that are not allowed by current domain profile",
            severity="medium",
            markers=matched,
        )
    ]
