from datetime import timedelta

import pytest

from app.core.time import utcnow
from app.models import Job, JobStatus, Payment, Photo, PhotoReview, ReviewerProfile
from tests.helpers import CHECKLIST, Inspection, image_bytes


@pytest.fixture
def flow(client, headers, store, monkeypatch):
    return Inspection(client, headers, store, monkeypatch).start()


def test_fee_quote_counts_only_rejected_items_and_deduplicates(flow):
    quote = flow.call('GET', f'/jobs/{flow.job_id}/photo-review/fee-quote', params=[('items', CHECKLIST[0]), ('items', CHECKLIST[0])])
    assert quote == {'items': [CHECKLIST[0]], 'photo_count': 1, 'fee': 25.0}


def test_wrong_fee_or_unknown_item_does_not_call_ai_or_hold_fee(flow):
    from app.routers import photo_review
    for items, fee in [([CHECKLIST[0]], 24), (['Unknown item'], 25)]:
        response = flow.client.post(f'/jobs/{flow.job_id}/photo-review/reject', headers=flow.headers(4), json={'items': items, 'confirm_fee': fee})
        assert response.status_code == 400
    photo_review.check_photos.assert_not_called()
    assert flow.review() is None
    flow.balances(-10000, 0, 0, 10000)


def test_failed_photo_ai_leaves_no_fee_or_case(flow):
    from app.routers import photo_review
    photo_review.check_photos.side_effect = RuntimeError('Test provider failure')
    response = flow.client.post(f'/jobs/{flow.job_id}/photo-review/reject', headers=flow.headers(4), json={'items': [CHECKLIST[0]], 'confirm_fee': 25})
    assert response.status_code == 502
    assert flow.review() is None
    flow.balances(-10000, 0, 0, 10000)


def test_only_rejected_images_are_sent_to_vision(flow):
    from app.services import verification_nodes
    assert flow.reject()['status'] == 'ai_checked_genuine'
    sent = verification_nodes.structured_llm.invoke.call_args.args[0][0].content
    images = [part for part in sent if part.get('type') == 'image_url']
    labels = [part['text'] for part in sent if part.get('type') == 'text' and part['text'].startswith('Photo submitted')]
    assert len(images) == 1
    assert len(labels) == 1 and 'AC working' in labels[0]
    flow.balances(-12500, 0, 0, 12500)
    assert flow.profile().strikes == 0


@pytest.mark.smoke
def test_genuine_ai_result_accepted_keeps_fee_and_pays_once(flow):
    flow.reject()
    result = flow.call('POST', f'/jobs/{flow.job_id}/photo-review/accept-ai-result')
    assert result['status'] == 'accepted_ai_result' and result['fee_status'] == 'kept'
    flow.balances(-12500, 8500, 4000)
    assert flow.client.post(f'/jobs/{flow.job_id}/photo-review/accept-ai-result', headers=flow.headers(4)).status_code == 400
    flow.balances(-12500, 8500, 4000)


@pytest.mark.parametrize('verdict', ['unclear', 'irrelevant', 'contradicts', 'no_photo'])
def test_non_supporting_ai_results_request_reupload_without_penalty(flow, verdict):
    case = flow.reject(verdict)
    assert case['status'] == 'awaiting_reupload'
    assert case['reupload_deadline'] is not None
    assert flow.profile().strikes == 0 and flow.profile().suspended is False
    flow.balances(-12500, 0, 0, 12500)


def test_reupload_requires_new_photos_and_only_rejected_items(flow):
    flow.reject('unclear')
    path = f'/jobs/{flow.job_id}/photo-review/reupload-complete'
    assert flow.client.post(path, headers=flow.headers(5)).status_code == 400
    response = flow.client.post(f'/jobs/{flow.job_id}/photos', headers=flow.headers(5), data={'checklist_item': CHECKLIST[1]}, files={'file': ('wrong.jpg', image_bytes(), 'image/jpeg')})
    assert response.status_code == 400
    assert flow.client.post(path, headers=flow.headers(6)).status_code == 403
    assert flow.reupload()['status'] == 'awaiting_renter_recheck'


@pytest.mark.smoke
def test_replacement_photos_approved_refunds_check_fee(flow):
    flow.reject('unclear')
    flow.reupload()
    case = flow.call('POST', f'/jobs/{flow.job_id}/photo-review/recheck/approve')
    assert case['status'] == 'approved_after_reupload' and case['fee_status'] == 'refunded'
    flow.balances(-10000, 8500, 1500)
    assert flow.profile().strikes == 0


@pytest.mark.parametrize('decision', ['genuine', 'not_genuine'])
@pytest.mark.smoke
def test_replacement_photos_rejected_go_to_human_without_extra_fee(flow, decision):
    flow.reject('unclear')
    flow.reupload()
    case = flow.call('POST', f'/jobs/{flow.job_id}/photo-review/recheck/reject', json={'reason': 'Replacement evidence is still unclear'})
    assert case['status'] == 'awaiting_human'
    assert case['human_fee_amount'] == 0 and case['human_fee_status'] == 'none'
    assert flow.profile().strikes == 0
    flow.balances(-12500, 0, 0, 12500)
    flow.decide(decision)
    if decision == 'genuine':
        flow.balances(-12500, 8500, 4000)
        assert flow.profile().strikes == 0
    else:
        flow.balances(0, 0, 0)
        assert flow.profile().strikes == 1


def test_human_fee_needs_exact_confirmation(flow):
    flow.reject()
    response = flow.client.post(f'/jobs/{flow.job_id}/photo-review/dispute-ai-result', headers=flow.headers(4), json={'reason': 'Please review', 'confirm_fee': 74})
    assert response.status_code == 400
    assert flow.review().human_fee_amount == 0
    assert flow.review().status.value == 'ai_checked_genuine'
    flow.balances(-12500, 0, 0, 12500)


@pytest.mark.smoke
@pytest.mark.parametrize('decision', ['genuine', 'not_genuine'])
def test_human_decision_handles_both_fees(flow, decision):
    flow.reject()
    case = flow.dispute_ai()
    assert case['human_fee_amount'] == 75 and case['human_fee_status'] == 'held'
    flow.balances(-20000, 0, 0, 20000)
    assert flow.profile().strikes == 0
    flow.decide(decision)
    if decision == 'genuine':
        flow.balances(-20000, 8500, 11500)
        assert flow.review().fee_status.value == 'kept'
        assert flow.review().human_fee_status.value == 'kept'
    else:
        flow.balances(0, 0, 0)
        assert flow.review().fee_status.value == 'refunded'
        assert flow.review().human_fee_status.value == 'refunded'
        assert flow.profile().strikes == 1
    assert flow.client.post(f'/admin/photo-reviews/{flow.job_id}/decide', headers=flow.headers(1), json={'decision': decision, 'notes': 'Duplicate decision'}).status_code == 400


@pytest.mark.parametrize('initial,appellant,expected', [('genuine', 4, (0, 0, 0)), ('not_genuine', 5, (-20000, 8500, 11500))])
@pytest.mark.smoke
def test_appeal_overturn_reverses_price_fees_and_strike(flow, initial, appellant, expected):
    flow.reject()
    flow.dispute_ai()
    flow.decide(initial)
    flow.call('POST', f'/jobs/{flow.job_id}/appeal', uid=appellant, json={'reason': 'Please reconsider this decision'})
    case = flow.call('POST', f'/admin/appeals/{flow.job_id}/decide', uid=1, json={'decision': 'overturn', 'notes': 'Appeal evidence changes the decision'})
    assert case['appeal_status'] == 'overturned'
    flow.balances(*expected)
    assert flow.profile().strikes == (1 if initial == 'genuine' else 0)
    assert flow.client.post(f'/admin/appeals/{flow.job_id}/decide', headers=flow.headers(1), json={'decision': 'overturn', 'notes': 'Repeat reversal'}).status_code == 400
    flow.balances(*expected)


def test_appeal_only_loser_once_and_within_window(flow):
    flow.reject()
    flow.dispute_ai()
    flow.decide('genuine')
    path = f'/jobs/{flow.job_id}/appeal'
    assert flow.call('GET', path)['can_appeal'] is True
    assert flow.call('GET', path, uid=5)['can_appeal'] is False
    assert flow.client.post(path, headers=flow.headers(5), json={'reason': 'Winner cannot appeal'}).status_code == 403
    assert flow.client.post(path, headers=flow.headers(7), json={'reason': 'Other renter cannot appeal'}).status_code == 403
    flow.call('POST', path, json={'reason': 'Renter requests appeal'})
    assert flow.client.post(path, headers=flow.headers(4), json={'reason': 'Second appeal'}).status_code == 400


def test_expired_appeal_is_rejected(flow):
    flow.reject()
    flow.dispute_ai()
    flow.decide('genuine')
    with flow.store() as db:
        db.query(PhotoReview).filter_by(job_id=flow.job_id).one().decided_at = utcnow() - timedelta(hours=49)
        db.commit()
    path = f'/jobs/{flow.job_id}/appeal'
    assert flow.call('GET', path)['can_appeal'] is False
    assert flow.client.post(path, headers=flow.headers(4), json={'reason': 'Too late'}).status_code == 400


@pytest.mark.parametrize('stage,field,expected,balances', [
    ('genuine', 'ai_result_deadline', 'auto_accepted_ai_result', (-12500, 8500, 4000)),
    ('reupload', 'reupload_deadline', 'awaiting_human', (-12500, 0, 0, 12500)),
    ('recheck', 'recheck_deadline', 'auto_approved_after_reupload', (-10000, 8500, 1500)),
])
@pytest.mark.smoke
def test_real_rejection_deadline_paths(flow, stage, field, expected, balances):
    flow.reject('supports' if stage == 'genuine' else 'unclear')
    if stage == 'recheck':
        flow.reupload()
    with flow.store() as db:
        setattr(db.query(PhotoReview).filter_by(job_id=flow.job_id).one(), field, utcnow() - timedelta(seconds=1))
        db.commit()
    assert flow.call('POST', '/admin/scheduler/run', uid=1)['changed'] == 1
    assert flow.call('POST', '/admin/scheduler/run', uid=1)['changed'] == 0
    assert flow.review().status.value == expected
    assert flow.profile().strikes == 0
    flow.balances(*balances)


def test_original_and_reupload_rounds_and_deletion_rules(flow):
    original = flow.call('GET', f'/jobs/{flow.job_id}/photos')[0]
    flow.reject('unclear')
    assert flow.client.delete(f'/photos/{original["id"]}', headers=flow.headers(5)).status_code == 400
    replacement = flow.upload()
    assert flow.client.delete(f'/photos/{replacement["id"]}', headers=flow.headers(5)).status_code == 200
    flow.reupload()
    flow.call('POST', f'/jobs/{flow.job_id}/photo-review/recheck/reject')
    detail = flow.call('GET', f'/admin/photo-reviews/{flow.job_id}', uid=1)
    assert sum(photo['round'] == 'original' for photo in detail['photos']) == 2
    assert sum(photo['round'] == 'reupload' for photo in detail['photos']) == 1


@pytest.mark.smoke
def test_three_human_strikes_suspend_and_unsuspend_sets_probation(client, headers, store, monkeypatch):
    jobs = []
    for _ in range(3):
        flow = Inspection(client, headers, store, monkeypatch).start()
        flow.reject()
        flow.dispute_ai()
        flow.decide('not_genuine')
        jobs.append(flow.job_id)
    assert flow.profile().strikes == 3 and flow.profile().suspended is True
    assert client.get('/jobs/open', headers=headers(5)).status_code == 403
    new_job = Inspection(client, headers, store, monkeypatch)
    new_job.create()
    assert client.post(f'/jobs/{new_job.job_id}/accept', headers=headers(5)).status_code == 403
    queue = flow.call('GET', '/admin/reviewers/suspended', uid=1)
    assert any(row['user_id'] == 5 for row in queue)
    response = flow.call('POST', '/admin/reviewers/5/unsuspend', uid=1, json={'notes': 'Reviewer is back on probation'})
    assert response['strikes'] == 2 and response['suspended'] is False
    new_job.accept()


def test_overturned_third_strike_lifts_suspension(client, headers, store, monkeypatch):
    with store() as db:
        db.query(ReviewerProfile).filter_by(user_id=5).one().strikes = 2
        db.commit()
    flow = Inspection(client, headers, store, monkeypatch).start()
    flow.reject()
    flow.dispute_ai()
    flow.decide('not_genuine')
    assert flow.profile().suspended is True
    flow.call('POST', f'/jobs/{flow.job_id}/appeal', uid=5, json={'reason': 'Please reconsider this strike'})
    flow.call('POST', f'/admin/appeals/{flow.job_id}/decide', uid=1, json={'decision': 'overturn', 'notes': 'Evidence supports the reviewer'})
    assert flow.profile().strikes == 2 and flow.profile().suspended is False
    flow.balances(-20000, 8500, 11500)


@pytest.mark.parametrize('action', ['complete', 'delete', 'cap', 'rounds'])
@pytest.mark.smoke
def test_reupload_membership_does_not_depend_on_timestamp_precision(flow, action):
    flow.reject('unclear')
    stamp = flow.review().created_at
    replacement = flow.upload()
    with flow.store() as db:
        db.get(Photo, replacement['id']).created_at = stamp
        db.commit()
    if action == 'complete':
        assert flow.call('POST', f'/jobs/{flow.job_id}/photo-review/reupload-complete', uid=5)['status'] == 'awaiting_renter_recheck'
    elif action == 'delete':
        assert flow.call('DELETE', f'/photos/{replacement["id"]}', uid=5)['deleted'] == replacement['id']
    elif action == 'cap':
        for _ in range(2):
            photo = flow.upload()
            with flow.store() as db:
                db.get(Photo, photo['id']).created_at = stamp
                db.commit()
        response = flow.client.post(f'/jobs/{flow.job_id}/photos', headers=flow.headers(5), data={'checklist_item': CHECKLIST[0]}, files={'file': ('fourth.jpg', image_bytes(), 'image/jpeg')})
        assert response.status_code == 400
    else:
        detail = flow.call('GET', f'/admin/photo-reviews/{flow.job_id}', uid=1)
        assert next(row for row in detail['photos'] if row['id'] == replacement['id'])['round'] == 'reupload'


@pytest.mark.smoke
def test_original_photo_is_not_a_reupload_even_if_clock_moves_backwards(flow):
    original = flow.call('GET', f'/jobs/{flow.job_id}/photos')[0]
    flow.reject('unclear')
    with flow.store() as db:
        db.get(Photo, original['id']).created_at = flow.review().created_at + timedelta(seconds=1)
        db.commit()
    assert flow.client.post(f'/jobs/{flow.job_id}/photo-review/reupload-complete', headers=flow.headers(5)).status_code == 400
    assert flow.client.delete(f'/photos/{original["id"]}', headers=flow.headers(5)).status_code == 400
