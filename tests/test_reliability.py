import math
import sqlite3
from datetime import timedelta
from types import SimpleNamespace

import jwt
import pytest
from pydantic import ValidationError
from sqlalchemy.orm.exc import StaleDataError

from app.core import database
from app.core.config import JWT_SECRET, JWT_ALGORITHM
from app.core.time import utcnow
from app.models import Job, JobStatus, Payment, PaymentStatus, PhotoReview, PhotoReviewStatus, FeeStatus, ReviewerProfile, Report, OtpCode, LedgerEntry
from app.schemas.job import JobCreate
from app.schemas.photo_review import RejectRequest, DisputeAIResultRequest
from app.schemas.dispute import DisputeResolve
from app.services import verification_nodes as nodes
from app.services.money import to_paise, same_amount


@pytest.mark.parametrize('items', [[], [' '], ['AC', 'ac'], ['AC', ' AC '], [None]])
def test_invalid_job_checklist(items):
    with pytest.raises(ValidationError):
        JobCreate(address='Test', checklist=items)


def test_valid_checklist():
    assert JobCreate(address=' Test ', checklist=[' AC ', 'Fire']).model_dump() == {'address': 'Test', 'checklist': ['AC', 'Fire']}


@pytest.mark.parametrize('value', [-1, math.nan, math.inf, -math.inf])
def test_invalid_money_inputs(value):
    for schema, data in [
        (RejectRequest, {'items': ['AC'], 'confirm_fee': value}),
        (DisputeAIResultRequest, {'confirm_fee': value}),
        (DisputeResolve, {'outcome': 'partial', 'notes': 'test', 'refund_amount': value}),
    ]:
        with pytest.raises(ValidationError):
            schema(**data)
    with pytest.raises(ValueError):
        to_paise(value)


def test_decimal_rounding_and_exact_confirmation():
    assert to_paise('1.005') == 101
    assert to_paise('103.31') == 10331
    assert same_amount(25, 25.0)
    assert not same_amount(25.0001, 25)
    assert not same_amount(math.nan, 25)


def test_http_invalid_job_before_geocoding(client, headers):
    response = client.post('/jobs/', headers=headers(4), json={'address': 'Test', 'checklist': []})
    assert response.status_code == 422


def test_role_and_photo_access(client, headers, make_job):
    jid = make_job()
    assert client.post(f'/jobs/{jid}/accept', headers=headers(4)).status_code == 403
    assert client.get(f'/jobs/{jid}', headers=headers(7)).status_code == 403
    assert client.get(f'/jobs/{jid}').status_code == 401


@pytest.mark.parametrize('claims', [{}, {'sub': 'not-a-number'}, {'sub': '-1'}])
def test_bad_jwt_subject_is_401(client, claims):
    token = jwt.encode({'exp': utcnow() + timedelta(minutes=5), **claims}, JWT_SECRET, algorithm=JWT_ALGORITHM)
    assert client.get('/auth/me', headers={'Authorization': 'Bearer ' + token}).status_code == 401


def test_legacy_release_blocked(client, headers, make_job, store):
    jid = make_job(review_status=PhotoReviewStatus.awaiting_human)
    with store() as db:
        pid = db.query(Payment).filter_by(job_id=jid).one().id
    for uid in (4, 1):
        assert client.post(f'/payments/{pid}/release', headers=headers(uid)).status_code == 409
    with store() as db:
        assert db.get(Payment, pid).status == PaymentStatus.held


@pytest.mark.parametrize('status', [None, *PhotoReviewStatus])
def test_legacy_dispute_cannot_interrupt_photo_review(client, headers, make_job, status):
    jid = make_job(review_status=status)
    assert client.post('/disputes/', headers=headers(4), json={'job_id': jid, 'reason': 'test'}).status_code == 409


def test_real_approval_ledger_and_repeat(client, headers, make_job, store):
    jid = make_job()
    assert client.post(f'/jobs/{jid}/photo-review/approve', headers=headers(4)).status_code == 200
    assert client.post(f'/jobs/{jid}/photo-review/approve', headers=headers(4)).status_code == 400
    with store() as db:
        assert db.get(Job, jid).status == JobStatus.paid
        assert db.query(Payment).filter_by(job_id=jid).one().status == PaymentStatus.released
        entries = db.query(LedgerEntry).filter_by(job_id=jid).all()
        assert sum(e.amount_paise for e in entries if e.kind == 'payout') == 8500
        assert sum(e.amount_paise for e in entries if e.kind == 'commission') == 1500
        assert db.query(ReviewerProfile).filter_by(user_id=5).one().jobs_completed == 1
    response = client.get('/admin/ledger/summary', headers=headers(1))
    assert response.status_code == 200
    assert response.json()['balanced'] is True


@pytest.mark.parametrize('payment_status', [None, PaymentStatus.refunded, PaymentStatus.released])
def test_cannot_pay_without_held_payment(client, headers, make_job, store, payment_status):
    jid = make_job(payment_status=payment_status)
    assert client.post(f'/jobs/{jid}/photo-review/approve', headers=headers(4)).status_code == 409
    with store() as db:
        assert db.get(Job, jid).status == JobStatus.verified
        assert db.query(PhotoReview).filter_by(job_id=jid).count() == 0


def test_stale_acceptance_rolls_back_payment_and_ledger(make_job, store):
    jid = make_job(status=JobStatus.requested, payment_status=None)
    with store() as first, store() as second:
        a, b = first.get(Job, jid), second.get(Job, jid)
        a.reviewer_id, a.status = 5, JobStatus.accepted
        first.add(Payment(job_id=jid, amount=100, status=PaymentStatus.held))
        first.commit()
        b.reviewer_id, b.status = 6, JobStatus.accepted
        second.add(Payment(job_id=jid, amount=100, status=PaymentStatus.held))
        with pytest.raises(StaleDataError):
            second.commit()
        second.rollback()
    with store() as db:
        assert db.get(Job, jid).reviewer_id == 5
        assert db.query(Payment).filter_by(job_id=jid).count() == 1
        assert db.query(LedgerEntry).filter_by(job_id=jid, kind='price_held').count() == 1


def test_accept_endpoint_and_repeat(client, headers, make_job, store):
    jid = make_job(status=JobStatus.requested, payment_status=None)
    assert client.post(f'/jobs/{jid}/accept', headers=headers(5)).status_code == 200
    assert client.post(f'/jobs/{jid}/accept', headers=headers(6)).status_code == 400
    with store() as db:
        assert db.get(Job, jid).reviewer_id == 5
        assert db.query(Payment).filter_by(job_id=jid).count() == 1


def test_child_only_review_changes_detect_conflict(make_job, store):
    jid = make_job(review_status=PhotoReviewStatus.ai_checked_genuine)
    with store() as first, store() as second:
        first.get(Job, jid)
        old_job = second.get(Job, jid)
        a = first.query(PhotoReview).filter_by(job_id=jid).one()
        b = second.query(PhotoReview).filter_by(job_id=jid).one()
        a.status = PhotoReviewStatus.awaiting_human
        first.commit()
        b.status = PhotoReviewStatus.accepted_ai_result
        with pytest.raises(StaleDataError):
            second.commit()
        second.rollback()
    with store() as db:
        assert db.query(PhotoReview).filter_by(job_id=jid).one().status == PhotoReviewStatus.awaiting_human


def test_otp_cannot_be_consumed_twice(store):
    with store() as db:
        otp = OtpCode(phone='9000000004', code_hash='test', expires_at=utcnow() + timedelta(minutes=5))
        db.add(otp)
        db.commit()
        oid = otp.id
    with store() as first, store() as second:
        a, b = first.get(OtpCode, oid), second.get(OtpCode, oid)
        a.used = True
        first.commit()
        b.used = True
        with pytest.raises(StaleDataError):
            second.commit()
        second.rollback()


def test_conflict_becomes_http_409(client, headers, make_job, store, monkeypatch):
    from app.routers import job as routes
    original = routes.calculate_price
    jid = make_job(status=JobStatus.requested, payment_status=None)
    def rival(distance):
        with store() as db:
            job = db.get(Job, jid)
            job.reviewer_id, job.status = 6, JobStatus.accepted
            db.add(Payment(job_id=jid, amount=100, status=PaymentStatus.held))
            db.commit()
        return original(distance)
    monkeypatch.setattr(routes, 'calculate_price', rival)
    assert client.post(f'/jobs/{jid}/accept', headers=headers(5)).status_code == 409
    with store() as db:
        assert db.get(Job, jid).reviewer_id == 6
        assert db.query(Payment).filter_by(job_id=jid).count() == 1


@pytest.mark.parametrize('names', [[], ['AC working'], ['AC working', 'AC working'], ['AC working', 'Unknown']])
def test_invalid_ai_result_coverage(names):
    with pytest.raises(nodes.InvalidVerificationResult):
        nodes._validated_results(['AC working', 'Fire extinguisher'], [{'item': name} for name in names])


def test_verification_failure_retry(client, headers, make_job, store, monkeypatch):
    from app.routers import report as routes
    jid = make_job(status=JobStatus.report_submitted)
    with store() as db:
        report = Report(job_id=jid, notes='Test notes')
        db.add(report)
        db.commit()
        rid = report.id
    routes.verification_graph.invoke.side_effect = nodes.InvalidVerificationResult('incomplete')
    assert client.post(f'/reports/{rid}/verify', headers=headers(4)).status_code == 502
    with store() as db:
        assert db.get(Job, jid).status == JobStatus.report_submitted
        assert db.get(Report, rid).check_score is None
    routes.verification_graph.invoke.side_effect = None
    routes.verification_graph.invoke.return_value = {
        'verification_result': [
            {'item': 'AC working', 'addressed': True, 'passed': True},
            {'item': 'Fire extinguisher', 'addressed': True, 'passed': False},
        ], 'summary': 'Mock summary', 'check_score': 50,
        'all_addressed': True,
    }
    assert client.post(f'/reports/{rid}/verify', headers=headers(4)).status_code == 200
    assert routes.verification_graph.invoke.call_args.args[0]['photos'] == []


def test_scheduler_pays_once_and_ledger_balances(client, headers, make_job, store):
    from app.services.scheduler import run_sweep
    jid = make_job()
    with store() as db:
        db.get(Job, jid).verified_at = utcnow() - timedelta(days=3)
        db.commit()
    assert run_sweep()['changed'] == 1
    assert run_sweep()['changed'] == 0
    assert client.get('/admin/ledger/summary', headers=headers(1)).json()['balanced'] is True
    with store() as db:
        assert db.query(ReviewerProfile).filter_by(user_id=5).one().jobs_completed == 1


def test_human_decision_and_overturn(client, headers, make_job, store):
    jid = make_job(review_status=PhotoReviewStatus.awaiting_human)
    body = {'decision': 'not_genuine', 'notes': 'Test human decision'}
    assert client.post(f'/admin/photo-reviews/{jid}/decide', headers=headers(1), json=body).status_code == 200
    assert client.post(f'/jobs/{jid}/appeal', headers=headers(5), json={'reason': 'Test appeal'}).status_code == 200
    response = client.post(f'/admin/appeals/{jid}/decide', headers=headers(1), json={'decision': 'overturn', 'notes': 'Test reversal'})
    assert response.status_code == 200
    with store() as db:
        assert db.get(Job, jid).status == JobStatus.paid
        profile = db.query(ReviewerProfile).filter_by(user_id=5).one()
        assert profile.strikes == 0
        assert profile.jobs_completed == 1
    assert client.get('/admin/ledger/summary', headers=headers(1)).json()['balanced'] is True


def test_paid_reversal_undoes_completion(client, headers, make_job, store):
    jid = make_job(review_status=PhotoReviewStatus.awaiting_human)
    assert client.post(f'/admin/photo-reviews/{jid}/decide', headers=headers(1), json={'decision': 'genuine', 'notes': 'test'}).status_code == 200
    assert client.post(f'/jobs/{jid}/appeal', headers=headers(4), json={'reason': 'test'}).status_code == 200
    assert client.post(f'/admin/appeals/{jid}/decide', headers=headers(1), json={'decision': 'overturn', 'notes': 'test'}).status_code == 200
    with store() as db:
        assert db.get(Job, jid).status == JobStatus.refunded
        assert db.query(ReviewerProfile).filter_by(user_id=5).one().jobs_completed == 0
    assert client.get('/admin/ledger/summary', headers=headers(1)).json()['balanced'] is True


def test_ledger_entries_cannot_be_edited_or_deleted(make_job, store):
    jid = make_job()
    for operation in ('edit', 'delete'):
        with store() as db:
            entry = db.query(LedgerEntry).filter_by(job_id=jid).first()
            if operation == 'edit':
                entry.amount_paise = 1
            else:
                db.delete(entry)
            with pytest.raises(ValueError, match='append-only'):
                db.commit()
            db.rollback()


def test_support_cannot_attach_foreign_job(client, headers, make_job):
    jid = make_job()
    assert client.post('/support/chat', headers=headers(7), json={'job_id': jid, 'message': 'Help'}).status_code == 404


def test_migration_is_idempotent_and_preserves_rows(tmp_path):
    from migrate_reliability import migrate
    path = tmp_path / 'old.db'
    with sqlite3.connect(path) as db:
        db.executescript('''CREATE TABLE jobs(id INTEGER PRIMARY KEY, reviewer_id INTEGER, status TEXT);
            CREATE TABLE reviewer_profiles(id INTEGER PRIMARY KEY, user_id INTEGER, jobs_completed INTEGER);
            CREATE TABLE otp_codes(id INTEGER PRIMARY KEY);
            INSERT INTO jobs VALUES(1, 5, 'paid');
            INSERT INTO reviewer_profiles VALUES(1, 5, 0);''')
    migrate(path)
    migrate(path)
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT version_id FROM jobs').fetchone()[0] == 1
        assert db.execute('SELECT jobs_completed FROM reviewer_profiles').fetchone()[0] == 1
    assert len(list(tmp_path.glob('*.before_reliability_*.db'))) == 1


def test_photo_upload_download_and_delete(client, headers, make_job, store, monkeypatch, tmp_path):
    import io
    from PIL import Image
    from app.routers import photo as routes
    from app.models import Photo
    monkeypatch.setattr(routes, 'UPLOAD_DIR', tmp_path)
    jid = make_job(status=JobStatus.visited)
    buffer = io.BytesIO()
    Image.new('RGB', (8, 8), 'grey').save(buffer, format='JPEG')
    photo = buffer.getvalue()
    response = client.post(f'/jobs/{jid}/photos', headers=headers(5), data={'checklist_item': 'AC working'}, files={'file': ('test.jpg', photo, 'image/jpeg')})
    assert response.status_code == 200
    pid = response.json()['id']
    response = client.get(f'/photos/{pid}', headers=headers(4))
    assert response.status_code == 200
    assert response.content == photo
    assert client.get(f'/photos/{pid}', headers=headers(7)).status_code == 403
    assert client.delete(f'/photos/{pid}', headers=headers(5)).status_code == 200
    assert list(tmp_path.iterdir()) == []
    with store() as db:
        assert db.get(Photo, pid) is None


@pytest.mark.parametrize('action', ['upload', 'delete'])
def test_photo_files_survive_failed_transaction(client, headers, make_job, store, monkeypatch, tmp_path, action):
    import io
    from PIL import Image
    from app.routers import photo as routes
    from app.models import Photo
    from sqlalchemy.orm import Session
    monkeypatch.setattr(routes, 'UPLOAD_DIR', tmp_path)
    jid = make_job(status=JobStatus.visited)
    buffer = io.BytesIO()
    Image.new('RGB', (8, 8), 'grey').save(buffer, format='JPEG')
    data = buffer.getvalue()
    if action == 'delete':
        (tmp_path / 'original.jpg').write_bytes(data)
        with store() as db:
            photo = Photo(job_id=jid, uploader_id=5, checklist_item='AC working', stored_name='original.jpg', content_type='image/jpeg', size_bytes=len(data))
            db.add(photo)
            db.commit()
            pid = photo.id
    def conflict(self):
        raise StaleDataError('Test concurrent write')
    monkeypatch.setattr(Session, 'commit', conflict)
    if action == 'upload':
        response = client.post(f'/jobs/{jid}/photos', headers=headers(5), data={'checklist_item': 'AC working'}, files={'file': ('test.jpg', data, 'image/jpeg')})
        assert response.status_code == 409
        assert list(tmp_path.iterdir()) == []
    else:
        assert client.delete(f'/photos/{pid}', headers=headers(5)).status_code == 409
        assert (tmp_path / 'original.jpg').read_bytes() == data
        with store() as db:
            assert db.get(Photo, pid) is not None


def test_ai_confidence_and_flags_are_validated():
    from app.services.verification_state import ChecklistItemResult
    data = {'item': 'AC', 'addressed': True, 'passed': True, 'confidence': .9, 'reasoning': 'test'}
    for value in (-.1, 1.1, math.nan, math.inf):
        with pytest.raises(ValidationError):
            ChecklistItemResult(**{**data, 'confidence': value})
    with pytest.raises(ValidationError):
        ChecklistItemResult(**{**data, 'addressed': False})


def test_fee_confirmation_cannot_use_nan(client, headers, make_job):
    jid = make_job()
    for value in ('NaN', 'Infinity', '-Infinity'):
        response = client.post(f'/jobs/{jid}/photo-review/reject', headers=headers(4), json={'items': ['AC working'], 'confirm_fee': value})
        assert response.status_code == 422


@pytest.mark.parametrize('refund', [-1, 100.01, 'NaN', 'Infinity'])
def test_legacy_refund_cannot_exceed_payment(client, headers, make_job, store, refund):
    from app.models import Dispute, DisputeStatus
    jid = make_job(status=JobStatus.disputed, payment_status=PaymentStatus.released)
    with store() as db:
        case = Dispute(job_id=jid, renter_id=4, reason='test', status=DisputeStatus.escalated)
        db.add(case)
        db.commit()
        did = case.id
    response = client.post(f'/disputes/{did}/resolve', headers=headers(1), json={'outcome': 'partial', 'notes': 'test', 'refund_amount': refund})
    assert response.status_code in (400, 422)
    with store() as db:
        assert db.query(Payment).filter_by(job_id=jid).one().status == PaymentStatus.released
        assert db.get(Dispute, did).status == DisputeStatus.escalated


def test_legacy_triage_cannot_move_money(client, headers, make_job, store):
    from app.models import Dispute, DisputeStatus
    from app.routers import dispute as routes
    jid = make_job(status=JobStatus.disputed, payment_status=PaymentStatus.released)
    with store() as db:
        case = Dispute(job_id=jid, renter_id=4, reason='test', status=DisputeStatus.open)
        db.add(case)
        db.add(Report(job_id=jid, notes='test'))
        db.commit()
        did = case.id
    routes.dispute_graph.invoke.side_effect = None
    routes.dispute_graph.invoke.return_value = {'recommended_outcome': 'refund', 'confidence': 1.0, 'reasoning': 'test'}
    assert client.post(f'/disputes/{did}/triage', headers=headers(4)).status_code == 200
    with store() as db:
        assert db.get(Dispute, did).status == DisputeStatus.escalated
        assert db.query(Payment).filter_by(job_id=jid).one().status == PaymentStatus.released


def test_concurrent_appeal_decisions_cannot_both_win(make_job, store):
    jid = make_job(review_status=PhotoReviewStatus.resolved_genuine, payment_status=PaymentStatus.released)
    with store() as db:
        job = db.get(Job, jid)
        job.status = JobStatus.paid
        review = db.query(PhotoReview).filter_by(job_id=jid).one()
        review.appeal_status = 'pending'
        db.commit()
    with store() as first, store() as second:
        first_job, second_job = first.get(Job, jid), second.get(Job, jid)
        a = first.query(PhotoReview).filter_by(job_id=jid).one()
        b = second.query(PhotoReview).filter_by(job_id=jid).one()
        a.appeal_status = 'upheld'
        first.commit()
        b.appeal_status = 'overturned'
        second_job.status = JobStatus.refunded
        second.query(Payment).filter_by(job_id=jid).one().status = PaymentStatus.refunded
        with pytest.raises(StaleDataError):
            second.commit()
        second.rollback()
    with store() as db:
        assert db.query(PhotoReview).filter_by(job_id=jid).one().appeal_status == 'upheld'
        assert db.get(Job, jid).status == JobStatus.paid


def test_backfill_cannot_duplicate_entries(client, headers, make_job, store):
    jid = make_job()
    with store() as db:
        initial = db.query(LedgerEntry).filter_by(job_id=jid).count()
    for _ in range(2):
        assert client.post('/admin/ledger/backfill', headers=headers(1)).json()['entries_added'] == 0
    with store() as db:
        assert db.query(LedgerEntry).filter_by(job_id=jid).count() == initial


@pytest.mark.parametrize('review_status,deadline_field,expected', [
    (PhotoReviewStatus.ai_checked_genuine, 'ai_result_deadline', PhotoReviewStatus.auto_accepted_ai_result),
    (PhotoReviewStatus.awaiting_renter_recheck, 'recheck_deadline', PhotoReviewStatus.auto_approved_after_reupload),
    (PhotoReviewStatus.awaiting_reupload, 'reupload_deadline', PhotoReviewStatus.awaiting_human),
])
def test_photo_deadline_paths(client, headers, make_job, store, review_status, deadline_field, expected):
    from app.services.scheduler import run_sweep
    jid = make_job(review_status=review_status)
    with store() as db:
        review = db.query(PhotoReview).filter_by(job_id=jid).one()
        setattr(review, deadline_field, utcnow() - timedelta(minutes=1))
        db.commit()
    assert run_sweep()['changed'] == 1
    assert run_sweep()['changed'] == 0
    with store() as db:
        review = db.query(PhotoReview).filter_by(job_id=jid).one()
        assert review.status == expected
        profile = db.query(ReviewerProfile).filter_by(user_id=5).one()
        assert profile.strikes == 0
        if expected == PhotoReviewStatus.awaiting_human:
            assert db.get(Job, jid).status == JobStatus.verified
            assert profile.jobs_completed == 0
        else:
            assert db.get(Job, jid).status == JobStatus.paid
            assert profile.jobs_completed == 1
    assert client.get('/admin/ledger/summary', headers=headers(1)).json()['balanced'] is True


@pytest.mark.parametrize('status', [JobStatus.accepted, JobStatus.visited, JobStatus.needs_reupload])
def test_submit_expiry_refunds_once(client, headers, make_job, store, status):
    from app.services.scheduler import run_sweep
    jid = make_job(status=status)
    with store() as db:
        db.get(Job, jid).submit_deadline = utcnow() - timedelta(seconds=1)
        db.commit()
    assert run_sweep()['changed'] == 1
    assert run_sweep()['changed'] == 0
    with store() as db:
        assert db.get(Job, jid).status == JobStatus.expired
        assert db.query(Payment).filter_by(job_id=jid).one().status == PaymentStatus.refunded
    assert client.get('/admin/ledger/summary', headers=headers(1)).json()['balanced'] is True


def test_failed_human_decision_does_not_add_strike(client, headers, make_job, store):
    jid = make_job(review_status=PhotoReviewStatus.awaiting_human, payment_status=None)
    response = client.post(f'/admin/photo-reviews/{jid}/decide', headers=headers(1), json={'decision': 'not_genuine', 'notes': 'test'})
    assert response.status_code == 409
    with store() as db:
        assert db.query(ReviewerProfile).filter_by(user_id=5).one().strikes == 0
        assert db.get(Job, jid).status == JobStatus.verified


def test_ratings_commit_with_average(client, headers, make_job, store):
    jid = make_job()
    assert client.post(f'/jobs/{jid}/photo-review/approve', headers=headers(4)).status_code == 200
    response = client.post('/ratings/', headers=headers(4), json={'job_id': jid, 'score': 4, 'comment': 'test'})
    assert response.status_code == 200
    assert client.post('/ratings/', headers=headers(4), json={'job_id': jid, 'score': 1}).status_code == 400
    with store() as db:
        assert db.query(ReviewerProfile).filter_by(user_id=5).one().rating_avg == 4.0


def test_real_graph_valid_and_incomplete_results(monkeypatch):
    from app.services.verification_graph import verification_graph
    from app.services.verification_state import VerificationOutput
    row = {'item': 'AC working', 'addressed': True, 'passed': False, 'confidence': .9, 'reasoning': 'AC is absent'}
    nodes.structured_llm.invoke.side_effect = None
    nodes.llm.invoke.side_effect = None
    nodes.llm.invoke.return_value = SimpleNamespace(content='Mock summary')
    nodes.structured_llm.invoke.return_value = VerificationOutput(results=[row])
    state = {'job_id': 1, 'checklist': ['AC working'], 'photos': [], 'notes': 'No AC', 'verification_result': [], 'all_addressed': False, 'check_score': 0, 'summary': ''}
    result = verification_graph.invoke(state)
    assert result['all_addressed'] is True
    assert result['check_score'] == 0
    nodes.structured_llm.invoke.return_value = VerificationOutput(results=[{**row, 'addressed': False}])
    assert verification_graph.invoke(state)['all_addressed'] is False
