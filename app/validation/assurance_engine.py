from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass(frozen=True)
class AssuranceIssue:
    code: str
    message: str
    severity: str  # low|medium|high


@dataclass(frozen=True)
class AssuranceResult:
    level: str  # low|medium|high
    score: float
    recommendation: str  # pass|degrade|block
    issues: List[AssuranceIssue]
    is_expired: bool


BASE_SCORE = {
    "low": 0.35,
    "medium": 0.6,
    "high": 0.85,
}


def _parse_valid_until(raw: str, now: datetime) -> tuple[bool, bool]:
    if not raw:
        return False, True
    txt = str(raw).strip()
    try:
        if len(txt) == 10:
            dt = datetime.fromisoformat(txt + "T00:00:00+00:00")
        else:
            dt = datetime.fromisoformat(txt.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return dt < now, False
    except ValueError:
        return False, True


def _level_from_score(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.55:
        return "medium"
    return "low"


def evaluate_assurance(frontmatter: Dict[str, object], now: Optional[datetime] = None) -> AssuranceResult:
    now = now or datetime.now(timezone.utc)
    issues: List[AssuranceIssue] = []

    declared = str(frontmatter.get("assurance_level") or "medium").lower()
    if declared not in BASE_SCORE:
        declared = "medium"

    epi = str(frontmatter.get("epistemic_status") or "inferred").lower()
    source_refs = list(frontmatter.get("source_refs") or [])
    evidence_refs = list(frontmatter.get("evidence_refs") or [])

    has_source = len(source_refs) > 0
    has_evidence = len(evidence_refs) > 0

    score = BASE_SCORE[declared]

    is_expired, invalid_valid_until = _parse_valid_until(str(frontmatter.get("valid_until") or ""), now)
    if invalid_valid_until:
        issues.append(AssuranceIssue("INVALID_VALID_UNTIL", "valid_until is missing or invalid", "medium"))
        score -= 0.15
    if is_expired:
        issues.append(AssuranceIssue("EXPIRED_ARTIFACT", "artifact valid_until has expired", "high"))
        score -= 0.35

    if has_source:
        score += 0.1
    else:
        issues.append(AssuranceIssue("MISSING_SOURCE_REFS", "source_refs are empty", "high"))
        score -= 0.25

    if has_evidence:
        score += 0.1
    elif epi in {"decision_grade", "operationally_confirmed"}:
        issues.append(AssuranceIssue("MISSING_EVIDENCE_REFS", "high-confidence epistemic claims require evidence_refs", "high"))
        score -= 0.35

    if epi == "hypothesis":
        score -= 0.1

    score = max(0.0, min(1.0, score))
    computed_level = _level_from_score(score)

    high_count = sum(1 for i in issues if i.severity == "high")

    recommendation = "pass"
    if declared == "high" and (not has_source or not has_evidence):
        recommendation = "block"
    elif epi == "decision_grade" and not has_evidence:
        recommendation = "block"
    elif is_expired:
        recommendation = "block"
    elif high_count > 0:
        recommendation = "degrade"
    elif computed_level == "low" and declared in {"medium", "high"}:
        recommendation = "degrade"

    return AssuranceResult(
        level=computed_level,
        score=round(score, 3),
        recommendation=recommendation,
        issues=issues,
        is_expired=is_expired,
    )
