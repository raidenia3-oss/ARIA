import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conversation_continuity as cc

def test_guardar_cargar():
    cc.guardar("tema", "ctx")
    d = cc.cargar()
    assert d and d["tema"] == "tema"