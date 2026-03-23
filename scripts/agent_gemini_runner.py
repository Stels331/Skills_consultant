#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CODEX_BIN = Path("/Users/stas/.antigravity/extensions/openai.chatgpt-0.4.79-darwin-arm64/bin/macos-aarch64/codex")
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "antigravity_review_result.schema.json"


def main() -> int:
    bundle = sys.stdin.read()
    if not bundle.strip():
        print("No bundle received on stdin", file=sys.stderr)
        return 2
    if not CODEX_BIN.exists():
        print(f"Codex binary not found: {CODEX_BIN}", file=sys.stderr)
        return 2
    print(
        f"[agent_gemini_runner] start reviewer bundle_bytes={len(bundle.encode('utf-8'))}",
        file=sys.stderr,
        flush=True,
    )
    with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as out_file:
        out_path = Path(out_file.name)
    print("[agent_gemini_runner] calling Codex reviewer transport", file=sys.stderr, flush=True)
    cmd = [
        str(CODEX_BIN),
        "exec",
        "-",
        "--full-auto",
        "-C",
        str(PROJECT_ROOT),
        "--skip-git-repo-check",
        "--output-schema",
        str(SCHEMA_PATH),
        "-o",
        str(out_path),
    ]
    proc = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        input=bundle,
        text=True,
        stdout=sys.stderr,
        stderr=sys.stderr,
        timeout=3600,
    )
    if proc.returncode != 0:
        print(f"[agent_gemini_runner] reviewer transport failed rc={proc.returncode}", file=sys.stderr, flush=True)
        return proc.returncode
    result_text = out_path.read_text(encoding="utf-8").strip()
    if not result_text:
        result = {
            "status": "fail",
            "report": "Reviewer transport returned empty JSON payload.",
        }
    else:
        result = json.loads(result_text)
    print(
        f"[agent_gemini_runner] result status={result['status']}",
        file=sys.stderr,
        flush=True,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
