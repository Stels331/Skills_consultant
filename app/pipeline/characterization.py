from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from app.llm.client import generate_markdown_with_skill
from app.pipeline.artifact_template import build_frontmatter, write_markdown_artifact
from app.pipeline.epistemic_sanitizer import soften_unanchored_claims
from app.pipeline.epistemic_store import sync_artifact_to_epistemic_store
from app.pipeline.section_contract_guard import (
    build_repair_prompt,
    load_required_sections,
    repair_sections_with_retry,
)


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _load_skill_prompt(project_root: Path) -> str:
    path = project_root / ".agent" / "skills" / "ec-characterization" / "SKILL.md"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return "name: ec-characterization\ndescription: characterization"


CHARACTERIZATION_OUTPUT_CONTRACT = """

## OUTPUT STRUCTURE — REQUIRED SECTIONS
Output must contain exactly these sections in this order:

## optimization_goals
- <item>

## hard_constraints
- <item>

## risk_signals
- <item>

## weakest_link
- <item>

## anti_goodhart_risks
- <item>

## source_summary
- <item>

Do not wrap the entire output in a fenced code block.
"""


def run_characterization(project_root: Path, workspace_id: str, llm_mode: str = "local") -> Dict[str, object]:
    workspace = project_root / "cases" / workspace_id
    out_dir = workspace / "characterization"
    out_dir.mkdir(parents=True, exist_ok=True)

    viewpoints_dir = workspace / "viewpoints"
    vp_texts: List[str] = []
    for p in sorted(viewpoints_dir.glob("*.md")):
        if p.name == "conflicts_index.md":
            continue
        vp_texts.append(soften_unanchored_claims(_read_text(p)))

    layer_texts: List[str] = []
    layers_dir = workspace / "layers"
    for name in [
        "layer_1_business_model.md",
        "layer_2_requirements.md",
        "layer_3_functional_model.md",
        "layer_4_allocation_model.md",
    ]:
        layer_texts.append(_read_text(layers_dir / name))

    skill_prompt = _load_skill_prompt(project_root)
    passport_payload = {
        "task_type": "build_characterization",
        "workspace_id": workspace_id,
        "viewpoint_summary": "\n".join(vp_texts),
        "layer_summary": "\n".join(layer_texts),
    }
    passport_body = generate_markdown_with_skill(
        system_skill_prompt=skill_prompt + CHARACTERIZATION_OUTPUT_CONTRACT,
        user_payload=passport_payload,
        mode=llm_mode,
    )
    required_sections = load_required_sections(project_root, "characterization_passport")
    section_check = repair_sections_with_retry(
        body=passport_body,
        required_sections=required_sections,
        repair_fn=lambda missing: generate_markdown_with_skill(
            system_skill_prompt=build_repair_prompt(skill_prompt + CHARACTERIZATION_OUTPUT_CONTRACT, "characterization_passport", missing),
            user_payload=passport_payload,
            mode=llm_mode,
        ),
    )
    if section_check.outcome == "failed":
        raise ValueError(
            f"SECTION_CONTRACT_VIOLATED_AFTER_REPAIR: characterization_passport, missing={section_check.missing_sections}"
        )
    passport_body = section_check.body

    passport_fm = build_frontmatter(
        artifact_id=f"{workspace_id}__characterization_passport",
        artifact_type="characterization_passport",
        stage="characterization",
        parent_refs=[
            str(p.relative_to(workspace)).replace("\\", "/")
            for p in sorted(viewpoints_dir.glob("*.md"))
        ],
        source_refs=["viewpoints/conflicts_index.md:L1"],
        next_expected_artifacts=["problems/ProblemArchive.md"],
    )
    passport_body = soften_unanchored_claims(passport_body)
    write_markdown_artifact(out_dir / "CharacterizationPassport.md", passport_fm, passport_body)
    sync_artifact_to_epistemic_store(
        workspace_path=workspace,
        artifact_rel="characterization/CharacterizationPassport.md",
        frontmatter=passport_fm,
        body=passport_body,
    )

    indicator_set_body = generate_markdown_with_skill(
        system_skill_prompt=skill_prompt,
        user_payload={
            "task_type": "build_indicator_set",
            "workspace_id": workspace_id,
            "characterization_passport": passport_body,
            "viewpoint_summary": "\n".join(vp_texts),
        },
        mode=llm_mode,
    )
    indicator_fm = build_frontmatter(
        artifact_id=f"{workspace_id}__indicator_set",
        artifact_type="indicator_set",
        stage="characterization",
        parent_refs=["characterization/CharacterizationPassport.md"],
        source_refs=["characterization/CharacterizationPassport.md:L1"],
        next_expected_artifacts=["problems/ProblemArchive.md"],
    )
    indicator_set_body = soften_unanchored_claims(indicator_set_body)
    write_markdown_artifact(out_dir / "IndicatorSet.md", indicator_fm, indicator_set_body)
    sync_artifact_to_epistemic_store(
        workspace_path=workspace,
        artifact_rel="characterization/IndicatorSet.md",
        frontmatter=indicator_fm,
        body=indicator_set_body,
    )

    parity_plan_body = generate_markdown_with_skill(
        system_skill_prompt=skill_prompt,
        user_payload={
            "task_type": "build_parity_plan",
            "workspace_id": workspace_id,
            "characterization_passport": passport_body,
            "indicator_set": indicator_set_body,
        },
        mode=llm_mode,
    )
    parity_fm = build_frontmatter(
        artifact_id=f"{workspace_id}__parity_plan",
        artifact_type="parity_plan",
        stage="characterization",
        parent_refs=["characterization/IndicatorSet.md"],
        source_refs=["characterization/IndicatorSet.md:L1"],
        next_expected_artifacts=["problems/ProblemArchive.md"],
    )
    parity_plan_body = soften_unanchored_claims(parity_plan_body)
    write_markdown_artifact(out_dir / "ParityPlan.md", parity_fm, parity_plan_body)

    card_paths = []
    cards_dir = out_dir / "CharacteristicCards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    indicator_roles = [
        ("decision_confidence_score", "optimization_goal"),
        ("unresolved_critical_gaps", "hard_constraint"),
        ("stakeholder_alignment_risk", "risk_signal"),
    ]
    for key, role in indicator_roles:
        body = generate_markdown_with_skill(
            system_skill_prompt=skill_prompt,
            user_payload={
                "task_type": "build_characteristic_card",
                "workspace_id": workspace_id,
                "indicator": key,
                "role": role,
                "characterization_passport": passport_body,
            },
            mode=llm_mode,
        )
        fm = build_frontmatter(
            artifact_id=f"{workspace_id}__char_card__{key}",
            artifact_type="characteristic_card",
            stage="characterization",
            parent_refs=["characterization/CharacterizationPassport.md"],
            source_refs=["characterization/CharacterizationPassport.md:L1"],
            next_expected_artifacts=["problems/ProblemArchive.md"],
        )
        target = cards_dir / f"{key}.md"
        body = soften_unanchored_claims(body)
        write_markdown_artifact(target, fm, body)
        card_paths.append(str(target.relative_to(workspace)))

    summary = {
        "workspace_id": workspace_id,
        "passport": "characterization/CharacterizationPassport.md",
        "indicator_set": "characterization/IndicatorSet.md",
        "parity_plan": "characterization/ParityPlan.md",
        "characteristic_cards": card_paths,
        "llm_mode": llm_mode,
    }
    (out_dir / "characterization_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return summary
