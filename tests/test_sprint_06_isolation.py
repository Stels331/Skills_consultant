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
from app.canonical_db.model_updates import ClarificationEngine
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
from app.dialogue_api import DialogueApiService, _RUNTIME_STATE
from app.validation.workspace_isolation import IsolationFinding, WorkspaceIsolationValidator


class Sprint06IsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db_path = self.root / "canonical.sqlite3"
        self.config = DatabaseConfig(dsn=f"sqlite:///{self.db_path}", environment="test")
        self.old_dsn = os.environ.get("CANONICAL_DB_DSN")
        os.environ["CANONICAL_DB_DSN"] = self.config.dsn
        _RUNTIME_STATE.reset()

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
        self.governance = SqliteGovernanceEventRepository(self.factory)
        self.org_service = OrganizationService(self.organizations, self.memberships, self.profiles)
        self.clarifications = ClarificationEngine(__import__("app.canonical_db.model_updates", fromlist=["SqliteQuestionQueueRepository"]).SqliteQuestionQueueRepository(self.factory))

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
        self.other_org = Organization(id="org-2", name="Org Two", slug="org-two", owner_user_id=self.owner.id)
        self.org_service.create_organization(self.other_org)

        self.workspace_a, self.version_a = self._create_workspace("ws-1", self.organization.id, "Case A")
        self.workspace_b, self.version_b = self._create_workspace("ws-2", self.organization.id, "Case B")
        self.workspace_c, self.version_c = self._create_workspace("ws-3", self.other_org.id, "Case C")

        self._seed_workspace(
            workspace=self.workspace_a,
            version=self.version_a,
            claim_key="budget_limit",
            statement="Budget limit must not exceed 500k",
            question_reason="Need finance confirmation for Case A.",
        )
        self._seed_workspace(
            workspace=self.workspace_b,
            version=self.version_b,
            claim_key="delivery_window",
            statement="Delivery must finish before October",
            question_reason="Need schedule clarification for Case B.",
        )
        self._seed_workspace(
            workspace=self.workspace_c,
            version=self.version_c,
            claim_key="compliance_rule",
            statement="Compliance review must be approved by legal",
            question_reason="Need legal review clarification for Case C.",
        )

    def tearDown(self) -> None:
        _RUNTIME_STATE.reset()
        if self.old_dsn is None:
            os.environ.pop("CANONICAL_DB_DSN", None)
        else:
            os.environ["CANONICAL_DB_DSN"] = self.old_dsn
        self.tmp.cleanup()

    def _create_workspace(self, workspace_id: str, organization_id: str, title: str) -> tuple[Workspace, WorkspaceVersion]:
        workspace = Workspace(
            id=workspace_id,
            organization_id=organization_id,
            workspace_key=workspace_id,
            title=title,
            case_type="analysis_case",
            status="active",
            current_stage="analysis",
            active_model_version=1,
            created_by_user_id=self.owner.id,
            metadata={},
        )
        version = WorkspaceVersion(
            id=f"{workspace_id}:v1",
            organization_id=organization_id,
            workspace_id=workspace_id,
            version_no=1,
            version_label="v1",
            change_reason="seed",
            created_by=self.owner.id,
        )
        self.workspaces.upsert(workspace, version)
        return workspace, version

    def _seed_workspace(
        self,
        *,
        workspace: Workspace,
        version: WorkspaceVersion,
        claim_key: str,
        statement: str,
        question_reason: str,
    ) -> None:
        self.claims.create_claim(
            Claim(
                id=f"claim:{workspace.id}",
                organization_id=workspace.organization_id,
                workspace_id=workspace.id,
                workspace_version_id=version.id,
                claim_key=claim_key,
                claim_type="decision_constraint",
                statement=statement,
                epistemic_status="accepted",
                confidence_score=0.9,
                source_kind="source_fact",
                source_ref="seed.md",
            ),
            change_reason="seed",
            changed_by_actor=self.owner.id,
        )
        self.clarifications.open_question(
            organization_id=workspace.organization_id,
            workspace_id=workspace.id,
            session_id=None,
            reason="MISSING_CASE_INPUT",
            missing_knowledge=question_reason,
            impact_preview="Affects active case only.",
        )
        workspace_root = self.root / workspace.id / "analysis"
        workspace_root.mkdir(parents=True, exist_ok=True)
        (workspace_root / "brief.md").write_text(
            f"# Evidence\n{statement}\n# Unknowns\n{question_reason}\n",
            encoding="utf-8",
        )
        artifact = Artifact(
            id=f"artifact:{workspace.id}",
            organization_id=workspace.organization_id,
            workspace_id=workspace.id,
            workspace_version_id=version.id,
            artifact_type="analysis_brief",
            stage_name="analysis",
            artifact_key="analysis/brief.md",
            status="active",
            format="markdown",
            payload={},
            file_path="analysis/brief.md",
        )
        BM25SectionIndex(self.chunks).index_sections(
            organization_id=workspace.organization_id,
            workspace_id=workspace.id,
            artifacts=[artifact],
            workspace_root=self.root / workspace.id,
            revision=1,
            source_revision=f"{workspace.id}:r1",
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

    def test_runtime_reset_and_namespace_keys_on_workspace_switch(self) -> None:
        service = DialogueApiService(self.root)
        first = service.ask(
            {
                "organization_id": self.organization.id,
                "workspace_id": self.workspace_a.id,
                "session_id": "session-a",
                "user_id": self.owner.id,
                "question": "What budget limit must we follow?",
                "budget_profile": "standard",
            }
        )
        second = service.ask(
            {
                "organization_id": self.organization.id,
                "workspace_id": self.workspace_b.id,
                "session_id": "session-b",
                "user_id": self.owner.id,
                "question": "What delivery limit applies?",
                "budget_profile": "standard",
            }
        )
        self.assertFalse(first["runtime"]["reset_applied"])
        self.assertTrue(second["runtime"]["reset_applied"])
        self.assertTrue(first["runtime"]["namespace_key"].startswith(f"{self.organization.id}:{self.workspace_a.id}"))
        self.assertTrue(second["runtime"]["namespace_key"].startswith(f"{self.organization.id}:{self.workspace_b.id}"))
        events = self.governance.list_for_workspace(self.workspace_b.id)
        self.assertTrue(any(event.event_type == "workspace_runtime_reset" for event in events))

    def test_session_rebinding_is_rejected_across_workspaces(self) -> None:
        service = DialogueApiService(self.root)
        service.ask(
            {
                "organization_id": self.organization.id,
                "workspace_id": self.workspace_a.id,
                "session_id": "shared-session",
                "user_id": self.owner.id,
                "question": "What budget limit must we follow?",
                "budget_profile": "standard",
            }
        )
        with self.assertRaises(PermissionError):
            service.ask(
                {
                    "organization_id": self.organization.id,
                    "workspace_id": self.workspace_b.id,
                    "session_id": "shared-session",
                    "user_id": self.owner.id,
                    "question": "What delivery limit applies?",
                    "budget_profile": "standard",
                }
            )

    def test_version_state_and_open_questions_are_workspace_scoped(self) -> None:
        service = DialogueApiService(self.root)
        state_a = service.version_state(workspace_id=self.workspace_a.id)
        state_b = service.version_state(workspace_id=self.workspace_b.id)
        questions_a = service.open_questions(workspace_id=self.workspace_a.id)
        questions_b = service.open_questions(workspace_id=self.workspace_b.id)
        self.assertNotEqual(state_a["runtime"]["cache_key"], state_b["runtime"]["cache_key"])
        self.assertTrue(all(item["question"].endswith("Case A.") for item in questions_a["unknowns"]))
        self.assertTrue(all(item["question"].endswith("Case B.") for item in questions_b["unknowns"]))

    def test_bm25_and_evidence_queries_are_namespaced(self) -> None:
        index = BM25SectionIndex(self.chunks)
        hits_a = index.search(
            organization_id=self.organization.id,
            workspace_id=self.workspace_a.id,
            query="budget limit",
        )
        hits_b = index.search(
            organization_id=self.organization.id,
            workspace_id=self.workspace_b.id,
            query="delivery limit",
        )
        self.assertTrue(hits_a)
        self.assertTrue(hits_b)
        self.assertTrue(all(item.chunk_id.startswith(f"{self.workspace_a.id}:") for item in hits_a))
        self.assertTrue(all(item.chunk_id.startswith(f"{self.workspace_b.id}:") for item in hits_b))

        evidence_a = json.loads(self._call(f"/api/workspaces/{self.workspace_a.id}/evidence")[1])
        evidence_b = json.loads(self._call(f"/api/workspaces/{self.workspace_b.id}/evidence")[1])
        self.assertTrue(all(item["chunk_id"].startswith(f"{self.workspace_a.id}:") for item in evidence_a["artifacts"]))
        self.assertTrue(all(item["chunk_id"].startswith(f"{self.workspace_b.id}:") for item in evidence_b["artifacts"]))

    def test_prompt_leak_is_blocked_and_logged(self) -> None:
        service = DialogueApiService(self.root)
        original_build = service._prompts.build

        def leaking_build(bundle, question):
            return original_build(bundle, question) + f"\nworkspace_id={self.workspace_b.id}\n"

        service._prompts.build = leaking_build
        response = service.ask(
            {
                "organization_id": self.organization.id,
                "workspace_id": self.workspace_a.id,
                "session_id": "leak-session",
                "user_id": self.owner.id,
                "question": "What budget limit must we follow?",
                "budget_profile": "standard",
            }
        )
        self.assertEqual(response["answer"]["validation_status"], "block")
        self.assertIn("WORKSPACE_CONTAMINATION_BLOCKED", response["validation"]["reason_codes"])
        self.assertEqual(response["answer"]["used_claims"], [])
        events = self.governance.list_for_workspace(self.workspace_a.id)
        blocked = [event for event in events if event.event_type == "workspace_contamination_blocked"]
        self.assertTrue(blocked)
        self.assertIn("PROMPT_WORKSPACE_LEAK", blocked[-1].payload["reason_codes"])

    def test_validator_extension_point_blocks_future_decision_entities(self) -> None:
        validator = WorkspaceIsolationValidator()

        def decision_entity_validator(context, entities):
            findings: list[IsolationFinding] = []
            for entity in entities:
                if entity.get("workspace_id") != context.workspace_id:
                    findings.append(
                        IsolationFinding(
                            code="DECISION_ENTITY_WORKSPACE_LEAK",
                            severity="block",
                            message="Decision entity belongs to foreign workspace",
                        )
                    )
            return findings

        validator.register_entity_validator("decision_entities", decision_entity_validator)
        context = DialogueApiService(self.root)._build_context(
            organization_id=self.organization.id,
            workspace_id=self.workspace_a.id,
            session_id="s-1",
            user_id=self.owner.id,
        )
        result = validator.validate(
            context=context,
            prompt_text=f"workspace_id={self.workspace_a.id}",
            answer_payload={
                "used_claims": [],
                "used_artifacts": [],
                "prompt_fragments": [],
                "lineage_refs": [],
                "decision_entities": [{"workspace_id": self.workspace_b.id, "decision_id": "dec-1"}],
            },
        )
        self.assertEqual(result.status, "block")
        self.assertIn("DECISION_ENTITY_WORKSPACE_LEAK", result.reason_codes)

    def test_ui_switch_guards_are_rendered(self) -> None:
        status, body = self._call(
            f"/ui/workspaces/{self.workspace_b.id}",
            query=f"organization_id={self.organization.id}",
        )
        self.assertEqual(status, "200 OK")
        self.assertIn("Active case: Case B", body)
        self.assertIn("Previous draft discarded after workspace switch", body)
        self.assertIn("dialogue-active-workspace", body)
        self.assertIn("dialogue-composer-draft", body)
        self.assertIn(f'data-workspace="{self.workspace_b.id}"', body)

    def test_cross_tenant_isolation_and_future_vector_placeholder(self) -> None:
        status, body = self._call(f"/api/workspaces/{self.workspace_c.id}/evidence")
        self.assertEqual(status, "200 OK")
        payload = json.loads(body)
        self.assertTrue(payload["runtime"]["namespace_key"].startswith(f"{self.other_org.id}:{self.workspace_c.id}"))
        self.assertTrue(payload["runtime"]["cache_key"].startswith(f"{self.other_org.id}:{self.workspace_c.id}:retrieval"))
        self.assertTrue(all(item["chunk_id"].startswith(f"{self.workspace_c.id}:") for item in payload["artifacts"]))


if __name__ == "__main__":
    unittest.main()
