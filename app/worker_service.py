from __future__ import annotations

from pathlib import Path

from app.canonical_db.model_updates import ReentryWorker
from app.canonical_db.projections import ProjectionRegistry, ProjectionService
from app.canonical_db.runtime import repository_bundle


class WorkerRuntimeService:
    def __init__(self, project_root: Path):
        self._project_root = project_root
        self._bundle = repository_bundle()
        self._projection_service = ProjectionService(
            self._bundle["claims"],
            self._bundle["projection_snapshots"],
            ProjectionRegistry(),
        )
        self._worker = ReentryWorker(
            self._bundle["reentry_jobs"],
            self._bundle["workspaces"],
            self._projection_service,
            self._bundle["governance"],
        )

    def health(self) -> dict[str, object]:
        return {"status": "alive", "service": "worker"}

    def readiness(self) -> dict[str, object]:
        queued = 0
        in_progress = 0
        with self._bundle["factory"]() as connection:
            rows = connection.execute("SELECT id FROM workspaces ORDER BY id").fetchall()
        for row in rows:
            for job in self._bundle["reentry_jobs"].list_for_workspace(row["id"]):
                if job.status == "queued":
                    queued += 1
                if job.status == "in_progress":
                    in_progress += 1
        return {
            "status": "ready",
            "service": "worker",
            "queue": {
                "queued_jobs": queued,
                "in_progress_jobs": in_progress,
            },
            "database": "reachable",
        }

    def run_next(self, *, workspace_id: str) -> dict[str, object] | None:
        jobs = self._bundle["reentry_jobs"].list_for_workspace(workspace_id)
        queued = next((job for job in jobs if job.status == "queued"), None)
        if queued is None:
            return None
        completed = self._worker.execute(queued.id)
        return {
            "job_id": completed.id,
            "workspace_id": completed.workspace_id,
            "status": completed.status,
        }
