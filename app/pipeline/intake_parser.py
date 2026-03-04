from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List

from app.pipeline.artifact_template import build_frontmatter, write_markdown_artifact


SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+|\n+")


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1", errors="ignore")


def _detect_language(text: str) -> str:
    cyr = sum(1 for ch in text if "\u0400" <= ch <= "\u04FF")
    lat = sum(1 for ch in text if "A" <= ch <= "z")
    return "uk/ru" if cyr >= lat else "en"


def _split_statements(text: str) -> List[str]:
    chunks = [x.strip() for x in SPLIT_PATTERN.split(text) if x.strip()]
    return chunks


def run_intake_parser(project_root: Path, workspace_id: str) -> Dict[str, object]:
    workspace = project_root / "cases" / workspace_id
    raw_dir = workspace / "raw"
    intake_dir = workspace / "intake"
    parsed_dir = workspace / "parsed"

    intake_dir.mkdir(parents=True, exist_ok=True)
    parsed_dir.mkdir(parents=True, exist_ok=True)

    docs = sorted([p for p in raw_dir.iterdir() if p.is_file()]) if raw_dir.exists() else []

    source_items: List[Dict[str, object]] = []
    normalized_blocks: List[str] = []

    for idx, path in enumerate(docs, start=1):
        text = _read_text(path)
        text_norm = "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").split("\n")).strip()
        statements = _split_statements(text_norm)
        sha = hashlib.sha256(text_norm.encode("utf-8", errors="ignore")).hexdigest()[:16]

        source_ref = f"raw/{path.name}:L1"
        source_items.append(
            {
                "doc_id": f"doc_{idx:03d}",
                "path": f"raw/{path.name}",
                "source_ref": source_ref,
                "chars": len(text_norm),
                "statements": len(statements),
                "language": _detect_language(text_norm),
                "sha256_16": sha,
            }
        )

        parsed_payload = {
            "doc_id": f"doc_{idx:03d}",
            "path": f"raw/{path.name}",
            "source_ref": source_ref,
            "language": _detect_language(text_norm),
            "statements": statements,
        }
        (parsed_dir / f"{path.stem}.json").write_text(
            json.dumps(parsed_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (parsed_dir / f"{path.stem}.md").write_text("\n\n".join(statements) + "\n", encoding="utf-8")

        normalized_blocks.append(f"## Source: {path.name}\n\n{text_norm}")

    manifest = {
        "workspace_id": workspace_id,
        "sources": source_items,
        "total_sources": len(source_items),
    }
    (intake_dir / "source_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    frontmatter = build_frontmatter(
        artifact_id=f"{workspace_id}__normalized_case",
        artifact_type="normalized_case",
        stage="intake",
        source_refs=[item["source_ref"] for item in source_items],
        next_expected_artifacts=[
            "layers/layer_1_business_model.md",
            "layers/layer_2_requirements.md",
            "layers/layer_3_functional_model.md",
            "layers/layer_4_allocation_model.md",
        ],
    )

    body = "# Normalized Case\n\n" + ("\n\n".join(normalized_blocks) if normalized_blocks else "No input sources found.")
    write_markdown_artifact(intake_dir / "normalized_case.md", frontmatter, body)

    return {
        "workspace_id": workspace_id,
        "source_count": len(source_items),
        "manifest_path": str((intake_dir / "source_manifest.json").relative_to(workspace)),
        "normalized_case_path": str((intake_dir / "normalized_case.md").relative_to(workspace)),
    }
