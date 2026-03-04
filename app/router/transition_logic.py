from __future__ import annotations

from typing import Dict, Set


CORE_PHASES = {
    "INTAKE",
    "PARSING",
    "EXTRACTION",
    "TYPIZATION",
    "CHARACTERIZATION",
    "MODELING",
    "EPISTEMIC_ANALYSIS",
    "PROBLEM_FACTORY",
    "SOLUTION_FACTORY",
    "DIALOGUE_REQUEST",
    "INCREMENTAL_UPDATE",
    "REPORTING",
}

SPECIAL_PHASES = {
    "CONTRADICTION_RESOLUTION",
    "VERSION_CHECKPOINT",
    "QUALITY_ASSESSMENT",
    "DIALOGUE_READY",
    "DONE",
}

ALL_PHASES = CORE_PHASES | SPECIAL_PHASES

TRANSITIONS: Dict[str, Set[str]] = {
    "INTAKE": {"PARSING"},
    "PARSING": {"EXTRACTION"},
    "EXTRACTION": {"TYPIZATION", "INCREMENTAL_UPDATE"},
    "TYPIZATION": {"CHARACTERIZATION"},
    "CHARACTERIZATION": {"MODELING"},
    "MODELING": {"EPISTEMIC_ANALYSIS"},
    "EPISTEMIC_ANALYSIS": {"PROBLEM_FACTORY", "SOLUTION_FACTORY"},
    "PROBLEM_FACTORY": {"SOLUTION_FACTORY", "DIALOGUE_REQUEST"},
    "DIALOGUE_REQUEST": {"INCREMENTAL_UPDATE"},
    "INCREMENTAL_UPDATE": {"EPISTEMIC_ANALYSIS", "CONTRADICTION_RESOLUTION"},
    "CONTRADICTION_RESOLUTION": {"EPISTEMIC_ANALYSIS"},
    "SOLUTION_FACTORY": {"REPORTING"},
    "REPORTING": {"DONE", "DIALOGUE_READY", "QUALITY_ASSESSMENT"},
    "DIALOGUE_READY": {"INCREMENTAL_UPDATE"},
    "QUALITY_ASSESSMENT": {"DONE", "DIALOGUE_READY"},
    "DONE": set(),
}


def is_valid_phase(phase: str) -> bool:
    return phase in ALL_PHASES


def can_transition(current_phase: str, next_phase: str) -> bool:
    return next_phase in TRANSITIONS.get(current_phase, set())


def suggest_next_phase(current_phase: str, signals: Dict[str, bool]) -> str:
    """Deterministic suggestion based on minimal signal set."""
    if current_phase == "EPISTEMIC_ANALYSIS":
        if signals.get("problem_defined", False):
            return "SOLUTION_FACTORY"
        return "PROBLEM_FACTORY"

    if current_phase == "PROBLEM_FACTORY":
        if signals.get("critical_unknowns", False):
            return "DIALOGUE_REQUEST"
        return "SOLUTION_FACTORY"

    if current_phase == "INCREMENTAL_UPDATE":
        if signals.get("conflicts_detected", False):
            return "CONTRADICTION_RESOLUTION"
        return "EPISTEMIC_ANALYSIS"

    default = sorted(TRANSITIONS.get(current_phase, set()))
    if not default:
        return current_phase
    return default[0]
