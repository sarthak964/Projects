import os
import sys
from pathlib import Path

os.environ['OPENAI_API_KEY'] = 'test-no-network'
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['SCHEDULER_ENABLED'] = 'false'
os.environ['ENVIRONMENT'] = 'development'
os.environ['JWT_SECRET'] = 'isolated-tests-only-secret'
os.environ['ADMIN_PHONES'] = '9999999999'
os.environ['LANGCHAIN_TRACING_V2'] = 'false'
os.environ['LANGSMITH_TRACING'] = 'false'
os.environ['CORS_ALLOWED_ORIGINS'] = 'http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173'
for key, value in {
    'ACCEPT_WINDOW_HOURS': '24', 'SUBMIT_WINDOW_HOURS': '48',
    'PHOTO_REVIEW_WINDOW_HOURS': '48', 'RECHECK_WINDOW_HOURS': '24',
    'REUPLOAD_WINDOW_HOURS': '24', 'APPEAL_WINDOW_HOURS': '48',
    'DISPUTE_WINDOW_DAYS': '30', 'STRIKES_BEFORE_SUSPENSION': '3',
    'HUMAN_REVIEW_FEE': '75', 'PLATFORM_COMMISSION_RATE': '0.15',
    'AI_COST_PER_PHOTO_INR': '0.5', 'PHOTO_REVIEW_FEE_MULTIPLIER': '6',
    'PHOTO_REVIEW_FEE_MIN': '25', 'PHOTO_REVIEW_FEE_MAX': '60',
    'OTP_EXPIRE_MINUTES': '5', 'OTP_MAX_ATTEMPTS': '5',
    'OTP_RESEND_COOLDOWN_SECONDS': '30',
    'MAX_SERVICE_DISTANCE_KM': '50',
}.items():
    os.environ[key] = value
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models
from app.core import database
from app.core.security import create_access_token
from app.core.time import utcnow
from app.main import app
from app.models import User, UserRole, ReviewerProfile, Job, JobStatus, Payment, PaymentStatus, PhotoReview
from datetime import timedelta


@pytest.fixture
def store(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    database.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(database, 'SessionLocal', factory)
    from app.services import scheduler
    monkeypatch.setattr(scheduler, 'SessionLocal', factory)
    with factory() as db:
        for uid, role in [(1, UserRole.admin), (4, UserRole.renter), (5, UserRole.reviewer), (6, UserRole.reviewer), (7, UserRole.renter)]:
            db.add(User(id=uid, phone=str(9000000000 + uid), role=role))
        for uid in (5, 6):
            db.add(ReviewerProfile(user_id=uid, home_lat=12.97, home_lng=77.59))
        db.commit()
    yield factory
    engine.dispose()


@pytest.fixture
def client(store):
    with TestClient(app) as client:
        yield client


@pytest.fixture
def headers():
    def token(uid):
        role = 'admin' if uid == 1 else 'reviewer' if uid in (5, 6) else 'renter'
        return {'Authorization': 'Bearer ' + create_access_token(uid, role)}
    return token


@pytest.fixture
def make_job(store):
    def create(status=JobStatus.verified, payment_status=PaymentStatus.held, review_status=None):
        with store() as db:
            job = Job(
                renter_id=4, reviewer_id=None if status == JobStatus.requested else 5,
                address='Test property', geocoded_lat=12.97, geocoded_lng=77.59,
                checklist_json=['AC working', 'Fire extinguisher'], price=100.0,
                status=status, accept_deadline=utcnow() + timedelta(hours=1),
                submit_deadline=utcnow() + timedelta(hours=1),
                verified_at=utcnow() if status == JobStatus.verified else None,
            )
            db.add(job)
            db.commit()
            if payment_status is not None:
                db.add(Payment(job_id=job.id, amount=100.0, status=payment_status))
            if review_status is not None:
                db.add(PhotoReview(job_id=job.id, status=review_status, rejected_items=['AC working'], fee_amount=25.0, fee_status='held'))
            db.commit()
            return job.id
    return create


@pytest.fixture(autouse=True)
def no_external_calls(monkeypatch):
    from unittest.mock import MagicMock
    from app.services import verification_nodes
    from app.routers import report, photo_review, dispute, support
    from app.services import geocoding
    for module, name in [(verification_nodes, 'llm'), (verification_nodes, 'structured_llm'), (report, 'verification_graph'), (dispute, 'dispute_graph'), (support, 'support_graph')]:
        mock = MagicMock()
        mock.invoke.side_effect = AssertionError('Unexpected external AI call in test')
        monkeypatch.setattr(module, name, mock)
    monkeypatch.setattr(photo_review, 'check_photos', MagicMock(side_effect=AssertionError('Unexpected vision call')))
    monkeypatch.setattr(geocoding, 'geocode_address', MagicMock(side_effect=AssertionError('Unexpected geocoding call')))
    from app.routers import auth, job, reviewer_profile
    monkeypatch.setattr(job, 'geocode_address', MagicMock(side_effect=AssertionError('Unexpected geocoding call')))
    monkeypatch.setattr(reviewer_profile, 'geocode_address', MagicMock(side_effect=AssertionError('Unexpected geocoding call')))
    monkeypatch.setattr(auth, 'send_otp_sms', MagicMock())
    import requests
    import httpx
    def blocked(*args, **kwargs):
        raise AssertionError('External HTTP is disabled in isolated tests')
    async def blocked_async(*args, **kwargs):
        raise AssertionError('External HTTP is disabled in isolated tests')
    monkeypatch.setattr(requests.sessions.Session, 'request', blocked)
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', blocked)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, 'handle_async_request', blocked_async)


@pytest.fixture(autouse=True)
def isolated_uploads(monkeypatch, tmp_path):
    from app.core import config
    from app.routers import photo, photo_review
    directory = tmp_path / 'uploads'
    for module in (config, photo, photo_review):
        monkeypatch.setattr(module, 'UPLOAD_DIR', directory)
