from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
import json
import sqlite3
from typing import Callable, Iterator, Sequence

from app.canonical_db.domain import (
    Artifact,
    AuthSession,
    Claim,
    ClaimVersion,
    ClaimRelation,
    DialogueSession,
    GovernanceEvent,
    MaterializedArtifactIndexEntry,
    Membership,
    Organization,
    ProjectionSnapshot,
    User,
    UserProfile,
    Workspace,
    WorkspaceVersion,
)


ConnectionFactory = Callable[[], sqlite3.Connection]


def _dumps(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _loads(payload: str | None) -> dict:
    if not payload:
        return {}
    return json.loads(payload)


class TransactionManager:
    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connection_factory()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


class UserRepository(ABC):
    @abstractmethod
    def upsert(self, user: User) -> User:
        raise NotImplementedError

    @abstractmethod
    def get(self, user_id: str) -> User | None:
        raise NotImplementedError

    @abstractmethod
    def get_by_email(self, email: str) -> User | None:
        raise NotImplementedError


class OrganizationRepository(ABC):
    @abstractmethod
    def upsert(self, organization: Organization) -> Organization:
        raise NotImplementedError

    @abstractmethod
    def get(self, organization_id: str) -> Organization | None:
        raise NotImplementedError


class UserProfileRepository(ABC):
    @abstractmethod
    def upsert(self, profile: UserProfile) -> UserProfile:
        raise NotImplementedError

    @abstractmethod
    def get(self, user_id: str) -> UserProfile | None:
        raise NotImplementedError


class MembershipRepository(ABC):
    @abstractmethod
    def upsert(self, membership: Membership) -> Membership:
        raise NotImplementedError

    @abstractmethod
    def get(self, organization_id: str, user_id: str) -> Membership | None:
        raise NotImplementedError

    @abstractmethod
    def list_for_user(self, user_id: str) -> list[Membership]:
        raise NotImplementedError


class WorkspaceRepository(ABC):
    @abstractmethod
    def upsert(self, workspace: Workspace, version: WorkspaceVersion) -> Workspace:
        raise NotImplementedError

    @abstractmethod
    def get(self, workspace_id: str) -> Workspace | None:
        raise NotImplementedError

    @abstractmethod
    def get_version(self, workspace_id: str, version_no: int) -> WorkspaceVersion | None:
        raise NotImplementedError


class ArtifactRepository(ABC):
    @abstractmethod
    def upsert_many(self, artifacts: Sequence[Artifact]) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_for_workspace(self, workspace_id: str) -> list[Artifact]:
        raise NotImplementedError


class ClaimRepository(ABC):
    @abstractmethod
    def replace_workspace_claims(
        self,
        workspace_id: str,
        claims: Sequence[Claim],
        relations: Sequence[ClaimRelation],
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_for_workspace(self, workspace_id: str) -> list[Claim]:
        raise NotImplementedError

    @abstractmethod
    def get_by_key(self, workspace_id: str, claim_key: str) -> Claim | None:
        raise NotImplementedError

    @abstractmethod
    def list_versions(self, claim_id: str) -> list[ClaimVersion]:
        raise NotImplementedError

    @abstractmethod
    def create_claim(self, claim: Claim, *, change_reason: str, changed_by_actor: str) -> Claim:
        raise NotImplementedError

    @abstractmethod
    def update_claim(
        self,
        claim_id: str,
        *,
        workspace_version_id: str,
        claim_type: str,
        statement: str,
        epistemic_status: str,
        confidence_score: float,
        source_kind: str,
        source_ref: str,
        attributes: dict,
        change_reason: str,
        changed_by_actor: str,
    ) -> Claim:
        raise NotImplementedError

    @abstractmethod
    def add_relation(self, relation: ClaimRelation) -> ClaimRelation:
        raise NotImplementedError

    @abstractmethod
    def list_relations_for_workspace(self, workspace_id: str) -> list[ClaimRelation]:
        raise NotImplementedError


class AuthSessionRepository(ABC):
    @abstractmethod
    def upsert(self, session: AuthSession) -> AuthSession:
        raise NotImplementedError

    @abstractmethod
    def get(self, session_id: str) -> AuthSession | None:
        raise NotImplementedError


class ProjectionSnapshotRepository(ABC):
    @abstractmethod
    def upsert_many(self, snapshots: Sequence[ProjectionSnapshot]) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_for_workspace(self, workspace_id: str) -> list[ProjectionSnapshot]:
        raise NotImplementedError

    @abstractmethod
    def mark_stale(self, workspace_id: str, projection_types: Sequence[str]) -> None:
        raise NotImplementedError


class MaterializedArtifactIndexRepository(ABC):
    @abstractmethod
    def replace_for_workspace(self, workspace_id: str, entries: Sequence[MaterializedArtifactIndexEntry]) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_for_workspace(self, workspace_id: str) -> list[MaterializedArtifactIndexEntry]:
        raise NotImplementedError


class DialogueSessionRepository(ABC):
    @abstractmethod
    def upsert(self, session: DialogueSession) -> DialogueSession:
        raise NotImplementedError

    @abstractmethod
    def get(self, session_id: str) -> DialogueSession | None:
        raise NotImplementedError


class GovernanceEventRepository(ABC):
    @abstractmethod
    def append(self, event: GovernanceEvent) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_for_workspace(self, workspace_id: str) -> list[GovernanceEvent]:
        raise NotImplementedError


class SqliteUserRepository(UserRepository):
    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def upsert(self, user: User) -> User:
        with self._connection_factory() as connection:
            connection.execute(
                """
                INSERT INTO users (id, email, password_hash, display_name, status)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    email = excluded.email,
                    password_hash = excluded.password_hash,
                    display_name = excluded.display_name,
                    status = excluded.status,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user.id, user.email, user.password_hash, user.display_name, user.status),
            )
        return user

    def get(self, user_id: str) -> User | None:
        with self._connection_factory() as connection:
            row = connection.execute(
                "SELECT id, email, password_hash, display_name, status FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        return None if row is None else User(**dict(row))

    def get_by_email(self, email: str) -> User | None:
        with self._connection_factory() as connection:
            row = connection.execute(
                "SELECT id, email, password_hash, display_name, status FROM users WHERE email = ?",
                (email,),
            ).fetchone()
        return None if row is None else User(**dict(row))


class SqliteOrganizationRepository(OrganizationRepository):
    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def upsert(self, organization: Organization) -> Organization:
        with self._connection_factory() as connection:
            connection.execute(
                """
                INSERT INTO organizations (id, name, slug, owner_user_id, status, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    slug = excluded.slug,
                    owner_user_id = excluded.owner_user_id,
                    status = excluded.status,
                    metadata_json = excluded.metadata_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    organization.id,
                    organization.name,
                    organization.slug,
                    organization.owner_user_id,
                    organization.status,
                    _dumps(organization.metadata),
                ),
            )
        return organization

    def get(self, organization_id: str) -> Organization | None:
        with self._connection_factory() as connection:
            row = connection.execute(
                """
                SELECT id, name, slug, owner_user_id, status, metadata_json
                FROM organizations WHERE id = ?
                """,
                (organization_id,),
            ).fetchone()
        if row is None:
            return None
        payload = dict(row)
        payload["metadata"] = _loads(payload.pop("metadata_json"))
        return Organization(**payload)


class SqliteUserProfileRepository(UserProfileRepository):
    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def upsert(self, profile: UserProfile) -> UserProfile:
        with self._connection_factory() as connection:
            connection.execute(
                """
                INSERT INTO user_profiles (user_id, active_organization_id, settings_json)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    active_organization_id = excluded.active_organization_id,
                    settings_json = excluded.settings_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (profile.user_id, profile.active_organization_id, _dumps(profile.settings)),
            )
        return profile

    def get(self, user_id: str) -> UserProfile | None:
        with self._connection_factory() as connection:
            row = connection.execute(
                """
                SELECT user_id, active_organization_id, settings_json
                FROM user_profiles
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        payload = dict(row)
        payload["settings"] = _loads(payload.pop("settings_json"))
        return UserProfile(**payload)


class SqliteMembershipRepository(MembershipRepository):
    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def upsert(self, membership: Membership) -> Membership:
        with self._connection_factory() as connection:
            connection.execute(
                """
                INSERT INTO memberships (
                    id, organization_id, user_id, role, status, invited_by_user_id, joined_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    role = excluded.role,
                    status = excluded.status,
                    invited_by_user_id = excluded.invited_by_user_id,
                    joined_at = excluded.joined_at,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    membership.id,
                    membership.organization_id,
                    membership.user_id,
                    membership.role,
                    membership.status,
                    membership.invited_by_user_id,
                    membership.joined_at,
                ),
            )
        return membership

    def get(self, organization_id: str, user_id: str) -> Membership | None:
        with self._connection_factory() as connection:
            row = connection.execute(
                """
                SELECT id, organization_id, user_id, role, status, invited_by_user_id, joined_at
                FROM memberships
                WHERE organization_id = ? AND user_id = ?
                """,
                (organization_id, user_id),
            ).fetchone()
        return None if row is None else Membership(**dict(row))

    def list_for_user(self, user_id: str) -> list[Membership]:
        with self._connection_factory() as connection:
            rows = connection.execute(
                """
                SELECT id, organization_id, user_id, role, status, invited_by_user_id, joined_at
                FROM memberships
                WHERE user_id = ?
                ORDER BY organization_id, created_at
                """,
                (user_id,),
            ).fetchall()
        return [Membership(**dict(row)) for row in rows]


class SqliteWorkspaceRepository(WorkspaceRepository):
    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def upsert(self, workspace: Workspace, version: WorkspaceVersion) -> Workspace:
        with self._connection_factory() as connection:
            connection.execute(
                """
                INSERT INTO workspaces (
                    id, organization_id, workspace_key, title, case_type, status,
                    current_stage, active_model_version, created_by_user_id, metadata_json,
                    reentry_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    case_type = excluded.case_type,
                    status = excluded.status,
                    current_stage = excluded.current_stage,
                    active_model_version = excluded.active_model_version,
                    created_by_user_id = excluded.created_by_user_id,
                    metadata_json = excluded.metadata_json,
                    reentry_status = excluded.reentry_status,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    workspace.id,
                    workspace.organization_id,
                    workspace.workspace_key,
                    workspace.title,
                    workspace.case_type,
                    workspace.status,
                    workspace.current_stage,
                    workspace.active_model_version,
                    workspace.created_by_user_id,
                    _dumps(workspace.metadata),
                    workspace.reentry_status,
                ),
            )
            connection.execute(
                """
                INSERT INTO workspace_versions (
                    id, organization_id, workspace_id, version_no, version_label,
                    change_reason, created_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    version_label = excluded.version_label,
                    change_reason = excluded.change_reason,
                    created_by = excluded.created_by
                """,
                (
                    version.id,
                    version.organization_id,
                    version.workspace_id,
                    version.version_no,
                    version.version_label,
                    version.change_reason,
                    version.created_by,
                ),
            )
        return workspace

    def get(self, workspace_id: str) -> Workspace | None:
        with self._connection_factory() as connection:
            row = connection.execute(
                """
                SELECT id, organization_id, workspace_key, title, case_type, status,
                       current_stage, active_model_version, created_by_user_id, metadata_json,
                       reentry_status
                FROM workspaces WHERE id = ?
                """,
                (workspace_id,),
            ).fetchone()
        if row is None:
            return None
        payload = dict(row)
        payload["metadata"] = _loads(payload.pop("metadata_json"))
        return Workspace(**payload)

    def get_version(self, workspace_id: str, version_no: int) -> WorkspaceVersion | None:
        with self._connection_factory() as connection:
            row = connection.execute(
                """
                SELECT id, organization_id, workspace_id, version_no, version_label,
                       change_reason, created_by
                FROM workspace_versions
                WHERE workspace_id = ? AND version_no = ?
                """,
                (workspace_id, version_no),
            ).fetchone()
        return None if row is None else WorkspaceVersion(**dict(row))


class SqliteArtifactRepository(ArtifactRepository):
    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def upsert_many(self, artifacts: Sequence[Artifact]) -> None:
        with self._connection_factory() as connection:
            connection.executemany(
                """
                INSERT INTO artifacts (
                    id, organization_id, workspace_id, workspace_version_id, artifact_type,
                    stage_name, artifact_key, status, format, payload_json, file_path, summary_text
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    artifact_type = excluded.artifact_type,
                    stage_name = excluded.stage_name,
                    artifact_key = excluded.artifact_key,
                    status = excluded.status,
                    format = excluded.format,
                    payload_json = excluded.payload_json,
                    file_path = excluded.file_path,
                    summary_text = excluded.summary_text,
                    updated_at = CURRENT_TIMESTAMP
                """,
                [
                    (
                        artifact.id,
                        artifact.organization_id,
                        artifact.workspace_id,
                        artifact.workspace_version_id,
                        artifact.artifact_type,
                        artifact.stage_name,
                        artifact.artifact_key,
                        artifact.status,
                        artifact.format,
                        _dumps(artifact.payload),
                        artifact.file_path,
                        artifact.summary_text,
                    )
                    for artifact in artifacts
                ],
            )

    def list_for_workspace(self, workspace_id: str) -> list[Artifact]:
        with self._connection_factory() as connection:
            rows = connection.execute(
                """
                SELECT id, organization_id, workspace_id, workspace_version_id, artifact_type,
                       stage_name, artifact_key, status, format, payload_json, file_path, summary_text
                FROM artifacts
                WHERE workspace_id = ?
                ORDER BY artifact_key
                """,
                (workspace_id,),
            ).fetchall()
        result = []
        for row in rows:
            payload = dict(row)
            payload["payload"] = _loads(payload.pop("payload_json"))
            result.append(Artifact(**payload))
        return result


class SqliteClaimRepository(ClaimRepository):
    def __init__(
        self,
        connection_factory: ConnectionFactory,
        transaction_manager: TransactionManager | None = None,
    ):
        self._connection_factory = connection_factory
        self._transactions = transaction_manager or TransactionManager(connection_factory)

    def replace_workspace_claims(
        self,
        workspace_id: str,
        claims: Sequence[Claim],
        relations: Sequence[ClaimRelation],
    ) -> None:
        with self._transactions.transaction() as connection:
            connection.execute("DELETE FROM claim_relations WHERE workspace_id = ?", (workspace_id,))
            connection.execute("DELETE FROM claim_versions WHERE workspace_id = ?", (workspace_id,))
            connection.execute("DELETE FROM claims WHERE workspace_id = ?", (workspace_id,))

            for claim in claims:
                connection.execute(
                    """
                    INSERT INTO claims (
                        id, organization_id, workspace_id, workspace_version_id, claim_key, claim_type,
                        statement, epistemic_status, confidence_score, source_kind, source_ref,
                        attributes_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        claim.id,
                        claim.organization_id,
                        claim.workspace_id,
                        claim.workspace_version_id,
                        claim.claim_key,
                        claim.claim_type,
                        claim.statement,
                        claim.epistemic_status,
                        claim.confidence_score,
                        claim.source_kind,
                        claim.source_ref,
                        _dumps(claim.attributes),
                    ),
                )
                self._insert_claim_version(
                    connection,
                    claim=claim,
                    version_no=1,
                    change_reason="replace_workspace_claims",
                    changed_by_actor="system",
                )

            for relation in relations:
                self._insert_relation(connection, relation)

    def list_for_workspace(self, workspace_id: str) -> list[Claim]:
        with self._connection_factory() as connection:
            rows = connection.execute(
                """
                SELECT id, organization_id, workspace_id, workspace_version_id, claim_key, claim_type,
                       statement, epistemic_status, confidence_score, source_kind, source_ref,
                       attributes_json
                FROM claims
                WHERE workspace_id = ?
                ORDER BY claim_key
                """,
                (workspace_id,),
            ).fetchall()
        claims = []
        for row in rows:
            payload = dict(row)
            payload["attributes"] = _loads(payload.pop("attributes_json"))
            claims.append(Claim(**payload))
        return claims

    def get_by_key(self, workspace_id: str, claim_key: str) -> Claim | None:
        with self._connection_factory() as connection:
            row = connection.execute(
                """
                SELECT id, organization_id, workspace_id, workspace_version_id, claim_key, claim_type,
                       statement, epistemic_status, confidence_score, source_kind, source_ref,
                       attributes_json
                FROM claims
                WHERE workspace_id = ? AND claim_key = ?
                """,
                (workspace_id, claim_key),
            ).fetchone()
        if row is None:
            return None
        payload = dict(row)
        payload["attributes"] = _loads(payload.pop("attributes_json"))
        return Claim(**payload)

    def list_versions(self, claim_id: str) -> list[ClaimVersion]:
        with self._connection_factory() as connection:
            rows = connection.execute(
                """
                SELECT id, organization_id, workspace_id, claim_id, version_no, claim_type, statement,
                       epistemic_status, confidence_score, source_kind, source_ref, attributes_json,
                       change_reason, changed_by_actor
                FROM claim_versions
                WHERE claim_id = ?
                ORDER BY version_no
                """,
                (claim_id,),
            ).fetchall()
        versions = []
        for row in rows:
            payload = dict(row)
            payload["attributes"] = _loads(payload.pop("attributes_json"))
            versions.append(ClaimVersion(**payload))
        return versions

    def create_claim(self, claim: Claim, *, change_reason: str, changed_by_actor: str) -> Claim:
        with self._transactions.transaction() as connection:
            connection.execute(
                """
                INSERT INTO claims (
                    id, organization_id, workspace_id, workspace_version_id, claim_key, claim_type,
                    statement, epistemic_status, confidence_score, source_kind, source_ref,
                    attributes_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim.id,
                    claim.organization_id,
                    claim.workspace_id,
                    claim.workspace_version_id,
                    claim.claim_key,
                    claim.claim_type,
                    claim.statement,
                    claim.epistemic_status,
                    claim.confidence_score,
                    claim.source_kind,
                    claim.source_ref,
                    _dumps(claim.attributes),
                ),
            )
            self._insert_claim_version(
                connection,
                claim=claim,
                version_no=1,
                change_reason=change_reason,
                changed_by_actor=changed_by_actor,
            )
        return claim

    def update_claim(
        self,
        claim_id: str,
        *,
        workspace_version_id: str,
        claim_type: str,
        statement: str,
        epistemic_status: str,
        confidence_score: float,
        source_kind: str,
        source_ref: str,
        attributes: dict,
        change_reason: str,
        changed_by_actor: str,
    ) -> Claim:
        with self._transactions.transaction() as connection:
            current_row = connection.execute(
                """
                SELECT id, organization_id, workspace_id, workspace_version_id, claim_key, claim_type,
                       statement, epistemic_status, confidence_score, source_kind, source_ref,
                       attributes_json
                FROM claims WHERE id = ?
                """,
                (claim_id,),
            ).fetchone()
            if current_row is None:
                raise KeyError(f"Unknown claim: {claim_id}")
            current_payload = dict(current_row)
            current_payload["attributes"] = _loads(current_payload.pop("attributes_json"))
            current_claim = Claim(**current_payload)
            updated_claim = Claim(
                id=current_claim.id,
                organization_id=current_claim.organization_id,
                workspace_id=current_claim.workspace_id,
                workspace_version_id=workspace_version_id,
                claim_key=current_claim.claim_key,
                claim_type=claim_type,
                statement=statement,
                epistemic_status=epistemic_status,
                confidence_score=confidence_score,
                source_kind=source_kind,
                source_ref=source_ref,
                attributes=attributes,
            )
            connection.execute(
                """
                UPDATE claims SET
                    workspace_version_id = ?,
                    claim_type = ?,
                    statement = ?,
                    epistemic_status = ?,
                    confidence_score = ?,
                    source_kind = ?,
                    source_ref = ?,
                    attributes_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    updated_claim.workspace_version_id,
                    updated_claim.claim_type,
                    updated_claim.statement,
                    updated_claim.epistemic_status,
                    updated_claim.confidence_score,
                    updated_claim.source_kind,
                    updated_claim.source_ref,
                    _dumps(updated_claim.attributes),
                    claim_id,
                ),
            )
            version_no = int(
                connection.execute(
                    "SELECT COALESCE(MAX(version_no), 0) FROM claim_versions WHERE claim_id = ?",
                    (claim_id,),
                ).fetchone()[0]
            ) + 1
            self._insert_claim_version(
                connection,
                claim=updated_claim,
                version_no=version_no,
                change_reason=change_reason,
                changed_by_actor=changed_by_actor,
            )
        return updated_claim

    def add_relation(self, relation: ClaimRelation) -> ClaimRelation:
        with self._transactions.transaction() as connection:
            self._validate_relation_workspace(connection, relation)
            self._insert_relation(connection, relation)
        return relation

    def list_relations_for_workspace(self, workspace_id: str) -> list[ClaimRelation]:
        with self._connection_factory() as connection:
            rows = connection.execute(
                """
                SELECT id, organization_id, workspace_id, from_claim_id, to_claim_id,
                       relation_type, weight, metadata_json
                FROM claim_relations
                WHERE workspace_id = ?
                ORDER BY relation_type, from_claim_id, to_claim_id
                """,
                (workspace_id,),
            ).fetchall()
        relations = []
        for row in rows:
            payload = dict(row)
            payload["metadata"] = _loads(payload.pop("metadata_json"))
            relations.append(ClaimRelation(**payload))
        return relations

    def _insert_claim_version(
        self,
        connection: sqlite3.Connection,
        *,
        claim: Claim,
        version_no: int,
        change_reason: str,
        changed_by_actor: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO claim_versions (
                id, organization_id, workspace_id, claim_id, version_no, claim_type, statement,
                epistemic_status, confidence_score, source_kind, source_ref, attributes_json,
                change_reason, changed_by_actor
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"{claim.id}:v{version_no}",
                claim.organization_id,
                claim.workspace_id,
                claim.id,
                version_no,
                claim.claim_type,
                claim.statement,
                claim.epistemic_status,
                claim.confidence_score,
                claim.source_kind,
                claim.source_ref,
                _dumps(claim.attributes),
                change_reason,
                changed_by_actor,
            ),
        )

    def _insert_relation(self, connection: sqlite3.Connection, relation: ClaimRelation) -> None:
        connection.execute(
            """
            INSERT INTO claim_relations (
                id, organization_id, workspace_id, from_claim_id, to_claim_id,
                relation_type, weight, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                relation.id,
                relation.organization_id,
                relation.workspace_id,
                relation.from_claim_id,
                relation.to_claim_id,
                relation.relation_type,
                relation.weight,
                _dumps(relation.metadata),
            ),
        )

    def _validate_relation_workspace(
        self,
        connection: sqlite3.Connection,
        relation: ClaimRelation,
    ) -> None:
        rows = connection.execute(
            """
            SELECT id, workspace_id, organization_id
            FROM claims
            WHERE id IN (?, ?)
            ORDER BY id
            """,
            (relation.from_claim_id, relation.to_claim_id),
        ).fetchall()
        if len(rows) != 2:
            raise sqlite3.IntegrityError("Relation endpoints must exist")
        for row in rows:
            if row["workspace_id"] != relation.workspace_id or row["organization_id"] != relation.organization_id:
                raise sqlite3.IntegrityError("Relation cannot connect claims across workspaces or organizations")


class SqliteDialogueSessionRepository(DialogueSessionRepository):
    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def upsert(self, session: DialogueSession) -> DialogueSession:
        with self._connection_factory() as connection:
            connection.execute(
                """
                INSERT INTO dialogue_sessions (
                    id, organization_id, workspace_id, created_by_user_id, status,
                    active_workspace_version_id, title
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    active_workspace_version_id = excluded.active_workspace_version_id,
                    title = excluded.title,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    session.id,
                    session.organization_id,
                    session.workspace_id,
                    session.created_by_user_id,
                    session.status,
                    session.active_workspace_version_id,
                    session.title,
                ),
            )
        return session

    def get(self, session_id: str) -> DialogueSession | None:
        with self._connection_factory() as connection:
            row = connection.execute(
                """
                SELECT id, organization_id, workspace_id, created_by_user_id, status,
                       active_workspace_version_id, title
                FROM dialogue_sessions
                WHERE id = ?
                """,
                (session_id,),
            ).fetchone()
        return None if row is None else DialogueSession(**dict(row))


class SqliteAuthSessionRepository(AuthSessionRepository):
    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def upsert(self, session: AuthSession) -> AuthSession:
        with self._connection_factory() as connection:
            connection.execute(
                """
                INSERT INTO auth_sessions (
                    id, user_id, organization_id, status, expires_at, last_seen_at, invalidated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    organization_id = excluded.organization_id,
                    status = excluded.status,
                    expires_at = excluded.expires_at,
                    last_seen_at = excluded.last_seen_at,
                    invalidated_at = excluded.invalidated_at,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    session.id,
                    session.user_id,
                    session.organization_id,
                    session.status,
                    session.expires_at,
                    session.last_seen_at,
                    session.invalidated_at,
                ),
            )
        return session

    def get(self, session_id: str) -> AuthSession | None:
        with self._connection_factory() as connection:
            row = connection.execute(
                """
                SELECT id, user_id, organization_id, status, expires_at, last_seen_at, invalidated_at
                FROM auth_sessions
                WHERE id = ?
                """,
                (session_id,),
            ).fetchone()
        return None if row is None else AuthSession(**dict(row))


class SqliteGovernanceEventRepository(GovernanceEventRepository):
    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def append(self, event: GovernanceEvent) -> None:
        with self._connection_factory() as connection:
            connection.execute(
                """
                INSERT INTO governance_events (
                    id, organization_id, workspace_id, event_type, payload_json, actor_type, actor_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    event_type = excluded.event_type,
                    payload_json = excluded.payload_json,
                    actor_type = excluded.actor_type,
                    actor_id = excluded.actor_id
                """,
                (
                    event.id,
                    event.organization_id,
                    event.workspace_id,
                    event.event_type,
                    _dumps(event.payload),
                    event.actor_type,
                    event.actor_id,
                ),
            )

    def list_for_workspace(self, workspace_id: str) -> list[GovernanceEvent]:
        with self._connection_factory() as connection:
            rows = connection.execute(
                """
                SELECT id, organization_id, workspace_id, event_type, payload_json, actor_type, actor_id
                FROM governance_events
                WHERE workspace_id = ?
                ORDER BY created_at, id
                """,
                (workspace_id,),
            ).fetchall()
        events = []
        for row in rows:
            payload = dict(row)
            payload["payload"] = _loads(payload.pop("payload_json"))
            events.append(GovernanceEvent(**payload))
        return events


class SqliteProjectionSnapshotRepository(ProjectionSnapshotRepository):
    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def upsert_many(self, snapshots: Sequence[ProjectionSnapshot]) -> None:
        with self._connection_factory() as connection:
            connection.executemany(
                """
                INSERT INTO projection_snapshots (
                    id, organization_id, workspace_id, workspace_version_id, projection_type,
                    freshness_status, source_claim_version_ids_json, payload_json, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    workspace_version_id = excluded.workspace_version_id,
                    freshness_status = excluded.freshness_status,
                    source_claim_version_ids_json = excluded.source_claim_version_ids_json,
                    payload_json = excluded.payload_json,
                    metadata_json = excluded.metadata_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                [
                    (
                        snapshot.id,
                        snapshot.organization_id,
                        snapshot.workspace_id,
                        snapshot.workspace_version_id,
                        snapshot.projection_type,
                        snapshot.freshness_status,
                        json.dumps(snapshot.source_claim_version_ids, ensure_ascii=False, sort_keys=True),
                        _dumps(snapshot.payload),
                        _dumps(snapshot.metadata),
                    )
                    for snapshot in snapshots
                ],
            )

    def list_for_workspace(self, workspace_id: str) -> list[ProjectionSnapshot]:
        with self._connection_factory() as connection:
            rows = connection.execute(
                """
                SELECT id, organization_id, workspace_id, workspace_version_id, projection_type,
                       freshness_status, source_claim_version_ids_json, payload_json, metadata_json
                FROM projection_snapshots
                WHERE workspace_id = ?
                ORDER BY projection_type
                """,
                (workspace_id,),
            ).fetchall()
        snapshots = []
        for row in rows:
            payload = dict(row)
            payload["source_claim_version_ids"] = json.loads(payload.pop("source_claim_version_ids_json") or "[]")
            payload["payload"] = _loads(payload.pop("payload_json"))
            payload["metadata"] = _loads(payload.pop("metadata_json"))
            snapshots.append(ProjectionSnapshot(**payload))
        return snapshots

    def mark_stale(self, workspace_id: str, projection_types: Sequence[str]) -> None:
        if not projection_types:
            return
        placeholders = ", ".join("?" for _ in projection_types)
        with self._connection_factory() as connection:
            connection.execute(
                f"""
                UPDATE projection_snapshots
                SET freshness_status = 'stale', updated_at = CURRENT_TIMESTAMP
                WHERE workspace_id = ? AND projection_type IN ({placeholders})
                """,
                [workspace_id, *projection_types],
            )


class SqliteMaterializedArtifactIndexRepository(MaterializedArtifactIndexRepository):
    def __init__(
        self,
        connection_factory: ConnectionFactory,
        transaction_manager: TransactionManager | None = None,
    ):
        self._connection_factory = connection_factory
        self._transactions = transaction_manager or TransactionManager(connection_factory)

    def replace_for_workspace(self, workspace_id: str, entries: Sequence[MaterializedArtifactIndexEntry]) -> None:
        with self._transactions.transaction() as connection:
            connection.execute(
                "DELETE FROM materialized_artifact_index_entries WHERE workspace_id = ?",
                (workspace_id,),
            )
            connection.executemany(
                """
                INSERT INTO materialized_artifact_index_entries (
                    id, organization_id, workspace_id, projection_type, stage_name, output_key, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        entry.id,
                        entry.organization_id,
                        entry.workspace_id,
                        entry.projection_type,
                        entry.stage_name,
                        entry.output_key,
                        _dumps(entry.metadata),
                    )
                    for entry in entries
                ],
            )

    def list_for_workspace(self, workspace_id: str) -> list[MaterializedArtifactIndexEntry]:
        with self._connection_factory() as connection:
            rows = connection.execute(
                """
                SELECT id, organization_id, workspace_id, projection_type, stage_name, output_key, metadata_json
                FROM materialized_artifact_index_entries
                WHERE workspace_id = ?
                ORDER BY projection_type, stage_name, output_key
                """,
                (workspace_id,),
            ).fetchall()
        entries = []
        for row in rows:
            payload = dict(row)
            payload["metadata"] = _loads(payload.pop("metadata_json"))
            entries.append(MaterializedArtifactIndexEntry(**payload))
        return entries
