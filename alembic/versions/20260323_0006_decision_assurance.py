from __future__ import annotations


revision = "20260323_0006"
down_revision = "20260323_0005"
branch_labels = None
depends_on = None


def upgrade(connection):
    connection.executescript(
        """
        ALTER TABLE decision_evidence_links ADD COLUMN valid_until TEXT;
        ALTER TABLE decision_evidence_links ADD COLUMN freshness_mode TEXT NOT NULL DEFAULT 'none';

        CREATE TABLE decision_assurance_snapshots (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            workspace_version_id TEXT NOT NULL REFERENCES workspace_versions(id) ON DELETE CASCADE,
            decision_record_id TEXT NOT NULL REFERENCES decision_records(id) ON DELETE CASCADE,
            assurance_score REAL NOT NULL,
            assurance_status TEXT NOT NULL,
            weakest_link_ref TEXT NOT NULL DEFAULT '',
            decay_penalty REAL NOT NULL DEFAULT 0.0,
            review_required INTEGER NOT NULL DEFAULT 0,
            staleness_flags_json TEXT NOT NULL DEFAULT '[]',
            waiver_active INTEGER NOT NULL DEFAULT 0,
            historical_outcome_modifier REAL NOT NULL DEFAULT 0.0,
            breakdown_json TEXT NOT NULL DEFAULT '{}',
            invalidated INTEGER NOT NULL DEFAULT 0,
            recompute_scope TEXT NOT NULL DEFAULT 'full',
            policy_class TEXT NOT NULL DEFAULT 'standard',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (decision_record_id)
        );
        CREATE INDEX ix_decision_assurance_snapshots_workspace_id ON decision_assurance_snapshots(workspace_id);
        CREATE INDEX ix_decision_assurance_snapshots_record_id ON decision_assurance_snapshots(decision_record_id);
        CREATE INDEX ix_decision_assurance_snapshots_status ON decision_assurance_snapshots(assurance_status);

        CREATE TABLE decision_waivers (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            workspace_version_id TEXT NOT NULL REFERENCES workspace_versions(id) ON DELETE CASCADE,
            decision_record_id TEXT NOT NULL REFERENCES decision_records(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'active',
            scope TEXT NOT NULL,
            justification TEXT NOT NULL,
            residual_risk TEXT NOT NULL,
            renewal_policy TEXT NOT NULL DEFAULT 'auto-expire-notify',
            expires_at TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX ix_decision_waivers_workspace_id ON decision_waivers(workspace_id);
        CREATE INDEX ix_decision_waivers_record_id ON decision_waivers(decision_record_id);
        CREATE INDEX ix_decision_waivers_status ON decision_waivers(status);
        """
    )


def downgrade(connection):
    return None
