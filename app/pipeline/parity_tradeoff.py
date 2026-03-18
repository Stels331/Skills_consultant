from __future__ import annotations

from pathlib import Path
from typing import Dict

from app.llm.client import generate_markdown_with_skill
from app.pipeline.artifact_template import build_frontmatter, write_markdown_artifact
from app.pipeline.epistemic_sanitizer import soften_unanchored_claims


def _load_skill(project_root: Path) -> str:
    p = project_root / ".agent" / "skills" / "ec-solution-generator" / "SKILL.md"
    if p.is_file():
        return p.read_text(encoding="utf-8")
    return "name: ec-solution-generator\ndescription: parity"


def run_parity_tradeoff(project_root: Path, workspace_id: str, llm_mode: str = "local") -> Dict[str, object]:
    workspace = project_root / "cases" / workspace_id
    out_dir = workspace / "solutions"
    out_dir.mkdir(parents=True, exist_ok=True)

    portfolio = workspace / "solutions" / "SolutionPortfolio.md"
    spec = workspace / "problems" / "ComparisonAcceptanceSpec.md"
    if not portfolio.is_file() or not spec.is_file():
        raise ValueError("PARITY_REQUIRES_PORTFOLIO_AND_ACCEPTANCE_SPEC")

    skill_prompt = _load_skill(project_root)

    parity_plan = generate_markdown_with_skill(
        system_skill_prompt=skill_prompt,
        user_payload={
            "task_type": "build_parity_tradeoff",
            "solution_output": "parity_plan",
            "workspace_id": workspace_id,
            "solution_portfolio": portfolio.read_text(encoding="utf-8"),
            "acceptance_spec": spec.read_text(encoding="utf-8"),
        },
        mode=llm_mode,
    )
    parity_plan = soften_unanchored_claims(parity_plan)
    parity_report = generate_markdown_with_skill(
        system_skill_prompt=skill_prompt,
        user_payload={
            "task_type": "build_parity_tradeoff",
            "solution_output": "parity_report",
            "workspace_id": workspace_id,
            "solution_portfolio": portfolio.read_text(encoding="utf-8"),
            "acceptance_spec": spec.read_text(encoding="utf-8"),
        },
        mode=llm_mode,
    )
    parity_report = soften_unanchored_claims(parity_report)
    tradeoff = generate_markdown_with_skill(
        system_skill_prompt=skill_prompt,
        user_payload={
            "task_type": "build_parity_tradeoff",
            "solution_output": "tradeoff_table",
            "workspace_id": workspace_id,
            "solution_portfolio": portfolio.read_text(encoding="utf-8"),
            "acceptance_spec": spec.read_text(encoding="utf-8"),
        },
        mode=llm_mode,
    )
    tradeoff = soften_unanchored_claims(tradeoff)

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
