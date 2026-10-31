import pytest
from app.models import JobStatus, Rating, Photo, PhotoReview

def test_profile_read_for_self_and_admin(client,headers):
    for uid in (5,1):
        response=client.get('/reviewers/5/profile',headers=headers(uid))
        assert response.status_code==200
        assert response.json()['user_id']==5
        assert response.json()['strikes']==0
        assert response.json()['suspended'] is False

@pytest.mark.parametrize('uid',[4,6,7])
def test_profile_read_denies_other_accounts(client,headers,uid):
    assert client.get('/reviewers/5/profile',headers=headers(uid)).status_code==403

def test_profile_read_requires_login_and_handles_missing_reviewer(client,headers):
    assert client.get('/reviewers/5/profile').status_code==401
    assert client.get('/reviewers/999/profile',headers=headers(1)).status_code==404

def test_job_rating_read_empty_then_saved(client,headers,make_job,store):
    jid=make_job(status=JobStatus.paid,payment_status='released')
    assert client.get(f'/ratings/job/{jid}',headers=headers(4)).json() is None
    response=client.post('/ratings/',headers=headers(4),json={'job_id':jid,'score':4,'comment':'Helpful report'})
    assert response.status_code==200
    for uid in (1,4,5):
        result=client.get(f'/ratings/job/{jid}',headers=headers(uid))
        assert result.status_code==200
        assert result.json()['score']==4

@pytest.mark.parametrize('uid',[6,7])
def test_job_rating_read_denies_nonparticipants(client,headers,make_job,uid):
    jid=make_job()
    assert client.get(f'/ratings/job/{jid}',headers=headers(uid)).status_code==403

def test_photo_round_labels_use_explicit_review_link(client,headers,make_job,store):
    jid=make_job()
    with store() as db:
        review=PhotoReview(job_id=jid,status='awaiting_reupload',rejected_items=['AC working'],fee_amount=25,fee_status='held')
        db.add(review);db.flush()
        db.add_all([Photo(job_id=jid,uploader_id=5,checklist_item='AC working',stored_name='original.jpg',content_type='image/jpeg',size_bytes=10),Photo(job_id=jid,uploader_id=5,checklist_item='AC working',stored_name='new.jpg',content_type='image/jpeg',size_bytes=10,photo_review_id=review.id)])
        db.commit()
    result=client.get(f'/jobs/{jid}/photos',headers=headers(4))
    assert result.status_code==200
    assert [p['round'] for p in result.json()]==['original','reupload']
