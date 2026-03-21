from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from app.pipeline.epistemic_graph import load_graph, save_graph
from app.pipeline.epistemic_ledger import append_event, build_event


@dataclass(frozen=True)
class ConflictIssue:
    code: str
    message: str
    severity: str  # low|medium|high
    conflict_id: str


def _normalize_statement_key(node: Dict[str, object]) -> str:
    explicit = str(node.get("claim_key") or "").strip().lower()
    if explicit:
        return explicit
    statement = str(node.get("statement") or "").lower()
    statement = re.sub(r"\b\d+(?:[.,]\d+)?\b", "#", statement)
    statement = re.sub(r"[^a-zа-я0-9#]+", " ", statement, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", statement).strip()


def _polarity(node: Dict[str, object]) -> str:
    text = str(node.get("statement") or "").lower()
    if any(marker in text for marker in [" not ", " no ", "нет ", "cannot", "forbid", "запрещ", "нельзя"]):
        return "negative"
    return "positive"


def _is_selection_critical(node: Dict[str, object]) -> bool:
    return str(node.get("node_type") or "") in {"source_fact", "derived_metric", "decision_constraint", "normative_target", "disputed_claim"}


def materialize_conflicts(workspace_path: Path) -> Dict[str, object]:
    graph_path = workspace_path / "analysis" / "epistemic_graph.json"
    graph = load_graph(graph_path, workspace_path.name)
    nodes = list(graph.get("nodes") or [])
    edges = list(graph.get("edges") or [])
    node_map = {str(node["id"]): node for node in nodes}
    existing_conflict_ids = {str(node["id"]) for node in nodes if str(node.get("node_type")) == "conflict_case"}
    edge_keys = {(str(edge["edge_type"]), str(edge["from"]), str(edge["to"])) for edge in edges}

    by_key: Dict[str, List[Dict[str, object]]] = {}
    for node in nodes:
        if str(node.get("node_type")) not in {"source_fact", "derived_metric", "normative_target", "decision_constraint", "interpretation"}:
            continue
        by_key.setdefault(_normalize_statement_key(node), []).append(node)

    new_nodes: List[Dict[str, object]] = []
    new_edges: List[Dict[str, object]] = []
    conflicts: List[Dict[str, object]] = []

    for key, candidates in by_key.items():
        if len(candidates) < 2:
            continue
        polarities = {_polarity(node) for node in candidates}
        different_values = len({str(node.get("statement") or "").strip().lower() for node in candidates}) > 1
        if len(polarities) < 2 and not different_values:
            continue

        conflict_id = f"conflict::{abs(hash(key))}"
        if conflict_id not in existing_conflict_ids and conflict_id not in {str(n['id']) for n in new_nodes}:
            conflict_node = {
                "id": conflict_id,
                "node_type": "conflict_case",
                "statement": f"Conflict on claim key: {key}",
                "source_refs": sorted({ref for node in candidates for ref in node.get("source_refs", [])}),
                "epistemic_status": "disputed",
                "stage": "validation",
                "owner": "validator",
                "created_at": "2026-03-19T00:00:00+00:00",
                "updated_at": "2026-03-19T00:00:00+00:00",
                "resolution_status": "open",
                "claim_key": key,
            }
            new_nodes.append(conflict_node)
        for node in candidates:
            if _is_selection_critical(node) and str(node.get("node_type")) != "disputed_claim":
                disputed_id = f"disputed::{node['id']}"
                if disputed_id not in node_map and disputed_id not in {str(n['id']) for n in new_nodes}:
                    new_nodes.append(
                        {
                            "id": disputed_id,
                            "node_type": "disputed_claim",
                            "statement": str(node.get("statement") or ""),
                            "source_refs": list(node.get("source_refs") or []),
                            "epistemic_status": "disputed",
                            "stage": str(node.get("stage") or "validation"),
                            "owner": "validator",
                            "created_at": "2026-03-19T00:00:00+00:00",
                            "updated_at": "2026-03-19T00:00:00+00:00",
                            "claim_key": key,
                            "origin_id": str(node["id"]),
                        }
                    )
                    if ("DERIVED_FROM", disputed_id, str(node["id"])) not in edge_keys:
                        new_edges.append({"edge_type": "DERIVED_FROM", "from": disputed_id, "to": str(node["id"]), "provenance": "conflict_validator"})
            if ("CONTRADICTS", str(node["id"]), conflict_id) not in edge_keys:
                new_edges.append({"edge_type": "CONTRADICTS", "from": str(node["id"]), "to": conflict_id, "provenance": "conflict_validator"})
        conflicts.append({"conflict_id": conflict_id, "claim_key": key, "node_ids": [str(node["id"]) for node in candidates]})

    if new_nodes or new_edges:
        graph["nodes"] = nodes + new_nodes
        graph["edges"] = edges + new_edges
        save_graph(graph_path, graph)
        append_event(
            workspace_path / "governance" / "epistemic_ledger.jsonl",
            build_event(
                event_type="conflict_marked",
                workspace_id=workspace_path.name,
                stage="validation",
                target_id=conflicts[0]["conflict_id"] if conflicts else "conflict_batch",
                payload={"conflicts": conflicts},
            ),
        )
    return graph


def validate_unresolved_conflicts(workspace_path: Path) -> List[ConflictIssue]:
    graph = materialize_conflicts(workspace_path)
    issues: List[ConflictIssue] = []
    for node in graph.get("nodes", []):
        if str(node.get("node_type")) != "conflict_case":
            continue
        status = str(node.get("resolution_status") or "open").lower()
        if status in {"resolved", "waived"}:
            continue
        issues.append(
            ConflictIssue(
                code="UNRESOLVED_SELECTION_CONFLICT",
                message="Selection-critical contradiction remains unresolved",
                severity="high",
                conflict_id=str(node["id"]),
            )
        )
    return issues
