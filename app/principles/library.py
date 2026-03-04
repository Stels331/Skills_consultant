from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class Principle:
    principle_id: str
    title: str
    scope_stages: List[str]
    description: str
    checklist: List[str]
    source_path: str


def _parse_kv(lines: List[str], key: str) -> str:
    prefix = f"{key}:"
    for line in lines:
        if line.lower().startswith(prefix.lower()):
            return line.split(":", 1)[1].strip()
    return ""


def _parse_section(lines: List[str], heading: str) -> List[str]:
    out: List[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.lower() == f"{heading.lower()}:":
            in_section = True
            continue

        if in_section and stripped.endswith(":") and not stripped.startswith("-"):
            break

        if in_section:
            if stripped.startswith("- "):
                out.append(stripped[2:].strip())
            elif stripped:
                out.append(stripped)
    return out


def _load_principle(path: Path) -> Principle:
    text = path.read_text(encoding="utf-8")
    lines = [line.rstrip() for line in text.splitlines()]

    pid = _parse_kv(lines, "principle_id")
    title = _parse_kv(lines, "title")
    scopes_raw = _parse_kv(lines, "scope_stages")
    scopes = [x.strip().lower() for x in scopes_raw.split(",") if x.strip()]
    description_lines = _parse_section(lines, "Description")
    checklist = _parse_section(lines, "Checklist")

    return Principle(
        principle_id=pid or path.stem,
        title=title or path.stem,
        scope_stages=scopes,
        description=" ".join(description_lines).strip(),
        checklist=checklist,
        source_path=str(path),
    )


def load_principles_for_stage(project_root: Path, stage_name: str) -> List[Principle]:
    stage = stage_name.lower()
    principles_dir = project_root / ".agent" / "principles"
    if not principles_dir.is_dir():
        return []

    out: List[Principle] = []
    for path in sorted(principles_dir.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        principle = _load_principle(path)
        if not principle.scope_stages or stage in principle.scope_stages:
            out.append(principle)
    return out
