from fastapi import HTTPException

from app.core.config import ENVIRONMENT


def send_otp_sms(phone: str, code: str) -> None:
    """
    Development: prints the code to the server console instead of sending it.
    Production: plug a real SMS provider in here (MSG91, Twilio, etc.).
    """
    if ENVIRONMENT == "development":
        print(f"[DEV OTP] {phone} -> {code}")
        return

    raise HTTPException(status_code=501, detail="SMS provider is not configured yet")
