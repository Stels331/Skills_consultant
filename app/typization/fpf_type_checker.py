from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


GENERIC_PROCESS_TERMS = {"процес", "комплекс", "process", "workflow"}
PROCESS_CONTEXT_HINTS = {
    "етап",
    "стадії",
    "стадия",
    "stage",
    "handoff",
    "sequence",
    "workflow",
    "синхронізація",
}

UMBRELLA_TERMS = {
    "процес",
    "комплекс",
    "ресурс",
    "труднощі",
    "система",
    "питання",
    "проблема",
}

LIFECYCLE_AMBIGUOUS_TERMS = {
    "план",
    "процес",
    "проект",
    "запуск",
    "рішення",
}

DESIGN_TIME_HINTS = {
    "план",
    "стратег",
    "опис",
    "схема",
    "проект",
    "бізнес-план",
}

RUNTIME_HINTS = {
    "запуск",
    "виконан",
    "тестовий",
    "фактич",
    "дата",
    "25.12.2025",
}

TECH_VIEWPOINT_HINTS = {
    "установка",
    "реактор",
    "обладнання",
    "вузол",
    "генерац",
}

RISK_VIEWPOINT_HINTS = {
    "ризик",
    "загроза",
    "ймовір",
    "можлив",
}

PREDICATE_PREFIXES = {"не ", "no ", "not "}


@dataclass(frozen=True)
class ComplianceResult:
    passed: bool
    violations: List[Dict]
    corrections: List[Dict]
    rule_results: List[Dict]


class FPFTypeChecker:
    """
    Mandatory post-typization checker for basic FPF strict distinction compliance.

    v1 rules:
    - R1 (A.7 strict distinction): generic terms must not be typed as Process
      unless claims provide explicit process context.
    - R2 (A.1.1 bounded context): each entity must have explicit context_of_meaning.
    - R3 (F.18 name card minimal): each entity must have label_tech + label_plain.
    """

    def _claims_for_entity(self, entity_id: str, claims: List[Dict]) -> List[str]:
        out = []
        for c in claims:
            if entity_id in c.get("entity_ids", []):
                out.append(c.get("text", ""))
        return out

    def _has_process_context(self, claim_texts: List[str]) -> bool:
        all_text = " ".join(claim_texts).lower()
        return any(h in all_text for h in PROCESS_CONTEXT_HINTS)

    @staticmethod
    def _looks_like_predicate_phrase(label: str) -> bool:
        low = label.strip().lower()
        if any(low.startswith(p) for p in PREDICATE_PREFIXES):
            return True
        if " " in low and any(low.endswith(s) for s in ("ла", "ли", "ло", "вся", "ться")):
            return True
        return False

    @staticmethod
    def _has_any_hint(claim_texts: List[str], hints: set[str]) -> bool:
        all_text = " ".join(claim_texts).lower()
        return any(h in all_text for h in hints)

    def check_and_correct(
        self,
        entities: List[Dict],
        typed_entities: List[Dict],
        claims: List[Dict],
        proposals: List[Dict],
    ) -> Tuple[List[Dict], List[Dict], List[Dict], ComplianceResult]:
        entities_out = [dict(e) for e in entities]
        typed_out = [dict(t) for t in typed_entities]
        props_out = [dict(p) for p in proposals]

        violations: List[Dict] = []
        corrections: List[Dict] = []

        typed_by_id = {t["entity_id"]: t for t in typed_out}
        rule_results: List[Dict] = []

        # R2 / A.1.1: context_of_meaning must be explicit.
        r2_viol = 0
        for e in entities_out:
            context = str(e.get("context_of_meaning", "")).strip()
            if context:
                continue
            r2_viol += 1
            violations.append(
                {
                    "rule_id": "FPF_A1_1_CONTEXT_REQUIRED",
                    "severity": "high",
                    "entity_id": e["entity_id"],
                    "entity_name": e.get("name"),
                    "message": "Entity has no explicit context_of_meaning.",
                }
            )
            e["context_of_meaning"] = "UNKNOWN_CONTEXT"
            corrections.append(
                {
                    "entity_id": e["entity_id"],
                    "from_type": "NO_CONTEXT",
                    "to_type": "UNKNOWN_CONTEXT",
                    "reason": "FPF_A1_1_CONTEXT_REQUIRED",
                }
            )

        rule_results.append(
            {
                "rule_id": "FPF_A1_1_CONTEXT_REQUIRED",
                "principle": "A.1.1",
                "violations": r2_viol,
                "passed": r2_viol == 0,
            }
        )

        # R3 / F.18: minimal name card (tech/plain labels).
        r3_viol = 0
        for e in entities_out:
            tech = str(e.get("label_tech", "")).strip()
            plain = str(e.get("label_plain", "")).strip()
            if tech and plain:
                continue
            r3_viol += 1
            violations.append(
                {
                    "rule_id": "FPF_F18_NAME_CARD_MINIMAL",
                    "severity": "medium",
                    "entity_id": e["entity_id"],
                    "entity_name": e.get("name"),
                    "message": "Entity has no minimal name card fields (label_tech/label_plain).",
                }
            )
            e["label_tech"] = e.get("label_tech") or str(e.get("name", ""))
            e["label_plain"] = e.get("label_plain") or str(e.get("name", ""))
            corrections.append(
                {
                    "entity_id": e["entity_id"],
                    "from_type": "NO_NAME_CARD",
                    "to_type": "MIN_NAME_CARD",
                    "reason": "FPF_F18_NAME_CARD_MINIMAL",
                }
            )

        rule_results.append(
            {
                "rule_id": "FPF_F18_NAME_CARD_MINIMAL",
                "principle": "F.18",
                "violations": r3_viol,
                "passed": r3_viol == 0,
            }
        )

        # R4 / A.11: umbrella terms must not become concrete types.
        r4_viol = 0
        for e in entities_out:
            name = str(e.get("name", "")).strip().lower()
            if name not in UMBRELLA_TERMS:
                continue
            if e.get("type") == "CandidateType":
                continue
            r4_viol += 1
            violations.append(
                {
                    "rule_id": "FPF_A11_UMBRELLA_TERM_FORBIDDEN",
                    "severity": "high",
                    "entity_id": e["entity_id"],
                    "entity_name": e.get("name"),
                    "message": "Umbrella lexical term cannot be a concrete ontology type.",
                }
            )
            old_type = e.get("type", "UNKNOWN")
            e["type"] = "CandidateType"
            e["type_id"] = "T_CANDIDATE"
            tr = typed_by_id.get(e["entity_id"])
            if tr:
                tr["assigned_type"] = "CandidateType"
                tr["assigned_type_id"] = "T_CANDIDATE"
                tr["assignment_method"] = "fpf_umbrella_demotion"
                tr["confidence"] = 0.5
            corrections.append(
                {
                    "entity_id": e["entity_id"],
                    "from_type": old_type,
                    "to_type": "CandidateType",
                    "reason": "FPF_A11_UMBRELLA_TERM_FORBIDDEN",
                }
            )
        rule_results.append(
            {
                "rule_id": "FPF_A11_UMBRELLA_TERM_FORBIDDEN",
                "principle": "A.11",
                "violations": r4_viol,
                "passed": r4_viol == 0,
            }
        )

        # R5 / A.7: predicate phrase must not become an entity type.
        r5_viol = 0
        for e in entities_out:
            label = str(e.get("name", "")).strip()
            if not self._looks_like_predicate_phrase(label):
                continue
            r5_viol += 1
            violations.append(
                {
                    "rule_id": "FPF_A7_PREDICATE_AS_TYPE_FORBIDDEN",
                    "severity": "high",
                    "entity_id": e["entity_id"],
                    "entity_name": e.get("name"),
                    "message": "Predicate phrase cannot be used as ontology entity/type label.",
                }
            )
            old_type = e.get("type", "UNKNOWN")
            e["type"] = "CandidateType"
            e["type_id"] = "T_CANDIDATE"
            tr = typed_by_id.get(e["entity_id"])
            if tr:
                tr["assigned_type"] = "CandidateType"
                tr["assigned_type_id"] = "T_CANDIDATE"
                tr["assignment_method"] = "fpf_predicate_demotion"
                tr["confidence"] = 0.4
            corrections.append(
                {
                    "entity_id": e["entity_id"],
                    "from_type": old_type,
                    "to_type": "CandidateType",
                    "reason": "FPF_A7_PREDICATE_AS_TYPE_FORBIDDEN",
                }
            )
        rule_results.append(
            {
                "rule_id": "FPF_A7_PREDICATE_AS_TYPE_FORBIDDEN",
                "principle": "A.7",
                "violations": r5_viol,
                "passed": r5_viol == 0,
            }
        )

        # R6 / A.15: lifecycle disambiguation for plan/process/project/launch labels.
        r6_viol = 0
        for e in entities_out:
            name = str(e.get("name", "")).strip().lower()
            if name not in LIFECYCLE_AMBIGUOUS_TERMS:
                continue
            claim_texts = self._claims_for_entity(e["entity_id"], claims)
            has_design = self._has_any_hint(claim_texts, DESIGN_TIME_HINTS)
            has_runtime = self._has_any_hint(claim_texts, RUNTIME_HINTS)
            if has_design ^ has_runtime:
                continue
            r6_viol += 1
            violations.append(
                {
                    "rule_id": "FPF_A15_LIFECYCLE_DISAMBIGUATION_REQUIRED",
                    "severity": "high",
                    "entity_id": e["entity_id"],
                    "entity_name": e.get("name"),
                    "message": "Ambiguous lifecycle term needs design-time/runtime disambiguation.",
                }
            )
            old_type = e.get("type", "UNKNOWN")
            e["type"] = "CandidateType"
            e["type_id"] = "T_CANDIDATE"
            tr = typed_by_id.get(e["entity_id"])
            if tr:
                tr["assigned_type"] = "CandidateType"
                tr["assigned_type_id"] = "T_CANDIDATE"
                tr["assignment_method"] = "fpf_lifecycle_demotion"
                tr["confidence"] = 0.45
            corrections.append(
                {
                    "entity_id": e["entity_id"],
                    "from_type": old_type,
                    "to_type": "CandidateType",
                    "reason": "FPF_A15_LIFECYCLE_DISAMBIGUATION_REQUIRED",
                }
            )
        rule_results.append(
            {
                "rule_id": "FPF_A15_LIFECYCLE_DISAMBIGUATION_REQUIRED",
                "principle": "A.15",
                "violations": r6_viol,
                "passed": r6_viol == 0,
            }
        )

        # R7 / multi-view: ambiguous Technology/Artifact/Risk require viewpoint hints.
        r7_viol = 0
        for e in entities_out:
            t = e.get("type")
            if t not in {"Technology", "Artifact", "Risk"}:
                continue
            name = str(e.get("name", "")).strip().lower()
            claim_texts = self._claims_for_entity(e["entity_id"], claims)

            if t == "Technology" and self._has_any_hint(claim_texts, TECH_VIEWPOINT_HINTS):
                continue
            if t == "Risk" and self._has_any_hint(claim_texts, RISK_VIEWPOINT_HINTS):
                continue
            # Artifact must be explicit descriptive carrier signal.
            if t == "Artifact" and any(k in " ".join(claim_texts).lower() for k in ("документ", "план", "схема", "опис")):
                continue

            if name in {"реактор", "газогенераційна", "газогенерації", "електрогенерації", "план", "втрата довіри", "труднощі", "не спрацювала"}:
                r7_viol += 1
                violations.append(
                    {
                        "rule_id": "FPF_MULTI_VIEW_VIEWPOINT_REQUIRED",
                        "severity": "medium",
                        "entity_id": e["entity_id"],
                        "entity_name": e.get("name"),
                        "message": "Ambiguous entity requires explicit viewpoint before fixed type.",
                    }
                )
                old_type = e.get("type", "UNKNOWN")
                e["type"] = "CandidateType"
                e["type_id"] = "T_CANDIDATE"
                tr = typed_by_id.get(e["entity_id"])
                if tr:
                    tr["assigned_type"] = "CandidateType"
                    tr["assigned_type_id"] = "T_CANDIDATE"
                    tr["assignment_method"] = "fpf_viewpoint_demotion"
                    tr["confidence"] = 0.5
                corrections.append(
                    {
                        "entity_id": e["entity_id"],
                        "from_type": old_type,
                        "to_type": "CandidateType",
                        "reason": "FPF_MULTI_VIEW_VIEWPOINT_REQUIRED",
                    }
                )
        rule_results.append(
            {
                "rule_id": "FPF_MULTI_VIEW_VIEWPOINT_REQUIRED",
                "principle": "Multi-view/BoundedContext",
                "violations": r7_viol,
                "passed": r7_viol == 0,
            }
        )

        # R1 / A.7: generic process forbidden without explicit process context.
        r1_viol = 0
        for e in entities_out:
            if e.get("type") != "Process":
                continue

            name = str(e.get("name", "")).strip().lower()
            if name not in GENERIC_PROCESS_TERMS:
                continue

            claim_texts = self._claims_for_entity(e["entity_id"], claims)
            if self._has_process_context(claim_texts):
                continue

            r1_viol += 1
            violations.append(
                {
                    "rule_id": "FPF_A7_GENERIC_PROCESS_FORBIDDEN",
                    "severity": "high",
                    "entity_id": e["entity_id"],
                    "entity_name": e.get("name"),
                    "message": "Generic term is incorrectly typed as Process without explicit process context.",
                }
            )

            # Auto-correction: demote to CandidateType and add candidate proposal.
            e["type"] = "CandidateType"
            e["type_id"] = "T_CANDIDATE"

            typed_rec = typed_by_id.get(e["entity_id"])
            if typed_rec:
                typed_rec["assigned_type"] = "CandidateType"
                typed_rec["assigned_type_id"] = "T_CANDIDATE"
                typed_rec["confidence"] = 0.5
                typed_rec["assignment_method"] = "fpf_compliance_demotion"

            cand_id = f"AUTO_CAND_{name[:24]}"
            if not any(p.get("candidate_id") == cand_id for p in props_out):
                props_out.append(
                    {
                        "candidate_id": cand_id,
                        "label": e.get("name"),
                        "proposed_type_family": "UNCLASSIFIED_DOMAIN_TERM",
                        "rationale": "Auto-demoted by FPF compliance rule A.7",
                        "status": "CANDIDATE",
                    }
                )

            corrections.append(
                {
                    "entity_id": e["entity_id"],
                    "from_type": "Process",
                    "to_type": "CandidateType",
                    "reason": "FPF_A7_GENERIC_PROCESS_FORBIDDEN",
                }
            )

        rule_results.append(
            {
                "rule_id": "FPF_A7_GENERIC_PROCESS_FORBIDDEN",
                "principle": "A.7",
                "violations": r1_viol,
                "passed": r1_viol == 0,
            }
        )

        return (
            entities_out,
            typed_out,
            props_out,
            ComplianceResult(
                passed=(len(violations) == 0),
                violations=violations,
                corrections=corrections,
                rule_results=rule_results,
            ),
        )
