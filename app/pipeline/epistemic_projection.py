from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from app.pipeline.constraint_compiler import compile_lawful_constraints
from app.pipeline.epistemic_graph import load_graph
from app.pipeline.epistemic_ledger import append_event, build_event


PROJECTION_TYPES = {
    "viewpoint_projection",
    "characterization_projection",
    "problem_factory_projection",
    "solution_factory_projection",
    "selection_projection",
    "reporting_projection",
}


def _append_contract_audit(workspace_path: Path, payload: Dict[str, object]) -> None:
    path = workspace_path / "governance" / "contract_audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def validate_projection(projection: Dict[str, object]) -> None:
    required = [
        "projection_id",
        "projection_type",
        "source_graph_version",
        "included_node_ids",
        "included_edge_ids",
        "projection_payload",
    ]
    missing = [key for key in required if key not in projection]
    if missing:
        raise ValueError(f"INVALID_PROJECTION_MISSING_FIELDS: {missing}")
    if str(projection["projection_type"]) not in PROJECTION_TYPES:
        raise ValueError(f"INVALID_PROJECTION_TYPE: {projection['projection_type']}")
    if not str(projection["source_graph_version"]).strip():
        raise ValueError("INVALID_PROJECTION_SOURCE_GRAPH_VERSION")


def _node_rel(node: Dict[str, object], prefix: str) -> bool:
    return str(node.get("artifact_rel") or "").startswith(prefix)


def _exclude_unresolved(nodes: List[Dict[str, object]]) -> List[Dict[str, object]]:
    out = []
    for node in nodes:
        status = str(node.get("epistemic_status") or "").lower()
        if status in {"hypothesis", "disputed", "unresolved"}:
            continue
        out.append(node)
    return out


def _artifact_body(workspace_path: Path, rel: str) -> str:
    path = workspace_path / rel
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _build_projection_payload(
    workspace_path: Path,
    projection_type: str,
    graph: Dict[str, object],
) -> Dict[str, object]:
    nodes = list(graph.get("nodes") or [])
    edges = list(graph.get("edges") or [])

    if projection_type == "problem_factory_projection":
        selected_nodes = [
            node
            for node in nodes
            if _node_rel(node, "characterization/")
            and str(node.get("node_type")) in {"source_fact", "derived_metric", "normative_target", "interpretation", "decision_constraint"}
        ]
        selected_ids = {str(node["id"]) for node in selected_nodes}
        selected_edges = [edge for edge in edges if str(edge.get("from")) in selected_ids and str(edge.get("to")) in selected_ids]
        return {
            "characterization_passport": _artifact_body(workspace_path, "characterization/CharacterizationPassport.md"),
            "indicator_set": _artifact_body(workspace_path, "characterization/IndicatorSet.md"),
            "conflicts_index": _artifact_body(workspace_path, "viewpoints/conflicts_index.md"),
            "claims": selected_nodes,
            "edges": selected_edges,
        }

    if projection_type == "solution_factory_projection":
        compiled = compile_lawful_constraints(workspace_path)
        lawful_ids = {str(node["id"]) for node in compiled.lawful_constraints}
        selected_nodes = [
            node
            for node in nodes
            if (
                _node_rel(node, "problems/")
                and str(node.get("node_type")) in {"problem", "decision_constraint", "source_fact", "interpretation", "derived_metric"}
            )
        ]
        selected_ids = {str(node["id"]) for node in selected_nodes}
        selected_edges = [edge for edge in edges if str(edge.get("from")) in selected_ids and str(edge.get("to")) in selected_ids]
        return {
            "selected_problem_card": _artifact_body(workspace_path, "problems/SelectedProblemCard.md"),
            "comparison_acceptance_spec": _artifact_body(workspace_path, "problems/ComparisonAcceptanceSpec.md"),
            "lawful_constraints": [node for node in selected_nodes if str(node.get("id")) in lawful_ids],
            "rejected_constraints": compiled.rejected_constraints,
            "relevant_claims": selected_nodes,
            "edges": selected_edges,
        }

    if projection_type == "selection_projection":
        compiled = compile_lawful_constraints(workspace_path)
        lawful_ids = {str(node["id"]) for node in compiled.lawful_constraints}
        selected_nodes = _exclude_unresolved(
            [
                node
                for node in nodes
                if _node_rel(node, "problems/")
                and str(node.get("node_type")) in {"problem", "decision_constraint", "source_fact", "interpretation", "derived_metric"}
            ]
        )
        selected_ids = {str(node["id"]) for node in selected_nodes}
        selected_edges = [edge for edge in edges if str(edge.get("from")) in selected_ids and str(edge.get("to")) in selected_ids]
        return {
            "solution_portfolio": _artifact_body(workspace_path, "solutions/SolutionPortfolio.md"),
            "parity_report": _artifact_body(workspace_path, "solutions/ParityReport.md"),
            "conflict_records": _artifact_body(workspace_path, "solutions/ConflictRecords.md"),
            "acceptance_spec": _artifact_body(workspace_path, "problems/ComparisonAcceptanceSpec.md"),
            "lawful_constraints": [node for node in selected_nodes if str(node.get("id")) in lawful_ids],
            "rejected_constraints": compiled.rejected_constraints,
            "relevant_claims": selected_nodes,
            "edges": selected_edges,
        }

    if projection_type == "reporting_projection":
        selected_nodes = _exclude_unresolved(nodes)
        selected_ids = {str(node["id"]) for node in selected_nodes}
        selected_edges = [edge for edge in edges if str(edge.get("from")) in selected_ids and str(edge.get("to")) in selected_ids]
        return {
            "human_facing_claims": selected_nodes,
            "edges": selected_edges,
            "artifact_context": {
                "problems/SelectedProblemCard.md": _artifact_body(workspace_path, "problems/SelectedProblemCard.md"),
                "problems/ComparisonAcceptanceSpec.md": _artifact_body(workspace_path, "problems/ComparisonAcceptanceSpec.md"),
                "solutions/SelectedSolutions.md": _artifact_body(workspace_path, "solutions/SelectedSolutions.md"),
                "decisions/ADR-001.md": _artifact_body(workspace_path, "decisions/ADR-001.md"),
                "operation/Runbook.md": _artifact_body(workspace_path, "operation/Runbook.md"),
                "operation/RollbackPlan.md": _artifact_body(workspace_path, "operation/RollbackPlan.md"),
            },
        }

    if projection_type == "characterization_projection":
        selected_nodes = [node for node in nodes if _node_rel(node, "viewpoints/")]
        selected_ids = {str(node["id"]) for node in selected_nodes}
        selected_edges = [edge for edge in edges if str(edge.get("from")) in selected_ids and str(edge.get("to")) in selected_ids]
        return {
            "viewpoint_claims": selected_nodes,
            "edges": selected_edges,
            "layers": {
                "layer_1": _artifact_body(workspace_path, "layers/layer_1_business_model.md"),
                "layer_2": _artifact_body(workspace_path, "layers/layer_2_requirements.md"),
                "layer_3": _artifact_body(workspace_path, "layers/layer_3_functional_model.md"),
                "layer_4": _artifact_body(workspace_path, "layers/layer_4_allocation_model.md"),
            },
        }

    if projection_type == "viewpoint_projection":
        return {
            "normalized_case": _artifact_body(workspace_path, "intake/normalized_case.md"),
            "layers": {
                "layer_1": _artifact_body(workspace_path, "layers/layer_1_business_model.md"),
                "layer_2": _artifact_body(workspace_path, "layers/layer_2_requirements.md"),
                "layer_3": _artifact_body(workspace_path, "layers/layer_3_functional_model.md"),
                "layer_4": _artifact_body(workspace_path, "layers/layer_4_allocation_model.md"),
            },
        }

    raise ValueError(f"UNSUPPORTED_PROJECTION_TYPE: {projection_type}")


def build_projection(workspace_path: Path, projection_type: str) -> Dict[str, object]:
    graph = load_graph(workspace_path / "analysis" / "epistemic_graph.json", workspace_path.name)
    payload = _build_projection_payload(workspace_path, projection_type, graph)

    node_ids = [str(node["id"]) for node in payload.get("claims", payload.get("relevant_claims", payload.get("human_facing_claims", payload.get("viewpoint_claims", []))))]
    edge_ids = [
        f"{edge['edge_type']}::{edge['from']}::{edge['to']}"
        for edge in payload.get("edges", [])
    ]
    projection = {
        "projection_id": f"{workspace_path.name}__{projection_type}",
        "projection_type": projection_type,
        "source_graph_version": str(graph.get("updated_at") or ""),
        "included_node_ids": node_ids,
        "included_edge_ids": edge_ids,
        "projection_payload": payload,
    }
    validate_projection(projection)
    return projection


def emit_projection(workspace_path: Path, projection_type: str) -> Dict[str, object]:
    projection = build_projection(workspace_path, projection_type)
    path = workspace_path / "analysis" / "projections" / f"{projection_type}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(projection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    append_event(
        workspace_path / "governance" / "epistemic_ledger.jsonl",
        build_event(
            event_type="projection_emitted",
            workspace_id=workspace_path.name,
            stage=projection_type.replace("_projection", ""),
            target_id=str(projection["projection_id"]),
            payload={
                "projection_type": projection_type,
                "source_graph_version": projection["source_graph_version"],
                "included_node_ids": projection["included_node_ids"],
                "included_edge_ids": projection["included_edge_ids"],
            },
        ),
    )
    _append_contract_audit(
        workspace_path,
        {
            "event": "projection_emitted",
            "projection_id": projection["projection_id"],
            "projection_type": projection_type,
            "source_graph_version": projection["source_graph_version"],
            "included_node_ids": projection["included_node_ids"],
            "included_edge_ids": projection["included_edge_ids"],
        },
    )
    return projection
