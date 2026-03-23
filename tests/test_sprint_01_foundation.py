from __future__ import annotations

import io
import json
import os
import sqlite3
import tempfile
from pathlib import Path
import unittest

from app.api_server import application
from app.canonical_db.config import DatabaseConfig, connect
from app.canonical_db.domain import (
    Artifact,
    Claim,
    ClaimRelation,
    DialogueSession,
    GovernanceEvent,
    Organization,
    User,
    Workspace,
    WorkspaceVersion,
)
from app.canonical_db.importer import LegacyWorkspaceImporter
from app.canonical_db.materializer import WorkspaceMaterializer
from app.canonical_db.migration_runner import available_revisions, current_revision, downgrade, upgrade
from app.canonical_db.repositories import (
    SqliteArtifactRepository,
    SqliteClaimRepository,
    SqliteDialogueSessionRepository,
    SqliteGovernanceEventRepository,
    SqliteOrganizationRepository,
    SqliteUserRepository,
    SqliteWorkspaceRepository,
    TransactionManager,
)
from app.canonical_db.service import DualWriteWorkspaceService


ALL_TABLES = {
    "users",
    "organizations",
    "memberships",
    "workspaces",
    "workspace_versions",
    "artifacts",
    "claims",
    "claim_versions",
    "claim_relations",
    "dialogue_sessions",
    "dialogue_messages",
    "question_queue",
    "validation_runs",
    "governance_events",
    "retrieval_chunks",
    "embedding_jobs",
    "reentry_jobs",
    "quota_ledger",
}


class CanonicalDbFoundationTests(unittest.TestCase):
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
        self.organizations = SqliteOrganizationRepository(self.factory)
        self.workspaces = SqliteWorkspaceRepository(self.factory)
        self.artifacts = SqliteArtifactRepository(self.factory)
        self.claims = SqliteClaimRepository(self.factory, TransactionManager(self.factory))
        self.dialogue_sessions = SqliteDialogueSessionRepository(self.factory)
        self.governance = SqliteGovernanceEventRepository(self.factory)
        self.materializer = WorkspaceMaterializer(
            self.workspaces, self.artifacts, self.claims, self.governance
        )
        self.dual_write = DualWriteWorkspaceService(
            self.workspaces, self.governance, self.materializer
        )
        self._seed_tenant()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _seed_tenant(self) -> None:
        self.user = User(
            id="user-1",
            email="owner@example.com",
            password_hash="hash",
            display_name="Owner",
        )
        self.organization = Organization(
            id="org-1",
            name="Org One",
            slug="org-one",
            owner_user_id=self.user.id,
        )
        self.users.upsert(self.user)
        self.organizations.upsert(self.organization)

    def _workspace(self, workspace_id: str = "case_20260322_001") -> tuple[Workspace, WorkspaceVersion]:
        workspace = Workspace(
            id=workspace_id,
            organization_id=self.organization.id,
            workspace_key=workspace_id,
            title="Canonical Workspace",
            case_type="analysis_case",
            status="active",
            current_stage="intake",
            active_model_version=1,
            created_by_user_id=self.user.id,
            metadata={"source": "test"},
        )
        version = WorkspaceVersion(
            id=f"{workspace_id}:v1",
            organization_id=self.organization.id,
            workspace_id=workspace_id,
            version_no=1,
            version_label="v1",
            change_reason="bootstrap",
            created_by=self.user.id,
        )
        return workspace, version

    def _create_legacy_workspace(self, invalid_extra_file: bool = False) -> Path:
        workspace_root = self.root / "legacy" / "case_20260322_099"
        for rel in [
            "raw",
            "parsed",
            "extracted",
            "model",
            "analysis",
            "dialogue",
            "evidence",
            "quality",
            "reports",
            "state",
            "versions",
        ]:
            (workspace_root / rel).mkdir(parents=True, exist_ok=True)
        (workspace_root / "workspace_metadata.json").write_text(
            json.dumps(
                {
                    "workspace_id": "case_20260322_099",
                    "title": "Legacy Workspace",
                    "state": "ACTIVE",
                    "current_stage": "reporting",
                    "case_type": "legacy_case",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (workspace_root / "model" / "model_version.json").write_text(
            json.dumps({"workspace_id": "case_20260322_099", "current_version": 2}, indent=2),
            encoding="utf-8",
        )
        (workspace_root / "model" / "case_model.json").write_text(
            json.dumps(
                {
                    "workspace_id": "case_20260322_099",
                    "claims": [
                        {
                            "claim_id": "claim-1",
                            "claim_key": "budget",
                            "claim_type": "decision_constraint",
                            "statement": "Budget is capped at 500k",
                            "epistemic_status": "accepted",
                            "confidence_score": 0.9,
                            "source_kind": "source_fact",
                            "source_ref": "raw/input.md",
                        }
                    ],
                    "relations": [],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (workspace_root / "state" / "version_changelog.json").write_text(
            json.dumps(
                {
                    "workspace_id": "case_20260322_099",
                    "events": [
                        {
                            "event_type": "WORKSPACE_CREATED",
                            "details": {"state": "ACTIVE"},
                        }
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (workspace_root / "dialogue" / "question_queue.json").write_text(
            json.dumps({"workspace_id": "case_20260322_099", "questions": []}, indent=2),
            encoding="utf-8",
        )
        (workspace_root / "raw" / "input.md").write_text("# Legacy input\n", encoding="utf-8")
        if invalid_extra_file:
            (workspace_root / "analysis" / "broken.json").write_text("{bad json", encoding="utf-8")
        return workspace_root

    def test_migration_schema_and_indexes(self) -> None:
        with self.factory() as connection:
            rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            self.assertTrue(ALL_TABLES.issubset({row[0] for row in rows}))

            workspace_fk = connection.execute("PRAGMA foreign_key_list(workspaces)").fetchall()
            self.assertTrue(any(row[2] == "organizations" for row in workspace_fk))

            msg_columns = connection.execute("PRAGMA table_info(dialogue_messages)").fetchall()
            column_names = {row[1] for row in msg_columns}
            self.assertIn("workspace_version_id", column_names)
            self.assertIn("question_class", column_names)

            claim_columns = {row[1]: row[2] for row in connection.execute("PRAGMA table_info(claims)")}
            self.assertEqual(claim_columns["confidence_score"], "REAL")

            indexes = {
                row[1]
                for row in connection.execute("PRAGMA index_list(dialogue_messages)").fetchall()
            }
            self.assertIn("ix_dialogue_messages_session_id", indexes)

    def test_constraint_failures(self) -> None:
        with self.factory() as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO workspaces (
                        id, organization_id, workspace_key, title, case_type, status,
                        current_stage, active_model_version, created_by_user_id, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "ws-missing-org",
                        None,
                        "ws-missing-org",
                        "Invalid",
                        "analysis",
                        "active",
                        "intake",
                        0,
                        self.user.id,
                        "{}",
                    ),
                )
            connection.rollback()

        workspace, version = self._workspace("case_20260322_002")
        self.workspaces.upsert(workspace, version)
        with self.factory() as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO dialogue_messages (
                        id, organization_id, workspace_id, session_id, workspace_version_id,
                        actor_type, question_class, message_type, content_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "msg-1",
                        self.organization.id,
                        workspace.id,
                        None,
                        version.id,
                        "user",
                        "constraint_query",
                        "question",
                        "hello",
                    ),
                )

    def test_upgrade_downgrade_and_config(self) -> None:
        revisions = available_revisions()
        head_revision = revisions[-1].revision
        previous_revision = revisions[-2].revision if len(revisions) > 1 else None
        os.environ["CANONICAL_DB_DSN_TEST"] = f"sqlite:///{self.root / 'env.sqlite3'}"
        try:
            cfg = DatabaseConfig.from_env("test")
            self.assertTrue(cfg.dsn.endswith("env.sqlite3"))
        finally:
            os.environ.pop("CANONICAL_DB_DSN_TEST", None)

        with self.factory() as connection:
            self.assertEqual(current_revision(connection), head_revision)
            self.assertEqual(downgrade(connection, steps=1), previous_revision)
            if len(revisions) > 1:
                self.assertIsNone(downgrade(connection, steps=len(revisions) - 1))
            remaining = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            self.assertFalse("workspaces" in remaining)
            self.assertEqual(upgrade(connection, target="head"), head_revision)

    def test_repository_crud_and_transaction_rollback(self) -> None:
        workspace, version = self._workspace()
        self.workspaces.upsert(workspace, version)
        self.assertEqual(self.workspaces.get(workspace.id).title, workspace.title)
        self.assertEqual(self.workspaces.get_version(workspace.id, 1).id, version.id)

        artifact = Artifact(
            id="artifact-1",
            organization_id=self.organization.id,
            workspace_id=workspace.id,
            workspace_version_id=version.id,
            artifact_type="report",
            stage_name="reporting",
            artifact_key="reports/report.json",
            status="active",
            format="json",
            payload={"ok": True},
            file_path="reports/report.json",
        )
        self.artifacts.upsert_many([artifact])
        self.assertEqual(len(self.artifacts.list_for_workspace(workspace.id)), 1)

        session = DialogueSession(
            id="session-1",
            organization_id=self.organization.id,
            workspace_id=workspace.id,
            created_by_user_id=self.user.id,
            status="active",
            active_workspace_version_id=version.id,
            title="Session",
        )
        self.dialogue_sessions.upsert(session)
        self.assertEqual(self.dialogue_sessions.get(session.id).title, "Session")

        self.governance.append(
            GovernanceEvent(
                id="event-1",
                organization_id=self.organization.id,
                workspace_id=workspace.id,
                event_type="workspace_created",
                payload={"ok": True},
                actor_type="system",
                actor_id="test",
            )
        )
        self.assertEqual(len(self.governance.list_for_workspace(workspace.id)), 1)

        claim = Claim(
            id="claim-1",
            organization_id=self.organization.id,
            workspace_id=workspace.id,
            workspace_version_id=version.id,
            claim_key="claim-1",
            claim_type="source_fact",
            statement="Fact",
            epistemic_status="accepted",
            confidence_score=0.8,
            source_kind="user",
            source_ref="src",
        )
        broken_relation = ClaimRelation(
            id="rel-1",
            organization_id=self.organization.id,
            workspace_id=workspace.id,
            from_claim_id=claim.id,
            to_claim_id="missing-claim",
            relation_type="supports",
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.claims.replace_workspace_claims(workspace.id, [claim], [broken_relation])
        self.assertEqual(self.claims.list_for_workspace(workspace.id), [])

    def test_importer_end_to_end_idempotency_and_fault_reporting(self) -> None:
        workspace_root = self._create_legacy_workspace(invalid_extra_file=True)
        importer = LegacyWorkspaceImporter(
            workspace_repo=self.workspaces,
            artifact_repo=self.artifacts,
            claim_repo=self.claims,
            governance_repo=self.governance,
        )
        report1 = importer.import_workspace(
            workspace_root,
            organization_id=self.organization.id,
            created_by_user_id=self.user.id,
        )
        report2 = importer.import_workspace(
            workspace_root,
            organization_id=self.organization.id,
            created_by_user_id=self.user.id,
        )

        self.assertTrue(report1.created)
        self.assertFalse(report2.created)
        self.assertEqual(report1.stats["claims"], 1)
        self.assertEqual(len(report1.partial_failures), 1)
        imported = self.workspaces.get("case_20260322_099")
        self.assertEqual(imported.metadata["migrated_from"], str(workspace_root.resolve()))
        self.assertEqual(len(self.claims.list_for_workspace(imported.id)), 1)
        self.assertEqual(len(self.governance.list_for_workspace(imported.id)), 1)
        self.assertGreaterEqual(len(self.artifacts.list_for_workspace(imported.id)), 5)

        with self.factory() as connection:
            claim_count = connection.execute(
                "SELECT COUNT(*) FROM claims WHERE workspace_id = ?",
                (imported.id,),
            ).fetchone()[0]
            event_count = connection.execute(
                "SELECT COUNT(*) FROM governance_events WHERE workspace_id = ?",
                (imported.id,),
            ).fetchone()[0]
        self.assertEqual(claim_count, 1)
        self.assertEqual(event_count, 1)

    def test_read_model_parity_with_legacy_workspace(self) -> None:
        workspace_root = self._create_legacy_workspace()
        importer = LegacyWorkspaceImporter(
            workspace_repo=self.workspaces,
            artifact_repo=self.artifacts,
            claim_repo=self.claims,
            governance_repo=self.governance,
        )
        importer.import_workspace(
            workspace_root,
            organization_id=self.organization.id,
            created_by_user_id=self.user.id,
        )
        legacy_model = json.loads((workspace_root / "model" / "case_model.json").read_text(encoding="utf-8"))
        repo_claims = self.claims.list_for_workspace("case_20260322_099")
        self.assertEqual(len(repo_claims), len(legacy_model["claims"]))
        self.assertEqual(repo_claims[0].statement, legacy_model["claims"][0]["statement"])

    def test_dual_write_materialization_determinism_and_sync_alarm(self) -> None:
        workspace, version = self._workspace("case_20260322_003")
        fingerprints1 = self.dual_write.create_workspace(
            workspace,
            version,
            self.root / "exports",
        )
        export_dir = self.root / "exports" / workspace.id
        self.assertTrue((export_dir / "workspace_metadata.json").exists())
        self.assertIsNotNone(self.workspaces.get(workspace.id))

        fingerprints2 = self.materializer.materialize(workspace.id, self.root / "exports")
        self.assertEqual(fingerprints1, fingerprints2)

        target_file = export_dir / "workspace_metadata.json"
        target_file.write_text('{"drift": true}\n', encoding="utf-8")
        self.materializer.materialize(workspace.id, self.root / "exports")
        events = self.governance.list_for_workspace(workspace.id)
        self.assertTrue(any(event.event_type == "sync_error" for event in events))

        dual_write_policy = (Path("docs") / "dual_write_policy.md").read_text(encoding="utf-8")
        self.assertIn("Drift rate", dual_write_policy)
        self.assertIn("Determinism", dual_write_policy)

    def test_api_health_and_docker_assets(self) -> None:
        head_revision = available_revisions()[-1].revision
        captured = {}

        def start_response(status, headers):
            captured["status"] = status
            captured["headers"] = headers

        old_dsn = os.environ.get("CANONICAL_DB_DSN")
        os.environ["CANONICAL_DB_DSN"] = self.config.dsn
        try:
            body = b"".join(
                application(
                    {
                        "PATH_INFO": "/health",
                        "REQUEST_METHOD": "GET",
                        "wsgi.input": io.BytesIO(),
                    },
                    start_response,
                )
            )
        finally:
            if old_dsn is None:
                os.environ.pop("CANONICAL_DB_DSN", None)
            else:
                os.environ["CANONICAL_DB_DSN"] = old_dsn

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(captured["status"], "200 OK")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["revision"], head_revision)

        dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
        self.assertIn("app.api_server", dockerfile)
        deployment_note = Path("docs/deployment_note.md").read_text(encoding="utf-8")
        self.assertIn("/health", deployment_note)


if __name__ == "__main__":
    unittest.main()
