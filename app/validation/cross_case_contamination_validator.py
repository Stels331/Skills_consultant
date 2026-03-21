from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set


@dataclass(frozen=True)
class ContaminationIssue:
    code: str
    message: str
    severity: str  # low|medium|high
    matched_terms: List[str]


DOMAIN_VOCAB: Dict[str, Set[str]] = {
    "commercial_presales_bottleneck": {"bant", "cpq", "shadow mode", "qualification", "lead", "presales", "sales funnel"},
    "industrial_transformation": {"throughput", "capex", "opex", "factory", "kiln", "wood", "plant", "production line"},
    "market_validation": {"mrr", "retention", "ma u", "conversion", "buyers", "channel", "pricing", "segment"},
    "governance_crisis": {"board", "decision rights", "owner", "governance", "trust", "alignment"},
    "service_operations": {"incident", "ticket", "service desk", "latency", "pager"},
}


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


def validate_cross_case_contamination(artifact_path: Path, body_text: str) -> List[ContaminationIssue]:
    workspace = _find_workspace_root(artifact_path)
    if workspace is None:
        return []
    profile = _load_domain_profile(workspace)
    axes = {
        str(item.get("axis"))
        for item in profile.get("domain_axes", [])
        if isinstance(item, dict) and str(item.get("axis") or "").strip()
    }
    allowed = {str(x) for x in profile.get("allowed_ontological_domains", []) if str(x).strip()}
    active = axes | allowed
    low = body_text.lower()

    foreign_terms: List[str] = []
    for domain, vocab in DOMAIN_VOCAB.items():
        if domain in active:
            continue
        foreign_terms.extend(term for term in vocab if term in low)

    if not foreign_terms:
        return []
    severity = "high" if len(set(foreign_terms)) >= 4 else "medium"
    return [
        ContaminationIssue(
            code="SEMANTIC_DOMAIN_DRIFT",
            message="Vocabulary is semantically alien to the allowed ontological domains for this case",
            severity=severity,
            matched_terms=sorted(set(foreign_terms)),
        )
    ]
