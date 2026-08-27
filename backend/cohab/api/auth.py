"""POST /auth/register, /verify, /login, /logout — build plan §4 Phase 4.

Thin per CLAUDE.md: validate (Pydantic), call `AuthService`, serialise. The
session cookie is set here, not in the service — cookies are an HTTP concern.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from cohab.api.deps import get_current_user, get_db
from cohab.api.schemas import (
    AccountUpdateRequest,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    ResendOTPRequest,
    UserOut,
    VerifyOTPRequest,
)
from cohab.core.config import COOKIE_SECURE, SESSION_COOKIE_NAME, SESSION_TTL_DAYS
from cohab.core.security import create_session_token
from cohab.models import User
from cohab.services.auth import (
    AccountNotActive,
    AlreadyVerified,
    AuthService,
    BlankFullName,
    EmailAlreadyRegistered,
    InvalidCredentials,
    InvalidOTP,
    OTPExpired,
    ResendTooSoon,
    TooManyOTPAttempts,
    UnknownEmailDomain,
    UserNotFound,
    update_account,
)
from cohab.services.otp import OTPDeliveryFailed, get_otp_sender

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("cohab.auth")


def _set_session_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=create_session_token(user.id),
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        max_age=SESSION_TTL_DAYS * 24 * 60 * 60,
        path="/",
    )


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    service = AuthService(db, get_otp_sender())
    try:
        user = service.register(
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            gender=body.gender,
            seeker_type=body.seeker_type,
            course=body.course,
            phone_number=body.phone_number,
        )
    except UnknownEmailDomain:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "email domain is not a registered institution")
    except EmailAlreadyRegistered:
        raise HTTPException(status.HTTP_409_CONFLICT, "this email is already registered")
    except OTPDeliveryFailed as exc:
        logger.error("OTP delivery failed: %s", str(exc).replace(body.email, "[email]"))
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "couldn't send the verification email — try again shortly")
    return RegisterResponse(user_id=user.id)


@router.post("/resend-otp", response_model=RegisterResponse)
def resend_otp(body: ResendOTPRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    service = AuthService(db, get_otp_sender())
    try:
        user = service.resend_otp(email=body.email)
    except UserNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no account found for this email")
    except AlreadyVerified:
        raise HTTPException(status.HTTP_409_CONFLICT, "this account is already verified — log in instead")
    except ResendTooSoon as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"wait a moment before requesting another code ({exc})")
    except OTPDeliveryFailed as exc:
        logger.error("OTP delivery failed: %s", str(exc).replace(body.email, "[email]"))
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "couldn't send the verification email — try again shortly")
    return RegisterResponse(user_id=user.id)


@router.post("/verify", response_model=UserOut)
def verify(body: VerifyOTPRequest, response: Response, db: Session = Depends(get_db)) -> User:
    service = AuthService(db, get_otp_sender())
    try:
        user = service.verify_otp(user_id=body.user_id, code=body.code)
    except TooManyOTPAttempts:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too many incorrect attempts")
    except OTPExpired:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "code has expired")
    except InvalidOTP:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "incorrect code")
    _set_session_cookie(response, user)
    return user


@router.post("/login", response_model=UserOut)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)) -> User:
    service = AuthService(db, get_otp_sender())
    try:
        user = service.login(email=body.email, password=body.password)
    except InvalidCredentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "incorrect email or password")
    except AccountNotActive:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "account is not active")
    _set_session_cookie(response, user)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def logout(response: Response, _user: User = Depends(get_current_user)) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.patch("/me", response_model=UserOut)
def update_me(
    body: AccountUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Edit your own account details (docs/DECISIONS.md D-13.9).

    PATCH rather than PUT: the body carries only the fields being changed,
    and omitting one must leave it untouched rather than blanking it.
    """
    try:
        return update_account(
            db,
            user,
            full_name=body.full_name,
            course=body.course,
            phone_number=body.phone_number,
        )
    except BlankFullName:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "full name cannot be blank")
