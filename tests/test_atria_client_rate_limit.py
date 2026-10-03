"""GATE 5 — AtriaClient ya no se auto-limita a la mitad de la tasa del servidor.

`AtriaClient.__init__` arrancaba con `rate_limit = 100` hardcodeado mientras el
servidor publicaba su tasa en el header `x-rpm-limit: 50`. El cliente dormia
mientras creia tener 100 req/min y se comia un 429 en cuanto el servidor agotaba
su mitad real. Ahora adopta el valor del header; y si el header falta o no es
utilizable, se queda con el default DECLARADO por el servidor sin inventar nada.

Cubre el parseo del header, que no invente ante basura, que `request()` lo lea
ANTES de `raise_for_status()` (para que un 429 tambien refresque el limite) y la
rama explicita de 429.
"""
from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import io
import os
from pathlib import Path

import httpx
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = PROJECT_ROOT / "ARIA_APP" / "backend" / "atria_integration" / "atria_client.py"


def _load_atria_client():
    """Carga `atria_client.py` por ruta, no como paquete.

    `ARIA_APP.backend.atria_integration` no es importable de forma directa: su
    `__init__.py` arrastra `integration.py`, que hace imports absolutos
    `from backend.atria_integration...` y exige `ARIA_APP` en `sys.path` — y ese
    `backend` colisiona con el `backend/` de la raiz del repo. Es un problema
    preexistente y fuera del alcance de este gate (arreglarlo implicaria tocar
    `__init__.py` e `integration.py`). `atria_client.py` no tiene imports
    relativos, asi que se carga solo, sin tocar `sys.modules`.
    """
    if not MODULE_PATH.is_file():
        raise RuntimeError(f"modulo no encontrado: {MODULE_PATH}")

    spec = importlib.util.spec_from_file_location("aria_atria_client_under_test", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"no se pudo crear spec para: {MODULE_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


atria_client = _load_atria_client()
AtriaClient = atria_client.AtriaClient


def _offline_client() -> "AtriaClient":
    """Cliente SIN API key.

    `__init__` corta con un `return` antes de abrir el `httpx.AsyncClient`, asi
    que el test no abre sockets ni deja clientes httpx sin cerrar. `ATRIA_API_KEY`
    se anula para que el resultado no dependa del entorno del que corre pytest.
    """
    previous = os.environ.pop("ATRIA_API_KEY", None)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            client = AtriaClient(api_key="")
    finally:
        if previous is not None:
            os.environ["ATRIA_API_KEY"] = previous

    assert client.available is False
    return client


def _status_error(status_code: int, headers: dict) -> httpx.HTTPStatusError:
    req = httpx.Request("POST", "https://atria.invalid/v1/chat/completions")
    resp = httpx.Response(status_code, headers=headers, request=req)
    return httpx.HTTPStatusError(f"HTTP {status_code}", request=req, response=resp)


class _StubResponse:
    def __init__(self, status_code: int, headers: dict):
        self.status_code = status_code
        self.headers = httpx.Headers(headers)

    def json(self) -> dict:
        return {"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 3}}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise _status_error(self.status_code, dict(self.headers))


class _StubClient:
    """Sustituye al `httpx.AsyncClient`: ni red ni sockets."""

    def __init__(self, response: "_StubResponse"):
        self._response = response

    async def post(self, *args, **kwargs):
        return self._response

    async def aclose(self) -> None:
        return None


def _make_client():
    """Cliente con API key: `__init__` si abre un `httpx.AsyncClient` real."""
    previous = os.environ.pop("ATRIA_API_KEY", None)
    try:
        return AtriaClient(api_key="test-key-not-real")
    finally:
        if previous is not None:
            os.environ["ATRIA_API_KEY"] = previous


async def _drive(status_code: int, headers: dict) -> tuple:
    """Ejecuta `request()` completo contra una respuesta simulada.

    Devuelve `(resultado, cliente)` y cierra el `httpx.AsyncClient` real que
    abrio `__init__` para no dejar conexiones sin cerrar.
    """
    client = _make_client()
    real_client = client.client
    client.client = _StubClient(_StubResponse(status_code, headers))
    try:
        result = await client.request("hola", max_tokens=10, category="test")
    finally:
        client.client = real_client
        await real_client.aclose()
    return result, client


def _run(status_code: int, headers: dict) -> tuple:
    return asyncio.run(_drive(status_code, headers))


def test_default_is_the_server_declared_rate_not_100():
    client = _offline_client()
    assert client.RPM_LIMIT_HEADER == "x-rpm-limit"
    assert client.DEFAULT_RATE_LIMIT == 50
    assert client.rate_limit == 50
    assert client.rate_limit_source == "unavailable"


def test_valid_header_is_adopted_and_marked_measured():
    client = _offline_client()
    client._observe_rpm_limit({"x-rpm-limit": "50"})
    assert client.rate_limit == 50
    assert client.rate_limit_source == "measured"


def test_header_updates_a_previously_measured_value():
    client = _offline_client()
    client._observe_rpm_limit({"x-rpm-limit": "50"})
    client._observe_rpm_limit({"x-rpm-limit": "120"})
    assert client.rate_limit == 120
    assert client.rate_limit_source == "measured"


def test_header_is_matched_case_insensitively():
    client = _offline_client()
    client._observe_rpm_limit(httpx.Headers({"X-RPM-Limit": "17"}))
    assert client.rate_limit == 17
    assert client.rate_limit_source == "measured"


def test_missing_header_keeps_the_declared_default():
    client = _offline_client()
    client._observe_rpm_limit({})
    assert client.rate_limit == 50
    assert client.rate_limit_source == "unavailable"

    client._observe_rpm_limit(None)
    assert client.rate_limit == 50
    assert client.rate_limit_source == "unavailable"


@pytest.mark.parametrize("bad", ["abc", "", "  ", "0", "-5", None, "50.5", "1_0x"])
def test_unusable_header_invents_nothing(bad):
    client = _offline_client()
    client._observe_rpm_limit({"x-rpm-limit": bad})
    assert client.rate_limit == 50
    assert client.rate_limit_source == "unavailable"


def test_unusable_header_does_not_erase_a_measured_value():
    client = _offline_client()
    client._observe_rpm_limit({"x-rpm-limit": "37"})
    client._observe_rpm_limit({"x-rpm-limit": "nope"})
    assert client.rate_limit == 37
    assert client.rate_limit_source == "measured"


def test_token_status_exposes_the_rate_and_its_source():
    client = _make_client()

    async def run() -> tuple:
        try:
            status = client.get_token_status()
            client._observe_rpm_limit({"x-rpm-limit": "50"})
            return status, client.get_token_status()
        finally:
            await client.close()

    before, after = asyncio.run(run())
    assert before["rate_limit"] == 50
    assert before["rate_limit_source"] == "unavailable"
    assert after["rate_limit"] == 50
    assert after["rate_limit_source"] == "measured"


def test_request_adopts_the_header_on_a_successful_call():
    result, client = _run(200, {"x-rpm-limit": "50"})
    assert result["success"] is True
    assert client.rate_limit == 50
    assert client.rate_limit_source == "measured"


def test_429_is_reported_explicitly_and_refreshes_the_rate():
    """El header se lee ANTES de `raise_for_status()`: por eso el 429 actualiza
    el limite y no queda cacheado el valor viejo."""
    result, client = _run(429, {"x-rpm-limit": "25"})
    assert result["error"] == "RATE_LIMITED"
    assert result["success"] is False
    assert result["rate_limit"] == 25
    assert result["rate_limit_source"] == "measured"
    assert client.rate_limit == 25


def test_429_without_header_keeps_the_declared_default():
    result, client = _run(429, {})
    assert result["error"] == "RATE_LIMITED"
    assert result["rate_limit"] == 50
    assert result["rate_limit_source"] == "unavailable"
    assert client.rate_limit == 50


def test_non_429_http_errors_keep_the_opaque_behaviour():
    result, _ = _run(500, {})
    assert result["success"] is False
    assert result["error"] != "RATE_LIMITED"
    assert "rate_limit" not in result


def test_check_rate_limit_does_not_sleep_below_the_observed_limit():
    client = _offline_client()
    client._observe_rpm_limit({"x-rpm-limit": "50"})
    client.requests_this_minute = 49
    asyncio.run(client._check_rate_limit())
    assert client.requests_this_minute == 49
