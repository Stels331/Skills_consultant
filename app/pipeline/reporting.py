from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.llm.client import generate_markdown_with_skill
from app.pipeline.artifact_template import build_frontmatter, write_markdown_artifact
from app.validation.artifact_contract_validator import read_frontmatter_document


ANALYTICAL_SECTIONS: List[Tuple[str, str, str]] = [
    ("1", "Action Context", "raw/case_input.md"),
    ("2", "Bounded Context", "problems/ComparisonAcceptanceSpec.md"),
    ("3", "Normalized Case", "intake/normalized_case.md"),
    ("4", "4-Layer Model", "layers/layer_1_business_model.md"),
    ("5", "Viewpoint Matrix", "viewpoints/conflicts_index.md"),
    ("6", "Characterization Passport", "characterization/CharacterizationPassport.md"),
    ("7", "Indicator Set", "characterization/IndicatorSet.md"),
    ("8", "Problem Archive", "problems/ProblemArchive.md"),
    ("9", "Problem Portfolio", "problems/ProblemPortfolio.md"),
    ("10", "Selected Problem Card", "problems/SelectedProblemCard.md"),
    ("11", "Comparison & Acceptance Spec", "problems/ComparisonAcceptanceSpec.md"),
    ("12", "Solution Portfolio", "solutions/SolutionPortfolio.md"),
    ("13", "Parity Plan/Report", "solutions/ParityReport.md"),
    ("14", "Tradeoff Resolution", "solutions/ConflictRecords.md"),
    ("15", "ADR", "decisions/ADR-001.md"),
    ("16", "Runbook/Rollback/Impact Plan", "operation/Runbook.md"),
    ("17", "Evidence Status", "evidence/evidence_graph.md"),
    ("18", "Open Questions", "dialogue/question_queue.json"),
    ("19", "Escalation/Re-entry conditions", "evidence/refresh_report.md"),
]

EXEC_SECTIONS = [
    "Кейс в 3-5 строках",
    "Главная проблема",
    "Ключевой конфликт интересов",
    "1-3 рекомендуемых решения",
    "Почему выбраны",
    "Главные риски",
    "План отката",
    "Ближайший шаг",
    "Что измерять дальше",
    "Epistemic status",
]

# Keep hard safety bans only for explicit policy leakage. Narrative reasoning for users is allowed.
PROHIBITED_MARKERS = [
    "<analysis>",
    "</analysis>",
    "BEGIN_CHAIN_OF_THOUGHT",
    "END_CHAIN_OF_THOUGHT",
]

TERM_REWRITE = {
    "fpf": "методическая модель",
    "goldilocks": "рабочая зона приоритизации",
    "anti-goodhart": "риск искажения метрик",
    "goodhart": "искажение метрик",
}

SKILL_CANDIDATES = ["ec-reporting", "ec-reporter"]


def _safe_read(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _md_body(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        return read_frontmatter_document(path).body.strip()
    except Exception:
        return _safe_read(path).strip()


def _normalize_terms(text: str) -> str:
    out = text
    for src, dst in TERM_REWRITE.items():
        out = re.sub(rf"\b{re.escape(src)}\b", dst, out, flags=re.IGNORECASE)
    return out


def _sanitize_prohibited_content(text: str) -> str:
    sanitized = text
    for marker in PROHIBITED_MARKERS:
        sanitized = re.sub(re.escape(marker), "[redacted]", sanitized, flags=re.IGNORECASE)
    return sanitized


def _validate_analytical_sections(text: str) -> None:
    for idx, title, _ in ANALYTICAL_SECTIONS:
        header = f"## {idx}. {title}"
        if header not in text:
            raise ValueError(f"ANALYTICAL_REPORT_MISSING_SECTION: {header}")


def _validate_executive_sections(text: str) -> None:
    for i, title in enumerate(EXEC_SECTIONS, start=1):
        header = f"## {i}. {title}"
        if header not in text:
            raise ValueError(f"EXECUTIVE_SUMMARY_MISSING_SECTION: {header}")


def _resolve_llm_mode(llm_mode: Optional[str]) -> str:
    if llm_mode:
        return llm_mode
    env_mode = os.environ.get("LLM_MODE", "").strip().lower()
    if env_mode in {"local", "openai", "antigravity"}:
        return env_mode
    return "antigravity"


def _load_reporting_skill(project_root: Path) -> str:
    for skill_name in SKILL_CANDIDATES:
        p = project_root / ".agent" / "skills" / skill_name / "SKILL.md"
        if p.is_file():
            return p.read_text(encoding="utf-8")
    raise FileNotFoundError("Reporting skill not found. Expected one of: ec-reporting, ec-reporter")


def _artifact_context(workspace: Path, rel: str, max_chars: int = 5500) -> str:
    text = _md_body(workspace / rel)
    if not text:
        return ""
    text = text.strip()
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n[truncated]"
    return text


def _collect_artifact_context(workspace: Path) -> Tuple[Dict[str, str], List[str]]:
    artifacts: Dict[str, str] = {}
    missing: List[str] = []
    for _, _, rel in ANALYTICAL_SECTIONS:
        body = _artifact_context(workspace, rel)
        artifacts[rel] = body
        if not body:
            missing.append(rel)

    # Ensure all 6 viewpoints are explicitly visible in reporting context.
    for vp in ["strategist", "analyst", "operator", "architect", "critic", "client"]:
        rel = f"viewpoints/{vp}.md"
        body = _artifact_context(workspace, rel)
        artifacts[rel] = body
        if not body:
            missing.append(rel)

    selected_raw = _md_body(workspace / "solutions" / "SelectedSolutions.md")
    artifacts["solutions/SelectedSolutions.md"] = selected_raw

    return artifacts, sorted(set(missing))


def _build_reporting_payload(
    workspace_id: str,
    report_type: str,
    analytical_sections: List[Tuple[str, str, str]],
    artifacts: Dict[str, str],
    missing_sources: List[str],
) -> Dict[str, object]:
    if report_type == "analytical":
        return {
            "task_type": "build_reporting_analytical",
            "workspace_id": workspace_id,
            "language": "ru",
            "analytical_sections": [
                {"index": idx, "title": title, "source": rel} for idx, title, rel in analytical_sections
            ],
            "artifact_context": artifacts,
            "missing_sources": missing_sources,
            "rules": {
                "must_be_traceable": True,
                "no_new_facts": True,
                "expand_causal_logic": True,
                "audience": "CEO_and_engineering_management",
            },
        }

    return {
        "task_type": "build_reporting_executive",
        "workspace_id": workspace_id,
        "language": "ru",
        "executive_sections": [
            {"index": str(i), "title": title} for i, title in enumerate(EXEC_SECTIONS, start=1)
        ],
        "artifact_context": artifacts,
        "missing_sources": missing_sources,
        "rules": {
            "must_be_traceable": True,
            "no_new_facts": True,
            "human_names_for_solutions": True,
            "audience": "CEO_and_engineering_management",
        },
    }


def _fallback_analytical(workspace: Path, artifacts: Dict[str, str], missing_sources: List[str]) -> str:
    blocks: List[str] = ["# Аналитический полный отчет", ""]

    for idx, title, rel in ANALYTICAL_SECTIONS:
        content = artifacts.get(rel, "")
        if not content:
            narrative = (
                "- Что зафиксировано: GAP: source artifact missing or empty.\n"
                "- Почему это важно: без этого блока нельзя надежно обосновать решение на управленческом уровне.\n"
                f"- Что сделать: восстановить `{rel}` и повторить сбор отчета."
            )
        else:
            lines = [ln.strip() for ln in content.splitlines() if ln.strip() and not ln.strip().startswith("#")]
            head = "; ".join(lines[:3]) if lines else "данные частично структурированы"
            tail = "; ".join(lines[3:6]) if len(lines) > 3 else "влияние ограничено полнотой входных данных"
            narrative = (
                f"- Что зафиксировано: {head}.\n"
                f"- Почему это важно: {tail}.\n"
                "- Что из этого следует: решение должно опираться на причинно-следственные связи и проверяемые ограничения."
            )

        blocks.extend([f"## {idx}. {title}", f"- source: {rel}", narrative, ""])

    if missing_sources:
        blocks.extend(
            [
                "## Traceability",
                "- Отчет построен на артефактах пайплайна; отсутствующие источники зафиксированы явно.",
                f"- Missing sources: {', '.join(missing_sources)}.",
                "",
            ]
        )

    return "\n".join(blocks).rstrip() + "\n"


def _fallback_executive(artifacts: Dict[str, str]) -> str:
    selected = artifacts.get("solutions/SelectedSolutions.md", "")
    selected_lines = [ln.strip()[2:] for ln in selected.splitlines() if ln.strip().startswith("- ")][:3]

    recs = (
        "\n".join(f"- {item}: вариант включен в набор управляемых решений." for item in selected_lines)
        if selected_lines
        else "- GAP: рекомендации не опубликованы, так как не зафиксирован evidence status."
    )

    sections = {
        "1": "Проект проходит через фазу принятия решения при неполной и местами противоречивой фактуре.",
        "2": "Главное затруднение связано с расхождением между целевой логикой и фактической реализацией.",
        "3": "Конфликт возникает между скоростью изменений и устойчивостью результата.",
        "4": recs,
        "5": "Выбранные варианты дают лучший баланс между ограничениями цикла, риском и обратимостью внедрения.",
        "6": "Основные риски связаны с неполнотой доказательной базы и возможной рассинхронизацией ролей.",
        "7": "План отката должен запускаться при ухудшении ключевых индикаторов в двух периодах подряд.",
        "8": "Ближайший шаг: запустить ограниченный пилот, назначить владельцев и критерии успеха.",
        "9": "Нужно отслеживать confidence решения, число критичных пробелов и риск рассогласования участников.",
        "10": "Уровень уверенности рабочий, но требует регулярной переоценки по результатам пилота.",
    }

    parts: List[str] = ["# Краткая управленческая записка", ""]
    for i, title in enumerate(EXEC_SECTIONS, start=1):
        idx = str(i)
        parts.extend([f"## {idx}. {title}", sections[idx], ""])
    return "\n".join(parts).rstrip() + "\n"


def compose_analytical_full_report(project_root: Path, workspace_id: str, llm_mode: Optional[str] = None) -> Dict[str, str]:
    workspace = project_root / "cases" / workspace_id
    report_dir = workspace / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    artifacts, missing = _collect_artifact_context(workspace)
    skill_prompt = _load_reporting_skill(project_root)
    mode = _resolve_llm_mode(llm_mode)
    payload = _build_reporting_payload(
        workspace_id=workspace_id,
        report_type="analytical",
        analytical_sections=ANALYTICAL_SECTIONS,
        artifacts=artifacts,
        missing_sources=missing,
    )

    generated = generate_markdown_with_skill(skill_prompt, payload, mode=mode).strip()
    if not generated:
        generated = _fallback_analytical(workspace, artifacts, missing).strip()

    body = _normalize_terms(_sanitize_prohibited_content(generated).rstrip() + "\n")
    try:
        _validate_analytical_sections(body)
    except Exception:
        body = _normalize_terms(_sanitize_prohibited_content(_fallback_analytical(workspace, artifacts, missing)).rstrip() + "\n")
        _validate_analytical_sections(body)

    fm = build_frontmatter(
        artifact_id=f"{workspace_id}__analytical_full_report",
        artifact_type="analytical_full_report",
        stage="reporting",
        parent_refs=[
            "problems/SelectedProblemCard.md",
            "problems/ComparisonAcceptanceSpec.md",
            "solutions/SelectedSolutions.md",
            "decisions/ADR-001.md",
            "operation/Runbook.md",
            "operation/RollbackPlan.md",
        ],
        source_refs=["reports/Analytical_Full_Report.md:L1"],
        evidence_refs=[
            "solutions/SelectedSolutions.md:L1",
            "decisions/ADR-001.md:L1",
            "evidence/evidence_graph.md:L1",
        ],
        epistemic_status="decision_grade",
        assurance_level="medium",
        next_expected_artifacts=["reports/Executive_Summary.md"],
    )
    out = report_dir / "Analytical_Full_Report.md"
    write_markdown_artifact(out, fm, body)

    return {
        "workspace_id": workspace_id,
        "analytical_full_report": "reports/Analytical_Full_Report.md",
        "missing_sources": missing,
    }


def compose_executive_summary(project_root: Path, workspace_id: str, llm_mode: Optional[str] = None) -> Dict[str, str]:
    workspace = project_root / "cases" / workspace_id
    report_dir = workspace / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    artifacts, missing = _collect_artifact_context(workspace)
    skill_prompt = _load_reporting_skill(project_root)
    mode = _resolve_llm_mode(llm_mode)
    payload = _build_reporting_payload(
        workspace_id=workspace_id,
        report_type="executive",
        analytical_sections=ANALYTICAL_SECTIONS,
        artifacts=artifacts,
        missing_sources=missing,
    )

    generated = generate_markdown_with_skill(skill_prompt, payload, mode=mode).strip()
    if not generated:
        generated = _fallback_executive(artifacts).strip()

    body = _normalize_terms(_sanitize_prohibited_content(generated).rstrip() + "\n")
    try:
        _validate_executive_sections(body)
    except Exception:
        body = _normalize_terms(_sanitize_prohibited_content(_fallback_executive(artifacts)).rstrip() + "\n")
        _validate_executive_sections(body)

    fm = build_frontmatter(
        artifact_id=f"{workspace_id}__executive_summary",
        artifact_type="executive_summary",
        stage="reporting",
        parent_refs=[
            "reports/Analytical_Full_Report.md",
            "solutions/SelectedSolutions.md",
            "decisions/ADR-001.md",
        ],
        source_refs=["reports/Analytical_Full_Report.md:L1"],
        evidence_refs=["solutions/SelectedSolutions.md:L1", "decisions/ADR-001.md:L1"],
        epistemic_status="decision_grade",
        assurance_level="medium",
        next_expected_artifacts=["reports/reporting_summary.json"],
    )
    out = report_dir / "Executive_Summary.md"
    write_markdown_artifact(out, fm, body)

    return {
        "workspace_id": workspace_id,
        "executive_summary": "reports/Executive_Summary.md",
    }


def run_reporting(project_root: Path, workspace_id: str, llm_mode: Optional[str] = None) -> Dict[str, object]:
    a = compose_analytical_full_report(project_root, workspace_id, llm_mode=llm_mode)
    e = compose_executive_summary(project_root, workspace_id, llm_mode=llm_mode)

    workspace = project_root / "cases" / workspace_id
    summary = {
        "workspace_id": workspace_id,
        "analytical_full_report": a["analytical_full_report"],
        "executive_summary": e["executive_summary"],
        "missing_sources": a.get("missing_sources", []),
    }
    (workspace / "reports" / "reporting_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary
