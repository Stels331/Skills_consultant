#!/usr/bin/env python3
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.release.release_package import prepare_release_package


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    out = prepare_release_package(root)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
