from __future__ import annotations

from pathlib import Path
import re
from typing import Dict

from app.llm.client import generate_markdown_with_skill
from app.pipeline.artifact_template import build_frontmatter, write_markdown_artifact
from app.pipeline.epistemic_guard import assess_decision_readiness


def _load_skill(project_root: Path) -> str:
    p = project_root / ".agent" / "skills" / "ec-solution-selector" / "SKILL.md"
    if p.is_file():
        return p.read_text(encoding="utf-8")
    return "name: ec-solution-selector\ndescription: selection"


SECTION_RE = re.compile(r"^##\s+(?:\*\*)?(sol_[a-z0-9_]+)(?:\*\*)?\s*$", re.IGNORECASE)
BULLET_RE = re.compile(r"^\s*[-*+]\s+(?:\*\*)?([a-zA-Z0-9_]+)(?:\*\*)?\s*:\s*[`'\"]?(.+?)[`'\"]?\s*$")
SELECTED_RE = re.compile(r"^\s*[-*+]\s+(?:\*\*)?[`'\"]?(sol_[a-z0-9_]+)[`'\"]?(?:\*\*)?(?:[\s:-].*)?$", re.IGNORECASE)
INLINE_SELECTED_RE = re.compile(r"\b(sol_[a-z0-9_]+)\b", re.IGNORECASE)


def _parse_portfolio_candidates(body: str) -> Dict[str, Dict[str, str]]:
    candidates: Dict[str, Dict[str, str]] = {}
    current = ""
    for line in body.splitlines():
        section = SECTION_RE.match(line.strip())
        if section:
            current = section.group(1).lower()
            candidates[current] = {}
            continue
        if not current:
            continue
        bullet = BULLET_RE.match(line)
        if bullet:
            candidates[current][bullet.group(1).strip().lower()] = bullet.group(2).strip()
    return candidates


def _extract_selected_ids(selected_markdown: str) -> list[str]:
    selected_ids: list[str] = []
    in_rejected_block = False
    for line in selected_markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if lowered.startswith("rejected:") or re.match(r"^#{1,6}\s+rejected\b", lowered):
            in_rejected_block = True
            continue
        if in_rejected_block:
            if stripped.startswith("#"):
                in_rejected_block = False
            else:
                continue
        m = SELECTED_RE.match(stripped)
        if m:
            sid = m.group(1).lower()
            if sid not in selected_ids:
                selected_ids.append(sid)
            continue

        # Accept hybrid/prose selections such as:
        # "Выбран гибридный подход: sol_01 + sol_02"
        # but ignore portfolio sections and rejected alternatives.
        if stripped.startswith("#"):
            continue
        if any(marker in lowered for marker in ["rejected", "отклон", "причина отказа"]):
            continue
        if not any(marker in lowered for marker in ["selected", "выбран", "принят", "одобрен", "решение", "конфигурац", "гибрид"]):
            continue
        for match in INLINE_SELECTED_RE.findall(stripped):
            sid = match.lower()
            if sid not in selected_ids:
                selected_ids.append(sid)
    return selected_ids


def _extract_rationale_lines(selected_markdown: str, limit: int = 4) -> list[str]:
    lines: list[str] = []
    in_rejected_block = False
    for raw in selected_markdown.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if lowered.startswith("rejected:") or re.match(r"^#{1,6}\s+rejected\b", lowered):
            in_rejected_block = True
            continue
        if in_rejected_block:
            continue
        if stripped.startswith("#"):
            continue
        if SELECTED_RE.match(stripped):
            continue
        if INLINE_SELECTED_RE.search(stripped) and any(
            marker in lowered for marker in ["selected", "выбран", "принят", "одобрен", "гибрид", "конфигурац"]
        ):
            continue
        cleaned = re.sub(r"^[*_`'\"]+|[*_`'\"]+$", "", stripped).strip()
        if len(cleaned) < 20:
            continue
        if cleaned not in lines:
            lines.append(cleaned)
        if len(lines) >= limit:
            break
    return lines


def _canonicalize_selected_markdown(selected_ids: list[str], selected_markdown: str) -> str:
    parts: list[str] = ["## Selected Solutions", ""]
    for sid in selected_ids:
        parts.append(f"- {sid}")
    parts.append("")

    parts.extend(["## Recommendation Status", ""])
    for sid in selected_ids:
        parts.append(f"- confirmed_action: {sid}")
    parts.append("")

    rationale_lines = _extract_rationale_lines(selected_markdown)
    if rationale_lines:
        parts.extend(["## Selection Rationale", ""])
        for line in rationale_lines:
            parts.append(f"- {line}")
        parts.append("")

    parts.extend(
        [
            "## traceability",
            *[f"- {sid} <- problems/ComparisonAcceptanceSpec.md:L1" for sid in selected_ids],
            "- parity <- solutions/ParityReport.md:L1",
            "- conflicts <- solutions/ConflictRecords.md:L1",
            "",
        ]
    )
    return "\n".join(parts).rstrip() + "\n"


DIMENSION_LABELS = {
    "flow_volume": "объем и ритм входящего потока",
    "conversion": "конверсия и причины потерь по воронке",
    "request_mix": "доля типовых и нетиповых запросов",
    "presales_economics": "экономика пресейла и цена ошибки оценки",
    "classification_logic": "критерии маршрутизации и квалификации заявок",
}


def _deferred_selected_markdown(readiness: Dict[str, object]) -> str:
    missing = [DIMENSION_LABELS.get(item, item) for item in readiness.get("missing_dimensions", [])]
    parts = [
        "## Decision Status",
        "",
        "- deferred_pending_data_collection",
        "",
        "## Recommendation Status",
        "",
        "- pilot_hypothesis: data_collection_and_reselection_cycle",
        "",
        "## Why Decision Deferred",
        "",
        "- Система не фиксирует полноценное управленческое решение, потому что критически важные параметры процесса описаны неполно.",
        "- При текущем уровне определенности допустим только диагноз и план добора данных, а не выбор целевой архитектуры.",
        "",
        "## Required Clarifications",
        "",
    ]
    if missing:
        for item in missing:
            parts.append(f"- Уточнить: {item}.")
    else:
        parts.append("- Уточнить: фактические операционные и экономические параметры процесса.")
    parts.extend(
        [
            "",
            "## Selection Rationale",
            "",
            "- Принцип выбора на этом цикле: не имитировать решение при дефиците данных.",
            "- Ближайший допустимый шаг: собрать недостающие параметры, затем повторно сравнить альтернативы.",
            "",
            "## traceability",
            "- readiness <- problems/SelectedProblemCard.md:L1",
            "- constraints <- problems/ComparisonAcceptanceSpec.md:L1",
            "- parity <- solutions/ParityReport.md:L1",
            "- conflicts <- solutions/ConflictRecords.md:L1",
            "",
        ]
    )
    return "\n".join(parts).rstrip() + "\n"


def _deferred_adr_markdown(readiness: Dict[str, object]) -> str:
    missing = ", ".join(DIMENSION_LABELS.get(item, item) for item in readiness.get("missing_dimensions", []))
    return (
        "# ADR-001: Decision Deferred Pending Clarification\n\n"
        "## Context\n"
        "- Диагноз системной проблемы уже сформирован, но критические входные параметры для выбора решения остаются неполными.\n"
        "- При таких условиях преждевременный выбор создаст ложную определенность и повысит риск ошибочного управленческого решения.\n\n"
        "## Decision\n"
        "- На текущем цикле не утверждать целевую архитектуру и не подменять решение статус-кво по умолчанию.\n"
        "- Зафиксировать режим controlled deferral: сначала сбор недостающих данных, затем повторный selection pass.\n\n"
        "## Missing Inputs\n"
        f"- {missing or 'Требуются дополнительные операционные и экономические данные.'}\n\n"
        "## Consequences\n"
        "- Команда получает не план внедрения, а план уточнения модели процесса.\n"
        "- Любые изменения до переоценки допускаются только как обратимые меры наблюдения и структурирования входа.\n"
    )


def _deferred_runbook_markdown(readiness: Dict[str, object]) -> str:
    missing = [DIMENSION_LABELS.get(item, item) for item in readiness.get("missing_dimensions", [])]
    lines = [
        "# Runbook",
        "",
        "## Preconditions",
        "- назначен владелец добора данных;",
        "- согласован короткий цикл повторной оценки;",
        "",
        "## Execution Steps",
        "1. Зафиксировать текущий operating baseline без объявления его целевым решением.",
        "2. Собрать недостающие параметры процесса на реальных заявках.",
        "3. Отделить подтвержденные факты от интерпретаций и рабочих гипотез.",
        "4. Повторно запустить parity и selection после обновления входных данных.",
        "",
        "## Success Criteria",
    ]
    if missing:
        lines.extend(f"- подтверждено: {item};" for item in missing)
    else:
        lines.append("- подтверждены критические параметры процесса;")
    lines.append("- решение следующего цикла опирается на проверяемые данные, а не на реконструкцию.")
    lines.append("")
    return "\n".join(lines)


def _deferred_rollback_markdown() -> str:
    return (
        "# Rollback Plan\n\n"
        "## Triggers\n"
        "- Откат требуется, если временные меры структурирования входа начинают ухудшать операционное ядро.\n"
        "- Откат требуется, если сбор данных превращается в скрытое внедрение новой архитектуры без повторного выбора.\n\n"
        "## Actions\n"
        "- Вернуться к последнему подтвержденному рабочему процессу без расширения временных ограничений и новых ролей.\n"
        "- Остановить любые решения, выданные как гипотезы, но интерпретированные как обязательные изменения.\n\n"
        "## Safe State\n"
        "- Система остается в режиме диагностического цикла до завершения переоценки.\n"
    )


def run_selection_engine(project_root: Path, workspace_id: str, llm_mode: str = "local") -> Dict[str, object]:
    workspace = project_root / "cases" / workspace_id

    required = {
        "solutions/SolutionPortfolio.md",
        "solutions/ParityReport.md",
        "solutions/TradeoffTable.md",
        "solutions/ConflictRecords.md",
        "problems/ComparisonAcceptanceSpec.md",
    }
    missing = [rel for rel in sorted(required) if not (workspace / rel).is_file()]
    if missing:
        raise ValueError(f"SELECTION_REQUIRES_PARITY_AND_CONFLICTS: missing {missing}")

    skill_prompt = _load_skill(project_root)
    portfolio_text = (workspace / "solutions" / "SolutionPortfolio.md").read_text(encoding="utf-8")
    parity_text = (workspace / "solutions" / "ParityReport.md").read_text(encoding="utf-8")
    conflicts_text = (workspace / "solutions" / "ConflictRecords.md").read_text(encoding="utf-8")
    spec_text = (workspace / "problems" / "ComparisonAcceptanceSpec.md").read_text(encoding="utf-8")
    readiness = assess_decision_readiness(workspace)

    if readiness["insufficient_for_decision"]:
        selected = _deferred_selected_markdown(readiness)
        selected_ids: list[str] = []
        adr = _deferred_adr_markdown(readiness)
        runbook = _deferred_runbook_markdown(readiness)
        rollback = _deferred_rollback_markdown()
    else:
        selected = generate_markdown_with_skill(
            skill_prompt,
            {
                "task_type": "build_selection_bundle",
                "solution_output": "selected_solutions",
                "workspace_id": workspace_id,
                "solution_portfolio": portfolio_text,
                "parity_report": parity_text,
                "conflict_records": conflicts_text,
                "acceptance_spec": spec_text,
            },
            mode=llm_mode,
        )
        candidates = _parse_portfolio_candidates(portfolio_text)
        selected_ids = _extract_selected_ids(selected)
        
        validation_passed = True
        if not (1 <= len(selected_ids) <= 3):
            print(f"  [WARN] Selection Engine validations failed: invalid count {len(selected_ids)} (expected 1-3). selected_ids={selected_ids}")
            validation_passed = False
        
        if validation_passed:
            for sid in selected_ids:
                if sid not in candidates:
                    print(f"  [WARN] Selection Engine validations failed: unknown candidate {sid}.")
                    validation_passed = False
                    break
                assurance = candidates[sid].get("assurance_level", "").strip()
                if not assurance:
                    raise ValueError(f"SELECTION_MISSING_ASSURANCE_LEVEL: {sid}")

        if not validation_passed:
            print("  [WARN] LLM selection failed struct validation. Falling back to deferred decision.")
            selected_ids = []
            selected = _deferred_selected_markdown(readiness)
            adr = _deferred_adr_markdown(readiness)
            runbook = _deferred_runbook_markdown(readiness)
            rollback = _deferred_rollback_markdown()
        else:
            selected = _canonicalize_selected_markdown(selected_ids, selected)

            adr = generate_markdown_with_skill(
                skill_prompt,
                {
                    "task_type": "build_selection_bundle",
                    "solution_output": "adr",
                    "workspace_id": workspace_id,
                    "solution_portfolio": portfolio_text,
                    "parity_report": parity_text,
                    "conflict_records": conflicts_text,
                    "acceptance_spec": spec_text,
                },
                mode=llm_mode,
            )
            runbook = generate_markdown_with_skill(
                skill_prompt,
                {
                    "task_type": "build_selection_bundle",
                    "solution_output": "runbook",
                    "workspace_id": workspace_id,
                    "selected_solutions": selected,
                },
                mode=llm_mode,
            )
            rollback = generate_markdown_with_skill(
                skill_prompt,
                {
                    "task_type": "build_selection_bundle",
                    "solution_output": "rollback",
                    "workspace_id": workspace_id,
                    "selected_solutions": selected,
                },
                mode=llm_mode,
            )

    # solutions dir artifacts
    for name, body, art_type in [
        ("SelectedSolutions.md", selected, "selected_solutions"),
    ]:
        fm = build_frontmatter(
            artifact_id=f"{workspace_id}__{name.replace('.md', '').lower()}",
            artifact_type=art_type,
            stage="solution_factory",
            parent_refs=[
                "solutions/SolutionPortfolio.md",
                "solutions/ParityReport.md",
                "solutions/ConflictRecords.md",
                "problems/ComparisonAcceptanceSpec.md",
            ],
            source_refs=["solutions/ParityReport.md:L1"],
            evidence_refs=["solutions/ConflictRecords.md:L1"],
            epistemic_status="hypothesis" if not selected_ids else "decision_grade",
            next_expected_artifacts=["decisions/ADR-001.md"],
        )
        write_markdown_artifact(workspace / "solutions" / name, fm, body)

    # decisions artifact
    dec_dir = workspace / "decisions"
    dec_dir.mkdir(parents=True, exist_ok=True)
    adr_fm = build_frontmatter(
        artifact_id=f"{workspace_id}__adr_001",
        artifact_type="adr_record",
        stage="solution_factory",
        parent_refs=["solutions/SelectedSolutions.md"],
        source_refs=["solutions/SelectedSolutions.md:L1"],
        evidence_refs=["solutions/ConflictRecords.md:L1"],
        epistemic_status="hypothesis" if not selected_ids else "decision_grade",
        next_expected_artifacts=["operation/Runbook.md", "operation/RollbackPlan.md"],
    )
    write_markdown_artifact(dec_dir / "ADR-001.md", adr_fm, adr)

    # operation artifacts
    op_dir = workspace / "operation"
    op_dir.mkdir(parents=True, exist_ok=True)
    runbook_fm = build_frontmatter(
        artifact_id=f"{workspace_id}__runbook",
        artifact_type="operation_runbook",
        stage="solution_factory",
        parent_refs=["decisions/ADR-001.md"],
        source_refs=["decisions/ADR-001.md:L1"],
        evidence_refs=["solutions/SelectedSolutions.md:L1"],
        next_expected_artifacts=["operation/RollbackPlan.md"],
    )
    write_markdown_artifact(op_dir / "Runbook.md", runbook_fm, runbook)

    rollback_fm = build_frontmatter(
        artifact_id=f"{workspace_id}__rollback_plan",
        artifact_type="rollback_plan",
        stage="solution_factory",
        parent_refs=["operation/Runbook.md"],
        source_refs=["operation/Runbook.md:L1"],
        evidence_refs=["decisions/ADR-001.md:L1"],
        next_expected_artifacts=["reports/Analytical_Full_Report.md"],
    )
    write_markdown_artifact(op_dir / "RollbackPlan.md", rollback_fm, rollback)

    return {
        "workspace_id": workspace_id,
        "selected_solutions": "solutions/SelectedSolutions.md",
        "adr": "decisions/ADR-001.md",
        "runbook": "operation/Runbook.md",
        "rollback": "operation/RollbackPlan.md",
        "llm_mode": llm_mode,
    }
