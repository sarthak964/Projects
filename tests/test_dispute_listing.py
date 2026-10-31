from app.models.dispute import Dispute

def test_dispute_listing_permissions_paging_and_filter(client,headers,make_job,store):
    first,second=make_job(),make_job()
    with store() as db:
        db.add_all([Dispute(job_id=first,renter_id=4,reason='First'),Dispute(job_id=second,renter_id=7,reason='Second')]);db.commit()
    assert client.get('/disputes/').status_code==401
    assert client.get('/disputes/',headers=headers(5)).status_code==403
    own=client.get('/disputes/',headers=headers(4)).json()
    assert len(own)==1 and own[0]['job_id']==first
    assert client.get(f'/disputes/?job_id={second}',headers=headers(4)).json()==[]
    assert len(client.get('/disputes/',headers=headers(1)).json())==2
    assert client.get('/disputes/?limit=1&offset=1',headers=headers(1)).json()[0]['job_id']==first
    assert client.get('/disputes/?limit=101',headers=headers(1)).status_code==422
