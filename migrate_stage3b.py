import sqlite3

conn = sqlite3.connect("trustay.db")

existing = {row[1] for row in conn.execute("PRAGMA table_info(photo_reviews)")}
new_columns = {
    "ai_result_deadline": "DATETIME",
    "human_fee_amount": "FLOAT DEFAULT 0",
    "human_fee_status": "VARCHAR DEFAULT 'none'",
}
for name, definition in new_columns.items():
    if name not in existing:
        conn.execute(f"ALTER TABLE photo_reviews ADD COLUMN {name} {definition}")
        print("added photo_reviews." + name)

# Cases already sitting at "AI found the photos genuine" get a 24-hour deadline.
cur = conn.execute(
    "UPDATE photo_reviews SET ai_result_deadline = datetime(created_at, '+1 day') "
    "WHERE status = 'ai_checked_genuine' AND ai_result_deadline IS NULL"
)
print("deadlines backfilled:", cur.rowcount)

conn.commit()
print("migration done")
