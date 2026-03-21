from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from app.pipeline.epistemic_graph import load_graph


@dataclass(frozen=True)
class ConstraintCompilationResult:
    lawful_constraints: List[Dict[str, object]]
    rejected_constraints: List[Dict[str, object]]


def _index_edges(edges: List[Dict[str, object]]) -> tuple[Dict[str, List[Dict[str, object]]], Dict[str, List[Dict[str, object]]]]:
    incoming: Dict[str, List[Dict[str, object]]] = {}
    outgoing: Dict[str, List[Dict[str, object]]] = {}
    for edge in edges:
        incoming.setdefault(str(edge["to"]), []).append(edge)
        outgoing.setdefault(str(edge["from"]), []).append(edge)
    return incoming, outgoing


def compile_lawful_constraints(workspace_path: Path) -> ConstraintCompilationResult:
    graph = load_graph(workspace_path / "analysis" / "epistemic_graph.json", workspace_path.name)
    nodes = {str(node["id"]): node for node in graph.get("nodes", [])}
    incoming, outgoing = _index_edges(list(graph.get("edges", [])))

    lawful: List[Dict[str, object]] = []
    rejected: List[Dict[str, object]] = []

    for node in nodes.values():
        if str(node.get("node_type")) != "decision_constraint":
            continue
        node_id = str(node["id"])
        reasons: List[str] = []

        if str(node.get("epistemic_status") or "").lower() in {"hypothesis", "disputed", "unresolved"}:
            reasons.append("constraint_status_not_lawful")

        incoming_edges = incoming.get(node_id, [])
        if any(
            str(nodes.get(str(edge["from"]), {}).get("node_type")) in {"hypothesis", "assumption"}
            for edge in incoming_edges
        ):
            reasons.append("hypothesis_to_decision_constraint_forbidden")
        if any(str(nodes.get(str(edge["from"]), {}).get("node_type")) == "interpretation" for edge in incoming_edges):
            reasons.append("interpretation_to_hard_constraint_forbidden")

        target_edges = [edge for edge in outgoing.get(node_id, []) if str(edge.get("edge_type")) == "CONSTRAINS"]
        lawful_via_target = False
        for edge in target_edges:
            target = nodes.get(str(edge["to"]))
            if not target or str(target.get("node_type")) != "normative_target":
                continue
            target_sources = outgoing.get(str(target["id"]), [])
            if any(
                str(nodes.get(str(src["to"]), {}).get("node_type")) in {"source_fact", "derived_metric", "confirmed_assumption"}
                for src in target_sources
                if str(src.get("edge_type")) == "DERIVED_FROM"
            ):
                lawful_via_target = True
                break

        if not lawful_via_target:
            reasons.append("constraint_missing_lawful_source_chain")

        if reasons:
            rejected.append({"node": node, "reasons": reasons})
        else:
            lawful.append(node)

    return ConstraintCompilationResult(lawful_constraints=lawful, rejected_constraints=rejected)
