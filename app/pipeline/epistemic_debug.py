from __future__ import annotations

import json
from pathlib import Path


def render_graph_summary(graph_path: Path) -> str:
    if not graph_path.is_file():
        return "Epistemic graph is empty."
    try:
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("CORRUPTED_EPISTEMIC_GRAPH") from exc

    nodes = list(graph.get("nodes") or [])
    edges = list(graph.get("edges") or [])
    counts = {}
    for node in nodes:
        node_type = str(node.get("node_type") or "unknown")
        counts[node_type] = counts.get(node_type, 0) + 1

    parts = [
        f"workspace_id: {graph.get('workspace_id', 'unknown')}",
        f"nodes: {len(nodes)}",
        f"edges: {len(edges)}",
    ]
    if counts:
        parts.append(
            "node_types: "
            + ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
        )
    return "\n".join(parts)
