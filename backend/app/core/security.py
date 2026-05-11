from datetime import datetime, timedelta, timezone
from typing import Any
import secrets
import uuid

from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings
from .redis import get_redis

pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: Any, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    return jwt.encode(
        {"sub": str(subject), "exp": expire},
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(subject: Any) -> tuple[str, str]:
    """Returns (encoded_token, jti). Caller must store jti in Redis."""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    jti = str(uuid.uuid4())
    token = jwt.encode(
        {"sub": str(subject), "exp": expire, "type": "refresh", "jti": jti},
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token, jti


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


def generate_verification_token() -> str:
    return secrets.token_urlsafe(32)


async def store_refresh_jti(jti: str) -> None:
    r = await get_redis()
    ttl = settings.refresh_token_expire_days * 86400
    await r.setex(f"refresh:{jti}", ttl, "1")


async def revoke_refresh_jti(jti: str) -> None:
    r = await get_redis()
    await r.delete(f"refresh:{jti}")


async def is_refresh_jti_valid(jti: str) -> bool:
    r = await get_redis()
    return bool(await r.exists(f"refresh:{jti}"))
