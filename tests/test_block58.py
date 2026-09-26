"""Tests for BLOQUE 58 - AURA Local Secure Code Execution Sandbox & Isolated Worker Engine.

Valida (100% local, sin cloud):
- SandboxOutcome: enumeracion de resultados.
- SandboxExecutionResult: serializacion y campos.
- SandboxConfig: deteccion de patrones peligrosos.
- IsolatedSandboxRunner: ejecucion, timeout, bloqueo, lint, test.
- Endpoints REST /api/agent/sandbox/*: status, execute, lint, executions.

Nota: los tests REST usan un app liviano sin cargar backend.main pesado.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.agent.sandbox import (
    IsolatedSandboxRunner,
    SandboxConfig,
    SandboxExecutionResult,
    SandboxOutcome,
    analyze_python_code,
    get_sandbox_runner,
    lint_python_code,
    reset_sandbox_runner,
)


class TestSandboxOutcome:
    def test_enum_values(self):
        assert SandboxOutcome.SUCCESS.value == "success"
        assert SandboxOutcome.FAILED.value == "failed"
        assert SandboxOutcome.TIMEOUT.value == "timeout"
        assert SandboxOutcome.KILLED.value == "killed"
        assert SandboxOutcome.BLOCKED.value == "blocked"
        assert SandboxOutcome.ERROR.value == "error"

    def test_enum_is_str(self):
        assert isinstance(SandboxOutcome.SUCCESS, str)
        assert SandboxOutcome.SUCCESS == "success"


class TestSandboxExecutionResult:
    def test_to_dict_serializes_all_fields(self):
        result = SandboxExecutionResult(
            execution_id="exec-001",
            code_hash="abc123",
            outcome=SandboxOutcome.SUCCESS,
            stdout="hello world",
            stderr="",
            return_code=0,
            duration_ms=150.5,
            memory_used_mb=32.0,
            peak_memory_mb=48.0,
            cpu_time_ms=100.0,
        )
        d = result.to_dict()
        assert d["execution_id"] == "exec-001"
        assert d["code_hash"] == "abc123"
        assert d["outcome"] == "success"
        assert d["stdout"] == "hello world"
        assert d["return_code"] == 0
        assert d["duration_ms"] == 150.5
        assert d["memory_used_mb"] == 32.0
        assert d["peak_memory_mb"] == 48.0
        assert d["cpu_time_ms"] == 100.0

    def test_to_dict_with_defaults(self):
        result = SandboxExecutionResult(
            execution_id="exec-002",
            code_hash="def456",
            outcome=SandboxOutcome.BLOCKED,
        )
        d = result.to_dict()
        assert d["stdout"] == ""
        assert d["stderr"] == ""
        assert d["return_code"] is None
        assert d["duration_ms"] == 0.0
        assert d["blocked_paths"] == []
        assert d["warnings"] == []


class TestSandboxConfig:
    def test_default_values(self):
        config = SandboxConfig()
        assert config.timeout_seconds == 30.0
        assert config.memory_limit_mb == 256.0
        assert config.cpu_time_limit_seconds == 10.0
        assert config.max_output_chars == 65536
        assert config.restrict_network is True
        assert config.restrict_filesystem is True

    def test_custom_values(self):
        config = SandboxConfig(timeout_seconds=60.0, memory_limit_mb=512.0)
        assert config.timeout_seconds == 60.0
        assert config.memory_limit_mb == 512.0

    def test_detects_system_paths(self):
        config = SandboxConfig()
        blocked = config.is_code_blocked("import os; os.system('cat /etc/passwd')")
        assert len(blocked) > 0
        assert any("ruta del sistema" in b for b in blocked)

    def test_detects_dangerous_commands(self):
        config = SandboxConfig()
        blocked = config.is_code_blocked("os.system('rm -rf /')")
        assert len(blocked) > 0
        assert any("rm -rf" in b for b in blocked)

    def test_detects_shutdown_commands(self):
        config = SandboxConfig()
        blocked = config.is_code_blocked("os.system('shutdown now')")
        assert len(blocked) > 0
        assert any("shutdown" in b for b in blocked)

    def test_allows_safe_code(self):
        config = SandboxConfig()
        blocked = config.is_code_blocked("x = 1 + 2\nprint(x)")
        assert len(blocked) == 0

    def test_detects_ssh_paths(self):
        config = SandboxConfig()
        blocked = config.is_code_blocked("open('/home/user/.ssh/id_rsa').read()")
        assert len(blocked) > 0
        assert any(".ssh" in b for b in blocked)

    def test_detects_aws_paths(self):
        config = SandboxConfig()
        blocked = config.is_code_blocked("open('/home/user/.aws/credentials').read()")
        assert len(blocked) > 0
        assert any(".aws" in b for b in blocked)

    def test_detects_env_files(self):
        config = SandboxConfig()
        blocked = config.is_code_blocked("open('.env').read()")
        assert len(blocked) > 0
        assert any(".env" in b for b in blocked)


class TestIsolatedSandboxRunner:
    @pytest.fixture()
    def runner(self, tmp_path):
        reset_sandbox_runner()
        r = IsolatedSandboxRunner(workspace_dir=tmp_path / "sandbox")
        yield r
        reset_sandbox_runner()

    @pytest.mark.asyncio
    async def test_execute_safe_code(self, runner):
        result = await runner.execute("print('hello world')")
        assert result.outcome == SandboxOutcome.SUCCESS
        assert "hello world" in result.stdout
        assert result.return_code == 0

    @pytest.mark.asyncio
    async def test_execute_failing_code(self, runner):
        result = await runner.execute("raise ValueError('test error')")
        assert result.outcome == SandboxOutcome.FAILED
        assert result.return_code != 0

    @pytest.mark.asyncio
    async def test_execute_syntax_error(self, runner):
        result = await runner.execute("def foo(")
        assert result.outcome == SandboxOutcome.FAILED

    @pytest.mark.asyncio
    async def test_execute_timeout(self, runner):
        result = await runner.execute(
            "import time; time.sleep(10)",
            timeout=1.0,
        )
        assert result.outcome == SandboxOutcome.TIMEOUT

    @pytest.mark.asyncio
    async def test_execute_blocks_dangerous_code(self, runner):
        result = await runner.execute("import os; os.system('rm -rf /')")
        assert result.outcome == SandboxOutcome.BLOCKED
        assert len(result.blocked_paths) > 0

    @pytest.mark.asyncio
    async def test_execute_blocks_unsupported_language(self, runner):
        result = await runner.execute("echo hello", language="bash")
        assert result.outcome == SandboxOutcome.BLOCKED

    @pytest.mark.asyncio
    async def test_get_execution_result(self, runner):
        result = await runner.execute("x = 42")
        fetched = runner.get_execution_result(result.execution_id)
        assert fetched is not None
        assert fetched.execution_id == result.execution_id

    @pytest.mark.asyncio
    async def test_list_recent_executions(self, runner):
        await runner.execute("a = 1")
        await runner.execute("b = 2")
        executions = runner.list_recent_executions()
        assert len(executions) == 2

    @pytest.mark.asyncio
    async def test_clear_executions(self, runner):
        await runner.execute("c = 3")
        count = runner.clear_executions()
        assert count == 1
        assert len(runner.list_recent_executions()) == 0

    @pytest.mark.asyncio
    async def test_get_status(self, runner):
        await runner.execute("d = 4")
        status = runner.get_status()
        assert "total_executions" in status
        assert status["total_executions"] == 1
        assert "outcomes" in status
        assert "config" in status


class TestLintAndTest:
    def test_lint_valid_code(self):
        result = lint_python_code("x = 1 + 2")
        assert result["valid"] is True
        assert result["error_count"] == 0

    def test_lint_invalid_code(self):
        result = lint_python_code("def foo(")
        assert result["valid"] is False
        assert result["error_count"] == 1
        assert len(result["error_messages"]) == 1
        assert result["error_messages"][0]["type"] == "SyntaxError"

    def test_lint_detects_imports(self):
        result = lint_python_code("import os")
        assert result["valid"] is True
        assert any("os" in w for w in result["warnings"])

    def test_lint_detects_eval(self):
        result = lint_python_code("eval('1 + 2')")
        assert result["valid"] is True
        assert any("eval" in w for w in result["warnings"])

    def test_lint_detects_exec(self):
        result = lint_python_code("exec('print(1)')")
        assert result["valid"] is True
        assert any("exec" in w for w in result["warnings"])

    def test_test_code_valid(self):
        result = analyze_python_code("import pytest")
        assert result["syntax_valid"] is True
        assert "pytest" in result["test_imports"]

    def test_test_code_no_tests(self):
        result = analyze_python_code("x = 1")
        assert result["syntax_valid"] is True
        assert result["test_imports"] == []


class TestSandboxREST:
    @pytest.fixture()
    def client(self):
        reset_sandbox_runner()
        from backend.agent.sandbox_routes import router as sandbox_router

        app = FastAPI()
        app.include_router(sandbox_router)

        with TestClient(app) as c:
            yield c
        reset_sandbox_runner()

    def test_sandbox_status(self, client):
        r = client.get("/api/agent/sandbox/status")
        assert r.status_code == 200
        body = r.json()
        assert "total_executions" in body
        assert "outcomes" in body
        assert "config" in body

    def test_execute_endpoint(self, client):
        r = client.post(
            "/api/agent/sandbox/execute",
            json={
                "code": "print('hello from sandbox')",
                "language": "python",
                "timeout_seconds": 5.0,
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["outcome"] == "success"
        assert "hello from sandbox" in body["stdout"]

    def test_execute_blocks_dangerous(self, client):
        r = client.post(
            "/api/agent/sandbox/execute",
            json={
                "code": "import os; os.system('rm -rf /')",
                "language": "python",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["outcome"] == "blocked"

    def test_list_executions(self, client):
        client.post(
            "/api/agent/sandbox/execute",
            json={
                "code": "x = 1",
            },
        )
        r = client.get("/api/agent/sandbox/executions")
        assert r.status_code == 200
        assert r.json()["count"] >= 1

    def test_lint_endpoint(self, client):
        r = client.post(
            "/api/agent/sandbox/lint",
            json={
                "code": "x = 1 + 2",
            },
        )
        assert r.status_code == 200
        assert r.json()["valid"] is True

    def test_lint_endpoint_invalid(self, client):
        r = client.post(
            "/api/agent/sandbox/lint",
            json={
                "code": "def foo(",
            },
        )
        assert r.status_code == 200
        assert r.json()["valid"] is False

    def test_test_endpoint(self, client):
        r = client.post(
            "/api/agent/sandbox/test",
            json={
                "code": "import pytest",
            },
        )
        assert r.status_code == 200
        assert r.json()["syntax_valid"] is True

    def test_cleanup_endpoint(self, client):
        client.post("/api/agent/sandbox/execute", json={"code": "y = 2"})
        r = client.post("/api/agent/sandbox/cleanup", json={})
        assert r.status_code == 200
        assert r.json()["cleaned"] >= 1

    def test_reset_endpoint(self, client):
        r = client.post("/api/agent/sandbox/reset")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_get_execution_not_found(self, client):
        r = client.get("/api/agent/sandbox/executions/non-existent-id")
        assert r.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
