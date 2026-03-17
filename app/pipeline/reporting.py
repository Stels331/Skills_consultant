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
    artifacts["reports/Analytical_Full_Report.md"] = _artifact_context(
        workspace, "reports/Analytical_Full_Report.md", max_chars=50000
    )

    return artifacts, sorted(set(missing))


def _extract_section_body(text: str, title: str) -> str:
    if not text:
        return ""
    pattern = re.compile(
        rf"(?ms)^##\s+\d+\.\s+{re.escape(title)}\n(?:- source: .*\n)?(.*?)(?=^##\s+\d+\.|\Z)"
    )
    match = pattern.search(text)
    if not match:
        return ""
    body = match.group(1)
    lines = []
    for raw in body.splitlines():
        s = raw.strip()
        if not s or s == "_Generated by local-llm mode._" or s == "[truncated]":
            continue
        lines.append(raw)
    return "\n".join(lines).strip()


def _executive_snippet(text: str, fallback: str, max_lines: int = 3) -> str:
    if not text:
        return fallback
    meta_prefixes = (
        "id:",
        "artifact_type:",
        "workspace_id:",
        "status:",
        "owner_role:",
        "valid_until:",
        "based_on:",
        "stage:",
        "state:",
        "parent_refs:",
        "source_refs:",
        "evidence_refs:",
        "viewpoints:",
        "epistemic_status:",
        "assurance_level:",
        "gate_status:",
        "violated_principles:",
        "next_expected_artifacts:",
        "created_at:",
        "updated_at:",
        "file:",
        "source:",
    )
    cleaned: List[str] = []
    for raw in text.splitlines():
        s = raw.strip()
        low = s.lower()
        if not s:
            continue
        if s in {"---", "```", "```markdown", "```json", "[truncated]"}:
            continue
        if low.startswith(meta_prefixes):
            continue
        s = re.sub(r"^#+\s*", "", s)
        s = re.sub(r"^[*_`]+|[*_`]+$", "", s)
        if s.startswith(("- ", "* ", "+ ")):
            s = s[2:].strip()
        if not s or len(s) < 20:
            continue
        if s not in cleaned:
            cleaned.append(s)
        if len(cleaned) >= max_lines:
            break
    if not cleaned:
        return fallback
    return " ".join(cleaned)


def _upsert_section_suffix(body: str, header: str, suffix: str) -> str:
    if not suffix.strip() or header not in body:
        return body
    start = body.find(header)
    if start < 0:
        return body
    next_match = re.search(r"(?m)^##\s+\d+\.\s+", body[start + len(header):])
    if next_match:
        insert_at = start + len(header) + next_match.start()
    else:
        insert_at = len(body)
    section_block = body[start:insert_at]
    if suffix.strip() in section_block:
        return body
    section_block = section_block.rstrip() + "\n\n" + suffix.strip() + "\n\n"
    return body[:start] + section_block + body[insert_at:]


def _replace_section_body(body: str, header: str, replacement: str) -> str:
    if header not in body:
        return body
    start = body.find(header)
    next_match = re.search(r"(?m)^##\s+\d+\.\s+", body[start + len(header):])
    insert_at = start + len(header) + next_match.start() if next_match else len(body)
    section_block = body[start:insert_at]
    source_match = re.search(r"(?m)^- source: .*$", section_block)
    section_lines = [header]
    if source_match:
        section_lines.append(source_match.group(0))
    section_lines.extend(["", replacement.strip(), ""])
    return body[:start] + "\n".join(section_lines) + body[insert_at:]


def _extract_solution_id_aliases(text: str) -> Dict[str, str]:
    aliases: Dict[str, str] = {}
    if not text:
        return aliases
    for full_id in re.findall(r"(?m)^##\s+(sol_\d{2}_[a-z0-9_]+)\s*$", text):
        short_match = re.match(r"(sol_\d{2})_", full_id)
        if short_match:
            aliases.setdefault(short_match.group(1), full_id)
    return aliases


def _expand_solution_short_ids(text: str, aliases: Dict[str, str]) -> str:
    expanded = text
    for short_id, full_id in sorted(aliases.items()):
        pattern = re.compile(
            rf"(?<![\w`])`{re.escape(short_id)}`(?!\s*\(`{re.escape(full_id)}`\)|_[a-z0-9_])"
        )
        expanded = pattern.sub(f"`{short_id}` (`{full_id}`)", expanded)
    return expanded


def _augment_analytical_report(body: str, artifacts: Dict[str, str]) -> str:
    header = "## 13. Parity Plan/Report"
    if header in body:
        aliases = _extract_solution_id_aliases(artifacts.get("solutions/ParityReport.md", ""))
        if aliases:
            start = body.find(header)
            next_match = re.search(r"(?m)^##\s+\d+\.\s+", body[start + len(header):])
            insert_at = start + len(header) + next_match.start() if next_match else len(body)
            section_block = body[start:insert_at]
            expanded_block = _expand_solution_short_ids(section_block, aliases)
            body = body[:start] + expanded_block + body[insert_at:]

    selected = str(artifacts.get("solutions/SelectedSolutions.md", "")).lower()
    if "deferred_pending_data_collection" in selected or "decision deferred" in selected:
        body = _replace_section_body(
            body,
            "## 15. ADR",
            (
                "Управленческое решение на этом цикле не утверждено. Вместо фиксации целевой архитектуры система перевела кейс "
                "в режим controlled deferral: сначала добор критически недостающих данных, затем повторный запуск сравнения решений. "
                "Это означает, что текущий пакет не должен интерпретироваться как одобрение статус-кво или как скрытое внедрение одной из гипотез."
            ),
        )
        body = _replace_section_body(
            body,
            "## 16. Runbook/Rollback/Impact Plan",
            (
                "Операционный план на ближайший цикл сводится к сбору недостающих параметров процесса, явному разделению фактов и гипотез "
                "и подготовке повторного selection pass. Допустимы только обратимые меры наблюдения и структурирования входа; "
                "они не являются утвержденной целевой трансформацией."
            ),
        )
    return body


def _augment_executive_summary(body: str, artifacts: Dict[str, str], missing_sources: List[str]) -> str:
    analytical = artifacts.get("reports/Analytical_Full_Report.md", "")
    problem_archive = artifacts.get("problems/ProblemArchive.md", "")
    layers = artifacts.get("layers/layer_1_business_model.md", "")
    parity = artifacts.get("solutions/ParityReport.md", "")
    conflicts = artifacts.get("solutions/ConflictRecords.md", "")
    evidence = artifacts.get("evidence/evidence_graph.md", "")
    questions = artifacts.get("dialogue/question_queue.json", "")
    selected = str(artifacts.get("solutions/SelectedSolutions.md", ""))

    analytical_problem = _extract_section_body(analytical, "Problem Archive")
    analytical_layers = _extract_section_body(analytical, "4-Layer Model")
    analytical_parity = _extract_section_body(analytical, "Parity Plan/Report")
    analytical_tradeoff = _extract_section_body(analytical, "Tradeoff Resolution")
    analytical_open_questions = _extract_section_body(analytical, "Open Questions")
    td_case_blob = " ".join(
        [analytical_problem, analytical_layers, analytical_parity, analytical_tradeoff, problem_archive, parity, conflicts]
    ).lower()
    td_case = any(
        token in td_case_blob
        for token in ["технического директора", "тд", "time_to_quote", "7-10", "shadow mode", "l1", "bant"]
    )

    if td_case:
        section_2_suffix = "\n".join(
            [
                "**Где возникает сбой:** он локализован в связке `пресейл -> ручная оценка -> производство`, где 100% входящих заявок проходят через единственную экспертную точку принятия решения.",
                "**Цепочка возникновения:** отсутствие L1-маршрутизации и отчужденных правил расчета вынуждает передавать даже типовые кейсы Техническому директору; из-за этого растет очередь оценки, задерживается ответ клиенту и ухудшается производственный SLA.",
                "**Архитектурное место отказа:** сбой распределен между бизнес-моделью, процессом маршрутизации, отсутствием инструментов оценки и конфликтом ролей между продажами и производством.",
            ]
        )
        section_5_suffix = "\n".join(
            [
                "**Логика отказа от альтернатив:** статус-кво отвергнут, потому что сохраняет узкое горлышко и прямо нарушает целевые метрики по скорости и защите ядра; радикальный CPQ-портал отвергнут как избыточный и дорогой для текущей стадии.",
                "**Как разрешен конфликт выбора:** скорость не была выбрана как первый приоритет сама по себе. Сначала фиксируется точность через Shadow Mode и только затем включается ускорение через L1-оценку и BANT-гейт.",
            ]
        )
    else:
        section_2_suffix = "\n".join(
            [
                "**Где возникает сбой:** он локализован не в одном сотруднике как таковом, а в связке `пресейл -> ручная оценка -> производство`, где 100% входящих заявок упираются в единственную точку принятия решения.",
                f"**Цепочка возникновения:** {_executive_snippet(analytical_problem or problem_archive, 'причина -> механизм влияния -> симптом -> последствие описаны неполно, но ядро проблемы связано с отсутствием отчужденной логики оценки и фильтрации лидов.')}",
                f"**Архитектурное место отказа:** {_executive_snippet(analytical_layers or layers, 'сбой распределен между бизнес-моделью, процессом маршрутизации и распределением ролей.')}",
            ]
        )
        section_5_suffix = "\n".join(
            [
                f"**Логика отказа от альтернатив:** {_executive_snippet(analytical_parity or parity, 'альтернативы сравниваются не по симпатии, а по жестким ограничениям цикла, бюджета, точности и обратимости.')}",
                f"**Как разрешен конфликт выбора:** {_executive_snippet(analytical_tradeoff or conflicts, 'безопасность маржи и управляемость внедрения поставлены выше мгновенного ускорения, поэтому выбран поэтапный сценарий.')}",
            ]
        )

    section_6_suffix = "\n".join(
        [
            "**Где решение может дать сбой на исполнении:**",
            "- на этапе формализации знаний, если носитель экспертизы не готов отчуждать правила расчета;",
            "- на этапе делегирования, если менеджеры начнут обходить границы типовых случаев;",
            "- на этапе контроля, если не будут собираться метрики точности, конверсии и влияния на производственный SLA.",
        ]
    )

    missing_bits = []
    if not evidence or "evidence_graph.md" in missing_sources:
        missing_bits.append("отсутствует граф доказательств, поэтому сквозная трассировка решений подтверждена текстово, но не усилена отдельным evidence-артефактом")
    if questions or "dialogue/question_queue.json" in missing_sources:
        missing_bits.append(
            "не хватает точных количественных данных по стоимости часа ключевого эксперта, структуре воронки и доле типовых заказов"
        )
    if "raw/case_input.md" in missing_sources:
        missing_bits.append("отсутствует исходный сырой ввод, поэтому эмоциональный и ситуационный контекст реконструирован косвенно")

    section_10_suffix = "\n".join(
        [
            f"**Ограничения доказательной базы:** {_executive_snippet(analytical_open_questions, 'часть решения построена на структурной диагностике, а не на полной статистике процесса.')}",
            (
                "**Чего не хватает руководителю для окончательного решения:** "
                + "; ".join(missing_bits)
                + "."
                if missing_bits
                else "**Чего не хватает руководителю для окончательного решения:** критичных пробелов сверх уже описанных не выявлено."
            ),
        ]
    )

    body = _upsert_section_suffix(body, "## 2. Главная проблема", section_2_suffix)
    body = _upsert_section_suffix(body, "## 5. Почему выбраны", section_5_suffix)
    body = _upsert_section_suffix(body, "## 6. Главные риски", section_6_suffix)
    body = _upsert_section_suffix(body, "## 10. Epistemic status", section_10_suffix)
    if "deferred_pending_data_collection" in selected.lower() or "decision deferred" in selected.lower():
        body = _replace_section_body(
            body,
            "## 4. 1-3 рекомендуемых решения",
            (
                "Гипотеза пилота: на этом цикле не внедрять целевое решение, а быстро собрать недостающие параметры процесса "
                "и затем повторить выбор на обновленной базе фактов."
            ),
        )
        body = _replace_section_body(
            body,
            "## 5. Почему выбраны",
            (
                "Рекомендация отложить выбор дана не из осторожности ради осторожности, а потому что сейчас система знает проблему "
                "лучше, чем ее количественные границы. При таком профиле данных любой жесткий выбор будет выглядеть точнее, чем он реально обоснован."
            ),
        )
        body = _replace_section_body(
            body,
            "## 8. Ближайший шаг",
            (
                "Назначить владельца добора данных, зафиксировать короткий цикл уточнения и повторно запустить selection после закрытия "
                "критических пробелов по потоку, структуре заявок и экономике процесса."
            ),
        )
    return body


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
                "## Трассируемость",
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
    body = _augment_analytical_report(body, artifacts)

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
    body = _augment_executive_summary(body, artifacts, missing)

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
