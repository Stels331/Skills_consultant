from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

from app.llm.client import generate_markdown_with_skill
from app.pipeline.artifact_template import build_frontmatter, write_markdown_artifact
from app.pipeline.epistemic_projection import emit_projection
from app.pipeline.epistemic_sanitizer import harden_generated_artifact
from app.pipeline.epistemic_store import sync_artifact_to_epistemic_store
from app.pipeline.section_contract_guard import (
    build_repair_prompt,
    load_required_sections,
    SectionContractGuard,
)


LINE_BULLET = re.compile(r"^\s*-\s+(.+)$")
MARKDOWN_FENCE_RE = re.compile(r"(?is)```markdown\s*(.*?)```")


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _load_skill_prompt(project_root: Path) -> str:
    path = project_root / ".agent" / "skills" / "ec-problem-factory" / "SKILL.md"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return "name: ec-problem-factory\ndescription: problem factory"


SELECTED_CARD_OUTPUT_CONTRACT = """

## OUTPUT STRUCTURE — REQUIRED SECTIONS
Output must contain exactly these sections:

## facts
- <source_fact>

## chr_targets
- <normative_target>

## derived_thresholds
- <derived threshold with explicit basis>

## anti_goodhart_conditions
- <condition>

## hypotheses_to_validate
- <hypothesis>

Do not wrap the entire output in a fenced code block.
"""


def _sanitize_problem_artifact_body(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return raw

    fenced = MARKDOWN_FENCE_RE.search(raw)
    if fenced:
        inner = fenced.group(1).strip()
        if inner:
            return inner + ("\n" if not inner.endswith("\n") else "")

    if raw.startswith("```") and raw.endswith("```"):
        raw = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return raw.strip() + ("\n" if raw.strip() else "")


def _extract_indicator_ids(indicator_set_text: str) -> List[str]:
    ids: List[str] = []
    for ln in indicator_set_text.splitlines():
        m = LINE_BULLET.match(ln)
        if not m:
            continue
        token = m.group(1).split("|")[0].strip()
        if token:
            ids.append(token)
    return ids


def run_problem_factory(project_root: Path, workspace_id: str, llm_mode: str = "local") -> Dict[str, object]:
    workspace = project_root / "cases" / workspace_id
    out_dir = workspace / "problems"
    out_dir.mkdir(parents=True, exist_ok=True)

    char_passport = _read(workspace / "characterization" / "CharacterizationPassport.md")
    indicator_set = _read(workspace / "characterization" / "IndicatorSet.md")
    conflicts = _read(workspace / "viewpoints" / "conflicts_index.md")
    projection = emit_projection(workspace, "problem_factory_projection")

    skill_prompt = _load_skill_prompt(project_root)

    archive_body = generate_markdown_with_skill(
        system_skill_prompt=skill_prompt,
        user_payload={
            "task_type": "build_problem_bundle",
            "problem_output": "archive",
            "workspace_id": workspace_id,
            "characterization_passport": char_passport,
            "indicator_set": indicator_set,
            "conflicts_index": conflicts,
            "projection": projection,
        },
        mode=llm_mode,
    )
    archive_body = _sanitize_problem_artifact_body(archive_body)
    archive_body = harden_generated_artifact(archive_body, stage_name="problem_factory", workspace_path=workspace)
    archive_fm = build_frontmatter(
        artifact_id=f"{workspace_id}__problem_archive",
        artifact_type="problem_archive",
        stage="problem_factory",
        parent_refs=[
            "characterization/CharacterizationPassport.md",
            "characterization/IndicatorSet.md",
            "viewpoints/conflicts_index.md",
        ],
        source_refs=["characterization/CharacterizationPassport.md:L1"],
        next_expected_artifacts=["problems/ProblemPortfolio.md"],
    )
    write_markdown_artifact(out_dir / "ProblemArchive.md", archive_fm, archive_body)
    sync_artifact_to_epistemic_store(
        workspace_path=workspace,
        artifact_rel="problems/ProblemArchive.md",
        frontmatter=archive_fm,
        body=archive_body,
    )

    portfolio_body = generate_markdown_with_skill(
        system_skill_prompt=skill_prompt,
        user_payload={
            "task_type": "build_problem_bundle",
            "problem_output": "portfolio",
            "workspace_id": workspace_id,
            "characterization_passport": char_passport,
            "indicator_set": indicator_set,
            "conflicts_index": conflicts,
            "projection": projection,
        },
        mode=llm_mode,
    )
    portfolio_body = _sanitize_problem_artifact_body(portfolio_body)
    portfolio_body = harden_generated_artifact(portfolio_body, stage_name="problem_factory", workspace_path=workspace)
    portfolio_fm = build_frontmatter(
        artifact_id=f"{workspace_id}__problem_portfolio",
        artifact_type="problem_portfolio",
        stage="problem_factory",
        parent_refs=["problems/ProblemArchive.md"],
        source_refs=["problems/ProblemArchive.md:L1"],
        next_expected_artifacts=["problems/SelectedProblemCard.md"],
    )
    write_markdown_artifact(out_dir / "ProblemPortfolio.md", portfolio_fm, portfolio_body)
    sync_artifact_to_epistemic_store(
        workspace_path=workspace,
        artifact_rel="problems/ProblemPortfolio.md",
        frontmatter=portfolio_fm,
        body=portfolio_body,
    )

    card_payload = {
        "task_type": "build_problem_bundle",
        "problem_output": "selected_card",
        "workspace_id": workspace_id,
        "characterization_passport": char_passport,
        "indicator_set": indicator_set,
        "conflicts_index": conflicts,
        "projection": projection,
    }
    card_body = generate_markdown_with_skill(
        system_skill_prompt=skill_prompt + SELECTED_CARD_OUTPUT_CONTRACT,
        user_payload={
            **card_payload,
        },
        mode=llm_mode,
    )
    guard = SectionContractGuard()
    section_check = guard.validate_before_write(
        body=card_body,
        required_sections=load_required_sections(project_root, "selected_problem_card"),
        repair_fn=lambda missing: generate_markdown_with_skill(
            system_skill_prompt=build_repair_prompt(skill_prompt + SELECTED_CARD_OUTPUT_CONTRACT, "selected_problem_card", missing),
            user_payload=card_payload,
            mode=llm_mode,
        ),
    )
    if section_check.route == "block":
        raise ValueError(
            f"SECTION_CONTRACT_VIOLATED_AFTER_REPAIR: selected_problem_card, missing={section_check.missing_sections}"
        )
    card_body = section_check.body
    card_body = _sanitize_problem_artifact_body(card_body)
    card_body = harden_generated_artifact(card_body, stage_name="problem_factory", workspace_path=workspace)
    card_fm = build_frontmatter(
        artifact_id=f"{workspace_id}__selected_problem_card",
        artifact_type="selected_problem_card",
        stage="problem_factory",
        parent_refs=["problems/ProblemPortfolio.md"],
        source_refs=["problems/ProblemPortfolio.md:L1"],
        evidence_refs=["viewpoints/conflicts_index.md:L1"],
        next_expected_artifacts=["problems/ComparisonAcceptanceSpec.md"],
    )
    card_fm["parse_metadata"] = {
        "parse_quality": section_check.audit.parse_quality,
        "artifact_trust_level": section_check.audit.artifact_trust_level,
        "retry_attempted": bool(section_check.audit.repair_attempts),
        "retry_outcome": section_check.audit.guard_outcome,
        "repair_attempts": section_check.audit.repair_attempts,
    }
    write_markdown_artifact(out_dir / "SelectedProblemCard.md", card_fm, card_body)
    sync_artifact_to_epistemic_store(
        workspace_path=workspace,
        artifact_rel="problems/SelectedProblemCard.md",
        frontmatter=card_fm,
        body=card_body,
    )

    indicators = _extract_indicator_ids(indicator_set)
    spec_body = generate_markdown_with_skill(
        system_skill_prompt=skill_prompt,
        user_payload={
            "task_type": "build_problem_bundle",
            "problem_output": "acceptance_spec",
            "workspace_id": workspace_id,
            "indicator_ids": indicators,
            "selected_problem_card": card_body,
            "projection": projection,
        },
        mode=llm_mode,
    )
    spec_body = _sanitize_problem_artifact_body(spec_body)
    spec_body = harden_generated_artifact(spec_body, stage_name="problem_factory", workspace_path=workspace)
    spec_fm = build_frontmatter(
        artifact_id=f"{workspace_id}__comparison_acceptance_spec",
        artifact_type="comparison_acceptance_spec",
        stage="problem_factory",
        parent_refs=["problems/SelectedProblemCard.md", "characterization/IndicatorSet.md"],
        source_refs=["problems/SelectedProblemCard.md:L1"],
        evidence_refs=["characterization/IndicatorSet.md:L1"],
        next_expected_artifacts=["solutions/SolutionPortfolio.md"],
    )
    write_markdown_artifact(out_dir / "ComparisonAcceptanceSpec.md", spec_fm, spec_body)
    sync_artifact_to_epistemic_store(
        workspace_path=workspace,
        artifact_rel="problems/ComparisonAcceptanceSpec.md",
        frontmatter=spec_fm,
        body=spec_body,
    )

    summary = {
        "workspace_id": workspace_id,
        "archive": "problems/ProblemArchive.md",
        "portfolio": "problems/ProblemPortfolio.md",
        "selected_problem_card": "problems/SelectedProblemCard.md",
        "comparison_acceptance_spec": "problems/ComparisonAcceptanceSpec.md",
        "llm_mode": llm_mode,
    }
    (out_dir / "problem_factory_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary
