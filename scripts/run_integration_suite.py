#!/usr/bin/env python3
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.testing.integration_suite import run_integration_suite


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    out = run_integration_suite(root)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
