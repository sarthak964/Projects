import sqlite3

conn = sqlite3.connect("trustay.db")
existing = {row[1] for row in conn.execute("PRAGMA table_info(photo_reviews)")}

new_columns = {
    "reupload_deadline": "DATETIME",
    "recheck_deadline": "DATETIME",
    "reuploaded_at": "DATETIME",
    "escalation_reason": "VARCHAR",
}
for name, col_type in new_columns.items():
    if name not in existing:
        conn.execute(f"ALTER TABLE photo_reviews ADD COLUMN {name} {col_type}")
        print("added column", name)

# Reviews already waiting for a re-upload get a 24-hour deadline from when they were created.
conn.execute(
    "UPDATE photo_reviews SET reupload_deadline = datetime(created_at, '+1 day') "
    "WHERE status = 'awaiting_reupload' AND reupload_deadline IS NULL"
)
conn.commit()
print("migration done")
