"""Models — Modelos de datos"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class Message:
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: Optional[str] = None


@dataclass
class Intent:
    text: str
    intent_type: str
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)


@dataclass
class Skill:
    name: str
    description: str
    handler: callable = None
    category: str = "general"
    enabled: bool = True
