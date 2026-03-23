from __future__ import annotations


revision = "20260322_0003"
down_revision = "20260322_0002"
branch_labels = None
depends_on = None


FRESHNESS_CHECK = "freshness_status IN ('fresh', 'stale')"


def upgrade(connection):
    connection.executescript(
        f"""
        ALTER TABLE retrieval_chunks ADD COLUMN retrieval_revision INTEGER NOT NULL DEFAULT 1;
        ALTER TABLE retrieval_chunks ADD COLUMN source_revision TEXT NOT NULL DEFAULT '';
        ALTER TABLE retrieval_chunks ADD COLUMN freshness_status TEXT NOT NULL DEFAULT 'fresh' CHECK ({FRESHNESS_CHECK});
        ALTER TABLE retrieval_chunks ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1;

        ALTER TABLE embedding_jobs ADD COLUMN source_revision TEXT NOT NULL DEFAULT '';
        ALTER TABLE embedding_jobs ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE embedding_jobs ADD COLUMN last_error TEXT NOT NULL DEFAULT '';
        """
    )


def downgrade(connection):
    # SQLite downgrade is intentionally non-destructive for additive Sprint 3 columns.
    return None
