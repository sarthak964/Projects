import hashlib
import sqlite3
from contextlib import closing

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import database
from app.services.demo_seed import OWNER, demo_paths, prepare_demo, require_owned


def query(path, sql):
    with closing(sqlite3.connect(path)) as db:
        return db.execute(sql).fetchall()


def test_seed_has_expected_accounts_stages_evidence_and_no_real_db_write(tmp_path):
    original = tmp_path / 'trustay.db'
    original.write_bytes(b'original database sentinel')
    result = prepare_demo(tmp_path)
    path, uploads = demo_paths(tmp_path)
    assert result['created'] is True
    assert original.read_bytes() == b'original database sentinel'
    assert query(path, 'SELECT COUNT(*) FROM users') == [(3,)]
    assert query(path, 'SELECT COUNT(*) FROM jobs') == [(10,)]
    assert query(path, 'SELECT owner FROM demo_metadata') == [(OWNER,)]
    assert query(path, 'PRAGMA integrity_check') == [('ok',)]
    assert query(path, 'PRAGMA foreign_key_check') == []
    assert query(path, "SELECT COUNT(*) FROM photo_reviews WHERE appeal_status = 'pending'") == [(1,)]
    rows = query(path, 'SELECT stored_name, size_bytes FROM photos')
    assert len({name for name, size in rows}) == len(rows)
    for name, size in rows:
        assert (uploads / name).stat().st_size == size
    assert all('PRECOMPUTED DEMO RESULT' in row[0] for row in query(path, 'SELECT ai_generated_summary FROM reports WHERE ai_generated_summary IS NOT NULL'))


def test_rerun_preserves_edits_and_reset_backs_up_only_owned_demo(tmp_path):
    prepare_demo(tmp_path)
    path, _ = demo_paths(tmp_path)
    with closing(sqlite3.connect(path)) as db:
        db.execute("UPDATE users SET name = 'Edited demo renter' WHERE id = 4")
        db.commit()
    assert prepare_demo(tmp_path)['created'] is False
    assert query(path, 'SELECT name FROM users WHERE id = 4') == [('Edited demo renter',)]
    result = prepare_demo(tmp_path, reset=True)
    assert result['backup']
    assert query(result['backup'], 'SELECT name FROM users WHERE id = 4') == [('Edited demo renter',)]
    assert query(path, 'SELECT name FROM users WHERE id = 4') == [('Demo Renter',)]


@pytest.mark.parametrize('reset', [False, True])
def test_unowned_database_is_never_replaced(tmp_path, reset):
    path, _ = demo_paths(tmp_path)
    path.parent.mkdir()
    with closing(sqlite3.connect(path)) as db:
        db.execute('CREATE TABLE important (value TEXT)')
        db.commit()
    digest = hashlib.sha256(path.read_bytes()).digest()
    with pytest.raises(ValueError, match='unmarked'):
        prepare_demo(tmp_path, reset=reset)
    assert hashlib.sha256(path.read_bytes()).digest() == digest


def test_wrong_owner_is_rejected(tmp_path):
    path, _ = demo_paths(tmp_path)
    path.parent.mkdir()
    with closing(sqlite3.connect(path)) as db:
        db.execute('CREATE TABLE demo_metadata (owner TEXT)')
        db.execute("INSERT INTO demo_metadata VALUES ('another-app')")
        db.commit()
    with pytest.raises(ValueError, match='not owned'):
        require_owned(path)


def test_reset_refuses_running_demo(tmp_path):
    prepare_demo(tmp_path)
    path, _ = demo_paths(tmp_path)
    lock = path.parent / 'server.lock'
    lock.write_text('test-running')
    digest = hashlib.sha256(path.read_bytes()).digest()
    with pytest.raises(ValueError, match='Stop run_demo'):
        prepare_demo(tmp_path, reset=True)
    assert hashlib.sha256(path.read_bytes()).digest() == digest


def test_seed_api_accounts_queues_photos_and_balanced_ledger(tmp_path, client, headers, monkeypatch):
    prepare_demo(tmp_path)
    path, uploads = demo_paths(tmp_path)
    engine = create_engine('sqlite:///' + path.as_posix(), connect_args={'check_same_thread': False})
    factory = sessionmaker(bind=engine, autoflush=False)
    monkeypatch.setattr(database, 'SessionLocal', factory)
    from app.routers import photo, photo_review
    monkeypatch.setattr(photo, 'UPLOAD_DIR', uploads)
    monkeypatch.setattr(photo_review, 'UPLOAD_DIR', uploads)
    try:
        assert client.get('/jobs/mine', headers=headers(4)).json()['total'] == 10
        rows = client.get('/jobs/open', headers=headers(5)).json()
        assert len(rows) == 1 and rows[0]['distance_km'] <= 50
        summary = client.get('/admin/ledger/summary', headers=headers(1)).json()
        assert summary['balanced'] is True
        assert summary['escrow_balance'] == 1175
        assert summary['platform_balance'] == 22.5
        assert client.get('/admin/photo-reviews', headers=headers(1)).status_code == 200
        assert client.get('/admin/appeals', headers=headers(1)).status_code == 200
        with factory() as db:
            from app.models import Photo
            pid = db.query(Photo.id).first()[0]
        assert client.get(f'/photos/{pid}', headers=headers(4)).status_code == 200
        assert client.post('/jobs/1/accept', headers=headers(5)).status_code == 200
        assert client.post('/jobs/6/photo-review/approve', headers=headers(4)).status_code == 200
        assert client.get('/admin/ledger/summary', headers=headers(1)).json()['balanced'] is True
    finally:
        engine.dispose()


def test_launcher_isolates_subprocess_and_locks_reset_without_editing_env(tmp_path, monkeypatch):
    import run_demo
    from types import SimpleNamespace
    prepare_demo(tmp_path)
    env_file = tmp_path / '.env'
    env_file.write_text('JWT_SECRET=keep-this-original-setting\n')
    original = env_file.read_bytes()
    monkeypatch.setattr(run_demo, '__file__', str(tmp_path / 'run_demo.py'))
    monkeypatch.setattr(run_demo.sys, 'argv', ['run_demo.py'])
    def launch(command, cwd, env):
        path, uploads = demo_paths(tmp_path)
        assert '8001' in command
        assert env['DATABASE_URL'] == 'sqlite:///' + path.as_posix()
        assert env['UPLOAD_DIR'] == str(uploads)
        assert env['JWT_SECRET'] == 'trustay-separate-local-demo-key'
        assert env['SCHEDULER_ENABLED'] == 'false'
        assert env['ENVIRONMENT'] == 'development'
        with pytest.raises(ValueError, match='Stop run_demo'):
            prepare_demo(tmp_path, reset=True)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(run_demo.subprocess, 'run', launch)
    assert run_demo.main() == 0
    assert env_file.read_bytes() == original
    assert not (tmp_path / 'demo_data/server.lock').exists()
