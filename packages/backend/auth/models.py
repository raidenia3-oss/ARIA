from sqlalchemy import Column, String, DateTime, Boolean, Integer, LargeBinary
from pydantic import BaseModel, EmailStr
from datetime import datetime
import uuid

try:
    from backend.database import Base
except Exception:
    from sqlalchemy.ext.declarative import declarative_base
    Base = declarative_base()

class User(Base):
    """Modelo SQLAlchemy para usuarios"""
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, index=True, nullable=False)
    # `index=True` se omite a proposito: `backend/models.py:10` ya declara
    # `email` con `unique=True, index=True` sobre la MISMA tabla (esta clase usa
    # `extend_existing`). Redecirlo aqui creaba un segundo `Index("ix_users_email")`
    # en la misma Table, y `Base.metadata.create_all` emitia dos veces
    # `CREATE UNIQUE INDEX ix_users_email`: el segundo fallaba con
    # `index ix_users_email already exists` al arrancar contra una DB nueva.
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(LargeBinary, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    theme = Column(String, default="dark")
    language = Column(String, default="es")
    timezone = Column(String, default="UTC")


class Session(Base):
    """Modelo SQLAlchemy para sesiones"""
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)


class UserCreate(BaseModel):
    """Request para crear usuario"""
    username: str
    email: EmailStr
    password: str
    full_name: str = None


class UserLogin(BaseModel):
    """Request para login"""
    username: str
    password: str


class UserResponse(BaseModel):
    """Response con datos del usuario"""
    id: str
    username: str
    email: str
    full_name: str = None
    is_active: bool
    is_admin: bool
    theme: str
    language: str
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Response con token"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class SessionResponse(BaseModel):
    """Response de sesión"""
    id: str
    user_id: str
    created_at: datetime
    ip_address: str = None
    user_agent: str = None
    expires_at: datetime
