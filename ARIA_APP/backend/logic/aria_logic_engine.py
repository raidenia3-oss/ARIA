"""LogicEngine wrapper — re-exporta desde ARIA_APP/aria_logic_engine.py."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ARIA_APP.aria_logic_engine import LogicEngine

__all__ = ["LogicEngine"]
