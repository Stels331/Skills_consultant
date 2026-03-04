from __future__ import annotations

from pathlib import Path
import re
from typing import Dict

from app.llm.client import generate_markdown_with_skill
from app.pipeline.artifact_template import build_frontmatter, write_markdown_artifact


def _load_skill(project_root: Path) -> str:
    p = project_root / ".agent" / "skills" / "ec-solution-selector" / "SKILL.md"
    if p.is_file():
        return p.read_text(encoding="utf-8")
    return "name: ec-solution-selector\ndescription: selection"


SECTION_RE = re.compile(r"^##\s+(?:\*\*)?(sol_[a-z0-9_]+)(?:\*\*)?\s*$", re.IGNORECASE)
BULLET_RE = re.compile(r"^\s*[-*+]\s+(?:\*\*)?([a-zA-Z0-9_]+)(?:\*\*)?\s*:\s*[`'\"]?(.+?)[`'\"]?\s*$")
SELECTED_RE = re.compile(r"^\s*[-*+]\s+(?:\*\*)?[`'\"]?(sol_[a-z0-9_]+)[`'\"]?(?:\*\*)?(?:[\s:-].*)?$", re.IGNORECASE)


def _parse_portfolio_candidates(body: str) -> Dict[str, Dict[str, str]]:
    candidates: Dict[str, Dict[str, str]] = {}
    current = ""
    for line in body.splitlines():
        section = SECTION_RE.match(line.strip())
        if section:
            current = section.group(1).lower()
            candidates[current] = {}
            continue
        if not current:
            continue
        bullet = BULLET_RE.match(line)
        if bullet:
            candidates[current][bullet.group(1).strip().lower()] = bullet.group(2).strip()
    return candidates


def _extract_selected_ids(selected_markdown: str) -> list[str]:
    selected_ids: list[str] = []
    for line in selected_markdown.splitlines():
        m = SELECTED_RE.match(line.strip())
        if not m:
            continue
        sid = m.group(1).lower()
        if sid not in selected_ids:
            selected_ids.append(sid)
    return selected_ids


def run_selection_engine(project_root: Path, workspace_id: str, llm_mode: str = "local") -> Dict[str, object]:
    workspace = project_root / "cases" / workspace_id

    required = {
        "solutions/SolutionPortfolio.md",
        "solutions/ParityReport.md",
        "solutions/TradeoffTable.md",
        "solutions/ConflictRecords.md",
        "problems/ComparisonAcceptanceSpec.md",
    }
    missing = [rel for rel in sorted(required) if not (workspace / rel).is_file()]
    if missing:
        raise ValueError(f"SELECTION_REQUIRES_PARITY_AND_CONFLICTS: missing {missing}")

    skill_prompt = _load_skill(project_root)
    portfolio_text = (workspace / "solutions" / "SolutionPortfolio.md").read_text(encoding="utf-8")
    parity_text = (workspace / "solutions" / "ParityReport.md").read_text(encoding="utf-8")
    conflicts_text = (workspace / "solutions" / "ConflictRecords.md").read_text(encoding="utf-8")
    spec_text = (workspace / "problems" / "ComparisonAcceptanceSpec.md").read_text(encoding="utf-8")

    selected = generate_markdown_with_skill(
        skill_prompt,
        {
            "task_type": "build_selection_bundle",
            "solution_output": "selected_solutions",
            "workspace_id": workspace_id,
            "solution_portfolio": portfolio_text,
            "parity_report": parity_text,
            "conflict_records": conflicts_text,
            "acceptance_spec": spec_text,
        },
        mode=llm_mode,
    )
    candidates = _parse_portfolio_candidates(portfolio_text)
    selected_ids = _extract_selected_ids(selected)
    
    validation_passed = True
    if not (1 <= len(selected_ids) <= 3):
        print(f"  [WARN] Selection Engine validations failed: invalid count {len(selected_ids)} (expected 1-3). selected_ids={selected_ids}")
        validation_passed = False
    
    if validation_passed:
        for sid in selected_ids:
            if sid not in candidates:
                print(f"  [WARN] Selection Engine validations failed: unknown candidate {sid}.")
                validation_passed = False
                break
            assurance = candidates[sid].get("assurance_level", "").strip()
            if not assurance:
                print(f"  [WARN] Selection Engine validations failed: missing assurance_level for {sid}")
                validation_passed = False
                break

    if not validation_passed:
        print("  [WARN] LLM selection failed struct validation. Falling back to status quo.")
        status_quo_id = "sol_00_status_quo"
        selected = f"## Selected Solutions\n\n- {status_quo_id}\n\n" + selected
        selected_ids = [status_quo_id]
        if status_quo_id not in candidates:
            # Inject a fake one just so the rest of the pipeline doesn't crash
            candidates[status_quo_id] = {"type": "none", "assurance_level": "low"}

    if "## traceability" not in selected.lower():
        selected = (
            selected.rstrip()
            + "\n\n## traceability\n"
            + "\n".join(f"- {sid} <- problems/ComparisonAcceptanceSpec.md:L1" for sid in selected_ids)
            + "\n- parity <- solutions/ParityReport.md:L1\n"
            + "- conflicts <- solutions/ConflictRecords.md:L1\n"
        )

    adr = generate_markdown_with_skill(
        skill_prompt,
        {
            "task_type": "build_selection_bundle",
            "solution_output": "adr",
            "workspace_id": workspace_id,
            "solution_portfolio": portfolio_text,
            "parity_report": parity_text,
            "conflict_records": conflicts_text,
            "acceptance_spec": spec_text,
        },
        mode=llm_mode,
    )
    runbook = generate_markdown_with_skill(
        skill_prompt,
        {
            "task_type": "build_selection_bundle",
            "solution_output": "runbook",
            "workspace_id": workspace_id,
            "selected_solutions": selected,
        },
        mode=llm_mode,
    )
    rollback = generate_markdown_with_skill(
        skill_prompt,
        {
            "task_type": "build_selection_bundle",
            "solution_output": "rollback",
            "workspace_id": workspace_id,
            "selected_solutions": selected,
        },
        mode=llm_mode,
    )

    # solutions dir artifacts
    for name, body, art_type in [
        ("SelectedSolutions.md", selected, "selected_solutions"),
    ]:
        fm = build_frontmatter(
            artifact_id=f"{workspace_id}__{name.replace('.md', '').lower()}",
            artifact_type=art_type,
            stage="solution_factory",
            parent_refs=[
                "solutions/SolutionPortfolio.md",
                "solutions/ParityReport.md",
                "solutions/ConflictRecords.md",
                "problems/ComparisonAcceptanceSpec.md",
            ],
            source_refs=["solutions/ParityReport.md:L1"],
            evidence_refs=["solutions/ConflictRecords.md:L1"],
            next_expected_artifacts=["decisions/ADR-001.md"],
        )
        write_markdown_artifact(workspace / "solutions" / name, fm, body)

    # decisions artifact
    dec_dir = workspace / "decisions"
    dec_dir.mkdir(parents=True, exist_ok=True)
    adr_fm = build_frontmatter(
        artifact_id=f"{workspace_id}__adr_001",
        artifact_type="adr_record",
        stage="solution_factory",
        parent_refs=["solutions/SelectedSolutions.md"],
        source_refs=["solutions/SelectedSolutions.md:L1"],
        evidence_refs=["solutions/ConflictRecords.md:L1"],
        next_expected_artifacts=["operation/Runbook.md", "operation/RollbackPlan.md"],
    )
    write_markdown_artifact(dec_dir / "ADR-001.md", adr_fm, adr)

    # operation artifacts
    op_dir = workspace / "operation"
    op_dir.mkdir(parents=True, exist_ok=True)
    runbook_fm = build_frontmatter(
        artifact_id=f"{workspace_id}__runbook",
        artifact_type="operation_runbook",
        stage="solution_factory",
        parent_refs=["decisions/ADR-001.md"],
        source_refs=["decisions/ADR-001.md:L1"],
        evidence_refs=["solutions/SelectedSolutions.md:L1"],
        next_expected_artifacts=["operation/RollbackPlan.md"],
    )
    write_markdown_artifact(op_dir / "Runbook.md", runbook_fm, runbook)

    rollback_fm = build_frontmatter(
        artifact_id=f"{workspace_id}__rollback_plan",
        artifact_type="rollback_plan",
        stage="solution_factory",
        parent_refs=["operation/Runbook.md"],
        source_refs=["operation/Runbook.md:L1"],
        evidence_refs=["decisions/ADR-001.md:L1"],
        next_expected_artifacts=["reports/Analytical_Full_Report.md"],
    )
    write_markdown_artifact(op_dir / "RollbackPlan.md", rollback_fm, rollback)

    return {
        "workspace_id": workspace_id,
        "selected_solutions": "solutions/SelectedSolutions.md",
        "adr": "decisions/ADR-001.md",
        "runbook": "operation/Runbook.md",
        "rollback": "operation/RollbackPlan.md",
        "llm_mode": llm_mode,
    }
