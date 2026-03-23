from __future__ import annotations

import io
import json
import os
import tempfile
from pathlib import Path
import unittest

from app.api_server import application
from app.canonical_db.claim_graph import ClaimGraphService
from app.canonical_db.config import DatabaseConfig, connect
from app.canonical_db.domain import (
    Artifact,
    Claim,
    ClaimRelation,
    DialogueSession,
    GovernanceEvent,
    MaterializedArtifactIndexEntry,
    Organization,
    ProjectionSnapshot,
    User,
    UserProfile,
    Workspace,
    WorkspaceVersion,
)
from app.canonical_db.migration_runner import upgrade
from app.canonical_db.model_updates import (
    ClarificationEngine,
    InputAcceptanceCheck,
    ModelUpdateEngine,
    ReentryPlanner,
    ReentryWorker,
    SqliteQuestionQueueRepository,
    SqliteReentryJobRepository,
    TypedInputClassifier,
    build_diff_panel,
)
from app.canonical_db.projections import MaterializedArtifactIndex, ProjectionRegistry, ProjectionService
from app.canonical_db.repositories import (
    SqliteClaimRepository,
    SqliteGovernanceEventRepository,
    SqliteMaterializedArtifactIndexRepository,
    SqliteMembershipRepository,
    SqliteOrganizationRepository,
    SqliteProjectionSnapshotRepository,
    SqliteDialogueSessionRepository,
    SqliteUserProfileRepository,
    SqliteUserRepository,
    SqliteWorkspaceRepository,
    TransactionManager,
)
from app.canonical_db.tenant_auth import OrganizationService


class BrokenProjectionService:
    def rebuild_workspace_projections(self, **kwargs):
        raise RuntimeError("projection rebuild failed")


class Sprint05ModelUpdatesReentryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db_path = self.root / "canonical.sqlite3"
        self.config = DatabaseConfig(dsn=f"sqlite:///{self.db_path}", environment="test")
        self.old_dsn = os.environ.get("CANONICAL_DB_DSN")
        os.environ["CANONICAL_DB_DSN"] = self.config.dsn

        def factory():
            return connect(self.config)

        self.factory = factory
        with self.factory() as connection:
            upgrade(connection, target="head")

        self.users = SqliteUserRepository(self.factory)
        self.profiles = SqliteUserProfileRepository(self.factory)
        self.memberships = SqliteMembershipRepository(self.factory)
        self.organizations = SqliteOrganizationRepository(self.factory)
        self.workspaces = SqliteWorkspaceRepository(self.factory)
        self.claims = SqliteClaimRepository(self.factory, TransactionManager(self.factory))
        self.governance = SqliteGovernanceEventRepository(self.factory)
        self.snapshots = SqliteProjectionSnapshotRepository(self.factory)
        self.materialized_entries = SqliteMaterializedArtifactIndexRepository(self.factory, TransactionManager(self.factory))
        self.question_queue = SqliteQuestionQueueRepository(self.factory)
        self.reentry_jobs = SqliteReentryJobRepository(self.factory, TransactionManager(self.factory))
        self.dialogue_sessions = SqliteDialogueSessionRepository(self.factory)
        self.org_service = OrganizationService(self.organizations, self.memberships, self.profiles)
        self.registry = ProjectionRegistry()
        self.projection_service = ProjectionService(self.claims, self.snapshots, self.registry)
        self.artifact_index = MaterializedArtifactIndex(self.registry, self.materialized_entries)
        self.clarifications = ClarificationEngine(self.question_queue)
        self.classifier = TypedInputClassifier()
        self.acceptance = InputAcceptanceCheck(self.claims)
        self.update_engine = ModelUpdateEngine(self.claims, self.governance, self.projection_service)
        self.reentry_planner = ReentryPlanner(self.registry, self.artifact_index, self.snapshots)
        self.reentry_worker = ReentryWorker(
            self.reentry_jobs,
            self.workspaces,
            self.projection_service,
            self.governance,
        )

        self.owner = User(
            id="owner-1",
            email="owner@example.com",
            password_hash="hash",
            display_name="Owner",
            status="active",
        )
        self.users.upsert(self.owner)
        self.profiles.upsert(UserProfile(user_id=self.owner.id))
        self.organization = Organization(id="org-1", name="Org One", slug="org-one", owner_user_id=self.owner.id)
        self.org_service.create_organization(self.organization)
        self.workspace = Workspace(
            id="ws-1",
            organization_id=self.organization.id,
            workspace_key="ws-1",
            title="Update Workspace",
            case_type="analysis_case",
            status="active",
            current_stage="analysis",
            active_model_version=1,
            created_by_user_id=self.owner.id,
            metadata={},
        )
        self.version_1 = WorkspaceVersion(
            id="ws-1:v1",
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            version_no=1,
            version_label="v1",
            change_reason="seed",
            created_by=self.owner.id,
        )
        self.version_2 = WorkspaceVersion(
            id="ws-1:v2",
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            version_no=2,
            version_label="v2",
            change_reason="clarification accepted",
            created_by=self.owner.id,
        )
        self.workspaces.upsert(self.workspace, self.version_1)
        self.workspaces.upsert(self.workspace, self.version_2)
        self.claim_graph = ClaimGraphService(self.claims)
        self._seed_claims()
        self.projection_service.rebuild_workspace_projections(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version_1.id,
        )
        self.artifact_index.rebuild(organization_id=self.organization.id, workspace_id=self.workspace.id)

    def tearDown(self) -> None:
        if self.old_dsn is None:
            os.environ.pop("CANONICAL_DB_DSN", None)
        else:
            os.environ["CANONICAL_DB_DSN"] = self.old_dsn
        self.tmp.cleanup()

    def _seed_claims(self) -> None:
        budget = self.claim_graph.create_claim(
            Claim(
                id="claim-budget",
                organization_id=self.organization.id,
                workspace_id=self.workspace.id,
                workspace_version_id=self.version_1.id,
                claim_key="budget_limit",
                claim_type="decision_constraint",
                statement="Budget limit must not exceed 500k",
                epistemic_status="accepted",
                confidence_score=0.9,
                source_kind="source_fact",
                source_ref="seed.md",
            ),
            changed_by_actor=self.owner.id,
            change_reason="seed",
        )
        baseline = self.claim_graph.create_claim(
            Claim(
                id="claim-baseline",
                organization_id=self.organization.id,
                workspace_id=self.workspace.id,
                workspace_version_id=self.version_1.id,
                claim_key="baseline_cost",
                claim_type="source_fact",
                statement="Current baseline cost is 420k",
                epistemic_status="accepted",
                confidence_score=0.8,
                source_kind="source_fact",
                source_ref="seed.md",
            ),
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

    def _call(self, path: str, *, method: str = "GET", payload: dict | None = None, query: str = ""):
        captured: dict[str, object] = {}

        def start_response(status, headers):
            captured["status"] = status
            captured["headers"] = headers

        body = json.dumps(payload).encode("utf-8") if payload is not None else b""
        result = application(
            {
                "PATH_INFO": path,
                "QUERY_STRING": query,
                "REQUEST_METHOD": method,
                "CONTENT_LENGTH": str(len(body)),
                "wsgi.input": io.BytesIO(body),
            },
            start_response,
        )
        return captured["status"], b"".join(result).decode("utf-8")

    def test_clarification_queue_lifecycle_and_open_questions_api(self) -> None:
        item = self.clarifications.open_question(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            session_id=None,
            reason="MISSING_BUDGET_BASIS",
            missing_knowledge="What budget basis should we use for vendor quotes?",
            impact_preview="Budgeting and selection stages will be affected.",
        )
        self.assertEqual(item.status, "open")
        self.assertEqual(item.reason_code, "MISSING_BUDGET_BASIS")
        self.assertIn("Budgeting", item.impact_preview)

        answered = self.clarifications.mark_answered(item)
        self.assertEqual(answered.status, "answered")
        rejected = self.clarifications.mark_rejected(answered, rationale="superseded by another clarification")
        self.assertEqual(rejected.status, "rejected")
        obsolete = self.clarifications.mark_obsolete(rejected)
        self.assertEqual(obsolete.status, "obsolete")

        fresh = self.clarifications.open_question(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            session_id=None,
            reason="MISSING_SCHEDULE_RULE",
            missing_knowledge="Can we move the delivery deadline by one month?",
            impact_preview="Reporting stage depends on the answer.",
        )
        self.assertEqual(fresh.status, "open")

        status, body = self._call(f"/api/workspaces/{self.workspace.id}/open-questions")
        self.assertEqual(status, "200 OK")
        payload = json.loads(body)
        self.assertEqual(len(payload["unknowns"]), 1)
        self.assertEqual(payload["unknowns"][0]["reason"], "MISSING_SCHEDULE_RULE")
        self.assertEqual(payload["unknowns"][0]["status"], "open")

    def test_typed_input_classifier_covers_provisional_types_and_audit_metadata(self) -> None:
        constraint = self.classifier.classify("Budget must stay below 550k")
        self.assertEqual(constraint.provisional_type, "user_declared_constraint")
        self.assertEqual(constraint.route, "model_update")
        self.assertGreater(constraint.confidence, 0.7)

        target = self.classifier.classify("Our goal is to cut downtime by 20 percent")
        self.assertEqual(target.provisional_type, "user_normative_target")

        hypothesis = self.classifier.classify("Maybe the baseline estimate is too optimistic")
        self.assertEqual(hypothesis.provisional_type, "user_hypothesis")
        self.assertEqual(hypothesis.route, "clarification_provided")

        asserted = self.classifier.classify("Vendor quotes are based on the revised scope")
        self.assertEqual(asserted.provisional_type, "user_asserted_fact")
        self.assertTrue(asserted.rationale)

    def test_input_acceptance_rejects_questions_conditionals_and_conflicts(self) -> None:
        conditional = self.classifier.classify("If budget is 800k then we can expand scope")
        decision = self.acceptance.evaluate(
            workspace_id=self.workspace.id,
            text="If budget is 800k then we can expand scope",
            classification=conditional,
        )
        self.assertEqual(decision.status, "rejected")
        self.assertEqual(decision.reason_code, "CONDITIONAL_INPUT")

        question = self.classifier.classify("Can we move the deadline?")
        question_result = self.acceptance.evaluate(
            workspace_id=self.workspace.id,
            text="Can we move the deadline?",
            classification=question,
        )
        self.assertEqual(question_result.status, "rejected")
        self.assertEqual(question_result.reason_code, "QUESTION_AS_STATEMENT")

        conflict = self.classifier.classify("Current baseline cost is not 420k")
        deferred = self.acceptance.evaluate(
            workspace_id=self.workspace.id,
            text="Current baseline cost is not 420k",
            classification=conflict,
        )
        self.assertEqual(deferred.status, "deferred")
        self.assertEqual(deferred.reason_code, "CONFLICTS_WITH_STABLE_CLAIM")
        self.assertEqual(len(self.claims.list_for_workspace(self.workspace.id)), 2)

    def test_model_update_creates_intermediate_claim_and_promotion_lineage(self) -> None:
        classification = self.classifier.classify("Budget should include contingency reserve")
        created = self.update_engine.create_intermediate_claim(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version_2.id,
            user_id=self.owner.id,
            source_text="Budget should include contingency reserve",
            classification=classification,
        )
        self.assertEqual(created.epistemic_status, "provisional_user_input")
        self.assertEqual(created.claim_type, "decision_constraint")
        self.assertEqual(created.source_kind, "dialogue_clarification")
        self.assertEqual(created.attributes["actor"], "user")
        self.assertEqual(created.attributes["workspace_version_context"], self.version_2.id)

        versions = self.claims.list_versions(created.id)
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0].change_reason, "clarification_accepted")

        promoted = self.update_engine.promote_claim(
            claim_id=created.id,
            target_type="source_fact",
            workspace_version_id=self.version_2.id,
            actor_id="reviewer-1",
        )
        self.assertEqual(promoted.claim_type, "source_fact")
        self.assertEqual(promoted.epistemic_status, "accepted")
        promoted_versions = self.claims.list_versions(created.id)
        self.assertEqual(len(promoted_versions), 2)
        self.assertEqual(promoted_versions[-1].change_reason, "lawful_promotion")
        self.assertEqual(promoted_versions[-1].attributes["promoted_to"], "source_fact")
        self.assertEqual(promoted_versions[-1].source_kind, "dialogue_clarification")

        event_types = [event.event_type for event in self.governance.list_for_workspace(self.workspace.id)]
        self.assertIn("claim_created", event_types)
        self.assertIn("claim_promoted", event_types)

    def test_reentry_planner_marks_stale_without_hardcoded_stage_map(self) -> None:
        classification = self.classifier.classify("Budget must remain below 530k")
        claim = self.update_engine.create_intermediate_claim(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version_2.id,
            user_id=self.owner.id,
            source_text="Budget must remain below 530k",
            classification=classification,
        )
        plan = self.reentry_planner.plan(workspace_id=self.workspace.id, claim=claim)
        self.assertTrue(plan.dependent_projections)
        self.assertIn("problem_factory_projection", plan.dependent_projections)
        self.assertIn("problem_factory", plan.affected_stages)
        self.assertTrue(any(output.endswith(".json") or output.endswith(".md") for output in plan.stale_outputs))

        snapshots = self.snapshots.list_for_workspace(self.workspace.id)
        stale_types = {snapshot.projection_type for snapshot in snapshots if snapshot.freshness_status == "stale"}
        self.assertTrue(set(plan.dependent_projections).issubset(stale_types))

    def test_reentry_worker_updates_version_state_and_diff_panel(self) -> None:
        classification = self.classifier.classify("Budget must remain below 530k")
        claim = self.update_engine.create_intermediate_claim(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version_2.id,
            user_id=self.owner.id,
            source_text="Budget must remain below 530k",
            classification=classification,
        )
        self.update_engine.promote_claim(
            claim_id=claim.id,
            target_type="decision_constraint",
            workspace_version_id=self.version_2.id,
            actor_id="reviewer-1",
        )
        self.governance.append(
            GovernanceEvent(
                id="gov:claim-budget:updated",
                organization_id=self.organization.id,
                workspace_id=self.workspace.id,
                event_type="claim_updated",
                payload={"claim_id": "claim-budget"},
                actor_type="system",
                actor_id="test",
            )
        )
        self.governance.append(
            GovernanceEvent(
                id="gov:claim-budget:degraded",
                organization_id=self.organization.id,
                workspace_id=self.workspace.id,
                event_type="claim_degraded",
                payload={"claim_id": "claim-budget"},
                actor_type="system",
                actor_id="test",
            )
        )
        plan = self.reentry_planner.plan(workspace_id=self.workspace.id, claim=claim)
        job = self.reentry_worker.submit(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            pending_version=self.version_2,
            plan=plan,
        )
        queued = self.reentry_jobs.get(job.id)
        self.assertEqual(queued.status, "queued")

        self.reentry_jobs.try_lock_workspace(self.workspace.id)
        with self.assertRaises(PermissionError):
            self.reentry_worker.execute(job.id)
        self.reentry_jobs.release_workspace(self.workspace.id, status="idle")

        executed = self.reentry_worker.execute(job.id)
        self.assertEqual(executed.status, "completed")
        self.assertEqual(self.workspaces.get(self.workspace.id).active_model_version, 2)
        self.assertEqual(self.workspaces.get(self.workspace.id).reentry_status, "idle")

        status, body = self._call(
            "/api/dialogue/ask",
            method="POST",
            payload={
                "organization_id": self.organization.id,
                "workspace_id": self.workspace.id,
                "session_id": "session-1",
                "user_id": self.owner.id,
                "question": "What budget constraint is currently published?",
                "budget_profile": "standard",
            },
        )
        self.assertEqual(status, "200 OK")
        answer = json.loads(body)["answer"]
        self.assertNotIn("Disclaimer: re-entry is in progress", answer["text"])

        self.reentry_jobs.try_lock_workspace(self.workspace.id)
        status, body = self._call(
            "/api/dialogue/ask",
            method="POST",
            payload={
                "organization_id": self.organization.id,
                "workspace_id": self.workspace.id,
                "session_id": "session-2",
                "user_id": self.owner.id,
                "question": "What budget constraint is currently published?",
                "budget_profile": "standard",
            },
        )
        self.assertEqual(status, "200 OK")
        answer = json.loads(body)["answer"]
        self.assertIn("Disclaimer: re-entry is in progress", answer["text"])
        self.reentry_jobs.release_workspace(self.workspace.id, status="idle")

        status, body = self._call(f"/api/workspaces/{self.workspace.id}/version-state")
        version_state = json.loads(body)
        self.assertEqual(version_state["current_published_version"], self.version_2.id)
        self.assertIsNone(version_state["pending_version"])
        self.assertIn("problem_factory", version_state["affected_stages"])

        status, body = self._call(f"/api/workspaces/{self.workspace.id}/diff-panel")
        diff_panel = json.loads(body)
        event_types = [item["event_type"] for item in diff_panel["events"]]
        self.assertIn("claim_created", event_types)
        self.assertIn("claim_updated", event_types)
        self.assertIn("claim_promoted", event_types)
        self.assertIn("claim_degraded", event_types)
        self.assertIn("projection_refreshed", event_types)
        self.assertIn("stage_recomputed", event_types)

    def test_reentry_worker_failure_marks_job_failed_and_keeps_published_version(self) -> None:
        broken_worker = ReentryWorker(
            self.reentry_jobs,
            self.workspaces,
            BrokenProjectionService(),
            self.governance,
        )
        claim = self.update_engine.create_intermediate_claim(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version_2.id,
            user_id=self.owner.id,
            source_text="Budget should include a 5 percent reserve",
            classification=self.classifier.classify("Budget should include a 5 percent reserve"),
        )
        plan = self.reentry_planner.plan(workspace_id=self.workspace.id, claim=claim)
        job = broken_worker.submit(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            pending_version=self.version_2,
            plan=plan,
        )
        with self.assertRaises(RuntimeError):
            broken_worker.execute(job.id)

        failed = self.reentry_jobs.get(job.id)
        self.assertEqual(failed.status, "failed")
        self.assertEqual(self.workspaces.get(self.workspace.id).active_model_version, 1)
        self.assertEqual(self.workspaces.get(self.workspace.id).reentry_status, "failed")

    def test_build_diff_panel_filters_supported_events(self) -> None:
        for index, event_type in enumerate(
            [
                "claim_created",
                "claim_updated",
                "claim_promoted",
                "claim_degraded",
                "projection_refreshed",
                "stage_recomputed",
                "unrelated_event",
            ],
            start=1,
        ):
            self.governance.append(
                GovernanceEvent(
                    id=f"gov:{index}",
                    organization_id=self.organization.id,
                    workspace_id=self.workspace.id,
                    event_type=event_type,
                    payload={"n": index},
                    actor_type="system",
                    actor_id="tester",
                )
            )
        panel = build_diff_panel(self.governance, self.workspace.id)
        self.assertEqual(
            [item["event_type"] for item in panel],
            [
                "claim_created",
                "claim_updated",
                "claim_promoted",
                "claim_degraded",
                "projection_refreshed",
                "stage_recomputed",
            ],
        )
