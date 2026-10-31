import sqlite3

conn = sqlite3.connect("trustay.db")

existing = {row[1] for row in conn.execute("PRAGMA table_info(photo_reviews)")}
new_columns = {
    "appeal_by": "INTEGER",
    "appeal_reason": "VARCHAR",
    "appealed_at": "DATETIME",
    "appeal_status": "VARCHAR",
    "appeal_decided_by": "INTEGER",
    "appeal_notes": "VARCHAR",
    "appeal_decided_at": "DATETIME",
}
for name, definition in new_columns.items():
    if name not in existing:
        conn.execute(f"ALTER TABLE photo_reviews ADD COLUMN {name} {definition}")
        print("added photo_reviews." + name)

conn.commit()
print("migration done")
