"""Tests for the ARIA control center: client, dashboard and CLI.

Every test runs against a fake transport. A control-center suite that needs a
live Axum backend on :8002 only passes on the machine that has one.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from aria_control import client as client_mod
from aria_control.cli import (
    EXIT_CONTROL_ERROR,
    EXIT_NO_TOKEN,
    EXIT_UNREACHABLE,
    cli,
)
from aria_control.client import (
    AuthRequired,
    BackendUnreachable,
    ControlClient,
    ControlError,
    StaticTransport,
)
from aria_control.tui import Dashboard, Snapshot

REPO_ROOT = Path(__file__).resolve().parent.parent
TOKEN = "test-token"


# --- fixtures ---------------------------------------------------------------


def _status_payload() -> dict:
    return {
        "aria_version": "6.0.0",
        "channel": "stable",
        "uptime": "2d 3h",
        "uptime_seconds": 183_600,
        "services_healthy": 2,
        "services_total": 3,
        "last_update_check": "2026-09-29T12:00:00Z",
        "checked_at": "2026-09-29T20:00:00Z",
    }


def _services_payload() -> dict:
    return {
        "services": [
            {
                "name": "axum-backend",
                "description": "Axum core backend",
                "status": "running",
                "pid": 32520,
                "port": None,
            },
            {
                "name": "ollama",
                "description": "Local inference server",
                "status": "running",
                "pid": None,
                "port": 11434,
            },
            {
                "name": "discord-bot",
                "description": "Discord interface bot",
                "status": "unknown",
                "pid": None,
                "port": None,
            },
        ],
        "count": 3,
    }


def _logs_payload(count: int = 3) -> dict:
    return {
        "lines": [
            {
                "ts": f"2026-09-29T20:0{index}:00Z",
                "level": ["info", "warn", "error"][index % 3],
                "target": "aria::auth",
                "message": f"event {index}",
            }
            for index in range(count)
        ],
        "count": count,
    }


def _config_payload() -> dict:
    return {
        "config": {"release-channel": "stable", "daemon-port": "8002"},
        "fields": [
            {
                "key": "release-channel",
                "default": "stable",
                "value": "stable",
                "description": "Rolling-release channel the updater follows.",
            },
            {
                "key": "daemon-port",
                "default": "8002",
                "value": "8002",
                "description": "TCP port the Axum backend listens on.",
            },
        ],
    }


def make_client(routes: dict, token: str = TOKEN) -> tuple[ControlClient, StaticTransport]:
    transport = StaticTransport(routes)
    return ControlClient(base_url="http://test:8002", transport=transport, token=token), transport


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def wired(monkeypatch):
    """Patch the CLI's client factory so commands hit a fake transport.

    The factory still *returns* a client; errors are raised at call time, the
    way a real transport behaves, so the CLI's error handling is what is under
    test rather than click's callback guard.
    """
    state: dict = {"routes": {}, "error": None}

    class MaybeBroken:
        def get(self, url, params=None):
            if state["error"] is not None:
                raise state["error"]
            return StaticTransport(state["routes"]).get(url, params)

        def post(self, url, json_body=None):
            if state["error"] is not None:
                raise state["error"]
            return StaticTransport(state["routes"]).post(url, json_body)

    def factory(base_url: str, token: str | None) -> ControlClient:
        return ControlClient(base_url="http://test:8002", transport=MaybeBroken(), token=token)

    monkeypatch.setattr("aria_control.cli.ControlClient", factory)
    return state


# --- client: URL construction ------------------------------------------------


def test_status_calls_the_control_path() -> None:
    api, transport = make_client({("GET", "/api/control/status"): _status_payload()})
    assert api.status()["aria_version"] == "6.0.0"
    assert transport.calls == [("GET", "/api/control/status", None)]


def test_base_url_trailing_slash_is_not_doubled() -> None:
    transport = StaticTransport({("GET", "/api/control/status"): _status_payload()})
    api = ControlClient(base_url="http://x:8002/", transport=transport, token=TOKEN)
    api.status()
    assert transport.calls[0][1] == "/api/control/status"


def test_path_extraction_strips_scheme_host_and_query() -> None:
    assert client_mod._path_of("http://h:8002/api/x") == "/api/x"
    assert client_mod._path_of("https://h/a/b?c=1") == "/a/b?c=1"
    assert client_mod._path_of("http://h") == "/"


# --- client: authentication -------------------------------------------------


def test_missing_token_fails_before_the_request() -> None:
    transport = StaticTransport({("GET", "/api/control/status"): _status_payload()})
    api = ControlClient(base_url="http://test:8002", transport=transport, token=None, )
    with pytest.raises(AuthRequired) as excinfo:
        api.status()
    assert "ARIA_API_KEY" in str(excinfo.value)
    assert transport.calls == [], "no request may be made without a token"


def test_token_falls_back_to_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("ARIA_API_KEY", "from-env")
    transport = StaticTransport({("GET", "/api/control/status"): _status_payload()})
    api = ControlClient(base_url="http://test:8002", transport=transport, token=None)
    assert api.status()["aria_version"] == "6.0.0"


def test_blank_token_env_still_fails(monkeypatch) -> None:
    monkeypatch.setenv("ARIA_API_KEY", "")
    transport = StaticTransport({("GET", "/api/control/status"): _status_payload()})
    api = ControlClient(base_url="http://test:8002", transport=transport, token=None)
    with pytest.raises(AuthRequired):
        api.status()


# --- client: payloads -------------------------------------------------------


def test_logs_clamps_the_requested_line_count() -> None:
    api, _ = make_client(
        {("GET", "/api/control/logs"): lambda params: {"lines": [], "asked": params}}
    )
    assert api.logs(lines=5)["asked"]["lines"] == 5
    assert api.logs(lines=100_000)["asked"]["lines"] == client_mod.LOGS_MAX_LINES
    # 0 would mean "no lines" on the server; the client never asks for it.
    assert api.logs(lines=0)["asked"]["lines"] == 1


def test_set_config_posts_key_and_value() -> None:
    api, transport = make_client(
        {("POST", "/api/control/config"): {"status": "ok", "key": "release-channel", "value": "testing"}}
    )
    result = api.set_config("release-channel", "testing")
    assert result["value"] == "testing"
    method, path, body = transport.calls[0]
    assert (method, path) == ("POST", "/api/control/config")
    assert body == {"key": "release-channel", "value": "testing"}


def test_numeric_config_values_are_stringified() -> None:
    api, transport = make_client({("POST", "/api/control/config"): {"status": "ok"}})
    api.set_config("daemon-port", 8002)
    assert transport.calls[0][2]["value"] == "8002"


def test_job_and_plugin_routes() -> None:
    api, transport = make_client(
        {
            ("GET", "/api/control/jobs/abc"): {"job": {"status": "succeeded"}},
            ("GET", "/api/control/plugins"): {"plugins": []},
            ("POST", "/api/control/plugins/chat/install"): {"status": "ok"},
        }
    )
    assert api.job("abc")["job"]["status"] == "succeeded"
    assert api.plugins() == {"plugins": []}
    api.install_plugin("chat")
    assert [call[1] for call in transport.calls] == [
        "/api/control/jobs/abc",
        "/api/control/plugins",
        "/api/control/plugins/chat/install",
    ]


# --- client: error mapping --------------------------------------------------


def test_server_error_is_raised_with_code_and_detail() -> None:
    class Response:
        status_code = 400

        @staticmethod
        def json():
            return {"error": "invalid_config", "detail": "'release-channel' must be one of stable"}

        @staticmethod
        def text():
            return ""

    class Boom:
        def get(self, url, params=None):
            return Response()

    api = ControlClient(base_url="http://test:8002", transport=Boom(), token=TOKEN)
    with pytest.raises(ControlError) as excinfo:
        api.status()
    assert excinfo.value.status == 400
    assert excinfo.value.code == "invalid_config"
    assert "stable" in excinfo.value.detail


def test_non_json_error_body_still_raises() -> None:
    class Response:
        status_code = 502
        text = "<html>bad gateway</html>"

        @staticmethod
        def json():
            raise ValueError("not json")

    class Boom:
        def get(self, url, params=None):
            return Response()

    api = ControlClient(base_url="http://test:8002", transport=Boom(), token=TOKEN)
    with pytest.raises(ControlError) as excinfo:
        api.status()
    assert "bad gateway" in str(excinfo.value)


def test_unreachable_transport_maps_to_backend_unreachable() -> None:
    api = ControlClient(
        base_url="http://down:8002",
        transport=client_mod.RequestsTransport(token=TOKEN, timeout=0.05),
        token=TOKEN,
    )
    with pytest.raises((BackendUnreachable, ControlError)):
        api.status()


# --- dashboard --------------------------------------------------------------


def test_snapshot_collects_every_section() -> None:
    api, _ = make_client(
        {
            ("GET", "/api/control/status"): _status_payload(),
            ("GET", "/api/control/services"): _services_payload(),
            ("GET", "/api/control/logs"): _logs_payload(),
        }
    )
    snap = Dashboard(client=api).snapshot()
    assert snap.ok
    assert snap.status is not None
    assert len(snap.services) == 3
    assert len(snap.logs) == 3
    assert snap.errors == {}


def test_snapshot_survives_a_partial_failure() -> None:
    class BrokenLogs:
        def get(self, url, params=None):
            if "/logs" in url:
                raise ControlError("logs exploded", status=500)
            return _status_payload() if "/status" in url else _services_payload()

    api = ControlClient(base_url="http://test:8002", transport=BrokenLogs(), token=TOKEN)
    snap = Dashboard(client=api).snapshot()
    assert snap.ok, "a failing log endpoint must not sink the whole dashboard"
    assert snap.status is not None
    assert snap.services
    assert "logs" in snap.errors


def test_snapshot_reports_an_unreachable_backend() -> None:
    class Dead:
        def get(self, url, params=None):
            raise BackendUnreachable("connection refused")

    api = ControlClient(base_url="http://test:8002", transport=Dead(), token=TOKEN)
    snap = Dashboard(client=api).snapshot()
    assert not snap.ok
    assert "connection refused" in snap.fatal


def test_render_produces_a_renderable() -> None:
    from rich.console import Console

    api, _ = make_client(
        {
            ("GET", "/api/control/status"): _status_payload(),
            ("GET", "/api/control/services"): _services_payload(),
            ("GET", "/api/control/logs"): _logs_payload(),
        }
    )
    dashboard = Dashboard(client=api)
    console = Console(record=True, width=100, force_terminal=False)
    dashboard.console = console
    console.print(dashboard.render())
    text = console.export_text()
    assert "ARIA v6.0.0 Control Center" in text
    assert "axum-backend" in text
    assert "ollama" in text


def test_render_shows_the_offline_panel() -> None:
    from rich.console import Console

    class Dead:
        def get(self, url, params=None):
            raise BackendUnreachable("connection refused")

    api = ControlClient(base_url="http://test:8002", transport=Dead(), token=TOKEN)
    console = Console(record=True, width=100, force_terminal=False)
    Dashboard(client=api, console=console).print_once()
    text = console.export_text()
    assert "Backend unreachable" in text
    assert "connection refused" in text


def test_render_handles_an_empty_snapshot() -> None:
    dashboard = Dashboard(client=None)
    renderable = dashboard.render(Snapshot())
    assert renderable is not None


# --- CLI --------------------------------------------------------------------


def test_cli_status_json(runner: CliRunner, wired) -> None:
    wired["routes"] = {("GET", "/api/control/status"): _status_payload()}
    result = runner.invoke(cli, ["--token", TOKEN, "status", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["aria_version"] == "6.0.0"


def test_cli_status_renders_a_dashboard(runner: CliRunner, wired) -> None:
    wired["routes"] = {
        ("GET", "/api/control/status"): _status_payload(),
        ("GET", "/api/control/services"): _services_payload(),
        ("GET", "/api/control/logs"): _logs_payload(),
    }
    result = runner.invoke(cli, ["--token", TOKEN, "status"])
    assert result.exit_code == 0, result.output
    assert "Control Center" in result.output


def test_cli_logs(runner: CliRunner, wired) -> None:
    wired["routes"] = {("GET", "/api/control/logs"): _logs_payload()}
    result = runner.invoke(cli, ["--token", TOKEN, "logs", "-n", "3"])
    assert result.exit_code == 0, result.output
    assert "event 0" in result.output


def test_cli_services(runner: CliRunner, wired) -> None:
    wired["routes"] = {("GET", "/api/control/services"): _services_payload()}
    result = runner.invoke(cli, ["--token", TOKEN, "services", "--json"])
    assert result.exit_code == 0, result.output
    assert len(json.loads(result.output)["services"]) == 3


def test_cli_config_list_get_and_set(runner: CliRunner, wired) -> None:
    wired["routes"] = {
        ("GET", "/api/control/config"): _config_payload(),
        ("POST", "/api/control/config"): {"status": "ok", "key": "release-channel", "value": "testing"},
    }
    listed = runner.invoke(cli, ["--token", TOKEN, "config", "list", "--json"])
    assert listed.exit_code == 0, listed.output
    assert json.loads(listed.output)["config"]["release-channel"] == "stable"

    got = runner.invoke(cli, ["--token", TOKEN, "config", "get", "daemon-port", "--json"])
    assert got.exit_code == 0, got.output
    assert json.loads(got.output) == {"key": "daemon-port", "value": "8002"}

    set_result = runner.invoke(cli, ["--token", TOKEN, "config", "set", "release-channel", "testing"])
    assert set_result.exit_code == 0, set_result.output
    assert "release-channel = testing" in set_result.output


def test_cli_config_get_rejects_an_unknown_key(runner: CliRunner, wired) -> None:
    wired["routes"] = {("GET", "/api/control/config"): _config_payload()}
    result = runner.invoke(cli, ["--token", TOKEN, "config", "get", "nope"])
    assert result.exit_code == EXIT_CONTROL_ERROR
    assert "unknown key" in result.output


def test_cli_plugins(runner: CliRunner, wired) -> None:
    wired["routes"] = {
        ("GET", "/api/control/plugins"): {
            "plugins": [{"name": "chat", "status": "active", "description": "AI chat"}]
        }
    }
    result = runner.invoke(cli, ["--token", TOKEN, "plugins", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["plugins"][0]["name"] == "chat"


def test_cli_restart_requires_confirmation(runner: CliRunner, wired) -> None:
    wired["routes"] = {("POST", "/api/control/restart"): {"status": "accepted", "job_id": "j1"}}
    declined = runner.invoke(cli, ["--token", TOKEN, "restart"], input="n\n")
    assert declined.exit_code == 0
    assert "aborted" in declined.output

    accepted = runner.invoke(cli, ["--token", TOKEN, "restart", "-y", "--json"])
    assert accepted.exit_code == 0, accepted.output
    assert json.loads(accepted.output)["job_id"] == "j1"


def test_cli_upgrade_with_wait(runner: CliRunner, wired) -> None:
    wired["routes"] = {
        ("POST", "/api/control/upgrade"): {"status": "accepted", "job_id": "j9"},
        ("GET", "/api/control/jobs/j9"): {
            "job": {"id": "j9", "kind": "upgrade", "status": "succeeded", "output": "up to date"}
        },
    }
    result = runner.invoke(cli, ["--token", TOKEN, "upgrade", "-y", "--wait", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["job"]["status"] == "succeeded"


def test_cli_job_command(runner: CliRunner, wired) -> None:
    wired["routes"] = {
        ("GET", "/api/control/jobs/j9"): {"job": {"id": "j9", "kind": "upgrade", "status": "failed"}}
    }
    result = runner.invoke(cli, ["--token", TOKEN, "job", "j9", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["job"]["status"] == "failed"


def test_cli_missing_token_exits_with_its_own_code(runner: CliRunner, wired) -> None:
    wired["routes"] = {("GET", "/api/control/status"): _status_payload()}
    result = runner.invoke(cli, ["--token", "", "status", "--json"], env={"ARIA_API_KEY": ""})
    assert result.exit_code == EXIT_NO_TOKEN


def test_cli_unreachable_backend_exits_with_its_own_code(runner: CliRunner, wired) -> None:
    wired["error"] = BackendUnreachable("connection refused")
    result = runner.invoke(cli, ["--token", TOKEN, "services", "--json"])
    assert result.exit_code == EXIT_UNREACHABLE
    assert "connection refused" in result.output


def test_cli_control_error_exits_with_its_own_code(runner: CliRunner, wired) -> None:
    wired["error"] = ControlError("invalid_config", status=400, detail="bad value")
    result = runner.invoke(cli, ["--token", TOKEN, "plugins", "--json"])
    assert result.exit_code == EXIT_CONTROL_ERROR


# --- repository contract ----------------------------------------------------


def test_log_streamer_consumes_frames(monkeypatch) -> None:
    """``aria logs -f`` must connect, authenticate, and skip malformed frames.

    Drives the streamer with a fake socket rather than a live server: the
    previous version of this loop had no ``yield`` and silently degraded into a
    coroutine, which only showed up when a real WebSocket was attached.
    """
    import rich.live
    import websockets

    from aria_control.cli import _stream_logs

    frames = [
        json.dumps({"ts": f"2026-01-01T00:00:0{i}Z", "level": "info", "target": "t", "message": f"m{i}"})
        for i in range(3)
    ]
    rendered: list[int] = []
    captured: dict = {}

    class FakeLive:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def update(self, _frame):
            rendered.append(1)

    class FakeSocket:
        async def __aiter__(self):
            for raw in [*frames, "not json", ""]:
                yield raw

    class FakeConnect:
        def __init__(self, url, additional_headers=None):
            self.url = url
            self.headers = additional_headers

        async def __aenter__(self):
            return FakeSocket()

        async def __aexit__(self, *exc):
            return False

    def fake_connect(url, additional_headers=None):
        captured["url"] = url
        captured["headers"] = additional_headers
        return FakeConnect(url, additional_headers)

    monkeypatch.setattr(rich.live, "Live", FakeLive)
    monkeypatch.setattr(websockets, "connect", fake_connect)

    _stream_logs(ControlClient(base_url="http://127.0.0.1:8002", token="tok"))

    assert captured["url"] == "ws://127.0.0.1:8002/api/control/logs/stream"
    assert captured["headers"] == {"Authorization": "Bearer tok"}
    # Three valid frames; the two unparseable ones are dropped, not rendered.
    assert len(rendered) == 3


def test_every_click_colour_is_valid() -> None:
    """Guard against ``fg="dim"`` and friends.

    click raises ``ValueError: Unknown color`` at render time, so a bad colour
    survives a normal test run and only explodes on the operator's terminal.
    """
    import re

    from click.termui import _ansi_colors

    source = (REPO_ROOT / "aria_control" / "cli.py").read_text(encoding="utf-8")
    used = set(re.findall(r'fg="([a-z_]+)"', source))
    assert used, "no colours found; the regex is probably wrong"
    invalid = sorted(used - set(_ansi_colors))
    assert not invalid, f"unknown click colours: {invalid}"


def test_render_job_accepts_a_dispatched_payload(runner: CliRunner, wired) -> None:
    """A 202 body (no nested 'job') must render, not crash on a bad colour."""
    wired["routes"] = {
        ("POST", "/api/control/restart"): {
            "status": "accepted",
            "job_id": "j1",
            "command": "aria-updater.exe --restart-services",
            "poll": "/api/control/jobs/j1",
        }
    }
    result = runner.invoke(cli, ["--token", TOKEN, "restart", "-y"])
    assert result.exit_code == 0, result.output
    assert "ACCEPTED" in result.output
    assert "aria-updater.exe" in result.output


def test_aria_console_script_is_declared() -> None:
    import tomllib

    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    assert pyproject["project"]["scripts"]["aria"] == "aria_control.cli:main"


def test_control_routes_are_not_public() -> None:
    """The control plane must stay behind the auth guard.

    ``/api/control/restart`` restarts the machine and ``/logs`` exposes whatever
    was logged; an open control plane on 0.0.0.0 is a remote shell.
    """
    guard = (REPO_ROOT / "v6" / "axum-poc" / "src" / "auth.rs").read_text(encoding="utf-8")
    public_block = guard.split("pub const PUBLIC_PATHS", 1)[1].split(";", 1)[0]
    assert "control" not in public_block
