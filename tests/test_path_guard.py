# -*- coding: utf-8 -*-
"""Tests de path_guard: confinamiento de archivos a las raices permitidas."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

ARIA_APP = Path(__file__).resolve().parent.parent / "ARIA_APP"
if str(ARIA_APP) not in sys.path:
    sys.path.insert(0, str(ARIA_APP))

import path_guard


@pytest.fixture()
def raiz(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    monkeypatch.setenv("ARIA_FS_ROOTS", str(root))
    # canario fuera de la raiz
    canario = tmp_path / "canario.txt"
    canario.write_text("SECRETO_CANARIO", encoding="utf-8")
    monkeypatch.setattr(path_guard, "_get_roots", lambda: [root.resolve()])
    return root, canario


def _denegado(fn):
    try:
        fn()
        return False
    except PermissionError:
        return True
    except Exception:
        return True


def test_vacio_denegado(raiz):
    root, _ = raiz
    assert _denegado(lambda: path_guard.resolve_allowed("", "read"))


def test_canario_por_punto_punto_denegado(raiz):
    root, canario = raiz
    assert _denegado(lambda: path_guard.resolve_allowed("..\\canario.txt", "read"))


def test_canario_ruta_absoluta_denegada(raiz):
    root, canario = raiz
    assert _denegado(lambda: path_guard.resolve_allowed(str(canario), "read"))


def test_unc_denegado(raiz):
    root, _ = raiz
    assert _denegado(lambda: path_guard.resolve_allowed("\\\\evil\\share\\x.txt", "read"))


def test_ads_flujo_denegado(raiz):
    root, _ = raiz
    assert _denegado(lambda: path_guard.resolve_allowed("x.txt:flujo", "read"))


def test_nombre_con_punto_final_denegado(raiz):
    root, _ = raiz
    assert _denegado(lambda: path_guard.resolve_allowed("x.txt.", "read"))


def test_prefijo_unc_escape_denegado(raiz):
    root, _ = raiz
    assert _denegado(lambda: path_guard.resolve_allowed("\\\\?\\C:\\Windows\\win.ini", "read"))


def test_junction_hacia_fuera_denegado(raiz):
    root, canario = raiz
    junction = root / "junction"
    try:
        os.system('mklink /J "%s" "%s" >nul 2>&1' % (str(junction), str(canario.parent)))
    except Exception:
        pytest.skip("mklink no disponible")
    if not junction.exists():
        pytest.skip("no se pudo crear junction")
    assert _denegado(lambda: path_guard.resolve_allowed(str(junction / "canario.txt"), "read"))


def test_otra_unidad_denegada(raiz):
    root, _ = raiz
    # En Windows, Z: casi seguro no existe o no es la raiz; intentamos D:
    assert _denegado(lambda: path_guard.resolve_allowed("D:\\algo.txt", "read"))


def test_nul_en_ruta_denegado(raiz):
    root, _ = raiz
    assert _denegado(lambda: path_guard.resolve_allowed("a\x00b.txt", "read"))


def test_valido_dentro_de_la_raiz(raiz):
    root, _ = raiz
    (root / "ok.txt").write_text("hola", encoding="utf-8")
    res = path_guard.resolve_allowed("ok.txt", "read")
    assert Path(res).resolve() == (root / "ok.txt").resolve()


def test_valido_subcarpeta(raiz):
    root, _ = raiz
    sub = root / "sub"
    sub.mkdir()
    (sub / "y.txt").write_text("y", encoding="utf-8")
    res = path_guard.resolve_allowed("sub/y.txt", "read")
    assert Path(res).resolve() == (sub / "y.txt").resolve()


def test_need_invalido_denegado(raiz):
    root, _ = raiz
    assert _denegado(lambda: path_guard.resolve_allowed("ok.txt", "delete"))


def test_limite_1mb_lectura(raiz):
    root, _ = raiz
    grande = root / "grande.bin"
    grande.write_bytes(b"x" * (1024 * 1024 + 1))
    assert _denegado(lambda: path_guard.resolve_allowed("grande.bin", "read"))