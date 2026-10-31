import sqlite3
from datetime import timedelta

import pytest
from sqlalchemy import delete
from sqlalchemy.orm.exc import StaleDataError

from app.core.time import utcnow
from app.models import Job, JobStatus, Notification, Payment, PaymentStatus, PhotoReview, PhotoReviewStatus


def alerts(store, jid, event_type=None):
    with store() as db:
        query = db.query(Notification).filter_by(job_id=jid)
        if event_type:
            query = query.filter_by(event_type=event_type)
        return query.order_by(Notification.id).all()


def test_job_creation_notifies_renter_only(store, make_job):
    jid = make_job(status=JobStatus.requested, payment_status=None)
    rows = alerts(store, jid)
    assert len(rows) == 1
    assert rows[0].user_id == 4
    assert rows[0].event_type == 'job.requested'
    assert rows[0].is_read is False
    assert rows[0].job_id == jid
    assert 'Test property' not in rows[0].message


def test_acceptance_notifies_only_participants(client, headers, store, make_job):
    jid = make_job(status=JobStatus.requested, payment_status=None)
    assert client.post(f'/jobs/{jid}/accept', headers=headers(5)).status_code == 200
    rows = alerts(store, jid, 'job.accepted')
    assert {row.user_id for row in rows} == {4, 5}
    assert all(row.deadline_at is not None for row in rows)
    assert client.get('/notifications', headers=headers(6)).json()['total'] == 0


def test_verified_notification_has_review_deadline(store, make_job):
    from app.core.config import PHOTO_REVIEW_WINDOW_HOURS
    jid = make_job()
    rows = alerts(store, jid, 'job.verified')
    assert {row.user_id for row in rows} == {4, 5}
    with store() as db:
        expected = db.get(Job, jid).verified_at + timedelta(hours=PHOTO_REVIEW_WINDOW_HOURS)
    assert all(row.deadline_at == expected for row in rows)


@pytest.mark.parametrize('review_status', list(PhotoReviewStatus))
def test_each_photo_status_notifies_participants(store, make_job, review_status):
    jid = make_job(review_status=review_status)
    rows = alerts(store, jid, 'photo_review.' + review_status.value)
    expected = {1, 4, 5} if review_status == PhotoReviewStatus.awaiting_human else {4, 5}
    assert {row.user_id for row in rows} == expected
    assert len(rows) == len(expected)


def test_human_queue_alerts_all_admins(store, make_job):
    from app.models import User, UserRole
    with store() as db:
        db.add(User(id=8, phone='9000000008', role=UserRole.admin))
        db.commit()
    jid = make_job(review_status=PhotoReviewStatus.awaiting_human)
    assert {row.user_id for row in alerts(store, jid, 'photo_review.awaiting_human')} == {1, 4, 5, 8}


def test_approval_has_one_alert_per_participant(client, headers, store, make_job):
    jid = make_job()
    assert client.post(f'/jobs/{jid}/photo-review/approve', headers=headers(4)).status_code == 200
    assert len(alerts(store, jid, 'photo_review.approved')) == 2
    assert alerts(store, jid, 'job.paid') == []
    before = len(alerts(store, jid))
    assert client.post(f'/jobs/{jid}/photo-review/approve', headers=headers(4)).status_code == 400
    assert len(alerts(store, jid)) == before


def test_appeal_submission_and_decision_alerts(client, headers, store, make_job):
    jid = make_job(review_status=PhotoReviewStatus.awaiting_human)
    assert client.post(f'/admin/photo-reviews/{jid}/decide', headers=headers(1), json={'decision': 'not_genuine', 'notes': 'test'}).status_code == 200
    assert client.post(f'/jobs/{jid}/appeal', headers=headers(5), json={'reason': 'test'}).status_code == 200
    assert {row.user_id for row in alerts(store, jid, 'appeal.pending')} == {1, 4, 5}
    before_reversed = len(alerts(store, jid, 'photo_review.resolved_genuine'))
    assert client.post(f'/admin/appeals/{jid}/decide', headers=headers(1), json={'decision': 'overturn', 'notes': 'test'}).status_code == 200
    assert {row.user_id for row in alerts(store, jid, 'appeal.overturned')} == {4, 5}
    assert len(alerts(store, jid, 'photo_review.resolved_genuine')) == before_reversed
    assert alerts(store, jid, 'job.paid') == []


def test_upheld_appeal_notifications(client, headers, store, make_job):
    jid = make_job(review_status=PhotoReviewStatus.awaiting_human)
    assert client.post(f'/admin/photo-reviews/{jid}/decide', headers=headers(1), json={'decision': 'genuine', 'notes': 'test'}).status_code == 200
    assert client.post(f'/jobs/{jid}/appeal', headers=headers(4), json={'reason': 'test'}).status_code == 200
    assert client.post(f'/admin/appeals/{jid}/decide', headers=headers(1), json={'decision': 'uphold', 'notes': 'test'}).status_code == 200
    assert {row.user_id for row in alerts(store, jid, 'appeal.upheld')} == {4, 5}


def test_notification_apis_are_scoped_and_paginated(client, headers, store, make_job):
    jid = make_job()
    with store() as db:
        db.execute(delete(Notification))
        for user_id in (4, 5):
            for i in range(3):
                db.add(Notification(user_id=user_id, job_id=jid, event_key=f'test:{user_id}:{i}', event_type='test', title='Test', message='Test'))
        db.commit()
    response = client.get('/notifications?limit=2&offset=1', headers=headers(4))
    assert response.status_code == 200
    page = response.json()
    assert page['total'] == 3 and page['limit'] == 2 and page['offset'] == 1
    assert len(page['items']) == 2
    assert page['items'][0]['id'] > page['items'][1]['id']
    assert all('user_id' not in row and 'event_key' not in row for row in page['items'])
    assert client.get('/notifications/unread-count', headers=headers(4)).json() == {'unread_count': 3}
    assert client.get('/notifications', headers=headers(1)).json()['total'] == 0


def test_mark_one_is_idempotent_and_owner_only(client, headers, store, make_job):
    jid = make_job()
    own = next(row for row in alerts(store, jid) if row.user_id == 4)
    path = f'/notifications/{own.id}/read'
    assert client.post(path, headers=headers(5)).status_code == 404
    assert client.post(path, headers=headers(1)).status_code == 404
    response = client.post(path, headers=headers(4))
    assert response.status_code == 200
    first = response.json()
    assert first['is_read'] is True and first['read_at'] is not None
    assert client.post(path, headers=headers(4)).json()['read_at'] == first['read_at']
    assert client.get('/notifications/unread-count', headers=headers(4)).json()['unread_count'] == 0
    assert client.get('/notifications?unread_only=true', headers=headers(4)).json()['items'] == []
    assert client.post('/notifications/999999/read', headers=headers(4)).status_code == 404


def test_mark_all_only_changes_own_notifications(client, headers, store, make_job):
    jid = make_job()
    assert client.post('/notifications/read-all', headers=headers(4)).json() == {'marked_read': 1}
    assert client.post('/notifications/read-all', headers=headers(4)).json() == {'marked_read': 0}
    assert client.get('/notifications/unread-count', headers=headers(5)).json()['unread_count'] == 1
    with store() as db:
        before = db.get(Job, jid).version_id
    assert client.post('/notifications/read-all', headers=headers(5)).json() == {'marked_read': 1}
    with store() as db:
        assert db.get(Job, jid).version_id == before
    assert len(alerts(store, jid)) == 2


@pytest.mark.parametrize('method,path', [('get', '/notifications'), ('get', '/notifications/unread-count'), ('post', '/notifications/read-all'), ('post', '/notifications/1/read')])
def test_authentication_required(client, method, path):
    assert getattr(client, method)(path).status_code == 401


@pytest.mark.parametrize('query', ['limit=0', 'limit=101', 'offset=-1'])
def test_bad_pagination_rejected(client, headers, query):
    assert client.get('/notifications?' + query, headers=headers(4)).status_code == 422


def test_failed_transaction_does_not_leave_notifications(store, make_job):
    jid = make_job()
    before = len(alerts(store, jid))
    with store() as db:
        db.get(Job, jid).status = JobStatus.needs_reupload
        db.flush()
        db.flush()
        assert db.query(Notification).filter_by(job_id=jid).count() == before + 2
        db.rollback()
        # The same session must not leak the discarded event into another commit.
        db.get(Job, jid).address = 'Updated test address'
        db.commit()
    assert len(alerts(store, jid)) == before


def test_stale_request_produces_no_alerts(store, make_job):
    jid = make_job(status=JobStatus.requested, payment_status=None)
    with store() as first, store() as second:
        winner, loser = first.get(Job, jid), second.get(Job, jid)
        winner.reviewer_id, winner.status = 5, JobStatus.accepted
        first.add(Payment(job_id=jid, amount=100, status=PaymentStatus.held))
        first.commit()
        loser.reviewer_id, loser.status = 6, JobStatus.accepted
        second.add(Payment(job_id=jid, amount=100, status=PaymentStatus.held))
        with pytest.raises(StaleDataError):
            second.commit()
        second.rollback()
    rows = alerts(store, jid, 'job.accepted')
    assert len(rows) == 2 and {row.user_id for row in rows} == {4, 5}


def test_repeated_flush_does_not_duplicate_notifications(store, make_job):
    jid = make_job()
    before = len(alerts(store, jid))
    with store() as db:
        db.get(Job, jid).status = JobStatus.needs_reupload
        db.flush()
        db.flush()
        db.flush()
        db.commit()
    assert len(alerts(store, jid)) == before + 2


def test_scheduler_notifications_written_once(store, make_job):
    from app.services.scheduler import run_sweep
    jid = make_job()
    with store() as db:
        db.get(Job, jid).verified_at = utcnow() - timedelta(days=3)
        db.commit()
    assert run_sweep()['changed'] == 1
    assert run_sweep()['changed'] == 0
    assert len(alerts(store, jid, 'photo_review.auto_approved')) == 2
    assert alerts(store, jid, 'job.paid') == []


def test_no_alert_for_accounting_or_unrelated_job_edit(store, make_job):
    jid = make_job()
    before = len(alerts(store, jid))
    with store() as db:
        db.get(Job, jid).address = 'Changed address'
        db.commit()
    assert len(alerts(store, jid)) == before


def test_empty_notification_list(client, headers):
    assert client.get('/notifications', headers=headers(4)).json() == {'items': [], 'total': 0, 'limit': 20, 'offset': 0}
    assert client.get('/notifications/unread-count', headers=headers(4)).json() == {'unread_count': 0}
    assert client.post('/notifications/read-all', headers=headers(4)).json() == {'marked_read': 0}


def test_migration_is_safe_to_repeat_and_preserves_read_state(tmp_path):
    from migrate_notifications import migrate
    path = tmp_path / 'existing.db'
    with sqlite3.connect(path) as db:
        db.executescript('CREATE TABLE users(id INTEGER PRIMARY KEY); CREATE TABLE jobs(id INTEGER PRIMARY KEY);')
    migrate(path)
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO notifications(user_id, job_id, event_key, event_type, title, message, is_read) VALUES (4, 1, 'test', 'test', 'Test', 'Test', 1)")
        db.commit()
    migrate(path)
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT COUNT(*), MIN(is_read) FROM notifications').fetchone() == (1, 1)
    assert len(list(tmp_path.glob('*.before_notifications_*.db'))) == 1
