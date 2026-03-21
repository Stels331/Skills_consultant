from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from typing import List, Literal


SectionCheckOutcome = Literal["clean", "repaired", "failed"]


@dataclass(frozen=True)
class SectionCheckResult:
    outcome: SectionCheckOutcome
    body: str
    missing_sections: List[str]
    repair_attempted: bool


def load_required_sections(project_root: Path, contract_name: str) -> List[str]:
    path = project_root / "contracts" / f"{contract_name}.contract.json"
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [str(item) for item in payload.get("required_sections", [])]


def check_required_sections(body: str, required_sections: List[str]) -> List[str]:
    return [section for section in required_sections if section not in body]


def build_repair_prompt(base_prompt: str, artifact_name: str, missing_sections: List[str]) -> str:
    lines = "\n".join(f"- {section}" for section in missing_sections) if missing_sections else "- none"
    return (
        base_prompt
        + "\n\n## OUTPUT REPAIR INSTRUCTIONS\n"
        + f"Artifact: {artifact_name}\n"
        + "The previous output missed required sections. Regenerate the full artifact and include these exact sections:\n"
        + lines
        + "\nDo not omit, rename, or reorder the required sections.\n"
        + "Do not wrap the entire output in a fenced code block.\n"
    )


def repair_sections_with_retry(
    *,
    body: str,
    required_sections: List[str],
    repair_fn,
) -> SectionCheckResult:
    missing = check_required_sections(body, required_sections)
    if not missing:
        return SectionCheckResult(outcome="clean", body=body, missing_sections=[], repair_attempted=False)
    repaired = repair_fn(missing)
    repaired_missing = check_required_sections(repaired, required_sections)
    if not repaired_missing:
        return SectionCheckResult(outcome="repaired", body=repaired, missing_sections=[], repair_attempted=True)
    return SectionCheckResult(
        outcome="failed",
        body=repaired,
        missing_sections=repaired_missing,
        repair_attempted=True,
    )
