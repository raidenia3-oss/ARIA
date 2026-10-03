"""Redaccion de secretos en superficie HTTP / stats (F1-F3 del audit de seguridad).

Tres fugas concretas que se cierran aqui:

1. ``CredentialVerifier.get_stats()`` publicaba ``secret_key_prefix`` (los
   primeros 8 caracteres de la clave de firma). Ahora no hay material de clave:
   solo ``secret_configured`` (booleano) y ``secret_source`` (procedencia).
2. La clave de firma por defecto es una constante publicada en el codigo
   fuente. Cuando esa constante esta en uso hay que reportarlo como
   ``development_default``, no insinuar una clave configurada.
3. ``GET /api/github/webhook/config`` devolvia el secreto del webhook entero y
   este router no exige autenticacion. Ahora devuelve booleanos.

Los modulos se cargan POR RUTA (no como paquete) siguiendo la convencion de
``tests/test_atria_client_rate_limit.py``: ``ARIA_APP.backend.core.__init__``
importa ``backend.core.*`` de forma absoluta, lo que arrastra la cadena de
imports completa (y colisiona con el ``backend/`` de la raiz del repo).
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_by_path(module_path: Path):
    if not module_path.is_file():
        raise RuntimeError(f"modulo no encontrado: {module_path}")

    spec = importlib.util.spec_from_file_location(
        f"aria_{module_path.stem}_under_test", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"no se pudo crear spec para: {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


aria_security = _load_by_path(PROJECT_ROOT / "ARIA_APP" / "backend" / "core" / "security.py")
gh = _load_by_path(PROJECT_ROOT / "ARIA_APP" / "backend" / "api" / "github_webhooks.py")

CredentialVerifier = aria_security.CredentialVerifier

# Credenciales falsas construidas en linea. No hay ningun valor real en este
# fichero: `FAKE_SIGNING_KEY` es lo que se inyecta en ARIA_SECRET_KEY y
# `FAKE_WEBHOOK_SECRET` lo que se inyecta en la config del webhook.
FAKE_SIGNING_KEY = "test-" + "x" * 24
FAKE_WEBHOOK_SECRET = "test-" + "y" * 24


def _verifier_with_env(monkeypatch, value):
    """CredentialVerifier con ARIA_SECRET_KEY fijada a `value` (o ausente)."""
    if value is None:
        monkeypatch.delenv("ARIA_SECRET_KEY", raising=False)
    else:
        monkeypatch.setenv("ARIA_SECRET_KEY", value)
    return CredentialVerifier()


# -- (a) get_stats() sin material de clave --------------------------------------


def test_stats_no_longer_expose_the_prefix_key(monkeypatch):
    stats = _verifier_with_env(monkeypatch, FAKE_SIGNING_KEY).get_stats()

    assert "secret_key_prefix" not in stats


def test_stats_do_not_contain_any_part_of_the_key(monkeypatch):
    stats = _verifier_with_env(monkeypatch, FAKE_SIGNING_KEY).get_stats()
    rendered = json.dumps(stats, default=str)

    assert FAKE_SIGNING_KEY not in rendered
    # El bug original truncaba a 8 caracteres; ese prefijo tambien cuenta.
    assert FAKE_SIGNING_KEY[:8] not in rendered
    assert FAKE_SIGNING_KEY[:4] not in rendered


def test_stats_report_a_configured_env_secret_honestly(monkeypatch):
    stats = _verifier_with_env(monkeypatch, FAKE_SIGNING_KEY).get_stats()

    assert stats["secret_configured"] is True
    assert stats["secret_source"] == "env"


def test_stats_report_the_development_fallback_as_such(monkeypatch):
    """Sin ARIA_SECRET_KEY la clave de firma es una constante PUBLICA.

    Reportarla como configurada seria mentir: cualquiera que lea el fuente
    puede firmar con ella.
    """
    verifier = _verifier_with_env(monkeypatch, None)

    stats = verifier.get_stats()
    assert stats["secret_configured"] is False
    assert stats["secret_source"] == "development_default"

    # El valor por defecto en uso es exactamente la constante del modulo, y no
    # aparece en la salida de stats.
    rendered = json.dumps(stats, default=str)
    assert verifier._secret == aria_security.DEV_SECRET_FALLBACK
    assert aria_security.DEV_SECRET_FALLBACK not in rendered
    assert aria_security.DEV_SECRET_FALLBACK[:8] not in rendered


def test_empty_env_var_is_not_reported_as_a_configured_secret(monkeypatch):
    """`ARIA_SECRET_KEY=""` no es una clave: es el fallback de desarrollo."""
    stats = _verifier_with_env(monkeypatch, "").get_stats()

    assert stats["secret_configured"] is False
    assert stats["secret_source"] == "development_default"


def test_stats_keep_their_non_secret_fields(monkeypatch):
    verifier = _verifier_with_env(monkeypatch, FAKE_SIGNING_KEY)
    verifier.initialize("admin-token-for-tests")

    stats = verifier.get_stats()

    assert stats["initialized"] is True
    assert stats["active_tokens"] == 1


def test_security_manager_stats_are_also_clean(monkeypatch, tmp_path):
    """`SecurityManager.get_stats()` mergea el del verificador: no reintroduce la fuga."""
    monkeypatch.setenv("ARIA_SECRET_KEY", FAKE_SIGNING_KEY)
    monkeypatch.setenv("ARIA_AUDIT_SECRET", FAKE_WEBHOOK_SECRET)
    # `AUDIT_LOG_FILE` se resuelve a nivel de modulo (import time), asi que el env
    # no sirve aqui: se redirige el sink del AuditLogger al tmp_path para no
    # escribir `data/audit.log` dentro del repo durante la suite.
    monkeypatch.setattr(aria_security, "AUDIT_LOG_FILE", tmp_path / "audit_redaction.log")

    aria_security.reset_security()
    try:
        stats = aria_security.get_security().get_stats()
    finally:
        aria_security.reset_security()

    rendered = json.dumps(stats, default=str)
    assert "secret_key_prefix" not in stats
    assert FAKE_SIGNING_KEY not in rendered
    assert FAKE_SIGNING_KEY[:8] not in rendered
    assert FAKE_WEBHOOK_SECRET not in rendered
    assert stats["secret_configured"] is True
    assert stats["secret_source"] == "env"


# -- (b) GET /api/github/webhook/config sin secreto -----------------------------


@pytest.fixture()
def webhook_client():
    """App minima con SOLO el router de webhooks.

    No se importa `ARIA_APP.backend.app`: ese modulo arranca el daemon
    orchestrator, whisper, edge_tts y十几个 singletons. El router bajo prueba
    solo necesita fastapi + pydantic a nivel de modulo.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(gh.router)
    return TestClient(app)


def test_webhook_config_endpoint_never_returns_the_secret(webhook_client, monkeypatch):
    monkeypatch.setattr(
        gh,
        "_load_webhook_config",
        lambda: {"events": ["push"], "secret": FAKE_WEBHOOK_SECRET, "active": True},
    )

    response = webhook_client.get("/api/github/webhook/config")

    assert response.status_code == 200
    body = response.json()
    rendered = json.dumps(body, default=str)
    assert "secret" not in body
    assert FAKE_WEBHOOK_SECRET not in rendered
    assert FAKE_WEBHOOK_SECRET[:8] not in rendered


def test_webhook_config_endpoint_reports_booleans_when_verified(webhook_client, monkeypatch):
    monkeypatch.setattr(
        gh,
        "_load_webhook_config",
        lambda: {"events": ["push"], "secret": FAKE_WEBHOOK_SECRET, "active": True},
    )

    body = webhook_client.get("/api/github/webhook/config").json()

    assert body["secret_configured"] is True
    assert body["verification_enabled"] is True
    assert body["active"] is True


def test_webhook_config_endpoint_reports_verification_off_when_unset(webhook_client, monkeypatch):
    """Sin secreto, `_verify_signature` acepta cualquier payload.

    Decirlo es obligatorio: si no, un webhook sin verificar se reporta activo.
    """
    monkeypatch.setattr(
        gh,
        "_load_webhook_config",
        lambda: {"events": ["push"], "secret": "", "active": True},
    )

    body = webhook_client.get("/api/github/webhook/config").json()

    assert body["secret_configured"] is False
    assert body["verification_enabled"] is False


def test_public_webhook_config_strips_every_credential_key():
    public = gh._public_webhook_config(
        {
            "events": ["push"],
            "secret": FAKE_WEBHOOK_SECRET,
            "token": FAKE_WEBHOOK_SECRET,
            "api_key": FAKE_WEBHOOK_SECRET,
            "active": True,
        }
    )

    rendered = json.dumps(public, default=str)
    assert set(public) == {"events", "active", "secret_configured", "verification_enabled"}
    assert FAKE_WEBHOOK_SECRET not in rendered


def test_public_webhook_config_does_not_mutate_the_input():
    config = {"events": ["push"], "secret": FAKE_WEBHOOK_SECRET, "active": True}

    gh._public_webhook_config(config)

    assert config["secret"] == FAKE_WEBHOOK_SECRET


# -- (c) las rutas de administracion exigen token; GET /config sigue abierta ----


# -- (c) las rutas de administracion del webhook exigen token --------------------


ADMIN_ROUTES = ("/api/github/webhook/config", "/api/github/webhook/autocommit",
                "/api/github/webhook/pr/create")

FAKE_ADMIN_TOKEN = "test-" + "a" * 24


def _app_source() -> str:
    return (PROJECT_ROOT / "ARIA_APP" / "backend" / "app.py").read_text(
        encoding="utf-8", errors="replace"
    )


def _admin_route(path: str):
    """La ruta POST ya montada, leida del router (no del fuente)."""
    for route in gh.router.routes:
        if getattr(route, "path", None) == path and "POST" in getattr(route, "methods", set()):
            return route
    raise AssertionError(f"el router no expone POST {path}")


def _guards(dependant) -> bool:
    """`require_admin_token` aparece en el arbol de dependencias de la ruta."""
    calls = []

    def walk(node):
        for sub in node.dependencies:
            calls.append(sub.call)
            walk(sub)

    walk(dependant)
    return gh.require_admin_token in calls


def test_the_app_no_longer_mounts_wildcard_cors_with_credentials():
    """`allow_origins=["*"]` + `allow_credentials=True` acepta el credential de
    cualquier origen. El CORS se deriva de `AURA_CORS_ORIGINS` y las credenciales
    solo se permiten si esa lista no trae `"*"`."""
    app_src = _app_source()

    assert 'allow_origins=["*"]' not in app_src
    assert "AURA_CORS_ORIGINS" in app_src
    assert 'allow_credentials="*" not in os.getenv("AURA_CORS_ORIGINS", "")' in app_src


def test_the_three_admin_routes_depend_on_require_admin_token():
    """`/autocommit` hace push a master y `/pr/create` empuja una rama: sin
    `Depends(require_admin_token)` cualquiera que alcance el puerto escribe en el
    repositorio."""
    for path in ADMIN_ROUTES:
        route = _admin_route(path)

        assert _guards(route.dependant), (
            f"POST {path} no depende de require_admin_token"
        )


def test_get_config_stays_open_and_therefore_redacted():
    """`GET /config` sigue sin token; por eso `_public_webhook_config` existe."""
    for route in gh.router.routes:
        if getattr(route, "path", None) != "/api/github/webhook/config":
            continue
        if "GET" not in getattr(route, "methods", set()):
            continue
        assert not _guards(route.dependant)
        return
    raise AssertionError("el router no expone GET /api/github/webhook/config")


@pytest.mark.parametrize("route", ADMIN_ROUTES)
def test_admin_routes_reject_a_request_without_a_token(webhook_client, monkeypatch, route):
    """503 (fail-closed) si no hay token configurado: nunca se ejecuta el cuerpo."""
    monkeypatch.delenv("ARIA_ADMIN_TOKEN", raising=False)

    response = webhook_client.post(route, json={})

    assert response.status_code == 503
    assert "ARIA_ADMIN_TOKEN" in response.json()["detail"]


@pytest.mark.parametrize("route", ADMIN_ROUTES)
def test_admin_routes_reject_a_wrong_token(webhook_client, monkeypatch, route):
    monkeypatch.setenv("ARIA_ADMIN_TOKEN", FAKE_ADMIN_TOKEN)

    for header in ({"Authorization": "Bearer wrong"}, {"Authorization": "Basic x"},
                   {"Authorization": FAKE_ADMIN_TOKEN}):
        response = webhook_client.post(route, json={}, headers=header)
        assert response.status_code == 401, f"{route} acepto {header}"
        assert response.headers.get("www-authenticate") == "Bearer"


@pytest.mark.parametrize("header", ["Bearer " + FAKE_ADMIN_TOKEN,
                                    "bearer " + FAKE_ADMIN_TOKEN,
                                    "BEARER " + FAKE_ADMIN_TOKEN])
def test_require_admin_token_accepts_the_configured_token(monkeypatch, header):
    """La dependencia se prueba directa: llamar a las rutas con token valido
    ejecutaria git de verdad."""
    from starlette.requests import Request

    monkeypatch.setenv("ARIA_ADMIN_TOKEN", FAKE_ADMIN_TOKEN)
    request = Request({
        "type": "http",
        "method": "POST",
        "path": "/api/github/webhook/autocommit",
        "headers": [(b"authorization", header.encode())],
    })

    assert gh.require_admin_token(request) is True


def test_require_admin_token_is_fail_closed_without_configuration(monkeypatch):
    from fastapi import HTTPException
    from starlette.requests import Request

    monkeypatch.setenv("ARIA_ADMIN_TOKEN", "   ")
    request = Request({"type": "http", "method": "POST", "path": "/x", "headers": []})

    with pytest.raises(HTTPException) as excinfo:
        gh.require_admin_token(request)
    assert excinfo.value.status_code == 503


def test_get_config_still_answers_without_a_token(webhook_client):
    """El contrato de solo lectura no se rompe al cerrar las rutas de admin."""
    assert webhook_client.get("/api/github/webhook/config").status_code == 200


# -- (d) el PAT en claro no se versiona -----------------------------------------


def test_the_webhook_config_with_the_pat_is_not_tracked():
    """`ARIA_APP/.github_webhook_config.json` contenia un PAT en claro y estaba
    trackeado: .gitignore no basta, hay que sacarlo del indice."""
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "ARIA_APP/.github_webhook_config.json"],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    assert tracked.returncode != 0, "el PAT sigue trackeado en git"


def test_the_webhook_config_path_is_gitignored():
    ignored = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".github_webhook_config.json" in ignored


# -- (e) los logs de auditoria no guardan prefijos de token ---------------------


@pytest.mark.parametrize("module_path", ["backend/core/security.py",
                                        "ARIA_APP/backend/core/security.py"])
def test_no_module_logs_a_token_prefix(module_path):
    """`tok_prefix=token[:8]` metia 8 caracteres de un token de auth en el log de
    auditoria, que ademas se persiste en disco."""
    source = (PROJECT_ROOT / module_path).read_text(encoding="utf-8", errors="replace")

    assert "tok_prefix" not in source
    assert "token[:8]" not in source
    assert "token_present" in source


def test_the_audit_default_secret_is_the_published_constant_not_a_real_one():
    """El fallback de desarrollo esta nombrado, no escrito inline en el __init__."""
    assert aria_security.DEV_SECRET_FALLBACK
    source = (PROJECT_ROOT / "ARIA_APP" / "backend" / "core" / "security.py").read_text(
        encoding="utf-8"
    )
    assert "DEV_SECRET_FALLBACK = " in source
    # Y ya no queda ninguna lectura con valor por defecto inline.
    assert 'os.environ.get("ARIA_SECRET_KEY", ' not in source


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Ningun test depende del entorno real del que corre pytest."""
    for name in (
        "ARIA_SECRET_KEY",
        "GITHUB_WEBHOOK_SECRET",
        "ARIA_AUDIT_SECRET",
        "ARIA_ADMIN_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)