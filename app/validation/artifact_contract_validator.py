from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.validation.schema_validator import (
    ValidationIssue,
    ValidationResult,
    load_schema,
    validate_payload,
)


STAGE_ARTIFACT_DIRS = {
    "intake",
    "layers",
    "viewpoints",
    "characterization",
    "problems",
    "solutions",
    "decisions",
    "operation",
    "evidence",
}


@dataclass(frozen=True)
class FrontmatterDocument:
    frontmatter: Dict[str, Any]
    body: str


def _parse_scalar(raw: str) -> Any:
    raw = raw.strip()
    if raw == "":
        return None

    low = raw.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in {"null", "none"}:
        return None

    if (raw.startswith("\"") and raw.endswith("\"")) or (
        raw.startswith("'") and raw.endswith("'")
    ):
        return raw[1:-1]

    if raw.startswith("[") and raw.endswith("]"):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return ast.literal_eval(raw)

    if raw.startswith("{") and raw.endswith("}"):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return ast.literal_eval(raw)

    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def _parse_frontmatter_block(block: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    lines = block.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        if ":" not in line:
            i += 1
            continue

        key, raw_value = line.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()

        if raw_value:
            data[key] = _parse_scalar(raw_value)
            i += 1
            continue

        items: List[Any] = []
        j = i + 1
        while j < len(lines):
            nxt = lines[j]
            nxt_stripped = nxt.strip()
            if not nxt_stripped:
                j += 1
                continue

            if nxt_stripped.startswith("- "):
                items.append(_parse_scalar(nxt_stripped[2:]))
                j += 1
                continue

            if nxt.startswith("  - "):
                items.append(_parse_scalar(nxt.strip()[2:]))
                j += 1
                continue

            break

        data[key] = items if items else None
        i = j

    return data


def read_frontmatter_document(path: Path) -> FrontmatterDocument:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("Missing YAML frontmatter opening delimiter '---'")

    closing_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            closing_idx = idx
            break

    if closing_idx is None:
        raise ValueError("Missing YAML frontmatter closing delimiter '---'")

    block = "\n".join(lines[1:closing_idx])
    body = "\n".join(lines[closing_idx + 1 :])
    return FrontmatterDocument(frontmatter=_parse_frontmatter_block(block), body=body)


def _serialize_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def write_frontmatter_document(path: Path, doc: FrontmatterDocument) -> None:
    lines: List[str] = ["---"]
    for key, value in doc.frontmatter.items():
        lines.append(f"{key}: {_serialize_scalar(value)}")
    lines.append("---")

    body = doc.body
    if body and not body.startswith("\n"):
        body = "\n" + body

    path.write_text("\n".join(lines) + body + "\n", encoding="utf-8")


def _workspace_duplicate_id_check(
    workspace_path: Path,
    artifact_path: Path,
    artifact_id: str,
) -> Optional[ValidationIssue]:
    if not artifact_id:
        return None

    for other in workspace_path.rglob("*.md"):
        if other.resolve() == artifact_path.resolve():
            continue
        try:
            other_doc = read_frontmatter_document(other)
        except Exception:
            continue
        if other_doc.frontmatter.get("id") == artifact_id:
            return ValidationIssue(
                path="$.id",
                expected="unique id within workspace",
                actual=artifact_id,
                message=f"Duplicate artifact id found in {other.relative_to(workspace_path)}",
            )
    return None


def validate_artifact_contract(
    project_root: Path,
    artifact_path: Path,
    workspace_path: Optional[Path] = None,
) -> ValidationResult:
    if not artifact_path.is_file():
        return ValidationResult(
            is_valid=False,
            issues=[
                ValidationIssue(
                    path=str(artifact_path),
                    expected="file exists",
                    actual="missing",
                    message="Artifact file is missing",
                )
            ],
        )

    try:
        doc = read_frontmatter_document(artifact_path)
    except Exception as exc:
        return ValidationResult(
            is_valid=False,
            issues=[
                ValidationIssue(
                    path="frontmatter",
                    expected="valid YAML-like frontmatter",
                    actual="invalid",
                    message=str(exc),
                )
            ],
        )

    schema = load_schema(project_root, "artifact_frontmatter")
    result = validate_payload(doc.frontmatter, schema)
    issues = list(result.issues)

    if workspace_path is not None:
        dup_issue = _workspace_duplicate_id_check(
            workspace_path=workspace_path,
            artifact_path=artifact_path,
            artifact_id=str(doc.frontmatter.get("id", "")),
        )
        if dup_issue is not None:
            issues.append(dup_issue)

    return ValidationResult(is_valid=not issues, issues=issues)


def validate_workspace_artifact_contracts(
    project_root: Path,
    workspace_path: Path,
) -> Dict[str, ValidationResult]:
    results: Dict[str, ValidationResult] = {}
    for md in sorted(workspace_path.rglob("*.md")):
        rel_parts = md.relative_to(workspace_path).parts
        if not rel_parts:
            continue
        if rel_parts[0] not in STAGE_ARTIFACT_DIRS:
            continue
        rel = str(md.relative_to(workspace_path))
        results[rel] = validate_artifact_contract(
            project_root=project_root,
            artifact_path=md,
            workspace_path=workspace_path,
        )
    return results
