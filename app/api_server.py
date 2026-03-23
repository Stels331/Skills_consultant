from __future__ import annotations

import json
import os
from pathlib import Path
from wsgiref.simple_server import make_server

from app.canonical_db.config import DatabaseConfig, connect
from app.canonical_db.migration_runner import current_revision, upgrade
from app.canonical_db.runtime import repository_bundle
from app.dialogue_api import DialogueApiService, maybe_handle_api_request
from app.observability.runtime_monitor import RUNTIME_MONITOR
from app.worker_service import WorkerRuntimeService


def _json(start_response, status: str, payload: dict) -> list[bytes]:
    start_response(status, [("Content-Type", "application/json")])
    return [json.dumps(payload, ensure_ascii=False).encode("utf-8")]


def _readiness_payload(project_root: Path) -> tuple[str, dict]:
    config = DatabaseConfig.from_env()
    dependencies = {
        "database": "unknown",
        "worker_queue": "unknown",
        "providers": "unknown",
    }
    ready = True
    revision = None
    try:
        connection = connect(config)
        try:
            revision = current_revision(connection)
            dependencies["database"] = "ready"
        finally:
            connection.close()
    except Exception as exc:
        ready = False
        dependencies["database"] = f"error:{exc}"

    try:
        bundle = repository_bundle()
        with bundle["factory"]() as connection:
            connection.execute("SELECT 1 FROM reentry_jobs LIMIT 1").fetchall()
        dependencies["worker_queue"] = "ready"
    except Exception as exc:
        ready = False
        dependencies["worker_queue"] = f"error:{exc}"

    try:
        diagnostics = DialogueApiService(project_root).provider_diagnostics()
        dependencies["providers"] = "ready" if diagnostics.get("direct_provider") == "configured" else "degraded"
    except Exception as exc:
        ready = False
        dependencies["providers"] = f"error:{exc}"
        diagnostics = {"active_mode": "unknown"}

    payload = {
        "status": "ready" if ready else "not_ready",
        "revision": revision,
        "dependencies": dependencies,
        "provider_diagnostics": diagnostics,
    }
    return ("200 OK" if ready else "503 Service Unavailable"), payload


def application(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    project_root = Path(__file__).resolve().parents[1]
    delegated = maybe_handle_api_request(project_root, environ, start_response)
    if delegated is not None:
        return delegated
    if path == "/metrics":
        return _json(start_response, "200 OK", RUNTIME_MONITOR.snapshot())
    if path == "/worker/health":
        return _json(start_response, "200 OK", WorkerRuntimeService(project_root).health())
    if path == "/worker/readiness":
        return _json(start_response, "200 OK", WorkerRuntimeService(project_root).readiness())
    if path == "/readiness":
        status, payload = _readiness_payload(project_root)
        return _json(start_response, status, payload)
    if path != "/health":
        return _json(start_response, "404 Not Found", {"status": "not_found"})

    config = DatabaseConfig.from_env()
    connection = connect(config)
    try:
        payload = {
            "status": "alive",
            "database": "reachable",
            "revision": current_revision(connection),
        }
        return _json(start_response, "200 OK", payload)
    finally:
        connection.close()


def main() -> int:
    config = DatabaseConfig.from_env()
    if os.environ.get("CANONICAL_DB_AUTO_UPGRADE", "1") == "1":
        connection = connect(config)
        try:
            upgrade(connection, target="head")
        finally:
            connection.close()

    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8000"))
    with make_server(host, port, application) as server:
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
