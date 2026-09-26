from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from backend.auth.models import User, Session as DBSession, UserCreate, UserLogin

SECRET_KEY = "tu-secreto-super-seguro-cambiar-en-produccion"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 horas

security = HTTPBearer()


class AuthService:
    """Servicio de autenticación"""

    @staticmethod
    def hash_password(password: str) -> bytes:
        """Hashear contraseña con bcrypt"""
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode("utf-8"), salt)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: bytes) -> bool:
        """Verificar contraseña"""
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password)

    @staticmethod
    def create_access_token(data: dict, expires_delta: timedelta = None) -> tuple:
        """Crear JWT token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt, expire

    @staticmethod
    def verify_token(token: str) -> dict:
        """Verificar y decodificar JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                raise HTTPException(status_code=401, detail="Token invalido")
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expirado")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Token invalido")

    @staticmethod
    def register_user(db: Session, user_data: UserCreate) -> User:
        """Registrar nuevo usuario"""
        if db.query(User).filter(User.username == user_data.username).first():
            raise HTTPException(status_code=409, detail="Usuario ya existe")

        if db.query(User).filter(User.email == user_data.email).first():
            raise HTTPException(status_code=409, detail="Email ya registrado")

        hashed_password = AuthService.hash_password(user_data.password)
        user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            is_admin=False,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        return user

    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
        """Autenticar usuario"""
        user = db.query(User).filter(User.username == username).first()
        if not user or not AuthService.verify_password(password, user.hashed_password):
            return None
        return user

    @staticmethod
    def create_session(db: Session, user_id: str, ip_address: str = None, user_agent: str = None) -> DBSession:
        """Crear sesión de usuario"""
        user = AuthService.get_user_by_id(db, user_id)
        is_admin = user.is_admin if user else False
        token, expires_at = AuthService.create_access_token({"sub": user_id, "is_admin": is_admin})

        session = DBSession(
            user_id=user_id,
            token=token,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        db.add(session)
        db.commit()
        db.refresh(session)

        return session

    @staticmethod
    def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
        """Obtener usuario por ID"""
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def list_user_sessions(db: Session, user_id: str) -> list:
        """Listar sesiones activas de usuario"""
        return db.query(DBSession).filter(
            DBSession.user_id == user_id,
            DBSession.is_active == True,
        ).all()

    @staticmethod
    def invalidate_session(db: Session, token: str) -> bool:
        """Invalidar sesión (logout)"""
        session = db.query(DBSession).filter(DBSession.token == token).first()
        if session:
            session.is_active = False
            db.commit()
            return True
        return False


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Obtener usuario actual desde token"""
    token = credentials.credentials
    payload = AuthService.verify_token(token)
    return payload


async def get_current_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Verificar que usuario sea admin"""
    if not current_user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Se requieren permisos de admin")
    return current_user
