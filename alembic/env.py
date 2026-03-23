from __future__ import annotations

"""Lightweight placeholder env for Alembic-compatible repo layout.

This repository executes migrations through `app.canonical_db.migration_runner`
because the runtime environment for the sprint does not ship the Alembic
package. The revision files still follow the familiar Alembic structure.
"""
