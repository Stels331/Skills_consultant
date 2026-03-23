from __future__ import annotations


revision = "20260322_0001"
down_revision = None
branch_labels = None
depends_on = None


STATUS_CHECK = "status IN ('active', 'inactive', 'pending', 'archived', 'failed', 'queued', 'completed', 'running')"
QUESTION_CLASS_CHECK = (
    "question_class IN ('constraint_query', 'problem_query', 'solution_query', "
    "'report_query', 'evidence_query', 'clarification_needed', 'clarification_provided')"
)


def upgrade(connection):
    connection.executescript(
        f"""
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active' CHECK ({STATUS_CHECK}),
            email_verified_at TEXT,
            last_login_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE organizations (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            owner_user_id TEXT NOT NULL REFERENCES users(id),
            status TEXT NOT NULL DEFAULT 'active' CHECK ({STATUS_CHECK}),
            metadata_json TEXT NOT NULL DEFAULT '{{}}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX ix_organizations_created_at ON organizations(created_at);
        CREATE INDEX ix_organizations_status ON organizations(status);

        CREATE TABLE memberships (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active' CHECK ({STATUS_CHECK}),
            invited_by_user_id TEXT REFERENCES users(id),
            joined_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (organization_id, user_id)
        );
        CREATE INDEX ix_memberships_organization_id ON memberships(organization_id);
        CREATE INDEX ix_memberships_created_at ON memberships(created_at);

        CREATE TABLE workspaces (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_key TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            case_type TEXT NOT NULL,
            status TEXT NOT NULL CHECK ({STATUS_CHECK}),
            current_stage TEXT NOT NULL,
            active_model_version INTEGER NOT NULL DEFAULT 0,
            reentry_status TEXT NOT NULL DEFAULT 'idle',
            reentry_started_at TEXT,
            created_by_user_id TEXT NOT NULL REFERENCES users(id),
            metadata_json TEXT NOT NULL DEFAULT '{{}}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX ix_workspaces_organization_id ON workspaces(organization_id);
        CREATE INDEX ix_workspaces_status ON workspaces(status);
        CREATE INDEX ix_workspaces_created_at ON workspaces(created_at);

        CREATE TABLE workspace_versions (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            version_no INTEGER NOT NULL,
            version_label TEXT NOT NULL,
            change_reason TEXT NOT NULL,
            created_by TEXT NOT NULL REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (workspace_id, version_no)
        );
        CREATE INDEX ix_workspace_versions_workspace_id ON workspace_versions(workspace_id);
        CREATE INDEX ix_workspace_versions_created_at ON workspace_versions(created_at);

        CREATE TABLE artifacts (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            workspace_version_id TEXT NOT NULL REFERENCES workspace_versions(id) ON DELETE CASCADE,
            artifact_type TEXT NOT NULL,
            stage_name TEXT NOT NULL,
            artifact_key TEXT NOT NULL,
            status TEXT NOT NULL CHECK ({STATUS_CHECK}),
            format TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{{}}',
            parse_metadata_json TEXT NOT NULL DEFAULT '{{}}',
            artifact_trust_level TEXT NOT NULL DEFAULT 'trusted',
            summary_text TEXT NOT NULL DEFAULT '',
            file_path TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (workspace_id, artifact_key)
        );
        CREATE INDEX ix_artifacts_workspace_id ON artifacts(workspace_id);
        CREATE INDEX ix_artifacts_status ON artifacts(status);
        CREATE INDEX ix_artifacts_created_at ON artifacts(created_at);

        CREATE TABLE claims (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            workspace_version_id TEXT NOT NULL REFERENCES workspace_versions(id) ON DELETE CASCADE,
            claim_key TEXT NOT NULL,
            claim_type TEXT NOT NULL,
            statement TEXT NOT NULL,
            epistemic_status TEXT NOT NULL,
            confidence_score REAL NOT NULL CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
            source_kind TEXT NOT NULL,
            source_ref TEXT NOT NULL,
            attributes_json TEXT NOT NULL DEFAULT '{{}}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (workspace_id, claim_key)
        );
        CREATE INDEX ix_claims_organization_id ON claims(organization_id);
        CREATE INDEX ix_claims_workspace_id ON claims(workspace_id);
        CREATE INDEX ix_claims_claim_type ON claims(claim_type);
        CREATE INDEX ix_claims_status ON claims(epistemic_status);
        CREATE INDEX ix_claims_created_at ON claims(created_at);

        CREATE TABLE claim_versions (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
            version_no INTEGER NOT NULL,
            claim_type TEXT NOT NULL,
            statement TEXT NOT NULL,
            epistemic_status TEXT NOT NULL,
            confidence_score REAL NOT NULL CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
            source_kind TEXT NOT NULL,
            source_ref TEXT NOT NULL,
            attributes_json TEXT NOT NULL DEFAULT '{{}}',
            change_reason TEXT NOT NULL,
            changed_by_actor TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (claim_id, version_no)
        );
        CREATE INDEX ix_claim_versions_workspace_id ON claim_versions(workspace_id);
        CREATE INDEX ix_claim_versions_created_at ON claim_versions(created_at);

        CREATE TABLE claim_relations (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            from_claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
            to_claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
            relation_type TEXT NOT NULL,
            weight REAL NOT NULL DEFAULT 1.0,
            metadata_json TEXT NOT NULL DEFAULT '{{}}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (from_claim_id, to_claim_id, relation_type)
        );
        CREATE INDEX ix_claim_relations_workspace_id ON claim_relations(workspace_id);
        CREATE INDEX ix_claim_relations_created_at ON claim_relations(created_at);

        CREATE TABLE dialogue_sessions (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            created_by_user_id TEXT NOT NULL REFERENCES users(id),
            status TEXT NOT NULL CHECK ({STATUS_CHECK}),
            active_workspace_version_id TEXT NOT NULL REFERENCES workspace_versions(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX ix_dialogue_sessions_organization_id ON dialogue_sessions(organization_id);
        CREATE INDEX ix_dialogue_sessions_workspace_id ON dialogue_sessions(workspace_id);
        CREATE INDEX ix_dialogue_sessions_status ON dialogue_sessions(status);
        CREATE INDEX ix_dialogue_sessions_created_at ON dialogue_sessions(created_at);

        CREATE TABLE dialogue_messages (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            session_id TEXT NOT NULL REFERENCES dialogue_sessions(id) ON DELETE CASCADE,
            workspace_version_id TEXT NOT NULL REFERENCES workspace_versions(id) ON DELETE CASCADE,
            actor_type TEXT NOT NULL,
            actor_user_id TEXT REFERENCES users(id),
            question_class TEXT NOT NULL CHECK ({QUESTION_CLASS_CHECK}),
            message_type TEXT NOT NULL,
            content_text TEXT NOT NULL,
            grounding_bundle_ref TEXT,
            validator_result TEXT,
            graph_version TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX ix_dialogue_messages_organization_id ON dialogue_messages(organization_id);
        CREATE INDEX ix_dialogue_messages_workspace_id ON dialogue_messages(workspace_id);
        CREATE INDEX ix_dialogue_messages_session_id ON dialogue_messages(session_id);
        CREATE INDEX ix_dialogue_messages_created_at ON dialogue_messages(created_at);

        CREATE TABLE question_queue (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            session_id TEXT REFERENCES dialogue_sessions(id) ON DELETE SET NULL,
            question_class TEXT NOT NULL CHECK ({QUESTION_CLASS_CHECK}),
            status TEXT NOT NULL CHECK ({STATUS_CHECK}),
            question_text TEXT NOT NULL,
            priority INTEGER NOT NULL DEFAULT 100,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX ix_question_queue_workspace_id ON question_queue(workspace_id);
        CREATE INDEX ix_question_queue_status ON question_queue(status);
        CREATE INDEX ix_question_queue_created_at ON question_queue(created_at);

        CREATE TABLE validation_runs (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            workspace_version_id TEXT REFERENCES workspace_versions(id) ON DELETE SET NULL,
            artifact_id TEXT REFERENCES artifacts(id) ON DELETE SET NULL,
            status TEXT NOT NULL CHECK ({STATUS_CHECK}),
            validator_name TEXT NOT NULL,
            result_json TEXT NOT NULL DEFAULT '{{}}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX ix_validation_runs_workspace_id ON validation_runs(workspace_id);
        CREATE INDEX ix_validation_runs_status ON validation_runs(status);
        CREATE INDEX ix_validation_runs_created_at ON validation_runs(created_at);

        CREATE TABLE governance_events (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            session_id TEXT REFERENCES dialogue_sessions(id) ON DELETE SET NULL,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{{}}',
            actor_type TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX ix_governance_events_organization_id ON governance_events(organization_id);
        CREATE INDEX ix_governance_events_workspace_id ON governance_events(workspace_id);
        CREATE INDEX ix_governance_events_created_at ON governance_events(created_at);

        CREATE TABLE retrieval_chunks (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            artifact_id TEXT REFERENCES artifacts(id) ON DELETE SET NULL,
            claim_id TEXT REFERENCES claims(id) ON DELETE SET NULL,
            chunk_key TEXT NOT NULL,
            chunk_text TEXT NOT NULL,
            section_title TEXT,
            status TEXT NOT NULL CHECK ({STATUS_CHECK}),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (workspace_id, chunk_key)
        );
        CREATE INDEX ix_retrieval_chunks_workspace_id ON retrieval_chunks(workspace_id);
        CREATE INDEX ix_retrieval_chunks_status ON retrieval_chunks(status);
        CREATE INDEX ix_retrieval_chunks_created_at ON retrieval_chunks(created_at);

        CREATE TABLE embedding_jobs (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            retrieval_chunk_id TEXT REFERENCES retrieval_chunks(id) ON DELETE CASCADE,
            status TEXT NOT NULL CHECK ({STATUS_CHECK}),
            provider TEXT NOT NULL,
            model_key TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX ix_embedding_jobs_workspace_id ON embedding_jobs(workspace_id);
        CREATE INDEX ix_embedding_jobs_status ON embedding_jobs(status);
        CREATE INDEX ix_embedding_jobs_created_at ON embedding_jobs(created_at);

        CREATE TABLE reentry_jobs (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            workspace_version_id TEXT REFERENCES workspace_versions(id) ON DELETE SET NULL,
            status TEXT NOT NULL CHECK ({STATUS_CHECK}),
            trigger_claim_id TEXT REFERENCES claims(id) ON DELETE SET NULL,
            dependent_projections_json TEXT NOT NULL DEFAULT '[]',
            affected_stages_json TEXT NOT NULL DEFAULT '[]',
            stale_outputs_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX ix_reentry_jobs_workspace_id ON reentry_jobs(workspace_id);
        CREATE INDEX ix_reentry_jobs_status ON reentry_jobs(status);
        CREATE INDEX ix_reentry_jobs_created_at ON reentry_jobs(created_at);

        CREATE TABLE quota_ledger (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT REFERENCES workspaces(id) ON DELETE SET NULL,
            user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            metric_key TEXT NOT NULL,
            delta REAL NOT NULL,
            unit TEXT NOT NULL,
            source_event TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX ix_quota_ledger_organization_id ON quota_ledger(organization_id);
        CREATE INDEX ix_quota_ledger_workspace_id ON quota_ledger(workspace_id);
        CREATE INDEX ix_quota_ledger_created_at ON quota_ledger(created_at);
        """
    )


def downgrade(connection):
    connection.executescript(
        """
        DROP TABLE IF EXISTS quota_ledger;
        DROP TABLE IF EXISTS reentry_jobs;
        DROP TABLE IF EXISTS embedding_jobs;
        DROP TABLE IF EXISTS retrieval_chunks;
        DROP TABLE IF EXISTS governance_events;
        DROP TABLE IF EXISTS validation_runs;
        DROP TABLE IF EXISTS question_queue;
        DROP TABLE IF EXISTS dialogue_messages;
        DROP TABLE IF EXISTS dialogue_sessions;
        DROP TABLE IF EXISTS claim_relations;
        DROP TABLE IF EXISTS claim_versions;
        DROP TABLE IF EXISTS claims;
        DROP TABLE IF EXISTS artifacts;
        DROP TABLE IF EXISTS workspace_versions;
        DROP TABLE IF EXISTS workspaces;
        DROP TABLE IF EXISTS memberships;
        DROP TABLE IF EXISTS organizations;
        DROP TABLE IF EXISTS users;
        """
    )
