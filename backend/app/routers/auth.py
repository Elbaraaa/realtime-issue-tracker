from functools import cache

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import get_current_user
from ..models import User
from ..ratelimit import FailureLimiter
from ..schemas import LoginIn, RegisterIn, TokenOut, UserOut
from ..security import create_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

_settings = get_settings()
email_limiter = FailureLimiter(
    _settings.login_max_failures_per_email, _settings.login_window_seconds
)
ip_limiter = FailureLimiter(_settings.login_max_failures_per_ip, _settings.login_window_seconds)


@cache
def _dummy_hash() -> str:
    return hash_password("not-a-real-password")


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: Session = Depends(get_db)) -> TokenOut:
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")
    user = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered") from None
    return TokenOut(access_token=create_token(user.id), user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)) -> TokenOut:
    email = body.email.lower()
    ip = request.client.host if request.client else "unknown"
    # Checked before the password so a locked-out guesser learns nothing, even when right.
    wait = max(email_limiter.retry_after(email), ip_limiter.retry_after(ip))
    if wait:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed sign-in attempts. Try again later.",
            headers={"Retry-After": str(wait)},
        )

    user = db.scalar(select(User).where(User.email == email))
    # Check a dummy hash for unknown emails so response time doesn't reveal which exist.
    ok = verify_password(body.password, user.password_hash if user else _dummy_hash())
    if user is None or not ok:
        email_limiter.record_failure(email)
        ip_limiter.record_failure(ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    email_limiter.reset(email)
    return TokenOut(access_token=create_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
