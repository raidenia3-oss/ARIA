# -*- coding: utf-8 -*-
"""Tests basicos de ARIA Chibi. Logica sin GUI; render con QT offscreen."""
import os
import sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# localizar chibi.py este test en tests/ o dentro de ARIA_APP
_here = os.path.dirname(os.path.abspath(__file__))
for _c in (_here, os.path.join(_here, "..", "ARIA_APP"), os.path.join(_here, "ARIA_APP")):
    if os.path.isfile(os.path.join(_c, "chibi.py")):
        sys.path.insert(0, _c)
        break

from PyQt5.QtWidgets import QApplication

import chibi as C

# Un QApplication vivo para los tests que pintan (QFont/QPainter).
_APP = QApplication.instance() or QApplication([])


def _ctrl():
    reloj = [1000.0]
    c = C.ChibiController(clock=lambda: reloj[0])
    return c, reloj


def test_estado_inicial():
    c, _ = _ctrl()
    assert c.estado == C.ChibiState.IDLE


def test_eventos_nucleo():
    c, _ = _ctrl()
    c.on_pensando(); assert c.estado == C.ChibiState.THINK
    c.on_escuchando(); assert c.estado == C.ChibiState.LISTEN
    c.on_respondio(); assert c.estado == C.ChibiState.TALK


def test_react_one_shot_vuelve():
    c, _ = _ctrl()
    c.on_idle(); c.click()
    assert c.estado == C.ChibiState.REACT
    for _ in range(c.cfg[C.ChibiState.REACT].frames):
        c.tick_anim()
    assert c.estado != C.ChibiState.REACT


def test_idle_a_walk_y_sleep():
    c, reloj = _ctrl()
    c.on_idle(); c.ultimo_evento = reloj[0]
    reloj[0] += C.ChibiController.T_WALK + 1
    c.tick_idle(); assert c.estado == C.ChibiState.WALK
    c.set_estado(C.ChibiState.IDLE); c.ultimo_evento = reloj[0] - (C.ChibiController.T_SLEEP + 5)
    reloj[0] += 1
    c.tick_idle(); assert c.estado == C.ChibiState.SLEEP


def test_interaccion_despierta():
    c, reloj = _ctrl()
    c.set_estado(C.ChibiState.SLEEP)
    c.interaccion()
    assert c.estado == C.ChibiState.IDLE


def test_sprite_placeholder_y_frames():
    sh = C.SpriteSheet("", 160, 160)
    assert sh.placeholder is True
    assert not sh.pixmap.isNull()
    r = sh.frame(C.ChibiState.WALK, 2)
    assert r.width() == 160 and r.height() == 160


def test_fx_expira():
    fx = C.EmocionFX(clock=lambda: 0.0)
    fx.disparar("estrella", dur=1.0)
    assert len(fx.activos) == 1
    # dibujar pasado el tiempo lo elimina
    from PyQt5.QtGui import QImage, QPainter
    from PyQt5.QtCore import QRect
    img = QImage(160, 160, QImage.Format_ARGB32_Premultiplied)
    p = QPainter(img)
    fx.dibujar(p, QRect(0, 0, 160, 160), now=2.0)
    p.end()
    assert len(fx.activos) == 0


def test_persistencia_roundtrip(tmp_path):
    ruta = str(tmp_path / "estado.json")
    pers = C.ChibiPersistence(ruta)
    pers.save({"pos": [10, 20], "tema": "cyberpunk", "estado": "idle"})
    d = pers.load()
    assert d["pos"] == [10, 20] and d["tema"] == "cyberpunk"
