from __future__ import annotations


revision = "20260322_0002"
down_revision = "20260322_0001"
branch_labels = None
depends_on = None


SESSION_STATUS_CHECK = "status IN ('active', 'expired', 'invalidated')"
FRESHNESS_CHECK = "freshness_status IN ('fresh', 'stale')"


def upgrade(connection):
    connection.executescript(
        f"""
        CREATE TABLE user_profiles (
            user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            active_organization_id TEXT REFERENCES organizations(id) ON DELETE SET NULL,
            settings_json TEXT NOT NULL DEFAULT '{{}}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE auth_sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            organization_id TEXT REFERENCES organizations(id) ON DELETE SET NULL,
            status TEXT NOT NULL CHECK ({SESSION_STATUS_CHECK}),
            expires_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            invalidated_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX ix_auth_sessions_user_id ON auth_sessions(user_id);
        CREATE INDEX ix_auth_sessions_status ON auth_sessions(status);

        CREATE TABLE projection_snapshots (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            workspace_version_id TEXT NOT NULL REFERENCES workspace_versions(id) ON DELETE CASCADE,
            projection_type TEXT NOT NULL,
            freshness_status TEXT NOT NULL CHECK ({FRESHNESS_CHECK}),
            source_claim_version_ids_json TEXT NOT NULL DEFAULT '[]',
            payload_json TEXT NOT NULL DEFAULT '{{}}',
            metadata_json TEXT NOT NULL DEFAULT '{{}}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (workspace_id, projection_type)
        );
        CREATE INDEX ix_projection_snapshots_workspace_id ON projection_snapshots(workspace_id);
        CREATE INDEX ix_projection_snapshots_freshness ON projection_snapshots(freshness_status);

        CREATE TABLE materialized_artifact_index_entries (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            projection_type TEXT NOT NULL,
            stage_name TEXT NOT NULL,
            output_key TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{{}}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (workspace_id, projection_type, stage_name, output_key)
        );
        CREATE INDEX ix_materialized_artifact_index_workspace_id ON materialized_artifact_index_entries(workspace_id);
        CREATE INDEX ix_materialized_artifact_index_projection_type ON materialized_artifact_index_entries(projection_type);
        """
    )


def downgrade(connection):
    connection.executescript(
        """
        DROP TABLE IF EXISTS materialized_artifact_index_entries;
        DROP TABLE IF EXISTS projection_snapshots;
        DROP TABLE IF EXISTS auth_sessions;
        DROP TABLE IF EXISTS user_profiles;
        """
    )
