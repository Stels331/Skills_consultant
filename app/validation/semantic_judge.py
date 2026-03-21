from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from app.principles.library import Principle
from app.validation.cross_case_contamination_validator import validate_cross_case_contamination
from app.validation.cross_case_markers import check_cross_case_markers
from app.validation.fpf_boundary_validator import validate_boundary_discipline
from app.validation.fpf_characteristic_validator import validate_characteristic_legality


@dataclass(frozen=True)
class SemanticIssue:
    code: str
    message: str
    severity: str  # low|medium|high


@dataclass(frozen=True)
class SemanticJudgeResult:
    is_valid: bool
    score: float
    recommendation: str  # pass|degrade|block
    issues: List[SemanticIssue]
    provider: str


STRUCTURAL_ISSUE_CODES = {
    "BODY_TOO_SHORT",
    "PLACEHOLDER_CONTENT",
}

EVIDENTIARY_ISSUE_CODES = {
    "MISSING_SOURCE_REFS",
    "MISSING_EVIDENCE_REFS",
    "UNANCHORED_NUMERIC_CLAIMS",
    "CROSS_CASE_CONTAMINATION",
    "SEMANTIC_DOMAIN_DRIFT",
    "FPF_BOUNDARY_SOUP",
    "CHR_TARGET_PRESENTED_AS_FACT",
}


def _issue_bucket(issue: SemanticIssue) -> str:
    if issue.code in STRUCTURAL_ISSUE_CODES:
        return "structural"
    if issue.code in EVIDENTIARY_ISSUE_CODES or issue.code.startswith(("FPF_", "CHR_")):
        return "evidentiary"
    return "principle"


def _recommendation_from_issues(issues: List[SemanticIssue]) -> str:
    by_bucket = {"structural": [], "evidentiary": [], "principle": []}
    for issue in issues:
        by_bucket[_issue_bucket(issue)].append(issue)

    if any(issue.severity == "high" for issue in issues):
        return "block"

    structural_medium = sum(1 for issue in by_bucket["structural"] if issue.severity == "medium")
    evidentiary_medium = any(issue.severity == "medium" for issue in by_bucket["evidentiary"])
    principle_medium = any(issue.severity == "medium" for issue in by_bucket["principle"])

    if evidentiary_medium or principle_medium or structural_medium >= 2:
        return "degrade"
    return "pass"


def _score_from_issues(issues: List[SemanticIssue]) -> float:
    penalties = {
        "structural": {"high": 0.22, "medium": 0.05, "low": 0.02},
        "evidentiary": {"high": 0.25, "medium": 0.10, "low": 0.03},
        "principle": {"high": 0.18, "medium": 0.07, "low": 0.02},
    }
    score = 1.0
    for issue in issues:
        score -= penalties[_issue_bucket(issue)].get(issue.severity, 0.0)
    return round(max(0.0, score), 3)


def _contains_placeholder(text: str) -> bool:
    low = text.lower()
    markers = ["todo", "tbd", "lorem ipsum", "fixme", "...", "заполнить"]
    return any(m in low for m in markers)


def _has_unanchored_numeric_claims(body: str) -> bool:
    low = body.lower()
    numeric_claim = bool(re.search(r"\b\d+(?:[.,]\d+)?\s*(?:%|квт|м³|м3|дн|дней|дня|недель|тиж|months?)\b", low))
    hard_claim_markers = [
        "верифиц",
        "математическ",
        "guaranteed",
        "неминуем",
        "гарантирован",
        "банкрот",
        "останов",
        "строго =",
        ">15%",
    ]
    if not numeric_claim and not any(marker in low for marker in hard_claim_markers):
        return False
    softeners = [
        "hypothesis",
        "гипотез",
        "estimate",
        "оценоч",
        "scenario",
        "сценар",
        "rough",
        "предполож",
        "requires verification",
        "требует проверки",
        "source:",
        "source_ref",
        "evidence_ref",
    ]
    return not any(marker in low for marker in softeners)


def _local_rule_judge(
    stage_name: str,
    artifact_path: Path,
    body_text: str,
    frontmatter: Dict[str, object],
    principles: List[Principle],
) -> SemanticJudgeResult:
    issues: List[SemanticIssue] = []
    stage = stage_name.lower()
    body = body_text.strip()

    if len(body) < 5:
        issues.append(SemanticIssue("BODY_TOO_SHORT", "Artifact body is too short for semantic review", "high"))

    if _contains_placeholder(body):
        issues.append(SemanticIssue("PLACEHOLDER_CONTENT", "Placeholder tokens detected in artifact body", "high"))

    epi = str(frontmatter.get("epistemic_status", ""))
    source_refs = frontmatter.get("source_refs") or []
    evidence_refs = frontmatter.get("evidence_refs") or []

    if epi in {"observed", "tested", "decision_grade", "operationally_confirmed"} and not source_refs:
        issues.append(SemanticIssue("MISSING_SOURCE_REFS", "source_refs required for current epistemic_status", "high"))

    if epi == "decision_grade" and not evidence_refs:
        issues.append(SemanticIssue("MISSING_EVIDENCE_REFS", "decision_grade artifact must include evidence_refs", "high"))

    if stage in {"viewpoints", "characterization", "problem_factory", "solution_factory", "reporting"}:
        if _has_unanchored_numeric_claims(body):
            issues.append(
                SemanticIssue(
                    "UNANCHORED_NUMERIC_CLAIMS",
                    "Numeric or hard factual claims appear without explicit source anchoring or hypothesis marking",
                    "high" if stage == "viewpoints" else "medium",
                )
            )

    if stage in {"viewpoints", "problem_factory", "solution_factory", "reporting"}:
        contamination_issues = check_cross_case_markers(artifact_path, body)
        for issue in contamination_issues:
            issues.append(
                SemanticIssue(
                    code=issue.code,
                    message=f"{issue.message}: {', '.join(issue.markers)}",
                    severity=issue.severity,
                )
            )
        semantic_drift_issues = validate_cross_case_contamination(artifact_path, body)
        for issue in semantic_drift_issues:
            issues.append(
                SemanticIssue(
                    code=issue.code,
                    message=f"{issue.message}: {', '.join(issue.matched_terms)}",
                    severity=issue.severity,
                )
            )

    if stage in {"problem_factory", "solution_factory", "reporting"}:
        for issue in validate_boundary_discipline(body):
            issues.append(SemanticIssue(code=issue.code, message=issue.message, severity=issue.severity))

    if stage in {"characterization", "problem_factory", "reporting"}:
        for issue in validate_characteristic_legality(body):
            issues.append(SemanticIssue(code=issue.code, message=issue.message, severity=issue.severity))

    principle_ids = {p.principle_id for p in principles}

    if "GOLDILOCKS_PROBLEM" in principle_ids and stage == "problem_factory":
        hints = ["symptom", "симптом", "constraint", "огранич", "acceptance", "критер"]
        if not any(h in body.lower() for h in hints):
            issues.append(SemanticIssue("GOLDILOCKS_INCOMPLETE", "Problem artifact misses key Goldilocks signals", "medium"))

    if "ANTI_GOODHART" in principle_ids and stage in {"characterization", "solution_factory"}:
        hints = ["goodhart", "gaming", "manip", "риск", "искривл"]
        if not any(h in body.lower() for h in hints):
            issues.append(SemanticIssue("ANTI_GOODHART_MISSING", "Anti-Goodhart risk section is missing", "medium"))

    if "UNCERTAINTY_ROUTING" in principle_ids and stage in {"characterization", "problem_factory", "solution_factory", "reporting"}:
        uncertainty_hints = ["gap", "unknown", "not provided", "не указ", "неизвест", "не хватает", "missing"]
        routing_hints = ["clarif", "collect", "defer", "уточ", "сбор данных", "data collection", "повторно", "next step"]
        if any(h in body.lower() for h in uncertainty_hints) and not any(h in body.lower() for h in routing_hints):
            issues.append(SemanticIssue("UNCERTAINTY_NOT_ROUTED", "Known uncertainty is not routed into clarification or deferral", "medium"))

    if "EPISTEMIC_SEPARATION" in principle_ids and stage in {"problem_factory", "solution_factory", "reporting"}:
        certainty_hints = ["единствен", "неизбеж", "математически", "guaranteed", "must", "only"]
        uncertainty_hints = ["gap", "unknown", "not provided", "не указ", "неизвест", "не хватает", "missing", "гипотез"]
        separation_hints = ["hypothesis", "гипотез", "интерпрет", "факт", "предполож"]
        if any(h in body.lower() for h in certainty_hints) and any(h in body.lower() for h in uncertainty_hints):
            if not any(h in body.lower() for h in separation_hints):
                issues.append(SemanticIssue("EPISTEMIC_LAYERS_BLURRED", "Facts and hypotheses are not clearly separated", "medium"))

    recommendation = _recommendation_from_issues(issues)
    score = _score_from_issues(issues)
    return SemanticJudgeResult(
        is_valid=recommendation != "block",
        score=score,
        recommendation=recommendation,
        issues=issues,
        provider="local-rules",
    )


def _openai_judge(
    stage_name: str,
    body_text: str,
    frontmatter: Dict[str, object],
    principles: List[Principle],
) -> SemanticJudgeResult:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")

    principles_payload = [
        {
            "principle_id": p.principle_id,
            "title": p.title,
            "description": p.description,
            "checklist": p.checklist,
        }
        for p in principles
    ]

    instruction = (
        "You are semantic judge. Return strict JSON only with fields: "
        "recommendation(pass|degrade|block), score(0..1), issues[{code,message,severity}]. "
        "Be conservative."
    )

    user_payload = {
        "stage": stage_name,
        "frontmatter": frontmatter,
        "artifact_body": body_text,
        "principles": principles_payload,
    }

    req_payload = {
        "model": model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": instruction}]},
            {"role": "user", "content": [{"type": "input_text", "text": json.dumps(user_payload, ensure_ascii=False)}]},
        ],
        "text": {"format": {"type": "json_object"}},
    }

    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(req_payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=60) as resp:
        raw = json.loads(resp.read().decode("utf-8"))

    output_text = raw.get("output_text", "")
    if not output_text:
        # fallback to nested text blocks if output_text unavailable
        output = raw.get("output", [])
        if output and isinstance(output, list):
            try:
                output_text = output[0]["content"][0]["text"]
            except Exception:
                output_text = "{}"

    parsed = json.loads(output_text or "{}")
    recommendation = str(parsed.get("recommendation", "degrade"))
    score = float(parsed.get("score", 0.5))
    issues = [
        SemanticIssue(
            code=str(i.get("code", "SEMANTIC_ISSUE")),
            message=str(i.get("message", "")),
            severity=str(i.get("severity", "medium")),
        )
        for i in parsed.get("issues", [])
    ]

    return SemanticJudgeResult(
        is_valid=recommendation != "block",
        score=score,
        recommendation=recommendation,
        issues=issues,
        provider=f"openai:{model}",
    )


def run_semantic_judge(
    stage_name: str,
    artifact_path: Path,
    frontmatter: Dict[str, object],
    body_text: str,
    principles: List[Principle],
    mode: Optional[str] = None,
) -> SemanticJudgeResult:
    selected_mode = (mode or os.environ.get("SEMANTIC_JUDGE_MODE", "local")).lower()

    if selected_mode == "openai":
        return _openai_judge(stage_name, body_text, frontmatter, principles)
    return _local_rule_judge(stage_name, artifact_path, body_text, frontmatter, principles)
