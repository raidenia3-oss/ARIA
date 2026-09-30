"""HTTP client for the ARIA control plane.

The transport is injectable on purpose. ``aria`` commands must be testable and
scriptable, and a test that needs a live Axum backend on :8002 is a test that
only passes on the author's machine.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

#: Default Axum backend. Matches the port the server binds in ``main.rs``.
DEFAULT_BASE_URL = "http://127.0.0.1:8002"

#: Environment variable holding the bearer token, per ``state::API_KEY_ENV``.
API_KEY_ENV = "ARIA_API_KEY"

#: Default per-request timeout, in seconds. Control calls are local, so this is
#: generous enough for a cold start and short enough that a dead server is
#: reported quickly instead of hanging the dashboard.
DEFAULT_TIMEOUT = 10.0

#: Hard ceiling on ``?lines=``; mirrors ``control::LOG_LINES_MAX`` server-side.
LOGS_MAX_LINES = 1000


class ControlError(RuntimeError):
    """The control plane answered with an error.

    ``code`` is the server's machine-readable ``error`` field, ``detail`` its
    human-readable ``detail``; both are kept so the CLI can print something
    specific instead of a status code.
    """

    def __init__(self, message: str, *, status: int = 0, code: str = "", detail: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.detail = detail


class BackendUnreachable(ControlError):
    """The backend did not answer at all."""


class AuthRequired(ControlError):
    """No bearer token is available for an endpoint that demands one."""


class Transport(Protocol):
    """Minimal HTTP surface the client needs."""

    def get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        ...

    def post(self, url: str, json_body: Any = None) -> Any:
        ...


class RequestsTransport:
    """Real transport backed by :mod:`requests`."""

    def __init__(self, token: str | None = None, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._token = token
        self._timeout = timeout

    def get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        import requests

        try:
            response = requests.get(url, params=params, headers=self._headers(), timeout=self._timeout)
        except requests.RequestException as exc:
            raise BackendUnreachable(f"cannot reach {url}: {exc}") from exc
        return response

    def post(self, url: str, json_body: Any = None) -> Any:
        import requests

        try:
            response = requests.post(
                url, json=json_body, headers=self._headers(), timeout=self._timeout
            )
        except requests.RequestException as exc:
            raise BackendUnreachable(f"cannot reach {url}: {exc}") from exc
        return response

    def _headers(self) -> dict[str, str]:
        if not self._token:
            return {}
        return {"Authorization": f"Bearer {self._token}"}


class StaticTransport:
    """In-memory transport for tests and offline demos.

    ``routes`` maps ``(method, path)`` to a response value. ``GET /logs``
    accepts a ``lines`` query parameter, so it may map to a callable that takes
    the params and returns the payload.
    """

    def __init__(self, routes: dict[tuple[str, str], Any]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, str, Any]] = []

    def get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        return self._dispatch("GET", url, None, params)

    def post(self, url: str, json_body: Any = None) -> Any:
        return self._dispatch("POST", url, json_body, None)

    def _dispatch(
        self, method: str, url: str, body: Any, params: dict[str, Any] | None
    ) -> Any:
        path = _path_of(url)
        self.calls.append((method, path, body))
        handler = self.routes.get((method, path))
        if handler is None:
            raise ControlError(
                f"no route for {method} {path}",
                status=404,
                code="no_route",
                detail="the fake transport has no handler registered",
            )
        if callable(handler):
            return handler(params) if params is not None else handler(body)
        return handler


def _path_of(url: str) -> str:
    """Strip scheme, host and query so routes can be keyed by path alone."""
    without_scheme = url.split("://", 1)[-1]
    slash = without_scheme.find("/")
    return without_scheme[slash:] if slash >= 0 else "/"


def _unwrap(response: Any) -> Any:
    """Normalize a transport result into data, or raise :class:`ControlError`.

    Applied by :class:`ControlClient` rather than by each transport, so every
    transport — real, fake or future — reports errors the same way. A transport
    that already returns parsed data (a plain ``dict``) passes straight
    through: the default ``status_code`` of 200 treats it as success.
    """
    if isinstance(response, (dict, list)):
        return response

    status = getattr(response, "status_code", 200)
    try:
        payload = response.json()
    except ValueError:
        payload = {"detail": getattr(response, "text", "")}

    if status >= 400:
        code = ""
        detail = ""
        if isinstance(payload, dict):
            code = str(payload.get("error", ""))
            detail = str(payload.get("detail", payload.get("message", "")))
        message = detail or code or f"HTTP {status}"
        raise ControlError(message, status=status, code=code, detail=detail)
    return payload


@dataclass(frozen=True)
class ControlClient:
    """Typed wrapper over ``/api/control/*``."""

    base_url: str = DEFAULT_BASE_URL
    transport: Any = None
    token: str | None = None

    def __post_init__(self) -> None:
        if self.transport is None:
            object.__setattr__(
                self,
                "transport",
                RequestsTransport(token=self.token, timeout=DEFAULT_TIMEOUT),
            )

    # -- plumbing ---------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}{path}"

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return _unwrap(self.transport.get(self._url(path), params=params))

    def _post(self, path: str, body: Any = None) -> Any:
        return _unwrap(self.transport.post(self._url(path), json_body=body))

    def _require_token(self) -> None:
        """Fail loudly before a confusing 401.

        Every control endpoint is authenticated. Hitting them without a token
        returns ``401 missing_token`` from the server, which reads like a bug
        rather than a missing environment variable.
        """
        token = self.token if self.token is not None else os.environ.get(API_KEY_ENV)
        if not token:
            raise AuthRequired(
                f"{API_KEY_ENV} is not set; the control plane requires a bearer token. "
                f"Export the key the server printed at startup, or pass --token.",
                code="missing_token",
            )

    # -- endpoints --------------------------------------------------------

    def status(self) -> dict[str, Any]:
        self._require_token()
        return self._get("/api/control/status")

    def services(self) -> dict[str, Any]:
        self._require_token()
        return self._get("/api/control/services")

    def logs(self, lines: int = 50) -> dict[str, Any]:
        self._require_token()
        bounded = max(1, min(int(lines), LOGS_MAX_LINES))
        return self._get("/api/control/logs", params={"lines": bounded})

    def config(self) -> dict[str, Any]:
        self._require_token()
        return self._get("/api/control/config")

    def set_config(self, key: str, value: str) -> dict[str, Any]:
        self._require_token()
        return self._post("/api/control/config", body={"key": key, "value": str(value)})

    def restart(self) -> dict[str, Any]:
        self._require_token()
        return self._post("/api/control/restart")

    def upgrade(self) -> dict[str, Any]:
        self._require_token()
        return self._post("/api/control/upgrade")

    def job(self, job_id: str) -> dict[str, Any]:
        self._require_token()
        return self._get(f"/api/control/jobs/{job_id}")

    def plugins(self) -> dict[str, Any]:
        self._require_token()
        return self._get("/api/control/plugins")

    def install_plugin(self, name: str) -> dict[str, Any]:
        self._require_token()
        return self._post(f"/api/control/plugins/{name}/install")


__all__ = [
    "API_KEY_ENV",
    "AuthRequired",
    "BackendUnreachable",
    "ControlClient",
    "ControlError",
    "DEFAULT_BASE_URL",
    "LOGS_MAX_LINES",
    "RequestsTransport",
    "StaticTransport",
    "Transport",
]
