import runpy
from pathlib import Path

import pytest

from app.models import Job, JobStatus, Payment
from app.models.ledger import LedgerEntry
from app.models.notification import Notification
from app.routers import job as routes


@pytest.mark.parametrize('distance,allowed', [(0, True), (49.999999, True), (50, True), (50.000001, False), (1741.356323, False)])
def test_radius_controls_list_and_direct_accept(client, headers, make_job, store, monkeypatch, distance, allowed):
    jid = make_job(status=JobStatus.requested, payment_status=None)
    monkeypatch.setattr(routes, 'haversine_distance_km', lambda *args: distance)
    with store() as db:
        notices = db.query(Notification).count()
        ledger_entries = db.query(LedgerEntry).count()
    for suffix in ('', '?max_distance_km=9999'):
        response = client.get('/jobs/open' + suffix, headers=headers(5))
        assert response.status_code == 200
        assert [row['id'] for row in response.json()] == ([jid] if allowed else [])
    response = client.post(f'/jobs/{jid}/accept', headers=headers(5))
    assert response.status_code == (200 if allowed else 400)
    if not allowed:
        assert 'service radius' in response.json()['detail']
        with store() as db:
            saved = db.get(Job, jid)
            assert saved.status == JobStatus.requested
            assert saved.reviewer_id is None
            assert db.query(Payment).filter_by(job_id=jid).count() == 0
            assert db.query(LedgerEntry).count() == ledger_entries
            assert db.query(Notification).count() == notices


def test_smaller_filter_still_applies(client, headers, make_job, monkeypatch):
    make_job(status=JobStatus.requested, payment_status=None)
    monkeypatch.setattr(routes, 'haversine_distance_km', lambda *args: 25)
    assert client.get('/jobs/open?max_distance_km=10', headers=headers(5)).json() == []


def test_configured_radius_applies_to_both_routes(client, headers, make_job, monkeypatch):
    jid = make_job(status=JobStatus.requested, payment_status=None)
    monkeypatch.setattr(routes, 'MAX_SERVICE_DISTANCE_KM', 10)
    monkeypatch.setattr(routes, 'haversine_distance_km', lambda *args: 11)
    assert client.get('/jobs/open', headers=headers(5)).json() == []
    assert client.post(f'/jobs/{jid}/accept', headers=headers(5)).status_code == 400


def test_real_delhi_bengaluru_distance_is_blocked(client, headers, make_job, store):
    jid = make_job(status=JobStatus.requested, payment_status=None)
    with store() as db:
        saved = db.get(Job, jid)
        saved.geocoded_lat = 28.6317695
        saved.geocoded_lng = 77.2193804
        db.commit()
    assert client.get('/jobs/open', headers=headers(5)).json() == []
    assert client.post(f'/jobs/{jid}/accept', headers=headers(5)).status_code == 400


@pytest.mark.parametrize('value', ['0', '-1', 'nan', 'inf', '-inf', 'abc', ''])
def test_invalid_radius_configuration_fails_startup(monkeypatch, value):
    monkeypatch.setenv('MAX_SERVICE_DISTANCE_KM', value)
    with pytest.raises(ValueError):
        runpy.run_path(str(Path(routes.__file__).parents[1] / 'core/config.py'))


def test_positive_custom_radius_configuration(monkeypatch):
    monkeypatch.setenv('MAX_SERVICE_DISTANCE_KM', '12.5')
    config = runpy.run_path(str(Path(routes.__file__).parents[1] / 'core/config.py'))
    assert config['MAX_SERVICE_DISTANCE_KM'] == 12.5
