import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import emotion_engine as ee

def test_emocion():
    assert ee.detectar("estoy triste") == "tristeza"
    assert ee.estrategia("tristeza")