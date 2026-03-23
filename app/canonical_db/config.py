from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse


DEFAULT_SQLITE_PATH = Path(".codex_data/canonical.db")


@dataclass(frozen=True)
class DatabaseConfig:
    dsn: str
    environment: str

    @classmethod
    def from_env(cls, environment: str | None = None) -> "DatabaseConfig":
        env_name = (environment or os.environ.get("APP_ENV") or "dev").lower()
        env_key = f"CANONICAL_DB_DSN_{env_name.upper()}"
        dsn = (
            os.environ.get(env_key)
            or os.environ.get("CANONICAL_DB_DSN")
            or os.environ.get("DATABASE_URL")
            or f"sqlite:///{DEFAULT_SQLITE_PATH}"
        )
        return cls(dsn=dsn, environment=env_name)


def connect(config: DatabaseConfig) -> sqlite3.Connection:
    parsed = urlparse(config.dsn)
    if parsed.scheme not in {"sqlite", ""}:
        raise ValueError(
            "This runtime only ships with sqlite support. "
            f"Configured DSN '{config.dsn}' should be used with PostgreSQL in deployment, "
            "but local/bootstrap tests must point to sqlite."
        )

    if parsed.scheme == "sqlite":
        db_path = parsed.path
        if db_path in {"", ":memory:"}:
            target = db_path or ":memory:"
        else:
            target = db_path.lstrip("/") if not db_path.startswith("//") else db_path[1:]
    else:
        target = config.dsn

    if target != ":memory:":
        Path(target).parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(target)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def connection_factory(environment: str | None = None) -> Callable[[], sqlite3.Connection]:
    config = DatabaseConfig.from_env(environment)

    def _factory() -> sqlite3.Connection:
        return connect(config)

    return _factory
