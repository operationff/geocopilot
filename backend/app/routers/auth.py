from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from authlib.integrations.httpx_client import AsyncOAuth2Client

from app.core.database import get_db
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    decode_token, generate_verification_token,
    store_refresh_jti, revoke_refresh_jti, is_refresh_jti_valid,
)
from app.core.config import settings
from app.core.deps import get_current_user
from app.core.redis import get_redis
from app.models.user import User
from app.services.email import send_verification_email

router = APIRouter(prefix="/api/auth", tags=["auth"])

_OAUTH_STATE_TTL = 600  # 10 minutes


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    verification_token = generate_verification_token()
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        verification_token=verification_token,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    await send_verification_email(user.email, user.full_name, verification_token)

    refresh_token, jti = create_refresh_token(user.id)
    await store_refresh_jti(jti)
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=refresh_token,
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    refresh_token, jti = create_refresh_token(user.id)
    await store_refresh_jti(jti)
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=refresh_token,
    )


@router.get("/verify-email")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.verification_token == token))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    user.is_verified = True
    user.verification_token = None
    await db.commit()
    return {"message": "Email verified successfully"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshRequest):
    data = decode_token(payload.refresh_token)
    if not data or data.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    jti = data.get("jti")
    if not jti or not await is_refresh_jti_valid(jti):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")

    # Rotate: revoke old token, issue new one
    await revoke_refresh_jti(jti)

    user_id = data.get("sub")
    new_refresh_token, new_jti = create_refresh_token(user_id)
    await store_refresh_jti(new_jti)
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=new_refresh_token,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: LogoutRequest):
    data = decode_token(payload.refresh_token)
    if data and data.get("type") == "refresh":
        jti = data.get("jti")
        if jti:
            await revoke_refresh_jti(jti)


@router.get("/google")
async def google_login():
    client = AsyncOAuth2Client(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        redirect_uri=settings.google_redirect_uri,
    )
    uri, state = client.create_authorization_url(
        "https://accounts.google.com/o/oauth2/v2/auth",
        scope="openid email profile",
        access_type="offline",
    )
    r = await get_redis()
    await r.setex(f"oauth_state:{state}", _OAUTH_STATE_TTL, "1")
    return {"authorization_url": uri, "state": state}


@router.get("/google/callback", response_model=TokenResponse)
async def google_callback(code: str, state: str, db: AsyncSession = Depends(get_db)):
    r = await get_redis()
    state_key = f"oauth_state:{state}"
    if not await r.exists(state_key):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    await r.delete(state_key)

    client = AsyncOAuth2Client(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        redirect_uri=settings.google_redirect_uri,
    )
    await client.fetch_token(
        "https://oauth2.googleapis.com/token", code=code
    )
    userinfo_resp = await client.get("https://openidconnect.googleapis.com/v1/userinfo")
    userinfo = userinfo_resp.json()

    google_id = userinfo["sub"]
    email = userinfo["email"]
    full_name = userinfo.get("name", email)
    avatar_url = userinfo.get("picture")

    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    if not user:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

    if user:
        user.google_id = google_id
        user.is_verified = True
        if avatar_url:
            user.avatar_url = avatar_url
    else:
        user = User(
            email=email,
            full_name=full_name,
            google_id=google_id,
            avatar_url=avatar_url,
            is_verified=True,
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)

    refresh_token, jti = create_refresh_token(user.id)
    await store_refresh_jti(jti)
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=refresh_token,
    )


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_verified": current_user.is_verified,
        "avatar_url": current_user.avatar_url,
    }

