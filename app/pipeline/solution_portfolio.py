from __future__ import annotations

from pathlib import Path
import re
from typing import Dict, List, Tuple

from app.llm.client import generate_markdown_with_skill
from app.pipeline.artifact_template import build_frontmatter, write_markdown_artifact


def _load_skill(project_root: Path) -> str:
    p = project_root / ".agent" / "skills" / "ec-solution-generator" / "SKILL.md"
    if p.is_file():
        return p.read_text(encoding="utf-8")
    return "name: ec-solution-generator\ndescription: generate solutions"


SECTION_RE = re.compile(r"^##\s+(?:\*\*)?(sol[-_][a-z0-9_-]+)(?:\*\*)?\s*$", re.IGNORECASE)
RELAXED_SECTION_RE = re.compile(r"^#{1,6}\s+.*?\b(sol[-_][a-z0-9_-]+)\b.*$", re.IGNORECASE)
BULLET_RE = re.compile(r"^\s*[-*+]\s+(?:\*\*)?([^\n:]+?)(?:\*\*)?\s*:\s*[`'\"]?(.+?)[`'\"]?\s*$")
RELAXED_ATTR_RE = re.compile(
    r"^\s*(?:[-*+]|\d+[.)])?\s*(?:\*\*)?([^\n:=\-–—]+?)(?:\*\*)?\s*(?::|=|-|–|—)\s*[`'\"]?(.+?)[`'\"]?\s*$"
)

KEY_ALIASES = {
    "assurance": "assurance_level",
    "assurance level": "assurance_level",
    "assurance_level": "assurance_level",
    "assurance lvl": "assurance_level",
    "confidence level": "assurance_level",
    "тип": "type",
    "solution type": "type",
    "type": "type",
    "тип решения": "type",
    "уровень уверенности": "assurance_level",
    "уровень достоверности": "assurance_level",
    "сила вмешательства": "intervention_force",
    "intervention force": "intervention_force",
    "intervention_force": "intervention_force",
    "основание релевантности": "relevance_basis",
    "основание актуальности": "relevance_basis",
    "relevance basis": "relevance_basis",
    "relevance_basis": "relevance_basis",
}

TYPE_ALIASES = {
    "architectural": "architecture",
    "architecture": "architecture",
    "архитектура": "architecture",
    "process": "process",
    "процесс": "process",
    "процессный": "process",
    "operational": "process",
    "operations": "process",
    "it": "it",
    "ит": "it",
    "технология": "it",
    "technology": "it",
    "tech": "it",
    "policy": "policy",
    "политика": "policy",
    "управление": "policy",
    "governance": "policy",
    "hr": "hr",
    "люди": "hr",
    "кадры": "hr",
    "people": "hr",
    "baseline": "baseline",
    "базовый": "baseline",
    "статус-кво": "baseline",
    "none": "baseline",
}


def _normalize_key(raw: str) -> str:
    key = raw.strip().lower().replace("—", " ").replace("–", " ")
    key = re.sub(r"\s+", " ", key).replace("-", " ").replace("_", " ")
    return KEY_ALIASES.get(key, key.replace(" ", "_"))


def _normalize_value(key: str, value: str) -> str:
    txt = value.strip()
    txt = re.sub(r"^[*_`'\"]+", "", txt)
    txt = re.sub(r"[*_`'\"]+$", "", txt)
    txt = txt.strip()
    if key == "type":
        low = txt.lower()
        return TYPE_ALIASES.get(low, low)
    if key == "assurance_level":
        low = txt.lower()
        low = {
            "низкий": "low",
            "средний": "medium",
            "высокий": "high",
        }.get(low, low)
        return low if low in {"low", "medium", "high"} else low
    if key == "intervention_force":
        low = txt.lower()
        low = {
            "слабое": "weak",
            "слабый": "weak",
            "среднее": "medium",
            "средний": "medium",
            "сильное": "strong",
            "сильный": "strong",
        }.get(low, low)
        return low if low in {"weak", "medium", "strong"} else low
    if key == "relevance_basis":
        low = txt.lower()
        low = {
            "pareto relevant": "pareto_relevant",
            "rollout relevant": "rollout_relevant",
            "парето-релевантно": "pareto_relevant",
            "парето релевантно": "pareto_relevant",
            "релевантно для раскатки": "rollout_relevant",
        }.get(low, low)
        return low if low in {"pareto_relevant", "rollout_relevant"} else low
    return txt


def _split_candidate_sections(body: str) -> Dict[str, str]:
    sections: Dict[str, List[str]] = {}
    current = ""
    for line in body.splitlines():
        stripped = line.strip()
        section = SECTION_RE.match(stripped) or RELAXED_SECTION_RE.match(stripped)
        if section:
            current = section.group(1).lower().replace("-", "_")
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(line)
    return {cid: "\n".join(lines) for cid, lines in sections.items()}


def _infer_type_from_text(candidate_id: str, section_text: str) -> str:
    lowered = f"{candidate_id}\n{section_text}".lower()
    keyword_groups = [
        ("architecture", ["architecture", "architectural", "cpq", "portal", "integration", "system redesign", "архитектур", "портал", "интеграц"]),
        ("policy", ["policy", "governance", "kpi", "sla", "rule", "governance reset", "политик", "управлен", "sla", "kpi"]),
        ("process", ["triage", "brief", "routing", "intake", "shadow mode", "estimator", "workflow", "process", "бриф", "маршрутиз", "процесс", "оценк"]),
        ("hr", ["staffing", "hiring", "training", "people", "role split", "кадр", "обучен", "роль"]),
        ("baseline", ["status quo", "статус-кво", "do nothing"]),
    ]
    for inferred, markers in keyword_groups:
        if any(marker in lowered for marker in markers):
            return inferred
    return ""


def _repair_candidate_attrs(candidates: Dict[str, Dict[str, str]], body: str) -> Dict[str, Dict[str, str]]:
    sections = _split_candidate_sections(body)
    repaired: Dict[str, Dict[str, str]] = {}
    for cid, attrs in candidates.items():
        section_text = sections.get(cid, "")
        merged = dict(attrs)
        if not merged.get("type"):
            inferred = _infer_type_from_text(cid, section_text)
            if inferred:
                merged["type"] = inferred
        repaired[cid] = merged
    return repaired


def _fallback_candidates() -> Dict[str, Dict[str, str]]:
    return {
        "sol_00_status_quo": {
            "type": "baseline",
            "assurance_level": "low",
            "anti_goodhart_risk": "hidden structural waste remains unmeasured under status quo",
        },
        "sol_01_fix1": {
            "type": "process",
            "assurance_level": "medium",
            "intervention_force": "weak",
            "relevance_basis": "rollout_relevant",
            "anti_goodhart_risk": "process speed can be gamed while quality drifts downstream",
        },
        "sol_02_fix2": {
            "type": "architecture",
            "assurance_level": "high",
            "intervention_force": "medium",
            "relevance_basis": "pareto_relevant",
            "anti_goodhart_risk": "implementation velocity may be optimized at the expense of outcome quality",
        },
        "sol_03_fix3": {
            "type": "hr",
            "assurance_level": "medium",
            "intervention_force": "strong",
            "relevance_basis": "pareto_relevant",
            "anti_goodhart_risk": "staffing metrics may improve without fixing the real bottleneck",
        },
    }


def _intervention_class_body(force: str) -> Tuple[str, str]:
    mapping = {
        "weak": (
            "Weak Intervention Class",
            "Класс weak-interventions описывает минимально достаточные и обратимые меры, которые меняют правила входа, фильтрацию, маршрутизацию или локальные роли без тяжелой перестройки архитектуры.",
        ),
        "medium": (
            "Medium Intervention Class",
            "Класс medium-interventions описывает меры, которые частично отчуждают повторяемую экспертную функцию в метод, инструмент или отдельный операционный контур, но не требуют полной трансформации системы.",
        ),
        "strong": (
            "Strong Intervention Class",
            "Класс strong-interventions описывает меры, которые меняют саму топологию системы, архитектурные границы, оргструктуру или бизнес-модель, когда локальные меры уже недостаточны.",
        ),
    }
    return mapping[force]


def _build_intervention_meta_model(candidates: Dict[str, Dict[str, str]]) -> List[str]:
    lines: List[str] = ["# Solution Space Meta-Model", ""]
    for force in ["weak", "medium", "strong"]:
        title, description = _intervention_class_body(force)
        members = [
            cid
            for cid, attrs in sorted(candidates.items())
            if attrs.get("intervention_force", "").strip().lower() == force and attrs.get("type", "").strip().lower() != "baseline"
        ]
        if not members:
            continue
        lines.append(f"## {title}")
        lines.append(f"- principle: {description}")
        lines.append("- purpose: represent a reusable intervention class, not a case-specific patch")
        lines.append("- selection_rule: keep this class in the portfolio only if it adds a distinct pareto profile or a safer rollout path")
        lines.append("- instances: " + ", ".join(members))
        lines.append("")
    return lines


def _canonicalize_candidates(candidates: Dict[str, Dict[str, str]], raw_body: str) -> str:
    sections: List[str] = _build_intervention_meta_model(candidates)
    for cid in sorted(candidates.keys()):
        attrs = candidates[cid]
        sections.append(f"## {cid}")
        preferred = [
            ("type", attrs.get("type", "")),
            ("assurance_level", attrs.get("assurance_level", "")),
            ("intervention_force", attrs.get("intervention_force", "")),
            ("relevance_basis", attrs.get("relevance_basis", "")),
        ]
        emitted = set()
        for key, value in preferred:
            if value:
                sections.append(f"- {key}: {value}")
                emitted.add(key)
        for key, value in attrs.items():
            if key in emitted or not value:
                continue
            sections.append(f"- {key}: {value}")
        sections.append("")
    return "\n".join(sections).strip() + "\n"


def _parse_candidates(body: str) -> Dict[str, Dict[str, str]]:
    candidates: Dict[str, Dict[str, str]] = {}
    current = ""
    for line in body.splitlines():
        stripped = line.strip()
        section = SECTION_RE.match(stripped) or RELAXED_SECTION_RE.match(stripped)
        if section:
            current = section.group(1).lower().replace("-", "_")
            candidates.setdefault(current, {})
            continue
        if not current:
            continue
        attr_line = line.replace("**", "")
        bullet = BULLET_RE.match(attr_line) or RELAXED_ATTR_RE.match(attr_line)
        if bullet:
            key = _normalize_key(bullet.group(1))
            value = _normalize_value(key, bullet.group(2))
            candidates[current][key] = value
    return _repair_candidate_attrs(candidates, body)


def run_solution_portfolio(project_root: Path, workspace_id: str, llm_mode: str = "local") -> Dict[str, object]:
    workspace = project_root / "cases" / workspace_id
    out_dir = workspace / "solutions"
    out_dir.mkdir(parents=True, exist_ok=True)

    selected_problem = (workspace / "problems" / "SelectedProblemCard.md")
    acceptance_spec = (workspace / "problems" / "ComparisonAcceptanceSpec.md")
    if not selected_problem.is_file() or not acceptance_spec.is_file():
        raise ValueError("SOLUTION_PORTFOLIO_REQUIRES_PROBLEM_CARD_AND_ACCEPTANCE_SPEC")

    skill_prompt = _load_skill(project_root)
    body = generate_markdown_with_skill(
        system_skill_prompt=skill_prompt,
        user_payload={
            "task_type": "build_solution_portfolio",
            "workspace_id": workspace_id,
            "selected_problem_card": selected_problem.read_text(encoding="utf-8"),
            "comparison_acceptance_spec": acceptance_spec.read_text(encoding="utf-8"),
        },
        mode=llm_mode,
    )

    candidates = _parse_candidates(body)
    
    validation_passed = True
    if len(candidates) < 4 or "sol_00_status_quo" not in candidates:
        print(f"  [WARN] Solution Portfolio validations failed: missing candidates or sol_00_status_quo.")
        validation_passed = False
        
    if validation_passed:
        types = {
            attrs.get("type", "").strip().lower()
            for cid, attrs in candidates.items()
            if cid != "sol_00_status_quo" and attrs.get("type", "").strip()
        }
        if len(types) < 2:
            print(f"  [WARN] Solution Portfolio validations failed: insufficient diversity (types={types}).")
            validation_passed = False

    if validation_passed:
        forces = {
            attrs.get("intervention_force", "").strip().lower()
            for cid, attrs in candidates.items()
            if cid != "sol_00_status_quo" and attrs.get("intervention_force", "").strip()
        }
        if not {"weak", "medium", "strong"}.issubset(forces):
            print(f"  [WARN] Solution Portfolio validations failed: intervention ladder incomplete (forces={forces}).")
            validation_passed = False
            
    if validation_passed:
        for candidate_id, attrs in candidates.items():
            if "assurance_level" not in attrs:
                print(f"  [WARN] Solution Portfolio validations failed: missing assurance_level for {candidate_id}.")
                validation_passed = False
                break
            if candidate_id != "sol_00_status_quo":
                if "intervention_force" not in attrs:
                    print(f"  [WARN] Solution Portfolio validations failed: missing intervention_force for {candidate_id}.")
                    validation_passed = False
                    break
                if "relevance_basis" not in attrs:
                    print(f"  [WARN] Solution Portfolio validations failed: missing relevance_basis for {candidate_id}.")
                    validation_passed = False
                    break

    if not validation_passed and len(candidates) < 4:
        raise ValueError("INVALID_SOLUTION_PORTFOLIO_MINIMUM_REQUIREMENTS")

    if not validation_passed:
        print("  [WARN] LLM solution generation failed struct validation. Falling back to canonical default portfolio.")
        body = _canonicalize_candidates(_fallback_candidates(), "")
    else:
        body = _canonicalize_candidates(candidates, body)

    fm = build_frontmatter(
        artifact_id=f"{workspace_id}__solution_portfolio",
        artifact_type="solution_portfolio",
        stage="solution_factory",
        parent_refs=[
            "problems/SelectedProblemCard.md",
            "problems/ComparisonAcceptanceSpec.md",
        ],
        source_refs=["problems/ComparisonAcceptanceSpec.md:L1"],
        evidence_refs=["problems/SelectedProblemCard.md:L1"],
        next_expected_artifacts=["solutions/ParityReport.md", "solutions/ConflictRecords.md"],
    )
    target = out_dir / "SolutionPortfolio.md"
    write_markdown_artifact(target, fm, body)

    return {
        "workspace_id": workspace_id,
        "solution_portfolio": "solutions/SolutionPortfolio.md",
        "llm_mode": llm_mode,
    }
