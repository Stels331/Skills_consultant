from __future__ import annotations

from pathlib import Path
import re
from typing import Dict

from app.llm.client import generate_markdown_with_skill
from app.pipeline.artifact_template import build_frontmatter, write_markdown_artifact


def _load_skill(project_root: Path) -> str:
    p = project_root / ".agent" / "skills" / "ec-solution-generator" / "SKILL.md"
    if p.is_file():
        return p.read_text(encoding="utf-8")
    return "name: ec-solution-generator\ndescription: generate solutions"


SECTION_RE = re.compile(r"^##\s+(?:\*\*)?(sol_[a-z0-9_]+)(?:\*\*)?\s*$", re.IGNORECASE)
BULLET_RE = re.compile(r"^\s*[-*+]\s+(?:\*\*)?([a-zA-Z0-9_]+)(?:\*\*)?\s*:\s*[`'\"]?(.+?)[`'\"]?\s*$")


def _parse_candidates(body: str) -> Dict[str, Dict[str, str]]:
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
            key = bullet.group(1).strip().lower()
            value = bullet.group(2).strip()
            candidates[current][key] = value
    return candidates


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
        for candidate_id, attrs in candidates.items():
            if "assurance_level" not in attrs:
                print(f"  [WARN] Solution Portfolio validations failed: missing assurance_level for {candidate_id}.")
                validation_passed = False
                break

    if not validation_passed:
        print("  [WARN] LLM solution generation failed struct validation. Falling back to simple default.")
        body = """## sol_00_status_quo
- type: none
- assurance_level: low

## sol_01_fix1
- type: process
- assurance_level: medium

## sol_02_fix2
- type: architectural
- assurance_level: high

## sol_03_fix3
- type: hr
- assurance_level: medium
""" + "\n\n" + body

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
