from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class BoundaryIssue:
    code: str
    message: str
    severity: str  # low|medium|high
    line: str


LAW_MARKERS = ("law", "legal", "закон", "регламент", "норматив", "compliance")
ADMISSIBILITY_MARKERS = ("admissible", "allowed", "допуст", "gate", "admission", "приемк")
DEONTIC_MARKERS = ("must", "shall", "should", "обязан", "должен", "запрещ", "нельзя")
EVIDENCE_MARKERS = ("evidence", "source", "proof", "доказ", "evidence_ref", "source_ref", "подтверж")


def _has_any(text: str, markers: tuple[str, ...]) -> bool:
    low = text.lower()
    return any(marker in low for marker in markers)


def _statement_lines(body_text: str) -> List[str]:
    lines: List[str] = []
    for raw in body_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("#", "---")):
            continue
        if line.startswith("- "):
            line = line[2:].strip()
        lines.append(line)
    return lines


def validate_boundary_discipline(body_text: str) -> List[BoundaryIssue]:
    issues: List[BoundaryIssue] = []
    for line in _statement_lines(body_text):
        buckets = 0
        buckets += int(_has_any(line, LAW_MARKERS))
        buckets += int(_has_any(line, ADMISSIBILITY_MARKERS))
        buckets += int(_has_any(line, DEONTIC_MARKERS))
        buckets += int(_has_any(line, EVIDENCE_MARKERS))
        if buckets >= 3:
            issues.append(
                BoundaryIssue(
                    code="FPF_BOUNDARY_SOUP",
                    message="Statement mixes law, admissibility, deontic, and/or evidence concerns in one boundary clause",
                    severity="medium",
                    line=line,
                )
            )
    return issues
