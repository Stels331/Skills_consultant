from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List


DOMAIN_RULES = [
    {
        "name": "industrial_transformation",
        "keywords": [
            "plant",
            "factory",
            "production",
            "manufacturing",
            "сырье",
            "цех",
            "завод",
            "термо",
            "сушка",
            "throughput",
            "capex",
            "opex",
        ],
        "reasoning_mode": "strategic_reframing",
    },
    {
        "name": "governance_crisis",
        "keywords": [
            "board",
            "trust",
            "правление",
            "довер",
            "конфликт",
            "owner",
            "ownership",
            "accountable",
            "decision right",
        ],
        "reasoning_mode": "governance_repair",
    },
    {
        "name": "market_validation",
        "keywords": [
            "client",
            "market",
            "customer",
            "price",
            "channel",
            "воронк",
            "клиент",
            "рын",
            "спрос",
            "продаж",
        ],
        "reasoning_mode": "market_validation",
    },
    {
        "name": "operations_bottleneck",
        "keywords": [
            "bottleneck",
            "queue",
            "sla",
            "handoff",
            "routing",
            "process",
            "узкое место",
            "очеред",
            "маршрут",
            "срок",
            "handoff",
        ],
        "reasoning_mode": "operational_bottleneck",
    },
    {
        "name": "commercial_presales_bottleneck",
        "keywords": [
            "quote",
            "quotation",
            "presales",
            "lead",
            "cpq",
            "bant",
            "technical director",
            "коммерческ",
            "заявк",
            "пресейл",
            "кп",
        ],
        "reasoning_mode": "commercial_presales",
    },
]


def _read_workspace_text(workspace: Path) -> str:
    parts: List[str] = []
    for rel in [
        "raw/case_input.md",
        "intake/normalized_case.md",
        "layers/layer_1_business_model.md",
        "layers/layer_2_requirements.md",
        "layers/layer_3_functional_model.md",
        "layers/layer_4_allocation_model.md",
    ]:
        path = workspace / rel
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts).lower()


def _score_axis(text: str, keywords: List[str]) -> int:
    return sum(1 for keyword in keywords if keyword in text)


def build_domain_profile(project_root: Path, workspace_id: str) -> Dict[str, object]:
    workspace = project_root / "cases" / workspace_id
    analysis_dir = workspace / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    case_text = _read_workspace_text(workspace)
    axes = []
    for rule in DOMAIN_RULES:
        score = _score_axis(case_text, rule["keywords"])
        if score <= 0:
            continue
        axes.append(
            {
                "axis": rule["name"],
                "score": score,
                "confidence": min(0.95, 0.4 + score * 0.1),
                "reasoning_mode": rule["reasoning_mode"],
            }
        )

    if not axes:
        axes.append(
            {
                "axis": "general_business_case",
                "score": 1,
                "confidence": 0.4,
                "reasoning_mode": "general_diagnostic",
            }
        )

    axes.sort(key=lambda item: item["score"], reverse=True)
    reasoning_modes: List[str] = []
    for axis in axes:
        mode = str(axis["reasoning_mode"])
        if mode not in reasoning_modes:
            reasoning_modes.append(mode)

    profile = {
        "workspace_id": workspace_id,
        "version": 1,
        "domain_axes": axes,
        "primary_modes": reasoning_modes[:2],
        "secondary_modes": reasoning_modes[2:],
        "allowed_ontological_domains": [axis["axis"] for axis in axes[:3]],
        "forbidden_template_markers": [
            "BANT",
            "Shadow Mode",
            "CPQ",
            "L1 estimator",
        ],
        "reasoning_scope": "mixed" if len(axes) > 1 else "single",
    }

    target = analysis_dir / "domain_profile.json"
    target.write_text(json.dumps(profile, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return profile
