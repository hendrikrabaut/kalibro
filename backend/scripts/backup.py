"""Consistent copy of the database (safe while the app runs), keeps the last 14."""

import sqlite3
from datetime import datetime
from pathlib import Path

from app.database import DATABASE_PATH, PROJECT_ROOT


KEEP = 14


def main() -> None:
    target_dir = PROJECT_ROOT / "data" / "backups"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"kalibro-{datetime.now():%Y%m%d-%H%M%S}.db"
    with sqlite3.connect(DATABASE_PATH) as source, sqlite3.connect(target) as copy:
        source.backup(copy)
    for old in sorted(target_dir.glob("kalibro-*.db"))[:-KEEP]:
        old.unlink()
    print(target)


if __name__ == "__main__":
    main()
