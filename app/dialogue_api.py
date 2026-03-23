from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import re
import time
from urllib.parse import parse_qs

from app.canonical_db.claim_graph import ClaimGraphService
from app.canonical_db.decision_assurance import (
    DecisionAssuranceEngine,
    DecisionAssuranceScheduler,
    DecisionOutcomeResolver,
    DecisionWaiverService,
    assurance_payload,
)
from app.canonical_db.decision_retrieval import (
    DecisionAnswerComposer,
    DecisionPatternRetrievalService,
    DecisionReusePolicy,
    DecisionReviewWorkflow,
)
from app.canonical_db.dialogue_backend import (
    BM25SectionIndex,
    DialogueOrchestrator,
    DialogueSessionService,
    EmbeddingLifecycleService,
    GraphRetrievalService,
    GroundingBundleBuilder,
    LLMProviderAdapter,
    PromptBuilder,
    QuestionRouter,
    RoutingPolicy,
)
from app.canonical_db.domain import Artifact, DialogueSession, GovernanceEvent, User
from app.canonical_db.model_updates import (
    ClarificationEngine,
    InputAcceptanceCheck,
    ModelUpdateEngine,
    ReentryPlanner,
    ReentryWorker,
    TypedInputClassifier,
    build_diff_panel,
)
from app.canonical_db.projections import MaterializedArtifactIndex, ProjectionRegistry, ProjectionService
from app.canonical_db.repositories import SqliteDialogueSessionRepository
from app.canonical_db.runtime import repository_bundle
from app.observability.runtime_monitor import RUNTIME_MONITOR
from app.validation.dialogue_validator import FPFResponseValidator
from app.validation.workspace_isolation import (
    WorkspaceIsolationValidator,
    WorkspaceRuntimeContext,
    WorkspaceRuntimeState,
)


_RUNTIME_STATE = WorkspaceRuntimeState()


def _json_response(start_response, status_code: str, payload: dict) -> list[bytes]:
    start_response(status_code, [("Content-Type", "application/json; charset=utf-8")])
    return [json.dumps(payload, ensure_ascii=False).encode("utf-8")]


def _html_response(start_response, html: str) -> list[bytes]:
    start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
    return [html.encode("utf-8")]


def _request_json(environ) -> dict:
    length = int(environ.get("CONTENT_LENGTH") or "0")
    raw = environ["wsgi.input"].read(length) if length > 0 else b"{}"
    return json.loads(raw.decode("utf-8"))


def _workspace_title(bundle: dict[str, object], workspace_id: str) -> str:
    workspace = bundle["workspaces"].get(workspace_id)
    return workspace.title if workspace else workspace_id


def _organization_name(bundle: dict[str, object], organization_id: str) -> str:
    organization = bundle["organizations"].get(organization_id)
    return organization.name if organization else organization_id


def _provider_stub(prompt: str, model_key: str) -> dict[str, object]:
    first_claim_line = next(
        (line for line in prompt.splitlines() if line.startswith("- [")),
        "No grounded claim was available.",
    )
    return {
        "text": f"Grounded answer based on {first_claim_line}",
        "usage": {"estimated_cost": 1.0},
        "model_key": model_key,
    }


def _tokenize_text(text: str) -> list[str]:
    return re.findall(r"[a-zа-я0-9]+", text.lower(), flags=re.IGNORECASE)


def render_answer_card(answer: dict) -> str:
    status = str(answer.get("validation_status") or "pass")
    explanation = ""
    if status == "block":
        explanation = f"<p class='muted'>Blocked. {answer.get('safe_fallback') or 'Use clarification path.'}</p>"
    elif status == "degrade":
        explanation = f"<p class='muted'>Warning. {'; '.join(answer.get('reason_codes') or ['limited confidence'])}</p>"
    return (
        f"<div class='card {status}'>"
        f"<h3>{'Safe Fallback' if status == 'block' else 'Grounded Answer'}</h3>"
        f"<p>{answer.get('text') or answer.get('safe_fallback') or ''}</p>"
        f"<p class='muted'>confidence={answer.get('confidence_score')} | epistemic_status={answer.get('epistemic_status')}</p>"
        f"{explanation}"
        "</div>"
    )


class DialogueApiService:
    def __init__(self, project_root: Path):
        self._project_root = project_root
        self._bundle = repository_bundle()
        self._dialogue_sessions = DialogueSessionService(
            sessions=SqliteDialogueSessionRepository(self._bundle["factory"]),
            messages=self._bundle["dialogue_messages"],
        )
        self._router = QuestionRouter()
        self._retrieval = GraphRetrievalService(self._bundle["claims"])
        self._bm25 = BM25SectionIndex(self._bundle["retrieval_chunks"])
        self._grounding = GroundingBundleBuilder()
        self._prompts = PromptBuilder()
        self._quota = __import__("app.canonical_db.dialogue_backend", fromlist=["QuotaEnforcementService"]).QuotaEnforcementService(
            self._bundle["quota_ledger"]
        )
        self._provider = LLMProviderAdapter(mode="direct", direct_callable=_provider_stub)
        self._policy = RoutingPolicy()
        self._validator = FPFResponseValidator()
        self._isolation = WorkspaceIsolationValidator()
        self._runtime = _RUNTIME_STATE
        self._projection_registry = ProjectionRegistry()
        self._projection_service = ProjectionService(
            self._bundle["claims"],
            self._bundle["projection_snapshots"],
            self._projection_registry,
        )
        self._clarifications = ClarificationEngine(self._bundle["question_queue"])
        self._classifier = TypedInputClassifier()
        self._input_acceptance = InputAcceptanceCheck(self._bundle["claims"])
        self._update_engine = ModelUpdateEngine(
            self._bundle["claims"],
            self._bundle["governance"],
            self._projection_service,
        )
        self._reentry_planner = ReentryPlanner(
            self._projection_registry,
            MaterializedArtifactIndex(self._projection_registry, self._bundle["materialized_artifact_index"]),
            self._bundle["projection_snapshots"],
        )
        self._reentry_worker = ReentryWorker(
            self._bundle["reentry_jobs"],
            self._bundle["workspaces"],
            self._projection_service,
            self._bundle["governance"],
        )
        self._decision_assurance = DecisionAssuranceEngine(
            self._bundle["decision_records"],
            self._bundle["decision_evidence_links"],
            self._bundle["decision_outcomes"],
            self._bundle["decision_assurance_snapshots"],
            self._bundle["decision_waivers"],
            self._bundle["decision_reviews"],
            self._bundle["governance"],
        )
        self._decision_outcome_resolver = DecisionOutcomeResolver(
            self._bundle["decision_outcomes"],
            self._bundle["governance"],
        )
        self._decision_waivers = DecisionWaiverService(
            self._bundle["decision_waivers"],
            self._bundle["governance"],
        )
        self._decision_assurance_scheduler = DecisionAssuranceScheduler(
            self._bundle["decision_records"],
            self._bundle["decision_assurance_snapshots"],
            self._decision_assurance,
        )
        self._decision_reuse_policy = DecisionReusePolicy()
        self._decision_pattern_retrieval = DecisionPatternRetrievalService(
            self._bundle["factory"],
            self._bundle["decision_records"],
            self._bundle["decision_comparisons"],
            self._bundle["decision_assurance_snapshots"],
            self._bundle["decision_outcomes"],
            self._bundle["governance"],
        )
        self._decision_answer_composer = DecisionAnswerComposer(
            self._bundle["decision_records"],
            self._bundle["decision_comparisons"],
            self._bundle["decision_assurance_snapshots"],
        )
        self._decision_review_workflow = DecisionReviewWorkflow(
            self._bundle["decision_records"],
            self._bundle["decision_reviews"],
            self._bundle["governance"],
        )
        self._orchestrator = DialogueOrchestrator(
            dialogue_sessions=self._dialogue_sessions,
            router=self._router,
            retrieval=self._retrieval,
            bm25=self._bm25,
            grounding=self._grounding,
            prompts=self._prompts,
            quota=self._quota,
            provider=self._provider,
            policy=self._policy,
        )

    def _legacy_evidence_claims(self, workspace_id: str) -> list[dict[str, object]]:
        graph_path = self._project_root / "cases" / workspace_id / "evidence" / "evidence_graph.json"
        if not graph_path.exists():
            return []
        payload = json.loads(graph_path.read_text(encoding="utf-8"))
        claims = payload.get("claims", [])
        normalized: list[dict[str, object]] = []
        for index, item in enumerate(claims, start=1):
            statement = str(item.get("claim_text") or "").strip()
            if not statement:
                continue
            normalized.append(
                {
                    "id": str(item.get("claim_id") or f"{workspace_id}:legacy:{index}"),
                    "claim_key": f"legacy_claim_{index:03d}",
                    "claim_type": str(item.get("claim_class") or "observed"),
                    "statement": statement,
                    "confidence_score": 0.5,
                    "artifact_path": str(item.get("artifact_path") or "evidence/evidence_graph.json"),
                }
            )
        return normalized

    def _legacy_evidence_match(self, workspace_id: str, question: str, limit: int = 6) -> list[dict[str, object]]:
        claims = self._legacy_evidence_claims(workspace_id)
        if not claims:
            return []
        query_tokens = set(_tokenize_text(question))
        scored: list[tuple[int, dict[str, object]]] = []
        for item in claims:
            score = len(query_tokens & set(_tokenize_text(str(item["statement"]))))
            scored.append((score, item))
        scored.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
        relevant = [item for score, item in scored if score > 0][:limit]
        return relevant if relevant else claims[:limit]

    def _latest_decision_record(self, workspace_id: str):
        records = self._bundle["decision_records"].list_for_workspace(workspace_id)
        return records[-1] if records else None

    def _effective_reuse_mode(self, *, organization_id: str, workspace_id: str, requested_mode: str | None = None) -> str:
        organization = self._bundle["organizations"].get(organization_id)
        workspace = self._bundle["workspaces"].get(workspace_id)
        return self._decision_reuse_policy.resolve_mode(
            organization_metadata=getattr(organization, "metadata", {}) or {},
            workspace_metadata=getattr(workspace, "metadata", {}) or {},
            requested_mode=requested_mode,
        )

    def _build_context(
        self,
        *,
        organization_id: str,
        workspace_id: str,
        session_id: str | None,
        user_id: str | None,
    ) -> WorkspaceRuntimeContext:
        return WorkspaceRuntimeContext(
            organization_id=organization_id,
            workspace_id=workspace_id,
            session_id=session_id,
            user_id=user_id,
            workspace_version_id=self._workspace_version_id(workspace_id),
            graph_version=self._graph_version(workspace_id),
        )

    def _append_governance_event(
        self,
        *,
        organization_id: str,
        workspace_id: str,
        event_type: str,
        payload: dict[str, object],
        actor_type: str = "system",
        actor_id: str = "dialogue_api",
    ) -> GovernanceEvent:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        event = GovernanceEvent(
            id=f"{event_type}:{workspace_id}:{timestamp}",
            organization_id=organization_id,
            workspace_id=workspace_id,
            event_type=event_type,
            payload=payload,
            actor_type=actor_type,
            actor_id=actor_id,
        )
        self._bundle["governance"].append(event)
        return event

    def _ensure_session(
        self,
        *,
        session_id: str,
        organization_id: str,
        workspace_id: str,
        user_id: str,
        workspace_version_id: str,
    ) -> None:
        if self._bundle["users"].get(user_id) is None:
            self._bundle["users"].upsert(
                User(
                    id=user_id,
                    email=f"{user_id}@example.local",
                    password_hash="not-used",
                    display_name=user_id,
                )
            )
        if self._bundle["dialogue_sessions"].get(session_id) is None:
            try:
                self._dialogue_sessions.create_session(
                    DialogueSession(
                        id=session_id,
                        organization_id=organization_id,
                        workspace_id=workspace_id,
                        created_by_user_id=user_id,
                        status="active",
                        active_workspace_version_id=workspace_version_id,
                        title=f"Dialogue {workspace_id}",
                    )
                )
            except sqlite3.IntegrityError:
                # Keep the UI usable even if the DB already contains a partially-created actor/session edge.
                pass

    def _workspace_version_id(self, workspace_id: str) -> str:
        workspace = self._bundle["workspaces"].get(workspace_id)
        if workspace is None:
            raise KeyError(workspace_id)
        version = self._bundle["workspaces"].get_version(workspace_id, workspace.active_model_version)
        return version.id if version else f"{workspace_id}:v{workspace.active_model_version}"

    def _graph_version(self, workspace_id: str) -> str:
        claims = self._bundle["claims"].list_for_workspace(workspace_id)
        return f"claims:{len(claims)}"

    def ask(self, payload: dict) -> dict:
        timer = RUNTIME_MONITOR.start_timer("dialogue_request")
        started_at = time.monotonic()
        workspace_id = str(payload["workspace_id"])
        organization_id = str(payload["organization_id"])
        session_id = str(payload["session_id"])
        user_id = str(payload["user_id"])
        question = str(payload["question"])
        budget_profile = str(payload.get("budget_profile") or "standard")
        correlation_id = str(payload.get("correlation_id") or f"corr:{workspace_id}:{session_id}:{abs(hash(question)) % 100000}")
        context = self._build_context(
            organization_id=organization_id,
            workspace_id=workspace_id,
            session_id=session_id,
            user_id=user_id,
        )
        bind_result = self._runtime.bind(context)
        workspace_version_id = context.workspace_version_id
        graph_version = context.graph_version
        workspace = self._bundle["workspaces"].get(workspace_id)
        if bind_result.reset_applied:
            self._append_governance_event(
                organization_id=organization_id,
                workspace_id=workspace_id,
                event_type="workspace_runtime_reset",
                payload={
                    "previous_namespace": bind_result.previous_namespace,
                    "active_namespace": bind_result.active_namespace,
                    "cleared_buffers": bind_result.cleared_buffers,
                },
            )
        request_event = self._append_governance_event(
            organization_id=organization_id,
            workspace_id=workspace_id,
            event_type="dialogue_request_received",
            payload={
                "correlation_id": correlation_id,
                "session_id": session_id,
                "workspace_version_id": workspace_version_id,
            },
            actor_type="user",
            actor_id=user_id,
        )
        self._ensure_session(
            session_id=session_id,
            organization_id=organization_id,
            workspace_id=workspace_id,
            user_id=user_id,
            workspace_version_id=workspace_version_id,
        )
        try:
            bundle, provider_response = self._orchestrator.answer(
                organization_id=organization_id,
                workspace_id=workspace_id,
                workspace_version_id=workspace_version_id,
                graph_version=graph_version,
                user_id=user_id,
                session_id=session_id,
                question=question,
                budget_profile=budget_profile,
            )
        except PermissionError as exc:
            elapsed_ms = RUNTIME_MONITOR.stop_timer(timer)
            reason_code = str(exc) or "insufficient_modeled_evidence"
            legacy_claims = self._legacy_evidence_match(workspace_id, question)
            fallback_text = "Недостаточно смоделированных evidence/claims для grounded ответа. Открой отчеты кейса или задай уточняющий вопрос по конкретному факту, ограничению или фрагменту отчета."
            if legacy_claims:
                preview = " ".join(
                    f"{idx}. {item['statement']}"
                    for idx, item in enumerate(legacy_claims[:3], start=1)
                )
                fallback_text = f"Canonical claims пусты, но в evidence_graph есть релевантные фрагменты: {preview}"
            validator_event = self._append_governance_event(
                organization_id=organization_id,
                workspace_id=workspace_id,
                event_type="validator_completed",
                payload={
                    "correlation_id": correlation_id,
                    "validation_status": "block",
                    "reason_codes": [reason_code],
                },
            )
            RUNTIME_MONITOR.increment("dialogue_requests_total")
            RUNTIME_MONITOR.increment(f"validation_{'degrade' if legacy_claims else 'block'}_total")
            RUNTIME_MONITOR.increment("blocked_answers_total" if legacy_claims else "provider_errors_total")
            RUNTIME_MONITOR.log(
                {
                    "event": "dialogue_request",
                    "correlation_id": correlation_id,
                    "workspace_id": workspace_id,
                    "provider": "not_called",
                    "validation_status": "degrade" if legacy_claims else "block",
                    "latency_ms": round((time.monotonic() - started_at) * 1000.0, 3),
                    "reason_codes": [reason_code],
                }
            )
            return {
                "contract_version": "2026-03-23",
                "workspace_id": workspace_id,
                "workspace_version_id": workspace_version_id,
                "graph_version": graph_version,
                "session_id": session_id,
                "answer": {
                    "text": fallback_text,
                    "epistemic_status": "degraded" if legacy_claims else "blocked",
                    "confidence_score": 0.35 if legacy_claims else 0.0,
                    "validation_status": "degrade" if legacy_claims else "block",
                    "reason_codes": [reason_code],
                    "safe_fallback": fallback_text,
                    "used_claims": legacy_claims,
                    "used_artifacts": [
                        {
                            "chunk_id": item["id"],
                            "section_title": item["artifact_path"],
                            "workspace_id": workspace_id,
                        }
                        for item in legacy_claims
                    ],
                    "open_unknowns": [reason_code],
                    "decision_assurance": {},
                    "decision_contract": {},
                },
                "validation": {
                    "status": "degrade" if legacy_claims else "block",
                    "reason_codes": [reason_code],
                    "confidence_score": 0.35 if legacy_claims else 0.0,
                    "epistemic_status": "degraded" if legacy_claims else "blocked",
                },
                "decision": {},
                "runtime": {
                    "correlation_id": correlation_id,
                    "namespace_key": context.namespace_key,
                    "prompt_cache_key": None,
                    "retrieval_cache_key": None,
                    "reset_applied": bind_result.reset_applied,
                    "latency_ms": elapsed_ms,
                },
                "governance": {
                    "events": [
                        {
                            "event_type": "dialogue_answer_validated",
                            "correlation_id": correlation_id,
                            "routing_outcome": "legacy_evidence_fallback" if legacy_claims else "blocked_pre_answer",
                            "validation_status": "degrade" if legacy_claims else "block",
                            "isolation_status": "not_evaluated",
                        }
                    ],
                    "event_refs": [request_event.id, validator_event.id],
                    "lineage": {
                        "used_claim_ids": [item["id"] for item in legacy_claims],
                        "used_artifact_refs": [item["artifact_path"] for item in legacy_claims],
                    },
                },
            }
        provider_diagnostics = self._provider.diagnostics()
        provider_event = self._append_governance_event(
            organization_id=organization_id,
            workspace_id=workspace_id,
            event_type="provider_call_completed",
            payload={
                "correlation_id": correlation_id,
                "provider": provider_response.provider,
                "tier": provider_response.tier,
                "fallback_used": provider_diagnostics.get("fallback_used"),
            },
        )
        prompt_text = self._prompts.build(bundle, question)
        prompt_cache_key = self._runtime.remember_prompt(context, prompt_text)
        retrieval_cache_key = self._runtime.remember_retrieval(
            context,
            {
                "used_claim_ids": [item["id"] for item in bundle.typed_claims],
                "artifact_ids": [fragment["chunk_id"] for fragment in bundle.text_fragments],
            },
        )
        answer_payload = {
            "answer_text": provider_response.text,
            "used_claims": [{**item, "workspace_id": workspace_id} for item in bundle.typed_claims],
            "used_artifacts": [
                {
                    "chunk_id": fragment["chunk_id"],
                    "section_title": fragment["section_title"],
                    "workspace_id": workspace_id,
                }
                for fragment in bundle.text_fragments
            ],
            "open_unknowns": [] if bundle.typed_claims else ["insufficient_modeled_evidence"],
            "routing": {"question_class": bundle.question_class},
            "prompt_fragments": [
                {"fragment_ref": fragment["chunk_id"], "workspace_id": workspace_id}
                for fragment in bundle.text_fragments
            ],
            "lineage_refs": [
                {"lineage_ref": item["id"], "workspace_id": workspace_id}
                for item in bundle.typed_claims
            ],
        }
        isolation = self._isolation.validate(
            context=context,
            answer_payload=answer_payload,
            prompt_text=prompt_text,
        )
        answer_payload["workspace_isolation"] = isolation.as_payload()
        reuse_mode = self._effective_reuse_mode(
            organization_id=organization_id,
            workspace_id=workspace_id,
            requested_mode=str(payload.get("reuse_mode") or "") or None,
        )
        latest_decision = self._latest_decision_record(workspace_id)
        decision_assurance = {}
        decision_contract = {}
        if latest_decision is not None:
            snapshot = self._bundle["decision_assurance_snapshots"].get(latest_decision.id)
            if snapshot is None or snapshot.invalidated:
                snapshot = self._decision_assurance.recompute(
                    decision_record_id=latest_decision.id,
                    recompute_scope="incremental",
                    trigger="dialogue_request",
                )
            waiver = self._bundle["decision_waivers"].get_active(latest_decision.id)
            decision_assurance = assurance_payload(snapshot, waiver)
            answer_payload["decision_assurance"] = decision_assurance
            if bundle.question_class == "decision_query":
                workspace_model = self._bundle["workspaces"].get(workspace_id)
                patterns = self._decision_pattern_retrieval.retrieve(
                    organization_id=organization_id,
                    workspace=workspace_model,
                    question=question,
                    reuse_mode=reuse_mode,
                )
                decision_contract = self._decision_answer_composer.compose(
                    workspace_id=workspace_id,
                    patterns=patterns,
                )
                answer_payload["decision_contract"] = decision_contract
        validation = self._validator.validate(
            answer_text=provider_response.text,
            workspace_id=workspace_id,
            answer_payload=answer_payload,
            expected_workspace_id=workspace_id,
            tier=provider_response.tier,
            escalation_used=False,
        )
        governance_event = {
            "event_type": "dialogue_answer_validated",
            "correlation_id": correlation_id,
            "routing_outcome": bundle.question_class,
            "validation_status": validation.status,
            "isolation_status": isolation.status,
        }
        validator_event = self._append_governance_event(
            organization_id=organization_id,
            workspace_id=workspace_id,
            event_type="validator_completed",
            payload={
                "correlation_id": correlation_id,
                "validation_status": validation.status,
                "reason_codes": validation.reason_codes,
            },
        )
        answer_text = provider_response.text
        open_unknowns = answer_payload["open_unknowns"]
        used_claims = answer_payload["used_claims"]
        used_artifacts = answer_payload["used_artifacts"]
        if isolation.status == "block":
            self._append_governance_event(
                organization_id=organization_id,
                workspace_id=workspace_id,
                event_type="workspace_contamination_blocked",
                payload={
                    "correlation_id": correlation_id,
                    "reason_codes": isolation.reason_codes,
                    "findings": [asdict(item) for item in isolation.findings],
                },
            )
            answer_text = "Workspace contamination guard blocked the response. Re-run the request inside the active case context."
            open_unknowns = ["workspace_context_reset_required"]
            used_claims = []
            used_artifacts = []
        if workspace and workspace.reentry_status == "in_progress":
            answer_text += " Disclaimer: re-entry is in progress; answer is grounded on the current published version."
            open_unknowns = [*open_unknowns, "reentry_in_progress"]
        elapsed_ms = RUNTIME_MONITOR.stop_timer(timer)
        RUNTIME_MONITOR.increment("dialogue_requests_total")
        RUNTIME_MONITOR.increment(f"validation_{validation.status}_total")
        if answer_payload["open_unknowns"]:
            RUNTIME_MONITOR.increment("clarification_rate_total")
        if validation.status == "block":
            RUNTIME_MONITOR.increment("provider_errors_total" if isolation.status == "block" else "blocked_answers_total")
        RUNTIME_MONITOR.log(
            {
                "event": "dialogue_request",
                "correlation_id": correlation_id,
                "workspace_id": workspace_id,
                "provider": provider_response.provider,
                "validation_status": validation.status,
                "latency_ms": round((time.monotonic() - started_at) * 1000.0, 3),
                "reason_codes": validation.reason_codes,
            }
        )
        return {
            "contract_version": "2026-03-23",
            "workspace_id": workspace_id,
            "workspace_version_id": workspace_version_id,
            "graph_version": graph_version,
            "session_id": session_id,
            "answer": {
                "text": answer_text,
                "epistemic_status": (
                    "grounded"
                    if validation.status == "pass"
                    else "blocked" if validation.status == "block" else "degraded"
                ),
                "confidence_score": 0.85 if validation.status == "pass" else 0.45,
                "validation_status": validation.status,
                "reason_codes": validation.reason_codes,
                "safe_fallback": (
                    "Ask a clarification question or inspect the evidence panel."
                    if validation.status == "block"
                    else None
                ),
                "used_claims": used_claims,
                "used_artifacts": used_artifacts,
                "open_unknowns": open_unknowns,
                "decision_assurance": decision_assurance,
                "decision_contract": decision_contract,
            },
            "validation": asdict(validation),
            "decision": decision_contract,
            "runtime": {
                "correlation_id": correlation_id,
                "namespace_key": context.namespace_key,
                "prompt_cache_key": prompt_cache_key,
                "retrieval_cache_key": retrieval_cache_key,
                "reset_applied": bind_result.reset_applied,
                "latency_ms": elapsed_ms,
            },
            "governance": {
                "events": [governance_event],
                "event_refs": [request_event.id, provider_event.id, validator_event.id],
                "lineage": {
                    "used_claim_ids": [item["id"] for item in used_claims],
                    "used_artifact_refs": [item["chunk_id"] for item in used_artifacts],
                },
            },
        }

    def history(self, *, session_id: str, workspace_id: str) -> dict:
        workspace = self._bundle["workspaces"].get(workspace_id)
        organization_id = workspace.organization_id if workspace else "unknown"
        context = self._build_context(
            organization_id=organization_id,
            workspace_id=workspace_id,
            session_id=session_id,
            user_id=None,
        )
        self._runtime.bind(context)
        history = self._dialogue_sessions.load_history(session_id=session_id, workspace_id=workspace_id)
        return {
            "session_id": session_id,
            "workspace_id": workspace_id,
            "runtime": {"namespace_key": context.namespace_key},
            "messages": [asdict(item) for item in history],
        }

    def evidence(self, *, workspace_id: str) -> dict:
        workspace = self._bundle["workspaces"].get(workspace_id)
        organization_id = workspace.organization_id if workspace else "unknown"
        context = self._build_context(
            organization_id=organization_id,
            workspace_id=workspace_id,
            session_id=None,
            user_id=None,
        )
        bind_result = self._runtime.bind(context)
        claims = self._bundle["claims"].list_for_workspace(workspace_id)
        chunks = self._bundle["retrieval_chunks"].list_for_workspace(workspace_id, active_only=True)
        if not claims:
            legacy_claims = self._legacy_evidence_claims(workspace_id)
            payload = {
                "workspace_id": workspace_id,
                "workspace_version_id": self._workspace_version_id(workspace_id),
                "graph_version": self._graph_version(workspace_id),
                "claims": legacy_claims[:30],
                "artifacts": [
                    {
                        "chunk_id": item["id"],
                        "section_title": item["artifact_path"],
                        "freshness_status": "legacy",
                    }
                    for item in legacy_claims[:30]
                ],
                "open_unknowns": [],
            }
            payload["runtime"] = {
                "namespace_key": context.namespace_key,
                "cache_key": self._runtime.remember_retrieval(context, payload, identifier="evidence"),
                "reset_applied": bind_result.reset_applied,
                "fallback_mode": "legacy_evidence_graph",
            }
            return payload
        payload = {
            "workspace_id": workspace_id,
            "workspace_version_id": self._workspace_version_id(workspace_id),
            "graph_version": self._graph_version(workspace_id),
            "claims": [
                {
                    "id": claim.id,
                    "claim_key": claim.claim_key,
                    "claim_type": claim.claim_type,
                    "statement": claim.statement,
                    "confidence_score": claim.confidence_score,
                }
                for claim in claims
            ],
            "artifacts": [
                {
                    "chunk_id": chunk.id,
                    "section_title": chunk.section_title,
                    "freshness_status": chunk.freshness_status,
                }
                for chunk in chunks
            ],
            "open_unknowns": [],
        }
        payload["runtime"] = {
            "namespace_key": context.namespace_key,
            "cache_key": self._runtime.remember_retrieval(context, payload, identifier="evidence"),
            "reset_applied": bind_result.reset_applied,
        }
        return payload

    def open_questions(self, *, workspace_id: str) -> dict:
        workspace = self._bundle["workspaces"].get(workspace_id)
        organization_id = workspace.organization_id if workspace else "unknown"
        context = self._build_context(
            organization_id=organization_id,
            workspace_id=workspace_id,
            session_id=None,
            user_id=None,
        )
        self._runtime.bind(context)
        items = self._bundle["question_queue"].list_for_workspace(workspace_id)
        return {
            "workspace_id": workspace_id,
            "workspace_version_id": self._workspace_version_id(workspace_id),
            "runtime": {"namespace_key": context.namespace_key},
            "unknowns": [
                {
                    "id": item.id,
                    "question": item.question_text,
                    "status": item.status,
                    "reason": item.reason_code,
                    "influence_area": item.influence_area,
                    "impact_preview": item.impact_preview,
                }
                for item in items
            ],
        }

    def version_state(self, *, workspace_id: str) -> dict:
        workspace = self._bundle["workspaces"].get(workspace_id)
        organization_id = workspace.organization_id if workspace else "unknown"
        context = self._build_context(
            organization_id=organization_id,
            workspace_id=workspace_id,
            session_id=None,
            user_id=None,
        )
        bind_result = self._runtime.bind(context)
        jobs = self._bundle["reentry_jobs"].list_for_workspace(workspace_id)
        pending = next((job for job in reversed(jobs) if job.status in {"queued", "in_progress", "completed"}), None)
        payload = {
            "workspace_id": workspace_id,
            "workspace_version_id": self._workspace_version_id(workspace_id),
            "graph_version": self._graph_version(workspace_id),
            "current_published_version": self._workspace_version_id(workspace_id),
            "pending_version": pending.workspace_version_id if pending and pending.status != "completed" else None,
            "reentry_status": workspace.reentry_status if workspace else "idle",
            "affected_stages": pending.affected_stages if pending else [],
            "stale_outputs": pending.stale_outputs if pending else [],
            "updated_at": "runtime",
        }
        payload["runtime"] = {
            "namespace_key": context.namespace_key,
            "cache_key": self._runtime.remember_version_state(context, payload),
            "reset_applied": bind_result.reset_applied,
        }
        return payload

    def decision_assurance_state(self, *, workspace_id: str) -> dict:
        records = self._bundle["decision_records"].list_for_workspace(workspace_id)
        snapshots = self._bundle["decision_assurance_snapshots"].list_for_workspace(workspace_id)
        return {
            "workspace_id": workspace_id,
            "records": [record.id for record in records],
            "assurance": [assurance_payload(snapshot) for snapshot in snapshots],
        }

    def decision_patterns(self, *, workspace_id: str, question: str, requested_mode: str | None = None) -> dict:
        workspace = self._bundle["workspaces"].get(workspace_id)
        if workspace is None:
            return {"workspace_id": workspace_id, "reuse_mode": "comparison-hint", "patterns": []}
        reuse_mode = self._effective_reuse_mode(
            organization_id=workspace.organization_id,
            workspace_id=workspace_id,
            requested_mode=requested_mode,
        )
        patterns = self._decision_pattern_retrieval.retrieve(
            organization_id=workspace.organization_id,
            workspace=workspace,
            question=question,
            reuse_mode=reuse_mode,
        )
        return {
            "workspace_id": workspace_id,
            "reuse_mode": reuse_mode,
            "patterns": [self._decision_answer_composer._pattern_payload(item) for item in patterns],
        }

    def decision_console(self, *, workspace_id: str, question: str = "decision") -> dict:
        patterns_payload = self.decision_patterns(workspace_id=workspace_id, question=question)["patterns"]
        decision_payload = self._decision_answer_composer.compose(workspace_id=workspace_id, patterns=[])
        assurance = self.decision_assurance_state(workspace_id=workspace_id)
        return {
            "workspace_id": workspace_id,
            "summary_card": {
                "selected_decision_id": decision_payload.get("selected_decision_id"),
                "selected_option_id": decision_payload.get("selected_option_id"),
                "review_conditions": decision_payload.get("review_conditions", {}),
            },
            "comparison": decision_payload.get("comparison", {}),
            "assurance": assurance.get("assurance", []),
            "historical_patterns": patterns_payload,
        }

    def review_action(self, *, decision_record_id: str, action: str, actor_id: str, expected_status: str | None = None) -> dict:
        review = self._decision_review_workflow.apply_action(
            decision_record_id=decision_record_id,
            action=action,
            actor_id=actor_id,
            expected_status=expected_status,
        )
        return {
            "decision_record_id": decision_record_id,
            "review_id": review.id,
            "status": review.status,
            "close_reason": review.close_reason,
        }

    def diff_panel(self, *, workspace_id: str) -> dict:
        return {
            "workspace_id": workspace_id,
            "events": build_diff_panel(self._bundle["governance"], workspace_id),
        }

    def governance_feed(self, *, workspace_id: str) -> dict:
        events = self._bundle["governance"].list_for_workspace(workspace_id)
        return {
            "workspace_id": workspace_id,
            "events": [
                {
                    "id": event.id,
                    "event_type": event.event_type,
                    "actor_type": event.actor_type,
                    "actor_id": event.actor_id,
                    "payload": event.payload,
                }
                for event in events
            ],
        }

    def provider_diagnostics(self) -> dict:
        return self._provider.diagnostics()

    def ui_page(self, *, workspace_id: str, organization_id: str) -> str:
        workspace = self._bundle["workspaces"].get(workspace_id)
        title = workspace.title if workspace else workspace_id
        stage = workspace.current_stage if workspace else "unknown"
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Dialogue Console {workspace_id}</title>
  <style>
    :root {{
      --bg: #f4f1e8;
      --ink: #14231b;
      --accent: #0e6b50;
      --warn: #a05b14;
      --block: #8f2f2f;
      --panel: #fffdf7;
      --line: #d8cfbe;
    }}
    body {{ font-family: Georgia, serif; background: linear-gradient(180deg, #efe8d8 0%, var(--bg) 60%); color: var(--ink); margin: 0; }}
    .topbar {{ padding: 18px 24px; border-bottom: 1px solid var(--line); background: rgba(255,255,255,.6); }}
    .topbar strong {{ letter-spacing: .04em; }}
    .grid {{ display: grid; grid-template-columns: 1.6fr 1fr 1fr; gap: 16px; padding: 20px; }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 18px; padding: 16px; box-shadow: 0 10px 30px rgba(20,35,27,.06); }}
    .card.pass {{ border-left: 6px solid var(--accent); }}
    .card.degrade {{ border-left: 6px solid var(--warn); }}
    .card.block {{ border-left: 6px solid var(--block); }}
    .muted {{ color: #56675e; font-size: 14px; }}
    .banner {{ margin: 12px 20px 0; padding: 12px 16px; border-radius: 14px; background: #f8efe2; border: 1px solid var(--line); }}
    textarea {{ width: 100%; min-height: 120px; border-radius: 12px; border: 1px solid var(--line); padding: 12px; font: inherit; }}
    button {{ background: var(--ink); color: white; border: 0; border-radius: 999px; padding: 10px 16px; cursor: pointer; }}
  </style>
</head>
<body>
  <div class="topbar">
    <strong>{_organization_name(self._bundle, organization_id)}</strong>
    <span class="muted"> | {title} | workspace_id={workspace_id} | stage={stage} | model=canonical-db</span>
  </div>
  <div class="banner" id="workspaceBanner">
    Active case: {title} ({workspace_id}). Switching workspace discards drafts and resets evidence, open questions, and version state caches.
  </div>
  <div class="grid">
    <section class="panel">
      <h2>Dialogue Console</h2>
      <p class="muted">Case-first workflow. Ask only within the active workspace.</p>
      <textarea id="questionBox">What grounded answer can you provide for this case?</textarea>
      <p><button id="askBtn">Ask</button></p>
      <div id="answerCard">{render_answer_card({'validation_status': 'pass', 'text': 'Waiting for question.', 'confidence_score': '-', 'epistemic_status': 'pending', 'reason_codes': [], 'safe_fallback': None})}</div>
    </section>
    <section class="panel">
      <h2>Evidence / Claims Panel</h2>
      <div id="evidencePanel" data-workspace="{workspace_id}">Load evidence after question.</div>
    </section>
    <section class="panel">
      <h2>Open Questions Panel</h2>
      <div id="openQuestions" data-workspace="{workspace_id}">Load unknowns after question.</div>
    </section>
  </div>
  <div class="grid">
    <section class="panel">
      <h2>Decision Summary</h2>
      <div id="decisionSummary">No decision loaded.</div>
    </section>
    <section class="panel">
      <h2>Assurance Breakdown</h2>
      <div id="assurancePanel">No assurance loaded.</div>
    </section>
    <section class="panel">
      <h2>Historical Reuse</h2>
      <div id="historicalPanel">No historical patterns loaded.</div>
    </section>
  </div>
  <script>
    const activeWorkspaceId = '{workspace_id}';
    const activeWorkspaceKey = 'dialogue-active-workspace';
    const draftKey = 'dialogue-composer-draft';
    const previousWorkspaceId = localStorage.getItem(activeWorkspaceKey);
    if (previousWorkspaceId && previousWorkspaceId !== activeWorkspaceId) {{
      localStorage.removeItem(draftKey);
      document.getElementById('questionBox').value = '';
      document.getElementById('workspaceBanner').innerHTML += ' Previous draft discarded after workspace switch.';
    }} else {{
      const storedDraft = localStorage.getItem(draftKey);
      if (storedDraft) {{
        document.getElementById('questionBox').value = storedDraft;
      }}
    }}
    localStorage.setItem(activeWorkspaceKey, activeWorkspaceId);
    document.getElementById('questionBox').addEventListener('input', () => {{
      localStorage.setItem(draftKey, document.getElementById('questionBox').value);
    }});
    async function refreshPanels() {{
      const evidence = await fetch('/api/workspaces/{workspace_id}/evidence').then(r => r.json());
      document.getElementById('evidencePanel').innerHTML = evidence.claims.map(c => `<div><strong>${{c.claim_key}}</strong><br>${{c.statement}}<br><span class="muted">confidence=${{c.confidence_score}}</span></div>`).join('<hr>');
      const unknowns = await fetch('/api/workspaces/{workspace_id}/open-questions').then(r => r.json());
      document.getElementById('openQuestions').innerHTML = unknowns.unknowns.map(u => `<div>${{u.question}}</div>`).join('');
      const decisionConsole = await fetch('/api/workspaces/{workspace_id}/decision-console').then(r => r.json());
      const summary = decisionConsole.summary_card || {{}};
      document.getElementById('decisionSummary').innerHTML = `<div><strong>${{summary.selected_decision_id || 'n/a'}}</strong><br><span class="muted">selected option=${{summary.selected_option_id || 'n/a'}}</span></div>`;
      const assurance = decisionConsole.assurance || [];
      document.getElementById('assurancePanel').innerHTML = assurance.map(a => `<div><strong>${{a.assurance_status}}</strong><br>score=${{a.assurance_score}}<br><span class="muted">weakest=${{a.weakest_link_ref || 'n/a'}}</span></div>`).join('<hr>');
      const patterns = decisionConsole.historical_patterns || [];
      document.getElementById('historicalPanel').innerHTML = patterns.map(p => `<div><strong>${{p.decision_record_id}}</strong><br><span class="muted">mode=${{p.reuse_mode}} | eligibility=${{p.reuse_eligibility}}</span><br><span class="muted">outcome=${{p.historical_outcome_summary?.average_score ?? 0}}</span></div>`).join('<hr>');
    }}
    document.getElementById('askBtn').onclick = async () => {{
      const payload = {{
        organization_id: '{organization_id}',
        workspace_id: '{workspace_id}',
        session_id: 'ui-session',
        user_id: 'ui-user',
        question: document.getElementById('questionBox').value,
        budget_profile: 'standard'
      }};
      const response = await fetch('/api/dialogue/ask', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(payload)
      }}).then(r => r.json());
      localStorage.setItem(draftKey, document.getElementById('questionBox').value);
      const status = response.answer.validation_status;
      const title = status === 'block' ? 'Safe Fallback' : 'Grounded Answer';
      const details = status === 'block'
        ? `<p class="muted">Blocked. ${{response.answer.safe_fallback || 'Use clarification path.'}}</p>`
        : status === 'degrade'
          ? `<p class="muted">Warning. ${{(response.answer.reason_codes || []).join(', ')}}</p>`
          : '';
      document.getElementById('answerCard').innerHTML =
        `<div class="card ${{status}}">
          <h3>${{title}}</h3>
          <p>${{response.answer.text || response.answer.safe_fallback || ''}}</p>
          <p class="muted">confidence=${{response.answer.confidence_score}} | epistemic_status=${{response.answer.epistemic_status}}</p>
          <p class="muted">decision_assurance=${{response.answer.decision_assurance?.assurance_status || 'n/a'}}</p>
          ${{details}}
        </div>`;
      refreshPanels();
    }};
    refreshPanels();
  </script>
</body>
</html>"""


def maybe_handle_api_request(project_root: Path, environ, start_response):
    service = DialogueApiService(project_root)
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET").upper()
    if path == "/api/dialogue/ask" and method == "POST":
        return _json_response(start_response, "200 OK", service.ask(_request_json(environ)))
    if path.startswith("/api/dialogue/sessions/") and path.endswith("/history") and method == "GET":
        session_id = path.split("/")[4]
        workspace_id = parse_qs(environ.get("QUERY_STRING", "")).get("workspace_id", [""])[0]
        return _json_response(start_response, "200 OK", service.history(session_id=session_id, workspace_id=workspace_id))
    if path.startswith("/api/workspaces/") and path.endswith("/evidence") and method == "GET":
        workspace_id = path.split("/")[3]
        return _json_response(start_response, "200 OK", service.evidence(workspace_id=workspace_id))
    if path.startswith("/api/workspaces/") and path.endswith("/open-questions") and method == "GET":
        workspace_id = path.split("/")[3]
        return _json_response(start_response, "200 OK", service.open_questions(workspace_id=workspace_id))
    if path.startswith("/api/workspaces/") and path.endswith("/version-state") and method == "GET":
        workspace_id = path.split("/")[3]
        return _json_response(start_response, "200 OK", service.version_state(workspace_id=workspace_id))
    if path.startswith("/api/workspaces/") and path.endswith("/diff-panel") and method == "GET":
        workspace_id = path.split("/")[3]
        return _json_response(start_response, "200 OK", service.diff_panel(workspace_id=workspace_id))
    if path.startswith("/api/workspaces/") and path.endswith("/governance-feed") and method == "GET":
        workspace_id = path.split("/")[3]
        return _json_response(start_response, "200 OK", service.governance_feed(workspace_id=workspace_id))
    if path.startswith("/api/workspaces/") and path.endswith("/decision-patterns") and method == "GET":
        workspace_id = path.split("/")[3]
        qs = parse_qs(environ.get("QUERY_STRING", ""))
        question = qs.get("question", ["decision"])[0]
        reuse_mode = qs.get("reuse_mode", [None])[0]
        return _json_response(start_response, "200 OK", service.decision_patterns(workspace_id=workspace_id, question=question, requested_mode=reuse_mode))
    if path.startswith("/api/workspaces/") and path.endswith("/decision-console") and method == "GET":
        workspace_id = path.split("/")[3]
        qs = parse_qs(environ.get("QUERY_STRING", ""))
        question = qs.get("question", ["decision"])[0]
        return _json_response(start_response, "200 OK", service.decision_console(workspace_id=workspace_id, question=question))
    if path == "/api/decision-review/action" and method == "POST":
        payload = _request_json(environ)
        return _json_response(
            start_response,
            "200 OK",
            service.review_action(
                decision_record_id=str(payload.get("decision_record_id") or ""),
                action=str(payload.get("action") or ""),
                actor_id=str(payload.get("actor_id") or "ui-user"),
                expected_status=payload.get("expected_status"),
            ),
        )
    if path == "/api/ops/provider-diagnostics" and method == "GET":
        return _json_response(start_response, "200 OK", service.provider_diagnostics())
    if path.startswith("/ui/workspaces/") and method == "GET":
        workspace_id = path.split("/")[3]
        qs = parse_qs(environ.get("QUERY_STRING", ""))
        organization_id = qs.get("organization_id", ["org-1"])[0]
        return _html_response(start_response, service.ui_page(workspace_id=workspace_id, organization_id=organization_id))
    return None
