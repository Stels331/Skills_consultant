from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List


def _extract_lines(text: str) -> List[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]


def _contains_any(text: str, keywords: List[str]) -> bool:
    low = text.lower()
    return any(k in low for k in keywords)


_PORTFOLIO_ID_RE = re.compile(r"^##\s+(sol_[a-z0-9_]+)\s*$", re.MULTILINE)


def _portfolio_solution_ids(text: str) -> List[str]:
    return [match.group(1) for match in _PORTFOLIO_ID_RE.finditer(text)]


def _local_default_solution_candidates() -> List[Dict[str, str]]:
    return [
        {
            "id": "sol_00_status_quo",
            "type": "baseline",
            "assurance_level": "low",
            "intervention_force": "",
            "relevance_basis": "",
            "anti_goodhart_risk": "hidden structural waste remains unmeasured under status quo",
            "solves_which_problems": "partial",
            "assumptions": "no change",
            "expected_effects": "low",
            "risks": "continued degradation",
            "constraints": "none",
            "required_capabilities": "existing only",
            "reversibility": "n/a",
            "affected_viewpoints": "strategist, operator, analyst",
        },
        {
            "id": "sol_01_process_stabilization",
            "type": "process",
            "assurance_level": "medium",
            "intervention_force": "weak",
            "relevance_basis": "rollout_relevant",
            "anti_goodhart_risk": "local process speed may improve while unresolved gaps are simply moved downstream",
            "solves_which_problems": "moderate",
            "assumptions": "current team can adopt bounded process changes",
            "expected_effects": "early reduction of noise and safer intake discipline",
            "risks": "adoption friction and cosmetic compliance",
            "constraints": "pilot window must remain bounded",
            "required_capabilities": "process owner + analytics",
            "reversibility": "high",
            "affected_viewpoints": "operator, analyst",
        },
        {
            "id": "sol_02_capability_transfer",
            "type": "process",
            "assurance_level": "medium",
            "intervention_force": "medium",
            "relevance_basis": "pareto_relevant",
            "anti_goodhart_risk": "delegation can improve throughput while silently degrading decision quality",
            "solves_which_problems": "strong",
            "assumptions": "repeatable knowledge can be transferred into a reusable operating contour",
            "expected_effects": "medium-high",
            "risks": "handoff ambiguity and maintenance overhead",
            "constraints": "quality guardrails must stay explicit",
            "required_capabilities": "operations lead + domain analyst",
            "reversibility": "medium",
            "affected_viewpoints": "operator, analyst, architect",
        },
        {
            "id": "sol_03_architecture_reframe",
            "type": "architecture",
            "assurance_level": "medium",
            "intervention_force": "strong",
            "relevance_basis": "pareto_relevant",
            "anti_goodhart_risk": "delivery teams may optimize rollout velocity instead of stable outcome quality",
            "solves_which_problems": "high",
            "assumptions": "modular rollout is feasible without destabilizing the core system",
            "expected_effects": "high",
            "risks": "integration complexity",
            "constraints": "budget and blast radius must be confirmed from actual case input",
            "required_capabilities": "architect + delivery team",
            "reversibility": "medium-high",
            "affected_viewpoints": "architect, strategist",
        },
        {
            "id": "sol_04_policy_guardrails",
            "type": "policy",
            "assurance_level": "medium",
            "intervention_force": "strong",
            "relevance_basis": "rollout_relevant",
            "anti_goodhart_risk": "policy compliance can be gamed without improving actual operational behavior",
            "solves_which_problems": "medium",
            "assumptions": "governance support will remain consistent through the pilot",
            "expected_effects": "medium",
            "risks": "stakeholder pushback",
            "constraints": "coordination overhead",
            "required_capabilities": "leadership + PMO",
            "reversibility": "medium",
            "affected_viewpoints": "strategist, client, critic",
        },
    ]


def _local_build_layer(payload: Dict[str, Any]) -> str:
    layer = payload.get("layer_name", "layer")
    normalized_case = str(payload.get("normalized_case", ""))
    lines = _extract_lines(normalized_case)
    joined = " ".join(lines).lower()

    def pick(keys: List[str], fallback: str) -> List[str]:
        picked = [ln for ln in lines if any(k in ln.lower() for k in keys)]
        return picked[:8] if picked else [fallback]

    if layer == "layer_1_business_model":
        points = pick(["value", "client", "market", "strategy", "цінн", "рин", "клієн", "конкур"], "GAP: business context is weak")
        title = "# Layer 1: Business Model"
    elif layer == "layer_2_requirements":
        points = pick(["must", "should", "need", "require", "треб", "повин", "необхід"], "GAP: requirements not explicit")
        title = "# Layer 2: Requirements"
    elif layer == "layer_3_functional_model":
        points = pick(["process", "flow", "stage", "function", "процес", "етап", "вироб"], "GAP: functional flow unclear")
        title = "# Layer 3: Functional Model"
    else:
        points = pick(["role", "owner", "team", "manager", "правл", "команд", "роль"], "GAP: allocation ownership undefined")
        title = "# Layer 4: Allocation Model"

    return title + "\n\n" + "\n".join(f"- {x}" for x in points) + "\n\n_Generated by local-llm mode._"


def _local_build_viewpoint(payload: Dict[str, Any]) -> str:
    viewpoint = str(payload.get("viewpoint", "viewpoint"))
    focus = str(payload.get("focus", ""))
    layers = payload.get("layers", {})

    def first_line(key: str) -> str:
        txt = str(layers.get(key, ""))
        lines = _extract_lines(txt)
        return lines[0] if lines else "no data"

    l1 = first_line("layer_1")
    l2 = first_line("layer_2")
    l3 = first_line("layer_3")
    l4 = first_line("layer_4")

    gaps = []
    for k, v in layers.items():
        if "GAP:" in str(v):
            gaps.append(f"{k} has unresolved GAP")

    objections = [f"Potential risk from {viewpoint} perspective"]
    if gaps:
        objections.append("Unresolved GAPs reduce decision confidence")

    body = [
        f"# Viewpoint: {viewpoint}",
        "",
        "## viewpoint_name",
        viewpoint,
        "",
        "## primary_concerns",
        f"- {focus}",
        "- preserve traceability and evidence quality",
        "",
        "## layer_findings",
        f"- layer_1: {l1}",
        f"- layer_2: {l2}",
        f"- layer_3: {l3}",
        f"- layer_4: {l4}",
        "",
        "## key_risks",
        "- decision under incomplete data",
        "- cross-layer inconsistency",
        "",
        "## supported_actions",
        "- proceed with explicit assumptions register",
        "",
        "## objections",
        *[f"- {x}" for x in objections],
        "",
        "## evidence_gaps",
        *( [f"- {g}" for g in gaps] if gaps else ["- none"] ),
        "",
        "## non_negotiables",
        "- do not skip acceptance constraints",
        "- keep links to source evidence",
        "",
        "_Generated by local-llm mode._",
    ]
    return "\n".join(body)


def _local_build_characterization(payload: Dict[str, Any]) -> str:
    viewpoint_summary = str(payload.get("viewpoint_summary", ""))
    layer_summary = str(payload.get("layer_summary", ""))
    weak_hint = "investment_status" if "invest" in viewpoint_summary.lower() else "team_alignment"
    return (
        "# Characterization Passport\n\n"
        "## optimization_goals\n"
        "- reduce strategic uncertainty and improve decision confidence\n\n"
        "## hard_constraints\n"
        "- budget and time horizon must be explicit\n"
        "- decision must remain reversible for pilot window\n\n"
        "## risk_signals\n"
        "- unresolved assumptions in layers/viewpoints\n"
        "- evidence gaps before selection stage\n\n"
        "## weakest_link\n"
        f"- {weak_hint}\n\n"
        "## anti_goodhart_risks\n"
        "- metric gaming by optimizing volume without value outcome\n"
        "- local KPI improvement with global system degradation\n\n"
        "## source_summary\n"
        f"- viewpoints: {viewpoint_summary[:180]}\n"
        f"- layers: {layer_summary[:180]}\n\n"
        "_Generated by local-llm mode._"
    )


def _local_build_indicator_set(payload: Dict[str, Any]) -> str:
    passport = str(payload.get("characterization_passport", "")).lower()
    indicators = [
        ("decision_confidence_score", "optimization_goal"),
        ("unresolved_critical_gaps", "hard_constraint"),
        ("stakeholder_alignment_risk", "risk_signal"),
    ]
    if "cash" in passport or "burn" in passport:
        indicators.append(("cash_burn_rate", "hard_constraint"))
    lines = ["# Indicator Set", ""]
    for name, role in indicators:
        lines.append(f"- {name} | role={role}")
    lines.extend(["", "_Generated by local-llm mode._"])
    return "\n".join(lines)


def _local_build_parity_plan(payload: Dict[str, Any]) -> str:
    indicator_set = str(payload.get("indicator_set", ""))
    indicators = []
    for ln in indicator_set.splitlines():
        s = ln.strip()
        if s.startswith("- "):
            indicators.append(s[2:].split("|")[0].strip())
    if not indicators:
        indicators = ["decision_confidence_score", "unresolved_critical_gaps"]

    lines = [
        "# Parity Plan",
        "",
        "## assumptions",
        "- all alternatives compared under same budget/time window",
        "- same baseline and source dataset",
        "",
        "## evaluation_window",
        "- 30 days",
        "",
        "## indicators_in_scope",
    ]
    lines.extend(f"- {x}" for x in indicators)
    lines.extend(["", "_Generated by local-llm mode._"])
    return "\n".join(lines)


def _local_build_characteristic_card(payload: Dict[str, Any]) -> str:
    indicator = str(payload.get("indicator", "generic_indicator"))
    role = str(payload.get("role", "risk_signal"))
    direction = "higher is better" if role == "optimization_goal" else "lower is better"
    return (
        f"# Characteristic Card: {indicator}\n\n"
        f"- role: {role}\n"
        f"- measurement: define clear counting rule for {indicator}\n"
        f"- direction: {direction}\n"
        "- valid_until: 2026-12-31\n\n"
        "_Generated by local-llm mode._"
    )


def _local_build_problem_bundle(payload: Dict[str, Any]) -> str:
    mode = str(payload.get("problem_output", "archive"))
    base_candidates = [
        {
            "id": "prob_01",
            "title": "Strategic-model mismatch",
            "severity": 5,
            "urgency": 5,
            "cost_of_inaction": "high",
            "complexity": 3,
            "owner": "strategy_owner",
        },
        {
            "id": "prob_02",
            "title": "Evidence debt before solution selection",
            "severity": 4,
            "urgency": 4,
            "cost_of_inaction": "medium",
            "complexity": 2,
            "owner": "analysis_owner",
        },
        {
            "id": "prob_03",
            "title": "Role ownership ambiguity",
            "severity": 3,
            "urgency": 4,
            "cost_of_inaction": "medium",
            "complexity": 2,
            "owner": "operations_owner",
        },
    ]

    for p in base_candidates:
        p["goldilocks_score"] = p["severity"] + p["urgency"] - p["complexity"]

    ranked = sorted(base_candidates, key=lambda x: x["goldilocks_score"], reverse=True)
    top = ranked[0]

    def _facts_block(items: List[str]) -> str:
        return "\n".join(f"- {item}" for item in items)

    if mode == "archive":
        lines = ["# Problem Archive", ""]
        for p in ranked:
            lines.extend(
                [
                    f"## {p['id']} - {p['title']}",
                    "### Facts",
                    f"- severity signal: {p['severity']}",
                    f"- urgency signal: {p['urgency']}",
                    "### Interpretations",
                    f"- the problem is material enough to enter the current cycle with owner {p['owner']}",
                    "### Hypotheses to Validate",
                    "- the described severity and urgency are stable after quantitative clarification",
                    f"- severity: {p['severity']}",
                    f"- urgency: {p['urgency']}",
                    f"- cost_of_inaction: {p['cost_of_inaction']}",
                    f"- owner: {p['owner']}",
                    f"- goldilocks_score: {p['goldilocks_score']}",
                    "",
                ]
            )
        lines.append("_Generated by local-llm mode._")
        return "\n".join(lines)

    if mode == "portfolio":
        lines = ["# Problem Portfolio", "", "## Facts", "", "Selected for current cycle:"]
        for p in ranked[:2]:
            lines.extend(
                [
                    f"- {p['id']} | {p['title']} | priority={p['goldilocks_score']} | owner={p['owner']}",
                ]
            )
        lines.extend(
            [
                "",
                "## Interpretations",
                "",
                "- The portfolio keeps only problems that are both significant and bounded for the current cycle.",
                "",
                "## Hypotheses to Validate",
                "",
                "- Priority order may change after quantitative clarification of throughput, economics, and failure rate.",
                "",
                "_Generated by local-llm mode._",
            ]
        )
        return "\n".join(lines)

    if mode == "selected_card":
        return (
            "# Selected Problem Card\n\n"
            f"- problem_id: {top['id']}\n"
            f"- title: {top['title']}\n"
            "## facts\n"
            "- strategy and execution are misaligned\n"
            "- decisions are made with unresolved evidence gaps\n"
            "## chr_targets\n"
            "- decision frame must connect strategy, execution, and ownership without hidden handoffs\n"
            "- acceptance basis must be explicit before downstream selection\n"
            "## derived_thresholds\n"
            "- unresolved evidence gaps must be reduced before final decision commitment\n"
            "- rework remains unacceptable if ownership ambiguity persists across affected layers\n"
            "## anti_goodhart_conditions\n"
            "- do not treat rhetorical alignment as evidence of operational readiness\n"
            "- do not collapse missing constraints into optimistic narrative summaries\n"
            "## hypotheses_to_validate\n"
            "- missing explicit acceptance constraints are the main driver of decision drift\n"
            "- ownership clarification will materially reduce rework and ambiguity\n"
            "- affected_layers: business_model, requirements, allocation\n"
            "- affected_viewpoints: strategist, analyst, architect\n"
            "- evidence_refs: viewpoints/conflicts_index.md:L1\n"
            "- severity: high\n"
            "- urgency: high\n"
            "- cost_of_inaction: high\n"
            "- owner: strategy_owner\n"
            "- epistemic_status: inferred\n\n"
            "_Generated by local-llm mode._"
        )

    return (
        "# Comparison & Acceptance Spec\n\n"
        "## indicators\n"
        "- decision_confidence_score >= 0.7\n"
        "- unresolved_critical_gaps <= 1\n\n"
        "## hard_constraints\n"
        "- budget_limit: not provided in case input; must be confirmed before final selection\n"
        "- time_horizon_days: not provided in case input; must be confirmed before final selection\n\n"
        "## assumptions_to_confirm\n"
        "- implementation budget is missing\n"
        "- decision horizon is missing\n"
        "- allowed blast radius is missing\n\n"
        "## selection_policy\n"
        "- choose option that satisfies constraints and maximizes confidence gain\n"
        "- reject options violating hard constraints\n\n"
        "## reversibility\n"
        "- change must be reversible within pilot window\n\n"
        "_Generated by local-llm mode._"
    )


def _local_build_solution_portfolio(payload: Dict[str, Any]) -> str:
    lines = ["# Solution Portfolio", ""]
    for candidate in _local_default_solution_candidates():
        lines.append(f"## {candidate['id']}")
        lines.append(f"- type: {candidate['type']}")
        lines.append(f"- assurance_level: {candidate['assurance_level']}")
        if candidate["intervention_force"]:
            lines.append(f"- intervention_force: {candidate['intervention_force']}")
        if candidate["relevance_basis"]:
            lines.append(f"- relevance_basis: {candidate['relevance_basis']}")
        lines.append(f"- anti_goodhart_risk: {candidate['anti_goodhart_risk']}")
        lines.append(f"- solves_which_problems: {candidate['solves_which_problems']}")
        lines.append(f"- assumptions: {candidate['assumptions']}")
        lines.append(f"- expected_effects: {candidate['expected_effects']}")
        lines.append(f"- risks: {candidate['risks']}")
        lines.append(f"- constraints: {candidate['constraints']}")
        lines.append(f"- required_capabilities: {candidate['required_capabilities']}")
        lines.append(f"- reversibility: {candidate['reversibility']}")
        lines.append(f"- affected_viewpoints: {candidate['affected_viewpoints']}")
        lines.append("- evidence_refs: problems/ComparisonAcceptanceSpec.md:L1")
        lines.append("")
    lines.append("_Generated by local-llm mode._")
    return "\n".join(lines)


def _local_build_parity_tradeoff(payload: Dict[str, Any]) -> str:
    mode = str(payload.get("solution_output", "parity_report"))
    portfolio_text = str(payload.get("solution_portfolio", ""))
    portfolio_ids = _portfolio_solution_ids(portfolio_text)
    non_baseline = [sid for sid in portfolio_ids if sid != "sol_00_status_quo"]
    primary = non_baseline[0] if non_baseline else "sol_01_primary_option"
    support = non_baseline[1] if len(non_baseline) > 1 else primary
    tertiary = non_baseline[2] if len(non_baseline) > 2 else support
    if mode == "parity_plan":
        return (
            "# Parity Plan\n\n"
            "## assumptions\n"
            "- all alternatives are compared against the same validated portfolio baseline\n"
            "- budget and time horizon remain assumptions unless explicitly anchored in the case input\n\n"
            "## evaluation_window\n"
            "- pilot-sized comparison window with explicit unknown penalties\n\n"
            "## indicators_in_scope\n"
            "- confidence_gain\n"
            "- unresolved_gaps\n"
            "- risk_exposure\n"
            "- reversibility\n\n"
            "_Generated by local-llm mode._"
        )

    if mode == "tradeoff_table":
        rows = [f"| sol_00_status_quo | low | high | high | n/a |"]
        profiles = [
            ("low-medium", "medium", "low", "high"),
            ("medium", "medium", "medium", "medium"),
            ("high", "low", "medium", "medium-high"),
            ("medium", "medium", "medium-high", "medium"),
        ]
        for idx, sid in enumerate(non_baseline):
            profile = profiles[min(idx, len(profiles) - 1)]
            rows.append(f"| {sid} | {profile[0]} | {profile[1]} | {profile[2]} | {profile[3]} |")
        return (
            "# Tradeoff Table\n\n"
            "| solution | confidence_gain | unresolved_gaps | risk_exposure | reversibility |\n"
            "|---|---|---|---|---|\n"
            + "\n".join(rows)
            + "\n\n"
            "_Generated by local-llm mode._"
        )

    return (
        "# Parity Report\n\n"
        "## Findings\n"
        f"- {primary} dominates sol_00_status_quo on target criteria.\n"
        f"- {support} and {tertiary} remain viable with different tradeoffs.\n"
        f"- {primary} remains the leading candidate because it improves outcome quality without discarding reversibility.\n"
        "- parity validity: usable only with explicit penalties for missing budget/time data; these are not confirmed facts.\n\n"
        "## Decision Logic\n"
        f"- {primary} gives the strongest effect under current assumptions.\n"
        f"- {support} remains a safer support option if risk tolerance is lower.\n\n"
        "## Traceability\n"
        "- solutions/SolutionPortfolio.md:L1\n"
        "- problems/ComparisonAcceptanceSpec.md:L1\n\n"
        "_Generated by local-llm mode._"
    )


def _local_build_conflict_routing(payload: Dict[str, Any]) -> str:
    return (
        "# Conflict Records\n\n"
        "## conflict_01\n"
        "- conflict_type: quality-attribute conflict\n"
        "- layers_involved: requirements,functional\n"
        "- viewpoints_involved: analyst,architect\n"
        "- method_selected: ATAM\n"
        "- selection_rationale: tradeoff between speed and reliability\n"
        "- resolution_status: resolved\n\n"
        "## conflict_02\n"
        "- conflict_type: alternative ranking conflict\n"
        "- layers_involved: business_model,allocation\n"
        "- viewpoints_involved: strategist,operator,client\n"
        "- method_selected: MCDA\n"
        "- selection_rationale: need explicit weighted comparison\n"
        "- resolution_status: resolved\n\n"
        "_Generated by local-llm mode._"
    )


def _local_build_selection_bundle(payload: Dict[str, Any]) -> str:
    mode = str(payload.get("solution_output", "selected_solutions"))
    portfolio_text = str(payload.get("solution_portfolio", ""))
    portfolio_ids = _portfolio_solution_ids(portfolio_text)
    non_baseline = [sid for sid in portfolio_ids if sid != "sol_00_status_quo"]
    primary = non_baseline[0] if non_baseline else "sol_01_primary_option"
    support = non_baseline[1] if len(non_baseline) > 1 else primary
    rejected = non_baseline[2:] if len(non_baseline) > 2 else []
    if mode == "selected_solutions":
        rejected_lines = [f"- {sid} (kept as lower-priority alternative under current horizon)" for sid in rejected]
        rejected_block = "\n".join(rejected_lines) + "\n\n" if rejected_lines else "\n"
        return (
            "# Selected Solutions\n\n"
            f"- {primary}\n"
            f"- {support}\n\n"
            "Rejected:\n"
            "- sol_00_status_quo (fails acceptance constraints)\n"
            f"{rejected_block}"
            "_Generated by local-llm mode._"
        )
    if mode == "adr":
        rejected_text = "\n".join(f"- {sid}: lower parity score under current assumptions." for sid in rejected)
        rejected_block = rejected_text + "\n\n" if rejected_text else "\n"
        return (
            "# ADR-001: Solution Selection\n\n"
            "## Context\n"
            "- Selection based on ComparisonAcceptanceSpec and parity/conflict outputs.\n\n"
            "## Decision\n"
            f"- Choose {primary} as primary and {support} as support.\n\n"
            "## Rejected Alternatives\n"
            "- sol_00_status_quo: does not satisfy constraints.\n"
            f"{rejected_block}"
            "## Risks\n"
            "- integration complexity; adoption lag.\n\n"
            "## Evidence Basis\n"
            "- problems/ComparisonAcceptanceSpec.md:L1\n"
            "- solutions/ParityReport.md:L1\n"
            "- solutions/ConflictRecords.md:L1\n\n"
            "## Consequences\n"
            "- implementation starts with a bounded architecture slice instead of a full transformation.\n"
            "- the team keeps a fallback path if adoption or technical fit is weaker than expected.\n\n"
            "_Generated by local-llm mode._"
        )
    if mode == "runbook":
        return (
            "# Runbook\n\n"
            "## Preconditions\n"
            "- owners and success criteria are aligned.\n\n"
            "## Execution Steps\n"
            "1. Align owners and success criteria.\n"
            "2. Launch limited architecture slice after lower-force controls are explicitly bounded.\n"
            "3. Measure indicators weekly.\n"
            "4. Expand only if acceptance thresholds are stable.\n\n"
            "## Success Criteria\n"
            "- acceptance thresholds remain stable across the pilot window.\n"
            "- no material regressions appear in the monitored indicators.\n\n"
            "_Generated by local-llm mode._"
        )
    return (
        "# Rollback Plan\n\n"
        "## Triggers\n"
        "- Trigger rollback if unresolved_critical_gaps increases for 2 consecutive checks.\n\n"
        "## Actions\n"
        "- Revert to previous baseline process and freeze expansion.\n"
        "- Re-open problem framing with updated evidence.\n\n"
        "## Safe State\n"
        "- the system returns to the previous stable operating baseline.\n\n"
        "_Generated by local-llm mode._"
    )


def _short_lines(text: str, max_lines: int = 4) -> List[str]:
    meta_prefixes = (
        "id:",
        "artifact_type:",
        "workspace_id:",
        "source:",
        "traceability:",
        "file:",
        "status:",
        "owner_role:",
        "valid_until:",
        "based_on:",
        "stage:",
        "state:",
        "parent_refs:",
        "source_refs:",
        "evidence_refs:",
        "viewpoints:",
        "epistemic_status:",
        "assurance_level:",
        "gate_status:",
        "violated_principles:",
        "next_expected_artifacts:",
        "created_at:",
        "updated_at:",
    )
    lines: List[str] = []
    for raw in str(text).splitlines():
        s = raw.strip()
        low = s.lower()
        if not s:
            continue
        if s in {"---", "```", "```markdown", "```json"}:
            continue
        if low.startswith(meta_prefixes):
            continue
        if low.startswith("### директория:") or low.startswith("#### файл:"):
            continue
        s = re.sub(r"^#+\s*", "", s)
        if s.startswith(("- ", "* ", "+ ")):
            s = s[2:].strip()
        s = re.sub(r"^\d+[.)]\s+", "", s)
        s = re.sub(r"[*_`]+", "", s)
        s = re.sub(r"\s+", " ", s).strip()
        if not s:
            continue
        low = s.lower()
        if low.startswith(meta_prefixes):
            continue
        if low.startswith(("source:", "traceability:", "generated by ", "sourcetext:", "selectionrationale:")):
            continue
        if re.match(r"^sol[_0-9a-z-]+$", low):
            continue
        if re.match(r'^"?(name|measurementprocedure|artifact|class|text|role|method|decision|context|consequences|status|date)"?\s*:', low):
            continue
        if re.match(r"^(type|assurancelevel|assurance_level|conflicttype|layersinvolved|viewpointsinvolved|methodselected|resolutionstatus|artifacttype|workspaceid|updatedat|claimscount|edgescount)\s*:", low):
            continue
        if low.startswith("claim::") or "| class=" in low or "| artifact=" in low or "| text=" in low:
            continue
        if re.match(r"^[a-z0-9_./:-]+$", low) and len(low) < 40:
            continue

        candidates = [seg.strip(" -;,.") for seg in re.split(r"(?<=[.!?])\s+", s) if seg.strip(" -;,.")]
        if not candidates:
            candidates = [s]
        for candidate in candidates:
            c_low = candidate.lower()
            words = re.findall(r"[A-Za-zА-Яа-я0-9%+-]+", candidate)
            if len(candidate) < 12:
                continue
            if len(words) < 3:
                continue
            if re.match(r"^[a-z0-9_./:-]+$", c_low) and len(c_low) < 60:
                continue
            if candidate not in lines:
                lines.append(candidate)
            if len(lines) >= max_lines:
                return lines[:max_lines]
    return lines[:max_lines]


def _market_viewpoint_required_from_artifacts(artifacts: Dict[str, Any]) -> bool:
    raw = str(artifacts.get("analysis/domain_profile.json", "")).strip()
    if not raw:
        return False
    try:
        profile = json.loads(raw)
    except Exception:
        return False
    axes = {
        str(item.get("axis"))
        for item in profile.get("domain_axes", [])
        if isinstance(item, dict) and str(item.get("axis") or "").strip()
    }
    return bool({"market_validation", "commercial_presales_bottleneck"} & axes)


def _pick_lines(lines: List[str], keywords: List[str], limit: int = 2) -> List[str]:
    picked = [ln for ln in lines if any(k in ln.lower() for k in keywords)]
    return picked[:limit]


def _sentence(text: str) -> str:
    out = str(text).strip().strip(" -;,.")
    if not out:
        return ""
    if out[-1] not in ".!?":
        out += "."
    return out


def _join_sentences(lines: List[str], fallback: str, limit: int = 2) -> str:
    selected = [_sentence(ln) for ln in lines[:limit] if ln.strip()]
    selected = [x for x in selected if x]
    if not selected:
        return _sentence(fallback)
    return " ".join(selected)


def _epistemic_triplet(facts: str, interpretations: str, hypotheses: str) -> str:
    return (
        f"**Факты:** {facts}\n"
        f"**Интерпретации:** {interpretations}\n"
        f"**Гипотезы / следующий шаг:** {hypotheses}"
    )


def _local_analytical_section_body(
    title: str,
    rel: str,
    text: str,
    artifacts: Dict[str, Any],
) -> str:
    lines = _short_lines(text, max_lines=12)
    selected_problem = _short_lines(str(artifacts.get("problems/SelectedProblemCard.md", "")), max_lines=8)
    acceptance = _short_lines(str(artifacts.get("problems/ComparisonAcceptanceSpec.md", "")), max_lines=8)
    parity = _short_lines(str(artifacts.get("solutions/ParityReport.md", "")), max_lines=8)
    runbook = _short_lines(str(artifacts.get("operation/Runbook.md", "")), max_lines=8)
    evidence = _short_lines(str(artifacts.get("evidence/evidence_graph.md", "")), max_lines=8)

    if title == "Action Context":
        return _epistemic_triplet(
            "GAP: source artifact missing or empty.",
            "Без исходного контекста снижается полнота доказательной базы и теряется часть первичных нюансов запроса.",
            f"Восстановить `{rel}`, затем повторить сборку отчета.",
        )

    if title == "Bounded Context":
        focus = _join_sentences(
            _pick_lines(lines, ["problem", "узк", "bottleneck", "маршрут", "заяв", "director", "технич"]),
            "В фокусе находится ограниченный контур принятия решения и прохождения заявки через узкое место.",
        )
        constraints = _join_sentences(
            _pick_lines(lines, ["target", "constraint", "огранич", "±", "sla", "budget", "вериф", "shadow"]),
            "Контур анализа ограничен критериями приемки, точностью оценки, бюджетом и защитой операционного ядра.",
        )
        return _epistemic_triplet(
            focus,
            constraints,
            "Решение должно касаться конкретной проблемной зоны, не переписывая всю систему.",
        )

    if title == "Normalized Case":
        observed = _join_sentences(lines[:3], "Кейс описывает операционный разрыв между входящим спросом и скоростью ответа.")
        impact = _join_sentences(
            _pick_lines(lines, ["проблем", "delay", "дн", "клієн", "client", "втра", "lost", "конкур"]),
            "Задержка ответа ухудшает конверсию, перегружает ключевой ресурс и ослабляет позицию компании на рынке.",
        )
        return _epistemic_triplet(
            observed,
            impact,
            "Требуется системное устранение корневой причины разрыва.",
        )

    if title == "4-Layer Model":
        return (
            f"- Как выглядит сбой по слоям: {_join_sentences(lines[:4], 'Разрыв проявляется на уровне бизнес-модели, процесса, инструментов и ролей.', limit=4)}\n"
            "- Почему это важно: проблема не локальна и не сводится к одному человеку, поэтому точечный административный нажим не даст устойчивого результата.\n"
            "- Что из этого следует: нужно одновременно перепроектировать процесс маршрутизации, инструменты оценки и распределение полномочий."
        )

    if title == "Viewpoint Matrix":
        viewpoints = []
        required = ["strategist", "analyst", "operator", "architect", "critic", "client"]
        optional: List[str] = []
        if _market_viewpoint_required_from_artifacts(artifacts):
            required.append("market")
        else:
            optional.append("market")
        for vp in required + optional:
            if str(artifacts.get(f"viewpoints/{vp}.md", "")).strip():
                viewpoints.append(vp)
        coverage_map = {
            "strategist": "стратег",
            "analyst": "аналитик",
            "operator": "оператор",
            "architect": "архитектор",
            "critic": "критик",
            "client": "клиент",
            "market": "рынок",
        }
        coverage = ", ".join(coverage_map.get(vp, vp) for vp in viewpoints) if viewpoints else "точки зрения не собраны"
        conflicts = "Конфликты между точками зрения явно не зафиксированы." if "no explicit conflicts" in text.lower() else "Между точками зрения есть напряжение, требующее отдельного разрешения."
        missing_required = [vp for vp in required if not str(artifacts.get(f"viewpoints/{vp}.md", "")).strip()]
        missing_optional = [vp for vp in optional if not str(artifacts.get(f"viewpoints/{vp}.md", "")).strip()]
        quality_note_parts = []
        if missing_required:
            quality_note_parts.append("Отсутствуют обязательные точки зрения: " + ", ".join(coverage_map.get(vp, vp) for vp in missing_required) + ".")
        if missing_optional:
            quality_note_parts.append("Не собраны optional-точки зрения: " + ", ".join(coverage_map.get(vp, vp) for vp in missing_optional) + ".")
        quality_note = " ".join(quality_note_parts)
        return (
            f"- Какие точки зрения покрыты: {coverage}.\n"
            f"- Что показывает матрица взглядов: {conflicts}\n"
            + ("- Ограничение coverage: " + quality_note + "\n" if quality_note else "")
            + "- Почему это важно: совпадение разных перспектив усиливает надежность диагноза и снижает риск слепых зон."
        )

    if title == "Characterization Passport":
        return (
            f"- Что признано слабым звеном: {_join_sentences(_pick_lines(lines, ['weak', 'слаб', 'triage', 'автоном', 'routing', 'маршрути']), 'Система не умеет автономно обрабатывать типовые кейсы без входа в экспертный контур.')}\n"
            "- Почему это важно: пока автономность равна нулю, масштабирование потока автоматически разрушает срок реакции и качество исполнения.\n"
            "- Что это означает для дальнейших стадий: решение должно повышать автономность, но не ломать защиту производственного ядра."
        )

    if title == "Indicator Set":
        metrics = _pick_lines(lines, ["time", "sla", "throughput", "accuracy", "qualification", "rate", "стоим", "срок", "точност", "поток"])
        return (
            f"- Какие метрики взяты в управление: {_join_sentences(metrics, 'Скорость цикла, точность решения, доля автономной маршрутизации и защита операционного SLA.', limit=4)}\n"
            "- Почему это важно: без измеримых индикаторов команда будет спорить о впечатлениях вместо контроля реального эффекта.\n"
            "- Что делать дальше: привязать переходы между фазами решения к этим метрикам, а не к субъективной уверенности участников."
        )

    if title == "Problem Archive":
        cause = _join_sentences(_pick_lines(lines, ["причин", "cause", "отсутств", "нет", "missing"]), "Корневая причина связана с отсутствием отчужденной логики и фильтрации на входе.")
        mechanism = _join_sentences(_pick_lines(lines, ["mechan", "влиян", "100%", "маршрут", "эскалац", "triage"]), "Все заявки проходят через единый экспертный узел без промежуточного отбора.")
        return (
            f"- Корневая причина: {cause}\n"
            f"- Механизм поломки: {mechanism}\n"
            "- К чему это ведет: растет очередь обработки, ухудшается предсказуемость выхода и появляется прямой ущерб операционному контуру."
        )

    if title == "Problem Portfolio":
        return (
            f"- Какие проблемы отобраны в работу: {_join_sentences(lines[:3], 'В работу взяты проблема централизации решения и проблема слепой эскалации неподготовленного входа.', limit=3)}\n"
            "- Почему это важно: портфель показывает, что лечить нужно не только узкое место в экспертном контуре, но и качество входящего потока.\n"
            "- Что из этого следует: решение должно сочетать делегирование типовых кейсов и фильтрацию сложных случаев до входа в экспертный контур."
        )

    if title == "Selected Problem Card":
        selected = _join_sentences(selected_problem[:3] or lines[:3], "Выбрана проблема отчуждения типовой оценки от самого дорогого производственного ресурса.", limit=3)
        targets = _join_sentences(acceptance[:3], "Цель состоит в отделении типовой оценки от экспертного контура без потери точности.", limit=2)
        return (
            f"- Какая проблема выбрана как ключевая: {selected}\n"
            f"- Почему именно она: {targets}\n"
            "- Что это означает для решения: приоритет отдан проблеме, которая расшивает главное узкое горлышко и дает обратимый путь внедрения."
        )

    if title == "Comparison & Acceptance Spec":
        return (
            f"- Какие условия считаются обязательными: {_join_sentences(acceptance[:4], 'Решение должно ускорить типовые ответы, удержать точность, не просадить SLA и пройти теневую проверку.', limit=4)}\n"
            "- Почему это важно: критерии приемки отсекают решения, которые красивы на бумаге, но опасны для маржи или для производства.\n"
            "- Что это означает для выбора: скорость сама по себе недостаточна, если она покупается ценой ошибки в себестоимости."
        )

    if title == "Solution Portfolio":
        return (
            f"- Какие альтернативы рассмотрены: {_join_sentences(lines[:4], 'Рассмотрены статус-кво, постепенное отчуждение оценки, немедленное делегирование и радикальная ИТ-автоматизация.', limit=4)}\n"
            "- Почему это важно: наличие разных классов альтернатив позволяет сравнить не только стоимость, но и обратимость, риск и скорость эффекта.\n"
            "- Что из этого следует: финальное решение должно быть выбрано через trade-off между скоростью, точностью и управляемостью внедрения."
        )

    if title == "Parity Plan/Report":
        return (
            f"- Что показало сравнение альтернатив: {_join_sentences(parity[:4] or lines[:4], 'Часть вариантов проваливается по бюджету, часть по точности, а безопасный вариант выигрывает за счет управляемости.', limit=4)}\n"
            "- Почему это важно: parity-проверка отделяет реально приемлемые решения от тех, которые нарушают жесткие ограничения.\n"
            "- Что это означает для отбора: безопасный пошаговый сценарий сильнее радикальных и рискованных ускорителей."
        )

    if title == "Tradeoff Resolution":
        return (
            f"- Какой конфликт пришлось разрешать: {_join_sentences(lines[:3], 'Главный конфликт проходит между скоростью ответа и защитой точности/маржи.', limit=3)}\n"
            "- Почему решение принято именно так: при жестком ограничении на точность скорость не может быть первичной ценностью.\n"
            "- Что из этого следует: выбран поэтапный сценарий, где сначала снимается неопределенность, а потом масштабируется эффект."
        )

    if title == "ADR":
        adr_core = _join_sentences(lines[:4], "Зафиксирован поэтапный архитектурный выбор, который сначала снижает неопределенность, затем делегирует типовые операции.", limit=4)
        return (
            f"- Какое решение зафиксировано: {adr_core}\n"
            "- Почему это важно: ADR связывает альтернативы, ограничения, причины выбора и последствия в одну управленческую рамку.\n"
            "- Что делать дальше: реализовать решение как контролируемый пилот, а не как мгновенную тотальную реформу."
        )

    if title == "Runbook/Rollback/Impact Plan":
        plan = _join_sentences(runbook[:4] or lines[:4], "План внедрения разбит на ограниченные фазы с явными триггерами запуска и отката.", limit=4)
        return (
            f"- Как выглядит операционный план: {plan}\n"
            "- Почему это важно: внедрение обратимо и не требует необратимого организационного прыжка в начале.\n"
            "- Что это означает для управления: пилот должен сопровождаться заранее утвержденным rollback-сценарием и метриками эффекта."
        )

    if title == "Evidence Status":
        if not evidence and not lines:
            return (
                "- Что зафиксировано: доказательная база неполна и не собрана в отдельный граф.\n"
                "- Почему это важно: без связанной evidence-модели труднее защищать решение перед руководством и повторно его проверять.\n"
                "- Что сделать: восстановить evidence-артефакты и повторить трассировку выводов."
            )
        return (
            f"- Что показывает доказательная база: {_join_sentences(evidence[:3] or lines[:3], 'Артефакты решения связаны между собой и поддерживают сквозную трассировку от симптомов к выбранному действию.', limit=3)}\n"
            "- Почему это важно: решение подтверждается не одним документом, а цепочкой согласованных артефактов.\n"
            "- Что это означает для качества вывода: уровень защищенности решения выше, чем при изолированном экспертном мнении."
        )

    if title == "Open Questions":
        if "[]" in text or not lines:
            return (
                "- Что остается неизвестным: явная очередь вопросов не сформирована, но количественные пробелы во входных данных сохраняются.\n"
                "- Почему это важно: без точной экономики процесса сложно посчитать ROI и темп масштабирования решения.\n"
                "- Что сделать: собрать стоимость часа ключевого эксперта, структуру воронки и долю типовых кейсов."
            )
        return (
            f"- Какие вопросы остаются открытыми: {_join_sentences(lines[:3], 'Часть количественных и организационных параметров еще не подтверждена.', limit=3)}\n"
            "- Почему это важно: открытые вопросы ограничивают точность прогноза эффекта и рисков.\n"
            "- Что сделать: закрыть недостающие данные в рамках пилота и следующего цикла переоценки."
        )

    if title == "Escalation/Re-entry conditions":
        return (
            "- Когда нужна эскалация: при невозможности удержать точность, при подтвержденном негативном эффекте на операционное ядро или при провале стандартизации типовых кейсов.\n"
            "- Почему это важно: re-entry условия защищают от замалчивания неудачного пилота и от ложного чувства прогресса.\n"
            "- Что делать: заранее согласовать пороги эскалации и владельца решения на следующий цикл."
        )

    observed = _join_sentences(lines[:2], "Факты описаны частично.")
    because = _join_sentences(lines[2:4], "Дополнительные ограничения не раскрыты полностью.")
    therefore = _join_sentences(lines[4:6], "Нужна синхронизация решений, критериев приемки и плана внедрения.")
    return _epistemic_triplet(observed, because, therefore)


def _local_build_reporting_analytical(payload: Dict[str, Any]) -> str:
    sections = payload.get("analytical_sections", [])
    artifacts = payload.get("artifact_context", {})
    missing = set(payload.get("missing_sources", []))

    parts = ["# Аналитический полный отчет", ""]
    for section in sections:
        idx = str(section.get("index", ""))
        title = str(section.get("title", ""))
        rel = str(section.get("source", ""))
        text = str(artifacts.get(rel, ""))

        if not text or rel in missing:
            body = (
                "- Что зафиксировано: GAP: source artifact missing or empty.\n"
                "- Почему это важно: без этого источника отчет теряет часть доказательной основы и управленческой надежности.\n"
                f"- Что сделать: восстановить `{rel}`, затем повторить сборку отчета."
            )
        else:
            body = _local_analytical_section_body(title, rel, text, artifacts)

        parts.extend([f"## {idx}. {title}", f"- source: {rel}", body, ""])

    parts.extend(
        [
            "## Трассируемость",
            "- Выводы сформированы только на базе входных артефактов кейса без добавления новых фактов.",
            "- Для каждого раздела сохраняется ссылка на исходный артефакт.",
            "",
            "_Generated by local-llm mode._",
        ]
    )
    return "\n".join(parts)


def _local_build_reporting_executive(payload: Dict[str, Any]) -> str:
    sections = payload.get("executive_sections", [])
    artifacts = payload.get("artifact_context", {})
    selected = str(artifacts.get("solutions/SelectedSolutions.md", ""))
    selected_lines = []
    confirmed_actions: List[str] = []
    pilot_hypotheses: List[str] = []
    provisional_recommendations: List[str] = []
    for ln in selected.splitlines():
        s = ln.strip()
        if not s.startswith("- "):
            continue
        val = s[2:].strip()
        low_val = val.lower()
        if low_val.startswith("confirmed_action:"):
            confirmed_actions.append(val.split(":", 1)[1].strip())
            continue
        if low_val.startswith("pilot_hypothesis:"):
            pilot_hypotheses.append(val.split(":", 1)[1].strip())
            continue
        if low_val.startswith("provisional_recommendation:"):
            provisional_recommendations.append(val.split(":", 1)[1].strip())
            continue
        if not val.lower().startswith("sol_"):
            continue
        if "<-" in val:
            continue
        selected_lines.append(val)
    selected_lines = selected_lines[:3]

    analytical = _short_lines(str(artifacts.get("reports/Analytical_Full_Report.md", "")), max_lines=20)
    normalized = _short_lines(str(artifacts.get("intake/normalized_case.md", "")), max_lines=8)
    selected_problem = _short_lines(str(artifacts.get("problems/SelectedProblemCard.md", "")), max_lines=10)
    acceptance = _short_lines(str(artifacts.get("problems/ComparisonAcceptanceSpec.md", "")), max_lines=10)
    parity = _short_lines(str(artifacts.get("solutions/ParityReport.md", "")), max_lines=10)
    portfolio = _short_lines(str(artifacts.get("solutions/SolutionPortfolio.md", "")), max_lines=12)
    adr = _short_lines(str(artifacts.get("decisions/ADR-001.md", "")), max_lines=10)
    runbook = _short_lines(str(artifacts.get("operation/Runbook.md", "")), max_lines=10)
    rollback = _short_lines(str(artifacts.get("operation/RollbackPlan.md", "")), max_lines=10)
    evidence = _short_lines(str(artifacts.get("evidence/evidence_graph.md", "")), max_lines=8)
    refresh = _short_lines(str(artifacts.get("evidence/refresh_report.md", "")), max_lines=8)
    missing_sources = set(payload.get("missing_sources", []))
    raw_case_blob = " ".join(
        [
            str(artifacts.get("intake/normalized_case.md", "")),
            str(artifacts.get("problems/SelectedProblemCard.md", "")),
            str(artifacts.get("problems/ComparisonAcceptanceSpec.md", "")),
            str(artifacts.get("solutions/ParityReport.md", "")),
            str(artifacts.get("decisions/ADR-001.md", "")),
            str(artifacts.get("operation/Runbook.md", "")),
        ]
    ).lower()

    human_names: Dict[str, str] = {}
    current_id = ""
    for raw in str(artifacts.get("solutions/SolutionPortfolio.md", "")).splitlines():
        s = raw.strip()
        if s.startswith("## "):
            match = re.match(r"##\s+(sol[_0-9a-z-]+)\s*[:-]?\s*(.*)$", s, flags=re.IGNORECASE)
            if not match:
                current_id = ""
                continue
            current_id = match.group(1).strip()
            title = match.group(2).strip(" -:")
            if title:
                human_names[current_id] = title
            continue
        if current_id and s.startswith("- ") and ":" in s:
            key, value = s[2:].split(":", 1)
            if key.strip().lower() in {"title", "name", "label"} and value.strip():
                human_names[current_id] = value.strip()

    recommendation_items = []
    if provisional_recommendations:
        for item in provisional_recommendations[:3]:
            label = human_names.get(item, item.replace("_", " "))
            recommendation_items.append(
                f"- Предварительная рекомендация: {label}. Вариант предлагается к реализации только как условно допустимый до повторной переоценки после добора данных."
            )
    elif pilot_hypotheses:
        recommendation_items = [
            "- Гипотеза пилота: на этом цикле не внедрять целевую архитектуру, а собрать недостающие данные и повторить выбор."
        ]
    else:
        for item in selected_lines:
            label = human_names.get(item, item.replace("_", " "))
            prefix = "Подтвержденное действие" if item in confirmed_actions or confirmed_actions else "Гипотеза пилота"
            recommendation_items.append(
                f"- {prefix}: {label}. Вариант взят в работу под текущие ограничения по точности, скорости и обратимости."
            )
    recommendations = (
        "\n".join(recommendation_items)
        if recommendation_items
        else "- GAP: рекомендации не опубликованы, так как не зафиксирован согласованный набор выбранных решений."
    )

    case_text = _join_sentences(
        normalized[:2] or analytical[:3] or selected_problem[:3],
        "Проект находится в точке, где нужно одновременно удержать темп реализации и снизить риск неверного выбора.",
        limit=3,
    )
    acceptance_text = _join_sentences(
        acceptance[:2] + refresh[:2],
        "Решение должно пройти через ограничения по бюджету, качеству, обратимости и условиям повторной проверки.",
        limit=3,
    )
    parity_text = _join_sentences(
        parity[:2] + adr[:2] + portfolio[:1],
        "Альтернативы сравниваются через ограничения, риск, обратимость и ожидаемый эффект.",
        limit=3,
    )
    rollout_text = _join_sentences(
        runbook[:2] + rollback[:1],
        "Следующий шаг — ограниченный пилот с владельцем, сроком, rollback-сценарием и измеримыми критериями результата.",
        limit=3,
    )
    default_sections = {
        "1": case_text,
        "2": _join_sentences(selected_problem[:3], "Ключевая проблема — рассогласование между целевой логикой проекта и фактической организацией исполнения.", limit=3),
        "3": _join_sentences(
            _pick_lines(selected_problem + acceptance + parity, ["скор", "risk", "устойчив", "quality", "обратим", "срок", "budget"], limit=3),
            "Главный конфликт интересов проходит между потребностью в быстрых изменениях и требованиями к устойчивости результата.",
            limit=3,
        ),
        "4": recommendations,
        "5": parity_text,
        "6": _join_sentences(
            runbook[:2] + rollback[:2] + refresh[:2],
            "Сохраняются риски по полноте доказательной базы, согласованности ролей и реалистичности темпа внедрения.",
            limit=3,
        ),
        "7": _join_sentences(
            rollback[:3],
            "Откат активируется при ухудшении ключевых метрик в двух последовательных контрольных периодах.",
            limit=3,
        ),
        "8": rollout_text,
        "9": acceptance_text,
        "10": _join_sentences(
                evidence[:2] + refresh[:2],
                "Уровень уверенности рабочий для пилота, но не финальный для масштабирования без дополнительной проверки.",
                limit=3,
            ),
        }

    if "raw/case_input.md" in missing_sources:
        default_sections["10"] += " Исходный сырой ввод отсутствует, поэтому часть исходного контекста реконструирована косвенно."

    parts = ["# Краткая управленческая записка", ""]
    for section in sections:
        idx = str(section.get("index", ""))
        title = str(section.get("title", ""))
        parts.extend([f"## {idx}. {title}", default_sections.get(idx, "Раздел ожидает уточнения по артефактам."), ""])
    parts.append("_Generated by local-llm mode._")
    return "\n".join(parts)


def _call_openai_responses(system_prompt: str, user_payload: Dict[str, Any]) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    req_payload = {
        "model": model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps(user_payload, ensure_ascii=False),
                    }
                ],
            },
        ],
    }

    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(req_payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=60) as resp:
        raw = json.loads(resp.read().decode("utf-8"))

    text = raw.get("output_text", "")
    if text:
        return text

    output = raw.get("output", [])
    if output and isinstance(output, list):
        for item in output:
            content = item.get("content", [])
            for block in content:
                txt = block.get("text")
                if txt:
                    return txt
    return ""


def _call_antigravity_adapter(system_prompt: str, user_payload: Dict[str, Any]) -> str:
    """
    Optional adapter for Antigravity-managed LLMs.
    Expects env ANTIGRAVITY_LLM_CMD with a shell command that reads JSON from stdin
    and returns markdown text to stdout.
    """
    cmd = os.environ.get("ANTIGRAVITY_LLM_CMD", "").strip()
    if not cmd:
        return ""

    req = {
        "system_prompt": system_prompt,
        "user_payload": user_payload,
    }
    proc = subprocess.run(
        cmd,
        input=json.dumps(req, ensure_ascii=False),
        text=True,
        shell=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip()


def _call_gemini_responses(system_prompt: str, user_payload: Dict[str, Any]) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    req_payload = {
        "systemInstruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": [
            {
                "parts": [{"text": json.dumps(user_payload, ensure_ascii=False)}]
            }
        ],
        "generationConfig": {
            "temperature": 0.2
        }
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(req_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    max_retries = 5
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(request, timeout=180) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            
            candidates = raw.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if parts:
                    return parts[0].get("text", "")
            return ""
            
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="ignore")
            if e.code in (429, 503):
                if attempt == 0:
                    print(f"  [API] Детали ошибки {e.code} от Google: {error_body.strip()[:200]}")
                wait_time = (attempt + 1) * 15  # 15s, 30s, 45s...
                print(f"  [API] Временно уперлись в лимит или сервер перегружен (Error {e.code}). Ждем {wait_time} сек... (Попытка {attempt+1}/{max_retries})")
                time.sleep(wait_time)
                continue
            else:
                print(f"Gemini API HTTP Error: {e.code} - {e.reason}\nBody: {error_body}")
                break
        except Exception as e:
            print(f"Gemini API error: {e}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 15
                print(f"  [API] Сетевая ошибка или таймаут. Ждем {wait_time} сек... (Попытка {attempt+1}/{max_retries})")
                time.sleep(wait_time)
                continue
            break
        
    return ""


def _strip_fenced_wrapper(text: str) -> str:
    stripped = str(text or "").strip()
    if not stripped:
        return str(text or "")
    match = re.match(r"^```(?:markdown|md|text)?\n(.*?)\n```\s*$", stripped, flags=re.S)
    if match:
        return match.group(1).strip()
    return str(text)


def generate_markdown_with_skill(
    system_skill_prompt: str,
    user_payload: Dict[str, Any],
    mode: str = "local",
) -> str:
    selected = (mode or "local").lower()
    task_type = str(user_payload.get("task_type", ""))

    if selected == "antigravity":
        text = _call_antigravity_adapter(system_skill_prompt, user_payload)
        if text.strip():
            return _strip_fenced_wrapper(text)

    if selected == "openai":
        text = _call_openai_responses(system_skill_prompt, user_payload)
        if text.strip():
            return _strip_fenced_wrapper(text)

    if selected == "gemini":
        text = _call_gemini_responses(system_skill_prompt, user_payload)
        if text.strip():
            return _strip_fenced_wrapper(text)

    if task_type == "build_layer":
        return _local_build_layer(user_payload)
    if task_type == "build_viewpoint":
        return _local_build_viewpoint(user_payload)
    if task_type == "build_characterization":
        return _local_build_characterization(user_payload)
    if task_type == "build_indicator_set":
        return _local_build_indicator_set(user_payload)
    if task_type == "build_parity_plan":
        return _local_build_parity_plan(user_payload)
    if task_type == "build_characteristic_card":
        return _local_build_characteristic_card(user_payload)
    if task_type == "build_problem_bundle":
        return _local_build_problem_bundle(user_payload)
    if task_type == "build_solution_portfolio":
        return _local_build_solution_portfolio(user_payload)
    if task_type == "build_parity_tradeoff":
        return _local_build_parity_tradeoff(user_payload)
    if task_type == "build_conflict_routing":
        return _local_build_conflict_routing(user_payload)
    if task_type == "build_selection_bundle":
        return _local_build_selection_bundle(user_payload)
    if task_type == "build_reporting_analytical":
        return _local_build_reporting_analytical(user_payload)
    if task_type == "build_reporting_executive":
        return _local_build_reporting_executive(user_payload)

    return "# Generated Artifact\n\n- No task-specific local renderer configured.\n\n_Generated by local-llm mode._"
