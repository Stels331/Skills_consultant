from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


WORKSPACE_ID_PATTERN = re.compile(r"^case_(\d{8})_(\d{3})$")
ALLOWED_STATES = {"CREATE", "ACTIVE", "SUSPENDED", "ARCHIVED"}
ALLOWED_TRANSITIONS = {
    "CREATE": {"ACTIVE", "SUSPENDED", "ARCHIVED"},
    "ACTIVE": {"SUSPENDED", "ARCHIVED"},
    "SUSPENDED": {"ACTIVE", "ARCHIVED"},
    "ARCHIVED": set(),
}

REQUIRED_DIRS = [
    "raw",
    "parsed",
    "extracted",
    "model",
    "analysis",
    "dialogue",
    "evidence",
    "quality",
    "reports",
    "state",
    "versions",
]

REQUIRED_FILES = [
    "workspace_metadata.json",
    "state/session_state.json",
    "state/version_changelog.json",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def today_yyyymmdd() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(path)


def _append_changelog(workspace_root: Path, event: Dict[str, Any]) -> None:
    changelog_path = workspace_root / "state" / "version_changelog.json"
    data = _read_json(changelog_path)
    events = data.setdefault("events", [])
    events.append(event)
    data["updated_at"] = utc_now_iso()
    _write_json(changelog_path, data)


@dataclass(frozen=True)
class WorkspaceRef:
    workspace_id: str
    path: Path


class WorkspaceManager:
    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.cases_root = self.project_root / "cases"
        self.cases_root.mkdir(parents=True, exist_ok=True)

    def _validate_workspace_id(self, workspace_id: str) -> None:
        if not WORKSPACE_ID_PATTERN.match(workspace_id):
            raise ValueError(
                "workspace_id must match case_YYYYMMDD_NNN, "
                f"got: {workspace_id!r}"
            )

    def generate_workspace_id(self, date_yyyymmdd: Optional[str] = None) -> str:
        date_part = date_yyyymmdd or today_yyyymmdd()
        max_seq = 0
        for child in self.cases_root.iterdir():
            if not child.is_dir():
                continue
            m = WORKSPACE_ID_PATTERN.match(child.name)
            if not m:
                continue
            if m.group(1) != date_part:
                continue
            max_seq = max(max_seq, int(m.group(2)))
        return f"case_{date_part}_{max_seq + 1:03d}"

    def create_workspace(self, workspace_id: Optional[str] = None) -> WorkspaceRef:
        wid = workspace_id or self.generate_workspace_id()
        self._validate_workspace_id(wid)

        root = self.cases_root / wid
        now = utc_now_iso()
        root.mkdir(parents=True, exist_ok=True)

        for rel in REQUIRED_DIRS:
            (root / rel).mkdir(parents=True, exist_ok=True)

        metadata_path = root / "workspace_metadata.json"
        if not metadata_path.exists():
            _write_json(
                metadata_path,
                {
                    "workspace_id": wid,
                    "state": "CREATE",
                    "created_at": now,
                    "updated_at": now,
                    "context_budget": {
                        "max_context_tokens": 30000,
                        "warning_threshold": 24000,
                    },
                    "lifecycle": {
                        "allowed_states": sorted(ALLOWED_STATES),
                        "allowed_transitions": {
                            k: sorted(v) for k, v in ALLOWED_TRANSITIONS.items()
                        },
                    },
                },
            )

        session_path = root / "state" / "session_state.json"
        if not session_path.exists():
            _write_json(
                session_path,
                {
                    "workspace_id": wid,
                    "current_phase": "INTAKE",
                    "last_phase": None,
                    "phase_updated_at": now,
                },
            )

        changelog_path = root / "state" / "version_changelog.json"
        if not changelog_path.exists():
            _write_json(
                changelog_path,
                {
                    "workspace_id": wid,
                    "updated_at": now,
                    "events": [
                        {
                            "event_type": "WORKSPACE_CREATED",
                            "timestamp": now,
                            "details": {"state": "CREATE"},
                        }
                    ],
                },
            )

        model_version_path = root / "model" / "model_version.json"
        if not model_version_path.exists():
            _write_json(
                model_version_path,
                {
                    "workspace_id": wid,
                    "current_version": 0,
                    "updated_at": now,
                },
            )

        # Baseline artifact skeletons (needed for schema validation and router guards).
        case_model_path = root / "model" / "case_model.json"
        if not case_model_path.exists():
            _write_json(
                case_model_path,
                {
                    "workspace_id": wid,
                    "entities": [],
                    "claims": [],
                    "relations": [],
                },
            )

        contradictions_path = root / "analysis" / "contradictions.json"
        if not contradictions_path.exists():
            _write_json(
                contradictions_path,
                {
                    "workspace_id": wid,
                    "items": [],
                },
            )

        quality_metrics_path = root / "quality" / "quality_metrics.json"
        if not quality_metrics_path.exists():
            _write_json(
                quality_metrics_path,
                {
                    "workspace_id": wid,
                    "metrics": {
                        "completeness": 0.0,
                        "coherence": 0.0,
                        "evidence_strength": 0.0,
                        "actionability": 0.0,
                        "efficiency": 0.0,
                    },
                },
            )

        question_queue_path = root / "dialogue" / "question_queue.json"
        if not question_queue_path.exists():
            _write_json(
                question_queue_path,
                {
                    "workspace_id": wid,
                    "questions": [],
                },
            )

        problem_card_path = root / "analysis" / "problem_card.json"
        if not problem_card_path.exists():
            _write_json(
                problem_card_path,
                {
                    "workspace_id": wid,
                    "problem_id": "UNSET",
                    "title": "Problem not selected yet",
                    "acceptance_criteria": [],
                },
            )

        return WorkspaceRef(workspace_id=wid, path=root)

    def load_workspace(self, workspace_id: str) -> WorkspaceRef:
        self._validate_workspace_id(workspace_id)
        root = self.cases_root / workspace_id
        if not root.exists() or not root.is_dir():
            raise FileNotFoundError(f"Workspace not found: {workspace_id}")

        missing_dirs = [rel for rel in REQUIRED_DIRS if not (root / rel).is_dir()]
        if missing_dirs:
            raise FileNotFoundError(f"Missing required directories: {missing_dirs}")

        missing_files = [rel for rel in REQUIRED_FILES if not (root / rel).is_file()]
        if missing_files:
            raise FileNotFoundError(f"Missing required files: {missing_files}")

        metadata = _read_json(root / "workspace_metadata.json")
        state = metadata.get("state")
        if state not in ALLOWED_STATES:
            raise ValueError(f"Invalid workspace state: {state!r}")

        return WorkspaceRef(workspace_id=workspace_id, path=root)

    def _set_state(self, root: Path, new_state: str, reason: Optional[str] = None) -> None:
        if new_state not in ALLOWED_STATES:
            raise ValueError(f"Unknown state: {new_state}")

        metadata_path = root / "workspace_metadata.json"
        metadata = _read_json(metadata_path)
        old_state = metadata["state"]

        if old_state == new_state:
            return

        allowed = ALLOWED_TRANSITIONS.get(old_state, set())
        if new_state not in allowed:
            raise ValueError(f"Invalid state transition: {old_state} -> {new_state}")

        now = utc_now_iso()
        metadata["state"] = new_state
        metadata["updated_at"] = now
        _write_json(metadata_path, metadata)

        _append_changelog(
            root,
            {
                "event_type": "LIFECYCLE_STATE_CHANGED",
                "timestamp": now,
                "details": {
                    "from": old_state,
                    "to": new_state,
                    "reason": reason or "manual",
                },
            },
        )

    def set_workspace_state(
        self, workspace_id: str, new_state: str, reason: Optional[str] = None
    ) -> WorkspaceRef:
        ref = self.load_workspace(workspace_id)
        self._set_state(ref.path, new_state=new_state, reason=reason)
        return ref

    def archive_workspace(self, workspace_id: str, reason: Optional[str] = None) -> WorkspaceRef:
        return self.set_workspace_state(
            workspace_id=workspace_id,
            new_state="ARCHIVED",
            reason=reason or "archive_workspace",
        )

    def create_checkpoint(
        self,
        workspace_id: str,
        reason: str,
        structural: bool = False,
    ) -> Path:
        ref = self.load_workspace(workspace_id)
        model_version_path = ref.path / "model" / "model_version.json"
        model_version = _read_json(model_version_path)
        current = int(model_version.get("current_version", 0))
        next_version = current + 1

        vdir = ref.path / "versions" / f"v{next_version}"
        vdir.mkdir(parents=True, exist_ok=False)

        now = utc_now_iso()
        metadata = _read_json(ref.path / "workspace_metadata.json")
        session_state = _read_json(ref.path / "state" / "session_state.json")

        _write_json(vdir / "workspace_metadata_snapshot.json", copy.deepcopy(metadata))
        _write_json(vdir / "session_state_snapshot.json", copy.deepcopy(session_state))

        case_model = ref.path / "model" / "case_model.json"
        if case_model.exists():
            shutil.copy2(case_model, vdir / "case_model_snapshot.json")

        _write_json(
            vdir / "version_metadata.json",
            {
                "workspace_id": workspace_id,
                "version": next_version,
                "created_at": now,
                "reason": reason,
                "structural": structural,
            },
        )

        model_version["current_version"] = next_version
        model_version["updated_at"] = now
        _write_json(model_version_path, model_version)

        _append_changelog(
            ref.path,
            {
                "event_type": "VERSION_CHECKPOINT_CREATED",
                "timestamp": now,
                "details": {
                    "version": next_version,
                    "reason": reason,
                    "structural": structural,
                },
            },
        )

        return vdir


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Workspace manager CLI")
    parser.add_argument(
        "--project-root",
        default=".",
        help="Path to project root (default: current directory)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create")
    p_create.add_argument("--workspace-id", default=None)

    p_load = sub.add_parser("load")
    p_load.add_argument("workspace_id")

    p_state = sub.add_parser("set-state")
    p_state.add_argument("workspace_id")
    p_state.add_argument("state", choices=sorted(ALLOWED_STATES))
    p_state.add_argument("--reason", default=None)

    p_archive = sub.add_parser("archive")
    p_archive.add_argument("workspace_id")
    p_archive.add_argument("--reason", default=None)

    p_checkpoint = sub.add_parser("checkpoint")
    p_checkpoint.add_argument("workspace_id")
    p_checkpoint.add_argument("--reason", required=True)
    p_checkpoint.add_argument("--structural", action="store_true")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    manager = WorkspaceManager(Path(args.project_root))

    if args.command == "create":
        ref = manager.create_workspace(args.workspace_id)
        print(json.dumps({"workspace_id": ref.workspace_id, "path": str(ref.path)}))
        return 0

    if args.command == "load":
        ref = manager.load_workspace(args.workspace_id)
        metadata = _read_json(ref.path / "workspace_metadata.json")
        print(
            json.dumps(
                {
                    "workspace_id": ref.workspace_id,
                    "path": str(ref.path),
                    "state": metadata["state"],
                }
            )
        )
        return 0

    if args.command == "set-state":
        ref = manager.set_workspace_state(args.workspace_id, args.state, args.reason)
        metadata = _read_json(ref.path / "workspace_metadata.json")
        print(json.dumps({"workspace_id": ref.workspace_id, "state": metadata["state"]}))
        return 0

    if args.command == "archive":
        ref = manager.archive_workspace(args.workspace_id, args.reason)
        metadata = _read_json(ref.path / "workspace_metadata.json")
        print(json.dumps({"workspace_id": ref.workspace_id, "state": metadata["state"]}))
        return 0

    if args.command == "checkpoint":
        vdir = manager.create_checkpoint(
            workspace_id=args.workspace_id,
            reason=args.reason,
            structural=args.structural,
        )
        print(json.dumps({"checkpoint_path": str(vdir)}))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
