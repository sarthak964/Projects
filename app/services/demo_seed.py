"""Offline, repeatable fixtures in a separately owned demo database."""
import sqlite3
import shutil
import os
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

OWNER = 'trustay-owned-demo-v1'
PHONES = {'renter': '9000000001', 'reviewer': '9000000002', 'admin': '9999999999'}
CHECKLIST = ['Check walls for cracks or damp patches', 'Check taps for water flow and leaks']


def demo_paths(root):
    root = Path(root).resolve()
    folder = root / 'demo_data'
    if folder.resolve() != folder or folder.is_symlink():
        raise ValueError('Demo directory must be a real directory inside the project')
    database = folder / 'trustay_demo.db'
    uploads = folder / 'uploads'
    for path in (database, uploads, folder / 'backups', folder / 'server.lock'):
        if path.is_symlink() or path.resolve() != path:
            raise ValueError('Demo paths must not be redirected with links')
    return database, uploads


def require_owned(database):
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as db:
        try:
            owner = db.execute('SELECT owner FROM demo_metadata').fetchall()
        except sqlite3.DatabaseError as exc:
            raise ValueError('Refusing to replace an unmarked database') from exc
        if owner != [(OWNER,)]:
            raise ValueError('Refusing to replace a database not owned by this demo')


def prepare_demo(root, reset=False):
    database, _ = demo_paths(root)
    database.parent.mkdir(parents=True, exist_ok=True)
    lock = database.parent / 'server.lock'
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ValueError('Stop run_demo.py before preparing or resetting the demo; another seed may also be running') from exc
    try:
        os.write(descriptor, f'seed:{os.getpid()}'.encode('ascii'))
        os.close(descriptor)
        return _prepare_demo(root, reset)
    finally:
        lock.unlink(missing_ok=True)


def _prepare_demo(root, reset=False):
    database, uploads = demo_paths(root)
    if database.exists():
        require_owned(database)
        if not reset:
            return {'database': str(database), 'uploads': str(uploads), 'created': False, 'backup': None}
    database.parent.mkdir(parents=True, exist_ok=True)
    uploads.mkdir(exist_ok=True)
    backup = None
    if database.exists():
        backup_dir = database.parent / 'backups'
        backup_dir.mkdir(exist_ok=True)
        backup = backup_dir / ('trustay_demo_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.db')
        with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as old:
            with closing(sqlite3.connect(backup)) as saved:
                old.backup(saved)
    temporary = database.with_name('building_' + uuid.uuid4().hex + '.db')
    try:
        _build(temporary, uploads)
        temporary.replace(database)
    finally:
        temporary.unlink(missing_ok=True)
    return {'database': str(database), 'uploads': str(uploads), 'created': True, 'backup': str(backup) if backup else None}


def _sample_images(uploads):
    from PIL import Image, ImageDraw
    names = []
    for label in ('walls', 'taps'):
        path = uploads / ('demo-sample-' + label + '.png')
        if path.is_symlink() or path.resolve().parent != uploads.resolve():
            raise ValueError('Sample image paths must remain in demo uploads')
        if not path.exists():
            image = Image.new('RGB', (640, 360), '#e8edf4')
            draw = ImageDraw.Draw(image)
            draw.text((35, 95), 'TRUSTAY DEMO - SAMPLE ' + label.upper(), fill='#16243b')
            draw.text((35, 140), 'Placeholder only. Not a property inspection photo.', fill='#16243b')
            image.save(path, format='PNG')
        names.append(path.name)
    return names


def _build(database, uploads):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    import app.models as models
    from app.core.database import Base
    from app.core.time import utcnow
    from app.services.ledger import backfill_ledger
    from app.services.verification_nodes import summarize_node

    names = _sample_images(uploads)
    engine = create_engine('sqlite:///' + database.as_posix())
    now = utcnow()
    try:
        Base.metadata.create_all(engine)
        with engine.begin() as db:
            db.exec_driver_sql('CREATE TABLE demo_metadata (owner TEXT NOT NULL)')
            db.exec_driver_sql('INSERT INTO demo_metadata (owner) VALUES (?)', (OWNER,))
            for uid, role, name in [(1, 'admin', 'Demo Admin'), (4, 'renter', 'Demo Renter'), (5, 'reviewer', 'Demo Reviewer')]:
                db.execute(models.User.__table__.insert().values(id=uid, phone=PHONES[role], name=name, role=role, created_at=now))
            db.execute(models.ReviewerProfile.__table__.insert().values(user_id=5, home_lat=28.632, home_lng=77.220, jobs_completed=1, strikes=1))
            stages = ['requested', 'accepted', 'visited', 'report_submitted', 'needs_reupload', 'verified', 'verified', 'verified', 'paid', 'refunded']
            for jid, status in enumerate(stages, 1):
                db.execute(models.Job.__table__.insert().values(
                    id=jid, renter_id=4, reviewer_id=None if jid == 1 else 5,
                    address=f'DEMO sample property {jid}, Connaught Place, New Delhi',
                    geocoded_lat=28.632 + jid * .001, geocoded_lng=77.220,
                    checklist_json=CHECKLIST, price=None if jid == 1 else 150,
                    status=status, created_at=now - timedelta(minutes=jid),
                    accept_deadline=now + timedelta(hours=24), submit_deadline=now + timedelta(hours=48),
                    verified_at=now if jid >= 6 else None,
                    commission_rate=.15 if jid == 9 else None,
                ))
                if jid >= 2:
                    payment = 'released' if jid == 9 else 'refunded' if jid == 10 else 'held'
                    db.execute(models.Payment.__table__.insert().values(job_id=jid, amount=150, status=payment, refund_amount=150 if jid == 10 else None))
                if jid >= 3:
                    photo_ids = []
                    for number, (item, template) in enumerate(zip(CHECKLIST, names), 1):
                        name = f'demo-job-{jid}-item-{number}.png'
                        image_path = uploads / name
                        if image_path.is_symlink() or image_path.resolve().parent != uploads.resolve():
                            raise ValueError('Sample evidence must remain in demo uploads')
                        if not image_path.exists():
                            shutil.copyfile(uploads / template, image_path)
                        photo_ids.append(db.execute(models.Photo.__table__.insert().values(
                            job_id=jid, uploader_id=5, checklist_item=item, stored_name=name,
                            content_type='image/png', size_bytes=(uploads / name).stat().st_size,
                            created_at=now - timedelta(minutes=5),
                        )).inserted_primary_key[0])
                    if jid >= 4:
                        results = [{'item': item, 'addressed': True, 'passed': True, 'photo_check': 'no_photo', 'photo_observation': 'no photos', 'confidence': .9, 'reasoning': 'Precomputed demo fixture, not a live AI result.'} for item in CHECKLIST]
                        summary = summarize_node({'checklist': CHECKLIST, 'verification_result': results, 'photos': []})
                        complete = jid >= 6
                        db.execute(models.Report.__table__.insert().values(
                            job_id=jid, media_urls=[f'/photos/{pid}' for pid in photo_ids],
                            notes='DEMO simulated findings only. Walls: no cracks or damp patches reported. Taps: steady water flow and no leaks reported.',
                            ai_verification_result=results if complete else None,
                            ai_generated_summary='PRECOMPUTED DEMO RESULT. ' + summary['summary'] if complete else None,
                            check_score=100 if complete else None,
                        ))
                if jid >= 7:
                    review = 'awaiting_reupload' if jid == 7 else 'awaiting_human' if jid == 8 else 'approved' if jid == 9 else 'resolved_not_genuine'
                    values = dict(job_id=jid, status=review, rejected_items=[] if jid == 9 else [CHECKLIST[0]], fee_amount=0 if jid == 9 else 25,
                                  fee_status='none' if jid == 9 else 'refunded' if jid == 10 else 'held',
                                  human_fee_amount=75 if jid in (8, 10) else 0,
                                  human_fee_status='refunded' if jid == 10 else 'held' if jid == 8 else 'none',
                                  created_at=now, renter_reason=None if jid == 9 else 'DEMO: sample evidence requires review.')
                    if jid == 7:
                        values.update(reupload_deadline=now + timedelta(hours=24), ai_verdict={'all_genuine': False, 'items': []})
                    if jid == 8:
                        values.update(escalation_reason='DEMO case awaiting an administrator decision.')
                    if jid == 9:
                        values.update(decided_at=now)
                    if jid == 10:
                        values.update(human_decision='not_genuine', decided_by=1, decided_at=now,
                                      decision_notes='DEMO decision: placeholder is not inspection evidence.',
                                      appeal_by=5, appeal_reason='DEMO request for another review.', appealed_at=now, appeal_status='pending')
                    db.execute(models.PhotoReview.__table__.insert().values(**values))
            for uid, jid, event in [(4, 6, 'report.verified'), (5, 7, 'photo_review.awaiting_reupload'), (1, 8, 'photo_review.awaiting_human'), (1, 10, 'appeal.pending')]:
                db.execute(models.Notification.__table__.insert().values(user_id=uid, job_id=jid, event_key=f'demo:{uid}:{jid}', event_type=event, title='Demo inspection update', message=f'DEMO: sample job {jid} is ready for your attention.', is_read=False, created_at=now))
        with Session(engine) as db:
            backfill_ledger(db)
        with engine.connect() as db:
            assert db.exec_driver_sql('PRAGMA integrity_check').scalar_one() == 'ok'
            assert not db.exec_driver_sql('PRAGMA foreign_key_check').fetchall()
    finally:
        engine.dispose()
