import sqlite3

conn = sqlite3.connect("trustay.db")

existing = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
if "commission_rate" not in existing:
    conn.execute("ALTER TABLE jobs ADD COLUMN commission_rate FLOAT")
    print("added jobs.commission_rate")

conn.commit()
print("migration done")
