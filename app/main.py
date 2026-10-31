import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.errors import configure_errors
from app.schemas.error import ApiErrorResponse
from app.schemas.demo import DemoInfo
from app.routers import job_lists

from app.core.config import APP_NAME, ENVIRONMENT, SCHEDULER_ENABLED, CORS_ALLOWED_ORIGINS
from app.routers import auth, user, job, report, photo, photo_review, admin_review, appeal, admin_appeals, admin_scheduler, ledger, payment, reviewer_profile, dispute, rating, support
from app.services import ledger as ledger_service  # noqa: F401  (importing this starts the automatic ledger recording)
from app.services.scheduler import scheduler_loop
from app.services import notifications as notification_service  # noqa: F401
from app.routers import notification


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(scheduler_loop()) if SCHEDULER_ENABLED else None
    yield
    if task is not None:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title=APP_NAME,
    description=(
        "TruStay demonstration backend. Payments, fees, refunds and payouts "
        "are simulated database records; no real money is transferred. "
        "Development login does not send SMS. Inspection content is for demonstration. "
        "Configured AI calls may incur real provider charges. "
        "Use GET /demo-info for notices to display in the interface."
    ),
    lifespan=lifespan,
    responses={status: {"model": ApiErrorResponse} for status in (400, 401, 403, 404, 405, 409, 422, 429, 500, 502, 503)},
)
configure_errors(app)
# Added last so CORS also wraps the normalized unexpected-error response.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)

app.include_router(notification.router)
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(job_lists.router)
app.include_router(job.router)
app.include_router(report.router)
app.include_router(photo.router)
app.include_router(photo_review.router)
app.include_router(admin_review.router)
app.include_router(appeal.router)
app.include_router(admin_appeals.router)
app.include_router(admin_scheduler.router)
app.include_router(ledger.router)
app.include_router(payment.router)
app.include_router(reviewer_profile.router)
app.include_router(dispute.router)
app.include_router(rating.router)
app.include_router(support.router)


@app.get("/health")
def health_check():
    return {"status": "ok", "app": APP_NAME, "env": ENVIRONMENT, "demo_mode": True}


@app.get("/demo-info", response_model=DemoInfo, tags=["demo"])
def demo_info():
    development = ENVIRONMENT == "development"
    return DemoInfo(
        login_mode="development_otp" if development else "sms_not_configured",
        login_notice=(
            "Development login: request a temporary OTP and use dev_otp from the response. No SMS is sent."
            if development else
            "SMS login is unavailable because an SMS provider is not configured. Development OTPs are not exposed in this environment."
        ),
    )
