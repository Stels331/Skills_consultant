from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass(frozen=True)
class ComparisonIssue:
    code: str
    message: str
    severity: str  # low|medium|high


HIDDEN_SCALARIZATION_MARKERS = (
    "weighted score",
    "total score",
    "общий балл",
    "суммарный балл",
    "rank alternatives by one score",
    "единый итоговый балл",
)
COMPARABILITY_MARKERS = (
    "comparison frame",
    "comparability basis",
    "same baseline",
    "reference plane",
    "admissibility of alternatives",
    "comparator basis",
)


def _has_any(text: str, markers: tuple[str, ...]) -> bool:
    low = text.lower()
    return any(marker in low for marker in markers)


def _has_explicit_basis(text: str) -> bool:
    low = text.lower()
    for marker in COMPARABILITY_MARKERS:
        if marker not in low:
            continue
        if re.search(rf"without\s+(?:\w+\s+){{0,3}}{re.escape(marker)}", low):
            continue
        if re.search(rf"no\s+(?:\w+\s+){{0,3}}{re.escape(marker)}", low):
            continue
        return True
    return False


def validate_comparison_legality(parity_text: str, selected_text: str, acceptance_spec_text: str) -> List[ComparisonIssue]:
    issues: List[ComparisonIssue] = []
    combined = "\n".join([parity_text, selected_text, acceptance_spec_text])

    if _has_any(combined, HIDDEN_SCALARIZATION_MARKERS) and not _has_explicit_basis(combined):
        issues.append(
            ComparisonIssue(
                code="HIDDEN_SCALARIZATION",
                message="Comparison appears to collapse alternatives into a hidden single-score scalarization without explicit comparability basis",
                severity="high",
            )
        )

    selected_ids = set(re.findall(r"\bsol_[a-z0-9_]+\b", selected_text.lower()))
    if len(selected_ids) > 3:
        issues.append(
            ComparisonIssue(
                code="SELECTION_NOT_SET_BOUNDED",
                message="Selection output exceeds allowed bounded portfolio size",
                severity="medium",
            )
        )
    return issues


def validate_selection_workspace(workspace: Path) -> List[ComparisonIssue]:
    parity = (workspace / "solutions" / "ParityReport.md").read_text(encoding="utf-8") if (workspace / "solutions" / "ParityReport.md").is_file() else ""
    selected = (workspace / "solutions" / "SelectedSolutions.md").read_text(encoding="utf-8") if (workspace / "solutions" / "SelectedSolutions.md").is_file() else ""
    spec = (workspace / "problems" / "ComparisonAcceptanceSpec.md").read_text(encoding="utf-8") if (workspace / "problems" / "ComparisonAcceptanceSpec.md").is_file() else ""
    return validate_comparison_legality(parity, selected, spec)
