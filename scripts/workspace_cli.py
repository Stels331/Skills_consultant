#!/usr/bin/env python3
from pathlib import Path
import sys

# Allow running as: python3 scripts/workspace_cli.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.state.workspace_manager import main


if __name__ == "__main__":
    raise SystemExit(main())
