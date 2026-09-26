"""
AURA Vision Package - Screen-Awareness & Desktop Vision Bridge
"""

from backend.vision.screen_bridge import (
    ScreenBridge,
    ScreenCaptureConfig,
    CaptureBackend,
    AnalysisMode,
    FrameData,
    VisionAnalysisResult,
    ScreenCapture,
    VisionAnalyzer,
    get_screen_bridge,
)

from backend.vision.router import router as vision_router

from backend.vision.tracker import (
    CoordinateMapper,
    DetectionResult,
    MatchMode,
    TemplateMatcher,
    TemplateRegistry,
    UIRegion,
    UITemplate,
    UITemplateTracker,
    UIMatchResult,
    get_template_tracker,
    reset_template_tracker,
)

from backend.vision.tracker import router as tracker_router

__all__ = [
    "ScreenBridge",
    "ScreenCaptureConfig",
    "CaptureBackend",
    "AnalysisMode",
    "FrameData",
    "VisionAnalysisResult",
    "ScreenCapture",
    "VisionAnalyzer",
    "get_screen_bridge",
    "vision_router",
    "CoordinateMapper",
    "DetectionResult",
    "MatchMode",
    "TemplateMatcher",
    "TemplateRegistry",
    "UIRegion",
    "UITemplate",
    "UITemplateTracker",
    "UIMatchResult",
    "get_template_tracker",
    "reset_template_tracker",
    "tracker_router",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
