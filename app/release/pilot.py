from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Dict[str, object]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_jsonl(path: Path) -> List[Dict[str, object]]:
    if not path.is_file():
        return []
    out: List[Dict[str, object]] = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if not s:
            continue
        try:
            out.append(json.loads(s))
        except Exception:
            continue
    return out


def _select_workspaces(project_root: Path, limit: int = 10) -> List[Path]:
    cases_root = project_root / "cases"
    if not cases_root.is_dir():
        return []
    dirs = sorted([p for p in cases_root.iterdir() if p.is_dir() and p.name.startswith("case_")])
    return dirs[-limit:]


def _case_metrics(ws: Path) -> Dict[str, object]:
    decision_log = _read_jsonl(ws / "governance" / "decision_log.jsonl")
    stage_events = _read_jsonl(ws / "governance" / "stage_events.jsonl")
    reporting_summary = _read_json(ws / "reports" / "reporting_summary.json")

    block_count = sum(1 for e in decision_log if str(e.get("gate_result")) == "block")
    degrade_count = sum(1 for e in decision_log if str(e.get("gate_result")) == "degrade")

    durations = [float(e.get("duration_ms") or 0.0) for e in stage_events]
    avg_duration = round(sum(durations) / len(durations), 3) if durations else 0.0

    missing_sources = list(reporting_summary.get("missing_sources", [])) if reporting_summary else []

    required_reports = [
        ws / "reports" / "Analytical_Full_Report.md",
        ws / "reports" / "Executive_Summary.md",
        ws / "operation" / "Runbook.md",
        ws / "operation" / "RollbackPlan.md",
    ]
    missing_required = [str(p.relative_to(ws)) for p in required_reports if not p.is_file()]

    return {
        "case_id": ws.name,
        "decision_entries": len(decision_log),
        "stage_events": len(stage_events),
        "block_count": block_count,
        "degrade_count": degrade_count,
        "avg_stage_duration_ms": avg_duration,
        "missing_sources": missing_sources,
        "missing_required": missing_required,
    }


def _collect_gaps(case_metrics: Dict[str, object]) -> List[Dict[str, str]]:
    case_id = str(case_metrics["case_id"])
    gaps: List[Dict[str, str]] = []

    if int(case_metrics.get("stage_events", 0)) == 0:
        gaps.append(
            {
                "gap_id": f"{case_id}::process::no_stage_events",
                "case_id": case_id,
                "category": "process",
                "priority": "high",
                "owner": "platform_owner",
                "description": "No stage event logs found for pilot run",
                "status": "open",
            }
        )

    if int(case_metrics.get("block_count", 0)) > 0:
        gaps.append(
            {
                "gap_id": f"{case_id}::functional::stage_blocks",
                "case_id": case_id,
                "category": "functional",
                "priority": "high",
                "owner": "pipeline_owner",
                "description": f"Pilot run has block outcomes: {case_metrics.get('block_count')}",
                "status": "open",
            }
        )

    if int(case_metrics.get("degrade_count", 0)) > 0:
        gaps.append(
            {
                "gap_id": f"{case_id}::quality::degrade_outcomes",
                "case_id": case_id,
                "category": "quality",
                "priority": "medium",
                "owner": "quality_owner",
                "description": f"Pilot run has degrade outcomes: {case_metrics.get('degrade_count')}",
                "status": "open",
            }
        )

    for rel in case_metrics.get("missing_sources", []):
        gaps.append(
            {
                "gap_id": f"{case_id}::documentation::missing_source::{rel}",
                "case_id": case_id,
                "category": "documentation",
                "priority": "medium",
                "owner": "documentation_owner",
                "description": f"Reporting missing source artifact: {rel}",
                "status": "open",
            }
        )

    for rel in case_metrics.get("missing_required", []):
        gaps.append(
            {
                "gap_id": f"{case_id}::functional::missing_required::{rel}",
                "case_id": case_id,
                "category": "functional",
                "priority": "high",
                "owner": "pipeline_owner",
                "description": f"Missing required pilot artifact: {rel}",
                "status": "open",
            }
        )

    return gaps


def _write_case_pilot_report(ws: Path, metrics: Dict[str, object], gaps: List[Dict[str, str]]) -> None:
    lines = [
        f"# Pilot Report — {ws.name}",
        "",
        f"- generated_at: {_utc_now_iso()}",
        f"- decision_entries: {metrics['decision_entries']}",
        f"- stage_events: {metrics['stage_events']}",
        f"- block_count: {metrics['block_count']}",
        f"- degrade_count: {metrics['degrade_count']}",
        f"- avg_stage_duration_ms: {metrics['avg_stage_duration_ms']}",
        "",
        "## Missing Sources",
    ]
    if metrics["missing_sources"]:
        lines.extend([f"- {x}" for x in metrics["missing_sources"]])
    else:
        lines.append("- none")

    lines.extend(["", "## Gaps"])
    if gaps:
        for g in gaps:
            lines.append(
                f"- {g['gap_id']} | category={g['category']} | priority={g['priority']} | owner={g['owner']} | status={g['status']}"
            )
    else:
        lines.append("- none")

    out = ws / "reports" / "pilot_report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_gap_register(project_root: Path, all_gaps: List[Dict[str, str]], case_count: int) -> Dict[str, str]:
    gov = project_root / "governance"
    gov.mkdir(parents=True, exist_ok=True)

    summary = {
        "generated_at": _utc_now_iso(),
        "pilot_case_count": case_count,
        "total_gaps": len(all_gaps),
        "high_priority": sum(1 for g in all_gaps if g["priority"] == "high"),
        "medium_priority": sum(1 for g in all_gaps if g["priority"] == "medium"),
        "low_priority": sum(1 for g in all_gaps if g["priority"] == "low"),
    }

    (gov / "pilot_gap_register.json").write_text(
        json.dumps({"summary": summary, "gaps": all_gaps}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Pilot Gap Register",
        "",
        f"- generated_at: {summary['generated_at']}",
        f"- pilot_case_count: {summary['pilot_case_count']}",
        f"- total_gaps: {summary['total_gaps']}",
        f"- high_priority: {summary['high_priority']}",
        f"- medium_priority: {summary['medium_priority']}",
        f"- low_priority: {summary['low_priority']}",
        "",
        "## Gaps",
    ]
    if all_gaps:
        for g in all_gaps:
            lines.append(
                f"- {g['gap_id']} | case={g['case_id']} | category={g['category']} | priority={g['priority']} | owner={g['owner']} | status={g['status']}"
            )
            lines.append(f"  description: {g['description']}")
    else:
        lines.append("- none")

    (gov / "pilot_gap_register.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "pilot_gap_register": "governance/pilot_gap_register.md",
        "pilot_gap_register_json": "governance/pilot_gap_register.json",
    }


def run_pilot(project_root: Path, workspace_ids: List[str] | None = None) -> Dict[str, object]:
    workspaces: List[Path] = []
    if workspace_ids:
        for wid in workspace_ids:
            ws = project_root / "cases" / wid
            if ws.is_dir():
                workspaces.append(ws)
    else:
        workspaces = _select_workspaces(project_root, limit=10)

    all_gaps: List[Dict[str, str]] = []
    case_reports: List[Dict[str, object]] = []

    for ws in workspaces:
        metrics = _case_metrics(ws)
        gaps = _collect_gaps(metrics)
        _write_case_pilot_report(ws, metrics, gaps)
        all_gaps.extend(gaps)
        case_reports.append(
            {
                "case_id": ws.name,
                "pilot_report": f"cases/{ws.name}/reports/pilot_report.md",
                "block_count": metrics["block_count"],
                "degrade_count": metrics["degrade_count"],
                "gap_count": len(gaps),
            }
        )

    reg = _write_gap_register(project_root, all_gaps, len(workspaces))

    return {
        "generated_at": _utc_now_iso(),
        "pilot_case_count": len(workspaces),
        "total_gaps": len(all_gaps),
        "case_reports": case_reports,
        **reg,
    }
