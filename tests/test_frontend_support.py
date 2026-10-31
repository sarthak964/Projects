from datetime import timedelta

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.core.config import CORS_ALLOWED_ORIGINS
from app.core.cors import parse_allowed_origins
from app.core.errors import configure_errors
from app.core.time import utcnow
from app.models import Job, JobStatus, PaymentStatus, PhotoReview, PhotoReviewStatus, Report, ReviewerProfile, Notification


def test_renter_lists_only_own_jobs(client, headers, make_job, store):
    own = make_job()
    other = make_job()
    with store() as db:
        db.get(Job, other).renter_id = 7
        db.commit()
    response = client.get('/jobs/mine?renter_id=7', headers=headers(4))
    assert response.status_code == 200
    assert response.json()['total'] == 1
    assert [row['id'] for row in response.json()['items']] == [own]
    assert [row['id'] for row in client.get('/jobs/mine', headers=headers(7)).json()['items']] == [other]


def test_reviewer_lists_only_assigned_jobs(client, headers, make_job, store):
    own = make_job()
    other = make_job()
    unassigned = make_job(status=JobStatus.requested, payment_status=None)
    with store() as db:
        db.get(Job, other).reviewer_id = 6
        db.commit()
    response = client.get('/jobs/mine?reviewer_id=6', headers=headers(5))
    assert response.status_code == 200
    assert [row['id'] for row in response.json()['items']] == [own]
    assert response.json()['total'] == 1
    assert [row['id'] for row in client.get('/jobs/mine', headers=headers(6)).json()['items']] == [other]


def test_suspended_reviewer_can_still_view_own_history(client, headers, make_job, store):
    jid = make_job()
    with store() as db:
        db.query(ReviewerProfile).filter_by(user_id=5).one().suspended = True
        db.commit()
    assert client.get('/jobs/mine', headers=headers(5)).json()['items'][0]['id'] == jid


@pytest.mark.parametrize('uid', [4, 5, 6, 7])
def test_admin_list_rejects_other_roles(client, headers, uid):
    response = client.get('/admin/jobs', headers=headers(uid))
    assert response.status_code == 403
    assert response.json()['error']['code'] == 'forbidden'


def test_admin_uses_admin_list(client, headers):
    assert client.get('/jobs/mine', headers=headers(1)).status_code == 403
    assert client.get('/admin/jobs', headers=headers(1)).json() == {'items': [], 'total': 0, 'limit': 20, 'offset': 0}


@pytest.mark.parametrize('path', ['/jobs/mine', '/admin/jobs'])
def test_lists_require_authentication(client, path):
    response = client.get(path)
    assert response.status_code == 401
    assert response.json()['error']['code'] == 'unauthorized'


def test_pagination_status_and_stable_order(client, headers, make_job, store):
    ids = [make_job() for _ in range(3)]
    pending = make_job(status=JobStatus.requested, payment_status=None)
    stamp = utcnow()
    with store() as db:
        for jid in ids + [pending]:
            db.get(Job, jid).created_at = stamp
        db.commit()
    page = client.get('/jobs/mine?status=verified&limit=1&offset=1', headers=headers(4)).json()
    assert page['total'] == 3 and page['limit'] == 1 and page['offset'] == 1
    assert [row['id'] for row in page['items']] == [ids[1]]
    assert client.get('/jobs/mine?offset=999', headers=headers(4)).json()['items'] == []


def test_admin_filters_combine(client, headers, make_job, store):
    matched = make_job()
    other = make_job()
    with store() as db:
        db.get(Job, other).renter_id = 7
        db.get(Job, other).reviewer_id = 6
        db.commit()
    assert client.get('/admin/jobs', headers=headers(1)).json()['total'] == 2
    response = client.get('/admin/jobs?status=verified&renter_id=4&reviewer_id=5', headers=headers(1))
    assert response.status_code == 200
    assert [row['id'] for row in response.json()['items']] == [matched]
    assert client.get('/admin/jobs?renter_id=7&reviewer_id=5', headers=headers(1)).json()['total'] == 0


@pytest.mark.parametrize('query', ['limit=0', 'limit=101', 'offset=-1', 'status=unknown'])
def test_invalid_list_parameters(client, headers, query):
    response = client.get('/jobs/mine?' + query, headers=headers(4))
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'validation_error'
    assert response.json()['error']['details']


@pytest.mark.parametrize('query', ['renter_id=0', 'reviewer_id=-1', 'renter_id=abc'])
def test_invalid_admin_filter(client, headers, query):
    assert client.get('/admin/jobs?' + query, headers=headers(1)).status_code == 422


def test_lists_include_joined_status_and_report(client, headers, make_job, store):
    jid = make_job(review_status=PhotoReviewStatus.awaiting_renter_recheck)
    with store() as db:
        review = db.query(PhotoReview).filter_by(job_id=jid).one()
        review.recheck_deadline = utcnow() + timedelta(hours=1)
        report = Report(job_id=jid, notes='Test inspection', check_score=50)
        db.add(report)
        db.commit()
        rid = report.id
    row = client.get('/jobs/mine', headers=headers(4)).json()['items'][0]
    assert row['id'] == jid
    assert row['payment_status'] == 'held'
    assert row['photo_review_status'] == 'awaiting_renter_recheck'
    assert row['recheck_deadline'] is not None
    assert row['review_deadline'] is not None
    assert row['report_id'] == rid and row['check_score'] == 50
    assert 'notes' not in row and 'stored_name' not in row and 'ai_verdict' not in row


def test_unassigned_job_has_nullable_related_fields(client, headers, make_job):
    jid = make_job(status=JobStatus.requested, payment_status=None)
    row = client.get('/jobs/mine', headers=headers(4)).json()['items'][0]
    assert row['id'] == jid
    for name in ('report_id', 'payment_status', 'check_score', 'photo_review_status', 'review_deadline'):
        assert row[name] is None


def test_lists_are_read_only(client, headers, make_job, store):
    jid = make_job(status=JobStatus.requested, payment_status=None)
    with store() as db:
        db.get(Job, jid).accept_deadline = utcnow() - timedelta(hours=1)
        db.commit()
        version = db.get(Job, jid).version_id
        count = db.query(Notification).count()
    assert client.get('/jobs/mine', headers=headers(4)).status_code == 200
    assert client.get('/admin/jobs', headers=headers(1)).status_code == 200
    with store() as db:
        assert db.get(Job, jid).version_id == version
        assert db.get(Job, jid).status == JobStatus.requested
        assert db.query(Notification).count() == count


def test_open_jobs_route_and_numeric_detail_still_work(client, headers, make_job):
    jid = make_job(status=JobStatus.requested, payment_status=None)
    assert client.get('/jobs/open', headers=headers(5)).status_code == 200
    assert client.get(f'/jobs/{jid}', headers=headers(4)).status_code == 200
    assert client.get('/jobs/mine', headers=headers(4)).status_code == 200


def test_report_read_is_participants_or_admin_only(client, headers, make_job, store):
    jid = make_job()
    with store() as db:
        report = Report(job_id=jid, notes='Inspection notes', check_score=50)
        db.add(report)
        db.commit()
        rid = report.id
    for uid in (1, 4, 5):
        response = client.get(f'/reports/{rid}', headers=headers(uid))
        assert response.status_code == 200
        assert response.json()['notes'] == 'Inspection notes'
    for uid in (6, 7):
        assert client.get(f'/reports/{rid}', headers=headers(uid)).status_code == 403
    assert client.get(f'/reports/{rid}').status_code == 401
    assert client.get('/reports/999999', headers=headers(4)).status_code == 404


def test_consistent_http_error_shape(client, headers):
    for path, expected in [('/jobs/mine', 401), ('/does-not-exist', 404)]:
        response = client.get(path)
        assert response.status_code == expected
        body = response.json()
        assert set(body['error']) == {'code', 'message', 'details'}
        assert body['error']['details'] == []
        assert body['detail'] == body['error']['message']
    assert client.put('/health').json()['error']['code'] == 'method_not_allowed'


def test_validation_errors_do_not_echo_input_or_exception_context(client, headers):
    response = client.post('/jobs/', headers=headers(4), json={'address': 'PRIVATE-ADDRESS', 'checklist': ['AC', 'AC']})
    assert response.status_code == 422
    body = response.json()
    assert body['error']['details'][0]['field'] == 'body.checklist'
    assert 'PRIVATE-ADDRESS' not in response.text
    assert 'input' not in body['detail'][0]
    assert 'ctx' not in body['detail'][0]


def test_json_decode_error_is_consistent(client, headers):
    response = client.post('/jobs/', headers={**headers(4), 'Content-Type': 'application/json'}, content='{invalid-json')
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'validation_error'


def test_cors_allowed_and_rejected_origins(client):
    origin = CORS_ALLOWED_ORIGINS[0]
    response = client.get('/health', headers={'Origin': origin})
    assert response.headers['access-control-allow-origin'] == origin
    assert 'access-control-allow-credentials' not in response.headers
    response = client.options('/jobs/mine', headers={'Origin': origin, 'Access-Control-Request-Method': 'GET', 'Access-Control-Request-Headers': 'Authorization, Content-Type'})
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == origin
    forbidden = 'https://untrusted.example'
    response = client.get('/health', headers={'Origin': forbidden})
    assert 'access-control-allow-origin' not in response.headers
    response = client.options('/jobs/mine', headers={'Origin': forbidden, 'Access-Control-Request-Method': 'GET'})
    assert response.status_code == 400
    assert 'access-control-allow-origin' not in response.headers


def test_cors_wraps_auth_errors(client):
    origin = CORS_ALLOWED_ORIGINS[0]
    response = client.get('/jobs/mine', headers={'Origin': origin})
    assert response.status_code == 401
    assert response.headers['access-control-allow-origin'] == origin
    assert response.json()['error']['code'] == 'unauthorized'


def test_unexpected_error_is_generic_and_has_cors():
    app = FastAPI()
    configure_errors(app)
    app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:3000'])
    @app.get('/crash')
    def crash():
        raise RuntimeError('PRIVATE-DATABASE-DETAIL')
    @app.get('/busy')
    def busy():
        raise HTTPException(status_code=503, detail='Retry later', headers={'Retry-After': '1'})
    with TestClient(app) as test_client:
        response = test_client.get('/crash', headers={'Origin': 'http://localhost:3000'})
        assert response.status_code == 500
        assert response.json()['error']['code'] == 'internal_error'
        assert response.headers['access-control-allow-origin'] == 'http://localhost:3000'
        assert 'PRIVATE-DATABASE-DETAIL' not in response.text
        response = test_client.get('/busy')
        assert response.status_code == 503
        assert response.headers['retry-after'] == '1'
        assert response.json()['error']['code'] == 'service_unavailable'


def test_cors_config_parsing():
    assert parse_allowed_origins('') == []
    assert parse_allowed_origins(' http://localhost:3000/,http://localhost:3000,https://Example.com ') == ['http://localhost:3000', 'https://example.com']


@pytest.mark.parametrize('raw', ['*', 'localhost:3000', 'https://example.com/path', 'https://user:pass@example.com', 'https://example.com?secret=value', 'https://example.com/#x', 'http://localhost:99999', 'https://*.example.com', 'https://exa mple.com', 'https://example.com\\evil'])
def test_cors_config_rejects_invalid_origins(raw):
    with pytest.raises(ValueError):
        parse_allowed_origins(raw)


def test_openapi_documents_lists_and_error_schema(client):
    schema = client.get('/openapi.json').json()
    assert '/jobs/mine' in schema['paths']
    assert '/admin/jobs' in schema['paths']
    assert '/reports/{report_id}' in schema['paths']
    assert schema['paths']['/jobs/mine']['get']['responses']['422']['content']['application/json']['schema']['$ref'].endswith('/ApiErrorResponse')
