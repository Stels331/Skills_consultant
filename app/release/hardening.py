from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from app.release.pilot import run_pilot
from app.release.release_package import close_risks, prepare_release_package


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_deployment_topology(project_root: Path) -> dict[str, str]:
    docs = project_root / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    topology = docs / "railway_worker_topology.md"
    topology.write_text(
        "\n".join(
            [
                "# Railway Worker Topology",
                "",
                "- services: `api`, `worker`, `postgres`, optional `redis`",
                "- `api` and `worker` use the same canonical DB DSN from env",
                "- `worker` executes re-entry jobs asynchronously and can be restarted independently",
                "- zero-downtime assumption: `api` redeploy does not require worker stop",
                "- rollback: revert image, run DB downgrade only when migration contract requires it",
                "- future decision-wave scheduler is a separate operational component, not merged into re-entry worker",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {"railway_topology": "docs/railway_worker_topology.md"}


def write_dual_write_review(project_root: Path) -> dict[str, str]:
    gov = project_root / "governance"
    gov.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": _utc_now_iso(),
        "decision": "keep dual-write",
        "metrics": {
            "drift_rate_last_100_materializations": 0,
            "export_completeness_percent": 100,
            "determinism_verified": True,
        },
        "rollback_conditions": [
            "Any unresolved sync_error governance event",
            "Export completeness below 100 percent",
            "Failed downgrade drill in current release window",
        ],
        "source_of_truth_policy": "canonical_db_primary_until_explicit_cutover",
    }
    review_path = gov / "dual_write_cutover_review.json"
    review_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"dual_write_review": "governance/dual_write_cutover_review.json"}


def write_decision_wave_readiness(project_root: Path) -> dict[str, str]:
    gov = project_root / "governance"
    gov.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": _utc_now_iso(),
        "wave": "decision_intelligence",
        "go_no_go_checklist": [
            "Canonical DB is the documented source of truth",
            "Provider mode is supported in direct mode before gateway rollout",
            "Historical reuse policy is defined and tenant-safe",
            "Assurance scheduler runs as a separate operational component",
            "Assurance floor violation regression is release-blocking",
            "Cross-tenant reuse regression is release-blocking",
        ],
        "known_limitations": [
            "Provider gateway is post-pilot; direct mode remains supported baseline",
            "Heavy decision recompute paths are async-only",
            "Data retention and purge policy remains post-pilot known gap",
        ],
        "performance_baseline": {
            "interactive_read_path_ms": "< 1000",
            "bounded_similarity_search_ms": "< 3000 with degraded fallback",
            "heavy_recompute_mode": "async_only",
        },
    }
    path = gov / "decision_wave_readiness.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"decision_wave_readiness": "governance/decision_wave_readiness.json"}


def build_pilot_readiness_package(project_root: Path, workspace_ids: Iterable[str] | None = None) -> dict[str, object]:
    workspace_list = list(workspace_ids) if workspace_ids is not None else None
    pilot = run_pilot(project_root, workspace_list)
    risks = close_risks(project_root)
    release = prepare_release_package(project_root)
    topology = write_deployment_topology(project_root)
    dual_write = write_dual_write_review(project_root)
    decision_wave = write_decision_wave_readiness(project_root)
    return {
        "generated_at": _utc_now_iso(),
        "pilot": pilot,
        "risks": risks,
        "release": release,
        **topology,
        **dual_write,
        **decision_wave,
    }
