from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.llm.client import generate_markdown_with_skill
from app.pipeline.artifact_template import build_frontmatter, write_markdown_artifact
from app.pipeline.epistemic_projection import emit_projection
from app.pipeline.epistemic_sanitizer import soften_unanchored_claims
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
    return soften_unanchored_claims(path.read_text(encoding="utf-8"))


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


def _load_domain_profile(workspace: Path) -> Dict[str, object]:
    path = workspace / "analysis" / "domain_profile.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _market_viewpoint_required(domain_profile: Dict[str, object]) -> bool:
    axes = {
        str(item.get("axis"))
        for item in domain_profile.get("domain_axes", [])
        if isinstance(item, dict) and str(item.get("axis") or "").strip()
    }
    return bool({"market_validation", "commercial_presales_bottleneck"} & axes)


def _viewpoint_coverage_policy(workspace: Path) -> Dict[str, object]:
    domain_profile = _load_domain_profile(workspace)
    required = ["strategist", "analyst", "operator", "architect", "critic", "client"]
    optional: List[str] = []
    if _market_viewpoint_required(domain_profile):
        required.append("market")
    else:
        optional.append("market")
    return {
        "required": required,
        "optional": optional,
        "domain_profile": domain_profile,
    }


def _collect_artifact_context(workspace: Path) -> Tuple[Dict[str, str], List[str]]:
    artifacts: Dict[str, str] = {}
    missing: List[str] = []
    for _, _, rel in ANALYTICAL_SECTIONS:
        body = _artifact_context(workspace, rel)
        artifacts[rel] = body
        if not body:
            missing.append(rel)

    policy = _viewpoint_coverage_policy(workspace)
    artifacts["analysis/domain_profile.json"] = _artifact_context(workspace, "analysis/domain_profile.json")

    for vp in policy["required"] + policy["optional"]:
        rel = f"viewpoints/{vp}.md"
        body = _artifact_context(workspace, rel)
        artifacts[rel] = body
        if not body and vp in policy["required"]:
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
    patterns = [
        re.compile(
            rf"(?ms)^##\s+\d+\.\s+{re.escape(title)}\n(?:- source: .*\n)?(.*?)(?=^##\s+\d+\.|^##\s+(?!\d+\.)|\Z)"
        ),
        re.compile(rf"(?ms)^##\s+{re.escape(title)}\n(?:- source: .*\n)?(.*?)(?=^##\s+|\Z)"),
    ]
    match = None
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            break
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


def _extract_bullet_values(text: str, section_title: str, prefix: str) -> List[str]:
    section = _extract_section_body(text, section_title)
    out: List[str] = []
    for raw in section.splitlines():
        s = raw.strip()
        if s.startswith(f"- {prefix}"):
            out.append(s.split(":", 1)[1].strip() if ":" in s else s[2:].strip())
    return out


def _extract_rejected_summary(selected_text: str) -> Dict[str, List[str]]:
    rejected_section = _extract_section_body(selected_text, "Rejected Alternatives")
    dominated: List[str] = []
    rollout: List[str] = []
    current_sid = ""
    for raw in rejected_section.splitlines():
        s = raw.strip()
        if s.startswith("- sol_") and ":" in s:
            sid, status = s[2:].split(":", 1)
            current_sid = sid.strip()
            status = status.strip()
            if status == "rollout_relevant_not_primary":
                rollout.append(current_sid)
            elif status == "dominated_or_constraint_failing":
                dominated.append(current_sid)
        elif s.startswith("- reason:") and current_sid:
            continue
    return {"dominated": dominated, "rollout": rollout}


def _coverage_note(artifacts: Dict[str, str]) -> str:
    domain_profile_raw = artifacts.get("analysis/domain_profile.json", "")
    try:
        domain_profile = json.loads(domain_profile_raw) if domain_profile_raw else {}
    except Exception:
        domain_profile = {}
    required = ["strategist", "analyst", "operator", "architect", "critic", "client"]
    optional: List[str] = []
    if _market_viewpoint_required(domain_profile):
        required.append("market")
    else:
        optional.append("market")

    missing_required = [vp for vp in required if not str(artifacts.get(f"viewpoints/{vp}.md", "")).strip()]
    missing_optional = [vp for vp in optional if not str(artifacts.get(f"viewpoints/{vp}.md", "")).strip()]

    notes: List[str] = []
    if missing_required:
        notes.append(
            "Отсутствуют обязательные точки зрения: " + ", ".join(missing_required) + ". Это понижает надежность решения и требует добора viewpoint coverage."
        )
    if missing_optional:
        notes.append(
            "Не собраны optional-точки зрения: " + ", ".join(missing_optional) + ". Это снижает полноту анализа, но не считается критическим дефектом для текущего профиля кейса."
        )
    return " ".join(notes)


def _parse_solution_portfolio(text: str) -> List[Dict[str, object]]:
    entries: List[Dict[str, object]] = []
    current: Optional[Dict[str, object]] = None
    for raw in text.splitlines():
        stripped = raw.strip()
        section = re.match(r"^##\s+(sol_[a-z0-9_]+)\s*$", stripped, flags=re.IGNORECASE)
        if section:
            current = {"id": section.group(1).lower(), "attrs": {}, "lines": []}
            entries.append(current)
            continue
        if not current or not stripped:
            continue
        current["lines"].append(stripped)
        if stripped.startswith("- ") and ":" in stripped:
            key, value = stripped[2:].split(":", 1)
            current["attrs"][key.strip().lower()] = value.strip()
    return entries


def _humanize_solution_id(solution_id: str) -> str:
    core = re.sub(r"^sol_\d{2}_", "", solution_id).strip("_")
    if not core:
        return solution_id
    return core.replace("_", " ")


def _infer_solution_task(entry: Dict[str, object]) -> str:
    attrs = entry.get("attrs", {})
    preferred_keys = [
        "expected_effects",
        "solves_which_problems",
        "roles",
        "стратегия",
    ]
    for key in preferred_keys:
        value = str(attrs.get(key, "")).strip()
        if value and len(value) > 12 and value.count("_") < 6:
            return value.rstrip(".")
    lines = [ln for ln in entry.get("lines", []) if ln.startswith("- ")]
    for line in lines:
        if ":" in line:
            key, value = line[2:].split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if key in {"type", "assurance_level", "intervention_force", "relevance_basis"}:
                continue
            if value and len(value) > 12 and value.count("_") < 6 and not value.endswith("):"):
                return value.rstrip(".")
    return _humanize_solution_id(str(entry.get("id", "решение")))


def _intervention_force_explanation(force: str) -> str:
    explanations = {
        "weak": "Это слабое решение, потому что оно меняет правила входа, фильтрацию или локальную маршрутизацию, но не требует тяжелой ИТ-разработки, новой оргструктуры или радикальной перестройки бизнес-модели.",
        "medium": "Это среднее решение, потому что оно уже меняет контур работы и частично отчуждает функцию в инструмент или новый операционный режим, но еще не требует полной архитектурной или организационной трансформации.",
        "strong": "Это сильное решение, потому что оно затрагивает архитектуру, оргструктуру или рыночную конфигурацию системы и поэтому имеет более высокий радиус поражения и цену ошибки.",
    }
    return explanations.get(force, "Уровень вмешательства требует отдельного уточнения.")


def _intervention_force_principle(force: str) -> str:
    principles = {
        "weak": "Класс weak-interventions решает универсальную задачу: вынести шум, неквалифицированный вход и простые правила допуска как можно ближе ко входу системы, не меняя ее базовую архитектуру.",
        "medium": "Класс medium-interventions решает универсальную задачу: частично отчуждать повторяемую экспертную логику в метод, инструмент или контролируемый операционный контур, не переходя к полной трансформации системы.",
        "strong": "Класс strong-interventions решает универсальную задачу: менять саму топологию системы, распределение ролей, архитектурные границы или бизнес-модель, когда локальных мер уже недостаточно.",
    }
    return principles.get(force, "Класс вмешательства требует отдельного принципиального описания.")


def _build_intervention_ladder_note(portfolio_text: str) -> str:
    entries = _parse_solution_portfolio(portfolio_text)
    if not entries:
        return ""
    ladder_parts: List[str] = []
    for force in ["weak", "medium", "strong"]:
        forced = [
            entry
            for entry in entries
            if str(entry.get("attrs", {}).get("intervention_force", "")).lower() == force
            and "status_quo" not in str(entry.get("id", ""))
            and str(entry.get("attrs", {}).get("type", "")).lower() != "baseline"
        ]
        if not forced:
            continue
        labels = [f"`{str(entry.get('id', ''))}`" for entry in forced[:3]]
        examples = ", ".join(labels)
        ladder_parts.append(
            f"**{force.capitalize()} interventions:** {_intervention_force_principle(force)} "
            f"{_intervention_force_explanation(force)} "
            f"В текущем кейсе этот класс представлен альтернативами: {examples}."
        )
    return "\n".join(ladder_parts)


def _collect_constraint_markers(*texts: str) -> List[str]:
    patterns = [
        (r"\bbudget\b|бюджет|opex|capex", "бюджет / OPEX"),
        (r"time_horizon|horizon|pilot window|30-day|30 days|6 months|срок|горизонт|пилот|месяц|дн", "срок / горизонт пилота"),
        (r"sla|service level|ttq|time-to-quote", "операционный SLA / целевое время"),
    ]
    found: List[str] = []
    combined = "\n".join(texts).lower()
    for pattern, label in patterns:
        if re.search(pattern, combined, flags=re.IGNORECASE) and label not in found:
            found.append(label)
    return found


def _build_constraint_assumption_note(artifacts: Dict[str, str]) -> str:
    source_text = "\n".join(
        [
            artifacts.get("raw/case_input.md", ""),
            artifacts.get("intake/normalized_case.md", ""),
        ]
    )
    derived_text = "\n".join(
        [
            artifacts.get("problems/ComparisonAcceptanceSpec.md", ""),
            artifacts.get("solutions/SolutionPortfolio.md", ""),
            artifacts.get("solutions/ParityReport.md", ""),
        ]
    )
    source_markers = _collect_constraint_markers(source_text)
    derived_markers = _collect_constraint_markers(derived_text)
    assumptions = [marker for marker in derived_markers if marker not in source_markers]
    if not assumptions:
        return ""
    return (
        "Замечание об ограничениях: "
        + ", ".join(assumptions)
        + " фигурируют в сравнении решений как рабочие предположения, а не как явно подтвержденные входные данные кейса. "
        "Если эти ограничения действительно критичны для выбора, их нужно либо подтвердить отдельным вводом пользователя, либо считать открытыми вопросами."
    )


def _build_high_confidence_data_note(artifacts: Dict[str, str], selected_text: str) -> str:
    missing_inputs = _extract_bullet_values(selected_text, "Decision Preconditions", "missing_input")
    defaults = [
        "топология входящего потока: объем, ритм, сезонность и точки накопления очереди",
        "переходные вероятности по стадиям процесса: конверсия, отвал, возвраты и причины потерь",
        "сегментация потока: какие классы запросов действительно различаются по сложности, марже и требуемой экспертизе",
        "экономика шага принятия решения: стоимость времени экспертов, стоимость ошибки, стоимость задержки и цена ложной эскалации",
        "границы допустимого решения: подтвержденный бюджет, горизонт пилота, допустимый радиус поражения и условия обратимости",
        "операционные и юридические ограничения: какие изменения разрешены в ролях, маршрутизации, IT-слое и ответственности",
        "risk tolerance и пороги отката: какие метрики нельзя ухудшать и какие отклонения считаются неприемлемыми",
        "структура прав принятия решений: кто владеет входом, кто владеет эскалацией, кто подтверждает исключения и кто принимает rollback",
    ]
    generic_missing = {
        "фактические операционные и экономические параметры процесса",
        "критические операционные и экономические параметры процесса",
    }
    items = defaults if not missing_inputs or set(missing_inputs).issubset(generic_missing) else missing_inputs
    lines = [
        "Для построения дерева проблем и решений с высокой уверенностью системе нужны не частные догадки по кейсу, а следующие классы данных мета-уровня:"
    ]
    lines.extend(f"- {item}." for item in items)
    return "\n".join(lines)


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
    selected_raw = str(artifacts.get("solutions/SelectedSolutions.md", ""))
    intervention_note = _build_intervention_ladder_note(str(artifacts.get("solutions/SolutionPortfolio.md", "")))
    constraint_note = _build_constraint_assumption_note(artifacts)
    coverage_note = _coverage_note(artifacts)
    if "deferred_pending_data_collection" in selected or "decision deferred" in selected:
        missing_inputs = _extract_bullet_values(selected_raw, "Decision Preconditions", "missing_input")
        clarifications = "; ".join(missing_inputs) if missing_inputs else "критические операционные и экономические параметры процесса"
        data_note = _build_high_confidence_data_note(artifacts, selected_raw)
        if intervention_note:
            body = _upsert_section_suffix(body, "## 12. Solution Portfolio", intervention_note)
        if constraint_note:
            body = _upsert_section_suffix(body, "## 11. Comparison & Acceptance Spec", constraint_note)
            body = _upsert_section_suffix(body, "## 13. Parity Plan/Report", constraint_note)
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
        body = _replace_section_body(
            body,
            "## 18. Open Questions",
            (
                "Для принятия решения требуется добавить следующие данные: "
                + clarifications
                + ". До их получения система должна оставаться в режиме controlled deferral, а не подменять выбор статус-кво или декоративной архитектурой.\n\n"
                + data_note
            ),
        )
    else:
        rejected = _extract_rejected_summary(selected_raw)
        suffix_bits: List[str] = []
        if intervention_note:
            body = _upsert_section_suffix(body, "## 12. Solution Portfolio", intervention_note)
        if constraint_note:
            body = _upsert_section_suffix(body, "## 11. Comparison & Acceptance Spec", constraint_note)
            body = _upsert_section_suffix(body, "## 13. Parity Plan/Report", constraint_note)
        missing_inputs = _extract_bullet_values(selected_raw, "Decision Preconditions", "missing_input")
        if missing_inputs:
            body = _upsert_section_suffix(body, "## 18. Open Questions", _build_high_confidence_data_note(artifacts, selected_raw))
        if rejected["dominated"]:
            suffix_bits.append("Доминируемые или не проходящие ограничения альтернативы: " + ", ".join(rejected["dominated"]) + ".")
        if rejected["rollout"]:
            suffix_bits.append("Оставленные как rollout-relevant but not primary: " + ", ".join(rejected["rollout"]) + ".")
        if suffix_bits:
            body = _upsert_section_suffix(body, "## 14. Tradeoff Resolution", " ".join(suffix_bits))
        if "provisional_pending_revalidation" in selected:
            body = _upsert_section_suffix(
                body,
                "## 15. ADR",
                "Выбранные решения следует трактовать как предварительные рекомендации, а не как окончательно утвержденную архитектуру. Они сохраняют силу только до момента повторной переоценки после поступления недостающих данных."
            )
    if coverage_note:
        body = _upsert_section_suffix(body, "## 5. Viewpoint Matrix", coverage_note)
        body = _upsert_section_suffix(body, "## 17. Evidence Status", coverage_note)
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
    rejected = _extract_rejected_summary(selected)
    missing_inputs = _extract_bullet_values(selected, "Decision Preconditions", "missing_input")
    coverage_note = _coverage_note(artifacts)

    analytical_problem = _extract_section_body(analytical, "Problem Archive")
    analytical_layers = _extract_section_body(analytical, "4-Layer Model")
    analytical_parity = _extract_section_body(analytical, "Parity Plan/Report")
    analytical_tradeoff = _extract_section_body(analytical, "Tradeoff Resolution")
    analytical_open_questions = _extract_section_body(analytical, "Open Questions")
    section_2_suffix = "\n".join(
        [
            "**Где возникает сбой:** он локализован в конкретном рабочем контуре, где входящий поток, оценка, согласование или исполнение завязаны на ограниченный набор ролей и правил.",
            f"**Цепочка возникновения:** {_executive_snippet(analytical_problem or problem_archive, 'причина -> механизм влияния -> симптом -> последствие описаны неполно, но ядро проблемы связано с отсутствием устойчивой логики маршрутизации, оценки или принятия решения.')}",
            f"**Архитектурное место отказа:** {_executive_snippet(analytical_layers or layers, 'сбой распределен между бизнес-моделью, процессом, инструментами и распределением ролей.')}",
        ]
    )
    section_5_suffix = "\n".join(
        [
            f"**Логика отказа от альтернатив:** {_executive_snippet(analytical_parity or parity, 'альтернативы сравниваются не по симпатии, а по жестким ограничениям цикла, бюджета, точности, обратимости и blast radius.')}",
            f"**Как разрешен конфликт выбора:** {_executive_snippet(analytical_tradeoff or conflicts, 'безопасность ядра и управляемость внедрения поставлены выше мгновенного ускорения, поэтому выбран сценарий с приемлемым риском и контролируемым rollout.')}",
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
    if coverage_note:
        body = _upsert_section_suffix(body, "## 10. Epistemic status", coverage_note)
        body = _upsert_section_suffix(body, "## 2. Главная проблема", coverage_note)
    portfolio_note = _build_intervention_ladder_note(str(artifacts.get("solutions/SolutionPortfolio.md", "")))
    if portfolio_note:
        summary_lines = []
        weak_match = re.search(r"\*\*Weak interventions:\*\*\s+(.*?)(?=\n\*\*|\Z)", portfolio_note, flags=re.S)
        medium_match = re.search(r"\*\*Medium interventions:\*\*\s+(.*?)(?=\n\*\*|\Z)", portfolio_note, flags=re.S)
        if weak_match:
            summary_lines.append("Слабые решения: " + weak_match.group(1).strip())
        if medium_match:
            summary_lines.append("Средние решения: " + medium_match.group(1).strip())
        if summary_lines:
            body = _upsert_section_suffix(body, "## 4. 1-3 рекомендуемых решения", "\n".join(summary_lines))
    constraint_note = _build_constraint_assumption_note(artifacts)
    if constraint_note:
        body = _upsert_section_suffix(body, "## 10. Epistemic status", constraint_note)
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
        if missing_inputs:
            body = _replace_section_body(
                body,
                "## 10. Epistemic status",
                (
                    "Решение не может быть принято до уточнения следующих данных: "
                    + "; ".join(missing_inputs)
                    + ". Текущий статус допускает диагноз и план уточнения, но не финальный управленческий выбор.\n\n"
                    + _build_high_confidence_data_note(artifacts, selected)
                    + ("\n\n" + constraint_note if constraint_note else "")
                ),
            )
    elif "provisional_pending_revalidation" in selected.lower():
        if missing_inputs:
            body = _replace_section_body(
                body,
                "## 10. Epistemic status",
                (
                    "Сервис предлагает предварительные решения, но они основаны на неполной количественной базе и должны быть пересмотрены после уточнения следующих данных: "
                    + "; ".join(missing_inputs)
                    + ".\n\n"
                    + _build_high_confidence_data_note(artifacts, selected)
                    + ("\n\n" + constraint_note if constraint_note else "")
                ),
            )
    elif rejected["dominated"] or rejected["rollout"]:
        why = []
        if rejected["dominated"]:
            why.append("Как dominated или constraint-failing были отклонены: " + ", ".join(rejected["dominated"]) + ".")
        if rejected["rollout"]:
            why.append("Как rollout-relevant but not primary оставлены: " + ", ".join(rejected["rollout"]) + ".")
        body = _upsert_section_suffix(body, "## 5. Почему выбраны", " ".join(why))
    return body


def _build_reporting_payload(
    workspace_id: str,
    report_type: str,
    analytical_sections: List[Tuple[str, str, str]],
    artifacts: Dict[str, str],
    missing_sources: List[str],
    projection: Dict[str, object],
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
            "reporting_projection": projection,
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
        "reporting_projection": projection,
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
    projection = emit_projection(workspace, "reporting_projection")
    payload = _build_reporting_payload(
        workspace_id=workspace_id,
        report_type="analytical",
        analytical_sections=ANALYTICAL_SECTIONS,
        artifacts=artifacts,
        missing_sources=missing,
        projection=projection,
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
    projection = emit_projection(workspace, "reporting_projection")
    payload = _build_reporting_payload(
        workspace_id=workspace_id,
        report_type="executive",
        analytical_sections=ANALYTICAL_SECTIONS,
        artifacts=artifacts,
        missing_sources=missing,
        projection=projection,
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
