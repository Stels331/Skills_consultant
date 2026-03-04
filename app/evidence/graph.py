from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

from app.validation.artifact_contract_validator import FrontmatterDocument, write_frontmatter_document

CLAIM_CLASSES = [
    "stated_by_user",
    "observed",
    "inferred",
    "hypothesis",
    "tested",
    "decision_grade",
    "operationally_confirmed",
]

# Lower rank means weaker epistemic confidence.
EPI_RANK = {
    "hypothesis": 0,
    "stated_by_user": 1,
    "inferred": 2,
    "observed": 3,
    "tested": 4,
    "decision_grade": 5,
    "operationally_confirmed": 6,
}


@dataclass(frozen=True)
class EvidenceGraphResult:
    claim_count: int
    edge_count: int
    inferred_epistemic_status: str
    untraceable_decision_claims: int
    graph_markdown_path: str
    graph_index_path: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_claim_lines(body_text: str) -> List[str]:
    lines: List[str] = []
    for raw in body_text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("#"):
            continue
        if s.startswith("- "):
            s = s[2:].strip()
        if len(s) < 3:
            continue
        lines.append(s)
    if lines:
        return lines
    compact = re.sub(r"\s+", " ", body_text).strip()
    if compact:
        return [compact[:500]]
    return []


def _classify_claim(text: str, fallback_status: str) -> str:
    low = text.lower()
    if any(k in low for k in ["hypothesis", "гипотез", "предполож", "may", "might"]):
        return "hypothesis"
    if any(k in low for k in ["operationally confirmed", "confirmed in production", "эксплуатац", "подтверждено"]):
        return "operationally_confirmed"
    if any(k in low for k in ["decision", "selected", "choose", "выбрано", "решение"]):
        return "decision_grade"
    if any(k in low for k in ["tested", "experiment", "validated", "протест", "проверено"]):
        return "tested"
    if any(k in low for k in ["observed", "measured", "факт", "наблюда", "метрика"]):
        return "observed"
    if any(k in low for k in ["inferred", "likely", "because", "следовательно", "вероятно"]):
        return "inferred"
    if any(k in low for k in ["user said", "заявил", "по словам", "со слов", "reported by"]):
        return "stated_by_user"
    return fallback_status if fallback_status in EPI_RANK else "inferred"


def _inherit_epistemic_status(classes: List[str], fallback_status: str) -> str:
    all_statuses = [c for c in classes if c in EPI_RANK]
    if fallback_status in EPI_RANK:
        all_statuses.append(fallback_status)
    if not all_statuses:
        return "inferred"
    return min(all_statuses, key=lambda c: EPI_RANK[c])


def _load_graph(path: Path, workspace_id: str) -> Dict[str, object]:
    if not path.is_file():
        return {
            "workspace_id": workspace_id,
            "updated_at": _utc_now_iso(),
            "claims": [],
            "edges": [],
            "artifacts": {},
        }
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raw = {}
    return {
        "workspace_id": raw.get("workspace_id", workspace_id),
        "updated_at": _utc_now_iso(),
        "claims": list(raw.get("claims", [])),
        "edges": list(raw.get("edges", [])),
        "artifacts": dict(raw.get("artifacts", {})),
    }


def _render_graph_markdown(graph: Dict[str, object]) -> str:
    lines = [
        "# Evidence Graph",
        "",
        f"- updated_at: {graph['updated_at']}",
        f"- claims_count: {len(graph['claims'])}",
        f"- edges_count: {len(graph['edges'])}",
        "",
        "## Claims",
    ]
    for c in graph["claims"]:
        lines.append(
            f"- {c['claim_id']} | class={c['claim_class']} | artifact={c['artifact_path']} | text={c['claim_text'][:120]}"
        )
    lines.extend(["", "## Edges"])
    for e in graph["edges"]:
        lines.append(f"- {e['from']} -> {e['to']} | kind={e['edge_kind']}")
    lines.append("")
    return "\n".join(lines)


def _artifact_rel(workspace_path: Path, artifact_path: Path) -> str:
    try:
        return str(artifact_path.relative_to(workspace_path))
    except Exception:
        return str(artifact_path)


def build_and_persist_evidence_graph(
    workspace_path: Path,
    artifact_path: Path,
    frontmatter: Dict[str, object],
    body_text: str,
) -> EvidenceGraphResult:
    workspace_id = workspace_path.name
    evidence_dir = workspace_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    graph_index = evidence_dir / "evidence_graph.json"
    graph_doc = evidence_dir / "evidence_graph.md"

    graph = _load_graph(graph_index, workspace_id)

    artifact_rel = _artifact_rel(workspace_path, artifact_path)
    existing_claims = [c for c in graph["claims"] if c.get("artifact_path") != artifact_rel]
    existing_edges = [e for e in graph["edges"] if not str(e.get("from", "")).startswith(f"claim::{artifact_rel}::")]

    source_refs = list(frontmatter.get("source_refs") or [])
    evidence_refs = list(frontmatter.get("evidence_refs") or [])
    fallback_epi = str(frontmatter.get("epistemic_status") or "inferred")

    claim_lines = _extract_claim_lines(body_text)
    claims: List[Dict[str, object]] = []
    edges: List[Dict[str, object]] = []
    claim_classes: List[str] = []

    for idx, claim_text in enumerate(claim_lines, start=1):
        claim_class = _classify_claim(claim_text, fallback_epi)
        claim_classes.append(claim_class)
        claim_id = f"claim::{artifact_rel}::c{idx:03d}"
        claims.append(
            {
                "claim_id": claim_id,
                "artifact_path": artifact_rel,
                "artifact_id": str(frontmatter.get("id") or "unknown"),
                "claim_text": claim_text,
                "claim_class": claim_class,
                "created_at": _utc_now_iso(),
            }
        )
        for ref in source_refs:
            edges.append({"from": claim_id, "to": str(ref), "edge_kind": "source_ref"})
        for ref in evidence_refs:
            edges.append({"from": claim_id, "to": str(ref), "edge_kind": "evidence_ref"})

    inferred = _inherit_epistemic_status(claim_classes, fallback_epi)

    all_claims = existing_claims + claims
    all_edges = existing_edges + edges

    graph["claims"] = all_claims
    graph["edges"] = all_edges
    artifacts = dict(graph.get("artifacts", {}))
    artifacts[artifact_rel] = {
        "artifact_id": str(frontmatter.get("id") or "unknown"),
        "epistemic_status": inferred,
        "claim_count": len(claims),
        "updated_at": _utc_now_iso(),
    }
    graph["artifacts"] = artifacts

    untraceable_decision_claims = 0
    for c in claims:
        if c["claim_class"] != "decision_grade":
            continue
        linked = [e for e in edges if e["from"] == c["claim_id"]]
        if not linked:
            untraceable_decision_claims += 1

    graph_index.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    now = _utc_now_iso()
    graph_fm = {
        "id": f"{workspace_id}__evidence_graph",
        "artifact_type": "evidence_graph",
        "stage": "evidence",
        "state": "evidence_linked",
        "parent_refs": [artifact_rel],
        "source_refs": source_refs,
        "evidence_refs": evidence_refs,
        "viewpoints": [],
        "epistemic_status": "observed",
        "assurance_level": "medium",
        "valid_until": "2026-12-31",
        "owner_role": "analyst",
        "gate_status": "pending",
        "violated_principles": [],
        "next_expected_artifacts": [],
        "created_at": now,
        "updated_at": now,
    }
    write_frontmatter_document(
        graph_doc,
        FrontmatterDocument(frontmatter=graph_fm, body=_render_graph_markdown(graph)),
    )

    return EvidenceGraphResult(
        claim_count=len(claims),
        edge_count=len(edges),
        inferred_epistemic_status=inferred,
        untraceable_decision_claims=untraceable_decision_claims,
        graph_markdown_path=str(graph_doc.relative_to(workspace_path)),
        graph_index_path=str(graph_index.relative_to(workspace_path)),
    )
