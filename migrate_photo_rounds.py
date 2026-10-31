"""Add explicit replacement-photo membership before deploying the new model."""
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
        if not {"photos", "photo_reviews"}.issubset(tables):
            raise SystemExit("Required photo tables are missing")
        columns = {row[1] for row in db.execute("PRAGMA table_info(photos)")}
        needs_column = "photo_review_id" not in columns
        # Existing, unambiguous legacy re-uploads can be linked using their old rule.
        needs_backfill = False if needs_column else bool(db.execute("""
            SELECT 1 FROM photos p JOIN photo_reviews r ON r.job_id = p.job_id
            WHERE p.photo_review_id IS NULL AND p.created_at > r.created_at LIMIT 1
        """).fetchone())
        if needs_column or needs_backfill:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup = path.with_name(path.stem + ".before_photo_rounds_" + stamp + ".db")
            with sqlite3.connect(backup) as copy:
                db.backup(copy)
            print("Database backup created:", backup.name)
        db.execute("BEGIN IMMEDIATE")
        try:
            if needs_column:
                db.execute("ALTER TABLE photos ADD COLUMN photo_review_id INTEGER REFERENCES photo_reviews(id)")
            db.execute("""UPDATE photos SET photo_review_id = (
                SELECT r.id FROM photo_reviews r
                WHERE r.job_id = photos.job_id AND photos.created_at > r.created_at
            ) WHERE photo_review_id IS NULL AND EXISTS (
                SELECT 1 FROM photo_reviews r
                WHERE r.job_id = photos.job_id AND photos.created_at > r.created_at
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS ix_photos_job_review_item ON photos(job_id, photo_review_id, checklist_item)")
            db.commit()
        except Exception:
            db.rollback()
            raise
    print("PASS: Photo-round migration complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=Path(__file__).parent / "trustay.db")
    migrate(parser.parse_args().database)
