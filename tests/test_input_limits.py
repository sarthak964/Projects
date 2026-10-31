import pytest
from pydantic import ValidationError

from app.models import Job, JobStatus, Report
from app.schemas.job import JobCreate
from app.schemas.report import ReportCreate
from tests.helpers import Inspection


@pytest.mark.parametrize('payload', [
    {'address': 'a' * 501, 'checklist': ['Walls']},
    {'address': 'Test address', 'checklist': ['a' * 201]},
    {'address': 'Test address', 'checklist': [f'Item {i}' for i in range(31)]},
    {'address': 'Test address', 'checklist': ['   ']},
])
def test_invalid_job_limits_stop_before_geocoding_and_writes(client, headers, store, payload):
    from app.routers import job
    response = client.post('/jobs/', headers=headers(4), json=payload)
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'validation_error'
    job.geocode_address.assert_not_called()
    with store() as db:
        assert db.query(Job).count() == 0


def test_exact_job_limits_and_whitespace_are_accepted():
    result = JobCreate(address='  ' + 'a' * 500 + '  ', checklist=['  ' + str(i).zfill(3) + 'x' * 197 + '  ' for i in range(30)])
    assert len(result.address) == 500
    assert len(result.checklist) == 30
    assert all(len(item) == 200 for item in result.checklist)


@pytest.mark.parametrize('payload', [
    {'job_id': 1}, {'job_id': 1, 'notes': None},
    {'job_id': 1, 'notes': ''}, {'job_id': 1, 'notes': ' ' * 50},
    {'job_id': 1, 'notes': 'Too short'},
    {'job_id': 1, 'notes': 'x' * 10001},
    {'job_id': 1, 'notes': '!' * 20},
    {'job_id': 0, 'notes': 'Walls checked and intact.'},
    {'job_id': -1, 'notes': 'Walls checked and intact.'},
])
def test_invalid_report_inputs_return_422_without_writes_or_ai(client, headers, store, payload):
    from app.routers import report
    response = client.post('/reports/', headers=headers(5), json=payload)
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'validation_error'
    report.verification_graph.invoke.assert_not_called()
    with store() as db:
        assert db.query(Report).count() == 0


@pytest.mark.parametrize('notes', ['abcdefghij', 'x' * 10000, 'Walls checked. No cracks.', '\u0915\u092e\u0930\u0947 \u0915\u0940 \u0926\u0940\u0935\u093e\u0930\u0947\u0902 \u0920\u0940\u0915 \u0939\u0948\u0902'])
def test_valid_notes_boundaries_and_unicode(notes):
    assert ReportCreate(job_id=1, notes='  ' + notes + '  ').notes == notes


def test_valid_trimmed_notes_are_saved_without_triggering_ai(client, headers, store, monkeypatch):
    flow = Inspection(client, headers, store, monkeypatch)
    flow.create()
    flow.accept()
    flow.visit()
    for item in ['AC working', 'Fire extinguisher']:
        flow.upload(item)
    result = flow.submit(notes='  AC is working. Fire extinguisher is absent.  ')
    assert result['notes'] == 'AC is working. Fire extinguisher is absent.'
    with store() as db:
        assert db.get(Job, flow.job_id).status == JobStatus.report_submitted


def test_invalid_resubmission_preserves_saved_report(client, headers, store, monkeypatch):
    flow = Inspection(client, headers, store, monkeypatch).start()
    with store() as db:
        db.get(Job, flow.job_id).status = JobStatus.needs_reupload
        original = db.get(Report, flow.report_id)
        notes, summary, score = original.notes, original.ai_generated_summary, original.check_score
        db.commit()
    response = client.post('/reports/', headers=headers(5), json={'job_id': flow.job_id, 'notes': ' '})
    assert response.status_code == 422
    with store() as db:
        saved = db.get(Report, flow.report_id)
        assert (saved.notes, saved.ai_generated_summary, saved.check_score) == (notes, summary, score)
        assert db.get(Job, flow.job_id).status == JobStatus.needs_reupload


def test_legacy_report_with_null_notes_is_still_readable(client, headers, make_job, store):
    jid = make_job()
    with store() as db:
        report = Report(job_id=jid, notes=None, media_urls=[])
        db.add(report)
        db.commit()
        rid = report.id
    response = client.get(f'/reports/{rid}', headers=headers(4))
    assert response.status_code == 200
    assert response.json()['notes'] is None


def test_openapi_exposes_limits_for_future_frontend(client):
    schemas = client.get('/openapi.json').json()['components']['schemas']
    job = schemas['JobCreate']['properties']
    assert job['address']['maxLength'] == 500
    assert job['checklist']['maxItems'] == 30
    assert job['checklist']['items']['maxLength'] == 200
    report = schemas['ReportCreate']
    assert 'notes' in report['required']
    assert report['properties']['notes']['minLength'] == 10
    assert report['properties']['notes']['maxLength'] == 10000
