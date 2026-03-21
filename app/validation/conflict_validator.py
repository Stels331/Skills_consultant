from __future__ import annotations

import json
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_cluster_id(prefix: str, key: str) -> str:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}::{digest}"


COMPATIBLE_TYPE_PAIRS = {
    frozenset({"normative_target", "derived_metric"}),
    frozenset({"interpretation", "derived_metric"}),
    frozenset({"interpretation", "source_fact"}),
    frozenset({"hypothesis", "interpretation"}),
    frozenset({"assumption", "interpretation"}),
}


def _extract_numeric_claim(node: Dict[str, object]) -> Optional[Tuple[str, float]]:
    claim_key = str(node.get("claim_key") or "").strip().lower()
    text = str(node.get("statement") or "").lower()
    match = re.search(r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>%|квт/ч|квт|м³/мес|м3/мес|м³|м3|шт/мес|шт|months?|месяц(?:а|ев)?|дн(?:ей|я)?|недель?)", text)
    if not match:
        return None
    metric = claim_key or _normalize_statement_key(node)
    return metric, float(match.group("value").replace(",", "."))


def _has_incompatible_numeric_claims(node_a: Dict[str, object], node_b: Dict[str, object]) -> bool:
    numeric_a = _extract_numeric_claim(node_a)
    numeric_b = _extract_numeric_claim(node_b)
    if not numeric_a or not numeric_b:
        return False
    if numeric_a[0] != numeric_b[0]:
        return False
    return abs(numeric_a[1] - numeric_b[1]) > 1e-9


def _has_opposite_polarity(node_a: Dict[str, object], node_b: Dict[str, object]) -> bool:
    return _polarity(node_a) != _polarity(node_b)


def _has_explicit_negation(node_a: Dict[str, object], node_b: Dict[str, object]) -> bool:
    text_a = str(node_a.get("statement") or "").lower()
    text_b = str(node_b.get("statement") or "").lower()
    neg_markers = (" not ", " no ", "нет ", "cannot", "forbid", "запрещ", "нельзя")
    has_neg_a = any(marker in text_a for marker in neg_markers)
    has_neg_b = any(marker in text_b for marker in neg_markers)
    if has_neg_a == has_neg_b:
        return False
    return _normalize_statement_key(node_a) == _normalize_statement_key(node_b) or _is_paraphrase(node_a, node_b)


def _is_paraphrase(node_a: Dict[str, object], node_b: Dict[str, object]) -> bool:
    key_a = _normalize_statement_key(node_a)
    key_b = _normalize_statement_key(node_b)
    if key_a and key_a == key_b:
        return True
    tokens_a = set(re.findall(r"[a-zа-я0-9#]+", str(node_a.get("statement") or "").lower(), flags=re.IGNORECASE))
    tokens_b = set(re.findall(r"[a-zа-я0-9#]+", str(node_b.get("statement") or "").lower(), flags=re.IGNORECASE))
    if not tokens_a or not tokens_b:
        return False
    overlap = len(tokens_a & tokens_b) / max(1, len(tokens_a | tokens_b))
    return overlap >= 0.6


def _is_genuine_conflict(
    node_a: Dict[str, object],
    node_b: Dict[str, object],
    *,
    different_values: bool,
) -> bool:
    type_pair = frozenset({str(node_a.get("node_type") or ""), str(node_b.get("node_type") or "")})
    if type_pair in COMPATIBLE_TYPE_PAIRS:
        return (
            _has_opposite_polarity(node_a, node_b)
            or _has_incompatible_numeric_claims(node_a, node_b)
            or _has_explicit_negation(node_a, node_b)
        )
    return (
        _has_opposite_polarity(node_a, node_b)
        or _has_incompatible_numeric_claims(node_a, node_b)
        or _has_explicit_negation(node_a, node_b)
        or (different_values and not _is_paraphrase(node_a, node_b))
    )


def materialize_conflicts(workspace_path: Path) -> Dict[str, object]:
    graph_path = workspace_path / "analysis" / "epistemic_graph.json"
    graph = load_graph(graph_path, workspace_path.name)
    nodes = list(graph.get("nodes") or [])
    edges = list(graph.get("edges") or [])
    node_map = {str(node["id"]): node for node in nodes}
    existing_conflict_ids = {str(node["id"]) for node in nodes if str(node.get("node_type")) == "conflict_case"}
    existing_duplicate_ids = {
        str(node["id"]) for node in nodes if str(node.get("node_type")) == "duplicate_claim_cluster"
    }
    existing_conflict_nodes = [node for node in nodes if str(node.get("node_type")) == "conflict_case"]
    edge_keys = {(str(edge["edge_type"]), str(edge["from"]), str(edge["to"])) for edge in edges}

    by_key: Dict[str, List[Dict[str, object]]] = {}
    for node in nodes:
        if str(node.get("node_type")) not in {"source_fact", "derived_metric", "normative_target", "decision_constraint", "interpretation"}:
            continue
        by_key.setdefault(_normalize_statement_key(node), []).append(node)

    new_nodes: List[Dict[str, object]] = []
    new_edges: List[Dict[str, object]] = []
    conflicts: List[Dict[str, object]] = []
    duplicates: List[Dict[str, object]] = []
    active_conflict_keys = set()

    for key, candidates in by_key.items():
        if len(candidates) < 2:
            continue
        polarities = {_polarity(node) for node in candidates}
        different_values = len({str(node.get("statement") or "").strip().lower() for node in candidates}) > 1
        if len(polarities) < 2 and not different_values:
            continue

        has_genuine_conflict = False
        for index, node_a in enumerate(candidates):
            for node_b in candidates[index + 1 :]:
                if _is_genuine_conflict(node_a, node_b, different_values=different_values):
                    has_genuine_conflict = True
                    break
            if has_genuine_conflict:
                break

        if not has_genuine_conflict:
            duplicate_id = _stable_cluster_id("duplicate", key)
            if duplicate_id not in existing_duplicate_ids and duplicate_id not in {str(n['id']) for n in new_nodes}:
                new_nodes.append(
                    {
                        "id": duplicate_id,
                        "node_type": "duplicate_claim_cluster",
                        "statement": f"Duplicate claim cluster on key: {key}",
                        "source_refs": sorted({ref for node in candidates for ref in node.get("source_refs", [])}),
                        "epistemic_status": "informational",
                        "stage": "validation",
                        "owner": "validator",
                        "created_at": _utc_now_iso(),
                        "updated_at": _utc_now_iso(),
                        "resolution_status": "informational",
                        "claim_key": key,
                    }
                )
            duplicates.append({"duplicate_id": duplicate_id, "claim_key": key, "node_ids": [str(node["id"]) for node in candidates]})
            continue

        active_conflict_keys.add(key)
        conflict_id = _stable_cluster_id("conflict", key)
        if conflict_id not in existing_conflict_ids and conflict_id not in {str(n['id']) for n in new_nodes}:
            conflict_node = {
                "id": conflict_id,
                "node_type": "conflict_case",
                "statement": f"Conflict on claim key: {key}",
                "source_refs": sorted({ref for node in candidates for ref in node.get("source_refs", [])}),
                "epistemic_status": "disputed",
                "stage": "validation",
                "owner": "validator",
                "created_at": _utc_now_iso(),
                "updated_at": _utc_now_iso(),
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
                            "created_at": _utc_now_iso(),
                            "updated_at": _utc_now_iso(),
                            "claim_key": key,
                            "origin_id": str(node["id"]),
                        }
                    )
                    if ("DERIVED_FROM", disputed_id, str(node["id"])) not in edge_keys:
                        new_edges.append({"edge_type": "DERIVED_FROM", "from": disputed_id, "to": str(node["id"]), "provenance": "conflict_validator"})
            if ("CONTRADICTS", str(node["id"]), conflict_id) not in edge_keys:
                new_edges.append({"edge_type": "CONTRADICTS", "from": str(node["id"]), "to": conflict_id, "provenance": "conflict_validator"})
        conflicts.append({"conflict_id": conflict_id, "claim_key": key, "node_ids": [str(node["id"]) for node in candidates]})

    graph_changed = bool(new_nodes or new_edges)
    for node in existing_conflict_nodes:
        claim_key = str(node.get("claim_key") or "")
        if not claim_key or claim_key in active_conflict_keys:
            continue
        status = str(node.get("resolution_status") or "open").lower()
        if status in {"resolved", "waived"}:
            continue
        node["resolution_status"] = "waived"
        node["updated_at"] = _utc_now_iso()
        graph_changed = True

    if graph_changed:
        graph["nodes"] = nodes + new_nodes
        graph["edges"] = edges + new_edges
        save_graph(graph_path, graph)
        if conflicts:
            append_event(
                workspace_path / "governance" / "epistemic_ledger.jsonl",
                build_event(
                    event_type="conflict_marked",
                    workspace_id=workspace_path.name,
                    stage="validation",
                    target_id=conflicts[0]["conflict_id"] if conflicts else "conflict_batch",
                    payload={"conflicts": conflicts, "duplicates": duplicates},
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
