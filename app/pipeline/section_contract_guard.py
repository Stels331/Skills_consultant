from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from typing import Callable, List, Literal


SectionCheckOutcome = Literal["clean", "repaired", "failed"]


@dataclass(frozen=True)
class SectionCheckResult:
    outcome: SectionCheckOutcome
    body: str
    missing_sections: List[str]
    repair_attempted: bool


@dataclass(frozen=True)
class SectionGuardAudit:
    parse_quality: str
    artifact_trust_level: str
    repair_attempts: int
    guard_outcome: str


@dataclass(frozen=True)
class SectionGuardResult:
    route: str
    body: str
    audit: SectionGuardAudit
    missing_sections: List[str]


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


class SectionContractGuard:
    def validate_before_write(
        self,
        *,
        body: str,
        required_sections: List[str],
        repair_fn: Callable[[List[str]], str],
    ) -> SectionGuardResult:
        result = repair_sections_with_retry(
            body=body,
            required_sections=required_sections,
            repair_fn=repair_fn,
        )
        if result.outcome == "clean":
            return SectionGuardResult(
                route="pass",
                body=result.body,
                missing_sections=[],
                audit=SectionGuardAudit(
                    parse_quality="clean",
                    artifact_trust_level="trusted",
                    repair_attempts=0,
                    guard_outcome="pass",
                ),
            )
        if result.outcome == "repaired":
            return SectionGuardResult(
                route="degrade",
                body=result.body,
                missing_sections=[],
                audit=SectionGuardAudit(
                    parse_quality="repaired",
                    artifact_trust_level="trusted",
                    repair_attempts=1,
                    guard_outcome="repaired",
                ),
            )
        return SectionGuardResult(
            route="block",
            body=result.body,
            missing_sections=result.missing_sections,
            audit=SectionGuardAudit(
                parse_quality="failed",
                artifact_trust_level="degraded",
                repair_attempts=1,
                guard_outcome="blocked_after_repair",
            ),
        )
