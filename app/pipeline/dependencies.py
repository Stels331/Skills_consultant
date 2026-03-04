from __future__ import annotations

from typing import Dict, List


STAGE_ORDER = [
    "intake",
    "layers",
    "viewpoints",
    "characterization",
    "problem_factory",
    "solution_factory",
    "reporting",
]


STAGE_DEPENDENCY_GRAPH: Dict[str, List[str]] = {
    "intake": ["layers", "viewpoints", "characterization", "problem_factory", "solution_factory", "reporting"],
    "layers": ["viewpoints", "characterization", "problem_factory", "solution_factory", "reporting"],
    "viewpoints": ["characterization", "problem_factory", "solution_factory", "reporting"],
    "characterization": ["problem_factory", "solution_factory", "reporting"],
    "problem_factory": ["solution_factory", "reporting"],
    "solution_factory": ["reporting"],
    "reporting": [],
}


def affected_stages(changed_stage: str) -> List[str]:
    stage = changed_stage.lower()
    if stage not in STAGE_ORDER:
        return []
    return [stage] + STAGE_DEPENDENCY_GRAPH.get(stage, [])
