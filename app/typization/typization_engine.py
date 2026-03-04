from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set

from app.typization.candidate_normalizer import CandidateNormalizer
from app.typization.fpf_type_checker import FPFTypeChecker
from app.typization.type_registry import TypeRegistry


FACT_PATTERN = re.compile(r"(\d|\bкВт\b|\bм куб\b|\b\d{2}\.\d{2}\.\d{4}\b)", re.IGNORECASE)
WORD_PATTERN = re.compile(r"[A-Za-zА-Яа-яІіЇїЄєҐґ0-9_\-]{3,}")


@dataclass(frozen=True)
class TypizationResult:
    entities_count: int
    claims_count: int
    proposals_count: int


class TypizationEngine:
    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.registry = TypeRegistry(self.project_root)
        self.fpf_checker = FPFTypeChecker()
        self.candidate_normalizer = CandidateNormalizer()

    @staticmethod
    def _read_text(path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="ignore")

    @staticmethod
    def _atomic_statements(text: str) -> List[str]:
        out: List[str] = []
        for raw in text.splitlines():
            line = raw.strip(" \t•-")
            if not line:
                continue
            if line.startswith("http://") or line.startswith("https://"):
                continue
            out.append(line)
        return out

    @staticmethod
    def _claim_kind(statement: str) -> str:
        return "FACT" if FACT_PATTERN.search(statement) else "INTERPRETATION"

    def _match_known_types(self, statement: str) -> List[Dict[str, str]]:
        matches: List[Dict[str, str]] = []
        low = statement.lower()
        for t in self.registry.known_types():
            t_name = t["name"]
            for alias in t.get("aliases", []):
                if alias.lower() in low:
                    matches.append({"type_id": t["type_id"], "type": t_name, "alias": alias})
                    break
        return matches

    def _propose_candidates(self, statement: str, known_aliases: Set[str]) -> List[Dict[str, str]]:
        proposals = []
        words = WORD_PATTERN.findall(statement)
        for w in words:
            wl = w.lower()
            if wl in known_aliases:
                continue
            if len(wl) < 6:
                continue
            if wl.isdigit():
                continue
            candidate_id = f"CAND_{wl[:24]}"
            proposals.append(
                {
                    "candidate_id": candidate_id,
                    "label": w,
                    "proposed_type_family": "UNCLASSIFIED_DOMAIN_TERM",
                    "rationale": "Unmatched frequent term in parsed claim",
                    "status": "CANDIDATE",
                }
            )
        uniq = {}
        for p in proposals:
            uniq[p["candidate_id"]] = p
        return list(uniq.values())

    def run_for_workspace(self, workspace_id: str) -> TypizationResult:
        ws = self.project_root / "cases" / workspace_id
        parsed_dir = ws / "parsed"
        extracted_dir = ws / "extracted"
        analysis_dir = ws / "analysis"
        reports_dir = ws / "reports"
        state_dir = ws / "state"

        extracted_dir.mkdir(parents=True, exist_ok=True)
        analysis_dir.mkdir(parents=True, exist_ok=True)
        reports_dir.mkdir(parents=True, exist_ok=True)

        parsed_files = sorted(parsed_dir.glob("*.txt"))
        if not parsed_files:
            raise FileNotFoundError(f"No parsed .txt files found in {parsed_dir}")

        all_statements: List[str] = []
        for p in parsed_files:
            all_statements.extend(self._atomic_statements(self._read_text(p)))

        entities = []
        claims = []
        relations = []
        typed_entities = []
        proposals = []

        known_aliases = {
            alias.lower()
            for t in self.registry.known_types()
            for alias in t.get("aliases", [])
        }

        entity_idx = 1
        claim_idx = 1

        for st in all_statements:
            kind = self._claim_kind(st)
            matched = self._match_known_types(st)
            entity_ids = []

            for m in matched:
                eid = f"E{entity_idx:04d}"
                entity_idx += 1
                entity = {
                    "entity_id": eid,
                    "name": m["alias"],
                    "type": m["type"],
                    "type_id": m["type_id"],
                    "aliases": [m["alias"]],
                    "context_of_meaning": "CASE_GLOBAL",
                    "label_tech": m["alias"],
                    "label_plain": m["alias"],
                }
                entities.append(entity)
                typed_entities.append(
                    {
                        "entity_id": eid,
                        "assigned_type": m["type"],
                        "assigned_type_id": m["type_id"],
                        "confidence": 0.75,
                        "assignment_method": "keyword_alias_match",
                    }
                )
                entity_ids.append(eid)

            cid = f"C{claim_idx:04d}"
            claim_idx += 1
            claims.append(
                {
                    "claim_id": cid,
                    "text": st,
                    "kind": kind,
                    "entity_ids": entity_ids,
                }
            )

            if not matched:
                for p in self._propose_candidates(st, known_aliases):
                    proposals.append(p)

        # de-duplicate entities by (name, type)
        seen = set()
        dedup_entities = []
        entity_id_map: Dict[str, str] = {}
        for e in entities:
            key = (e["name"].lower(), e["type_id"])
            if key in seen:
                continue
            seen.add(key)
            dedup_entities.append(e)
            entity_id_map[e["entity_id"]] = e["entity_id"]

        payload_claims = {
            "workspace_id": workspace_id,
            "claims": claims,
        }
        payload_relations = {
            "workspace_id": workspace_id,
            "relations": relations,
        }

        uniq_props = {}
        for p in proposals:
            uniq_props[p["candidate_id"]] = p
        payload_proposals = {
            "workspace_id": workspace_id,
            "type_proposals": list(uniq_props.values()),
        }

        # Mandatory FPF compliance cycle for type assignments.
        dedup_entities, typed_entities, corrected_proposals, compliance = (
            self.fpf_checker.check_and_correct(
                entities=dedup_entities,
                typed_entities=typed_entities,
                claims=claims,
                proposals=payload_proposals["type_proposals"],
            )
        )
        payload_proposals["type_proposals"] = corrected_proposals
        payload_entities = {
            "workspace_id": workspace_id,
            "entities": dedup_entities,
        }
        payload_typed = {
            "workspace_id": workspace_id,
            "typed_entities": typed_entities,
        }

        type_counter: Dict[str, int] = {}
        for e in dedup_entities:
            t = e["type"]
            type_counter[t] = type_counter.get(t, 0) + 1

        payload_case_types = {
            "workspace_id": workspace_id,
            "summary": {
                "claims_total": len(claims),
                "entities_total": len(dedup_entities),
                "typed_entities_total": len(typed_entities),
                "type_proposals_total": len(payload_proposals["type_proposals"]),
            },
            "type_distribution": type_counter,
            "entities": dedup_entities,
            "type_proposals": payload_proposals["type_proposals"],
        }
        payload_fpf_compliance = {
            "workspace_id": workspace_id,
            "passed": compliance.passed,
            "violations": compliance.violations,
            "corrections": compliance.corrections,
            "rule_results": compliance.rule_results,
        }
        candidate_normalization = self.candidate_normalizer.normalize(
            proposals=payload_proposals["type_proposals"],
            claims=claims,
            known_types=self.registry.known_types(),
        )
        payload_candidate_normalization = {
            "workspace_id": workspace_id,
            **candidate_normalization,
        }

        status_by_candidate: Dict[str, str] = {}
        for x in payload_candidate_normalization["promote_to_known"]:
            status_by_candidate[x["candidate_id"]] = "PROMOTE_TO_KNOWN"
        for x in payload_candidate_normalization["map_to_existing"]:
            status_by_candidate[x["candidate_id"]] = "MAP_TO_EXISTING"
        for x in payload_candidate_normalization["deprecate"]:
            status_by_candidate[x["candidate_id"]] = "DEPRECATE"
        for x in payload_candidate_normalization["keep_candidate"]:
            status_by_candidate[x["candidate_id"]] = "CANDIDATE_PENDING"

        for p in payload_proposals["type_proposals"]:
            cid = p.get("candidate_id")
            p["normalization_status"] = status_by_candidate.get(cid, "CANDIDATE_PENDING")

        (extracted_dir / "entities.json").write_text(
            json.dumps(payload_entities, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (extracted_dir / "claims.json").write_text(
            json.dumps(payload_claims, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (extracted_dir / "relations.json").write_text(
            json.dumps(payload_relations, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (analysis_dir / "typed_entities.json").write_text(
            json.dumps(payload_typed, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (analysis_dir / "type_proposals.json").write_text(
            json.dumps(payload_proposals, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (analysis_dir / "case_types_report.json").write_text(
            json.dumps(payload_case_types, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (analysis_dir / "fpf_type_compliance.json").write_text(
            json.dumps(payload_fpf_compliance, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (analysis_dir / "candidate_normalization.json").write_text(
            json.dumps(payload_candidate_normalization, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        md_lines = [
            f"# Case Types Report — {workspace_id}",
            "",
            "## Summary",
            f"- claims_total: {payload_case_types['summary']['claims_total']}",
            f"- entities_total: {payload_case_types['summary']['entities_total']}",
            f"- typed_entities_total: {payload_case_types['summary']['typed_entities_total']}",
            f"- type_proposals_total: {payload_case_types['summary']['type_proposals_total']}",
            "",
            "## Type distribution",
        ]
        for t_name, count in sorted(type_counter.items(), key=lambda x: (-x[1], x[0])):
            md_lines.append(f"- {t_name}: {count}")

        md_lines.extend(["", "## Collected entities"])
        for e in dedup_entities:
            md_lines.append(
                f"- {e['entity_id']} | {e['name']} | {e['type']} ({e['type_id']})"
            )

        pending_candidates = [
            p for p in payload_proposals["type_proposals"]
            if p.get("normalization_status") == "CANDIDATE_PENDING"
        ]
        md_lines.extend(["", "## Candidate types (pending only)"])
        for p in pending_candidates:
            md_lines.append(
                f"- {p['candidate_id']} | {p['label']} | {p['status']} | {p.get('normalization_status')}"
            )

        (reports_dir / "case_types_report.md").write_text(
            "\n".join(md_lines) + "\n",
            encoding="utf-8",
        )

        compliance_lines = [
            f"# FPF Type Compliance Report — {workspace_id}",
            "",
            f"- passed: {str(payload_fpf_compliance['passed']).lower()}",
            f"- violations: {len(payload_fpf_compliance['violations'])}",
            f"- corrections: {len(payload_fpf_compliance['corrections'])}",
            "",
            "## Rule coverage",
        ]
        for rr in payload_fpf_compliance.get("rule_results", []):
            compliance_lines.append(
                f"- {rr['rule_id']} ({rr['principle']}): passed={str(rr['passed']).lower()}, violations={rr['violations']}"
            )

        compliance_lines.extend([
            "",
            "## Violations",
        ])
        if not payload_fpf_compliance["violations"]:
            compliance_lines.append("- none")
        else:
            for v in payload_fpf_compliance["violations"]:
                compliance_lines.append(
                    f"- {v['rule_id']} | {v['entity_id']} | {v['entity_name']} | {v['message']}"
                )

        compliance_lines.extend(["", "## Corrections"])
        if not payload_fpf_compliance["corrections"]:
            compliance_lines.append("- none")
        else:
            for c in payload_fpf_compliance["corrections"]:
                compliance_lines.append(
                    f"- {c['entity_id']} | {c['from_type']} -> {c['to_type']} | {c['reason']}"
                )

        (reports_dir / "fpf_type_compliance.md").write_text(
            "\n".join(compliance_lines) + "\n",
            encoding="utf-8",
        )

        norm_lines = [
            f"# Candidate Normalization Report — {workspace_id}",
            "",
            "## Summary",
            f"- promote_to_known: {payload_candidate_normalization['summary']['promote_to_known']}",
            f"- map_to_existing: {payload_candidate_normalization['summary']['map_to_existing']}",
            f"- deprecate: {payload_candidate_normalization['summary']['deprecate']}",
            f"- keep_candidate: {payload_candidate_normalization['summary']['keep_candidate']}",
            "",
            "## Promote To Known Types",
        ]
        if not payload_candidate_normalization["promote_to_known"]:
            norm_lines.append("- none")
        else:
            for x in payload_candidate_normalization["promote_to_known"]:
                norm_lines.append(
                    f"- {x['candidate_id']} | {x['label']} | {x['suggested_type']} ({x['suggested_type_id']}) | {x['reason']}"
                )

        norm_lines.extend(["", "## Map To Existing Types"])
        if not payload_candidate_normalization["map_to_existing"]:
            norm_lines.append("- none")
        else:
            for x in payload_candidate_normalization["map_to_existing"]:
                norm_lines.append(
                    f"- {x['candidate_id']} | {x['label']} -> {x['target_type']} ({x['target_type_id']}) | {x['reason']}"
                )

        norm_lines.extend(["", "## Deprecate Candidates"])
        if not payload_candidate_normalization["deprecate"]:
            norm_lines.append("- none")
        else:
            for x in payload_candidate_normalization["deprecate"]:
                norm_lines.append(
                    f"- {x['candidate_id']} | {x['label']} | {x['reason']}"
                )

        norm_lines.extend(["", "## Keep As Candidate"])
        if not payload_candidate_normalization["keep_candidate"]:
            norm_lines.append("- none")
        else:
            for x in payload_candidate_normalization["keep_candidate"][:30]:
                norm_lines.append(
                    f"- {x['candidate_id']} | {x['label']} | {x['reason']}"
                )

        (reports_dir / "candidate_normalization.md").write_text(
            "\n".join(norm_lines) + "\n",
            encoding="utf-8",
        )

        for p in payload_proposals["type_proposals"]:
            self.registry.add_candidate_type(p)

        changelog = state_dir / "version_changelog.json"
        if changelog.exists():
            data = json.loads(changelog.read_text(encoding="utf-8"))
            data.setdefault("events", []).append(
                {
                    "event_type": "TYPIZATION_COMPLETED",
                    "timestamp": "2026-02-28T00:00:00Z",
                    "details": {
                        "claims": len(claims),
                        "entities": len(dedup_entities),
                        "proposals": len(payload_proposals["type_proposals"]),
                        "artifacts": [
                            "extracted/entities.json",
                            "extracted/claims.json",
                            "extracted/relations.json",
                            "analysis/typed_entities.json",
                            "analysis/type_proposals.json",
                            "analysis/case_types_report.json",
                            "analysis/fpf_type_compliance.json",
                            "analysis/candidate_normalization.json",
                            "reports/case_types_report.md",
                            "reports/fpf_type_compliance.md",
                            "reports/candidate_normalization.md",
                        ],
                        "fpf_type_compliance_passed": compliance.passed,
                    },
                }
            )
            changelog.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        return TypizationResult(
            entities_count=len(dedup_entities),
            claims_count=len(claims),
            proposals_count=len(payload_proposals["type_proposals"]),
        )
