from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sqlite3
from typing import Callable, Iterable, Sequence

from app.canonical_db.domain import (
    Artifact,
    Claim,
    DialogueMessage,
    DialogueSession,
    EmbeddingJob,
    QuotaLedgerEntry,
    RetrievalChunk,
)
from app.canonical_db.repositories import (
    ClaimRepository,
    ConnectionFactory,
    DialogueSessionRepository,
    TransactionManager,
)


QUESTION_CLASSES = {
    "constraint_query",
    "problem_query",
    "solution_query",
    "decision_query",
    "report_query",
    "evidence_query",
    "clarification_needed",
    "clarification_provided",
}

QUESTION_CLASS_TO_CLAIM_TYPES = {
    "constraint_query": {"decision_constraint", "normative_target"},
    "problem_query": {"source_fact", "derived_metric", "interpretation"},
    "solution_query": {"decision_constraint", "interpretation", "derived_metric"},
    "decision_query": {"decision_constraint", "normative_target", "interpretation", "derived_metric"},
    "report_query": {"source_fact", "derived_metric", "normative_target", "decision_constraint", "interpretation"},
    "evidence_query": {"source_fact", "derived_metric", "interpretation", "hypothesis"},
    "clarification_needed": set(),
    "clarification_provided": set(),
}

TIERS = ("cheap", "balanced", "premium")
BUDGET_LIMITS = {
    "economy": 5.0,
    "standard": 20.0,
    "premium": 100.0,
    "strict_cap": 1.0,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zа-я0-9]+", text.lower(), flags=re.IGNORECASE)


def _json_dumps(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


@dataclass(frozen=True)
class QuestionRoute:
    question_class: str
    confidence_score: float
    safe_fallback: str


@dataclass(frozen=True)
class RetrievedClaim:
    claim: Claim
    score: float
    signal_type: str


@dataclass(frozen=True)
class TextFragment:
    chunk_id: str
    section_title: str
    text: str
    supplementary_only: bool
    score: float


@dataclass(frozen=True)
class RetrievalResult:
    typed_claims: list[RetrievedClaim]
    support_chains: list[dict[str, object]]
    text_fragments: list[TextFragment]
    outcome: str


@dataclass(frozen=True)
class GroundingBundle:
    workspace_id: str
    workspace_version_id: str
    graph_version: str
    question_class: str
    typed_claims: list[dict[str, object]]
    text_fragments: list[dict[str, object]]


@dataclass(frozen=True)
class ProviderResponse:
    provider: str
    model_key: str
    tier: str
    text: str
    usage: dict[str, float]
    raw_payload: dict[str, object]


@dataclass(frozen=True)
class SectionDoc:
    chunk: RetrievalChunk
    artifact_type: str
    stage_name: str
    source_refs: list[str]


class SqliteDialogueMessageRepository:
    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def append(self, message: DialogueMessage) -> DialogueMessage:
        with self._connection_factory() as connection:
            connection.execute(
                """
                INSERT INTO dialogue_messages (
                    id, organization_id, workspace_id, session_id, workspace_version_id,
                    actor_type, actor_user_id, question_class, message_type, content_text,
                    grounding_bundle_ref, validator_result, graph_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.id,
                    message.organization_id,
                    message.workspace_id,
                    message.session_id,
                    message.workspace_version_id,
                    message.actor_type,
                    message.actor_user_id,
                    message.question_class,
                    message.message_type,
                    message.content_text,
                    message.grounding_bundle_ref,
                    message.validator_result,
                    message.graph_version,
                ),
            )
        return message

    def list_for_session(self, session_id: str, workspace_id: str) -> list[DialogueMessage]:
        with self._connection_factory() as connection:
            rows = connection.execute(
                """
                SELECT id, organization_id, workspace_id, session_id, workspace_version_id,
                       actor_type, actor_user_id, question_class, message_type, content_text,
                       grounding_bundle_ref, validator_result, graph_version
                FROM dialogue_messages
                WHERE session_id = ? AND workspace_id = ?
                ORDER BY created_at, CASE WHEN message_type = 'question' THEN 0 ELSE 1 END, id
                """,
                (session_id, workspace_id),
            ).fetchall()
        return [DialogueMessage(**dict(row)) for row in rows]


class SqliteRetrievalChunkRepository:
    def __init__(
        self,
        connection_factory: ConnectionFactory,
        transaction_manager: TransactionManager | None = None,
    ):
        self._connection_factory = connection_factory
        self._transactions = transaction_manager or TransactionManager(connection_factory)

    def replace_for_workspace(self, workspace_id: str, chunks: Sequence[RetrievalChunk]) -> None:
        with self._transactions.transaction() as connection:
            connection.execute("DELETE FROM retrieval_chunks WHERE workspace_id = ?", (workspace_id,))
            self._insert_many(connection, chunks)

    def add_chunks(self, chunks: Sequence[RetrievalChunk]) -> None:
        with self._transactions.transaction() as connection:
            self._insert_many(connection, chunks)

    def list_for_workspace(self, workspace_id: str, *, active_only: bool = False) -> list[RetrievalChunk]:
        query = """
            SELECT id, organization_id, workspace_id, artifact_id, claim_id, chunk_key, chunk_text,
                   section_title, status, retrieval_revision, source_revision, freshness_status, is_active
            FROM retrieval_chunks
            WHERE workspace_id = ?
        """
        params: list[object] = [workspace_id]
        if active_only:
            query += " AND is_active = 1 AND freshness_status = 'fresh'"
        query += " ORDER BY chunk_key"
        with self._connection_factory() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_chunk(row) for row in rows]

    def activate_revision(self, workspace_id: str, revision: int) -> None:
        with self._connection_factory() as connection:
            connection.execute(
                "UPDATE retrieval_chunks SET is_active = CASE WHEN retrieval_revision = ? THEN 1 ELSE 0 END WHERE workspace_id = ?",
                (revision, workspace_id),
            )
            connection.execute(
                "UPDATE retrieval_chunks SET freshness_status = 'fresh' WHERE workspace_id = ? AND retrieval_revision = ?",
                (workspace_id, revision),
            )

    def mark_stale(self, workspace_id: str, source_revision: str) -> None:
        with self._connection_factory() as connection:
            connection.execute(
                """
                UPDATE retrieval_chunks
                SET freshness_status = 'stale', is_active = 0, source_revision = ?
                WHERE workspace_id = ?
                """,
                (source_revision, workspace_id),
            )

    def _insert_many(self, connection: sqlite3.Connection, chunks: Sequence[RetrievalChunk]) -> None:
        connection.executemany(
            """
            INSERT INTO retrieval_chunks (
                id, organization_id, workspace_id, artifact_id, claim_id, chunk_key, chunk_text,
                section_title, status, retrieval_revision, source_revision, freshness_status, is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    chunk.id,
                    chunk.organization_id,
                    chunk.workspace_id,
                    chunk.artifact_id,
                    chunk.claim_id,
                    chunk.chunk_key,
                    chunk.chunk_text,
                    chunk.section_title,
                    chunk.status,
                    chunk.retrieval_revision,
                    chunk.source_revision,
                    chunk.freshness_status,
                    1 if chunk.is_active else 0,
                )
                for chunk in chunks
            ],
        )

    def _row_to_chunk(self, row: sqlite3.Row) -> RetrievalChunk:
        payload = dict(row)
        payload["is_active"] = bool(payload["is_active"])
        return RetrievalChunk(**payload)


class SqliteEmbeddingJobRepository:
    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def upsert(self, job: EmbeddingJob) -> EmbeddingJob:
        with self._connection_factory() as connection:
            connection.execute(
                """
                INSERT INTO embedding_jobs (
                    id, organization_id, workspace_id, retrieval_chunk_id, status, provider, model_key,
                    source_revision, attempt_count, last_error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    retrieval_chunk_id = excluded.retrieval_chunk_id,
                    status = excluded.status,
                    provider = excluded.provider,
                    model_key = excluded.model_key,
                    source_revision = excluded.source_revision,
                    attempt_count = excluded.attempt_count,
                    last_error = excluded.last_error
                """,
                (
                    job.id,
                    job.organization_id,
                    job.workspace_id,
                    job.retrieval_chunk_id,
                    job.status,
                    job.provider,
                    job.model_key,
                    job.source_revision,
                    job.attempt_count,
                    job.last_error,
                ),
            )
        return job

    def get(self, job_id: str) -> EmbeddingJob | None:
        with self._connection_factory() as connection:
            row = connection.execute(
                """
                SELECT id, organization_id, workspace_id, retrieval_chunk_id, status, provider, model_key,
                       source_revision, attempt_count, last_error
                FROM embedding_jobs WHERE id = ?
                """,
                (job_id,),
            ).fetchone()
        return None if row is None else EmbeddingJob(**dict(row))

    def list_for_workspace(self, workspace_id: str) -> list[EmbeddingJob]:
        with self._connection_factory() as connection:
            rows = connection.execute(
                """
                SELECT id, organization_id, workspace_id, retrieval_chunk_id, status, provider, model_key,
                       source_revision, attempt_count, last_error
                FROM embedding_jobs
                WHERE workspace_id = ?
                ORDER BY created_at, id
                """,
                (workspace_id,),
            ).fetchall()
        return [EmbeddingJob(**dict(row)) for row in rows]


class SqliteQuotaLedgerRepository:
    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def append(self, entry: QuotaLedgerEntry) -> QuotaLedgerEntry:
        with self._connection_factory() as connection:
            connection.execute(
                """
                INSERT INTO quota_ledger (
                    id, organization_id, workspace_id, user_id, metric_key, delta, unit, source_event
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.organization_id,
                    entry.workspace_id,
                    entry.user_id,
                    entry.metric_key,
                    entry.delta,
                    entry.unit,
                    entry.source_event,
                ),
            )
        return entry

    def sum_for_scope(self, *, organization_id: str, workspace_id: str | None, metric_key: str) -> float:
        with self._connection_factory() as connection:
            if workspace_id is None:
                row = connection.execute(
                    """
                    SELECT COALESCE(SUM(delta), 0.0) FROM quota_ledger
                    WHERE organization_id = ? AND metric_key = ?
                    """,
                    (organization_id, metric_key),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT COALESCE(SUM(delta), 0.0) FROM quota_ledger
                    WHERE organization_id = ? AND workspace_id = ? AND metric_key = ?
                    """,
                    (organization_id, workspace_id, metric_key),
                ).fetchone()
        return float(row[0] or 0.0)


class DialogueSessionService:
    def __init__(
        self,
        sessions: DialogueSessionRepository,
        messages: SqliteDialogueMessageRepository,
    ):
        self._sessions = sessions
        self._messages = messages

    def create_session(self, session: DialogueSession) -> DialogueSession:
        return self._sessions.upsert(session)

    def append_message(self, message: DialogueMessage) -> DialogueMessage:
        session = self._sessions.get(message.session_id)
        if session is None:
            raise PermissionError("Unknown dialogue session")
        if session.workspace_id != message.workspace_id:
            raise PermissionError("Cross-workspace session reuse is forbidden")
        return self._messages.append(message)

    def load_history(self, *, session_id: str, workspace_id: str) -> list[DialogueMessage]:
        session = self._sessions.get(session_id)
        if session is None or session.workspace_id != workspace_id:
            raise PermissionError("Session does not belong to workspace")
        return self._messages.list_for_session(session_id, workspace_id)


class QuestionRouter:
    def route(self, question: str) -> QuestionRoute:
        text = question.strip().lower()
        if text.startswith("clarification:") or text.startswith("уточнение:"):
            return QuestionRoute("clarification_provided", 0.98, "clarification_provided")
        rules = [
            ("constraint_query", ("constraint", "огранич", "limit", "лимит", "must", "should not", "нельзя")),
            ("decision_query", ("decision", "choose", "selection", "решени", "выбор", "какой вариант", "which option")),
            ("solution_query", ("solution", "вариант", "опци", "recommend", "рекоменду")),
            ("problem_query", ("problem", "issue", "root cause", "проблем", "почему")),
            ("report_query", ("report", "summary", "отчет", "вывод")),
            ("evidence_query", ("evidence", "fact", "source", "доказ", "факт", "источник")),
        ]
        best_class = "evidence_query"
        best_score = 0.0
        for question_class, markers in rules:
            score = sum(1 for marker in markers if marker in text)
            if score > best_score:
                best_class = question_class
                best_score = float(score)
        if best_score == 0.0:
            fallback = "clarification_needed" if len(_tokenize(text)) <= 3 else "evidence_query"
            return QuestionRoute(fallback, 0.2, fallback)
        confidence = min(0.95, 0.45 + best_score * 0.2)
        if confidence < 0.5:
            return QuestionRoute("evidence_query", confidence, "evidence_query")
        return QuestionRoute(best_class, confidence, "evidence_query")


class GraphRetrievalService:
    def __init__(self, claims: ClaimRepository):
        self._claims = claims

    def retrieve(self, *, workspace_id: str, question: str, question_class: str) -> RetrievalResult:
        allowed_types = QUESTION_CLASS_TO_CLAIM_TYPES[question_class]
        all_claims = self._claims.list_for_workspace(workspace_id)
        relations = self._claims.list_relations_for_workspace(workspace_id)
        query_tokens = set(_tokenize(question))
        ranked: list[RetrievedClaim] = []
        for claim in all_claims:
            if claim.claim_type not in allowed_types:
                continue
            claim_tokens = set(_tokenize(claim.statement + " " + claim.claim_key))
            overlap = len(query_tokens & claim_tokens)
            if overlap == 0:
                continue
            ranked.append(
                RetrievedClaim(
                    claim=claim,
                    score=float(overlap) + claim.confidence_score,
                    signal_type="typed_claim",
                )
            )
        ranked.sort(key=lambda item: (-item.score, item.claim.claim_key, item.claim.id))
        if not ranked:
            fallback = (
                "needs_clarification"
                if question_class in {"clarification_needed", "evidence_query"} or len(query_tokens) <= 3
                else "insufficient_modeled_evidence"
            )
            return RetrievalResult([], [], [], fallback)

        selected = ranked[:5]
        selected_ids = {item.claim.id for item in selected}
        support = []
        for relation in relations:
            if relation.from_claim_id in selected_ids or relation.to_claim_id in selected_ids:
                support.append(
                    {
                        "relation_type": relation.relation_type,
                        "from_claim_id": relation.from_claim_id,
                        "to_claim_id": relation.to_claim_id,
                        "signal_type": "support_chain",
                    }
                )
        return RetrievalResult(selected, support, [], "ok")


class BM25SectionIndex:
    def __init__(self, chunks: SqliteRetrievalChunkRepository):
        self._chunks = chunks

    def index_sections(
        self,
        *,
        organization_id: str,
        workspace_id: str,
        artifacts: Sequence[Artifact],
        workspace_root: Path,
        revision: int = 1,
        source_revision: str = "",
    ) -> list[SectionDoc]:
        docs: list[SectionDoc] = []
        raw_chunks: list[RetrievalChunk] = []
        for artifact in artifacts:
            path = workspace_root / artifact.file_path
            if not path.exists() or path.suffix.lower() not in {".md", ".markdown"}:
                continue
            for index, (section_title, section_text) in enumerate(_split_markdown_sections(path.read_text(encoding="utf-8"))):
                chunk = RetrievalChunk(
                    id=f"{workspace_id}:{artifact.id}:{index}",
                    organization_id=organization_id,
                    workspace_id=workspace_id,
                    artifact_id=None,
                    claim_id=None,
                    chunk_key=f"{organization_id}:{workspace_id}:{artifact.artifact_key}:{index}",
                    chunk_text=section_text,
                    section_title=section_title,
                    status="active",
                    retrieval_revision=revision,
                    source_revision=source_revision,
                    freshness_status="fresh",
                    is_active=True,
                )
                raw_chunks.append(chunk)
                docs.append(
                    SectionDoc(
                        chunk=chunk,
                        artifact_type=artifact.artifact_type,
                        stage_name=artifact.stage_name,
                        source_refs=list(artifact.payload.get("source_refs", [])),
                    )
                )
        self._chunks.replace_for_workspace(workspace_id, raw_chunks)
        return docs

    def search(self, *, organization_id: str, workspace_id: str, query: str, limit: int = 3) -> list[TextFragment]:
        chunks = [
            chunk
            for chunk in self._chunks.list_for_workspace(workspace_id, active_only=True)
            if chunk.organization_id == organization_id
        ]
        corpus = [_tokenize(chunk.chunk_text) for chunk in chunks]
        if not corpus:
            return []
        avg_doc_len = sum(len(doc) for doc in corpus) / len(corpus)
        doc_freqs = Counter()
        for tokens in corpus:
            for token in set(tokens):
                doc_freqs[token] += 1
        query_tokens = _tokenize(query)
        scored: list[TextFragment] = []
        for chunk, tokens in zip(chunks, corpus, strict=False):
            term_freq = Counter(tokens)
            score = 0.0
            for token in query_tokens:
                if term_freq[token] == 0:
                    continue
                idf = math.log(1 + (len(corpus) - doc_freqs[token] + 0.5) / (doc_freqs[token] + 0.5))
                numerator = term_freq[token] * 2.2
                denominator = term_freq[token] + 1.2 * (1 - 0.75 + 0.75 * (len(tokens) / max(avg_doc_len, 1)))
                score += idf * numerator / denominator
            if score > 0:
                scored.append(
                    TextFragment(
                        chunk_id=chunk.id,
                        section_title=chunk.section_title or "",
                        text=chunk.chunk_text,
                        supplementary_only=True,
                        score=score,
                    )
                )
        scored.sort(key=lambda item: (-item.score, item.chunk_id))
        return scored[:limit]


class GroundingBundleBuilder:
    def build(
        self,
        *,
        workspace_id: str,
        workspace_version_id: str,
        graph_version: str,
        question_class: str,
        typed_claims: Sequence[RetrievedClaim],
        text_fragments: Sequence[TextFragment],
    ) -> GroundingBundle:
        safe_fragments = [
            fragment
            for fragment in text_fragments
            if fragment.chunk_id.startswith(f"{workspace_id}:")
        ]
        return GroundingBundle(
            workspace_id=workspace_id,
            workspace_version_id=workspace_version_id,
            graph_version=graph_version,
            question_class=question_class,
            typed_claims=[
                {
                    "id": item.claim.id,
                    "claim_key": item.claim.claim_key,
                    "claim_type": item.claim.claim_type,
                    "statement": item.claim.statement,
                    "signal_type": item.signal_type,
                    "score": item.score,
                }
                for item in typed_claims
            ],
            text_fragments=[
                {
                    "chunk_id": fragment.chunk_id,
                    "section_title": fragment.section_title,
                    "text": fragment.text,
                    "supplementary_only": True,
                    "score": fragment.score,
                }
                for fragment in safe_fragments
            ],
        )


class PromptBuilder:
    def build(self, bundle: GroundingBundle, question: str) -> str:
        claims_block = "\n".join(
            f"- [{item['claim_type']}] {item['claim_key']}: {item['statement']}"
            for item in bundle.typed_claims
        ) or "- none"
        text_block = "\n".join(
            f"- ({item['section_title']}) {item['text']}"
            for item in bundle.text_fragments
        ) or "- none"
        return (
            "WORKSPACE CONTEXT\n"
            f"workspace_id={bundle.workspace_id}\n"
            f"workspace_version_id={bundle.workspace_version_id}\n"
            f"graph_version={bundle.graph_version}\n\n"
            "QUESTION\n"
            f"{question}\n\n"
            "VERIFIED CLAIMS\n"
            f"{claims_block}\n\n"
            "SUPPORTING TEXT\n"
            f"{text_block}\n\n"
            "EPISTEMIC RULES\n"
            "- Treat VERIFIED CLAIMS as primary grounded evidence.\n"
            "- Treat SUPPORTING TEXT as supplementary only.\n"
            "- Do not fabricate unsupported claims.\n\n"
            "RESPONSE CONTRACT\n"
            "- Answer only from current workspace grounding.\n"
            "- State when modeled evidence is insufficient.\n"
        )


class EmbeddingLifecycleService:
    def __init__(
        self,
        chunks: SqliteRetrievalChunkRepository,
        jobs: SqliteEmbeddingJobRepository,
    ):
        self._chunks = chunks
        self._jobs = jobs

    def create_job_for_claim_change(
        self,
        *,
        organization_id: str,
        workspace_id: str,
        claim_id: str,
        source_revision: str,
        provider: str = "test-provider",
        model_key: str = "text-embedding-3-small",
    ) -> EmbeddingJob:
        self._chunks.mark_stale(workspace_id, source_revision)
        job = EmbeddingJob(
            id=f"embedding:{workspace_id}:{claim_id}:{source_revision}",
            organization_id=organization_id,
            workspace_id=workspace_id,
            retrieval_chunk_id=None,
            status="queued",
            provider=provider,
            model_key=model_key,
            source_revision=source_revision,
            attempt_count=0,
            last_error="",
        )
        return self._jobs.upsert(job)

    def complete_job(self, *, job_id: str, activate_revision: int) -> EmbeddingJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        self._chunks.activate_revision(job.workspace_id, activate_revision)
        completed = EmbeddingJob(
            id=job.id,
            organization_id=job.organization_id,
            workspace_id=job.workspace_id,
            retrieval_chunk_id=job.retrieval_chunk_id,
            status="completed",
            provider=job.provider,
            model_key=job.model_key,
            source_revision=job.source_revision,
            attempt_count=job.attempt_count + 1,
            last_error="",
        )
        return self._jobs.upsert(completed)

    def fail_job(self, *, job_id: str, error: str) -> EmbeddingJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        failed = EmbeddingJob(
            id=job.id,
            organization_id=job.organization_id,
            workspace_id=job.workspace_id,
            retrieval_chunk_id=job.retrieval_chunk_id,
            status="failed",
            provider=job.provider,
            model_key=job.model_key,
            source_revision=job.source_revision,
            attempt_count=job.attempt_count + 1,
            last_error=error,
        )
        return self._jobs.upsert(failed)

    def retry_failed_job(self, job_id: str) -> EmbeddingJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        if job.status != "failed":
            raise ValueError("Only failed jobs can be retried")
        retried = EmbeddingJob(
            id=job.id,
            organization_id=job.organization_id,
            workspace_id=job.workspace_id,
            retrieval_chunk_id=job.retrieval_chunk_id,
            status="queued",
            provider=job.provider,
            model_key=job.model_key,
            source_revision=job.source_revision,
            attempt_count=job.attempt_count,
            last_error="",
        )
        return self._jobs.upsert(retried)


class QuotaEnforcementService:
    def __init__(self, ledger: SqliteQuotaLedgerRepository):
        self._ledger = ledger

    def reserve(
        self,
        *,
        organization_id: str,
        workspace_id: str,
        user_id: str,
        budget_profile: str,
        estimated_cost: float,
        source_event: str,
    ) -> QuotaLedgerEntry:
        limit = BUDGET_LIMITS[budget_profile]
        current = self._ledger.sum_for_scope(
            organization_id=organization_id,
            workspace_id=workspace_id,
            metric_key="llm_cost",
        )
        if current + estimated_cost > limit:
            raise PermissionError("Quota preflight reservation failed")
        entry = QuotaLedgerEntry(
            id=f"quota:{workspace_id}:{source_event}:{int(current * 1000)}",
            organization_id=organization_id,
            workspace_id=workspace_id,
            user_id=user_id,
            metric_key="llm_cost",
            delta=estimated_cost,
            unit="credits",
            source_event=source_event,
        )
        return self._ledger.append(entry)


class LLMProviderAdapter:
    def __init__(
        self,
        *,
        mode: str,
        direct_callable: Callable[[str, str], dict[str, object]] | None = None,
        gateway_callable: Callable[[str, str], dict[str, object]] | None = None,
        fallback_callable: Callable[[str, str], dict[str, object]] | None = None,
    ):
        self._mode = mode
        self._direct_callable = direct_callable
        self._gateway_callable = gateway_callable
        self._fallback_callable = fallback_callable
        self._last_diagnostics: dict[str, object] = {
            "active_mode": mode,
            "last_provider": None,
            "last_model_key": None,
            "fallback_used": False,
            "last_error": None,
        }

    def generate(self, *, prompt: str, tier: str, model_key: str) -> ProviderResponse:
        provider_name = self._mode
        fallback_used = False
        try:
            if self._mode == "direct":
                if self._direct_callable is None:
                    raise RuntimeError("Direct provider callable is not configured")
                payload = self._direct_callable(prompt, model_key)
            else:
                if self._gateway_callable is None:
                    raise RuntimeError("Gateway provider callable is not configured")
                payload = self._gateway_callable(prompt, model_key)
        except Exception as exc:
            if self._fallback_callable is None:
                self._last_diagnostics = {
                    "active_mode": self._mode,
                    "last_provider": provider_name,
                    "last_model_key": model_key,
                    "fallback_used": False,
                    "last_error": str(exc),
                }
                raise
            payload = self._fallback_callable(prompt, model_key)
            provider_name = f"{self._mode}->fallback"
            fallback_used = True
            self._last_diagnostics = {
                "active_mode": self._mode,
                "last_provider": provider_name,
                "last_model_key": model_key,
                "fallback_used": True,
                "last_error": str(exc),
            }
        else:
            self._last_diagnostics = {
                "active_mode": self._mode,
                "last_provider": provider_name,
                "last_model_key": model_key,
                "fallback_used": False,
                "last_error": None,
            }
        return ProviderResponse(
            provider=provider_name,
            model_key=model_key,
            tier=tier,
            text=str(payload.get("text", "")),
            usage=dict(payload.get("usage", {"estimated_cost": 0.0})),
            raw_payload=payload,
        )

    def diagnostics(self) -> dict[str, object]:
        direct_status = "configured" if self._direct_callable is not None else "missing"
        gateway_status = "configured" if self._gateway_callable is not None else "missing"
        fallback_status = "configured" if self._fallback_callable is not None else "missing"
        return {
            "active_mode": self._mode,
            "direct_provider": direct_status,
            "gateway_provider": gateway_status,
            "fallback_provider": fallback_status,
            **self._last_diagnostics,
        }


class RoutingPolicy:
    def choose_tier(self, *, task_class: str, risk_level: str, budget_profile: str) -> str:
        if budget_profile == "strict_cap":
            return "cheap"
        if risk_level == "high" or task_class in {"report_query", "solution_query"}:
            return "balanced" if budget_profile in {"economy", "standard"} else "premium"
        return "cheap" if budget_profile == "economy" else "balanced"

    def escalate(self, tier: str) -> str:
        if tier == "cheap":
            return "balanced"
        if tier == "balanced":
            return "premium"
        raise ValueError("Escalation ceiling reached")


class DialogueOrchestrator:
    def __init__(
        self,
        *,
        dialogue_sessions: DialogueSessionService,
        router: QuestionRouter,
        retrieval: GraphRetrievalService,
        bm25: BM25SectionIndex,
        grounding: GroundingBundleBuilder,
        prompts: PromptBuilder,
        quota: QuotaEnforcementService,
        provider: LLMProviderAdapter,
        policy: RoutingPolicy,
    ):
        self._dialogue_sessions = dialogue_sessions
        self._router = router
        self._retrieval = retrieval
        self._bm25 = bm25
        self._grounding = grounding
        self._prompts = prompts
        self._quota = quota
        self._provider = provider
        self._policy = policy

    def answer(
        self,
        *,
        organization_id: str,
        workspace_id: str,
        workspace_version_id: str,
        graph_version: str,
        user_id: str,
        session_id: str,
        question: str,
        budget_profile: str,
        risk_level: str = "medium",
    ) -> tuple[GroundingBundle, ProviderResponse]:
        route = self._router.route(question)
        retrieval_result = self._retrieval.retrieve(
            workspace_id=workspace_id,
            question=question,
            question_class=route.question_class,
        )
        if route.question_class != "clarification_provided" and retrieval_result.outcome == "ok" and len(retrieval_result.typed_claims) < 2:
            supplementary = self._bm25.search(
                organization_id=organization_id,
                workspace_id=workspace_id,
                query=question,
            )
        else:
            supplementary = []
        bundle = self._grounding.build(
            workspace_id=workspace_id,
            workspace_version_id=workspace_version_id,
            graph_version=graph_version,
            question_class=route.question_class,
            typed_claims=retrieval_result.typed_claims,
            text_fragments=supplementary,
        )
        if route.question_class != "clarification_provided" and not bundle.typed_claims:
            raise PermissionError(retrieval_result.outcome)
        tier = self._policy.choose_tier(
            task_class=route.question_class,
            risk_level=risk_level,
            budget_profile=budget_profile,
        )
        prompt = self._prompts.build(bundle, question)
        self._quota.reserve(
            organization_id=organization_id,
            workspace_id=workspace_id,
            user_id=user_id,
            budget_profile=budget_profile,
            estimated_cost=1.0 if tier == "cheap" else 2.0 if tier == "balanced" else 3.0,
            source_event=f"dialogue:{session_id}",
        )
        response = self._provider.generate(prompt=prompt, tier=tier, model_key=f"{tier}-model")
        self._dialogue_sessions.append_message(
            DialogueMessage(
                id=f"{session_id}:question:{len(question)}",
                organization_id=organization_id,
                workspace_id=workspace_id,
                session_id=session_id,
                workspace_version_id=workspace_version_id,
                actor_type="user",
                actor_user_id=user_id,
                question_class=route.question_class,
                message_type="question",
                content_text=question,
                graph_version=graph_version,
            )
        )
        self._dialogue_sessions.append_message(
            DialogueMessage(
                id=f"{session_id}:answer:{len(response.text)}",
                organization_id=organization_id,
                workspace_id=workspace_id,
                session_id=session_id,
                workspace_version_id=workspace_version_id,
                actor_type="assistant",
                actor_user_id=None,
                question_class=route.question_class,
                message_type="answer",
                content_text=response.text,
                grounding_bundle_ref=_json_dumps(asdict(bundle)),
                graph_version=graph_version,
            )
        )
        return bundle, response


def _split_markdown_sections(markdown_text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_title = "Document"
    current_lines: list[str] = []
    for line in markdown_text.splitlines():
        if line.startswith("#"):
            if current_lines:
                sections.append((current_title, "\n".join(current_lines).strip()))
            current_title = line.lstrip("#").strip() or "Untitled"
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines or not sections:
        sections.append((current_title, "\n".join(current_lines).strip()))
    return [(title, text) for title, text in sections if text]
