from datetime import timedelta

import jwt
import pytest

from app.core.config import JWT_ALGORITHM, JWT_SECRET
from app.core.time import utcnow
from app.models import OtpCode, User


def request_code(client, phone):
    response = client.post('/auth/request-otp', json={'phone': phone})
    assert response.status_code == 200
    return response.json()['dev_otp']


@pytest.mark.smoke
@pytest.mark.parametrize('role', ['renter', 'reviewer'])
def test_otp_signup_login_and_me(client, store, role, monkeypatch):
    from app.routers import auth
    monkeypatch.setattr(auth, 'generate_otp', lambda: '012345')
    phone = '9000000055'
    code = request_code(client, phone)
    assert code == '012345'
    with store() as db:
        otp = db.query(OtpCode).filter_by(phone=phone).one()
        assert len(otp.code_hash) == 64 and otp.code_hash != code
        assert otp.used is False and otp.attempts == 0
    response = client.post('/auth/verify-otp', json={'phone': phone, 'code': code, 'role': role, 'name': 'Test user'})
    assert response.status_code == 200
    result = response.json()
    assert result['user']['role'] == role
    headers = {'Authorization': 'Bearer ' + result['access_token']}
    assert client.get('/auth/me', headers=headers).json()['id'] == result['user']['id']
    assert client.post('/auth/verify-otp', json={'phone': phone, 'code': code, 'role': role}).status_code == 400


def test_existing_user_cannot_promote_role(client):
    phone = '9000000004'
    code = request_code(client, phone)
    response = client.post('/auth/verify-otp', json={'phone': phone, 'code': code, 'role': 'admin'})
    assert response.status_code == 200
    assert response.json()['user']['role'] == 'renter'


def test_new_user_cannot_choose_admin(client, store):
    phone = '9000000055'
    code = request_code(client, phone)
    assert client.post('/auth/verify-otp', json={'phone': phone, 'code': code, 'role': 'admin'}).status_code == 400
    with store() as db:
        assert db.query(User).filter_by(phone=phone).count() == 0


@pytest.mark.smoke
def test_allowlisted_phone_becomes_admin(client):
    phone = '9999999999'
    code = request_code(client, phone)
    response = client.post('/auth/verify-otp', json={'phone': phone, 'code': code})
    assert response.status_code == 200
    assert response.json()['user']['role'] == 'admin'


def test_new_user_must_choose_role(client, store):
    phone = '9000000055'
    code = request_code(client, phone)
    assert client.post('/auth/verify-otp', json={'phone': phone, 'code': code}).status_code == 400
    with store() as db:
        assert db.query(User).filter_by(phone=phone).count() == 0


def test_otp_cooldown_and_resend_invalidates_old_code(client, store, monkeypatch):
    from app.routers import auth
    codes = iter(['123456', '654321'])
    monkeypatch.setattr(auth, 'generate_otp', lambda: next(codes))
    phone = '9000000004'
    assert request_code(client, phone) == '123456'
    assert client.post('/auth/request-otp', json={'phone': phone}).status_code == 429
    with store() as db:
        db.query(OtpCode).filter_by(phone=phone).one().created_at = utcnow() - timedelta(seconds=31)
        db.commit()
    assert request_code(client, phone) == '654321'
    assert client.post('/auth/verify-otp', json={'phone': phone, 'code': '123456'}).status_code == 400
    assert client.post('/auth/verify-otp', json={'phone': phone, 'code': '654321'}).status_code == 200


def test_expired_otp_rejected(client, store):
    phone = '9000000004'
    code = request_code(client, phone)
    with store() as db:
        db.query(OtpCode).filter_by(phone=phone).one().expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert client.post('/auth/verify-otp', json={'phone': phone, 'code': code}).status_code == 400


def test_wrong_otp_attempt_limit_blocks_even_correct_code(client, store):
    phone = '9000000004'
    code = request_code(client, phone)
    wrong = '000000' if code != '000000' else '111111'
    for _ in range(5):
        assert client.post('/auth/verify-otp', json={'phone': phone, 'code': wrong}).status_code == 400
    assert client.post('/auth/verify-otp', json={'phone': phone, 'code': code}).status_code == 400
    with store() as db:
        otp = db.query(OtpCode).filter_by(phone=phone).one()
        assert otp.used is True and otp.attempts == 5


def test_production_response_hides_dev_otp(client, monkeypatch):
    from app.routers import auth
    monkeypatch.setattr(auth, 'ENVIRONMENT', 'production')
    response = client.post('/auth/request-otp', json={'phone': '9000000055'})
    assert response.status_code == 200
    assert response.json()['dev_otp'] is None


@pytest.mark.parametrize('phone', ['123', 'abcdefghij', '', '+1234567890123456'])
def test_invalid_phone_is_rejected(client, phone):
    assert client.post('/auth/request-otp', json={'phone': phone}).status_code == 422


@pytest.mark.parametrize('claims,secret', [
    ({'sub': '4', 'exp': utcnow() - timedelta(seconds=5)}, JWT_SECRET),
    ({'sub': '4'}, JWT_SECRET),
    ({'sub': '4', 'exp': utcnow() + timedelta(minutes=5)}, 'wrong-test-secret'),
])
def test_expired_missing_expiry_and_wrong_signature_tokens(client, claims, secret):
    token = jwt.encode(claims, secret, algorithm=JWT_ALGORITHM)
    assert client.get('/auth/me', headers={'Authorization': 'Bearer ' + token}).status_code == 401


def test_user_detail_self_and_admin_only(client, headers):
    assert client.get('/users/4', headers=headers(4)).status_code == 200
    assert client.get('/users/4', headers=headers(1)).status_code == 200
    assert client.get('/users/4', headers=headers(5)).status_code == 403
