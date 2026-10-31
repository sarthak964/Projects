from app.core.time import utcnow
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import (
    ADMIN_PHONES,
    ENVIRONMENT,
    OTP_EXPIRE_MINUTES,
    OTP_MAX_ATTEMPTS,
    OTP_RESEND_COOLDOWN_SECONDS,
)
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    generate_otp,
    hash_otp,
    verify_otp_hash,
)
from app.models.otp_code import OtpCode
from app.models.user import User, UserRole
from app.schemas.auth import OtpRequest, OtpRequestOut, OtpVerify, TokenOut
from app.schemas.user import UserOut
from app.services.sms import send_otp_sms

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/request-otp", response_model=OtpRequestOut)
def request_otp(req: OtpRequest, db: Session = Depends(get_db)):
    now = utcnow()

    latest = (
        db.query(OtpCode)
        .filter(OtpCode.phone == req.phone)
        .order_by(OtpCode.created_at.desc())
        .first()
    )
    if latest and now - latest.created_at < timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS):
        raise HTTPException(
            status_code=429,
            detail=f"Please wait {OTP_RESEND_COOLDOWN_SECONDS} seconds before requesting another code",
        )

    # Only the newest code is ever valid.
    db.query(OtpCode).filter(OtpCode.phone == req.phone, OtpCode.used == False).update(  # noqa: E712
        {"used": True, "version_id": OtpCode.version_id + 1}
    )

    code = generate_otp()
    db.add(
        OtpCode(
            phone=req.phone,
            code_hash=hash_otp(req.phone, code),
            expires_at=now + timedelta(minutes=OTP_EXPIRE_MINUTES),
        )
    )
    db.commit()

    send_otp_sms(req.phone, code)

    return OtpRequestOut(
        message=("Development OTP generated. No SMS was sent." if ENVIRONMENT == "development" else "OTP sent"),
        dev_otp=code if ENVIRONMENT == "development" else None,
    )


@router.post("/verify-otp", response_model=TokenOut)
def verify_otp(req: OtpVerify, db: Session = Depends(get_db)):
    now = utcnow()

    otp = (
        db.query(OtpCode)
        .filter(OtpCode.phone == req.phone, OtpCode.used == False)  # noqa: E712
        .order_by(OtpCode.created_at.desc())
        .first()
    )
    if otp is None or now > otp.expires_at:
        raise HTTPException(status_code=400, detail="No valid code. Please request a new one")

    if otp.attempts >= OTP_MAX_ATTEMPTS:
        otp.used = True
        db.commit()
        raise HTTPException(status_code=400, detail="Too many wrong attempts. Request a new code")

    if not verify_otp_hash(req.phone, req.code, otp.code_hash):
        otp.attempts += 1
        db.commit()
        raise HTTPException(status_code=400, detail="Incorrect code")

    otp.used = True

    is_admin_phone = req.phone in ADMIN_PHONES

    user = db.query(User).filter(User.phone == req.phone).first()
    if user is None:
        if is_admin_phone:
            new_role = UserRole.admin
        elif req.role in (UserRole.renter, UserRole.reviewer):
            new_role = req.role
        else:
            db.commit()
            raise HTTPException(
                status_code=400,
                detail="New accounts must choose a role: 'renter' or 'reviewer'",
            )
        user = User(phone=req.phone, name=req.name, role=new_role)
        db.add(user)
    elif is_admin_phone and user.role != UserRole.admin:
        user.role = UserRole.admin

    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.role.value)
    return TokenOut(access_token=token, user=user)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
