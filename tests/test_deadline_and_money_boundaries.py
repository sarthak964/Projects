from datetime import datetime, timedelta

import pytest

from app.core.time import utcnow
from app.models import Job, JobStatus, PhotoReview, Report
from tests.helpers import Inspection


@pytest.mark.parametrize('late', [False, True])
def test_initial_photo_review_deadline_is_inclusive(client, headers, store, monkeypatch, late):
    from app.services import job_lifecycle
    flow = Inspection(client, headers, store, monkeypatch).start()
    deadline = utcnow()
    with store() as db:
        db.get(Job, flow.job_id).verified_at = deadline - timedelta(hours=48)
        db.commit()
    monkeypatch.setattr(job_lifecycle, 'utcnow', lambda: deadline + timedelta(microseconds=1 if late else 0))
    response = client.post(f'/jobs/{flow.job_id}/photo-review/approve', headers=headers(4))
    assert response.status_code == (400 if late else 200)
    assert flow.review().status.value == ('auto_approved' if late else 'approved')
    flow.balances(-10000, 8500, 1500)


@pytest.mark.parametrize('stage,field,action,manual,automatic', [
    ('genuine', 'ai_result_deadline', 'accept-ai-result', 'accepted_ai_result', 'auto_accepted_ai_result'),
    ('recheck', 'recheck_deadline', 'recheck/approve', 'approved_after_reupload', 'auto_approved_after_reupload'),
    ('reupload', 'reupload_deadline', 'reupload-complete', 'awaiting_renter_recheck', 'awaiting_human'),
])
@pytest.mark.parametrize('late', [False, True])
def test_photo_substage_deadline_boundaries(client, headers, store, monkeypatch, stage, field, action, manual, automatic, late):
    from app.services import job_lifecycle
    flow = Inspection(client, headers, store, monkeypatch).start()
    flow.reject('supports' if stage == 'genuine' else 'unclear')
    if stage == 'recheck':
        flow.reupload()
    elif stage == 'reupload':
        flow.upload()
    deadline = utcnow()
    with store() as db:
        setattr(db.query(PhotoReview).filter_by(job_id=flow.job_id).one(), field, deadline)
        db.commit()
    monkeypatch.setattr(job_lifecycle, 'utcnow', lambda: deadline + timedelta(microseconds=1 if late else 0))
    uid = 5 if stage == 'reupload' else 4
    response = client.post(f'/jobs/{flow.job_id}/photo-review/{action}', headers=headers(uid))
    assert response.status_code == (400 if late else 200)
    assert flow.review().status.value == (automatic if late else manual)
    assert flow.profile().strikes == 0
    if stage == 'genuine':
        flow.balances(-12500, 8500, 4000)
    elif stage == 'recheck':
        flow.balances(-10000, 8500, 1500)
    else:
        flow.balances(-12500, 0, 0, 12500)


@pytest.mark.parametrize('late', [False, True])
def test_appeal_deadline_boundary(client, headers, store, monkeypatch, late):
    from app.routers import appeal
    flow = Inspection(client, headers, store, monkeypatch).start()
    flow.reject()
    flow.dispute_ai()
    flow.decide('genuine')
    deadline = utcnow()
    with store() as db:
        db.query(PhotoReview).filter_by(job_id=flow.job_id).one().decided_at = deadline - timedelta(hours=48)
        db.commit()
    monkeypatch.setattr(appeal, 'utcnow', lambda: deadline + timedelta(microseconds=1 if late else 0))
    response = client.post(f'/jobs/{flow.job_id}/appeal', headers=headers(4), json={'reason': 'Boundary appeal test'})
    assert response.status_code == (400 if late else 200)


@pytest.mark.parametrize('late', [False, True])
def test_retained_legacy_thirty_day_boundary(client, headers, make_job, store, monkeypatch, late):
    from app.routers import dispute
    from app.models import PaymentStatus
    jid = make_job(status=JobStatus.paid, payment_status=PaymentStatus.released)
    deadline = utcnow()
    with store() as db:
        db.get(Job, jid).verified_at = deadline - timedelta(days=30)
        db.commit()
    monkeypatch.setattr(dispute, 'utcnow', lambda: deadline + timedelta(microseconds=1 if late else 0))
    response = client.post('/disputes/', headers=headers(4), json={'job_id': jid, 'reason': 'Legacy deadline boundary'})
    assert response.status_code == (400 if late else 200)


def test_paise_commission_and_frozen_rate_across_other_writes(client, headers, store, monkeypatch):
    from app.routers import job
    from app.services import ledger
    monkeypatch.setattr(job, 'calculate_price', lambda distance: 103.31)
    flow = Inspection(client, headers, store, monkeypatch).start()
    flow.call('POST', f'/jobs/{flow.job_id}/photo-review/approve')
    flow.balances(-10331, 8781, 1550)
    monkeypatch.setattr(ledger, 'PLATFORM_COMMISSION_RATE', .5)
    flow.call('POST', '/ratings/', json={'job_id': flow.job_id, 'score': 5, 'comment': 'Test rating after setting change'})
    with store() as db:
        assert db.get(Job, flow.job_id).commission_rate == .15
    flow.balances(-10331, 8781, 1550)


@pytest.mark.parametrize('count,expected', [(0, 25), (1, 25), (9, 30), (20, 60), (100, 60)])
def test_check_fee_minimum_rounding_and_cap(count, expected):
    from app.services.photo_fees import calculate_review_fee
    assert calculate_review_fee(count) == expected


def test_invalid_real_graph_response_is_retryable_without_saving(client, headers, store, monkeypatch):
    from app.services import verification_nodes
    from app.services.verification_graph import verification_graph
    from app.services.verification_state import VerificationOutput
    from app.routers import report
    flow = Inspection(client, headers, store, monkeypatch)
    flow.create()
    flow.accept()
    flow.visit()
    flow.upload('AC working')
    flow.upload('Fire extinguisher')
    flow.submit()
    monkeypatch.setattr(report, 'verification_graph', verification_graph)
    verification_nodes.structured_llm.invoke.side_effect = None
    verification_nodes.structured_llm.invoke.return_value = VerificationOutput(results=[])
    response = client.post(f'/reports/{flow.report_id}/verify', headers=headers(5))
    assert response.status_code == 502
    with store() as db:
        assert db.get(Job, flow.job_id).status == JobStatus.report_submitted
        assert db.get(Report, flow.report_id).check_score is None
    flow.balances(-10000, 0, 0, 10000)


def test_scheduler_wins_during_photo_ai_without_holding_check_fee(client, headers, store, monkeypatch):
    from app.routers import photo_review
    from app.services.scheduler import run_sweep
    flow = Inspection(client, headers, store, monkeypatch).start()
    def concurrent_approval(items, notes, photos):
        with store() as db:
            db.get(Job, flow.job_id).verified_at = utcnow() - timedelta(days=3)
            db.commit()
        assert run_sweep()['changed'] == 1
        return {'all_genuine': True, 'items': []}
    monkeypatch.setattr(photo_review, 'check_photos', concurrent_approval)
    response = client.post(f'/jobs/{flow.job_id}/photo-review/reject', headers=headers(4), json={'items': ['AC working'], 'confirm_fee': 25})
    assert response.status_code == 409
    assert flow.review().status.value == 'auto_approved'
    flow.balances(-10000, 8500, 1500)
