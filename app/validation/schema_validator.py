from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


JSON_TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    expected: str
    actual: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    issues: List[ValidationIssue]


class SchemaValidationError(ValueError):
    pass


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _matches_type(value: Any, type_name: str) -> bool:
    py_type = JSON_TYPE_MAP[type_name]
    if type_name == "number":
        return isinstance(value, py_type) and not isinstance(value, bool)
    if type_name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, py_type)


def _validate(payload: Any, schema: Dict[str, Any], path: str, out: List[ValidationIssue]) -> None:
    expected_type = schema.get("type")
    if expected_type is not None:
        expected_types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(_matches_type(payload, t) for t in expected_types):
            out.append(
                ValidationIssue(
                    path=path,
                    expected="|".join(expected_types),
                    actual=_type_name(payload),
                    message="Type mismatch",
                )
            )
            return

    enum_values = schema.get("enum")
    if enum_values is not None and payload not in enum_values:
        out.append(
            ValidationIssue(
                path=path,
                expected=f"enum({enum_values})",
                actual=repr(payload),
                message="Value is not in enum",
            )
        )

    if isinstance(payload, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in payload:
                out.append(
                    ValidationIssue(
                        path=f"{path}.{key}",
                        expected="present",
                        actual="missing",
                        message="Required field is missing",
                    )
                )

        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)

        for key, val in payload.items():
            subpath = f"{path}.{key}"
            if key in properties:
                _validate(val, properties[key], subpath, out)
            elif not additional:
                out.append(
                    ValidationIssue(
                        path=subpath,
                        expected="defined property",
                        actual="additional property",
                        message="Additional properties are not allowed",
                    )
                )

    if isinstance(payload, list):
        item_schema = schema.get("items")
        if item_schema is not None:
            for idx, val in enumerate(payload):
                _validate(val, item_schema, f"{path}[{idx}]", out)


def validate_payload(payload: Any, schema: Dict[str, Any]) -> ValidationResult:
    issues: List[ValidationIssue] = []
    _validate(payload, schema, "$", issues)
    return ValidationResult(is_valid=not issues, issues=issues)


def load_schema(project_root: Path, schema_id: str) -> Dict[str, Any]:
    schema_path = project_root / "schemas" / f"{schema_id}.schema.json"
    if not schema_path.is_file():
        raise FileNotFoundError(f"Schema not found: {schema_path}")
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_artifact(project_root: Path, artifact_path: Path, schema_id: str) -> ValidationResult:
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

    schema = load_schema(project_root, schema_id)
    with artifact_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    return validate_payload(payload, schema)


DEFAULT_WORKSPACE_SCHEMA_MAP = {
    "model/case_model.json": "case_model",
    "workspace_metadata.json": "workspace_metadata",
    "state/session_state.json": "session_state",
    "analysis/contradictions.json": "contradictions",
    "quality/quality_metrics.json": "quality_metrics",
    "dialogue/question_queue.json": "question_queue",
    "analysis/problem_card.json": "problem_card",
}


def validate_workspace(
    project_root: Path,
    workspace_path: Path,
    schema_map: Optional[Dict[str, str]] = None,
) -> Dict[str, ValidationResult]:
    mapping = schema_map or DEFAULT_WORKSPACE_SCHEMA_MAP
    results: Dict[str, ValidationResult] = {}

    for rel, schema_id in mapping.items():
        artifact = workspace_path / rel
        results[rel] = validate_artifact(project_root, artifact, schema_id)

    return results


def raise_on_invalid(results: Dict[str, ValidationResult]) -> None:
    errors = []
    for rel, result in results.items():
        if result.is_valid:
            continue
        for issue in result.issues:
            errors.append(
                f"{rel}: {issue.path} expected={issue.expected} actual={issue.actual}: {issue.message}"
            )
    if errors:
        raise SchemaValidationError("\n".join(errors))
