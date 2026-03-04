from __future__ import annotations

from pathlib import Path
from typing import Dict

from app.pipeline.conflict_router import run_conflict_router
from app.pipeline.parity_tradeoff import run_parity_tradeoff
from app.pipeline.selection_engine import run_selection_engine
from app.pipeline.solution_portfolio import run_solution_portfolio


def run_solution_factory(project_root: Path, workspace_id: str, llm_mode: str = "local") -> Dict[str, object]:
    s1 = run_solution_portfolio(project_root, workspace_id, llm_mode=llm_mode)
    s2 = run_parity_tradeoff(project_root, workspace_id, llm_mode=llm_mode)
    s3 = run_conflict_router(project_root, workspace_id, llm_mode=llm_mode)
    s4 = run_selection_engine(project_root, workspace_id, llm_mode=llm_mode)
    return {
        "workspace_id": workspace_id,
        "solution_portfolio": s1["solution_portfolio"],
        "parity_report": s2["parity_report"],
        "conflict_records": s3["conflict_records"],
        "selected_solutions": s4["selected_solutions"],
        "adr": s4["adr"],
        "runbook": s4["runbook"],
        "rollback": s4["rollback"],
        "llm_mode": llm_mode,
    }
