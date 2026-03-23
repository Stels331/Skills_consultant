#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.canonical_db.config import DatabaseConfig, connect
from app.canonical_db.migration_runner import current_revision, downgrade, upgrade


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap canonical DB schema")
    parser.add_argument("command", choices=["upgrade", "downgrade", "current"])
    parser.add_argument("--env", default=None)
    parser.add_argument("--steps", type=int, default=1)
    args = parser.parse_args()

    config = DatabaseConfig.from_env(args.env)
    connection = connect(config)
    try:
        if args.command == "upgrade":
            print(upgrade(connection, target="head") or "base")
        elif args.command == "downgrade":
            print(downgrade(connection, steps=args.steps) or "base")
        else:
            print(current_revision(connection) or "base")
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
