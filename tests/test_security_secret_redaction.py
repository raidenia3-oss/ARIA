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


# -- (c) el router de webhooks no exige autenticacion ---------------------------


def test_the_real_app_still_has_no_auth_markers():
    """Documenta por que el secreto no puede salir de este router.

    `ARIA_APP/backend/app.py` no registra middleware de auth ni dependencias
    `Depends(require_auth)` / `HTTPBearer` / `APIKeyHeader` / `OAuth2`, y monta
    el CORS con `allow_origins=["*"]` + `allow_credentials=True`. Este test lee
    el fuente: si alguien anade auth, el aviso deja de ser cierto.
    """
    app_src = (PROJECT_ROOT / "ARIA_APP" / "backend" / "app.py").read_text(
        encoding="utf-8", errors="replace"
    )

    for marker in ("HTTPBearer", "APIKeyHeader", "OAuth2PasswordBearer", "require_auth"):
        assert marker not in app_src, (
            f"app.py ya define `{marker}`: reevaluar si GET /api/github/webhook/config "
            "sigue necesitando redactar el secreto"
        )


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
    for name in ("ARIA_SECRET_KEY", "GITHUB_WEBHOOK_SECRET", "ARIA_AUDIT_SECRET"):
        monkeypatch.delenv(name, raising=False)