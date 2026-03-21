from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class CharacteristicIssue:
    code: str
    message: str
    severity: str  # low|medium|high
    line: str


CHR_RE = re.compile(r"\bCHR-[A-Z0-9_-]+\b", re.IGNORECASE)
TARGET_MARKERS = ("target", "should be", "must be", "должен быть", "целев", "норма")
OBSERVED_MARKERS = ("current", "now", "observed", "сейчас", "теку", "факт", "is ", "=")
DERIVED_MARKERS = ("derived", "computed", "расчет", "derived_metric", "оценоч")


def _statement_lines(body_text: str) -> List[str]:
    out: List[str] = []
    for raw in body_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("#", "---")):
            continue
        out.append(line[2:].strip() if line.startswith("- ") else line)
    return out


def _has_any(text: str, markers: tuple[str, ...]) -> bool:
    low = text.lower()
    return any(marker in low for marker in markers)


def validate_characteristic_legality(body_text: str) -> List[CharacteristicIssue]:
    issues: List[CharacteristicIssue] = []
    for line in _statement_lines(body_text):
        if not CHR_RE.search(line):
            continue
        has_target = _has_any(line, TARGET_MARKERS)
        has_observed = _has_any(line, OBSERVED_MARKERS)
        has_derived = _has_any(line, DERIVED_MARKERS)
        if has_target and has_observed:
            issues.append(
                CharacteristicIssue(
                    code="CHR_TARGET_PRESENTED_AS_FACT",
                    message="Characteristic target is mixed with observed/factual wording",
                    severity="high",
                    line=line,
                )
            )
        elif has_target and has_derived:
            issues.append(
                CharacteristicIssue(
                    code="CHR_TARGET_AND_DERIVED_BLURRED",
                    message="Characteristic target is blurred with derived metric wording",
                    severity="medium",
                    line=line,
                )
            )
    return issues
