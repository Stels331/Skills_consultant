#!/usr/bin/env python3
from pathlib import Path
import argparse
import json


def _read_jsonl(path: Path):
    if not path.is_file():
        return []
    out = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if not s:
            continue
        try:
            out.append(json.loads(s))
        except Exception:
            continue
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose latest stage result for workspace")
    parser.add_argument("workspace_id")
    parser.add_argument("stage_name")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    log = root / "cases" / args.workspace_id / "governance" / "decision_log.jsonl"
    entries = [e for e in _read_jsonl(log) if str(e.get("stage_name", "")).lower() == args.stage_name.lower()]
    if not entries:
        print(json.dumps({"error": "no stage entries found"}, ensure_ascii=False, indent=2))
        return 1
    latest = entries[-1]
    out = {
        "workspace_id": args.workspace_id,
        "stage_name": args.stage_name,
        "gate_result": latest.get("gate_result"),
        "from_state": latest.get("from_state"),
        "to_state": latest.get("to_state"),
        "recheck_trigger": latest.get("recheck_trigger"),
        "violations": latest.get("violations", []),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
