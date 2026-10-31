import sqlite3

conn = sqlite3.connect("trustay.db")


def add_columns(table, columns):
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
            print("added", table + "." + name)


add_columns(
    "reviewer_profiles",
    {
        "strikes": "INTEGER DEFAULT 0",
        "suspended": "BOOLEAN DEFAULT 0",
    },
)
add_columns(
    "photo_reviews",
    {
        "human_decision": "VARCHAR",
        "decided_by": "INTEGER",
        "decision_notes": "VARCHAR",
    },
)

conn.commit()
print("migration done")
