"""AriaAdaptiveEngine wrapper — re-exporta desde ARIA_APP/backend/aria_adaptive_engine.py."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.aria_adaptive_engine import AriaAdaptiveEngine

__all__ = ["AriaAdaptiveEngine"]
