import pytest

from app.models import Job, JobStatus, ReviewerProfile, User
from tests.helpers import Inspection


@pytest.mark.smoke
def test_admin_case_and_appeal_queues(client, headers, store, monkeypatch):
    flow = Inspection(client, headers, store, monkeypatch).start()
    flow.reject()
    flow.dispute_ai()
    queue = flow.call('GET', '/admin/photo-reviews', uid=1)
    assert [row['job_id'] for row in queue] == [flow.job_id]
    assert queue[0]['fee_amount'] == 25 and queue[0]['human_fee_amount'] == 75
    detail = flow.call('GET', f'/admin/photo-reviews/{flow.job_id}', uid=1)
    assert detail['report_notes'] == 'AC working. No fire extinguisher found.'
    assert len(detail['photos']) == 2 and detail['reviewer_strikes'] == 0
    flow.decide('genuine')
    assert flow.call('GET', '/admin/photo-reviews', uid=1) == []
    flow.call('POST', f'/jobs/{flow.job_id}/appeal', json={'reason': 'Please reconsider'})
    appeals = flow.call('GET', '/admin/appeals', uid=1)
    assert len(appeals) == 1 and appeals[0]['job_id'] == flow.job_id
    case = flow.call('GET', f'/admin/appeals/{flow.job_id}', uid=1)
    assert case['appeal_status'] == 'pending' and case['appeal_by'] == 4
    flow.call('POST', f'/admin/appeals/{flow.job_id}/decide', uid=1, json={'decision': 'uphold', 'notes': 'Original decision stands'})
    assert flow.call('GET', '/admin/appeals', uid=1) == []
    assert flow.call('GET', '/admin/appeals?status=upheld', uid=1)[0]['job_id'] == flow.job_id


@pytest.mark.smoke
def test_personal_and_job_ledger_endpoints_are_scoped(client, headers, store, monkeypatch):
    flow = Inspection(client, headers, store, monkeypatch).start()
    before = flow.call('GET', f'/admin/ledger/jobs/{flow.job_id}', uid=1)
    assert before['escrow_balance'] == 100 and before['settled'] is False
    flow.call('POST', f'/jobs/{flow.job_id}/photo-review/approve')
    assert flow.call('GET', '/ledger/me')['net'] == -100
    assert flow.call('GET', '/ledger/me', uid=5)['net'] == 85
    assert flow.call('GET', '/ledger/me', uid=7)['entries'] == []
    assert client.get('/ledger/me', headers=headers(1)).status_code == 403
    after = flow.call('GET', f'/admin/ledger/jobs/{flow.job_id}', uid=1)
    assert after['escrow_balance'] == 0 and after['settled'] is True
    assert client.get(f'/admin/ledger/jobs/{flow.job_id}', headers=headers(4)).status_code == 403


@pytest.mark.parametrize('path', ['/admin/photo-reviews', '/admin/photo-reviews/1', '/admin/appeals', '/admin/appeals/1', '/admin/reviewers/suspended', '/admin/scheduler/status'])
def test_admin_queue_reads_reject_non_admin(client, headers, path):
    assert client.get(path, headers=headers(4)).status_code == 403


@pytest.mark.parametrize('action,uid,body', [
    ('approve', 7, None),
    ('reject', 7, {'items': ['AC working'], 'confirm_fee': 25}),
    ('accept-ai-result', 7, None),
    ('dispute-ai-result', 7, {'reason': 'Not my case', 'confirm_fee': 75}),
    ('reupload-complete', 6, None),
    ('recheck/approve', 7, None),
    ('recheck/reject', 7, {'reason': 'Not my case'}),
])
def test_nonparticipants_cannot_change_photo_review(client, headers, store, monkeypatch, action, uid, body):
    flow = Inspection(client, headers, store, monkeypatch).start()
    response = client.post(f'/jobs/{flow.job_id}/photo-review/{action}', headers=headers(uid), json=body)
    assert response.status_code == 403
    assert flow.review() is None
    flow.balances(-10000, 0, 0, 10000)


def test_scheduler_status_and_manual_trigger(client, headers):
    before = client.get('/admin/scheduler/status', headers=headers(1)).json()
    response = client.post('/admin/scheduler/run', headers=headers(1))
    assert response.status_code == 200
    assert response.json() == {'checked': 0, 'changed': 0, 'errors': 0}
    after = client.get('/admin/scheduler/status', headers=headers(1)).json()
    assert after['total_sweeps'] == before['total_sweeps'] + 1
    assert after['last_run_at'] is not None
    assert client.post('/admin/scheduler/run', headers=headers(5)).status_code == 403


def test_ratings_read_and_duplicate_rules(client, headers, store, monkeypatch):
    flow = Inspection(client, headers, store, monkeypatch).start()
    assert client.post('/ratings/', headers=headers(4), json={'job_id': flow.job_id, 'score': 5}).status_code == 400
    flow.call('POST', f'/jobs/{flow.job_id}/photo-review/approve')
    result = flow.call('POST', '/ratings/', json={'job_id': flow.job_id, 'score': 5, 'comment': 'Test inspection rating'})
    assert flow.call('GET', f'/ratings/{result["id"]}')['score'] == 5
    assert client.get(f'/ratings/{result["id"]}').status_code == 401
    assert client.post('/ratings/', headers=headers(4), json={'job_id': flow.job_id, 'score': 1}).status_code == 400
    assert client.post('/ratings/', headers=headers(7), json={'job_id': flow.job_id, 'score': 1}).status_code == 403


def test_new_reviewer_can_create_location_profile(client, store, monkeypatch):
    from app.routers import reviewer_profile
    phone = '9000000066'
    otp = client.post('/auth/request-otp', json={'phone': phone}).json()['dev_otp']
    response = client.post('/auth/verify-otp', json={'phone': phone, 'code': otp, 'role': 'reviewer'})
    assert response.status_code == 200
    user_id = response.json()['user']['id']
    auth = {'Authorization': 'Bearer ' + response.json()['access_token']}
    monkeypatch.setattr(reviewer_profile, 'geocode_address', lambda value: {'lat': 12.97, 'lng': 77.59})
    response = client.post(f'/reviewers/{user_id}/location', headers=auth, json={'address': 'Test reviewer home'})
    assert response.status_code == 200
    assert response.json()['home_lat'] == 12.97
    with store() as db:
        assert db.query(ReviewerProfile).filter_by(user_id=user_id).count() == 1


def test_open_jobs_nearest_first_and_distance_filter(client, headers, make_job, store):
    near = make_job(status=JobStatus.requested, payment_status=None)
    far = make_job(status=JobStatus.requested, payment_status=None)
    with store() as db:
        db.get(Job, near).geocoded_lat = 12.98
        db.get(Job, far).geocoded_lat = 13.17
        db.commit()
    rows = client.get('/jobs/open', headers=headers(5)).json()
    assert [row['id'] for row in rows] == [near, far]
    assert rows[0]['distance_km'] < rows[1]['distance_km']
    limited = client.get('/jobs/open?max_distance_km=2&limit=1', headers=headers(5)).json()
    assert [row['id'] for row in limited] == [near]


def test_unresolvable_address_does_not_create_job(client, headers, store, monkeypatch):
    from app.routers import job
    monkeypatch.setattr(job, 'geocode_address', lambda value: None)
    response = client.post('/jobs/', headers=headers(4), json={'address': 'Unresolvable test address', 'checklist': ['AC working']})
    assert response.status_code == 400
    with store() as db:
        assert db.query(Job).count() == 0
