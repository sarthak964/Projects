"""Add concurrency columns before deploying the matching model changes."""
import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def migrate(path):
    path = Path(path).resolve()
    if not path.is_file():
        raise SystemExit("Database file not found; migration refused")
    with sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=30) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = ("jobs", "reviewer_profiles", "otp_codes")
        if not set(required).issubset(tables):
            raise SystemExit("Required tables are missing; migration refused")
        pending = [name for name in required if "version_id" not in {
            row[1] for row in db.execute(f"PRAGMA table_info({name})")
        }]
        if not pending:
            print("PASS: Reliability migration already applied")
            return
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = path.with_name(path.stem + ".before_reliability_" + stamp + ".db")
        with sqlite3.connect(backup) as copy:
            db.backup(copy)
        print("Database backup created:", backup.name)
        db.execute("BEGIN IMMEDIATE")
        try:
            for name in pending:
                db.execute(f"ALTER TABLE {name} ADD COLUMN version_id INTEGER NOT NULL DEFAULT 1")
            db.execute("""UPDATE reviewer_profiles SET jobs_completed = (
                SELECT COUNT(*) FROM jobs
                WHERE jobs.reviewer_id = reviewer_profiles.user_id AND jobs.status = 'paid'
            )""")
            db.commit()
        except Exception:
            db.rollback()
            raise
        print("PASS: Reliability migration applied")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=Path(__file__).parent / "trustay.db")
    migrate(parser.parse_args().database)
