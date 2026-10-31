from datetime import timedelta

import pytest

from app.core.time import utcnow
from app.models import Job, JobStatus, Payment, Photo, PhotoReview, Report
from tests.helpers import CHECKLIST, Inspection, image_bytes


@pytest.fixture
def flow(client, headers, store, monkeypatch):
    return Inspection(client, headers, store, monkeypatch)


@pytest.mark.smoke
def test_full_inspection_notes_only_verification_and_approval(flow):
    from app.services import verification_nodes
    created = flow.create()
    assert created['price'] is None and created['status'] == 'requested'
    accepted = flow.accept()
    assert accepted['price'] == 100 and accepted['status'] == 'accepted'
    flow.balances(-10000, 0, 0, 10000)
    flow.visit()
    photos = [flow.upload(item) for item in CHECKLIST]
    submitted = flow.submit()
    assert submitted['media_urls'] == [f'/photos/{photo["id"]}' for photo in photos]
    result = flow.verify()
    assert result['check_score'] == 50
    assert isinstance(verification_nodes.structured_llm.invoke.call_args.args[0], str)
    assert flow.call('GET', f'/jobs/{flow.job_id}')['status'] == 'verified'
    assert flow.call('POST', f'/jobs/{flow.job_id}/photo-review/approve')['status'] == 'approved'
    flow.balances(-10000, 8500, 1500)
    assert flow.profile().jobs_completed == 1


@pytest.mark.smoke
def test_missing_checklist_photo_blocks_report(flow):
    flow.create()
    flow.accept()
    flow.visit()
    flow.upload(CHECKLIST[0])
    response = flow.client.post('/reports/', headers=flow.headers(5), json={'job_id': flow.job_id, 'notes': 'Both checked'})
    assert response.status_code == 400
    assert 'Fire extinguisher' in response.json()['error']['message']
    with flow.store() as db:
        assert db.query(Report).filter_by(job_id=flow.job_id).count() == 0
        assert db.get(Job, flow.job_id).status == JobStatus.visited


def test_report_resubmission_clears_old_ai_result(flow):
    flow.create()
    flow.accept()
    flow.visit()
    for item in CHECKLIST:
        flow.upload(item)
    flow.submit('Nothing else to report')
    flow.verify(addressed=False)
    assert flow.call('GET', f'/jobs/{flow.job_id}')['status'] == 'needs_reupload'
    original_id = flow.report_id
    replacement = flow.submit()
    assert replacement['id'] == original_id
    assert replacement['ai_verification_result'] is None
    assert replacement['ai_generated_summary'] is None
    assert replacement['check_score'] is None
    assert flow.verify()['check_score'] == 50
    assert flow.call('GET', f'/jobs/{flow.job_id}')['status'] == 'verified'


def test_submission_and_verification_cannot_be_repeated(flow):
    flow.start()
    assert flow.client.post('/reports/', headers=flow.headers(5), json={'job_id': flow.job_id, 'notes': 'Submitting the same report again.'}).status_code == 400
    assert flow.client.post(f'/reports/{flow.report_id}/verify', headers=flow.headers(5)).status_code == 400
    with flow.store() as db:
        assert db.query(Report).filter_by(job_id=flow.job_id).count() == 1


@pytest.mark.parametrize('uid', [1, 4, 5])
def test_only_participants_or_admin_can_verify(client, headers, store, monkeypatch, uid):
    flow = Inspection(client, headers, store, monkeypatch)
    flow.create()
    flow.accept()
    flow.visit()
    for item in CHECKLIST:
        flow.upload(item)
    flow.submit()
    from app.routers import report
    from app.services.verification_graph import verification_graph
    monkeypatch.setattr(report, 'verification_graph', verification_graph)
    flow.ai_output(CHECKLIST)
    assert client.post(f'/reports/{flow.report_id}/verify', headers=headers(uid)).status_code == 200


@pytest.mark.parametrize('uid', [6, 7])
def test_nonparticipants_cannot_verify(client, headers, store, monkeypatch, uid):
    flow = Inspection(client, headers, store, monkeypatch).start()
    assert client.post(f'/reports/{flow.report_id}/verify', headers=headers(uid)).status_code == 403


@pytest.mark.parametrize('fmt', ['JPEG', 'PNG', 'WEBP'])
def test_real_image_formats_are_accepted_by_bytes(flow, fmt):
    flow.create()
    flow.accept()
    flow.visit()
    photo = flow.upload(fmt=fmt)
    assert photo['content_type'] == {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'WEBP': 'image/webp'}[fmt]


@pytest.mark.parametrize('data', [b'', b'not an image', image_bytes('GIF')])
def test_empty_spoofed_and_disallowed_images_are_rejected(flow, data):
    flow.create()
    flow.accept()
    flow.visit()
    response = flow.client.post(f'/jobs/{flow.job_id}/photos', headers=flow.headers(5), data={'checklist_item': CHECKLIST[0]}, files={'file': ('fake.jpg', data, 'image/jpeg')})
    assert response.status_code == 400
    with flow.store() as db:
        assert db.query(Photo).filter_by(job_id=flow.job_id).count() == 0


@pytest.mark.smoke
def test_upload_size_limit_and_item_cap(flow, monkeypatch):
    from app.routers import photo
    monkeypatch.setattr(photo, 'MAX_PHOTO_BYTES', 1000)
    flow.create()
    flow.accept()
    flow.visit()
    response = flow.client.post(f'/jobs/{flow.job_id}/photos', headers=flow.headers(5), data={'checklist_item': CHECKLIST[0]}, files={'file': ('large.jpg', b'x' * 1001, 'image/jpeg')})
    assert response.status_code == 413
    for _ in range(3):
        flow.upload()
    response = flow.client.post(f'/jobs/{flow.job_id}/photos', headers=flow.headers(5), data={'checklist_item': CHECKLIST[0]}, files={'file': ('fourth.jpg', image_bytes(), 'image/jpeg')})
    assert response.status_code == 400


def test_upload_phase_item_and_owner_restrictions(flow):
    flow.create()
    flow.accept()
    path = f'/jobs/{flow.job_id}/photos'
    args = {'data': {'checklist_item': CHECKLIST[0]}, 'files': {'file': ('test.jpg', image_bytes(), 'image/jpeg')}}
    assert flow.client.post(path, headers=flow.headers(5), **args).status_code == 400
    flow.visit()
    assert flow.client.post(path, headers=flow.headers(6), **args).status_code == 403
    assert flow.client.post(path, headers=flow.headers(4), **args).status_code == 403
    args['data']['checklist_item'] = 'Unknown item'
    assert flow.client.post(path, headers=flow.headers(5), **args).status_code == 400


def test_original_photos_are_immutable_after_report_submission(flow):
    flow.start()
    photos = flow.call('GET', f'/jobs/{flow.job_id}/photos')
    assert flow.client.delete(f'/photos/{photos[0]["id"]}', headers=flow.headers(5)).status_code == 400
    assert flow.client.delete(f'/photos/{photos[0]["id"]}', headers=flow.headers(6)).status_code == 403


def test_requested_job_expiry_has_no_payment(client, headers, make_job, store):
    jid = make_job(status=JobStatus.requested, payment_status=None)
    with store() as db:
        db.get(Job, jid).accept_deadline = utcnow() - timedelta(seconds=1)
        db.commit()
    response = client.post('/admin/scheduler/run', headers=headers(1))
    assert response.status_code == 200
    with store() as db:
        assert db.get(Job, jid).status == JobStatus.expired
        assert db.query(Payment).filter_by(job_id=jid).count() == 0


def test_external_http_is_blocked_by_test_harness():
    import requests
    import httpx
    with pytest.raises(AssertionError, match='External HTTP'):
        requests.get('https://example.invalid')
    with pytest.raises(AssertionError, match='External HTTP'):
        httpx.get('https://example.invalid')
