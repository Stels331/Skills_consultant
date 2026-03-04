from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from app.llm.client import generate_markdown_with_skill
from app.pipeline.artifact_template import build_frontmatter, write_markdown_artifact


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _load_skill_prompt(project_root: Path) -> str:
    path = project_root / ".agent" / "skills" / "ec-characterization" / "SKILL.md"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return "name: ec-characterization\ndescription: characterization"


def run_characterization(project_root: Path, workspace_id: str, llm_mode: str = "local") -> Dict[str, object]:
    workspace = project_root / "cases" / workspace_id
    out_dir = workspace / "characterization"
    out_dir.mkdir(parents=True, exist_ok=True)

    viewpoints_dir = workspace / "viewpoints"
    vp_texts: List[str] = []
    for p in sorted(viewpoints_dir.glob("*.md")):
        if p.name == "conflicts_index.md":
            continue
        vp_texts.append(_read_text(p))

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
    passport_body = generate_markdown_with_skill(
        system_skill_prompt=skill_prompt,
        user_payload={
            "task_type": "build_characterization",
            "workspace_id": workspace_id,
            "viewpoint_summary": "\n".join(vp_texts),
            "layer_summary": "\n".join(layer_texts),
        },
        mode=llm_mode,
    )

    passport_fm = build_frontmatter(
        artifact_id=f"{workspace_id}__characterization_passport",
        artifact_type="characterization_passport",
        stage="characterization",
        parent_refs=[
            "viewpoints/strategist.md",
            "viewpoints/analyst.md",
            "viewpoints/operator.md",
            "viewpoints/architect.md",
            "viewpoints/critic.md",
            "viewpoints/client.md",
        ],
        source_refs=["viewpoints/conflicts_index.md:L1"],
        next_expected_artifacts=["problems/ProblemArchive.md"],
    )
    write_markdown_artifact(out_dir / "CharacterizationPassport.md", passport_fm, passport_body)

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
    write_markdown_artifact(out_dir / "IndicatorSet.md", indicator_fm, indicator_set_body)

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
