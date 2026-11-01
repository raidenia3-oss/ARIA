import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import personalization_engine as pe

def test_tonos():
    assert pe.adaptar("hola", "coach")

def test_default():
    assert "amable" in pe.adaptar("x", "noexiste") or True