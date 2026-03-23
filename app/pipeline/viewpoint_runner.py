from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

from app.llm.client import generate_markdown_with_skill
from app.pipeline.artifact_template import build_frontmatter, write_markdown_artifact
from app.pipeline.domain_profiler import build_domain_profile
from app.pipeline.section_contract_guard import (
    build_repair_prompt,
    load_required_sections,
    SectionContractGuard,
)


VIEWPOINTS: List[Tuple[str, str]] = [
    ("strategist", "market fit, value proposition, strategic risks"),
    ("analyst", "metrics, evidence quality, causal assumptions"),
    ("operator", "operational flow, bottlenecks, handoffs"),
    ("architect", "cross-layer consistency and component fit"),
    ("critic", "failure modes, hidden assumptions, blind spots"),
    ("client", "user friction, payer-value mismatch, adoption risks"),
]


def _read_layer(path: Path) -> str:
    if not path.exists():
        return "GAP: layer missing"
    text = path.read_text(encoding="utf-8").strip()
    return text if text else "GAP: layer empty"


def _load_viewpoint_skill(project_root: Path, viewpoint: str) -> str:
    path = project_root / ".agent" / "skills" / f"ec-vp-{viewpoint}" / "SKILL.md"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return f"name: ec-vp-{viewpoint}\ndescription: viewpoint analyzer"


def _market_required(domain_profile: Dict[str, object]) -> bool:
    axes = {
        str(item.get("axis"))
        for item in domain_profile.get("domain_axes", [])
        if isinstance(item, dict) and str(item.get("axis") or "").strip()
    }
    return bool({"market_validation", "commercial_presales_bottleneck"} & axes)


def _active_viewpoints(domain_profile: Dict[str, object]) -> List[Tuple[str, str]]:
    viewpoints = list(VIEWPOINTS)
    if _market_required(domain_profile):
        viewpoints.append(("market", "sales funnel, demand proof, alternatives, status quo defense"))
    return viewpoints


VIEWPOINT_EPISTEMIC_GUARD = """

## Epistemic Guard
- Не подавайте расчетные реконструкции как наблюденные факты.
- Любые числа, проценты, сроки, объемы, маржа, ROI, сроки банкротства и физические пределы должны либо:
  - прямо присутствовать во входных слоях;
  - либо быть явно помечены как estimate / hypothesis / scenario / rough calculation.
- Запрещены формулировки уровня "верифицировано", "математический факт", "гарантированно", "неминуемо", если исходный кейс не содержит достаточной опоры.
- Если вы делаете инженерную или экономическую прикидку, добавьте явный маркер, что это расчетная гипотеза, требующая проверки на данных.
"""

VIEWPOINT_OUTPUT_CONTRACT = """

## OUTPUT STRUCTURE — REQUIRED SECTIONS
Output must contain exactly these sections in this order:

## viewpoint_name
<single line>

## primary_concerns
- <item>

## layer_findings
- layer_1: <finding>
- layer_2: <finding>
- layer_3: <finding>
- layer_4: <finding>

## key_risks
- <risk>

## supported_actions
- <action>

## objections
- <objection>

## evidence_gaps
- <gap or none>

## non_negotiables
- <constraint>

Do not wrap the entire output in a fenced code block.
"""


def run_viewpoints(project_root: Path, workspace_id: str, llm_mode: str = "local") -> Dict[str, object]:
    workspace = project_root / "cases" / workspace_id
    layers_dir = workspace / "layers"
    out_dir = workspace / "viewpoints"
    out_dir.mkdir(parents=True, exist_ok=True)
    domain_profile = build_domain_profile(project_root, workspace_id)

    layer_payload = {
        "layer_1": _read_layer(layers_dir / "layer_1_business_model.md"),
        "layer_2": _read_layer(layers_dir / "layer_2_requirements.md"),
        "layer_3": _read_layer(layers_dir / "layer_3_functional_model.md"),
        "layer_4": _read_layer(layers_dir / "layer_4_allocation_model.md"),
    }

    active_viewpoints = _active_viewpoints(domain_profile)
    required_sections = load_required_sections(project_root, "viewpoint_report")
    artifacts: List[str] = []
    conflicts: List[str] = []

    for viewpoint, focus in active_viewpoints:
        payload = {
            "task_type": "build_viewpoint",
            "workspace_id": workspace_id,
            "viewpoint": viewpoint,
            "focus": focus,
            "layers": layer_payload,
        }
        skill_prompt = _load_viewpoint_skill(project_root, viewpoint) + VIEWPOINT_EPISTEMIC_GUARD + VIEWPOINT_OUTPUT_CONTRACT
        body = generate_markdown_with_skill(system_skill_prompt=skill_prompt, user_payload=payload, mode=llm_mode)
        guard = SectionContractGuard()
        section_check = guard.validate_before_write(
            body=body,
            required_sections=required_sections,
            repair_fn=lambda missing: generate_markdown_with_skill(
                system_skill_prompt=build_repair_prompt(skill_prompt, f"viewpoint:{viewpoint}", missing),
                user_payload=payload,
                mode=llm_mode,
            ),
        )
        if section_check.route == "block":
            raise ValueError(f"SECTION_CONTRACT_VIOLATED_AFTER_REPAIR: viewpoint:{viewpoint}, missing={section_check.missing_sections}")
        body = section_check.body

        frontmatter = build_frontmatter(
            artifact_id=f"{workspace_id}__viewpoint__{viewpoint}",
            artifact_type="viewpoint_report",
            stage="viewpoints",
            parent_refs=[
                "layers/layer_1_business_model.md",
                "layers/layer_2_requirements.md",
                "layers/layer_3_functional_model.md",
                "layers/layer_4_allocation_model.md",
            ],
            source_refs=["layers/layer_1_business_model.md:L1"],
            viewpoints=[viewpoint],
            epistemic_status="inferred",
            next_expected_artifacts=["characterization/CharacterizationPassport.md"],
        )
        frontmatter["parse_metadata"] = {
            "parse_quality": section_check.audit.parse_quality,
            "artifact_trust_level": section_check.audit.artifact_trust_level,
            "retry_attempted": bool(section_check.audit.repair_attempts),
            "retry_outcome": section_check.audit.guard_outcome,
            "repair_attempts": section_check.audit.repair_attempts,
        }

        target = out_dir / f"{viewpoint}.md"
        write_markdown_artifact(target, frontmatter, body)
        artifacts.append(str(target.relative_to(workspace)))

        if "## objections" in body:
            for ln in body.splitlines():
                s = ln.strip()
                if s.startswith("- ") and "risk" in s.lower():
                    conflicts.append(f"{viewpoint}: {s[2:]}")
                    break

    index_body = "# Viewpoint Conflicts Index\n\n" + (
        "\n".join(f"- {x}" for x in conflicts) if conflicts else "- no explicit conflicts"
    )
    index_frontmatter = build_frontmatter(
        artifact_id=f"{workspace_id}__viewpoints_conflicts_index",
        artifact_type="viewpoint_conflicts_index",
        stage="viewpoints",
        parent_refs=artifacts,
        source_refs=["viewpoints/strategist.md:L1"],
        viewpoints=[name for name, _ in active_viewpoints],
        next_expected_artifacts=["characterization/CharacterizationPassport.md"],
    )
    write_markdown_artifact(out_dir / "conflicts_index.md", index_frontmatter, index_body)

    return {
        "workspace_id": workspace_id,
        "viewpoint_count": len(active_viewpoints),
        "artifacts": artifacts,
        "conflicts_index": "viewpoints/conflicts_index.md",
        "domain_profile": "analysis/domain_profile.json",
        "domain_axes": [axis["axis"] for axis in domain_profile.get("domain_axes", [])],
        "market_required": _market_required(domain_profile),
        "llm_mode": llm_mode,
    }
