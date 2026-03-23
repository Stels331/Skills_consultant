from __future__ import annotations

import io
import json
import os
import tempfile
from pathlib import Path
import unittest

from app.api_server import application
from app.canonical_db.config import DatabaseConfig, connect
from app.canonical_db.dialogue_backend import BM25SectionIndex, SqliteRetrievalChunkRepository
from app.canonical_db.domain import Artifact, Claim, Organization, User, UserProfile, Workspace, WorkspaceVersion
from app.canonical_db.migration_runner import upgrade
from app.canonical_db.repositories import (
    SqliteClaimRepository,
    SqliteMembershipRepository,
    SqliteOrganizationRepository,
    SqliteUserProfileRepository,
    SqliteUserRepository,
    SqliteWorkspaceRepository,
    TransactionManager,
)
from app.canonical_db.tenant_auth import OrganizationService
from app.dialogue_api import render_answer_card
from app.pipeline.section_contract_guard import SectionContractGuard
from app.validation.dialogue_validator import FPFResponseValidator


class Sprint04ValidationUiTests(unittest.TestCase):
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
        self.chunks = SqliteRetrievalChunkRepository(self.factory, TransactionManager(self.factory))
        self.org_service = OrganizationService(self.organizations, self.memberships, self.profiles)

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
            title="Validation Workspace",
            case_type="analysis_case",
            status="active",
            current_stage="dialogue",
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
        self.claims.create_claim(
            Claim(
                id="claim-1",
                organization_id=self.organization.id,
                workspace_id=self.workspace.id,
                workspace_version_id=self.version.id,
                claim_key="budget_limit",
                claim_type="decision_constraint",
                statement="Budget limit must not exceed 500k",
                epistemic_status="accepted",
                confidence_score=0.8,
                source_kind="source_fact",
                source_ref="raw/input.md",
            ),
            change_reason="seed",
            changed_by_actor=self.owner.id,
        )

        workspace_root = self.root / self.workspace.id
        workspace_root.mkdir(parents=True, exist_ok=True)
        (workspace_root / "analysis").mkdir(exist_ok=True)
        (workspace_root / "analysis" / "brief.md").write_text(
            "# Budget\nBudget explanation section.\n# Unknowns\nNeed confirmation from finance.\n",
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
            payload={},
            file_path="analysis/brief.md",
        )
        BM25SectionIndex(self.chunks).index_sections(
            organization_id=self.organization.id,
            workspace_id=self.workspace.id,
            artifacts=[artifact],
            workspace_root=workspace_root,
            revision=1,
            source_revision="artifact-r1",
        )

    def tearDown(self) -> None:
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

    def test_fpf_response_validator_outcomes_and_escalation_contract(self) -> None:
        validator = FPFResponseValidator()
        passed = validator.validate(
            answer_text="Grounded answer",
            workspace_id="ws-1",
            expected_workspace_id="ws-1",
            tier="cheap",
            escalation_used=False,
            answer_payload={
                "used_claims": [{"id": "claim-1", "statement": "Budget limit must not exceed 500k"}],
                "used_artifacts": [{"chunk_id": "ws-1:artifact-1:0"}],
                "open_unknowns": [],
            },
        )
        self.assertEqual(passed.status, "pass")

        degraded = validator.validate(
            answer_text="This is definitely correct.",
            workspace_id="ws-1",
            expected_workspace_id="ws-1",
            tier="balanced",
            escalation_used=False,
            answer_payload={
                "used_claims": [{"id": "claim-1", "statement": "Budget limit must not exceed 500k"}],
                "used_artifacts": [],
                "open_unknowns": ["Need finance confirmation"],
            },
        )
        self.assertEqual(degraded.status, "degrade")
        self.assertIn("MISSING_CITATION", degraded.reason_codes)

        blocked = validator.validate(
            answer_text="The spacecraft engine is guaranteed to work.",
            workspace_id="ws-2",
            expected_workspace_id="ws-1",
            tier="cheap",
            escalation_used=False,
            answer_payload={"used_claims": [], "used_artifacts": [], "open_unknowns": []},
        )
        self.assertEqual(blocked.status, "block")
        self.assertEqual(blocked.next_tier, "balanced")

        terminal = validator.validate(
            answer_text="Bad answer",
            workspace_id="ws-2",
            expected_workspace_id="ws-1",
            tier="premium",
            escalation_used=True,
            answer_payload={"used_claims": [], "used_artifacts": [], "open_unknowns": []},
        )
        self.assertEqual(terminal.status, "block")
        self.assertIsNone(terminal.next_tier)
        self.assertEqual(terminal.final_outcome, "block")

    def test_section_contract_guard_repairs_before_block_and_emits_audit(self) -> None:
        guard = SectionContractGuard()
        result = guard.validate_before_write(
            body="## facts\n- ok\n",
            required_sections=["## facts", "## chr_targets"],
            repair_fn=lambda missing: "## facts\n- ok\n## chr_targets\n- repaired\n",
        )
        self.assertEqual(result.route, "degrade")
        self.assertEqual(result.audit.parse_quality, "repaired")
        self.assertEqual(result.audit.artifact_trust_level, "trusted")
        self.assertEqual(result.audit.repair_attempts, 1)

        blocked = guard.validate_before_write(
            body="## facts\n- ok\n",
            required_sections=["## facts", "## chr_targets"],
            repair_fn=lambda missing: "## facts\n- still broken\n",
        )
        self.assertEqual(blocked.route, "block")
        self.assertEqual(blocked.audit.artifact_trust_level, "degraded")
        self.assertTrue(blocked.missing_sections)

    def test_dialogue_api_contract_history_evidence_open_questions_and_version_state(self) -> None:
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
            },
        )
        self.assertEqual(status, "200 OK")
        payload = json.loads(body)
        self.assertEqual(payload["workspace_id"], self.workspace.id)
        self.assertIn(payload["answer"]["validation_status"], {"pass", "degrade"})
        self.assertIn("used_claims", payload["answer"])
        self.assertIn("governance", payload)
        self.assertIn("lineage", payload["governance"])

        status, body = self._call(
            "/api/dialogue/sessions/session-1/history",
            query=f"workspace_id={self.workspace.id}",
        )
        history = json.loads(body)
        self.assertEqual(len(history["messages"]), 2)
        self.assertTrue(all(msg["workspace_id"] == self.workspace.id for msg in history["messages"]))

        status, body = self._call(f"/api/workspaces/{self.workspace.id}/evidence")
        evidence = json.loads(body)
        self.assertIn("claims", evidence)
        self.assertIn("artifacts", evidence)
        self.assertIn("workspace_version_id", evidence)

        status, body = self._call(f"/api/workspaces/{self.workspace.id}/open-questions")
        unknowns = json.loads(body)
        self.assertIn("unknowns", unknowns)

        status, body = self._call(f"/api/workspaces/{self.workspace.id}/version-state")
        version_state = json.loads(body)
        self.assertEqual(version_state["workspace_id"], self.workspace.id)
        self.assertIn("workspace_version_id", version_state)
        self.assertIn("graph_version", version_state)

    def test_ui_case_first_shell_and_answer_card_ux(self) -> None:
        status, body = self._call(
            f"/ui/workspaces/{self.workspace.id}",
            query=f"organization_id={self.organization.id}",
        )
        self.assertEqual(status, "200 OK")
        self.assertIn("Dialogue Console", body)
        self.assertIn(self.workspace.id, body)
        self.assertIn(self.organization.name, body)
        self.assertIn("Evidence / Claims Panel", body)
        self.assertIn("Open Questions Panel", body)

        blocked_html = render_answer_card(
            {
                "validation_status": "block",
                "text": "",
                "safe_fallback": "Ask a clarification question.",
                "confidence_score": 0.0,
                "epistemic_status": "blocked",
                "reason_codes": ["UNSUPPORTED_CONCLUSION"],
            }
        )
        self.assertIn("Safe Fallback", blocked_html)
        self.assertNotIn("Grounded Answer</h3><p></p>", blocked_html)

        degraded_html = render_answer_card(
            {
                "validation_status": "degrade",
                "text": "Limited answer",
                "safe_fallback": None,
                "confidence_score": 0.4,
                "epistemic_status": "degraded",
                "reason_codes": ["MISSING_CITATION"],
            }
        )
        self.assertIn("Warning.", degraded_html)
        self.assertIn("MISSING_CITATION", degraded_html)


if __name__ == "__main__":
    unittest.main()
