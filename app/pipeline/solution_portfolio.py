from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Literal, Tuple

from app.llm.client import generate_markdown_with_skill
from app.pipeline.artifact_template import build_frontmatter, write_markdown_artifact
from app.pipeline.epistemic_sanitizer import detect_unanchored_claim_lines, soften_unanchored_claims
from app.pipeline.epistemic_projection import emit_projection


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

NormalizationLevel = Literal["none", "key_only", "value_translated", "inferred"]
ParseQuality = Literal["clean", "normalized", "inferred", "failed"]

REQUIRED_BASE_FIELDS = {"type", "assurance_level"}
REQUIRED_NON_BASELINE_FIELDS = {"intervention_force", "relevance_basis"}


@dataclass(frozen=True)
class FieldTrustSource:
    method: Literal["llm_explicit", "alias", "text_inference", "repair_retry", "fallback"]
    key: str
    detail: str

    def to_audit_str(self) -> str:
        return f"{self.method}:key={self.key}:detail={self.detail}"


VALID_SOURCE_DETAILS = {
    "llm_explicit": {""},
    "fallback": {"canonical_default"},
    "repair_retry": {"attempt=1", "attempt=2"},
    "text_inference": {
        "rule=force_keyword_weak",
        "rule=force_keyword_medium",
        "rule=force_keyword_strong",
        "rule=force_keyword_ru_weak",
        "rule=force_keyword_ru_medium",
        "rule=force_keyword_ru_strong",
    },
}


@dataclass(frozen=True)
class FieldTrust:
    value: str
    F: Literal["explicit", "alias_normalized", "value_reinterpreted", "inferred_text", "inferred_positional"]
    G: Literal["this_case", "generic_domain", "cross_domain"]
    R: Literal["high", "medium", "low"]
    normalization_level: NormalizationLevel
    source: FieldTrustSource


@dataclass(frozen=True)
class ParseResult:
    candidates: Dict[str, Dict[str, str]]
    field_trust: Dict[str, Dict[str, FieldTrust]]
    missing_fields: Dict[str, List[str]]
    parse_quality: ParseQuality


def _append_contract_audit(workspace: Path, payload: Dict[str, object]) -> None:
    path = workspace / "governance" / "contract_audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _write_raw_llm_output(workspace: Path, artifact_name: str, raw_text: str) -> Path:
    path = workspace / "analysis" / "debug" / "llm_raw" / artifact_name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw_text, encoding="utf-8")
    return path


def _write_failed_audit(workspace: Path, payload: Dict[str, object]) -> None:
    required = {"raw_output_path", "missing_fields", "retry_attempted", "retry_outcome"}
    missing = required - set(payload.keys())
    if missing:
        raise ValueError(f"INCOMPLETE_FAILED_AUDIT_ENTRY: {sorted(missing)}")
    _append_contract_audit(workspace, payload)


def _validate_source(source: FieldTrustSource) -> None:
    if source.method == "alias":
        normalized = source.key.strip().lower().replace("—", " ").replace("–", " ")
        normalized = re.sub(r"\s+", " ", normalized).replace("-", " ").replace("_", " ")
        if normalized not in KEY_ALIASES:
            raise ValueError(f"INVALID_FIELD_TRUST_SOURCE_DETAIL: alias key {source.key}")
        return
    allowed = VALID_SOURCE_DETAILS.get(source.method)
    if allowed is not None and source.detail not in allowed:
        raise ValueError(f"INVALID_FIELD_TRUST_SOURCE_DETAIL: {source.detail}")


def _trust_dict(trust: FieldTrust) -> Dict[str, str]:
    return {
        "value": trust.value,
        "F": trust.F,
        "G": trust.G,
        "R": trust.R,
        "normalization_level": trust.normalization_level,
        "source": trust.source.to_audit_str(),
    }


def _normalize_key(raw: str) -> str:
    key = raw.strip().lower().replace("—", " ").replace("–", " ")
    key = re.sub(r"\s+", " ", key).replace("-", " ").replace("_", " ")
    return KEY_ALIASES.get(key, key.replace(" ", "_"))


def _normalize_value(key: str, value: str) -> Tuple[str, Literal["none", "value_translated"]]:
    txt = value.strip()
    txt = re.sub(r"^[*_`'\"]+", "", txt)
    txt = re.sub(r"[*_`'\"]+$", "", txt)
    txt = txt.strip()
    if key == "type":
        low = txt.lower()
        normalized = TYPE_ALIASES.get(low, low)
        return normalized, ("value_translated" if normalized != txt else "none")
    if key == "assurance_level":
        low = txt.lower()
        normalized = {
            "низкий": "low",
            "средний": "medium",
            "высокий": "high",
        }.get(low, low)
        if normalized in {"low", "medium", "high"}:
            return normalized, ("value_translated" if normalized != txt else "none")
        return normalized, "none"
    if key == "intervention_force":
        low = txt.lower()
        normalized = {
            "слабое": "weak",
            "слабый": "weak",
            "среднее": "medium",
            "средний": "medium",
            "сильное": "strong",
            "сильный": "strong",
        }.get(low, low)
        if normalized in {"weak", "medium", "strong"}:
            return normalized, ("value_translated" if normalized != txt else "none")
        return normalized, "none"
    if key == "relevance_basis":
        low = txt.lower()
        normalized = {
            "pareto relevant": "pareto_relevant",
            "rollout relevant": "rollout_relevant",
            "парето-релевантно": "pareto_relevant",
            "парето релевантно": "pareto_relevant",
            "релевантно для раскатки": "rollout_relevant",
        }.get(low, low)
        if normalized in {"pareto_relevant", "rollout_relevant"}:
            return normalized, ("value_translated" if normalized != txt else "none")
        return normalized, "none"
    return txt, "none"


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


def _infer_force_from_text(candidate_id: str, section_text: str) -> Tuple[str, str]:
    lowered = f"{candidate_id}\n{section_text}".lower()
    if "intervention_force: weak" in lowered or "intervention force: weak" in lowered:
        return "weak", "rule=force_keyword_weak"
    if "intervention_force: medium" in lowered or "intervention force: medium" in lowered:
        return "medium", "rule=force_keyword_medium"
    if "intervention_force: strong" in lowered or "intervention force: strong" in lowered:
        return "strong", "rule=force_keyword_strong"
    if "weak" in lowered:
        return "weak", "rule=force_keyword_weak"
    if "medium" in lowered:
        return "medium", "rule=force_keyword_medium"
    if "strong" in lowered:
        return "strong", "rule=force_keyword_strong"
    if "слаб" in lowered:
        return "weak", "rule=force_keyword_ru_weak"
    if "средн" in lowered:
        return "medium", "rule=force_keyword_ru_medium"
    if "сильн" in lowered or "радикальн" in lowered:
        return "strong", "rule=force_keyword_ru_strong"
    return "", ""


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


def _fallback_field_trust(candidates: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, FieldTrust]]:
    field_trust: Dict[str, Dict[str, FieldTrust]] = {}
    for cid, attrs in candidates.items():
        field_trust[cid] = {}
        for key, value in attrs.items():
            source = FieldTrustSource(method="fallback", key=key, detail="canonical_default")
            _validate_source(source)
            field_trust[cid][key] = FieldTrust(
                value=value,
                F="inferred_text",
                G="generic_domain",
                R="low",
                normalization_level="inferred",
                source=source,
            )
    return field_trust


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


def _canonicalize_candidates(candidates: Dict[str, Dict[str, str]]) -> str:
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


def _field_source(raw_key: str, normalized_key: str, value_level: Literal["none", "value_translated"]) -> Tuple[str, NormalizationLevel, FieldTrustSource, str]:
    raw_low = raw_key.strip().lower().replace("—", " ").replace("–", " ")
    raw_low = re.sub(r"\s+", " ", raw_low).replace("-", " ").replace("_", " ")
    alias_used = KEY_ALIASES.get(raw_low, raw_low.replace(" ", "_")) != raw_low.replace(" ", "_")
    if value_level == "value_translated":
        source = FieldTrustSource(method="alias" if alias_used else "llm_explicit", key=raw_key, detail=normalized_key if alias_used else "")
        _validate_source(source)
        return "value_reinterpreted", "value_translated", source, "medium"
    if alias_used:
        source = FieldTrustSource(method="alias", key=raw_key, detail=normalized_key)
        _validate_source(source)
        return "alias_normalized", "key_only", source, "medium"
    source = FieldTrustSource(method="llm_explicit", key=normalized_key, detail="")
    _validate_source(source)
    return "explicit", "none", source, "high"


def _required_fields_for_candidate(candidate_id: str, attrs: Dict[str, str]) -> set[str]:
    required = set(REQUIRED_BASE_FIELDS)
    if candidate_id != "sol_00_status_quo" and attrs.get("type", "").strip().lower() != "baseline":
        required.update(REQUIRED_NON_BASELINE_FIELDS)
    return required


def _parse_candidates(body: str, *, allow_inference: bool, retry_attempt: int = 0) -> ParseResult:
    candidates: Dict[str, Dict[str, str]] = {}
    field_trust: Dict[str, Dict[str, FieldTrust]] = {}
    current = ""

    for line in body.splitlines():
        stripped = line.strip()
        section = SECTION_RE.match(stripped) or RELAXED_SECTION_RE.match(stripped)
        if section:
            current = section.group(1).lower().replace("-", "_")
            candidates.setdefault(current, {})
            field_trust.setdefault(current, {})
            continue
        if not current:
            continue
        attr_line = line.replace("**", "")
        bullet = BULLET_RE.match(attr_line) or RELAXED_ATTR_RE.match(attr_line)
        if not bullet:
            continue
        raw_key = bullet.group(1).strip()
        normalized_key = _normalize_key(raw_key)
        value, value_level = _normalize_value(normalized_key, bullet.group(2))
        candidates[current][normalized_key] = value
        f_value, normalization_level, source, reliability = _field_source(raw_key, normalized_key, value_level)
        field_trust[current][normalized_key] = FieldTrust(
            value=value,
            F=f_value,  # type: ignore[arg-type]
            G="this_case",
            R=reliability,  # type: ignore[arg-type]
            normalization_level=normalization_level,
            source=source,
        )

    if allow_inference:
        sections = _split_candidate_sections(body)
        for cid, attrs in candidates.items():
            section_text = sections.get(cid, "")
            if not attrs.get("intervention_force"):
                inferred_force, detail = _infer_force_from_text(cid, section_text)
                if inferred_force:
                    attrs["intervention_force"] = inferred_force
                    source = FieldTrustSource(
                        method="repair_retry" if retry_attempt else "text_inference",
                        key="intervention_force",
                        detail=f"attempt={retry_attempt}" if retry_attempt else detail,
                    )
                    _validate_source(source)
                    field_trust[cid]["intervention_force"] = FieldTrust(
                        value=inferred_force,
                        F="inferred_text",
                        G="generic_domain",
                        R="low",
                        normalization_level="inferred",
                        source=source,
                    )
            if not attrs.get("type"):
                inferred_type = _infer_type_from_text(cid, section_text)
                if inferred_type:
                    attrs["type"] = inferred_type
                    source = FieldTrustSource(
                        method="repair_retry" if retry_attempt else "text_inference",
                        key="type",
                        detail=f"attempt={retry_attempt}" if retry_attempt else "rule=force_keyword_medium",
                    )
                    _validate_source(source)
                    field_trust[cid]["type"] = FieldTrust(
                        value=inferred_type,
                        F="inferred_text",
                        G="generic_domain",
                        R="low",
                        normalization_level="inferred",
                        source=source,
                    )

    missing_fields: Dict[str, List[str]] = {}
    if len(candidates) < 4 or "sol_00_status_quo" not in candidates:
        missing_fields["_portfolio"] = ["minimum_candidates"]
    for cid, attrs in candidates.items():
        missing = [field for field in sorted(_required_fields_for_candidate(cid, attrs)) if not attrs.get(field)]
        if missing:
            missing_fields[cid] = missing

    if missing_fields:
        quality: ParseQuality = "failed"
    else:
        trusts = [trust for per_candidate in field_trust.values() for trust in per_candidate.values()]
        if any(trust.normalization_level == "inferred" for trust in trusts):
            quality = "inferred"
        elif any(trust.normalization_level in {"key_only", "value_translated"} for trust in trusts):
            quality = "normalized"
        else:
            quality = "clean"

    return ParseResult(
        candidates=candidates,
        field_trust=field_trust,
        missing_fields=missing_fields,
        parse_quality=quality,
    )


def _field_provenance_payload(field_trust: Dict[str, Dict[str, FieldTrust]]) -> Dict[str, Dict[str, Dict[str, str]]]:
    payload: Dict[str, Dict[str, Dict[str, str]]] = {}
    for cid, attrs in sorted(field_trust.items()):
        entries = {
            field: _trust_dict(trust)
            for field, trust in sorted(attrs.items())
            if trust.F != "explicit"
        }
        if entries:
            payload[cid] = entries
    return payload


def _build_repair_prompt(base_prompt: str, result: ParseResult) -> str:
    missing_lines: List[str] = []
    for cid, fields in sorted(result.missing_fields.items()):
        if cid == "_portfolio":
            continue
        missing_lines.append(f"- {cid}: {', '.join(fields)}")
    required_format = (
        "REQUIRED OUTPUT FORMAT for each solution section:\n"
        "## sol_XX_name\n"
        "- type: process|architecture|policy|hr|baseline\n"
        "- assurance_level: low|medium|high\n"
        "- intervention_force: weak|medium|strong\n"
        "- relevance_basis: pareto_relevant|rollout_relevant\n"
        "- anti_goodhart_risk: ...\n"
        "Do not rename, translate or omit these field names.\n"
    )
    return (
        base_prompt
        + "\n\n"
        + required_format
        + "\nYour previous output missed required fields. Regenerate the full portfolio in the required format.\n"
        + ("\n".join(missing_lines) if missing_lines else "- missing structural requirements")
    )


def _artifact_epistemic_status(result: ParseResult, used_fallback: bool) -> str:
    if used_fallback or result.parse_quality in {"inferred", "failed"}:
        return "hypothesis"
    if any(
        trust.normalization_level == "value_translated"
        for per_candidate in result.field_trust.values()
        for trust in per_candidate.values()
    ):
        return "inferred"
    return "decision_grade"


def _artifact_trust_level(result: ParseResult, used_fallback: bool) -> str:
    if used_fallback or result.parse_quality in {"inferred", "failed"}:
        return "degraded"
    return "trusted"


def _frontmatter_parse_metadata(
    result: ParseResult,
    *,
    retry_attempted: bool,
    retry_outcome: str,
    used_fallback: bool,
) -> Dict[str, object]:
    inferred_fields: Dict[str, List[Dict[str, str]]] = {}
    for cid, attrs in sorted(result.field_trust.items()):
        rows = []
        for field, trust in sorted(attrs.items()):
            if trust.normalization_level != "inferred":
                continue
            rows.append(
                {
                    "field": field,
                    "F": trust.F,
                    "R": trust.R,
                    "source": trust.source.to_audit_str(),
                }
            )
        if rows:
            inferred_fields[cid] = rows
    return {
        "parse_quality": result.parse_quality,
        "artifact_trust_level": _artifact_trust_level(result, used_fallback),
        "retry_attempted": retry_attempted,
        "retry_outcome": retry_outcome,
        "missing_fields": result.missing_fields,
        "inferred_fields": inferred_fields,
    }


def _validate_portfolio_structure(result: ParseResult) -> Tuple[bool, List[str]]:
    issues: List[str] = []
    candidates = result.candidates

    if len(candidates) < 4 or "sol_00_status_quo" not in candidates:
        issues.append("missing candidates or sol_00_status_quo")

    types = {
        attrs.get("type", "").strip().lower()
        for cid, attrs in candidates.items()
        if cid != "sol_00_status_quo" and attrs.get("type", "").strip()
    }
    if len(types) < 2:
        issues.append(f"insufficient diversity (types={types})")

    forces = {
        attrs.get("intervention_force", "").strip().lower()
        for cid, attrs in candidates.items()
        if cid != "sol_00_status_quo" and attrs.get("intervention_force", "").strip()
    }
    if not {"weak", "medium", "strong"}.issubset(forces):
        issues.append(f"intervention ladder incomplete (forces={forces})")

    for candidate_id, attrs in candidates.items():
        if "assurance_level" not in attrs:
            issues.append(f"missing assurance_level for {candidate_id}")
        if candidate_id != "sol_00_status_quo":
            if "intervention_force" not in attrs:
                issues.append(f"missing intervention_force for {candidate_id}")
            if "relevance_basis" not in attrs:
                issues.append(f"missing relevance_basis for {candidate_id}")

    return not issues, issues


def run_solution_portfolio(project_root: Path, workspace_id: str, llm_mode: str = "local") -> Dict[str, object]:
    workspace = project_root / "cases" / workspace_id
    out_dir = workspace / "solutions"
    out_dir.mkdir(parents=True, exist_ok=True)

    selected_problem = workspace / "problems" / "SelectedProblemCard.md"
    acceptance_spec = workspace / "problems" / "ComparisonAcceptanceSpec.md"
    if not selected_problem.is_file() or not acceptance_spec.is_file():
        raise ValueError("SOLUTION_PORTFOLIO_REQUIRES_PROBLEM_CARD_AND_ACCEPTANCE_SPEC")

    skill_prompt = _load_skill(project_root)
    projection = emit_projection(workspace, "solution_factory_projection")
    payload = {
        "task_type": "build_solution_portfolio",
        "workspace_id": workspace_id,
        "selected_problem_card": selected_problem.read_text(encoding="utf-8"),
        "comparison_acceptance_spec": acceptance_spec.read_text(encoding="utf-8"),
        "projection": projection,
    }

    raw_body = generate_markdown_with_skill(system_skill_prompt=skill_prompt, user_payload=payload, mode=llm_mode)
    raw_path = _write_raw_llm_output(workspace, "solution_portfolio.raw.md", raw_body)
    parse = _parse_candidates(raw_body, allow_inference=False)

    retry_attempted = False
    retry_outcome = "not_attempted"
    final_body = raw_body
    final_parse = parse
    used_fallback = False

    if parse.parse_quality in {"inferred", "failed"}:
        retry_attempted = True
        repair_prompt = _build_repair_prompt(skill_prompt, parse)
        retry_body = generate_markdown_with_skill(system_skill_prompt=repair_prompt, user_payload=payload, mode=llm_mode)
        retry_path = _write_raw_llm_output(workspace, "solution_portfolio.retry.raw.md", retry_body)
        retry_parse = _parse_candidates(retry_body, allow_inference=True, retry_attempt=1)
        retry_outcome = retry_parse.parse_quality
        if len(retry_parse.candidates) < 4 or "sol_00_status_quo" not in retry_parse.candidates:
            raise ValueError("INVALID_SOLUTION_PORTFOLIO_MINIMUM_REQUIREMENTS")
        if retry_parse.parse_quality in {"clean", "normalized"} and not any(
            trust.normalization_level == "value_translated"
            for per_candidate in retry_parse.field_trust.values()
            for trust in per_candidate.values()
        ):
            final_body = retry_body
            final_parse = retry_parse
        else:
            used_fallback = True
            fallback_candidates = _fallback_candidates()
            final_parse = ParseResult(
                candidates=fallback_candidates,
                field_trust=_fallback_field_trust(fallback_candidates),
                missing_fields=retry_parse.missing_fields,
                parse_quality=retry_parse.parse_quality,
            )
            final_body = _canonicalize_candidates(fallback_candidates)
            _write_failed_audit(
                workspace,
                {
                    "event": "solution_portfolio_parse_failed",
                    "workspace_id": workspace_id,
                    "raw_output_path": str(raw_path.relative_to(workspace)),
                    "missing_fields": retry_parse.missing_fields,
                    "retry_attempted": True,
                    "retry_raw_output_path": str(retry_path.relative_to(workspace)),
                    "retry_outcome": retry_parse.parse_quality,
                    "fallback_used": True,
                    "fallback_reason": "parse_failed_after_retry",
                },
            )

    valid_structure, validation_issues = _validate_portfolio_structure(final_parse)
    if not valid_structure and len(final_parse.candidates) < 4:
        raise ValueError("INVALID_SOLUTION_PORTFOLIO_MINIMUM_REQUIREMENTS")
    if not valid_structure and not used_fallback:
        print("  [WARN] LLM solution generation failed struct validation. Falling back to canonical default portfolio.")
        for issue in validation_issues:
            print(f"  [WARN] Solution Portfolio validations failed: {issue}.")
        fallback_candidates = _fallback_candidates()
        final_parse = ParseResult(
            candidates=fallback_candidates,
            field_trust=_fallback_field_trust(fallback_candidates),
            missing_fields=final_parse.missing_fields,
            parse_quality=final_parse.parse_quality,
        )
        final_body = _canonicalize_candidates(fallback_candidates)
        used_fallback = True

    if not used_fallback:
        final_body = _canonicalize_candidates(final_parse.candidates)

    if detect_unanchored_claim_lines(final_body):
        final_body = soften_unanchored_claims(final_body)

    _append_contract_audit(
        workspace,
        {
            "event": "solution_portfolio_parsed",
            "workspace_id": workspace_id,
            "parse_quality": final_parse.parse_quality,
            "artifact_trust_level": _artifact_trust_level(final_parse, used_fallback),
            "field_provenance": _field_provenance_payload(final_parse.field_trust),
            "retry_attempted": retry_attempted,
            "retry_outcome": retry_outcome,
            "fallback_used": used_fallback,
        },
    )

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
        epistemic_status=_artifact_epistemic_status(final_parse, used_fallback),
        next_expected_artifacts=["solutions/ParityReport.md", "solutions/ConflictRecords.md"],
    )
    fm["parse_metadata"] = _frontmatter_parse_metadata(
        final_parse,
        retry_attempted=retry_attempted,
        retry_outcome=retry_outcome,
        used_fallback=used_fallback,
    )

    target = out_dir / "SolutionPortfolio.md"
    write_markdown_artifact(target, fm, final_body)

    return {
        "workspace_id": workspace_id,
        "solution_portfolio": "solutions/SolutionPortfolio.md",
        "llm_mode": llm_mode,
    }
