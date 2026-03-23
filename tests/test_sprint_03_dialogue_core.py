from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from app.canonical_db.claim_graph import ClaimGraphService
from app.canonical_db.config import DatabaseConfig, connect
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
    SqliteDialogueMessageRepository,
    SqliteEmbeddingJobRepository,
    SqliteQuotaLedgerRepository,
    SqliteRetrievalChunkRepository,
    TextFragment,
    QuotaEnforcementService,
)
from app.canonical_db.domain import (
    Artifact,
    Claim,
    ClaimRelation,
    DialogueMessage,
    DialogueSession,
    Organization,
    RetrievalChunk,
    User,
    UserProfile,
    Workspace,
    WorkspaceVersion,
)
from app.canonical_db.migration_runner import upgrade
from app.canonical_db.repositories import (
    SqliteClaimRepository,
    SqliteDialogueSessionRepository,
    SqliteMembershipRepository,
    SqliteOrganizationRepository,
    SqliteUserProfileRepository,
    SqliteUserRepository,
    SqliteWorkspaceRepository,
    TransactionManager,
)
from app.canonical_db.tenant_auth import OrganizationService


class Sprint03DialogueCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = self.root / "canonical.sqlite3"
        self.config = DatabaseConfig(dsn=f"sqlite:///{self.db_path}", environment="test")

        def factory():
            return connect(self.config)

        self.factory = factory
        with self.factory() as connection:
            upgrade(connection, target="head")

        self.users = SqliteUserRepository(self.factory)
        self.user_profiles = SqliteUserProfileRepository(self.factory)
        self.memberships = SqliteMembershipRepository(self.factory)
        self.organizations = SqliteOrganizationRepository(self.factory)
        self.workspaces = SqliteWorkspaceRepository(self.factory)
        self.dialogue_sessions = SqliteDialogueSessionRepository(self.factory)
        self.dialogue_messages = SqliteDialogueMessageRepository(self.factory)
        self.claims = SqliteClaimRepository(self.factory, TransactionManager(self.factory))
        self.retrieval_chunks = SqliteRetrievalChunkRepository(self.factory, TransactionManager(self.factory))
        self.embedding_jobs = SqliteEmbeddingJobRepository(self.factory)
        self.ledger = SqliteQuotaLedgerRepository(self.factory)

        self.org_service = OrganizationService(self.organizations, self.memberships, self.user_profiles)
        self.claim_graph = ClaimGraphService(self.claims)
        self.router = QuestionRouter()
        self.retrieval = GraphRetrievalService(self.claims)
        self.grounding = GroundingBundleBuilder()
        self.prompt_builder = PromptBuilder()
        self.bm25 = BM25SectionIndex(self.retrieval_chunks)
        self.embedding = EmbeddingLifecycleService(self.retrieval_chunks, self.embedding_jobs)
        self.quota = QuotaEnforcementService(self.ledger)
        self.policy = RoutingPolicy()
        self.session_service = DialogueSessionService(self.dialogue_sessions, self.dialogue_messages)

        self.owner = User(
            id="owner-1",
            email="owner@example.com",
            password_hash="hash",
            display_name="Owner",
            status="active",
        )
        self.users.upsert(self.owner)
        self.user_profiles.upsert(self.user_profiles.get(self.owner.id) or UserProfile(user_id=self.owner.id))
        self.organization = Organization(id="org-1", name="Org One", slug="org-one", owner_user_id=self.owner.id)
        self.org_service.create_organization(self.organization)
        self.workspace, self.version = self._workspace("ws-1", self.organization.id, self.owner.id, 1)
        self.workspaces.upsert(self.workspace, self.version)
        self._seed_claims()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _workspace(self, workspace_id: str, organization_id: str, user_id: str, version_no: int):
        workspace = Workspace(
            id=workspace_id,
            organization_id=organization_id,
            workspace_key=workspace_id,
            title=f"Workspace {workspace_id}",
            case_type="analysis_case",
            status="active",
            current_stage="analysis",
            active_model_version=version_no,
            created_by_user_id=user_id,
            metadata={},
        )
        version = WorkspaceVersion(
            id=f"{workspace_id}:v{version_no}",
            organization_id=organization_id,
            workspace_id=workspace_id,
            version_no=version_no,
            version_label=f"v{version_no}",
            change_reason="test",
            created_by=user_id,
        )
        return workspace, version

    def _claim(self, claim_id: str, claim_key: str, claim_type: str, statement: str) -> Claim:
        return Claim(
            id=claim_id,
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            claim_key=claim_key,
            claim_type=claim_type,
            statement=statement,
            epistemic_status="accepted",
            confidence_score=0.8,
            source_kind="source_fact",
            source_ref="raw/input.md",
        )

    def _seed_claims(self) -> None:
        budget = self.claim_graph.create_claim(
            self._claim("claim-budget", "budget_limit", "decision_constraint", "Budget limit must not exceed 500k"),
            changed_by_actor=self.owner.id,
            change_reason="seed",
        )
        baseline = self.claim_graph.create_claim(
            self._claim("claim-baseline", "baseline_cost", "source_fact", "Current baseline cost is 420k"),
            changed_by_actor=self.owner.id,
            change_reason="seed",
        )
        option = self.claim_graph.create_claim(
            self._claim("claim-option", "upgrade_option", "interpretation", "Upgrade option reduces downtime risk"),
            changed_by_actor=self.owner.id,
            change_reason="seed",
        )
        self.claim_graph.add_relation(
            ClaimRelation(
                id="rel-support",
                organization_id=self.organization.id,
                workspace_id=self.workspace.id,
                from_claim_id=baseline.id,
                to_claim_id=budget.id,
                relation_type="supports",
            )
        )
        self.claim_graph.add_relation(
            ClaimRelation(
                id="rel-solution",
                organization_id=self.organization.id,
                workspace_id=self.workspace.id,
                from_claim_id=option.id,
                to_claim_id=budget.id,
                relation_type="depends_on",
            )
        )

    def test_dialogue_session_message_persistence_and_isolation(self) -> None:
        session = DialogueSession(
            id="session-1",
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            created_by_user_id=self.owner.id,
            status="active",
            active_workspace_version_id=self.version.id,
            title="Budget Q&A",
        )
        self.session_service.create_session(session)
        question = DialogueMessage(
            id="msg-1",
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            session_id=session.id,
            workspace_version_id=self.version.id,
            actor_type="user",
            actor_user_id=self.owner.id,
            question_class="constraint_query",
            message_type="question",
            content_text="Какие есть бюджетные ограничения?",
            graph_version="graph-v1",
        )
        answer = DialogueMessage(
            id="msg-2",
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            session_id=session.id,
            workspace_version_id=self.version.id,
            actor_type="assistant",
            actor_user_id=None,
            question_class="constraint_query",
            message_type="answer",
            content_text="Бюджет не должен превышать 500k.",
            graph_version="graph-v1",
        )
        self.session_service.append_message(question)
        self.session_service.append_message(answer)
        history = self.session_service.load_history(session_id=session.id, workspace_id=self.workspace.id)
        self.assertEqual([item.actor_type for item in history], ["user", "assistant"])
        self.assertTrue(all(item.workspace_version_id == self.version.id for item in history))
        self.assertTrue(all(item.graph_version == "graph-v1" for item in history))

        other_workspace, other_version = self._workspace("ws-2", self.organization.id, self.owner.id, 1)
        self.workspaces.upsert(other_workspace, other_version)
        with self.assertRaises(PermissionError):
            self.session_service.load_history(session_id=session.id, workspace_id=other_workspace.id)
        with self.assertRaises(PermissionError):
            self.session_service.append_message(
                DialogueMessage(
                    id="msg-x",
                    organization_id=self.organization.id,
                    workspace_id=other_workspace.id,
                    session_id=session.id,
                    workspace_version_id=other_version.id,
                    actor_type="user",
                    actor_user_id=self.owner.id,
                    question_class="evidence_query",
                    message_type="question",
                    content_text="cross workspace",
                )
            )

    def test_question_router_covers_classes_and_fallbacks(self) -> None:
        self.assertEqual(self.router.route("What are the budget constraints?").question_class, "constraint_query")
        self.assertEqual(self.router.route("What is the root cause of downtime?").question_class, "problem_query")
        self.assertEqual(self.router.route("Which solution should we choose?").question_class, "solution_query")
        self.assertEqual(self.router.route("Give me the final report summary").question_class, "report_query")
        self.assertEqual(self.router.route("Show the source evidence").question_class, "evidence_query")
        self.assertEqual(self.router.route("clarification: budget means total cap").question_class, "clarification_provided")
        fallback = self.router.route("help?")
        self.assertIn(fallback.question_class, {"evidence_query", "clarification_needed"})
        self.assertLess(fallback.confidence_score, 0.5)

    def test_graph_first_retrieval_is_workspace_scoped_and_support_chains_present(self) -> None:
        other_workspace, other_version = self._workspace("ws-foreign", self.organization.id, self.owner.id, 1)
        self.workspaces.upsert(other_workspace, other_version)
        self.claims.create_claim(
            Claim(
                id="claim-foreign",
                organization_id=self.organization.id,
                workspace_id=other_workspace.id,
                workspace_version_id=other_version.id,
                claim_key="budget_limit_foreign",
                claim_type="decision_constraint",
                statement="Foreign workspace budget limit is 999k",
                epistemic_status="accepted",
                confidence_score=0.7,
                source_kind="source_fact",
                source_ref="raw/foreign.md",
            ),
            change_reason="seed",
            changed_by_actor=self.owner.id,
        )
        result = self.retrieval.retrieve(
            workspace_id=self.workspace.id,
            question="What budget limit must we follow?",
            question_class="constraint_query",
        )
        self.assertGreaterEqual(len(result.typed_claims), 1)
        self.assertTrue(any(item.claim.claim_type == "decision_constraint" for item in result.typed_claims))
        self.assertTrue(any(chain["signal_type"] == "support_chain" for chain in result.support_chains))
        self.assertTrue(all(item.claim.workspace_id == self.workspace.id for item in result.typed_claims))

        zero = self.retrieval.retrieve(
            workspace_id=self.workspace.id,
            question="Tell me about a spacecraft engine",
            question_class="constraint_query",
        )
        self.assertIn(zero.outcome, {"needs_clarification", "insufficient_modeled_evidence"})
        self.assertEqual(zero.typed_claims, [])

    def test_section_indexing_bm25_namespace_and_supplementary_flag(self) -> None:
        workspace_root = self.root / self.workspace.id
        workspace_root.mkdir(parents=True, exist_ok=True)
        (workspace_root / "analysis").mkdir(exist_ok=True)
        doc_path = workspace_root / "analysis" / "brief.md"
        doc_path.write_text(
            "# Budget\nBudget limit is explained here.\n# Evidence\nSource evidence supports baseline cost.\n",
            encoding="utf-8",
        )
        artifact = Artifact(
            id="artifact-1",
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            artifact_type="analysis_brief",
            stage_name="analysis",
            artifact_key="analysis/brief.md",
            status="active",
            format="markdown",
            payload={"source_refs": ["raw/input.md"]},
            file_path="analysis/brief.md",
        )
        docs = self.bm25.index_sections(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            artifacts=[artifact],
            workspace_root=workspace_root,
            revision=1,
            source_revision="artifact-r1",
        )
        self.assertEqual(len(docs), 2)

        other_workspace_root = self.root / "ws-other"
        other_workspace_root.mkdir(parents=True, exist_ok=True)
        (other_workspace_root / "analysis").mkdir(exist_ok=True)
        (other_workspace_root / "analysis" / "brief.md").write_text("# Budget\nOther org budget details.\n", encoding="utf-8")
        outsider = User(
            id="owner-2",
            email="owner2@example.com",
            password_hash="hash",
            display_name="Owner Two",
            status="active",
        )
        self.users.upsert(outsider)
        self.user_profiles.upsert(UserProfile(user_id=outsider.id))
        other_org = Organization(id="org-2", name="Org Two", slug="org-two", owner_user_id=outsider.id)
        self.org_service.create_organization(other_org)
        other_workspace, other_version = self._workspace("ws-other", other_org.id, outsider.id, 1)
        self.workspaces.upsert(other_workspace, other_version)
        other_artifact = Artifact(
            id="artifact-2",
            organization_id=other_org.id,
            workspace_id=other_workspace.id,
            workspace_version_id=other_version.id,
            artifact_type="analysis_brief",
            stage_name="analysis",
            artifact_key="analysis/brief.md",
            status="active",
            format="markdown",
            payload={},
            file_path="analysis/brief.md",
        )
        self.bm25.index_sections(
            organization_id=other_org.id,
            workspace_id=other_workspace.id,
            artifacts=[other_artifact],
            workspace_root=other_workspace_root,
            revision=1,
            source_revision="artifact-r1",
        )

        hits = self.bm25.search(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            query="budget evidence",
        )
        self.assertTrue(hits)
        self.assertTrue(all(hit.supplementary_only for hit in hits))
        self.assertTrue(all(hit.chunk_id.startswith(f"{self.workspace.id}:") for hit in hits))

    def test_grounding_bundle_and_prompt_prevent_cross_workspace_leaks(self) -> None:
        retrieval = self.retrieval.retrieve(
            workspace_id=self.workspace.id,
            question="What budget limit must we follow?",
            question_class="constraint_query",
        )
        fragments = [
            TextFragment(
                chunk_id=f"{self.workspace.id}:chunk:1",
                section_title="Budget",
                text="Budget section",
                supplementary_only=True,
                score=1.0,
            ),
            TextFragment(
                chunk_id="foreign:chunk:2",
                section_title="Foreign",
                text="Should be dropped",
                supplementary_only=True,
                score=0.5,
            ),
        ]
        bundle = self.grounding.build(
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            graph_version="graph-v1",
            question_class="constraint_query",
            typed_claims=retrieval.typed_claims,
            text_fragments=fragments,
        )
        self.assertEqual(bundle.workspace_version_id, self.version.id)
        self.assertEqual(bundle.graph_version, "graph-v1")
        self.assertEqual(len(bundle.text_fragments), 1)
        prompt = self.prompt_builder.build(bundle, "What budget limit must we follow?")
        self.assertIn("VERIFIED CLAIMS", prompt)
        self.assertIn("SUPPORTING TEXT", prompt)
        self.assertIn("EPISTEMIC RULES", prompt)
        self.assertNotIn("Should be dropped", prompt)

    def test_embedding_lifecycle_marks_stale_switches_active_set_and_retries(self) -> None:
        self.retrieval_chunks.add_chunks(
            [
                RetrievalChunk(
                    id=f"{self.workspace.id}:chunk:a",
                    organization_id=self.organization.id,
                    workspace_id=self.workspace.id,
                    artifact_id=None,
                    claim_id="claim-budget",
                    chunk_key=f"{self.organization.id}:{self.workspace.id}:a",
                    chunk_text="budget chunk",
                    section_title="Budget",
                    status="active",
                    retrieval_revision=1,
                    source_revision="r1",
                    freshness_status="fresh",
                    is_active=True,
                ),
                RetrievalChunk(
                    id=f"{self.workspace.id}:chunk:b",
                    organization_id=self.organization.id,
                    workspace_id=self.workspace.id,
                    artifact_id=None,
                    claim_id="claim-budget",
                    chunk_key=f"{self.organization.id}:{self.workspace.id}:b",
                    chunk_text="budget chunk new",
                    section_title="Budget",
                    status="active",
                    retrieval_revision=2,
                    source_revision="r2",
                    freshness_status="stale",
                    is_active=False,
                ),
            ]
        )
        job = self.embedding.create_job_for_claim_change(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            claim_id="claim-budget",
            source_revision="r2",
        )
        active_before = self.retrieval_chunks.list_for_workspace(self.workspace.id, active_only=True)
        self.assertEqual(active_before, [])
        failed = self.embedding.fail_job(job_id=job.id, error="timeout")
        self.assertEqual(failed.status, "failed")
        retried = self.embedding.retry_failed_job(job.id)
        self.assertEqual(retried.status, "queued")
        completed = self.embedding.complete_job(job_id=job.id, activate_revision=2)
        self.assertEqual(completed.status, "completed")
        active_after = self.retrieval_chunks.list_for_workspace(self.workspace.id, active_only=True)
        self.assertEqual([chunk.retrieval_revision for chunk in active_after], [2])

    def test_provider_policy_quota_and_dialogue_orchestration(self) -> None:
        session = DialogueSession(
            id="session-orchestrator",
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            created_by_user_id=self.owner.id,
            status="active",
            active_workspace_version_id=self.version.id,
            title="Dialogue",
        )
        self.session_service.create_session(session)
        workspace_root = self.root / self.workspace.id
        workspace_root.mkdir(parents=True, exist_ok=True)
        (workspace_root / "analysis").mkdir(exist_ok=True)
        (workspace_root / "analysis" / "support.md").write_text("# Support\nSupplementary support text.\n", encoding="utf-8")
        artifact = Artifact(
            id="artifact-support",
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            artifact_type="analysis_note",
            stage_name="analysis",
            artifact_key="analysis/support.md",
            status="active",
            format="markdown",
            payload={},
            file_path="analysis/support.md",
        )
        self.bm25.index_sections(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            artifacts=[artifact],
            workspace_root=workspace_root,
            revision=1,
            source_revision="artifact-r1",
        )
        calls: list[tuple[str, str]] = []

        def direct_callable(prompt: str, model_key: str):
            calls.append((prompt, model_key))
            return {"text": "Grounded answer", "usage": {"estimated_cost": 1.0}, "provider": "direct"}

        adapter = LLMProviderAdapter(mode="direct", direct_callable=direct_callable)
        orchestrator = DialogueOrchestrator(
            dialogue_sessions=self.session_service,
            router=self.router,
            retrieval=self.retrieval,
            bm25=self.bm25,
            grounding=self.grounding,
            prompts=self.prompt_builder,
            quota=self.quota,
            provider=adapter,
            policy=self.policy,
        )
        bundle, response = orchestrator.answer(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            graph_version="graph-v1",
            user_id=self.owner.id,
            session_id=session.id,
            question="What budget limit must we follow?",
            budget_profile="standard",
        )
        self.assertEqual(response.tier, "balanced")
        self.assertEqual(len(calls), 1)
        history = self.session_service.load_history(session_id=session.id, workspace_id=self.workspace.id)
        self.assertEqual([item.message_type for item in history], ["question", "answer"])
        self.assertIn("typed_claims", history[1].grounding_bundle_ref)
        self.assertEqual(bundle.workspace_id, self.workspace.id)

        strict_orchestrator = DialogueOrchestrator(
            dialogue_sessions=self.session_service,
            router=self.router,
            retrieval=self.retrieval,
            bm25=self.bm25,
            grounding=self.grounding,
            prompts=self.prompt_builder,
            quota=self.quota,
            provider=adapter,
            policy=self.policy,
        )
        with self.assertRaises(PermissionError):
            strict_orchestrator.answer(
                organization_id=self.organization.id,
                workspace_id=self.workspace.id,
                workspace_version_id=self.version.id,
                graph_version="graph-v1",
                user_id=self.owner.id,
                session_id=session.id,
                question="Which solution should we choose?",
                budget_profile="strict_cap",
                risk_level="high",
            )
        self.assertEqual(self.policy.escalate("cheap"), "balanced")
        self.assertEqual(self.policy.escalate("balanced"), "premium")
        with self.assertRaises(ValueError):
            self.policy.escalate("premium")


if __name__ == "__main__":
    unittest.main()
