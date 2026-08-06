"""Self-serve tenant signup/login/password-reset -- an alternative to
manually running scripts/create_tenant.py by hand. Only relevant to a
seller running one shared multi-tenant instance; a single self-hosted buyer
never needs any of this (see auth.py's DEFAULT_TENANT_ID fallback).

Login/signup hand back a tenant's API key (the same credential used
everywhere else via `Authorization: Bearer <key>`) rather than issuing a
separate session token -- this app has exactly one credential type. Since
only the key's hash is ever stored (storage.py), login can't recover the
original key issued at signup; it issues a fresh one instead (see
storage.rotate_api_key), which invalidates whichever key was active before.
That's a real tradeoff -- logging in on a second device signs the first one
out -- documented rather than hidden, since it's the kind of thing that's
confusing to hit by surprise.
"""

from fastapi import APIRouter, HTTPException, Request
from loguru import logger
from pydantic import BaseModel, EmailStr, Field

from .. import storage
from ..config import APP_BASE_URL, PASSWORD_RESET_TTL_MINUTES, RATE_LIMIT_AUTH
from ..middleware import limiter
from ..services.password import hash_password, validate_password_strength, verify_password
from ..services.reset_email import send_password_reset_email

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=200)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(max_length=200)


class TenantAuthResponse(BaseModel):
    tenant_id: str
    name: str
    api_key: str


@router.post("/signup", response_model=TenantAuthResponse)
@limiter.limit(RATE_LIMIT_AUTH)
def signup(request: Request, payload: SignupRequest):
    if storage.get_tenant_by_email(payload.email) is not None:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")
    try:
        validate_password_strength(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    tenant, api_key = storage.create_tenant(
        payload.name, email=payload.email, password_hash=hash_password(payload.password)
    )
    logger.info("New self-serve signup: {} ({})", tenant.name, payload.email)
    return TenantAuthResponse(tenant_id=tenant.id, name=tenant.name, api_key=api_key)


@router.post("/login", response_model=TenantAuthResponse)
@limiter.limit(RATE_LIMIT_AUTH)
def login(request: Request, payload: LoginRequest):
    auth = storage.get_tenant_auth_by_email(payload.email)
    # Same error either way -- don't let a different message for "no such
    # account" vs. "wrong password" leak which emails have accounts.
    if auth is None or not verify_password(payload.password, auth[1]):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    tenant, _ = auth
    api_key = storage.rotate_api_key(tenant.id)
    return TenantAuthResponse(tenant_id=tenant.id, name=tenant.name, api_key=api_key)


@router.post("/forgot-password")
@limiter.limit(RATE_LIMIT_AUTH)
def forgot_password(request: Request, payload: ForgotPasswordRequest):
    tenant = storage.get_tenant_by_email(payload.email)
    if tenant is not None:
        token = storage.create_password_reset(tenant.id, ttl_seconds=PASSWORD_RESET_TTL_MINUTES * 60)
        reset_url = f"{APP_BASE_URL}/reset-password?token={token}"
        send_password_reset_email(payload.email, reset_url, PASSWORD_RESET_TTL_MINUTES)
    # Always the same response whether or not the email has an account --
    # avoids leaking which emails are registered.
    return {"detail": "If that email has an account, a reset link is on its way."}


@router.post("/reset-password", response_model=TenantAuthResponse)
@limiter.limit(RATE_LIMIT_AUTH)
def reset_password(request: Request, payload: ResetPasswordRequest):
    tenant_id = storage.consume_password_reset(payload.token)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="That reset link is invalid or has expired.")
    try:
        validate_password_strength(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    storage.update_tenant_password(tenant_id, hash_password(payload.password))
    api_key = storage.rotate_api_key(tenant_id)
    tenant = storage.get_tenant_by_id(tenant_id)
    name = tenant.name if tenant else ""
    return TenantAuthResponse(tenant_id=tenant_id, name=name, api_key=api_key)
