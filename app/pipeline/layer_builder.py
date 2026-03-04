from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from app.pipeline.artifact_template import build_frontmatter, write_markdown_artifact
from app.llm.client import generate_markdown_with_skill


def _load_skill_prompt(project_root: Path) -> str:
    skill_path = project_root / ".agent" / "skills" / "ec-layer-modeler" / "SKILL.md"
    if skill_path.is_file():
        return skill_path.read_text(encoding="utf-8")
    return "name: ec-layer-modeler\ndescription: Build layered model"


def build_layers(project_root: Path, workspace_id: str, llm_mode: str = "local") -> Dict[str, object]:
    workspace = project_root / "cases" / workspace_id
    intake_md = workspace / "intake" / "normalized_case.md"
    layers_dir = workspace / "layers"
    layers_dir.mkdir(parents=True, exist_ok=True)

    if intake_md.exists():
        text = intake_md.read_text(encoding="utf-8")
    else:
        text = ""

    skill_prompt = _load_skill_prompt(project_root)

    artifacts = [
        (
            "layer_1_business_model.md",
            "business_model_layer",
            "layer_1_business_model",
        ),
        (
            "layer_2_requirements.md",
            "requirements_layer",
            "layer_2_requirements",
        ),
        (
            "layer_3_functional_model.md",
            "functional_model_layer",
            "layer_3_functional_model",
        ),
        (
            "layer_4_allocation_model.md",
            "allocation_model_layer",
            "layer_4_allocation_model",
        ),
    ]

    for filename, artifact_type, layer_name in artifacts:
        body = generate_markdown_with_skill(
            system_skill_prompt=skill_prompt,
            user_payload={
                "task_type": "build_layer",
                "layer_name": layer_name,
                "workspace_id": workspace_id,
                "normalized_case": text,
            },
            mode=llm_mode,
        )
        frontmatter = build_frontmatter(
            artifact_id=f"{workspace_id}__{filename.replace('.md', '')}",
            artifact_type=artifact_type,
            stage="layers",
            parent_refs=["intake/normalized_case.md"],
            source_refs=["intake/normalized_case.md:L1"],
            next_expected_artifacts=["viewpoints/strategist.md"],
        )
        write_markdown_artifact(layers_dir / filename, frontmatter, body)

    trace_links = {
        "workspace_id": workspace_id,
        "links": [
            {
                "from": "layer_1_business_model.md",
                "to": "layer_2_requirements.md",
                "relation": "business_to_requirements",
            },
            {
                "from": "layer_2_requirements.md",
                "to": "layer_3_functional_model.md",
                "relation": "requirements_to_functions",
            },
            {
                "from": "layer_3_functional_model.md",
                "to": "layer_4_allocation_model.md",
                "relation": "functions_to_allocation",
            },
        ],
    }
    (layers_dir / "trace_links.json").write_text(
        json.dumps(trace_links, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "workspace_id": workspace_id,
        "layers": [name for name, _, _ in artifacts],
        "trace_links": "layers/trace_links.json",
    }
