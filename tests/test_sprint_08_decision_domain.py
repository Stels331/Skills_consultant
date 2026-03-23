from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path
import unittest

from app.canonical_db.claim_graph import ClaimGraphService
from app.canonical_db.config import DatabaseConfig, connect
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
from app.canonical_db.dialogue_backend import QuestionRouter
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


class Sprint08DecisionDomainTests(unittest.TestCase):
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
        self.review_service = DecisionReviewService(self.reviews, self.records)
        self.frame_builder = ProblemFrameBuilder(
            self.frames,
            self.options,
            self.comparisons,
            self.drafts,
            self.records,
            self.reviews,
            self.governance,
        )
        self.option_engine = DecisionOptionEngine(self.options, self.governance)
        self.comparison_service = DecisionComparisonService(self.comparisons, self.governance)
        self.contract_service = DecisionContractService(
            self.drafts,
            self.records,
            self.links,
            self.outcomes,
            self.review_service,
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
            title="Decision Workspace",
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

    def test_schema_and_router_extension(self) -> None:
        with sqlite3.connect(self.db_path) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'decision_%' OR name = 'problem_frames'"
                ).fetchall()
            }
        self.assertIn("problem_frames", tables)
        self.assertIn("decision_records", tables)
        self.assertIn("decision_outcomes", tables)

        route = QuestionRouter().route("Какое решение выбрать по этому кейсу?")
        self.assertEqual(route.question_class, "decision_query")

    def test_problem_frame_build_and_invalidation_cascade(self) -> None:
        claims = self.claims.list_for_workspace(self.workspace.id)
        frame = self.frame_builder.build(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            root_problem="Нужно выбрать способ снижения затрат без выхода за бюджет.",
            supporting_claims=claims,
            unresolved_unknowns=["Нужно уточнить условия по вендору"],
            active_constraints=["Бюджет не выше 500k"],
            success_criteria=["Снижение затрат", "Срок внедрения до 2 месяцев"],
            scope_boundary="Только текущий контур закупок",
            correlation_id="corr-s8-1",
        )
        option = self.option_engine.materialize(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            problem_frame_id=frame.id,
            option_key="renegotiate_vendor",
            title="Пересогласовать условия с текущим вендором",
            summary_text="Rollback possible if terms are not accepted",
            assumptions=["Вендор готов к скидке"],
            confidence_in_assumptions=0.72,
            benefits=["Снижение затрат без смены платформы"],
            costs=["Переговорный цикл"],
            risks=["Вендор может отказаться"],
            prerequisites=["Подготовить обоснование"],
            correlation_id="corr-s8-1",
        )
        comparison = self.comparison_service.compare(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            problem_frame_id=frame.id,
            options=[option],
            selected_option_id=option.id,
            tradeoffs=["Быстро, но зависит от вендора"],
            rationale_notes=["Подходит под текущий бюджет"],
            correlation_id="corr-s8-1",
        )
        links = [
            DecisionEvidenceLink(
                id="del-1",
                organization_id=self.organization.id,
                workspace_id=self.workspace.id,
                workspace_version_id=self.version.id,
                decision_record_id=None,
                decision_option_id=option.id,
                link_type="supports",
                link_strength=0.9,
                link_direction="supports",
                source_ref="claim:budget_limit",
                criticality="critical",
                claim_id="claim-budget",
            )
        ]
        draft = self.contract_service.create_draft(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            frame=frame,
            comparison=comparison,
            evidence_links=links,
            rationale=["Опция укладывается в ограничения"],
        )
        record = self.contract_service.promote(
            draft=draft,
            comparison=comparison,
            evidence_links=links,
            decision_basis=["Поддержано budget_limit и baseline_cost"],
            limitations=["Требует подтверждения от вендора"],
            review_due="2026-04-01T00:00:00+00:00",
            actor_id=self.owner.id,
            correlation_id="corr-s8-1",
        )

        invalidated = self.frame_builder.invalidate(
            problem_frame_id=frame.id,
            reason="Новый критичный claim противоречит исходной модели",
            actor_id=self.owner.id,
            correlation_id="corr-s8-2",
        )
        self.assertEqual(invalidated.status, "invalidated")
        self.assertEqual(self.options.list_for_frame(frame.id)[0].status, "stale")
        self.assertEqual(self.comparisons.get(comparison.id).status, "stale")
        self.assertEqual(self.drafts.get(draft.id).status, "stale")
        self.assertEqual(self.records.get(record.id).status, "review_required")
        self.assertIsNotNone(self.reviews.get_open_for_record(record.id))

    def test_option_materialization_is_machine_readable_and_idempotent(self) -> None:
        frame = self.frame_builder.build(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            root_problem="Нужно определить вариант сокращения издержек.",
            supporting_claims=self.claims.list_for_workspace(self.workspace.id),
            unresolved_unknowns=[],
            active_constraints=["Бюджет не выше 500k"],
            success_criteria=["Достижимо в квартал"],
            scope_boundary="Финансовый контур",
        )
        option = self.option_engine.materialize(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            problem_frame_id=frame.id,
            option_key="automation",
            title="Автоматизировать сверку",
            summary_text="Снижает ручной труд",
            assumptions=["Есть доступ к данным"],
            confidence_in_assumptions=0.65,
            benefits=["Экономия времени"],
            costs=["Настройка интеграций"],
            risks=["Риск неполных данных"],
            prerequisites=["Согласовать API доступ"],
        )
        self.option_engine.materialize(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            problem_frame_id=frame.id,
            option_key="automation",
            title="Автоматизировать сверку",
            summary_text="Снижает ручной труд",
            assumptions=["Есть доступ к данным"],
            confidence_in_assumptions=0.65,
            benefits=["Экономия времени"],
            costs=["Настройка интеграций"],
            risks=["Риск неполных данных"],
            prerequisites=["Согласовать API доступ"],
        )
        options = self.options.list_for_frame(frame.id)
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0].assumptions, ["Есть доступ к данным"])
        self.assertEqual(options[0].risks, ["Риск неполных данных"])
        self.assertAlmostEqual(options[0].confidence_in_assumptions, 0.65)
        self.assertEqual(options[0].id, option.id)

    def test_comparison_supports_domain_dimensions_and_rejected_options(self) -> None:
        frame = self.frame_builder.build(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            root_problem="Нужно выбрать стратегию внедрения.",
            supporting_claims=self.claims.list_for_workspace(self.workspace.id),
            unresolved_unknowns=[],
            active_constraints=["Бюджет не выше 500k"],
            success_criteria=["Миграция без остановки"],
            scope_boundary="Операционный контур",
        )
        option_a = self.option_engine.materialize(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            problem_frame_id=frame.id,
            option_key="pilot",
            title="Пилотный rollout",
            summary_text="Постепенный rollout with rollback",
            assumptions=["Команда выдержит двойной режим"],
            confidence_in_assumptions=0.8,
            benefits=["Ниже риск"],
            costs=["Дольше по времени"],
            risks=["Сложнее поддержка"],
            prerequisites=["Подготовить план пилота"],
        )
        option_b = self.option_engine.materialize(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            problem_frame_id=frame.id,
            option_key="big_bang",
            title="Полный cutover",
            summary_text="Быстрый запуск",
            assumptions=["Инцидентов не будет"],
            confidence_in_assumptions=0.45,
            benefits=["Быстрее реализация"],
            costs=["Большая нагрузка"],
            risks=["Высокий риск отказа"],
            prerequisites=["Полная готовность"],
        )
        comparison = self.comparison_service.compare(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            problem_frame_id=frame.id,
            options=[option_a, option_b],
            domain_dimensions=["compliance_fit"],
            selected_option_id=option_a.id,
            tradeoffs=["Пилот медленнее, но безопаснее"],
            blockers=["Нет blocker для pilot"],
            rationale_notes=["Pilot лучше по risk dimension"],
            correlation_id="corr-s8-3",
        )
        self.assertIn("compliance_fit", comparison.comparison_dimensions)
        self.assertIn(option_b.id, comparison.rejected_option_ids)
        self.assertIn("risk", comparison.option_scores[option_a.id])

    def test_missing_contract_gate_builds_partial_recommendation(self) -> None:
        frame = self.frame_builder.build(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            root_problem="Нужно выбрать вариант экономии.",
            supporting_claims=self.claims.list_for_workspace(self.workspace.id),
            unresolved_unknowns=["Нет данных по альтернативным вендорам"],
            active_constraints=["Бюджет не выше 500k"],
            success_criteria=["Экономия в этом квартале"],
            scope_boundary="Закупки",
        )
        option = self.option_engine.materialize(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            problem_frame_id=frame.id,
            option_key="renegotiate",
            title="Пересогласование контракта",
            summary_text="Прямые переговоры с поставщиком",
            assumptions=["Поставщик пойдет на уступки"],
            confidence_in_assumptions=0.55,
            benefits=["Быстрая экономия"],
            costs=["Переговорный ресурс"],
            risks=["Нет встречного предложения"],
            prerequisites=["Подготовить аргументацию"],
        )
        comparison = self.comparison_service.compare(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            problem_frame_id=frame.id,
            options=[option],
            selected_option_id=option.id,
        )
        draft = self.contract_service.create_draft(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            frame=frame,
            comparison=comparison,
            evidence_links=[],
            rationale=["Основание пока частичное"],
        )
        self.assertEqual(draft.status, "degrade")
        self.assertIn("supporting_evidence", draft.missing_basis)
        self.assertIn("partial_decision_basis", draft.uncertainty_markers)

    def test_outcome_updates_record_and_governance_history(self) -> None:
        frame = self.frame_builder.build(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            root_problem="Нужно принять решение по снижению затрат.",
            supporting_claims=self.claims.list_for_workspace(self.workspace.id),
            unresolved_unknowns=[],
            active_constraints=["Бюджет не выше 500k"],
            success_criteria=["Подтвержденное снижение затрат"],
            scope_boundary="Закупки",
        )
        option = self.option_engine.materialize(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            problem_frame_id=frame.id,
            option_key="vendor_discount",
            title="Добиться скидки",
            summary_text="Скидка за продление контракта",
            assumptions=["Вендор заинтересован"],
            confidence_in_assumptions=0.74,
            benefits=["Прямая экономия"],
            costs=["Время на переговоры"],
            risks=["Скидка может быть меньше ожидаемой"],
            prerequisites=["Данные по spend"],
        )
        comparison = self.comparison_service.compare(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            problem_frame_id=frame.id,
            options=[option],
            selected_option_id=option.id,
        )
        link = DecisionEvidenceLink(
            id="del-outcome",
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            decision_record_id=None,
            decision_option_id=option.id,
            link_type="supports",
            link_strength=0.85,
            link_direction="supports",
            source_ref="claim:baseline_cost",
            criticality="standard",
            claim_id="claim-baseline",
        )
        draft = self.contract_service.create_draft(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            frame=frame,
            comparison=comparison,
            evidence_links=[link],
            rationale=["Есть опора на baseline_cost"],
        )
        record = self.contract_service.promote(
            draft=draft,
            comparison=comparison,
            evidence_links=[link],
            decision_basis=["Снижение baseline cost подтверждено"],
            limitations=[],
            review_due=None,
            actor_id=self.owner.id,
            correlation_id="corr-s8-4",
        )
        outcome = self.contract_service.record_outcome(
            record_id=record.id,
            outcome_type="implemented_successfully",
            outcome_score=0.9,
            source="operator_confirmed",
            evidence={"ticket": "OPS-42"},
            correlation_id="corr-s8-4",
        )
        updated = self.records.get(record.id)
        self.assertEqual(outcome.outcome_type, "implemented_successfully")
        self.assertEqual(updated.last_outcome_status, "implemented_successfully")
        self.assertAlmostEqual(updated.historical_value_score, 0.9)
        events = self.governance.list_for_workspace(self.workspace.id)
        outcome_events = [event for event in events if event.event_type == "decision_outcome_recorded"]
        self.assertEqual(len(outcome_events), 1)
        self.assertEqual(outcome_events[0].payload["decision_record_id"], record.id)

    def test_review_close_updates_record_state(self) -> None:
        frame = self.frame_builder.build(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            root_problem="Нужно выбрать вариант исполнения.",
            supporting_claims=self.claims.list_for_workspace(self.workspace.id),
            unresolved_unknowns=[],
            active_constraints=["Бюджет не выше 500k"],
            success_criteria=["Исполнение без блокеров"],
            scope_boundary="Исполнение",
        )
        option = self.option_engine.materialize(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            problem_frame_id=frame.id,
            option_key="controlled_rollout",
            title="Контролируемый rollout",
            summary_text="С ограниченным масштабом запуска",
            assumptions=["Есть ресурс на поддержку"],
            confidence_in_assumptions=0.7,
            benefits=["Управляемый риск"],
            costs=["Дольше вывод в прод"],
            risks=["Нужна двойная поддержка"],
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
        link = DecisionEvidenceLink(
            id="del-review",
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            decision_record_id=None,
            decision_option_id=option.id,
            link_type="supports",
            link_strength=0.8,
            link_direction="supports",
            source_ref="claim:budget_limit",
            criticality="standard",
            claim_id="claim-budget",
        )
        draft = self.contract_service.create_draft(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
            frame=frame,
            comparison=comparison,
            evidence_links=[link],
            rationale=["Есть достаточная опора"],
        )
        record = self.contract_service.promote(
            draft=draft,
            comparison=comparison,
            evidence_links=[link],
            decision_basis=["Ограничения учтены"],
            limitations=[],
            review_due=None,
            actor_id=self.owner.id,
        )
        record = self.contract_service.mark_review_required(record_id=record.id, reason="manual audit requested", actor_id=self.owner.id)
        review = self.reviews.get_open_for_record(record.id)
        self.assertIsNotNone(review)
        closed = self.review_service.close_review(review, closed_by=self.owner.id, close_reason="accepted", next_record_status="closed")
        self.assertEqual(closed.status, "closed")
        self.assertEqual(self.records.get(record.id).status, "closed")


if __name__ == "__main__":
    unittest.main()
