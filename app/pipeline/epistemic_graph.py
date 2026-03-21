from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple


NODE_TYPES = {
    "source_fact",
    "derived_metric",
    "normative_target",
    "interpretation",
    "hypothesis",
    "problem",
    "decision_constraint",
    "disputed_claim",
    "conflict_case",
}

EDGE_TYPES = {
    "DERIVED_FROM",
    "CONSTRAINS",
    "SUPPORTS",
    "RELATES_TO",
    "CONTRADICTS",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_graph(workspace_id: str) -> Dict[str, object]:
    return {
        "workspace_id": workspace_id,
        "version": 1,
        "updated_at": _utc_now_iso(),
        "nodes": [],
        "edges": [],
    }


def load_graph(path: Path, workspace_id: str) -> Dict[str, object]:
    if not path.is_file():
        return default_graph(workspace_id)
    raw = json.loads(path.read_text(encoding="utf-8"))
    graph = {
        "workspace_id": str(raw.get("workspace_id") or workspace_id),
        "version": int(raw.get("version") or 1),
        "updated_at": str(raw.get("updated_at") or _utc_now_iso()),
        "nodes": list(raw.get("nodes") or []),
        "edges": list(raw.get("edges") or []),
    }
    validate_graph(graph)
    return graph


def save_graph(path: Path, graph: Dict[str, object]) -> None:
    graph = dict(graph)
    graph["updated_at"] = _utc_now_iso()
    validate_graph(graph)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_node(node: Dict[str, object]) -> None:
    required = [
        "id",
        "node_type",
        "statement",
        "source_refs",
        "epistemic_status",
        "stage",
        "owner",
        "created_at",
        "updated_at",
    ]
    missing = [key for key in required if key not in node]
    if missing:
        raise ValueError(f"INVALID_EPISTEMIC_NODE_MISSING_FIELDS: {missing}")
    if str(node["node_type"]) not in NODE_TYPES:
        raise ValueError(f"INVALID_EPISTEMIC_NODE_TYPE: {node['node_type']}")
    if not isinstance(node["source_refs"], list):
        raise ValueError("INVALID_EPISTEMIC_NODE_SOURCE_REFS")


def validate_edge(edge: Dict[str, object], node_ids: set[str]) -> None:
    required = ["edge_type", "from", "to", "provenance"]
    missing = [key for key in required if key not in edge]
    if missing:
        raise ValueError(f"INVALID_EPISTEMIC_EDGE_MISSING_FIELDS: {missing}")
    if str(edge["edge_type"]) not in EDGE_TYPES:
        raise ValueError(f"INVALID_EPISTEMIC_EDGE_TYPE: {edge['edge_type']}")
    if str(edge["from"]) not in node_ids or str(edge["to"]) not in node_ids:
        raise ValueError("INVALID_EPISTEMIC_EDGE_DANGLING_REFERENCE")


def validate_graph(graph: Dict[str, object]) -> None:
    node_ids: set[str] = set()
    for node in graph.get("nodes", []):
        validate_node(node)
        node_id = str(node["id"])
        if node_id in node_ids:
            raise ValueError(f"DUPLICATE_EPISTEMIC_NODE_ID: {node_id}")
        node_ids.add(node_id)
    for edge in graph.get("edges", []):
        validate_edge(edge, node_ids)


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9а-яА-Я_]+", "_", text.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "claim"


def make_node_id(artifact_rel: str, node_type: str, statement: str, index: int) -> str:
    return f"{artifact_rel}::{node_type}::{index:03d}::{_slug(statement)[:40]}"


def build_node(
    *,
    artifact_rel: str,
    node_type: str,
    statement: str,
    source_refs: List[str],
    epistemic_status: str,
    stage: str,
    owner: str,
    index: int,
) -> Dict[str, object]:
    now = _utc_now_iso()
    return {
        "id": make_node_id(artifact_rel, node_type, statement, index),
        "artifact_rel": artifact_rel,
        "node_type": node_type,
        "statement": statement,
        "source_refs": source_refs,
        "epistemic_status": epistemic_status,
        "stage": stage,
        "owner": owner,
        "created_at": now,
        "updated_at": now,
    }


def build_edge(edge_type: str, from_id: str, to_id: str, provenance: str) -> Dict[str, object]:
    return {
        "edge_type": edge_type,
        "from": from_id,
        "to": to_id,
        "provenance": provenance,
    }


def _extract_bullets(section_text: str) -> List[str]:
    values: List[str] = []
    for raw in section_text.splitlines():
        s = raw.strip()
        if s.startswith("- "):
            values.append(s[2:].strip())
    return [v for v in values if v]


def _extract_md_section(body: str, title: str) -> str:
    pattern = re.compile(rf"(?ms)^##\s+{re.escape(title)}\n(.*?)(?=^##\s+|\Z)")
    match = pattern.search(body)
    return match.group(1).strip() if match else ""


def extract_claims_from_artifact(
    artifact_rel: str,
    artifact_type: str,
    stage: str,
    frontmatter: Dict[str, object],
    body: str,
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    source_refs = [str(x) for x in frontmatter.get("source_refs", [])]
    owner = str(frontmatter.get("owner_role") or "analyst")
    epi = str(frontmatter.get("epistemic_status") or "inferred")
    nodes: List[Dict[str, object]] = []
    edges: List[Dict[str, object]] = []

    def add_nodes(node_type: str, statements: List[str], epistemic_status: str) -> List[str]:
        ids: List[str] = []
        for statement in statements:
            node = build_node(
                artifact_rel=artifact_rel,
                node_type=node_type,
                statement=statement,
                source_refs=source_refs,
                epistemic_status=epistemic_status,
                stage=stage,
                owner=owner,
                index=len(nodes) + 1,
            )
            nodes.append(node)
            ids.append(str(node["id"]))
        return ids

    if artifact_type == "characterization_passport":
        fact_ids = add_nodes("source_fact", _extract_bullets(_extract_md_section(body, "source_summary")), "observed")
        target_ids = add_nodes("normative_target", _extract_bullets(_extract_md_section(body, "optimization_goals")), epi)
        constraint_ids = add_nodes("decision_constraint", _extract_bullets(_extract_md_section(body, "hard_constraints")), epi)
        interpretation_ids = add_nodes("interpretation", _extract_bullets(_extract_md_section(body, "risk_signals")), "inferred")
        for target_id in target_ids:
            for fact_id in fact_ids:
                edges.append(build_edge("DERIVED_FROM", target_id, fact_id, artifact_rel))
        for constraint_id in constraint_ids:
            for target_id in target_ids:
                edges.append(build_edge("CONSTRAINS", constraint_id, target_id, artifact_rel))
        for interpretation_id in interpretation_ids:
            for fact_id in fact_ids:
                edges.append(build_edge("DERIVED_FROM", interpretation_id, fact_id, artifact_rel))

    elif artifact_type == "indicator_set":
        metric_lines = []
        for raw in body.splitlines():
            s = raw.strip()
            if s.startswith("- "):
                metric_lines.append(s[2:].split("|")[0].strip())
        add_nodes("derived_metric", metric_lines, "inferred")

    elif artifact_type == "problem_archive":
        problem_titles = re.findall(r"(?m)^##\s+[^-]+-\s+(.+)$", body)
        add_nodes("problem", [title.strip() for title in problem_titles], "inferred")

    elif artifact_type == "problem_portfolio":
        selected = _extract_bullets(_extract_md_section(body, "Facts"))
        problem_ids = add_nodes("problem", selected, "inferred")
        interpretation_ids = add_nodes("interpretation", _extract_bullets(_extract_md_section(body, "Interpretations")), "inferred")
        hypothesis_ids = add_nodes("hypothesis", _extract_bullets(_extract_md_section(body, "Hypotheses to Validate")), "hypothesis")
        for interpretation_id in interpretation_ids:
            for problem_id in problem_ids:
                edges.append(build_edge("SUPPORTS", interpretation_id, problem_id, artifact_rel))
        for hypothesis_id in hypothesis_ids:
            for problem_id in problem_ids:
                edges.append(build_edge("RELATES_TO", hypothesis_id, problem_id, artifact_rel))

    elif artifact_type == "selected_problem_card":
        title_match = re.search(r"(?m)^- title:\s+(.+)$", body)
        problem_titles = [title_match.group(1).strip()] if title_match else []
        problem_ids = add_nodes("problem", problem_titles, "inferred")
        fact_ids = add_nodes("source_fact", _extract_bullets(_extract_md_section(body, "Facts")), "observed")
        interpretation_ids = add_nodes("interpretation", _extract_bullets(_extract_md_section(body, "Interpretations")), "inferred")
        hypothesis_ids = add_nodes("hypothesis", _extract_bullets(_extract_md_section(body, "Hypotheses to Validate")), "hypothesis")
        for problem_id in problem_ids:
            for fact_id in fact_ids:
                edges.append(build_edge("DERIVED_FROM", problem_id, fact_id, artifact_rel))
            for interpretation_id in interpretation_ids:
                edges.append(build_edge("SUPPORTS", interpretation_id, problem_id, artifact_rel))
            for hypothesis_id in hypothesis_ids:
                edges.append(build_edge("RELATES_TO", hypothesis_id, problem_id, artifact_rel))

    elif artifact_type == "comparison_acceptance_spec":
        metric_ids = add_nodes("derived_metric", _extract_bullets(_extract_md_section(body, "indicators")), "inferred")
        constraint_ids = add_nodes("decision_constraint", _extract_bullets(_extract_md_section(body, "hard_constraints")), epi)
        assumption_ids = add_nodes("hypothesis", _extract_bullets(_extract_md_section(body, "assumptions_to_confirm")), "hypothesis")
        for constraint_id in constraint_ids:
            for metric_id in metric_ids:
                edges.append(build_edge("CONSTRAINS", constraint_id, metric_id, artifact_rel))
        for assumption_id in assumption_ids:
            for constraint_id in constraint_ids:
                edges.append(build_edge("RELATES_TO", assumption_id, constraint_id, artifact_rel))

    return nodes, edges


def merge_graph_entities(
    graph: Dict[str, object],
    nodes: List[Dict[str, object]],
    edges: List[Dict[str, object]],
) -> Tuple[Dict[str, object], Dict[str, Dict[str, object]], Dict[str, Dict[str, object]]]:
    existing_nodes = {str(node["id"]): dict(node) for node in graph.get("nodes", [])}
    existing_edges = {
        (str(edge["edge_type"]), str(edge["from"]), str(edge["to"])): dict(edge)
        for edge in graph.get("edges", [])
    }
    previous_nodes = dict(existing_nodes)

    for node in nodes:
        existing_nodes[str(node["id"])] = node
    for edge in edges:
        existing_edges[(str(edge["edge_type"]), str(edge["from"]), str(edge["to"]))] = edge

    merged = {
        "workspace_id": graph["workspace_id"],
        "version": graph.get("version", 1),
        "updated_at": _utc_now_iso(),
        "nodes": list(existing_nodes.values()),
        "edges": list(existing_edges.values()),
    }
    validate_graph(merged)
    return merged, previous_nodes, existing_nodes
