from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set


@dataclass(frozen=True)
class ContaminationIssue:
    code: str
    message: str
    severity: str  # low|medium|high
    matched_terms: List[str]


DEFAULT_DOMAIN_VOCAB: Dict[str, Set[str]] = {
    "commercial_presales_bottleneck": {"bant", "cpq", "shadow mode", "qualification", "lead", "presales", "sales funnel"},
    "industrial_transformation": {"throughput", "capex", "opex", "factory", "kiln", "wood", "plant", "production line"},
    "market_validation": {"mrr", "retention", "mau", "conversion", "buyers", "channel", "pricing", "segment"},
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


def _load_vocab_registry(workspace_path: Path) -> Dict[str, Set[str]]:
    registry: Dict[str, Set[str]] = {domain: set(terms) for domain, terms in DEFAULT_DOMAIN_VOCAB.items()}
    path = workspace_path / "analysis" / "domain_vocab.json"
    if not path.is_file():
        return registry
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return registry
    if not isinstance(raw, dict):
        return registry
    for domain, terms in raw.items():
        if isinstance(terms, list):
            registry.setdefault(str(domain), set()).update(
                str(term).strip().lower() for term in terms if str(term).strip()
            )
    return registry


def _matched_domains(low_text: str, vocab_registry: Dict[str, Set[str]], excluded_domains: Set[str]) -> Dict[str, Set[str]]:
    matched: Dict[str, Set[str]] = {}
    for domain, vocab in vocab_registry.items():
        if domain in excluded_domains:
            continue
        terms = set()
        for term in vocab:
            escaped = re.escape(term)
            if " " in term or "-" in term:
                pattern = escaped
            else:
                pattern = rf"\b{escaped}\b"
            if re.search(pattern, low_text):
                terms.add(term)
        if terms:
            matched[domain] = terms
    return matched


def _severity_for_matches(matches: Dict[str, Set[str]]) -> str:
    matched_terms = {term for terms in matches.values() for term in terms}
    if not matched_terms:
        return "low"
    if len(matches) >= 2:
        return "high"
    if len(matched_terms) >= 4:
        return "high"
    return "medium"


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
    vocab_registry = _load_vocab_registry(workspace)

    foreign_domain_matches = _matched_domains(low, vocab_registry, active)
    foreign_terms = sorted({term for terms in foreign_domain_matches.values() for term in terms})

    if not foreign_terms:
        return []
    severity = _severity_for_matches(foreign_domain_matches)
    return [
        ContaminationIssue(
            code="SEMANTIC_DOMAIN_DRIFT",
            message="Vocabulary is semantically alien to the allowed ontological domains for this case",
            severity=severity,
            matched_terms=foreign_terms,
        )
    ]
