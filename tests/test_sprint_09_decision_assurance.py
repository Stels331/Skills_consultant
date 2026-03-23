from __future__ import annotations

from dataclasses import replace
import os
import tempfile
from pathlib import Path
import unittest

from app.canonical_db.claim_graph import ClaimGraphService
from app.canonical_db.config import DatabaseConfig, connect
from app.canonical_db.decision_assurance import (
    DecisionAssuranceEngine,
    DecisionAssuranceScheduler,
    DecisionOutcomeResolver,
    DecisionWaiverService,
    SqliteDecisionAssuranceSnapshotRepository,
    SqliteDecisionWaiverRepository,
    assurance_payload,
    recompute_scope_from_reentry,
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
from app.canonical_db.domain import (
    Claim,
    ClaimRelation,
    DecisionEvidenceLink,
    GovernanceEvent,
    Organization,
    User,
    UserProfile,
    Workspace,
    WorkspaceVersion,
)
from app.canonical_db.migration_runner import upgrade
from app.canonical_db.model_updates import ReentryJobRecord
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
from app.validation.dialogue_validator import FPFResponseValidator


class Sprint09DecisionAssuranceTests(unittest.TestCase):
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
        self.org_service = OrganizationService(self.organizations, self.memberships, self.profiles)
        self.claim_graph = ClaimGraphService(self.claims)

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
            self.records,
            self.links,
            self.outcomes,
            self.snapshots,
            self.waivers,
            self.reviews,
            self.governance,
        )
        self.scheduler = DecisionAssuranceScheduler(self.records, self.snapshots, self.assurance)
        self.waiver_service = DecisionWaiverService(self.waivers, self.governance)
        self.outcome_resolver = DecisionOutcomeResolver(self.outcomes, self.governance)

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
            title="Assurance Workspace",
            case_type="analysis_case",
            status="active",
            current_stage="analysis",
            active_model_version=1,
            created_by_user_id=self.owner.id,
            metadata={},
        )
        self.version = WorkspaceVersion(
            id="ws-1:v1",
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            version_no=1,
            version_label="v1",
            change_reason="seed",
            created_by=self.owner.id,
        )
        self.workspaces.upsert(self.workspace, self.version)
        self._seed_claims()
        self.record = self._seed_decision_record()

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
                workspace_version_id=self.version.id,
                claim_key="budget_limit",
                claim_type="decision_constraint",
                statement="Budget limit must not exceed 500k",
                epistemic_status="accepted",
                confidence_score=0.92,
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
                workspace_version_id=self.version.id,
                claim_key="baseline_cost",
                claim_type="source_fact",
                statement="Current baseline cost is 420k",
                epistemic_status="accepted",
                confidence_score=0.81,
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

    def _seed_decision_record(self):
        frame = self.frame_builder.build(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            root_problem="Нужно выбрать финансово безопасное решение.",
            supporting_claims=self.claims.list_for_workspace(self.workspace.id),
            unresolved_unknowns=[],
            active_constraints=["Бюджет не выше 500k"],
            success_criteria=["Без превышения бюджета"],
            scope_boundary="Финансовый контур",
        )
        option = self.option_engine.materialize(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            problem_frame_id=frame.id,
            option_key="controlled_rollout",
            title="Контролируемый rollout",
            summary_text="С откатом и контрольными точками",
            assumptions=["Команда выдержит staged rollout"],
            confidence_in_assumptions=0.75,
            benefits=["Ниже риск"],
            costs=["Дольше rollout"],
            risks=["Есть операционная нагрузка"],
            prerequisites=["План отката"],
        )
        comparison = self.comparison_service.compare(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            problem_frame_id=frame.id,
            options=[option],
            selected_option_id=option.id,
        )
        links = [
            DecisionEvidenceLink(
                id="del-critical",
                organization_id=self.organization.id,
                workspace_id=self.workspace.id,
                workspace_version_id=self.version.id,
                decision_record_id=None,
                decision_option_id=option.id,
                link_type="supports",
                link_strength=0.45,
                link_direction="supports",
                source_ref="claim:budget_limit",
                criticality="critical",
                claim_id="claim-budget",
                metadata={"valid_until": "2026-03-20T00:00:00+00:00", "freshness_mode": "soft"},
            ),
            DecisionEvidenceLink(
                id="del-standard",
                organization_id=self.organization.id,
                workspace_id=self.workspace.id,
                workspace_version_id=self.version.id,
                decision_record_id=None,
                decision_option_id=option.id,
                link_type="supports",
                link_strength=0.9,
                link_direction="supports",
                source_ref="claim:baseline_cost",
                criticality="standard",
                claim_id="claim-baseline",
                metadata={"valid_until": "2026-04-01T00:00:00+00:00", "freshness_mode": "none"},
            ),
        ]
        draft = self.contract_service.create_draft(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            frame=frame,
            comparison=comparison,
            evidence_links=links,
            rationale=["Есть опора на constraint и baseline"],
        )
        return self.contract_service.promote(
            draft=draft,
            comparison=comparison,
            evidence_links=links,
            decision_basis=["Учитывает budget_limit и baseline_cost"],
            limitations=[],
            review_due="2026-04-10T00:00:00+00:00",
            actor_id=self.owner.id,
        )

    def test_assurance_scoring_uses_weakest_link_and_soft_staleness(self) -> None:
        snapshot = self.assurance.recompute(
            decision_record_id=self.record.id,
            now="2026-03-23T00:00:00+00:00",
            trigger="unit-test",
        )
        self.assertEqual(snapshot.weakest_link_ref, "del-critical")
        self.assertEqual(snapshot.assurance_status, "degrade")
        self.assertIn("soft_staleness:del-critical", snapshot.staleness_flags)
        self.assertGreater(snapshot.decay_penalty, 0.0)

    def test_hard_expiry_and_waiver_expiry_affect_status_predictably(self) -> None:
        links = self.links.list_for_record(self.record.id)
        hard_link = replace(
            links[0],
            metadata={"valid_until": "2026-03-20T00:00:00+00:00", "freshness_mode": "hard"},
        )
        self.links.replace_for_record(self.record.id, [hard_link, links[1]])
        waiver = self.waiver_service.apply(
            record=self.record,
            scope="temporary-use",
            justification="manual mitigation accepted",
            residual_risk="known stale support",
            renewal_policy="auto-expire-notify",
            expires_at="2026-03-22T00:00:00+00:00",
            actor_id=self.owner.id,
        )
        snapshot = self.assurance.recompute(
            decision_record_id=self.record.id,
            now="2026-03-23T00:00:00+00:00",
            policy_class="critical",
            trigger="expiry-test",
        )
        self.assertEqual(waiver.status, "active")
        self.assertEqual(snapshot.assurance_status, "block")
        self.assertIn("hard_expiry:del-critical", snapshot.staleness_flags)
        expired = self.waivers.list_for_record(self.record.id)[0]
        self.assertEqual(expired.status, "expired")

    def test_outcome_modifier_is_bounded_and_recorded(self) -> None:
        self.contract_service.record_outcome(
            record_id=self.record.id,
            outcome_type="implemented_successfully",
            outcome_score=0.9,
            source="operator_confirmed",
            evidence={"ticket": "OPS-1"},
        )
        self.contract_service.record_outcome(
            record_id=self.record.id,
            outcome_type="stable_after_reentry_window",
            outcome_score=0.8,
            source="reentry_worker",
            evidence={"job": "reentry:1"},
        )
        snapshot = self.assurance.recompute(
            decision_record_id=self.record.id,
            now="2026-03-19T00:00:00+00:00",
            trigger="outcome-test",
        )
        self.assertLessEqual(snapshot.historical_outcome_modifier, 0.1)
        self.assertGreater(snapshot.historical_outcome_modifier, 0.0)
        events = self.governance.list_for_workspace(self.workspace.id)
        self.assertTrue(any(event.event_type == "decision_outcome_applied_to_assurance" for event in events))

    def test_reentry_contract_and_scheduler_idempotency(self) -> None:
        job = ReentryJobRecord(
            id="reentry:ws-1:ws-1:v2",
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id="ws-1:v2",
            status="completed",
            trigger_claim_id="claim-budget",
            dependent_projections=["claim_graph"],
            affected_stages=["analysis"],
            stale_outputs=["analysis.report"],
        )
        self.assertEqual(recompute_scope_from_reentry(job), "incremental")

        first = self.scheduler.run_workspace(workspace_id=self.workspace.id, now="2026-03-23T00:00:00+00:00")
        second = self.scheduler.run_workspace(workspace_id=self.workspace.id, now="2026-03-23T00:00:00+00:00")
        self.assertTrue(first)
        self.assertEqual(len(second), len(first))
        recompute_events = [e for e in self.governance.list_for_workspace(self.workspace.id) if e.event_type == "decision_assurance_recomputed"]
        ids = {event.id for event in recompute_events}
        self.assertEqual(len(recompute_events), len(ids))

    def test_outcome_resolver_and_validator_payload_contract(self) -> None:
        self.governance.append(
            GovernanceEvent(
                id="gov:decision-selected",
                organization_id=self.organization.id,
                workspace_id=self.workspace.id,
                event_type="decision_selected",
                payload={"decision_record_id": self.record.id},
                actor_type="user",
                actor_id=self.owner.id,
            )
        )
        resolved = self.outcome_resolver.resolve_workspace(
            workspace_id=self.workspace.id,
            record_id=self.record.id,
            workspace_version_id=self.version.id,
            organization_id=self.organization.id,
        )
        self.assertTrue(resolved)
        snapshot = self.assurance.recompute(
            decision_record_id=self.record.id,
            now="2026-03-23T00:00:00+00:00",
            trigger="validator-test",
        )
        payload = assurance_payload(snapshot)
        validator = FPFResponseValidator()
        decision = validator.validate(
            answer_text="Grounded answer with evidence.",
            workspace_id=self.workspace.id,
            answer_payload={
                "used_claims": [{"id": "claim-budget", "statement": "Budget"}],
                "used_artifacts": [{"chunk_id": "a1"}],
                "open_unknowns": [],
                "decision_assurance": payload,
            },
            expected_workspace_id=self.workspace.id,
            tier="balanced",
            escalation_used=False,
        )
        self.assertIn("assurance_score", payload)
        self.assertIn(decision.status, {"pass", "degrade", "block"})


if __name__ == "__main__":
    unittest.main()
