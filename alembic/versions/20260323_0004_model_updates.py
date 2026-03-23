from __future__ import annotations


revision = "20260323_0004"
down_revision = "20260322_0003"
branch_labels = None
depends_on = None


def upgrade(connection):
    connection.executescript(
        """
        ALTER TABLE question_queue ADD COLUMN reason_code TEXT NOT NULL DEFAULT '';
        ALTER TABLE question_queue ADD COLUMN influence_area TEXT NOT NULL DEFAULT '';
        ALTER TABLE question_queue ADD COLUMN impact_preview TEXT NOT NULL DEFAULT '';
        ALTER TABLE question_queue ADD COLUMN rationale TEXT NOT NULL DEFAULT '';
        ALTER TABLE question_queue ADD COLUMN classifier_confidence REAL NOT NULL DEFAULT 0.0;
        """
    )


def downgrade(connection):
    return None
