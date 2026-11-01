"""Regresión: `backend/main.py` debe importar sin lanzar.

La causa raíz que atrapa este test era que las rutas con `@limiter.limit`
(slowapi) registraban el wrapper ante FastAPI, y con
`from __future__ import annotations` la anotación `GesturePredictRequest`
no se resolvía: el import de `backend.main` moría en `@app.post` de
`/api/gesture/predict` DESPUÉS de registrar las 4 métricas de Prometheus.
El módulo fallido salía de `sys.modules` y cada re-ejecución re-registraba
los mismos nombres -> `DuplicateTimeseries` en la colección.

Este test es el que habría atrapado el bug: falla tan pronto como la ruta
deje de importar.
"""
from __future__ import annotations


def test_backend_main_imports_without_raising():
    import backend.main  # noqa: F401

    assert True


def test_gesture_predict_route_is_registered():
    """La ruta cuya anotación fallaba debe existir tras el import."""
    import backend.main as main

    paths = {getattr(r, "path", None) for r in main.app.routes}
    assert "/api/gesture/predict" in paths


def test_metrics_still_served_after_import():
    """/metrics debe seguir sirviendo http_requests_total (no tocar el registry)."""
    import backend.main as main
    from prometheus_client import REGISTRY, generate_latest

    # backend/main.py sirve generate_latest() sobre el REGISTRY global; ese
    # es el camino exacto que /metrics usa y que
    # tests/integration/test_backend_api.py:93 asserta.
    body = generate_latest(REGISTRY).decode("utf-8", "replace")
    assert "http_requests_total" in body
    # El registro no debe haberse duplicado (dos Counters con el mismo nombre
    # explotarían al registrar: DuplicateTimeseries en el import).
    assert hasattr(main, "generate_latest")
