from __future__ import annotations

from pathlib import Path
from typing import Dict

from app.pipeline.epistemic_graph import (
    extract_claims_from_artifact,
    load_graph,
    merge_graph_entities,
    save_graph,
)
from app.pipeline.epistemic_ledger import append_event, build_event

EPI_RANK = {
    "hypothesis": 0,
    "stated_by_user": 1,
    "inferred": 2,
    "observed": 3,
    "tested": 4,
    "decision_grade": 5,
    "operationally_confirmed": 6,
}


def sync_artifact_to_epistemic_store(
    *,
    workspace_path: Path,
    artifact_rel: str,
    frontmatter: Dict[str, object],
    body: str,
) -> None:
    graph_path = workspace_path / "analysis" / "epistemic_graph.json"
    ledger_path = workspace_path / "governance" / "epistemic_ledger.jsonl"
    workspace_id = workspace_path.name
    artifact_type = str(frontmatter.get("artifact_type") or "")
    stage = str(frontmatter.get("stage") or "")

    nodes, edges = extract_claims_from_artifact(
        artifact_rel=artifact_rel,
        artifact_type=artifact_type,
        stage=stage,
        frontmatter=frontmatter,
        body=body,
    )
    if not nodes and not edges:
        return

    graph = load_graph(graph_path, workspace_id)
    merged, previous_nodes, current_nodes, node_diffs = merge_graph_entities(graph, nodes, edges)
    save_graph(graph_path, merged)
    diffs_by_node_id = {str(item["node_id"]): item for item in node_diffs}

    for node in nodes:
        node_id = str(node["id"])
        previous = previous_nodes.get(node_id)
        current_status = str(current_nodes[node_id]["epistemic_status"])
        if previous is None:
            append_event(
                ledger_path,
                build_event(
                    event_type="claim_created",
                    workspace_id=workspace_id,
                    stage=stage,
                    target_id=node_id,
                    payload={
                        "node_type": node["node_type"],
                        "epistemic_status": current_status,
                        "artifact_rel": artifact_rel,
                    },
                ),
            )
        else:
            diff = diffs_by_node_id.get(node_id)
            if diff and diff.get("change_type") == "updated":
                append_event(
                    ledger_path,
                    build_event(
                        event_type="claim_updated",
                        workspace_id=workspace_id,
                        stage=stage,
                        target_id=node_id,
                        payload={
                            "artifact_rel": artifact_rel,
                            "changed_fields": diff["changed_fields"],
                        },
                    ),
                )
            previous_status = str(previous.get("epistemic_status") or "inferred")
            if EPI_RANK.get(current_status, 0) > EPI_RANK.get(previous_status, 0):
                append_event(
                    ledger_path,
                    build_event(
                        event_type="claim_promoted",
                        workspace_id=workspace_id,
                        stage=stage,
                        target_id=node_id,
                        payload={
                            "from_status": previous_status,
                            "to_status": current_status,
                            "artifact_rel": artifact_rel,
                        },
                    ),
                )
            elif EPI_RANK.get(current_status, 0) < EPI_RANK.get(previous_status, 0):
                append_event(
                    ledger_path,
                    build_event(
                        event_type="claim_degraded",
                        workspace_id=workspace_id,
                        stage=stage,
                        target_id=node_id,
                        payload={
                            "from_status": previous_status,
                            "to_status": current_status,
                            "artifact_rel": artifact_rel,
                        },
                    ),
                )

        if str(node["node_type"]) == "decision_constraint":
            append_event(
                ledger_path,
                build_event(
                    event_type="constraint_compiled",
                    workspace_id=workspace_id,
                    stage=stage,
                    target_id=node_id,
                    payload={
                        "artifact_rel": artifact_rel,
                        "statement": node["statement"],
                    },
                ),
            )
