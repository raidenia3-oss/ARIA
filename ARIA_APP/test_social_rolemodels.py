import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import social_rolemodels as sr

def test_lecciones():
    assert len(sr.LECCIONES["patrick_jane"]) >= 5
    assert len(sr.LECCIONES["barney_stinson"]) >= 5

def test_videos():
    assert sr.videos_referencia("patrick_jane")
    assert sr.videos_referencia("barney_stinson")

def test_simulacion():
    r = sr.simulacion_citas("hola")
    assert "guia" in r and "respuesta" in r

def test_investigar():
    r = sr.investigar_personaje("patrick_jane")
    assert r["videos"] and r["lecciones"]
