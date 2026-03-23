from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
import unittest

from app.canonical_db.claim_graph import ClaimGraphService
from app.canonical_db.config import DatabaseConfig, connect
from app.canonical_db.domain import Claim, ClaimRelation, Organization, User, Workspace, WorkspaceVersion
from app.canonical_db.migration_runner import upgrade
from app.canonical_db.projections import (
    MaterializedArtifactIndex,
    ProjectionRegistry,
    ProjectionService,
    legacy_validator_outcome,
)
from app.canonical_db.repositories import (
    SqliteAuthSessionRepository,
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
from app.canonical_db.tenant_auth import AuthService, OrganizationService, TenantAuthorizationService


class Sprint02AuthGraphTests(unittest.TestCase):
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
        self.sessions = SqliteAuthSessionRepository(self.factory)
        self.claims = SqliteClaimRepository(self.factory, TransactionManager(self.factory))
        self.governance = SqliteGovernanceEventRepository(self.factory)
        self.projections = SqliteProjectionSnapshotRepository(self.factory)
        self.artifact_index = SqliteMaterializedArtifactIndexRepository(self.factory, TransactionManager(self.factory))
        self.auth = AuthService(self.users, self.user_profiles, self.sessions)
        self.org_service = OrganizationService(self.organizations, self.memberships, self.user_profiles)
        self.registry = ProjectionRegistry()
        self.projection_service = ProjectionService(self.claims, self.projections, self.registry)
        self.claim_graph = ClaimGraphService(self.claims, self.projection_service.mark_stale_for_claim_type)
        self.authorization = TenantAuthorizationService(self.memberships, self.workspaces, self.governance)
        self.index = MaterializedArtifactIndex(self.registry, self.artifact_index)

        self.owner = self.auth.register_user(
            user_id="owner-1",
            email="owner@example.com",
            password="owner-pass",
            display_name="Owner",
        )
        self.org = Organization(id="org-1", name="Org One", slug="org-one", owner_user_id=self.owner.id)
        self.org_service.create_organization(self.org)
        self.workspace, self.version = self._workspace("ws-1", self.org.id, self.owner.id, 1)
        self.workspaces.upsert(self.workspace, self.version)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _workspace(
        self,
        workspace_id: str,
        organization_id: str,
        user_id: str,
        version_no: int,
    ) -> tuple[Workspace, WorkspaceVersion]:
        workspace = Workspace(
            id=workspace_id,
            organization_id=organization_id,
            workspace_key=workspace_id,
            title=f"Workspace {workspace_id}",
            case_type="analysis_case",
            status="active",
            current_stage="intake",
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

    def _claim(
        self,
        *,
        claim_id: str,
        claim_key: str,
        claim_type: str,
        statement: str,
        workspace_version_id: str | None = None,
    ) -> Claim:
        return Claim(
            id=claim_id,
            organization_id=self.org.id,
            workspace_id=self.workspace.id,
            workspace_version_id=workspace_version_id or self.version.id,
            claim_key=claim_key,
            claim_type=claim_type,
            statement=statement,
            epistemic_status="accepted",
            confidence_score=0.8,
            source_kind="source_fact",
            source_ref="raw/input.md",
            attributes={"source": "test"},
        )

    def test_auth_registration_login_logout_and_expiry(self) -> None:
        user = self.auth.register_user(
            user_id="user-1",
            email="user@example.com",
            password="secret-pass",
            display_name="User One",
        )
        self.assertIsNotNone(self.user_profiles.get(user.id))

        session = self.auth.login(email="user@example.com", password="secret-pass", session_id="session-1")
        self.assertEqual(session.status, "active")
        self.assertEqual(self.sessions.get("session-1").status, "active")

        logged_out = self.auth.logout("session-1")
        self.assertEqual(logged_out.status, "invalidated")
        with self.assertRaises(PermissionError):
            self.auth.require_session("session-1")

        inactive = User(
            id="user-2",
            email="inactive@example.com",
            password_hash=self.users.get_by_email("user@example.com").password_hash,
            display_name="Inactive",
            status="inactive",
        )
        self.users.upsert(inactive)
        with self.assertRaises(PermissionError):
            self.auth.login(email="inactive@example.com", password="secret-pass", session_id="session-2")

        fresh = self.auth.login(email="user@example.com", password="secret-pass", session_id="session-3", session_ttl_hours=1)
        with self.factory() as connection:
            connection.execute(
                "UPDATE auth_sessions SET expires_at = '2000-01-01T00:00:00+00:00' WHERE id = ?",
                (fresh.id,),
            )
        with self.assertRaises(PermissionError):
            self.auth.require_session(fresh.id)
        self.assertEqual(self.sessions.get(fresh.id).status, "expired")

    def test_organization_memberships_switch_and_role_matrix(self) -> None:
        invited = self.auth.register_user(
            user_id="viewer-1",
            email="viewer@example.com",
            password="viewer-pass",
            display_name="Viewer",
        )
        admin = self.auth.register_user(
            user_id="admin-1",
            email="admin@example.com",
            password="admin-pass",
            display_name="Admin",
        )

        self.org_service.invite_member(
            organization_id=self.org.id,
            user_id=invited.id,
            role="workspace_viewer",
            invited_by_user_id=self.owner.id,
        )
        joined = self.org_service.join_membership(organization_id=self.org.id, user_id=invited.id)
        self.assertEqual(joined.role, "workspace_viewer")
        self.assertEqual(joined.status, "active")

        self.org_service.invite_member(
            organization_id=self.org.id,
            user_id=admin.id,
            role="organization_admin",
            invited_by_user_id=self.owner.id,
        )
        self.org_service.join_membership(organization_id=self.org.id, user_id=admin.id)

        other_org = Organization(id="org-2", name="Org Two", slug="org-two", owner_user_id=admin.id)
        self.org_service.create_organization(other_org)
        switched = self.org_service.switch_active_organization(user_id=admin.id, organization_id=other_org.id)
        self.assertEqual(switched.active_organization_id, other_org.id)

        with self.assertRaises(PermissionError):
            self.authorization.require_workspace_access(
                user_id=invited.id,
                organization_id=self.org.id,
                workspace_id=self.workspace.id,
                permission="claim_edit",
            )
        authorized = self.authorization.require_workspace_access(
            user_id=admin.id,
            organization_id=self.org.id,
            workspace_id=self.workspace.id,
            permission="membership_manage",
        )
        self.assertEqual(authorized.id, self.workspace.id)

    def test_tenant_guard_blocks_cross_tenant_access_and_logs_event(self) -> None:
        outsider = self.auth.register_user(
            user_id="member-1",
            email="member@example.com",
            password="member-pass",
            display_name="Member",
        )
        org_b = Organization(id="org-b", name="Org B", slug="org-b", owner_user_id=outsider.id)
        self.org_service.create_organization(org_b)
        ws_b, version_b = self._workspace("ws-b", org_b.id, outsider.id, 1)
        self.workspaces.upsert(ws_b, version_b)

        with self.assertRaises(PermissionError):
            self.authorization.require_workspace_access(
                user_id=outsider.id,
                organization_id=org_b.id,
                workspace_id=self.workspace.id,
                permission="workspace_view",
            )

        events = self.governance.list_for_workspace(self.workspace.id)
        self.assertTrue(any(event.event_type == "security_unauthorized_access" for event in events))

    def test_claim_versioning_relations_conflicts_and_duplicates(self) -> None:
        claim_a = self.claim_graph.create_claim(
            self._claim(
                claim_id="claim-a",
                claim_key="budget_max",
                claim_type="decision_constraint",
                statement="Budget must not exceed 500k",
            ),
            changed_by_actor=self.owner.id,
            change_reason="initial",
        )
        updated_workspace, updated_version = self._workspace("ws-1", self.org.id, self.owner.id, 2)
        self.workspaces.upsert(updated_workspace, updated_version)
        updated = self.claim_graph.update_claim(
            claim_a.id,
            workspace_version_id=updated_version.id,
            claim_type="decision_constraint",
            statement="Budget must not exceed 450k",
            epistemic_status="accepted",
            confidence_score=0.9,
            source_kind="source_fact",
            source_ref="parsed/spec.md",
            attributes={"changed": True},
            change_reason="tightened budget",
            changed_by_actor=self.owner.id,
        )
        versions = self.claims.list_versions(claim_a.id)
        self.assertEqual([version.version_no for version in versions], [1, 2])
        self.assertEqual(updated.statement, "Budget must not exceed 450k")

        claim_b = self.claim_graph.create_claim(
            self._claim(
                claim_id="claim-b",
                claim_key="budget_min",
                claim_type="derived_metric",
                statement="Budget must exceed 450k",
                workspace_version_id=updated_version.id,
            ),
            changed_by_actor=self.owner.id,
            change_reason="derived",
        )
        self.claim_graph.add_relation(
            ClaimRelation(
                id="rel-1",
                organization_id=self.org.id,
                workspace_id=self.workspace.id,
                from_claim_id=claim_a.id,
                to_claim_id=claim_b.id,
                relation_type="depends_on",
                metadata={"source": "test"},
            )
        )

        other_workspace, other_version = self._workspace("ws-2", self.org.id, self.owner.id, 1)
        self.workspaces.upsert(other_workspace, other_version)
        foreign_claim = self.claim_graph.create_claim(
            Claim(
                id="claim-foreign",
                organization_id=self.org.id,
                workspace_id=other_workspace.id,
                workspace_version_id=other_version.id,
                claim_key="foreign",
                claim_type="source_fact",
                statement="Foreign claim",
                epistemic_status="accepted",
                confidence_score=0.5,
                source_kind="source_fact",
                source_ref="raw/foreign.md",
            ),
            changed_by_actor=self.owner.id,
            change_reason="initial",
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.claim_graph.add_relation(
                ClaimRelation(
                    id="rel-cross",
                    organization_id=self.org.id,
                    workspace_id=self.workspace.id,
                    from_claim_id=claim_a.id,
                    to_claim_id=foreign_claim.id,
                    relation_type="contradicts",
                )
            )

        duplicate = self.claim_graph.create_claim(
            self._claim(
                claim_id="claim-c",
                claim_key="budget_dup",
                claim_type="interpretation",
                statement="Budget should stay near 450k",
                workspace_version_id=updated_version.id,
            ),
            changed_by_actor=self.owner.id,
            change_reason="duplicate",
        )
        self.claim_graph.create_claim(
            self._claim(
                claim_id="claim-d",
                claim_key="budget_dup_2",
                claim_type="interpretation",
                statement="Budget should stay near 470k",
                workspace_version_id=updated_version.id,
            ),
            changed_by_actor=self.owner.id,
            change_reason="duplicate",
        )

        summary = self.claim_graph.summarize_conflicts(self.workspace.id)
        self.assertTrue(any(item["conflict_id"].startswith("conflict::") for item in summary.conflict_cases))
        self.assertTrue(any(item["duplicate_id"].startswith("duplicate::") for item in summary.duplicate_clusters))
        self.assertIn(duplicate.id, {node_id for item in summary.duplicate_clusters for node_id in item["node_ids"]})

    def test_projection_rebuild_registry_parity_and_freshness(self) -> None:
        claim_1 = self.claim_graph.create_claim(
            self._claim(
                claim_id="claim-1",
                claim_key="energy_cap",
                claim_type="decision_constraint",
                statement="Energy cap is 1000 kWh",
            ),
            changed_by_actor=self.owner.id,
            change_reason="initial",
        )
        claim_2 = self.claim_graph.create_claim(
            self._claim(
                claim_id="claim-2",
                claim_key="baseline",
                claim_type="source_fact",
                statement="Baseline load is 800 kWh",
            ),
            changed_by_actor=self.owner.id,
            change_reason="initial",
        )

        rebuilt = self.projection_service.rebuild_workspace_projections(
            organization_id=self.org.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
        )
        rebuilt_again = self.projection_service.rebuild_workspace_projections(
            organization_id=self.org.id,
            workspace_id=self.workspace.id,
            workspace_version_id=self.version.id,
        )
        self.assertEqual(
            [(item.projection_type, item.payload) for item in rebuilt],
            [(item.projection_type, item.payload) for item in rebuilt_again],
        )

        expected = legacy_validator_outcome([claim_1, claim_2])
        actual = self.projection_service.validator_outcome_from_db(self.workspace.id, "reporting_projection")
        self.assertEqual(actual, expected)

        affected = self.registry.projection_types_for_claim_type("decision_constraint")
        self.assertIn("selection_projection", affected)

        next_workspace, next_version = self._workspace("ws-1", self.org.id, self.owner.id, 3)
        self.workspaces.upsert(next_workspace, next_version)
        self.claim_graph.update_claim(
            claim_1.id,
            workspace_version_id=next_version.id,
            claim_type="decision_constraint",
            statement="Energy cap is 900 kWh",
            epistemic_status="accepted",
            confidence_score=0.85,
            source_kind="source_fact",
            source_ref="parsed/update.md",
            attributes={},
            change_reason="tighter cap",
            changed_by_actor=self.owner.id,
        )
        stale_projection_types = {
            snapshot.projection_type
            for snapshot in self.projections.list_for_workspace(self.workspace.id)
            if snapshot.freshness_status == "stale"
        }
        self.assertTrue(set(affected).issubset(stale_projection_types))

    def test_materialized_artifact_index_is_deterministic_and_reentry_friendly(self) -> None:
        self.index.rebuild(organization_id=self.org.id, workspace_id=self.workspace.id)
        first_graph = self.index.stable_graph(self.workspace.id)
        affected = self.index.affected_outputs(self.workspace.id, "selection_projection")
        self.assertIn("selection", affected["stages"])
        self.assertTrue(any(output.endswith("selection_projection.json") for output in affected["outputs"]))

        self.index.rebuild(organization_id=self.org.id, workspace_id=self.workspace.id)
        second_graph = self.index.stable_graph(self.workspace.id)
        self.assertEqual(first_graph, second_graph)

        entries = self.artifact_index.list_for_workspace(self.workspace.id)
        contracts = [entry.metadata.get("dependency_contract") for entry in entries if entry.projection_type == "selection_projection"]
        self.assertTrue(all(contract and "projection_type" in contract and "stage_name" in contract for contract in contracts))


if __name__ == "__main__":
    unittest.main()
