from datetime import datetime, timedelta
from typing import Optional
import secrets

import bcrypt
import jwt
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

SECRET_KEY = secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

security = HTTPBearer()


class TokenData(BaseModel):
    sub: str
    exp: datetime
    scopes: list = []


class Credentials(BaseModel):
    username: str
    password: str


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.utcnow() + expires_delta
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.utcnow(),
        "scopes": ["read", "write"],
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return TokenData(
            sub=user_id,
            exp=payload.get("exp"),
            scopes=payload.get("scopes", []),
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    token = credentials.credentials
    token_data = verify_token(token)
    return token_data.sub


USERS_DB = {
    "admin": {
        "username": "admin",
        "password": hash_password("changeme123!"),
        "is_active": True,
        "roles": ["admin", "operator"],
    },
    "operator": {
        "username": "operator",
        "password": hash_password("operator123!"),
        "is_active": True,
        "roles": ["operator"],
    },
}


def authenticate_user(username: str, password: str) -> Optional[str]:
    user = USERS_DB.get(username)
    if not user or not verify_password(password, user["password"]):
        return None
    return username
