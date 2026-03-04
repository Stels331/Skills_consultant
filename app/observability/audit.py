from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List


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
        except json.JSONDecodeError:
            continue
    return out


def build_audit_trail(workspace_path: Path) -> Dict[str, object]:
    gov = workspace_path / "governance"
    decisions = _read_jsonl(gov / "decision_log.jsonl")
    stage_events = _read_jsonl(gov / "stage_events.jsonl")

    by_stage = defaultdict(lambda: Counter())
    reasons = Counter()
    total_ms = 0.0
    total_events = 0
    for ev in stage_events:
        stage = str(ev.get("stage_name") or "unknown")
        gate = str(ev.get("gate_result") or "unknown")
        by_stage[stage][gate] += 1
        dur = float(ev.get("duration_ms") or 0.0)
        total_ms += dur
        total_events += 1

    for d in decisions:
        for v in d.get("violations", []):
            reasons[str(v.get("message") or "unknown")] += 1

    p95_ms = 0.0
    durations = sorted(float(ev.get("duration_ms") or 0.0) for ev in stage_events)
    if durations:
        idx = min(len(durations) - 1, int(0.95 * (len(durations) - 1)))
        p95_ms = durations[idx]

    summary = {
        "workspace_id": workspace_path.name,
        "decision_log_entries": len(decisions),
        "stage_event_entries": len(stage_events),
        "stage_outcomes": {k: dict(v) for k, v in by_stage.items()},
        "top_block_degrade_reasons": reasons.most_common(10),
        "avg_stage_duration_ms": round(total_ms / total_events, 3) if total_events else 0.0,
        "p95_stage_duration_ms": round(p95_ms, 3),
    }

    lines = [
        "# Audit Trail",
        "",
        f"- workspace_id: {summary['workspace_id']}",
        f"- decision_log_entries: {summary['decision_log_entries']}",
        f"- stage_event_entries: {summary['stage_event_entries']}",
        f"- avg_stage_duration_ms: {summary['avg_stage_duration_ms']}",
        f"- p95_stage_duration_ms: {summary['p95_stage_duration_ms']}",
        "",
        "## Stage Outcomes",
    ]
    for stage, counters in summary["stage_outcomes"].items():
        lines.append(f"- {stage}: {counters}")

    lines.extend(["", "## Top Reasons"])
    for reason, cnt in summary["top_block_degrade_reasons"]:
        lines.append(f"- {reason}: {cnt}")
    if not summary["top_block_degrade_reasons"]:
        lines.append("- none")

    report_dir = workspace_path / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "audit_trail.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (report_dir / "audit_trail.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return summary
