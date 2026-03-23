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
from app.canonical_db.decision_assurance import (
    DecisionAssuranceEngine,
    SqliteDecisionAssuranceSnapshotRepository,
    SqliteDecisionWaiverRepository,
)
from app.canonical_db.decision_domain import (
    DecisionComparisonService,
    DecisionContractService,
    DecisionOptionEngine,
    DecisionReviewService,
    ProblemFrameBuilder,
    SqliteDecisionComparisonRepository,
    SqliteDecisionDraftRepository,
    SqliteDecisionEvidenceLinkRepository,
    SqliteDecisionOptionRepository,
    SqliteDecisionOutcomeRepository,
    SqliteDecisionRecordRepository,
    SqliteDecisionReviewRepository,
    SqliteProblemFrameRepository,
)
from app.canonical_db.decision_retrieval import DecisionPatternRetrievalService, DecisionReusePolicy, DecisionReviewWorkflow
from app.canonical_db.domain import (
    Claim,
    ClaimRelation,
    DecisionEvidenceLink,
    Organization,
    User,
    UserProfile,
    Workspace,
    WorkspaceVersion,
)
from app.canonical_db.migration_runner import upgrade
from app.canonical_db.repositories import (
    SqliteClaimRepository,
    SqliteGovernanceEventRepository,
    SqliteMembershipRepository,
    SqliteOrganizationRepository,
    SqliteUserProfileRepository,
    SqliteUserRepository,
    SqliteWorkspaceRepository,
    TransactionManager,
)
from app.canonical_db.tenant_auth import OrganizationService


class Sprint10DecisionRetrievalUxTests(unittest.TestCase):
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
        self.claim_graph = ClaimGraphService(self.claims)
        self.org_service = OrganizationService(self.organizations, self.memberships, self.profiles)

        self.frames = SqliteProblemFrameRepository(self.factory)
        self.options = SqliteDecisionOptionRepository(self.factory)
        self.comparisons = SqliteDecisionComparisonRepository(self.factory)
        self.drafts = SqliteDecisionDraftRepository(self.factory)
        self.records = SqliteDecisionRecordRepository(self.factory)
        self.links = SqliteDecisionEvidenceLinkRepository(self.factory, TransactionManager(self.factory))
        self.reviews = SqliteDecisionReviewRepository(self.factory)
        self.outcomes = SqliteDecisionOutcomeRepository(self.factory)
        self.snapshots = SqliteDecisionAssuranceSnapshotRepository(self.factory)
        self.waivers = SqliteDecisionWaiverRepository(self.factory)
        self.review_service = DecisionReviewService(self.reviews, self.records)
        self.frame_builder = ProblemFrameBuilder(
            self.frames, self.options, self.comparisons, self.drafts, self.records, self.reviews, self.governance
        )
        self.option_engine = DecisionOptionEngine(self.options, self.governance)
        self.comparison_service = DecisionComparisonService(self.comparisons, self.governance)
        self.contract_service = DecisionContractService(
            self.drafts, self.records, self.links, self.outcomes, self.review_service, self.governance
        )
        self.assurance = DecisionAssuranceEngine(
            self.records, self.links, self.outcomes, self.snapshots, self.waivers, self.reviews, self.governance
        )
        self.retrieval = DecisionPatternRetrievalService(
            self.factory, self.records, self.comparisons, self.snapshots, self.outcomes, self.governance
        )
        self.policy = DecisionReusePolicy()
        self.workflow = DecisionReviewWorkflow(self.records, self.reviews, self.governance)

        self.owner = User(id="owner-1", email="owner@example.com", password_hash="hash", display_name="Owner", status="active")
        self.users.upsert(self.owner)
        self.profiles.upsert(UserProfile(user_id=self.owner.id))
        self.org = Organization(
            id="org-1",
            name="Org One",
            slug="org-one",
            owner_user_id=self.owner.id,
            metadata={"decision_reuse_mode": "suggestion-only"},
        )
        self.org_service.create_organization(self.org)
        self.ws1 = self._create_workspace("ws-1", metadata={"decision_reuse_mode": "prefilled-option"})
        self.ws2 = self._create_workspace("ws-2")
        self.org2 = Organization(id="org-2", name="Org Two", slug="org-two", owner_user_id=self.owner.id)
        self.org_service.create_organization(self.org2)
        self.ws_other = self._create_workspace("ws-x", organization=self.org2)

        self._seed_claims(self.ws1, "ws-1:v1")
        self._seed_claims(self.ws2, "ws-2:v1")
        self._seed_claims(self.ws_other, "ws-x:v1")
        self.record1 = self._create_decision(self.ws1, "ws-1:v1", "cost_cut", conflict=False)
        self.record2 = self._create_decision(self.ws2, "ws-2:v1", "cost_cut_history", conflict=True)
        self._create_decision(self.ws_other, "ws-x:v1", "foreign_pattern", conflict=False)

    def tearDown(self) -> None:
        if self.old_dsn is None:
            os.environ.pop("CANONICAL_DB_DSN", None)
        else:
            os.environ["CANONICAL_DB_DSN"] = self.old_dsn
        self.tmp.cleanup()

    def _create_workspace(self, workspace_id: str, organization: Organization | None = None, metadata: dict | None = None) -> Workspace:
        organization = organization or self.org
        workspace = Workspace(
            id=workspace_id,
            organization_id=organization.id,
            workspace_key=workspace_id,
            title=f"Workspace {workspace_id}",
            case_type="analysis_case",
            status="active",
            current_stage="analysis",
            active_model_version=1,
            created_by_user_id=self.owner.id,
            metadata=metadata or {},
        )
        version = WorkspaceVersion(
            id=f"{workspace_id}:v1",
            organization_id=organization.id,
            workspace_id=workspace_id,
            version_no=1,
            version_label="v1",
            change_reason="seed",
            created_by=self.owner.id,
        )
        self.workspaces.upsert(workspace, version)
        return workspace

    def _seed_claims(self, workspace: Workspace, version_id: str) -> None:
        budget = self.claim_graph.create_claim(
            Claim(
                id=f"{workspace.id}-budget",
                organization_id=workspace.organization_id,
                workspace_id=workspace.id,
                workspace_version_id=version_id,
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
                id=f"{workspace.id}-baseline",
                organization_id=workspace.organization_id,
                workspace_id=workspace.id,
                workspace_version_id=version_id,
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
                id=f"{workspace.id}-rel-support",
                organization_id=workspace.organization_id,
                workspace_id=workspace.id,
                from_claim_id=baseline.id,
                to_claim_id=budget.id,
                relation_type="supports",
            )
        )

    def _create_decision(self, workspace: Workspace, version_id: str, suffix: str, *, conflict: bool) -> object:
        frame = self.frame_builder.build(
            organization_id=workspace.organization_id,
            workspace_id=workspace.id,
            workspace_version_id=version_id,
            root_problem="Need to choose a cost reduction path.",
            supporting_claims=self.claims.list_for_workspace(workspace.id),
            unresolved_unknowns=[],
            active_constraints=["budget <= 500k"],
            success_criteria=["reduce costs"],
            scope_boundary="procurement",
        )
        option = self.option_engine.materialize(
            organization_id=workspace.organization_id,
            workspace_id=workspace.id,
            workspace_version_id=version_id,
            problem_frame_id=frame.id,
            option_key=suffix,
            title=f"Option {suffix}",
            summary_text="Controlled rollout with rollback",
            assumptions=["vendor cooperates"],
            confidence_in_assumptions=0.8,
            benefits=["cost reduction"],
            costs=["negotiation effort"],
            risks=["vendor refuses"],
            prerequisites=["negotiation plan"],
        )
        comparison = self.comparison_service.compare(
            organization_id=workspace.organization_id,
            workspace_id=workspace.id,
            workspace_version_id=version_id,
            problem_frame_id=frame.id,
            options=[option],
            selected_option_id=option.id,
        )
        link = DecisionEvidenceLink(
            id=f"del:{workspace.id}:{suffix}",
            organization_id=workspace.organization_id,
            workspace_id=workspace.id,
            workspace_version_id=version_id,
            decision_record_id=None,
            decision_option_id=option.id,
            link_type="supports" if not conflict else "contextualizes",
            link_strength=0.85,
            link_direction="contradicts" if conflict else "supports",
            source_ref="claim:budget_limit",
            criticality="standard",
            claim_id=f"{workspace.id}-budget",
        )
        draft = self.contract_service.create_draft(
            organization_id=workspace.organization_id,
            workspace_id=workspace.id,
            workspace_version_id=version_id,
            frame=frame,
            comparison=comparison,
            evidence_links=[link],
            rationale=["budget claim available"],
        )
        record = self.contract_service.promote(
            draft=draft,
            comparison=comparison,
            evidence_links=[link],
            decision_basis=["budget_limit", "baseline_cost"],
            limitations=[],
            review_due=None,
            actor_id=self.owner.id,
        )
        if workspace.id == "ws-2":
            self.contract_service.record_outcome(
                record_id=record.id,
                outcome_type="implemented_successfully",
                outcome_score=0.9,
                source="operator_confirmed",
                evidence={"ticket": "OPS-7"},
            )
        self.assurance.recompute(decision_record_id=record.id, now="2026-03-23T00:00:00+00:00", trigger="seed")
        return record

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

    def test_reuse_policy_hierarchy_and_namespace_safe_retrieval(self) -> None:
        mode = self.policy.resolve_mode(
            organization_metadata=self.org.metadata,
            workspace_metadata=self.ws1.metadata,
            requested_mode="prefilled-option",
        )
        self.assertEqual(mode, "suggestion-only")
        patterns = self.retrieval.retrieve(
            organization_id=self.org.id,
            workspace=self.ws1,
            question="Which decision should we choose to reduce costs?",
            reuse_mode=mode,
        )
        self.assertTrue(patterns)
        self.assertTrue(all(item.source_workspace_id != self.ws_other.id for item in patterns))

    def test_conflict_detection_and_outcome_aware_ranking(self) -> None:
        patterns = self.retrieval.retrieve(
            organization_id=self.org.id,
            workspace=self.ws1,
            question="Need a cost reduction decision with rollback",
            reuse_mode="suggestion-only",
        )
        self.assertTrue(patterns)
        top = patterns[0]
        self.assertEqual(top.source_workspace_id, self.ws1.id)
        conflicting = next(item for item in patterns if item.source_workspace_id == self.ws2.id)
        self.assertTrue(conflicting.conflict)
        self.assertEqual(conflicting.reuse_eligibility, "blocked")
        self.assertLess(conflicting.final_score, top.final_score)

    def test_decision_query_response_contains_structured_payload_and_provenance(self) -> None:
        status, body = self._call(
            "/api/dialogue/ask",
            method="POST",
            payload={
                "organization_id": self.org.id,
                "workspace_id": self.ws1.id,
                "session_id": "session-10",
                "user_id": self.owner.id,
                "question": "Which decision should we choose under the budget limit?",
                "budget_profile": "standard",
                "reuse_mode": "prefilled-option",
            },
        )
        self.assertEqual(status, "200 OK")
        payload = json.loads(body)
        self.assertIn("decision", payload)
        self.assertEqual(payload["decision"]["selected_decision_id"], self.record1.id)
        self.assertTrue(payload["decision"]["historical_patterns"])
        first_pattern = payload["decision"]["historical_patterns"][0]
        self.assertIn("provenance", first_pattern)
        self.assertIn("reuse_eligibility", first_pattern)

    def test_decision_console_and_review_workflow(self) -> None:
        status, body = self._call(f"/api/workspaces/{self.ws1.id}/decision-console")
        self.assertEqual(status, "200 OK")
        payload = json.loads(body)
        self.assertIn("summary_card", payload)
        self.assertIn("assurance", payload)
        self.assertIn("historical_patterns", payload)

        status, body = self._call(
            "/api/decision-review/action",
            method="POST",
            payload={
                "decision_record_id": self.record1.id,
                "action": "approve",
                "actor_id": self.owner.id,
                "expected_status": "selected",
            },
        )
        self.assertEqual(status, "200 OK")
        review = json.loads(body)
        self.assertEqual(review["status"], "closed")

        with self.assertRaises(ValueError):
            self.workflow.apply_action(
                decision_record_id=self.record1.id,
                action="request_revision",
                actor_id=self.owner.id,
                expected_status="selected",
            )


if __name__ == "__main__":
    unittest.main()
