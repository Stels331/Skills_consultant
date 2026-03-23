from __future__ import annotations

import importlib.util
from pathlib import Path
import sqlite3


VERSIONS_DIR = Path(__file__).resolve().parents[2] / "alembic" / "versions"


def _load_revision(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load revision from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def available_revisions() -> list[object]:
    revisions = []
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        if path.name.startswith("__"):
            continue
        revisions.append(_load_revision(path))
    return revisions


def ensure_version_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS alembic_version (
            version_num TEXT PRIMARY KEY
        )
        """
    )


def current_revision(connection: sqlite3.Connection) -> str | None:
    ensure_version_table(connection)
    row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    return None if row is None else row[0]


def stamp_revision(connection: sqlite3.Connection, revision: str | None) -> None:
    ensure_version_table(connection)
    connection.execute("DELETE FROM alembic_version")
    if revision is not None:
        connection.execute("INSERT INTO alembic_version(version_num) VALUES (?)", (revision,))


def upgrade(connection: sqlite3.Connection, target: str = "head") -> str | None:
    revisions = available_revisions()
    current = current_revision(connection)
    applied = current
    for revision in revisions:
        if current == revision.revision:
            continue
        if current is not None and revision.down_revision != current:
            continue
        revision.upgrade(connection)
        applied = revision.revision
        stamp_revision(connection, applied)
        current = applied
        if target != "head" and target == applied:
            break
    connection.commit()
    return applied


def downgrade(connection: sqlite3.Connection, steps: int = 1) -> str | None:
    revisions = {revision.revision: revision for revision in available_revisions()}
    current = current_revision(connection)
    for _ in range(steps):
        if current is None:
            break
        revision = revisions[current]
        revision.downgrade(connection)
        current = revision.down_revision
        stamp_revision(connection, current)
    connection.commit()
    return current
