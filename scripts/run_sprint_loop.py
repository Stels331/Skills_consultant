#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = PROJECT_ROOT / "reports"
PROMPTS_DIR = REPORTS_DIR / "prompts"
TESTS_DIR = REPORTS_DIR / "tests"
REVIEWS_DIR = REPORTS_DIR / "reviews"
SPRINTS_DIR = PROJECT_ROOT / "TECHNICAL_SPEC_DIALOGUE_PLATFORM_UPDATE" / "SPRINTS_DETAILED"
STATE_PATH = REPORTS_DIR / "sprint_state.json"
CODEX_TEMPLATE = PROJECT_ROOT / "prompts" / "antigravity" / "codex_sprint_prompt.md"
ACCEPTANCE_TEMPLATE = PROJECT_ROOT / "prompts" / "antigravity" / "manual_acceptance_prompt.md"

SPRINT_ORDER = [
    "SPRINT_01_FOUNDATION",
    "SPRINT_02_AUTH_GRAPH",
    "SPRINT_03_DIALOGUE_CORE",
    "SPRINT_04_VALIDATION_UI",
    "SPRINT_05_MODEL_UPDATES_REENTRY",
    "SPRINT_06_ISOLATION",
    "SPRINT_07_HARDENING_RELEASE",
    "SPRINT_08_DECISION_DOMAIN",
    "SPRINT_09_DECISION_ASSURANCE",
    "SPRINT_10_DECISION_RETRIEVAL_UX",
]

SPRINT_FILE_MAP = {
    "SPRINT_01_FOUNDATION": "SPRINT_01_FOUNDATION.md",
    "SPRINT_02_AUTH_GRAPH": "SPRINT_02_AUTH_GRAPH.md",
    "SPRINT_03_DIALOGUE_CORE": "SPRINT_03_DIALOGUE_CORE.md",
    "SPRINT_04_VALIDATION_UI": "SPRINT_04_VALIDATION_UI.md",
    "SPRINT_05_MODEL_UPDATES_REENTRY": "SPRINT_05_MODEL_UPDATES_REENTRY.md",
    "SPRINT_06_ISOLATION": "SPRINT_06_ISOLATION.md",
    "SPRINT_07_HARDENING_RELEASE": "SPRINT_07_HARDENING_RELEASE.md",
    "SPRINT_08_DECISION_DOMAIN": "SPRINT_08_DECISION_DOMAIN.md",
    "SPRINT_09_DECISION_ASSURANCE": "SPRINT_09_DECISION_ASSURANCE.md",
    "SPRINT_10_DECISION_RETRIEVAL_UX": "SPRINT_10_DECISION_RETRIEVAL_UX.md",
}


def ensure_dirs() -> None:
    for path in [REPORTS_DIR, PROMPTS_DIR, REVIEWS_DIR, TESTS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def default_state() -> dict:
    return {
        "current_sprint": SPRINT_ORDER[0],
        "status": "ready",
        "attempt": 1,
        "last_commit": None,
        "codex_summary_path": None,
        "test_report_path": None,
        "acceptance_notes_path": None,
    }


def normalize_state(raw_state: dict) -> dict:
    state = default_state()
    state.update(raw_state)

    legacy_status_map = {
        "awaiting_review": "awaiting_acceptance",
        "changes_requested": "changes_requested",
        "accepted": "accepted",
        "completed": "completed",
    }
    state["status"] = legacy_status_map.get(state.get("status"), state.get("status", "ready"))

    legacy_review_status = state.pop("review_status", None)
    if state.get("status") == "ready" and legacy_review_status == "fail":
        state["status"] = "changes_requested"
    if state.get("status") == "ready" and state.get("codex_summary_path") and state.get("test_report_path"):
        state["status"] = "awaiting_acceptance"

    legacy_review_report = state.pop("review_report_path", None)
    if not state.get("acceptance_notes_path") and legacy_review_report:
        state["acceptance_notes_path"] = legacy_review_report

    if state.get("current_sprint") not in SPRINT_ORDER:
        state["current_sprint"] = SPRINT_ORDER[0]
    if not isinstance(state.get("attempt"), int) or state["attempt"] < 1:
        state["attempt"] = 1

    return state


def load_state() -> dict:
    ensure_dirs()
    if not STATE_PATH.exists():
        state = default_state()
        save_state(state)
        return state
    return normalize_state(json.loads(STATE_PATH.read_text(encoding="utf-8")))


def save_state(state: dict) -> None:
    ensure_dirs()
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sprint_file_path(sprint_name: str) -> Path:
    return SPRINTS_DIR / SPRINT_FILE_MAP[sprint_name]


def sprint_slug(sprint_name: str) -> str:
    return sprint_name.lower()


def render_template(template_path: Path, replacements: dict[str, str]) -> str:
    text = template_path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def read_optional_text(path_str: str | None) -> str:
    if not path_str:
        return "Not provided"
    path = PROJECT_ROOT / path_str
    if not path.exists():
        return f"Missing file: {path_str}"
    return path.read_text(encoding="utf-8")


def git_diff_hint(commit_hash: str | None) -> str:
    if not commit_hash or commit_hash.startswith("not-created"):
        return "No commit recorded yet"
    try:
        result = subprocess.run(
            ["git", "rev-parse", f"{commit_hash}~1"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        parent = result.stdout.strip()
        return f"git diff {parent}..{commit_hash}"
    except subprocess.CalledProcessError:
        return f"git show {commit_hash}"


def cmd_init(_: argparse.Namespace) -> int:
    save_state(default_state())
    print(f"Initialized sprint state at {STATE_PATH}")
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    state = load_state()
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def cmd_prepare_codex(_: argparse.Namespace) -> int:
    state = load_state()
    sprint = state["current_sprint"]
    sprint_path = sprint_file_path(sprint)
    prompt_path = PROMPTS_DIR / f"{sprint_slug(sprint)}_codex_prompt.md"
    content = render_template(
        CODEX_TEMPLATE,
        {
            "CURRENT_SPRINT": sprint,
            "SPRINT_SPEC_PATH": str(sprint_path.relative_to(PROJECT_ROOT)),
            "REVIEW_STATUS": state["status"],
            "ATTEMPT": str(state["attempt"]),
            "REVIEW_REPORT_PATH": state["acceptance_notes_path"] or "none",
        },
    )
    prompt_path.write_text(content + "\n", encoding="utf-8")
    print(str(prompt_path))
    return 0


def cmd_start_codex(_: argparse.Namespace) -> int:
    state = load_state()
    if state["status"] in {"awaiting_acceptance", "accepted", "completed"}:
        print(f"Cannot start codex from status={state['status']}", file=sys.stderr)
        return 1
    state["status"] = "in_progress"
    save_state(state)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def cmd_codex_done(args: argparse.Namespace) -> int:
    state = load_state()
    state["last_commit"] = args.commit
    state["codex_summary_path"] = args.summary_file
    state["test_report_path"] = args.test_report
    state["status"] = "awaiting_acceptance"
    save_state(state)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def cmd_build_bundle(args: argparse.Namespace) -> int:
    state = load_state()
    sprint = state["current_sprint"]
    sprint_path = sprint_file_path(sprint)
    if args.agent == "acceptance":
        if not state.get("codex_summary_path") or not state.get("test_report_path"):
            print("Cannot build acceptance bundle: codex-done data is incomplete", file=sys.stderr)
            return 1
        inline_prompt = render_template(
            ACCEPTANCE_TEMPLATE,
            {
                "CURRENT_SPRINT": sprint,
                "SPRINT_SPEC_PATH": str(sprint_path.relative_to(PROJECT_ROOT)),
                "STATE_STATUS": state["status"],
                "ATTEMPT": str(state["attempt"]),
                "CODEX_SUMMARY_PATH": state["codex_summary_path"] or "none",
                "TEST_REPORT_PATH": state["test_report_path"] or "none",
            },
        )
        bundle_path = PROMPTS_DIR / f"{sprint_slug(sprint)}_acceptance_bundle.md"
        parts = [
            f"# Acceptance Bundle: {sprint}",
            "## Sprint State",
            "```json",
            json.dumps(state, ensure_ascii=False, indent=2),
            "```",
            "## Acceptance Prompt",
            inline_prompt.strip(),
            "## Sprint Spec Path",
            str(sprint_path.relative_to(PROJECT_ROOT)),
            "## Sprint Spec",
            sprint_path.read_text(encoding="utf-8").strip(),
            "## Codex Summary Path",
            state["codex_summary_path"] or "not-set",
            "## Codex Summary",
            read_optional_text(state.get("codex_summary_path")).strip(),
            "## Test Report Path",
            state["test_report_path"] or "not-set",
            "## Test Report",
            read_optional_text(state.get("test_report_path")).strip(),
            "## Commit / Diff Context",
            state["last_commit"] or "not-set",
            "## Diff Hint",
            git_diff_hint(state.get("last_commit")),
            "## Acceptance Checklist",
            "- Все обязательные задачи спринта закрыты.",
            "- Критерии приемки спринта выполнены.",
            "- Релевантные тесты запущены и результаты зафиксированы.",
            "- Нет очевидного scope creep вне спринта.",
            "- Оставшиеся ограничения и blockers описаны явно.",
        ]
    else:
        inline_prompt = render_template(
            CODEX_TEMPLATE,
            {
                "CURRENT_SPRINT": sprint,
                "SPRINT_SPEC_PATH": str(sprint_path.relative_to(PROJECT_ROOT)),
                "REVIEW_STATUS": state["status"],
                "ATTEMPT": str(state["attempt"]),
                "REVIEW_REPORT_PATH": state["acceptance_notes_path"] or "none",
            },
        )
        bundle_path = PROMPTS_DIR / f"{sprint_slug(sprint)}_codex_bundle.md"
        parts = [
            f"# Codex Bundle: {sprint}",
            "## Sprint State",
            "```json",
            json.dumps(state, ensure_ascii=False, indent=2),
            "```",
            "## Executor Prompt",
            inline_prompt.strip(),
            "## Sprint Spec Path",
            str(sprint_path.relative_to(PROJECT_ROOT)),
            "## Sprint Spec",
            sprint_path.read_text(encoding="utf-8").strip(),
            "## Previous Acceptance Notes Path",
            state["acceptance_notes_path"] or "none",
            "## Previous Acceptance Notes",
            read_optional_text(state.get("acceptance_notes_path")).strip(),
        ]
    bundle_path.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    print(str(bundle_path))
    return 0


def cmd_set_sprint(args: argparse.Namespace) -> int:
    state = load_state()
    if args.name not in SPRINT_ORDER:
        print(f"Unknown sprint: {args.name}", file=sys.stderr)
        return 2
    state.update(
        {
            "current_sprint": args.name,
            "status": "ready",
            "attempt": 1,
            "last_commit": None,
            "codex_summary_path": None,
            "test_report_path": None,
            "acceptance_notes_path": None,
        }
    )
    save_state(state)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def cmd_accept_sprint(args: argparse.Namespace) -> int:
    state = load_state()
    state["acceptance_notes_path"] = args.notes_file
    state["status"] = "accepted"
    save_state(state)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def cmd_request_changes(args: argparse.Namespace) -> int:
    state = load_state()
    state["acceptance_notes_path"] = args.notes_file
    state["status"] = "changes_requested"
    state["attempt"] += 1
    save_state(state)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def cmd_advance(_: argparse.Namespace) -> int:
    state = load_state()
    if state["status"] != "accepted":
        print("Cannot advance: current sprint has not been manually accepted", file=sys.stderr)
        return 1
    current = state["current_sprint"]
    idx = SPRINT_ORDER.index(current)
    if idx == len(SPRINT_ORDER) - 1:
        state["status"] = "completed"
        save_state(state)
        print("Final sprint completed")
        return 0
    next_sprint = SPRINT_ORDER[idx + 1]
    state.update(
        {
            "current_sprint": next_sprint,
            "status": "ready",
            "attempt": 1,
            "last_commit": None,
            "codex_summary_path": None,
            "test_report_path": None,
            "acceptance_notes_path": None,
        }
    )
    save_state(state)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Codex sprint execution with human acceptance")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init")
    subparsers.add_parser("status")
    set_sprint = subparsers.add_parser("set-sprint")
    set_sprint.add_argument("--name", required=True, choices=SPRINT_ORDER)
    subparsers.add_parser("prepare-codex")
    subparsers.add_parser("start-codex")

    codex_done = subparsers.add_parser("codex-done")
    codex_done.add_argument("--commit", required=True)
    codex_done.add_argument("--summary-file", required=True)
    codex_done.add_argument("--test-report", required=True)

    build_bundle = subparsers.add_parser("build-bundle")
    build_bundle.add_argument("--agent", required=True, choices=["codex", "acceptance"])

    accept = subparsers.add_parser("accept-sprint")
    accept.add_argument("--notes-file", required=True)

    reject = subparsers.add_parser("request-changes")
    reject.add_argument("--notes-file", required=True)

    subparsers.add_parser("advance")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "init":
        return cmd_init(args)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "set-sprint":
        return cmd_set_sprint(args)
    if args.command == "prepare-codex":
        return cmd_prepare_codex(args)
    if args.command == "start-codex":
        return cmd_start_codex(args)
    if args.command == "codex-done":
        return cmd_codex_done(args)
    if args.command == "build-bundle":
        return cmd_build_bundle(args)
    if args.command == "accept-sprint":
        return cmd_accept_sprint(args)
    if args.command == "request-changes":
        return cmd_request_changes(args)
    if args.command == "advance":
        return cmd_advance(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
