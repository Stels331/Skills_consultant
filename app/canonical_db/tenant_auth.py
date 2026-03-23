from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
from uuid import uuid4

from app.canonical_db.domain import (
    AuthSession,
    GovernanceEvent,
    Membership,
    Organization,
    User,
    UserProfile,
    Workspace,
)
from app.canonical_db.repositories import (
    AuthSessionRepository,
    GovernanceEventRepository,
    MembershipRepository,
    OrganizationRepository,
    UserProfileRepository,
    UserRepository,
    WorkspaceRepository,
)


ROLE_PERMISSIONS = {
    "organization_owner": {"membership_manage", "organization_manage", "workspace_view", "claim_edit"},
    "organization_admin": {"membership_manage", "workspace_view", "claim_edit"},
    "workspace_editor": {"workspace_view", "claim_edit"},
    "workspace_viewer": {"workspace_view"},
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class AuthService:
    def __init__(
        self,
        users: UserRepository,
        profiles: UserProfileRepository,
        sessions: AuthSessionRepository,
    ):
        self._users = users
        self._profiles = profiles
        self._sessions = sessions

    def register_user(self, *, email: str, password: str, display_name: str, user_id: str | None = None) -> User:
        user = User(
            id=user_id or f"user-{uuid4().hex[:12]}",
            email=email,
            password_hash=_hash_password(password),
            display_name=display_name,
            status="active",
        )
        self._users.upsert(user)
        self._profiles.upsert(UserProfile(user_id=user.id))
        return user

    def login(
        self,
        *,
        email: str,
        password: str,
        session_id: str | None = None,
        organization_id: str | None = None,
        session_ttl_hours: int = 8,
    ) -> AuthSession:
        user = self._users.get_by_email(email)
        if user is None or user.password_hash != _hash_password(password):
            raise PermissionError("Invalid credentials")
        if user.status != "active":
            raise PermissionError("User is not active")
        now = _utc_now()
        session = AuthSession(
            id=session_id or f"session-{uuid4().hex[:12]}",
            user_id=user.id,
            organization_id=organization_id,
            status="active",
            expires_at=_iso(now + timedelta(hours=session_ttl_hours)),
            last_seen_at=_iso(now),
            invalidated_at=None,
        )
        self._sessions.upsert(session)
        return session

    def logout(self, session_id: str) -> AuthSession:
        session = self.require_session(session_id)
        invalidated = replace(
            session,
            status="invalidated",
            invalidated_at=_iso(_utc_now()),
            last_seen_at=_iso(_utc_now()),
        )
        self._sessions.upsert(invalidated)
        return invalidated

    def require_session(self, session_id: str) -> AuthSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise PermissionError("Unknown session")
        if session.status != "active":
            raise PermissionError("Session is not active")
        if datetime.fromisoformat(session.expires_at) <= _utc_now():
            expired = replace(session, status="expired", last_seen_at=_iso(_utc_now()))
            self._sessions.upsert(expired)
            raise PermissionError("Session expired")
        return session


class OrganizationService:
    def __init__(
        self,
        organizations: OrganizationRepository,
        memberships: MembershipRepository,
        profiles: UserProfileRepository,
    ):
        self._organizations = organizations
        self._memberships = memberships
        self._profiles = profiles

    def create_organization(self, organization: Organization) -> Organization:
        self._organizations.upsert(organization)
        self._memberships.upsert(
            Membership(
                id=f"membership:{organization.id}:{organization.owner_user_id}",
                organization_id=organization.id,
                user_id=organization.owner_user_id,
                role="organization_owner",
                status="active",
                invited_by_user_id=organization.owner_user_id,
                joined_at=_iso(_utc_now()),
            )
        )
        profile = self._profiles.get(organization.owner_user_id) or UserProfile(user_id=organization.owner_user_id)
        if profile.active_organization_id is None:
            self._profiles.upsert(replace(profile, active_organization_id=organization.id))
        return organization

    def invite_member(
        self,
        *,
        organization_id: str,
        user_id: str,
        role: str,
        invited_by_user_id: str,
        membership_id: str | None = None,
    ) -> Membership:
        membership = Membership(
            id=membership_id or f"membership:{organization_id}:{user_id}",
            organization_id=organization_id,
            user_id=user_id,
            role=role,
            status="pending",
            invited_by_user_id=invited_by_user_id,
            joined_at=None,
        )
        return self._memberships.upsert(membership)

    def join_membership(self, *, organization_id: str, user_id: str) -> Membership:
        membership = self._memberships.get(organization_id, user_id)
        if membership is None:
            raise PermissionError("Membership invitation not found")
        joined = replace(membership, status="active", joined_at=_iso(_utc_now()))
        self._memberships.upsert(joined)
        profile = self._profiles.get(user_id) or UserProfile(user_id=user_id)
        if profile.active_organization_id is None:
            self._profiles.upsert(replace(profile, active_organization_id=organization_id))
        return joined

    def switch_active_organization(self, *, user_id: str, organization_id: str) -> UserProfile:
        membership = self._memberships.get(organization_id, user_id)
        if membership is None or membership.status != "active":
            raise PermissionError("User is not an active member of the organization")
        profile = self._profiles.get(user_id) or UserProfile(user_id=user_id)
        updated = replace(profile, active_organization_id=organization_id)
        self._profiles.upsert(updated)
        return updated


class TenantAuthorizationService:
    def __init__(
        self,
        memberships: MembershipRepository,
        workspaces: WorkspaceRepository,
        governance: GovernanceEventRepository,
    ):
        self._memberships = memberships
        self._workspaces = workspaces
        self._governance = governance

    def require_workspace_access(
        self,
        *,
        user_id: str,
        organization_id: str,
        workspace_id: str,
        permission: str,
    ) -> Workspace:
        membership = self._memberships.get(organization_id, user_id)
        if membership is None or membership.status != "active":
            self._log_security_event(
                organization_id=organization_id,
                workspace_id=workspace_id,
                user_id=user_id,
                reason="missing_membership",
                permission=permission,
            )
            raise PermissionError("Membership is required")
        allowed = ROLE_PERMISSIONS.get(membership.role, set())
        if permission not in allowed:
            self._log_security_event(
                organization_id=organization_id,
                workspace_id=workspace_id,
                user_id=user_id,
                reason="role_forbidden",
                permission=permission,
            )
            raise PermissionError("Role does not allow this action")
        workspace = self._workspaces.get(workspace_id)
        if workspace is None or workspace.organization_id != organization_id:
            self._log_security_event(
                organization_id=organization_id,
                workspace_id=workspace_id,
                user_id=user_id,
                reason="cross_tenant_access",
                permission=permission,
            )
            raise PermissionError("Workspace is outside active tenant")
        return workspace

    def _log_security_event(
        self,
        *,
        organization_id: str,
        workspace_id: str,
        user_id: str,
        reason: str,
        permission: str,
    ) -> None:
        self._governance.append(
            GovernanceEvent(
                id=f"security:{organization_id}:{workspace_id}:{user_id}:{reason}:{uuid4().hex[:8]}",
                organization_id=organization_id,
                workspace_id=workspace_id,
                event_type="security_unauthorized_access",
                payload={"reason": reason, "permission": permission},
                actor_type="user",
                actor_id=user_id,
            )
        )
