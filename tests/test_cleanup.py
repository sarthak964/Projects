import math

import pytest

from app.models import Job, JobStatus, Payment, LedgerEntry, ReviewerProfile
from app.services.pricing import calculate_price, haversine_distance_km, valid_coordinates


@pytest.mark.parametrize('lat,lng', [(None, None), (91, 0), (0, 181), (math.nan, 0), (0, math.inf)])
def test_invalid_job_coordinates_are_rejected(client, headers, make_job, store, lat, lng):
    jid = make_job(status=JobStatus.requested, payment_status=None)
    with store() as db:
        job = db.get(Job, jid)
        job.geocoded_lat, job.geocoded_lng = lat, lng
        db.commit()
    response = client.post(f'/jobs/{jid}/accept', headers=headers(5))
    assert response.status_code == 409
    with store() as db:
        assert db.get(Job, jid).status == JobStatus.requested
        assert db.query(Payment).filter_by(job_id=jid).count() == 0
        assert db.query(LedgerEntry).filter_by(job_id=jid).count() == 0


def test_invalid_reviewer_location_is_rejected(client, headers, make_job, store):
    jid = make_job(status=JobStatus.requested, payment_status=None)
    with store() as db:
        db.query(ReviewerProfile).filter_by(user_id=5).one().home_lng = 181
        db.commit()
    assert client.post(f'/jobs/{jid}/accept', headers=headers(5)).status_code == 400
    assert client.get('/jobs/open', headers=headers(5)).status_code == 400


def test_distance_calculation_handles_boundaries():
    assert valid_coordinates(0, 0)
    assert valid_coordinates(-90, 180)
    assert haversine_distance_km(0, 0, 0, 0) == 0
    assert math.isfinite(haversine_distance_km(90, 0, -90, 180))
    assert 20000 < haversine_distance_km(0, 0, 0, 180) < 20100
    with pytest.raises(ValueError):
        haversine_distance_km(91, 0, 0, 0)


@pytest.mark.parametrize('value', [-1, math.nan, math.inf])
def test_invalid_distance_cannot_produce_price(value):
    with pytest.raises(ValueError):
        calculate_price(value)


def test_pricing_preserves_rule_and_uses_half_up_paise():
    assert calculate_price(0) == 100
    assert calculate_price(1) == 110
    assert calculate_price(0.331) == 103.31
    assert calculate_price(0.0005) == 100.01
