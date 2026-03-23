from __future__ import annotations


revision = "20260323_0005"
down_revision = "20260323_0004"
branch_labels = None
depends_on = None


QUESTION_CLASS_CHECK = (
    "question_class IN ('constraint_query', 'problem_query', 'solution_query', "
    "'decision_query', 'report_query', 'evidence_query', "
    "'clarification_needed', 'clarification_provided')"
)


def upgrade(connection):
    connection.executescript(
        f"""
        CREATE TABLE problem_frames (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            workspace_version_id TEXT NOT NULL REFERENCES workspace_versions(id) ON DELETE CASCADE,
            root_problem TEXT NOT NULL,
            scope_boundary TEXT NOT NULL,
            success_criteria_json TEXT NOT NULL DEFAULT '[]',
            active_constraints_json TEXT NOT NULL DEFAULT '[]',
            unresolved_unknowns_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'active',
            invalidation_reason TEXT NOT NULL DEFAULT '',
            correlation_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX ix_problem_frames_workspace_id ON problem_frames(workspace_id);
        CREATE INDEX ix_problem_frames_workspace_version_id ON problem_frames(workspace_version_id);
        CREATE INDEX ix_problem_frames_status ON problem_frames(status);

        CREATE TABLE decision_options (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            workspace_version_id TEXT NOT NULL REFERENCES workspace_versions(id) ON DELETE CASCADE,
            problem_frame_id TEXT NOT NULL REFERENCES problem_frames(id) ON DELETE CASCADE,
            option_key TEXT NOT NULL,
            title TEXT NOT NULL,
            summary_text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'candidate',
            assumptions_json TEXT NOT NULL DEFAULT '[]',
            confidence_in_assumptions REAL NOT NULL DEFAULT 0.0,
            benefits_json TEXT NOT NULL DEFAULT '[]',
            costs_json TEXT NOT NULL DEFAULT '[]',
            risks_json TEXT NOT NULL DEFAULT '[]',
            prerequisites_json TEXT NOT NULL DEFAULT '[]',
            historical_value_score REAL NOT NULL DEFAULT 0.0,
            reuse_success_score REAL NOT NULL DEFAULT 0.0,
            negative_outcome_count INTEGER NOT NULL DEFAULT 0,
            metadata_json TEXT NOT NULL DEFAULT '{{}}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (workspace_version_id, problem_frame_id, option_key)
        );
        CREATE INDEX ix_decision_options_workspace_id ON decision_options(workspace_id);
        CREATE INDEX ix_decision_options_problem_frame_id ON decision_options(problem_frame_id);
        CREATE INDEX ix_decision_options_status ON decision_options(status);

        CREATE TABLE decision_comparisons (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            workspace_version_id TEXT NOT NULL REFERENCES workspace_versions(id) ON DELETE CASCADE,
            problem_frame_id TEXT NOT NULL REFERENCES problem_frames(id) ON DELETE CASCADE,
            selected_option_id TEXT REFERENCES decision_options(id) ON DELETE SET NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            comparison_dimensions_json TEXT NOT NULL DEFAULT '[]',
            option_scores_json TEXT NOT NULL DEFAULT '{{}}',
            rejected_option_ids_json TEXT NOT NULL DEFAULT '[]',
            tradeoffs_json TEXT NOT NULL DEFAULT '[]',
            blockers_json TEXT NOT NULL DEFAULT '[]',
            rationale_notes_json TEXT NOT NULL DEFAULT '[]',
            correlation_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX ix_decision_comparisons_workspace_id ON decision_comparisons(workspace_id);
        CREATE INDEX ix_decision_comparisons_problem_frame_id ON decision_comparisons(problem_frame_id);

        CREATE TABLE decision_drafts (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            workspace_version_id TEXT NOT NULL REFERENCES workspace_versions(id) ON DELETE CASCADE,
            problem_frame_id TEXT NOT NULL REFERENCES problem_frames(id) ON DELETE CASCADE,
            comparison_id TEXT NOT NULL REFERENCES decision_comparisons(id) ON DELETE CASCADE,
            selected_option_id TEXT REFERENCES decision_options(id) ON DELETE SET NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            missing_basis_json TEXT NOT NULL DEFAULT '[]',
            uncertainty_markers_json TEXT NOT NULL DEFAULT '[]',
            rationale_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX ix_decision_drafts_workspace_id ON decision_drafts(workspace_id);

        CREATE TABLE decision_records (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            workspace_version_id TEXT NOT NULL REFERENCES workspace_versions(id) ON DELETE CASCADE,
            problem_frame_id TEXT NOT NULL REFERENCES problem_frames(id) ON DELETE CASCADE,
            comparison_id TEXT NOT NULL REFERENCES decision_comparisons(id) ON DELETE CASCADE,
            draft_id TEXT REFERENCES decision_drafts(id) ON DELETE SET NULL,
            selected_option_id TEXT NOT NULL REFERENCES decision_options(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'selected',
            decision_basis_json TEXT NOT NULL DEFAULT '[]',
            rejected_option_ids_json TEXT NOT NULL DEFAULT '[]',
            review_due TEXT,
            limitations_json TEXT NOT NULL DEFAULT '[]',
            historical_value_score REAL NOT NULL DEFAULT 0.0,
            last_outcome_status TEXT NOT NULL DEFAULT '',
            last_outcome_at TEXT,
            missing_basis_json TEXT NOT NULL DEFAULT '[]',
            uncertainty_markers_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX ix_decision_records_workspace_id ON decision_records(workspace_id);
        CREATE INDEX ix_decision_records_selected_option_id ON decision_records(selected_option_id);
        CREATE INDEX ix_decision_records_status ON decision_records(status);

        CREATE TABLE decision_evidence_links (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            workspace_version_id TEXT NOT NULL REFERENCES workspace_versions(id) ON DELETE CASCADE,
            decision_record_id TEXT REFERENCES decision_records(id) ON DELETE CASCADE,
            decision_option_id TEXT REFERENCES decision_options(id) ON DELETE CASCADE,
            link_type TEXT NOT NULL,
            link_strength REAL NOT NULL,
            link_direction TEXT NOT NULL,
            source_ref TEXT NOT NULL,
            criticality TEXT NOT NULL DEFAULT 'standard',
            claim_id TEXT REFERENCES claims(id) ON DELETE SET NULL,
            artifact_id TEXT REFERENCES artifacts(id) ON DELETE SET NULL,
            projection_snapshot_id TEXT REFERENCES projection_snapshots(id) ON DELETE SET NULL,
            metadata_json TEXT NOT NULL DEFAULT '{{}}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX ix_decision_evidence_links_workspace_id ON decision_evidence_links(workspace_id);
        CREATE INDEX ix_decision_evidence_links_record_id ON decision_evidence_links(decision_record_id);

        CREATE TABLE decision_reviews (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            workspace_version_id TEXT NOT NULL REFERENCES workspace_versions(id) ON DELETE CASCADE,
            decision_record_id TEXT NOT NULL REFERENCES decision_records(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'open',
            opened_by TEXT NOT NULL,
            closed_by TEXT,
            close_reason TEXT NOT NULL DEFAULT '',
            notes_json TEXT NOT NULL DEFAULT '[]',
            correlation_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX ix_decision_reviews_workspace_id ON decision_reviews(workspace_id);
        CREATE INDEX ix_decision_reviews_record_id ON decision_reviews(decision_record_id);
        CREATE INDEX ix_decision_reviews_status ON decision_reviews(status);

        CREATE TABLE decision_outcomes (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            workspace_version_id TEXT NOT NULL REFERENCES workspace_versions(id) ON DELETE CASCADE,
            decision_record_id TEXT NOT NULL REFERENCES decision_records(id) ON DELETE CASCADE,
            outcome_type TEXT NOT NULL,
            outcome_score REAL NOT NULL,
            source TEXT NOT NULL,
            evidence_json TEXT NOT NULL DEFAULT '{{}}',
            recorded_at TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX ix_decision_outcomes_workspace_id ON decision_outcomes(workspace_id);
        CREATE INDEX ix_decision_outcomes_record_id ON decision_outcomes(decision_record_id);

        DROP INDEX IF EXISTS ix_dialogue_messages_organization_id;
        DROP INDEX IF EXISTS ix_dialogue_messages_workspace_id;
        DROP INDEX IF EXISTS ix_dialogue_messages_session_id;
        DROP INDEX IF EXISTS ix_dialogue_messages_created_at;
        ALTER TABLE dialogue_messages RENAME TO dialogue_messages_legacy_0005;
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
        INSERT INTO dialogue_messages (
            id, organization_id, workspace_id, session_id, workspace_version_id, actor_type,
            actor_user_id, question_class, message_type, content_text, grounding_bundle_ref,
            validator_result, graph_version, created_at
        )
        SELECT
            id, organization_id, workspace_id, session_id, workspace_version_id, actor_type,
            actor_user_id, question_class, message_type, content_text, grounding_bundle_ref,
            validator_result, graph_version, created_at
        FROM dialogue_messages_legacy_0005;
        DROP TABLE dialogue_messages_legacy_0005;

        DROP INDEX IF EXISTS ix_question_queue_workspace_id;
        DROP INDEX IF EXISTS ix_question_queue_status;
        DROP INDEX IF EXISTS ix_question_queue_created_at;
        ALTER TABLE question_queue RENAME TO question_queue_legacy_0005;
        CREATE TABLE question_queue (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            session_id TEXT REFERENCES dialogue_sessions(id) ON DELETE SET NULL,
            question_class TEXT NOT NULL CHECK ({QUESTION_CLASS_CHECK}),
            status TEXT NOT NULL,
            question_text TEXT NOT NULL,
            priority INTEGER NOT NULL DEFAULT 100,
            reason_code TEXT NOT NULL DEFAULT '',
            influence_area TEXT NOT NULL DEFAULT '',
            impact_preview TEXT NOT NULL DEFAULT '',
            rationale TEXT NOT NULL DEFAULT '',
            classifier_confidence REAL NOT NULL DEFAULT 0.0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX ix_question_queue_workspace_id ON question_queue(workspace_id);
        CREATE INDEX ix_question_queue_status ON question_queue(status);
        CREATE INDEX ix_question_queue_created_at ON question_queue(created_at);
        INSERT INTO question_queue (
            id, organization_id, workspace_id, session_id, question_class, status,
            question_text, priority, reason_code, influence_area, impact_preview, rationale,
            classifier_confidence, created_at
        )
        SELECT
            id, organization_id, workspace_id, session_id, question_class, status,
            question_text, priority, reason_code, influence_area, impact_preview, rationale,
            classifier_confidence, created_at
        FROM question_queue_legacy_0005;
        DROP TABLE question_queue_legacy_0005;
        """
    )


def downgrade(connection):
    return None
