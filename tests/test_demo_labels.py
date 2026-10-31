from app import main


def test_health_preserves_existing_fields_and_marks_demo(client):
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok', 'app': 'TruStay', 'env': 'development', 'demo_mode': True}


def test_public_demo_info_explains_simulation_and_real_ai_costs(client):
    response = client.get('/demo-info')
    assert response.status_code == 200
    data = response.json()
    assert data['demo_mode'] is True
    assert data['payment_mode'] == 'simulated'
    assert 'No real money' in data['payment_notice']
    assert data['login_mode'] == 'development_otp'
    assert 'No SMS' in data['login_notice']
    assert 'not proof' in data['inspection_notice']
    assert 'notes only' in data['ai_notice']
    assert 'real provider charges' in data['ai_notice']
    assert 'dev_otp' not in data
    assert 'access_token' not in data


def test_non_development_metadata_does_not_offer_development_login(client, monkeypatch):
    monkeypatch.setattr(main, 'ENVIRONMENT', 'production')
    data = client.get('/demo-info').json()
    assert data['demo_mode'] is True
    assert data['login_mode'] == 'sms_not_configured'
    assert 'not exposed' in data['login_notice']


def test_otp_message_describes_actual_development_delivery(client):
    response = client.post('/auth/request-otp', json={'phone': '9000000055'})
    assert response.status_code == 200
    data = response.json()
    assert data['message'] == 'Development OTP generated. No SMS was sent.'
    assert data['dev_otp']


def test_api_docs_explain_demo_and_describe_metadata_endpoint(client):
    spec = client.get('/openapi.json').json()
    assert 'no real money' in spec['info']['description']
    assert '/demo-info' in spec['paths']
    assert spec['paths']['/demo-info']['get']['responses']['200']['content']['application/json']['schema']['$ref'].endswith('/DemoInfo')
