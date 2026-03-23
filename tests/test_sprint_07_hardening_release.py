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
from app.canonical_db.dialogue_backend import LLMProviderAdapter
from app.canonical_db.domain import Claim, ClaimRelation, Organization, User, UserProfile, Workspace, WorkspaceVersion
from app.canonical_db.migration_runner import upgrade
from app.canonical_db.model_updates import ReentryPlanner, ReentryWorker
from app.canonical_db.projections import MaterializedArtifactIndex, ProjectionRegistry, ProjectionService
from app.canonical_db.repositories import (
    SqliteClaimRepository,
    SqliteGovernanceEventRepository,
    SqliteMaterializedArtifactIndexRepository,
    SqliteMembershipRepository,
    SqliteOrganizationRepository,
    SqliteProjectionSnapshotRepository,
    SqliteUserProfileRepository,
    SqliteUserRepository,
    SqliteWorkspaceRepository,
    TransactionManager,
)
from app.canonical_db.tenant_auth import OrganizationService
from app.observability.runtime_monitor import RUNTIME_MONITOR
from app.release.hardening import build_pilot_readiness_package
from app.worker_service import WorkerRuntimeService


class Sprint07HardeningReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db_path = self.root / "canonical.sqlite3"
        self.config = DatabaseConfig(dsn=f"sqlite:///{self.db_path}", environment="test")
        self.old_dsn = os.environ.get("CANONICAL_DB_DSN")
        os.environ["CANONICAL_DB_DSN"] = self.config.dsn
        RUNTIME_MONITOR.reset()

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
        self.org_service = OrganizationService(self.organizations, self.memberships, self.profiles)
        self.registry = ProjectionRegistry()
        self.projection_service = ProjectionService(self.claims, self.snapshots, self.registry)
        self.artifact_index = MaterializedArtifactIndex(self.registry, self.materialized_entries)
        self.reentry_planner = ReentryPlanner(self.registry, self.artifact_index, self.snapshots)
        self.reentry_worker = ReentryWorker(
            __import__("app.canonical_db.model_updates", fromlist=["SqliteReentryJobRepository"]).SqliteReentryJobRepository(self.factory, TransactionManager(self.factory)),
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
            title="Hardening Workspace",
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
        self.claim_graph = ClaimGraphService(self.claims)
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
                workspace_version_id=self.version.id,
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
        self.projection_service.rebuild_workspace_projections(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
        )

    def tearDown(self) -> None:
        RUNTIME_MONITOR.reset()
        if self.old_dsn is None:
            os.environ.pop("CANONICAL_DB_DSN", None)
        else:
            os.environ["CANONICAL_DB_DSN"] = self.old_dsn
        self.tmp.cleanup()

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

    def test_correlation_trace_and_governance_feed(self) -> None:
        status, body = self._call(
            "/api/dialogue/ask",
            method="POST",
            payload={
                "organization_id": self.organization.id,
                "workspace_id": self.workspace.id,
                "session_id": "session-1",
                "user_id": self.owner.id,
                "question": "What budget limit must we follow?",
                "budget_profile": "standard",
                "correlation_id": "corr-001",
            },
        )
        self.assertEqual(status, "200 OK")
        payload = json.loads(body)
        self.assertEqual(payload["runtime"]["correlation_id"], "corr-001")

        status, body = self._call(f"/api/workspaces/{self.workspace.id}/governance-feed")
        feed = json.loads(body)
        correlated = [event for event in feed["events"] if event["payload"].get("correlation_id") == "corr-001"]
        event_types = {event["event_type"] for event in correlated}
        self.assertIn("dialogue_request_received", event_types)
        self.assertIn("provider_call_completed", event_types)
        self.assertIn("validator_completed", event_types)

    def test_metrics_logs_health_and_readiness(self) -> None:
        self._call(
            "/api/dialogue/ask",
            method="POST",
            payload={
                "organization_id": self.organization.id,
                "workspace_id": self.workspace.id,
                "session_id": "session-2",
                "user_id": self.owner.id,
                "question": "What budget limit must we follow?",
                "budget_profile": "standard",
                "correlation_id": "corr-002",
            },
        )
        status, body = self._call("/metrics")
        self.assertEqual(status, "200 OK")
        metrics = json.loads(body)
        self.assertGreaterEqual(metrics["counters"]["dialogue_requests_total"], 1)
        self.assertIn("dialogue_request", metrics["latencies"])
        self.assertTrue(any(item["correlation_id"] == "corr-002" for item in metrics["recent_logs"]))

        status, body = self._call("/health")
        self.assertEqual(status, "200 OK")
        self.assertEqual(json.loads(body)["status"], "alive")

        status, body = self._call("/readiness")
        self.assertEqual(status, "200 OK")
        readiness = json.loads(body)
        self.assertEqual(readiness["status"], "ready")
        self.assertEqual(readiness["dependencies"]["database"], "ready")
        self.assertEqual(readiness["dependencies"]["worker_queue"], "ready")

    def test_provider_diagnostics_and_fallback_contracts(self) -> None:
        status, body = self._call("/api/ops/provider-diagnostics")
        self.assertEqual(status, "200 OK")
        diagnostics = json.loads(body)
        self.assertEqual(diagnostics["active_mode"], "direct")
        self.assertEqual(diagnostics["direct_provider"], "configured")

        adapter = LLMProviderAdapter(
            mode="gateway",
            gateway_callable=lambda prompt, model: (_ for _ in ()).throw(RuntimeError("gateway down")),
            fallback_callable=lambda prompt, model: {"text": "fallback response", "usage": {"estimated_cost": 1.0}},
        )
        response = adapter.generate(prompt="hello", tier="balanced", model_key="balanced-model")
        self.assertEqual(response.provider, "gateway->fallback")
        self.assertTrue(adapter.diagnostics()["fallback_used"])

    def test_worker_runtime_processes_reentry_job_and_reports_readiness(self) -> None:
        pending_version = WorkspaceVersion(
            id="ws-1:v2",
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            version_no=2,
            version_label="v2",
            change_reason="update",
            created_by=self.owner.id,
        )
        self.workspaces.upsert(self.workspace, pending_version)
        plan = self.reentry_planner.plan(
            workspace_id=self.workspace.id,
            claim=self.claims.get_by_key(self.workspace.id, "budget_limit"),
        )
        job = self.reentry_worker.submit(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            pending_version=pending_version,
            plan=plan,
        )
        worker = WorkerRuntimeService(self.root)
        readiness = worker.readiness()
        self.assertEqual(readiness["status"], "ready")
        self.assertEqual(readiness["queue"]["queued_jobs"], 1)

        result = worker.run_next(workspace_id=self.workspace.id)
        self.assertEqual(result["status"], "completed")

        status, body = self._call("/worker/readiness")
        self.assertEqual(status, "200 OK")
        payload = json.loads(body)
        self.assertEqual(payload["service"], "worker")

    def test_pilot_readiness_package_and_decision_wave_contract(self) -> None:
        gov = self.root / "governance"
        gov.mkdir(parents=True, exist_ok=True)
        reports = self.root / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "integration_quality_report.json").write_text(
            json.dumps(
                {
                    "total_cases": 10,
                    "silent_failures": 0,
                    "hard_fail_detection_rate": 1.0,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        case_root = self.root / "cases" / "case_20260323_701"
        (case_root / "governance").mkdir(parents=True, exist_ok=True)
        (case_root / "reports").mkdir(parents=True, exist_ok=True)
        (case_root / "operation").mkdir(parents=True, exist_ok=True)
        (case_root / "governance" / "decision_log.jsonl").write_text("", encoding="utf-8")
        (case_root / "governance" / "stage_events.jsonl").write_text("", encoding="utf-8")
        (case_root / "reports" / "reporting_summary.json").write_text(json.dumps({"missing_sources": []}), encoding="utf-8")
        for rel in ["reports/Analytical_Full_Report.md", "reports/Executive_Summary.md", "operation/Runbook.md", "operation/RollbackPlan.md"]:
            target = case_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("ok\n", encoding="utf-8")

        bundle = build_pilot_readiness_package(self.root, workspace_ids=["case_20260323_701"])
        self.assertIn("railway_topology", bundle)
        self.assertIn("dual_write_review", bundle)
        self.assertIn("decision_wave_readiness", bundle)
        self.assertTrue((self.root / "docs" / "railway_worker_topology.md").is_file())
        self.assertTrue((self.root / "governance" / "dual_write_cutover_review.json").is_file())
        self.assertTrue((self.root / "governance" / "decision_wave_readiness.json").is_file())
        self.assertTrue((self.root / "governance" / "GO_NO_GO_DECISION.json").is_file())


if __name__ == "__main__":
    unittest.main()
