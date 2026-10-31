import sqlite3

from migrate_photo_rounds import migrate


def test_photo_round_migration_preserves_originals_links_legacy_reuploads_and_is_repeatable(tmp_path):
    path = tmp_path / 'photos.db'
    with sqlite3.connect(path) as db:
        db.executescript('''
            CREATE TABLE photos(id INTEGER PRIMARY KEY, job_id INTEGER, checklist_item TEXT, created_at DATETIME);
            CREATE TABLE photo_reviews(id INTEGER PRIMARY KEY, job_id INTEGER, created_at DATETIME);
            INSERT INTO photo_reviews VALUES(1, 10, '2026-10-22 10:00:00.000000');
            INSERT INTO photos VALUES(1, 10, 'AC working', '2026-10-22 09:00:00.000000');
            INSERT INTO photos VALUES(2, 10, 'AC working', '2026-10-22 10:00:00.000000');
            INSERT INTO photos VALUES(3, 10, 'AC working', '2026-10-22 11:00:00.000000');
        ''')
    migrate(path)
    migrate(path)
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT id, photo_review_id FROM photos ORDER BY id').fetchall() == [(1, None), (2, None), (3, 1)]
        assert db.execute('SELECT created_at FROM photos WHERE id = 2').fetchone()[0] == '2026-10-22 10:00:00.000000'
        assert 'ix_photos_job_review_item' in {row[1] for row in db.execute('PRAGMA index_list(photos)')}
    assert len(list(tmp_path.glob('*.before_photo_rounds_*.db'))) == 1
