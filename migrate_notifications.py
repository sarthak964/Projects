"""Create the notifications table before connecting application event hooks."""
import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_COLUMNS = {
    "id", "user_id", "job_id", "event_key", "event_type", "title", "message",
    "deadline_at", "is_read", "read_at", "created_at",
}


def migrate(path):
    path = Path(path).resolve()
    if not path.is_file():
        raise SystemExit("Database file not found; migration refused")
    with sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=30) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"users", "jobs"}.issubset(tables):
            raise SystemExit("Required users/jobs tables are missing")
        if "notifications" in tables:
            columns = {row[1] for row in db.execute("PRAGMA table_info(notifications)")}
            if not _COLUMNS.issubset(columns):
                raise SystemExit("An incompatible notifications table exists; migration refused")
            print("PASS: Notifications table already exists")
        else:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup = path.with_name(path.stem + ".before_notifications_" + stamp + ".db")
            with sqlite3.connect(backup) as copy:
                db.backup(copy)
            print("Database backup created:", backup.name)
        db.execute("BEGIN IMMEDIATE")
        try:
            db.execute("""CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                job_id INTEGER NOT NULL REFERENCES jobs(id),
                event_key VARCHAR(255) NOT NULL UNIQUE,
                event_type VARCHAR(80) NOT NULL,
                title VARCHAR(160) NOT NULL,
                message TEXT NOT NULL,
                deadline_at DATETIME,
                is_read BOOLEAN NOT NULL DEFAULT 0 CONSTRAINT ck_notifications_is_read CHECK (is_read IN (0, 1)),
                read_at DATETIME,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS ix_notifications_user_id_id ON notifications(user_id, id)")
            db.execute("CREATE INDEX IF NOT EXISTS ix_notifications_user_unread_id ON notifications(user_id, is_read, id)")
            db.commit()
        except Exception:
            db.rollback()
            raise
    print("PASS: Notifications migration complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=Path(__file__).parent / "trustay.db")
    migrate(parser.parse_args().database)
