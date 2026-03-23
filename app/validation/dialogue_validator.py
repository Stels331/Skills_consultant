from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ValidationFinding:
    code: str
    severity: str
    message: str


@dataclass(frozen=True)
class ValidationDecision:
    status: str
    reason_codes: list[str]
    findings: list[ValidationFinding] = field(default_factory=list)
    next_tier: str | None = None
    final_outcome: str | None = None


class FPFResponseValidator:
    ALLOWED_ESCALATIONS = {
        "cheap": "balanced",
        "balanced": "premium",
    }

    def validate(
        self,
        *,
        answer_text: str,
        workspace_id: str,
        answer_payload: dict[str, Any],
        expected_workspace_id: str,
        tier: str,
        escalation_used: bool,
    ) -> ValidationDecision:
        findings: list[ValidationFinding] = []
        typed_claims = list(answer_payload.get("used_claims") or [])
        used_artifacts = list(answer_payload.get("used_artifacts") or [])
        open_unknowns = list(answer_payload.get("open_unknowns") or [])
        text = answer_text.lower()
        isolation = dict(answer_payload.get("workspace_isolation") or {})
        decision_assurance = dict(answer_payload.get("decision_assurance") or {})

        if workspace_id != expected_workspace_id:
            findings.append(
                ValidationFinding(
                    code="OUT_OF_WORKSPACE_LEAKAGE",
                    severity="block",
                    message="Answer payload leaks data outside active workspace",
                )
            )

        if isolation.get("status") == "block":
            reason_codes = list(isolation.get("reason_codes") or [])
            findings.append(
                ValidationFinding(
                    code="WORKSPACE_CONTAMINATION_BLOCKED",
                    severity="block",
                    message=f"Isolation guard blocked payload: {', '.join(reason_codes) or 'mixed workspace references'}",
                )
            )

        if not typed_claims and not open_unknowns:
            findings.append(
                ValidationFinding(
                    code="UNSUPPORTED_CONCLUSION",
                    severity="block",
                    message="Answer has no grounded claims and no uncertainty routing",
                )
            )

        if typed_claims and not used_artifacts:
            findings.append(
                ValidationFinding(
                    code="MISSING_CITATION",
                    severity="degrade",
                    message="Answer uses claims without artifact references",
                )
            )

        if decision_assurance:
            assurance_status = str(decision_assurance.get("assurance_status") or "").lower()
            review_required = bool(decision_assurance.get("review_required"))
            if assurance_status == "block":
                findings.append(
                    ValidationFinding(
                        code="DECISION_ASSURANCE_BLOCK",
                        severity="block",
                        message="Decision assurance floor was violated",
                    )
                )
            elif assurance_status == "degrade" or review_required:
                findings.append(
                    ValidationFinding(
                        code="DECISION_ASSURANCE_DEGRADED",
                        severity="degrade",
                        message="Decision assurance requires review or stale evidence refresh",
                    )
                )

        if ("definitely" in text or "guaranteed" in text or "точно" in text) and open_unknowns:
            findings.append(
                ValidationFinding(
                    code="UNCERTAINTY_OMISSION",
                    severity="degrade",
                    message="Answer overstates certainty while unknowns remain open",
                )
            )

        contamination_markers = {"bankruptcy", "patient", "tumor", "spacecraft"}
        claim_text = " ".join(str(claim.get("statement") or "") for claim in typed_claims).lower()
        if any(marker in text and marker not in claim_text for marker in contamination_markers):
            findings.append(
                ValidationFinding(
                    code="ANTI_CROSS_CASE_CONTAMINATION",
                    severity="block",
                    message="Answer introduces alien domain concepts not grounded in the case",
                )
            )

        if any(item.severity == "block" for item in findings):
            next_tier = None
            if not escalation_used and tier in self.ALLOWED_ESCALATIONS:
                next_tier = self.ALLOWED_ESCALATIONS[tier]
            return ValidationDecision(
                status="block",
                reason_codes=[item.code for item in findings],
                findings=findings,
                next_tier=next_tier,
                final_outcome="block" if next_tier is None else None,
            )

        if findings:
            return ValidationDecision(
                status="degrade",
                reason_codes=[item.code for item in findings],
                findings=findings,
                final_outcome="degrade",
            )

        return ValidationDecision(
            status="pass",
            reason_codes=[],
            findings=[],
            final_outcome="pass",
        )
