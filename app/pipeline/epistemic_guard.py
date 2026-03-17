from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List


GAP_CUES = [
    "gap",
    "unknown",
    "not provided",
    "not defined",
    "not specified",
    "unspecified",
    "missing",
    "отсутств",
    "не указ",
    "неизвест",
    "не хватает",
]

CRITICAL_DIMENSIONS = {
    "flow_volume": ["volume", "flow", "queue", "поток", "объем", "очеред"],
    "conversion": ["conversion", "конверс", "reject", "отказ", "churn"],
    "request_mix": ["standard", "non-standard", "типов", "нестандарт", "segment", "mix"],
    "presales_economics": ["cost", "roi", "margin", "econom", "стоим", "марж", "себестоим"],
    "classification_logic": ["triage", "brief", "routing", "qualif", "бриф", "маршрути", "квалиф"],
}


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _lines(text: str) -> List[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def assess_decision_readiness(workspace: Path) -> Dict[str, object]:
    corpus_parts = [
        _read(workspace / "raw" / "case_input.md"),
        _read(workspace / "layers" / "layer_1_business_model.md"),
        _read(workspace / "problems" / "SelectedProblemCard.md"),
        _read(workspace / "problems" / "ComparisonAcceptanceSpec.md"),
        _read(workspace / "dialogue" / "question_queue.json"),
    ]
    corpus = "\n".join(part for part in corpus_parts if part)
    low = corpus.lower()
    lines = _lines(corpus)

    gap_hits = sum(low.count(marker) for marker in GAP_CUES)
    numeric_signals = len(re.findall(r"\b\d+(?:[.,]\d+)?%?\b", corpus))

    missing_dimensions: List[str] = []
    for dimension, keywords in CRITICAL_DIMENSIONS.items():
        relevant = [line.lower() for line in lines if any(keyword in line.lower() for keyword in keywords)]
        if not relevant:
            missing_dimensions.append(dimension)
            continue
        if all(any(cue in line for cue in GAP_CUES) or not re.search(r"\b\d+(?:[.,]\d+)?%?\b", line) for line in relevant):
            missing_dimensions.append(dimension)

    insufficient = len(missing_dimensions) >= 3 or (gap_hits >= 4 and numeric_signals < 8)
    return {
        "insufficient_for_decision": insufficient,
        "missing_dimensions": missing_dimensions,
        "gap_hits": gap_hits,
        "numeric_signals": numeric_signals,
    }

