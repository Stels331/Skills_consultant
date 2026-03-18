from __future__ import annotations

import re


NUMERIC_CLAIM_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:%|квт|м³|м3|дн|дней|дня|недель|тиж|months?|мес|куб)\b",
    flags=re.IGNORECASE,
)

HARD_ASSERTION_MARKERS = [
    "верифиц",
    "математическ",
    "гарантирован",
    "неминуем",
    "банкрот",
    "физически останов",
    "строго =",
    "обязательно",
]

SOFTENING_MARKERS = [
    "гипотез",
    "hypothesis",
    "estimate",
    "оценоч",
    "scenario",
    "сценар",
    "предполож",
    "requires verification",
    "требует проверки",
    "интерпретац",
]


def _should_soften_line(line: str) -> bool:
    low = line.lower()
    if any(marker in low for marker in SOFTENING_MARKERS):
        return False
    return bool(NUMERIC_CLAIM_RE.search(low) or any(marker in low for marker in HARD_ASSERTION_MARKERS))


def soften_unanchored_claims(text: str) -> str:
    out = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            out.append(raw)
            continue
        if _should_soften_line(stripped):
            prefix = "Гипотеза/оценка: "
            if stripped.startswith(("- ", "* ")):
                out.append(raw.replace(stripped[:2], stripped[:2] + prefix, 1))
            else:
                out.append(prefix + raw)
            continue
        out.append(raw)
    return "\n".join(out)
