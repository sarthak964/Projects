from datetime import timedelta

import pytest

from app.core.time import utcnow
from app.models import Dispute, Job, JobStatus, PaymentStatus, SupportTicket
from tests.helpers import Inspection


def legacy_job(make_job, store, age=0):
    jid = make_job(status=JobStatus.paid, payment_status=PaymentStatus.released)
    with store() as db:
        db.get(Job, jid).verified_at = utcnow() - timedelta(days=age)
        db.commit()
    return jid


@pytest.mark.smoke
@pytest.mark.parametrize('outcome,refund,expected', [
    ('uphold', None, (-10000, 8500, 1500)),
    ('refund', None, (0, 0, 0)),
    ('partial', 25.5, (-7450, 6332, 1118)),
])
def test_retained_legacy_dispute_full_human_resolution(client, headers, make_job, store, monkeypatch, outcome, refund, expected):
    from app.models import Report
    from app.routers import dispute
    jid = legacy_job(make_job, store)
    with store() as db:
        db.add(Report(job_id=jid, notes='Historical inspection report'))
        db.commit()
    response = client.post('/disputes/', headers=headers(4), json={'job_id': jid, 'reason': 'Inspection report was incorrect'})
    assert response.status_code == 200
    did = response.json()['id']
    assert response.json()['status'] == 'open'
    assert client.post('/disputes/', headers=headers(4), json={'job_id': jid, 'reason': 'Duplicate complaint'}).status_code == 400
    dispute.dispute_graph.invoke.side_effect = None
    dispute.dispute_graph.invoke.return_value = {'recommended_outcome': 'refund', 'confidence': 1.0, 'reasoning': 'Mock recommendation'}
    response = client.post(f'/disputes/{did}/triage', headers=headers(4))
    assert response.status_code == 200
    assert response.json()['status'] == 'escalated'
    flow = Inspection(client, headers, store, monkeypatch)
    flow.job_id = jid
    flow.balances(-10000, 8500, 1500)
    response = client.post(f'/disputes/{did}/resolve', headers=headers(1), json={'outcome': outcome, 'notes': 'Human decision', 'refund_amount': refund})
    assert response.status_code == 200
    assert response.json()['status'] == 'resolved'
    flow.balances(*expected)
    assert client.post(f'/disputes/{did}/resolve', headers=headers(1), json={'outcome': outcome, 'notes': 'Duplicate decision', 'refund_amount': refund}).status_code == 400
    flow.balances(*expected)
    assert client.get(f'/disputes/{did}', headers=headers(4)).status_code == 200
    assert client.get(f'/disputes/{did}', headers=headers(1)).status_code == 200
    assert client.get(f'/disputes/{did}', headers=headers(7)).status_code == 403


def test_legacy_window_and_ownership(client, headers, make_job, store):
    jid = legacy_job(make_job, store, age=31)
    assert client.post('/disputes/', headers=headers(4), json={'job_id': jid, 'reason': 'Too late'}).status_code == 400
    eligible = legacy_job(make_job, store, age=29)
    assert client.post('/disputes/', headers=headers(7), json={'job_id': eligible, 'reason': 'Other renter'}).status_code == 403
    assert client.post('/disputes/', headers=headers(4), json={'job_id': eligible, 'reason': 'Within the legacy window'}).status_code == 200


def test_legacy_analysis_failure_can_be_retried(client, headers, make_job, store):
    from app.models import Report
    from app.routers import dispute
    jid = legacy_job(make_job, store)
    with store() as db:
        db.add(Report(job_id=jid, notes='Historical report'))
        db.commit()
    case = client.post('/disputes/', headers=headers(4), json={'job_id': jid, 'reason': 'Test legacy complaint'}).json()
    did = case['id']
    dispute.dispute_graph.invoke.side_effect = RuntimeError('Test analysis service failure')
    assert client.post(f'/disputes/{did}/triage', headers=headers(4)).status_code == 502
    assert client.get(f'/disputes/{did}', headers=headers(4)).json()['status'] == 'open'
    dispute.dispute_graph.invoke.side_effect = None
    dispute.dispute_graph.invoke.return_value = {'recommended_outcome': 'uphold', 'confidence': .9, 'reasoning': 'Mock result'}
    assert client.post(f'/disputes/{did}/triage', headers=headers(4)).json()['status'] == 'escalated'


@pytest.mark.parametrize('intent', ['faq', 'status_check', 'escalate'])
def test_authenticated_support_intents(client, headers, make_job, store, intent):
    from app.routers import support
    jid = make_job()
    support.support_graph.invoke.side_effect = None
    support.support_graph.invoke.return_value = {'intent': intent, 'faq_answer': 'Mock FAQ answer', 'dispute_reason': None, 'escalation_summary': 'Mock support summary'}
    response = client.post('/support/chat', headers=headers(4), json={'job_id': jid, 'message': 'Please help with my inspection'})
    assert response.status_code == 200
    assert response.json()['intent'] == intent
    with store() as db:
        assert db.query(SupportTicket).count() == (1 if intent == 'escalate' else 0)
    if intent == 'status_check':
        assert 'photo-review' in response.json()['reply']


def test_support_dispute_uses_photo_review_for_modern_job(client, headers, make_job, store):
    from app.routers import support
    jid = make_job()
    support.support_graph.invoke.side_effect = None
    support.support_graph.invoke.return_value = {'intent': 'dispute', 'faq_answer': None, 'dispute_reason': 'Wrong evidence', 'escalation_summary': None}
    response = client.post('/support/chat', headers=headers(4), json={'job_id': jid, 'message': 'Wrong evidence'})
    assert response.status_code == 200
    assert 'photo-review' in response.json()['reply']
    with store() as db:
        assert db.query(Dispute).filter_by(job_id=jid).count() == 0
        assert db.get(Job, jid).status == JobStatus.verified


def test_support_service_failure_does_not_create_ticket(client, headers, store):
    from app.routers import support
    support.support_graph.invoke.side_effect = RuntimeError('Test support failure')
    assert client.post('/support/chat', headers=headers(4), json={'message': 'Please help'}).status_code == 502
    with store() as db:
        assert db.query(SupportTicket).count() == 0


def test_reviewer_location_ownership_and_missing_address(client, headers, store, monkeypatch):
    from app.routers import reviewer_profile
    reviewer_profile.geocode_address.return_value = None
    reviewer_profile.geocode_address.side_effect = None
    assert client.post('/reviewers/5/location', headers=headers(6), json={'address': 'Other reviewer address'}).status_code == 403
    reviewer_profile.geocode_address.assert_not_called()
    assert client.post('/reviewers/5/location', headers=headers(5), json={'address': 'Unresolvable test address'}).status_code == 400
    monkeypatch.setattr(reviewer_profile, 'geocode_address', lambda value: {'lat': 12.98, 'lng': 77.60})
    assert client.post('/reviewers/5/location', headers=headers(5), json={'address': 'New test address'}).status_code == 200
    assert client.post('/reviewers/4/location', headers=headers(1), json={'address': 'Renter account'}).status_code == 400
