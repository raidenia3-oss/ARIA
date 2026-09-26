from pkgutil import extend_path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

__path__ = extend_path(__path__, __name__)


@dataclass
class VideoAnalysisResult:
    video_path: str = ""
    url: str = ""
    platform: str = ""
    title: str = ""
    duration_seconds: float = 0.0
    transcription: Dict[str, Any] = field(default_factory=dict)
    visual_analysis: Dict[str, Any] = field(default_factory=dict)
    topics: List[Dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    importance: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    key_moments: List[Dict[str, Any]] = field(default_factory=list)
    saved: bool = False
    content_id: str = ""
    processing_time: float = 0.0
