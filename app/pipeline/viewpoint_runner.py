from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

from app.llm.client import generate_markdown_with_skill
from app.pipeline.artifact_template import build_frontmatter, write_markdown_artifact


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


def run_viewpoints(project_root: Path, workspace_id: str, llm_mode: str = "local") -> Dict[str, object]:
    workspace = project_root / "cases" / workspace_id
    layers_dir = workspace / "layers"
    out_dir = workspace / "viewpoints"
    out_dir.mkdir(parents=True, exist_ok=True)

    layer_payload = {
        "layer_1": _read_layer(layers_dir / "layer_1_business_model.md"),
        "layer_2": _read_layer(layers_dir / "layer_2_requirements.md"),
        "layer_3": _read_layer(layers_dir / "layer_3_functional_model.md"),
        "layer_4": _read_layer(layers_dir / "layer_4_allocation_model.md"),
    }

    artifacts: List[str] = []
    conflicts: List[str] = []

    for viewpoint, focus in VIEWPOINTS:
        skill_prompt = _load_viewpoint_skill(project_root, viewpoint)
        body = generate_markdown_with_skill(
            system_skill_prompt=skill_prompt,
            user_payload={
                "task_type": "build_viewpoint",
                "workspace_id": workspace_id,
                "viewpoint": viewpoint,
                "focus": focus,
                "layers": layer_payload,
            },
            mode=llm_mode,
        )

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
            next_expected_artifacts=["characterization/CharacterizationPassport.md"],
        )

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
        viewpoints=[name for name, _ in VIEWPOINTS],
        next_expected_artifacts=["characterization/CharacterizationPassport.md"],
    )
    write_markdown_artifact(out_dir / "conflicts_index.md", index_frontmatter, index_body)

    return {
        "workspace_id": workspace_id,
        "viewpoint_count": len(VIEWPOINTS),
        "artifacts": artifacts,
        "conflicts_index": "viewpoints/conflicts_index.md",
        "llm_mode": llm_mode,
    }
