import os
import math
from pathlib import Path

from dotenv import load_dotenv

from app.core.cors import parse_allowed_origins

load_dotenv()  # reads variables from a .env file, if one exists

APP_NAME = "TruStay"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./trustay.db")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
ACCEPT_WINDOW_HOURS = int(os.getenv("ACCEPT_WINDOW_HOURS", "24"))
SUBMIT_WINDOW_HOURS = int(os.getenv("SUBMIT_WINDOW_HOURS", "48"))

# Maximum straight-line distance for new reviewer assignments.
MAX_SERVICE_DISTANCE_KM = float(os.getenv("MAX_SERVICE_DISTANCE_KM", "50"))
if not math.isfinite(MAX_SERVICE_DISTANCE_KM) or MAX_SERVICE_DISTANCE_KM <= 0:
    raise ValueError("MAX_SERVICE_DISTANCE_KM must be a finite number greater than zero")
DISPUTE_WINDOW_DAYS = int(os.getenv("DISPUTE_WINDOW_DAYS", "30"))
DISPUTE_AUTO_RESOLVE_CONFIDENCE = float(os.getenv("DISPUTE_AUTO_RESOLVE_CONFIDENCE", "0.8"))

# --- Auth ---
_DEV_JWT_SECRET = "dev-secret-change-me"
JWT_SECRET = os.getenv("JWT_SECRET", _DEV_JWT_SECRET)
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))  # 24 hours
OTP_EXPIRE_MINUTES = int(os.getenv("OTP_EXPIRE_MINUTES", "5"))
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
OTP_RESEND_COOLDOWN_SECONDS = int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", "30"))

# Comma-separated phone numbers that become admins when they log in, e.g. ADMIN_PHONES=9876543210,9123456780
ADMIN_PHONES = {p.strip() for p in os.getenv("ADMIN_PHONES", "").split(",") if p.strip()}

# --- Photo uploads ---
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(Path(__file__).resolve().parents[2] / "uploads")))
MAX_PHOTO_BYTES = int(os.getenv("MAX_PHOTO_BYTES", str(8 * 1024 * 1024)))  # 8 MB
MAX_PHOTOS_PER_ITEM = int(os.getenv("MAX_PHOTOS_PER_ITEM", "3"))

if ENVIRONMENT != "development" and JWT_SECRET == _DEV_JWT_SECRET:
    raise RuntimeError("Set a real JWT_SECRET in .env before running outside development")

# --- Photo review (renter checks the reviewer's photos) ---
PHOTO_REVIEW_WINDOW_HOURS = int(os.getenv("PHOTO_REVIEW_WINDOW_HOURS", "48"))
AI_COST_PER_PHOTO_INR = float(os.getenv("AI_COST_PER_PHOTO_INR", "0.5"))
PHOTO_REVIEW_FEE_MULTIPLIER = float(os.getenv("PHOTO_REVIEW_FEE_MULTIPLIER", "6"))
PHOTO_REVIEW_FEE_MIN = int(os.getenv("PHOTO_REVIEW_FEE_MIN", "25"))
PHOTO_REVIEW_FEE_MAX = int(os.getenv("PHOTO_REVIEW_FEE_MAX", "60"))

REUPLOAD_WINDOW_HOURS = int(os.getenv("REUPLOAD_WINDOW_HOURS", "24"))
RECHECK_WINDOW_HOURS = int(os.getenv("RECHECK_WINDOW_HOURS", "24"))

STRIKES_BEFORE_SUSPENSION = int(os.getenv("STRIKES_BEFORE_SUSPENSION", "3"))

HUMAN_REVIEW_FEE = int(os.getenv("HUMAN_REVIEW_FEE", "75"))

APPEAL_WINDOW_HOURS = int(os.getenv("APPEAL_WINDOW_HOURS", "48"))

PLATFORM_COMMISSION_RATE = float(os.getenv("PLATFORM_COMMISSION_RATE", "0.15"))

SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
SCHEDULER_INTERVAL_SECONDS = int(os.getenv("SCHEDULER_INTERVAL_SECONDS", "60"))

# Comma-separated browser origins; production has no default allowed origins.

_DEV_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173"
CORS_ALLOWED_ORIGINS = parse_allowed_origins(os.getenv(
    "CORS_ALLOWED_ORIGINS",
    _DEV_CORS_ORIGINS if ENVIRONMENT == "development" else "",
))
