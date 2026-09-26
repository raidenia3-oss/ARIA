"""Tests for BLOQUE 56 - Specialized Skills & Dynamic Tool-Registry Engine.

Valida (100% local, sin cloud):
- DynamicToolRegistry: escaneo de modulos built-in, categorias y esquemas.
- SkillExecutionSandbox: coercion tipada, excepciones, timeouts, serializacion.
- Aislamiento: solo callables registrados; traversal rechazado; unknown limpio.
- Integracion con el orquestador (ToolConnector fallback al registro).
- REST /api/agent/tools: listar, esquemas, auditoria, ejecutar, cargar, retirar.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from backend.agents.tools_registry import (
    DynamicToolRegistry,
    ToolEntry,
    get_tools_registry,
    reset_tools_registry,
    tool_registry,
)
from backend.main import app

# ---------------------------------------------------------------- registro ----


class TestRegistryScan:
    def test_builtin_modules_scanned(self):
        tools = {t["name"] for t in tool_registry.list_tools()}
        assert len(tools) >= 9
        assert "text.utils.slugify" in tools
        assert "numeric.compute.average" in tools
        assert "notes.local.write" in tools

    def test_builtin_categories_detected(self):
        categories = {t["category"] for t in tool_registry.list_tools()}
        assert {"text", "numeric", "notes"} <= categories

    def test_function_schema_shape_is_openai_compatible(self):
        schemas = tool_registry.function_schemas()
        assert len(schemas) >= 9
        first = schemas[0]
        assert first["type"] == "function"
        fn = first["function"]
        assert fn["name"] and isinstance(fn["description"], str)
        assert fn["parameters"]["type"] == "object"
        assert "properties" in fn["parameters"]

    def test_rescan_is_idempotent(self):
        before = len(tool_registry.list_tools())
        tool_registry.scan()
        after = len(tool_registry.list_tools())
        assert after >= before
        names = [t["name"] for t in tool_registry.list_tools()]
        assert len(names) == len(set(names))

    def test_register_and_unregister_callable(self):
        reg = DynamicToolRegistry(scripts_dir=None, auto_scan=False)
        reg.register_callable(
            "custom.echo",
            lambda **kw: {"echo": kw.get("text", "")},
            "Devuelve el texto",
            {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        )
        assert reg.has("custom.echo")
        assert reg.unregister("custom.echo") is True
        assert reg.unregister("custom.echo") is False
        assert not reg.has("custom.echo")


# ---------------------------------------------------------------- sandbox -----


def _sandbox_registry():
    reg = DynamicToolRegistry(scripts_dir=None, auto_scan=False)
    schema = lambda props, req: {"type": "object", "properties": props, "required": req}
    reg.register_callable(
        "t.ok",
        lambda **kw: {"got": kw.get("text", "")},
        "ok",
        schema({"text": {"type": "string"}}, ["text"]),
    )
    reg.register_callable(
        "t.typed",
        lambda value, low=0.0, high=1.0: max(low, min(high, float(value))),
        "coercion",
        schema(
            {"value": {"type": "number"}, "low": {"type": "number"}, "high": {"type": "number"}},
            ["value"],
        ),
    )
    reg.register_callable(
        "t.bool", lambda flag: bool(flag), "bool", schema({"flag": {"type": "boolean"}}, ["flag"])
    )

    def _boom():
        raise RuntimeError("fallo controlado")

    reg.register_callable("t.boom", _boom, "raise", schema({}, []))

    def _slow():
        time.sleep(1.0)
        return "ok"

    reg.register_callable("t.slow", _slow, "timeout", schema({}, []))
    reg.register_callable("t.weird", lambda: {"s": {1, 2}}, "no serializable", schema({}, []))

    async def _async_tool(text: str = ""):
        return {"async": text}

    reg.register_callable("t.async", _async_tool, "async", schema({"text": {"type": "string"}}, []))
    return reg


class TestSandboxIsolation:
    @pytest.mark.asyncio
    async def test_executes_registered_tool(self):
        reg = _sandbox_registry()
        out = await reg.execute_tool("t.ok", {"text": "hola"})
        assert out["success"] is True and out["output"] == {"got": "hola"}

    @pytest.mark.asyncio
    async def test_coerces_typed_arguments(self):
        reg = _sandbox_registry()
        out = await reg.execute_tool("t.typed", {"value": "5", "low": "0", "high": "3"})
        assert out["success"] is True and out["output"] == 3.0
        out2 = await reg.execute_tool("t.bool", {"flag": "true"})
        assert out2["success"] is True and out2["output"] is True

    @pytest.mark.asyncio
    async def test_missing_required_argument_fails(self):
        reg = _sandbox_registry()
        out = await reg.execute_tool("t.ok", {})
        assert out["success"] is False
        assert "faltan argumentos requeridos" in out["error"]

    @pytest.mark.asyncio
    async def test_exception_is_captured_not_raised(self):
        reg = _sandbox_registry()
        out = await reg.execute_tool("t.boom", {})
        assert out["success"] is False
        assert "fallo controlado" in out["error"]
        assert reg.get("t.boom").last_error and "fallo controlado" in reg.get("t.boom").last_error

    @pytest.mark.asyncio
    async def test_timeout_is_captured(self):
        reg = _sandbox_registry()
        out = await reg.execute_tool("t.slow", {}, timeout=0.2)
        assert out["success"] is False and "timeout" in out["error"]

    @pytest.mark.asyncio
    async def test_non_serializable_output_is_stringified(self):
        reg = _sandbox_registry()
        out = await reg.execute_tool("t.weird", {})
        assert out["success"] is True and isinstance(out["output"], str)

    @pytest.mark.asyncio
    async def test_async_tool_supported(self):
        reg = _sandbox_registry()
        out = await reg.execute_tool("t.async", {"text": "va"})
        assert out["success"] is True and out["output"] == {"async": "va"}

    @pytest.mark.asyncio
    async def test_unknown_tool_fails_clean(self):
        reg = _sandbox_registry()
        out = await reg.execute_tool("no.existe", {})
        assert out["success"] is False and "unknown tool" in out["error"]

    def test_path_traversal_rejected(self, tmp_path):
        reg = DynamicToolRegistry(scripts_dir=str(tmp_path), auto_scan=False)
        with pytest.raises(ValueError):
            reg.load_from_path("../outside.py")

    def test_load_from_path_registers_module(self, tmp_path):
        reg = DynamicToolRegistry(scripts_dir=str(tmp_path), auto_scan=False)
        (tmp_path / "extra.py").write_text(
            'TOOLS = {"extra.hello": {"description": "d", '
            '"parameters": {"type": "object", "properties": {}, "required": []}, '
            '"func": lambda: "hello"}}',
            encoding="utf-8",
        )
        registered = reg.load_from_path("extra.py")
        assert registered == 1 and reg.has("extra.hello")

    def test_corrupt_module_is_skipped(self, tmp_path):
        (tmp_path / "broken.py").write_text("TOOLS = { esto no es python", encoding="utf-8")
        reg = DynamicToolRegistry(scripts_dir=str(tmp_path), auto_scan=True)
        assert reg.list_tools() == []


# -------------------------------------------------- integracion orquestador ---


class TestOrchestratorIntegration:
    @pytest.mark.asyncio
    async def test_toolconnector_falls_back_to_dynamic_registry(self):
        from backend.agents.orchestrator import ToolConnector, ToolResultStatus

        tc = ToolConnector()
        res = await tc.execute("text.utils.slugify", {"text": "Hola AURA"})
        assert res.status == ToolResultStatus.SUCCESS
        assert "hola-aura" in str(res.output)
        assert res.metadata.get("source") == "dynamic_registry"

    @pytest.mark.asyncio
    async def test_toolconnector_unknown_tool_fails(self):
        from backend.agents.orchestrator import ToolConnector, ToolResultStatus

        res = await ToolConnector().execute("definitivamente.no.existe", {})
        assert res.status == ToolResultStatus.FAILED
        assert "unknown tool" in res.error


# ---------------------------------------------------------------------- REST --


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.delenv("AURA_API_KEY", raising=False)
    reset_tools_registry()
    from backend.main import app

    yield TestClient(app)
    reset_tools_registry()


class TestToolsREST:
    def test_list_tools(self, client):
        r = client.get("/api/agent/tools")
        assert r.status_code == 200
        body = r.json()
        assert body["tools_total"] >= 9
        assert "text" in body["categories"]

    def test_list_tools_category_filter(self, client):
        r = client.get("/api/agent/tools", params={"category": "numeric"})
        assert r.status_code == 200
        body = r.json()
        assert body["tools_total"] >= 3
        assert all(t["category"] == "numeric" for t in body["tools"])

    def test_registry_status(self, client):
        r = client.get("/api/agent/tools/status")
        assert r.status_code == 200
        body = r.json()
        assert body["tools_total"] >= 9
        assert body["scripts_dir"]

    def test_schemas_endpoint(self, client):
        r = client.get("/api/agent/tools/schemas")
        assert r.status_code == 200
        schemas = r.json()["schemas"]
        assert len(schemas) >= 9
        assert schemas[0]["type"] == "function"
        assert schemas[0]["function"]["name"]

    def test_get_single_tool(self, client):
        ok = client.get("/api/agent/tools/text.utils.slugify")
        assert ok.status_code == 200
        assert ok.json()["name"] == "text.utils.slugify"
        assert client.get("/api/agent/tools/nope.nope").status_code == 404

    def test_execute_tool_ok(self, client):
        r = client.post(
            "/api/agent/tools/execute",
            json={
                "tool": "text.utils.slugify",
                "params": {"text": "Hola AURA"},
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["output"] == "hola-aura"

    def test_execute_tool_business_failure_is_400(self, client):
        r = client.post(
            "/api/agent/tools/execute",
            json={
                "tool": "text.utils.slugify",
                "params": {},
            },
        )
        assert r.status_code == 400
        assert "faltan argumentos requeridos" in r.json()["error"]

    def test_execute_unknown_tool_404(self, client):
        r = client.post("/api/agent/tools/execute", json={"tool": "no.existe", "params": {}})
        assert r.status_code == 404

    def test_execute_validates_payload(self, client):
        assert client.post("/api/agent/tools/execute", json={"params": {}}).status_code == 422

    def test_load_skill_module_and_traversal(self, client):
        ok = client.post("/api/agent/tools/load", json={"path": "text_utils.py"})
        assert ok.status_code == 200
        assert ok.json()["loaded"] is True
        assert ok.json()["registered"] >= 1
        bad = client.post("/api/agent/tools/load", json={"path": "../evil.py"})
        assert bad.status_code == 422

    def test_audit_endpoint(self, client):
        r = client.get("/api/agent/tools/audit")
        assert r.status_code == 200
        body = r.json()
        assert body["tools_total"] >= 9
        assert isinstance(body["recent_events"], list)

    def test_unregister_and_reset_restores_builtins(self, client):
        gone = client.delete("/api/agent/tools/notes.sys.timestamp")
        assert gone.status_code == 200
        assert client.get("/api/agent/tools/notes.sys.timestamp").status_code == 404
        again = client.post("/api/agent/tools/unregister", json={"name": "notes.sys.timestamp"})
        assert again.status_code == 404
        reset = client.post("/api/agent/tools/reset")
        assert reset.status_code == 200
        assert reset.json()["tools_total"] >= 9
        assert client.get("/api/agent/tools/notes.sys.timestamp").status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
