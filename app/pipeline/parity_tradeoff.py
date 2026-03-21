from __future__ import annotations

from pathlib import Path
import re
from typing import Dict, List, Set

from app.llm.client import generate_markdown_with_skill
from app.pipeline.artifact_template import build_frontmatter, write_markdown_artifact
from app.pipeline.epistemic_sanitizer import soften_unanchored_claims


def _load_skill(project_root: Path) -> str:
    p = project_root / ".agent" / "skills" / "ec-solution-generator" / "SKILL.md"
    if p.is_file():
        return p.read_text(encoding="utf-8")
    return "name: ec-solution-generator\ndescription: parity"


SOLUTION_ID_RE = re.compile(r"\b(sol_[a-z0-9_]+)\b", re.IGNORECASE)
SECTION_ID_RE = re.compile(r"^##\s+(sol_[a-z0-9_]+)\s*$", re.IGNORECASE | re.MULTILINE)


def _portfolio_ids(portfolio_text: str) -> List[str]:
    ids = [match.group(1).lower() for match in SECTION_ID_RE.finditer(portfolio_text)]
    return ids


def _unknown_solution_ids(text: str, allowed_ids: Set[str]) -> Set[str]:
    seen = {match.group(1).lower() for match in SOLUTION_ID_RE.finditer(text)}
    return {sid for sid in seen if sid not in allowed_ids}


def _canonical_parity_plan(allowed_ids: List[str]) -> str:
    non_baseline = [sid for sid in allowed_ids if sid != "sol_00_status_quo"]
    return (
        "# Parity Plan\n\n"
        "## assumptions\n"
        "- all alternatives are compared against the same baseline portfolio;\n"
        "- budget and timeline remain assumptions unless explicitly anchored in the case input;\n\n"
        "## evaluation_window\n"
        "- pilot-sized comparison window with explicit unknown penalties;\n\n"
        "## indicators_in_scope\n"
        "- confidence_gain\n"
        "- unresolved_gaps\n"
        "- risk_exposure\n"
        "- reversibility\n"
        f"- candidate_set: {', '.join(non_baseline) if non_baseline else 'none'}\n"
    )


def _canonical_parity_report(allowed_ids: List[str]) -> str:
    non_baseline = [sid for sid in allowed_ids if sid != "sol_00_status_quo"]
    primary = non_baseline[0] if non_baseline else "no_primary_candidate"
    support = non_baseline[1] if len(non_baseline) > 1 else primary
    return (
        "# Parity Report\n\n"
        "## Findings\n"
        f"- `{primary}` remains admissible inside the current canonical portfolio.\n"
        f"- `{support}` is retained as a secondary tradeoff position if risk tolerance is lower.\n"
        "- parity validity depends on explicit handling of unknown budget/time assumptions rather than invented hard numbers.\n\n"
        "## Decision Logic\n"
        "- compare only alternatives from the validated SolutionPortfolio.\n"
        "- reject any candidate name that does not exist in the canonical portfolio for this workspace.\n\n"
        "## Traceability\n"
        "- solutions/SolutionPortfolio.md:L1\n"
        "- problems/ComparisonAcceptanceSpec.md:L1\n"
    )


def _canonical_tradeoff_table(allowed_ids: List[str]) -> str:
    rows = []
    default_profiles = {
        "sol_00_status_quo": ("low", "high", "high", "n/a"),
    }
    for idx, sid in enumerate(allowed_ids):
        profile = default_profiles.get(sid)
        if not profile:
            if idx == 1:
                profile = ("medium", "medium", "low", "high")
            elif idx == 2:
                profile = ("medium", "medium", "medium", "medium")
            else:
                profile = ("high", "low", "medium", "medium")
        rows.append(f"| {sid} | {profile[0]} | {profile[1]} | {profile[2]} | {profile[3]} |")
    return (
        "# Tradeoff Table\n\n"
        "| solution | confidence_gain | unresolved_gaps | risk_exposure | reversibility |\n"
        "|---|---|---|---|---|\n"
        + ("\n".join(rows) if rows else "| none | n/a | n/a | n/a | n/a |")
        + "\n"
    )


def _validate_parity_artifact(kind: str, body: str, allowed_ids: Set[str]) -> bool:
    required_headers = {
        "parity_plan": ["# Parity Plan", "## assumptions", "## evaluation_window", "## indicators_in_scope"],
        "parity_report": ["# Parity Report", "## Findings", "## Decision Logic"],
        "tradeoff_table": ["# Tradeoff Table"],
    }[kind]
    if not all(header in body for header in required_headers):
        return False
    if "```markdown" in body.lower():
        return False
    if _unknown_solution_ids(body, allowed_ids):
        return False
    return True


def run_parity_tradeoff(project_root: Path, workspace_id: str, llm_mode: str = "local") -> Dict[str, object]:
    workspace = project_root / "cases" / workspace_id
    out_dir = workspace / "solutions"
    out_dir.mkdir(parents=True, exist_ok=True)

    portfolio = workspace / "solutions" / "SolutionPortfolio.md"
    spec = workspace / "problems" / "ComparisonAcceptanceSpec.md"
    if not portfolio.is_file() or not spec.is_file():
        raise ValueError("PARITY_REQUIRES_PORTFOLIO_AND_ACCEPTANCE_SPEC")

    skill_prompt = _load_skill(project_root)
    portfolio_text = portfolio.read_text(encoding="utf-8")
    allowed_ids = _portfolio_ids(portfolio_text)
    allowed_id_set = set(allowed_ids)

    parity_plan = generate_markdown_with_skill(
        system_skill_prompt=skill_prompt,
        user_payload={
            "task_type": "build_parity_tradeoff",
            "solution_output": "parity_plan",
            "workspace_id": workspace_id,
            "solution_portfolio": portfolio_text,
            "acceptance_spec": spec.read_text(encoding="utf-8"),
        },
        mode=llm_mode,
    )
    parity_plan = soften_unanchored_claims(parity_plan)
    if not _validate_parity_artifact("parity_plan", parity_plan, allowed_id_set):
        print("  [WARN] Parity Plan failed validation. Falling back to canonical parity plan.")
        parity_plan = _canonical_parity_plan(allowed_ids)
    parity_report = generate_markdown_with_skill(
        system_skill_prompt=skill_prompt,
        user_payload={
            "task_type": "build_parity_tradeoff",
            "solution_output": "parity_report",
            "workspace_id": workspace_id,
            "solution_portfolio": portfolio_text,
            "acceptance_spec": spec.read_text(encoding="utf-8"),
        },
        mode=llm_mode,
    )
    parity_report = soften_unanchored_claims(parity_report)
    if not _validate_parity_artifact("parity_report", parity_report, allowed_id_set):
        print("  [WARN] Parity Report failed validation. Falling back to canonical parity report.")
        parity_report = _canonical_parity_report(allowed_ids)
    tradeoff = generate_markdown_with_skill(
        system_skill_prompt=skill_prompt,
        user_payload={
            "task_type": "build_parity_tradeoff",
            "solution_output": "tradeoff_table",
            "workspace_id": workspace_id,
            "solution_portfolio": portfolio_text,
            "acceptance_spec": spec.read_text(encoding="utf-8"),
        },
        mode=llm_mode,
    )
    tradeoff = soften_unanchored_claims(tradeoff)
    if not _validate_parity_artifact("tradeoff_table", tradeoff, allowed_id_set):
        print("  [WARN] Tradeoff Table failed validation. Falling back to canonical tradeoff table.")
        tradeoff = _canonical_tradeoff_table(allowed_ids)

    for name, body, art_type in [
        ("ParityPlan.md", parity_plan, "solution_parity_plan"),
        ("ParityReport.md", parity_report, "solution_parity_report"),
        ("TradeoffTable.md", tradeoff, "solution_tradeoff_table"),
    ]:
        fm = build_frontmatter(
            artifact_id=f"{workspace_id}__{name.replace('.md', '').lower()}",
            artifact_type=art_type,
            stage="solution_factory",
            parent_refs=["solutions/SolutionPortfolio.md", "problems/ComparisonAcceptanceSpec.md"],
            source_refs=["solutions/SolutionPortfolio.md:L1"],
            evidence_refs=["problems/ComparisonAcceptanceSpec.md:L1"],
            next_expected_artifacts=["solutions/ConflictRecords.md", "solutions/SelectedSolutions.md"],
        )
        write_markdown_artifact(out_dir / name, fm, body)

    return {
        "workspace_id": workspace_id,
        "parity_plan": "solutions/ParityPlan.md",
        "parity_report": "solutions/ParityReport.md",
        "tradeoff_table": "solutions/TradeoffTable.md",
        "llm_mode": llm_mode,
    }
