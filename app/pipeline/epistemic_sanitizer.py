from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable


NUMERIC_CLAIM_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?(?:\s*[-–]\s*\d+(?:[.,]\d+)?)?\s*(?:%|квт(?:/ч)?|квтч|м³|м3|дн|дней|дня|недель|тиж|months?|мес|куб|квартал(?:а|ов)?|quarters?)(?=$|[^\w/])",
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
    "гипотеза/оценка",
    "estimate",
    "оценоч",
    "scenario",
    "сценар",
    "предполож",
    "рабоч",
    "working assumption",
    "requires verification",
    "требует проверки",
    "интерпретац",
    "source:",
    "source_ref",
    "evidence_ref",
]

DOMAIN_TERM_REWRITES: dict[str, tuple[tuple[str, str], ...]] = {
    "service_operations": (
        ("board decision latency", "delay of board decisions"),
        ("latency управленческих решений", "задержка управленческих решений"),
        ("decision latency", "decision delay"),
        ("service desk", "операционный контур поддержки"),
        ("ticket", "операционный запрос"),
        ("incident", "сбой"),
        ("pager", "срочный канал эскалации"),
        ("latency", "delay"),
    ),
}

GOLDILOCKS_SIGNAL_BULLETS: dict[str, tuple[str, ...]] = {
    "facts": (
        "Симптом: система готовится к запуску без подтвержденной положительной unit economics и без закрытия ресурсных ограничений.",
    ),
    "derived_thresholds": (
        "Constraint/ограничение: запуск допустим только внутри лимитов ликвидности, мощности и физически подтвержденного отвода отходов.",
    ),
    "hypotheses_to_validate": (
        "Acceptance/критерий приемки: решение считается жизнеспособным только после подтверждения положительной маржи, легального отвода отходов и обеспеченного источника энергии.",
    ),
}


def _should_soften_line(line: str) -> bool:
    low = line.lower()
    if any(marker in low for marker in SOFTENING_MARKERS):
        return False
    return bool(NUMERIC_CLAIM_RE.search(low) or any(marker in low for marker in HARD_ASSERTION_MARKERS))


def detect_unanchored_claim_lines(text: str) -> list[str]:
    findings = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if _should_soften_line(stripped):
            findings.append(stripped)
    return findings


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


def _load_domain_profile(workspace_path: Path | None) -> dict[str, object]:
    if workspace_path is None:
        return {}
    path = workspace_path / "analysis" / "domain_profile.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _allowed_domains(workspace_path: Path | None) -> set[str]:
    profile = _load_domain_profile(workspace_path)
    allowed = {
        str(item).strip()
        for item in profile.get("allowed_ontological_domains", [])
        if str(item).strip()
    }
    axes = {
        str(item.get("axis")).strip()
        for item in profile.get("domain_axes", [])
        if isinstance(item, dict) and str(item.get("axis") or "").strip()
    }
    return allowed | axes


def normalize_domain_language(text: str, workspace_path: Path | None = None) -> str:
    out = text
    allowed = _allowed_domains(workspace_path)
    for domain, rewrites in DOMAIN_TERM_REWRITES.items():
        if domain in allowed:
            continue
        for source, target in rewrites:
            out = re.sub(re.escape(source), target, out, flags=re.IGNORECASE)
    return out


def _append_section_bullets(text: str, section_name: str, bullets: Iterable[str]) -> str:
    lines = text.splitlines()
    start_idx = None
    end_idx = len(lines)
    header = f"## {section_name}"
    for idx, raw in enumerate(lines):
        if raw.strip().lower() == header.lower():
            start_idx = idx + 1
            continue
        if start_idx is not None and raw.strip().startswith("## "):
            end_idx = idx
            break
    if start_idx is None:
        return text
    existing = "\n".join(lines[start_idx:end_idx]).lower()
    additions = [f"- {bullet}" for bullet in bullets if bullet.lower() not in existing]
    if not additions:
        return text
    insertion = start_idx
    while insertion < end_idx and not lines[insertion].strip():
        insertion += 1
    updated = lines[:insertion] + additions + lines[insertion:]
    return "\n".join(updated)


def enforce_goldilocks_signals(text: str) -> str:
    lowered = text.lower()
    if any(marker in lowered for marker in ("symptom", "симптом", "constraint", "огранич", "acceptance", "критер")):
        return text
    out = text
    for section_name, bullets in GOLDILOCKS_SIGNAL_BULLETS.items():
        out = _append_section_bullets(out, section_name, bullets)
    return out


def harden_generated_artifact(text: str, *, stage_name: str, workspace_path: Path | None = None) -> str:
    out = str(text or "")
    out = normalize_domain_language(out, workspace_path)
    out = soften_unanchored_claims(out)
    if stage_name == "problem_factory":
        out = enforce_goldilocks_signals(out)
    return out
