from datetime import datetime, timedelta
from typing import Any, Union
from jose import jwt
from passlib.context import CryptContext
import secrets

from app.core.config import settings

hash_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"


def create_access_token(
        subject: Union[str, Any],
        expires_delta: timedelta = None
) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject), "iat": datetime.utcnow()}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_api_key(
        owner_id: int
) -> str:
    return secrets.token_hex()


def verify_hashed_secret(plain_secret: str, hashed_secret: str) -> bool:
    return hash_context.verify(plain_secret, hashed_secret)


def get_secret_hash(secret: str) -> str:
    return hash_context.hash(secret)
