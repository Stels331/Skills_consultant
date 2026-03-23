#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CODEX_BIN = Path("/Users/stas/.antigravity/extensions/openai.chatgpt-0.4.79-darwin-arm64/bin/macos-aarch64/codex")
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "antigravity_codex_result.schema.json"


def main() -> int:
    bundle = sys.stdin.read()
    if not bundle.strip():
        print("No bundle received on stdin", file=sys.stderr)
        return 2
    if not CODEX_BIN.exists():
        print(f"Codex binary not found: {CODEX_BIN}", file=sys.stderr)
        return 2

    with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as out_file:
        out_path = Path(out_file.name)
    print(
        f"[agent_codex_runner] start bundle_bytes={len(bundle.encode('utf-8'))} output_file={out_path}",
        file=sys.stderr,
        flush=True,
    )

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
    print(
        f"[agent_codex_runner] launching codex exec in {PROJECT_ROOT}",
        file=sys.stderr,
        flush=True,
    )
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
        print(f"[agent_codex_runner] codex exec failed rc={proc.returncode}", file=sys.stderr, flush=True)
        return proc.returncode

    print("[agent_codex_runner] codex exec completed, reading JSON result", file=sys.stderr, flush=True)
    result_text = out_path.read_text(encoding="utf-8").strip()
    if not result_text:
        print("Codex did not produce a final JSON message", file=sys.stderr)
        return 1
    # Return the JSON contract exactly to stdout for run-auto.
    payload = json.loads(result_text)
    print(
        f"[agent_codex_runner] result commit={payload.get('commit', 'missing')}",
        file=sys.stderr,
        flush=True,
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
