import ast
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtWidgets import QApplication

import ARIA_APP.ui.nucleo_v2 as nucleo_v2


def test_render_states_not_empty():
    app = QApplication.instance() or QApplication([])
    nucleo = nucleo_v2.Nucleo()
    estados = ["reposo", "escuchando", "pensando", "hablando", "alerta"]
    for estado in estados:
        img = QImage(400, 400, QImage.Format_ARGB32_Premultiplied)
        img.fill(0)
        p = QPainter(img)
        nucleo.paint(p, QRectF(0, 0, 400, 400), 1.0, estado, 0.5)
        p.end()
        assert not img.isNull()
        assert img.width() == 400 and img.height() == 400
        assert any(img.pixel(x, y) != 0 for x in range(0, 400, 20) for y in range(0, 400, 20))


def test_baja_faster_than_alta():
    app = QApplication.instance() or QApplication([])
    alta = nucleo_v2.Nucleo(n=520)
    baja = nucleo_v2.Nucleo(n=120)
    def medir(nucleo, frames=8):
        img = QImage(400, 400, QImage.Format_ARGB32_Premultiplied)
        start = time.perf_counter()
        for i in range(frames):
            img.fill(0)
            p = QPainter(img)
            nucleo.paint(p, QRectF(0, 0, 400, 400), i / 30.0, "hablando", 0.7)
            p.end()
        return (time.perf_counter() - start) / frames
    assert medir(baja) < medir(alta)


def test_imports_allowed():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ARIA_APP", "ui", "nucleo_v2.py"))
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    allowed = {"math", "random", "time", "PyQt5"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] in allowed
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert node.module.split(".")[0] in allowed
