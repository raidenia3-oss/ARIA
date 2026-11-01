import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import intent_router as ir

def test_intent():
    assert ir.detectar("analiza reel") == "reel"
    assert ir.detectar("practica cita") == "social"