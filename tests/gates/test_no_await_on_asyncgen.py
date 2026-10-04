"""Gate C2 — ninguna función async generator puede consumirse con `await`.

AIRouter.generate_response era un async generator (tenía `yield` en el cuerpo)
pero sus cuatro llamadores hacían `await` sobre él. Eso lanza TypeError en
runtime, y como cada caller lo envolvía en un `except` genérico, el router
simulaba funcionar mientras nunca devolvía una respuesta.

El mismo bug existía como `asyncio.run(generator)` en código síncrono, que es
un `Call`, no un `Await`, así que también lo detectamos.

Aquí no buscamos por anotación (`-> AsyncGenerator[...]`): buscamos la forma real
del bug — una async function con `yield` propio usada como valor de `await` o
como argumento de `asyncio.run`/`run_until_complete`.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCAN_DIRS = (ROOT / "backend", ROOT / "ARIA_APP" / "backend")

SYNC_RUNNERS = {"run", "run_until_complete"}


def _own_yields(node: ast.AsyncFunctionDef) -> list:
    """Yields propios de la función; se ignoran los de funciones anidadas."""
    found: list = []

    def visit(current: ast.AST) -> None:
        for child in ast.iter_child_nodes(current):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            if isinstance(child, (ast.Yield, ast.YieldFrom)):
                found.append(child)
            visit(child)

    visit(node)
    return found


def _async_generator_names(tree: ast.Module) -> set:
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and _own_yields(node)
    }


def _called_name(value: ast.AST) -> str | None:
    """Nombre de la función invocada por una expresión, si se puede resolver."""
    if isinstance(value, ast.Call):
        return _called_name(value.func)
    if isinstance(value, ast.Attribute):
        return value.attr
    if isinstance(value, ast.Name):
        return value.id
    return None


def find_violations(tree: ast.Module) -> list:
    """(línea, nombre, tipo) por cada consumo inválido de un async generator."""
    generators = _async_generator_names(tree)
    if not generators:
        return []

    violations: list = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Await):
            name = _called_name(node.value)
            if name in generators:
                violations.append((node.lineno, name, "await"))
        elif isinstance(node, ast.Call):
            runner = _called_name(node.func)
            if runner in SYNC_RUNNERS:
                for arg in list(node.args) + [kw.value for kw in node.keywords]:
                    name = _called_name(arg)
                    if name in generators:
                        violations.append((node.lineno, name, runner))
    return violations


def _python_files() -> list:
    files: list = []
    for directory in SCAN_DIRS:
        if directory.is_dir():
            files.extend(sorted(directory.rglob("*.py")))
    return files


def test_backend_and_app_dirs_exist():
    assert SCAN_DIRS[0].is_dir(), "no se encontró backend/"
    assert SCAN_DIRS[1].is_dir(), "no se encontró ARIA_APP/backend/"


def test_detector_flags_the_original_bug():
    """Autoverificación: el detector debe ver el bug exacto que corregimos."""
    source = """
async def generate_response(self, prompt):
    yield "chunk"

class Caller:
    async def run(self, router):
        return await router.generate_response("hola")

def sync_caller(router):
    import asyncio
    return asyncio.run(router.generate_response("hola"))
"""
    violations = find_violations(ast.parse(source))
    kinds = {kind for _, _, kind in violations}
    assert len(violations) == 2, violations
    assert {"await", "run"} <= kinds, kinds


def test_detector_allows_valid_streaming_patterns():
    source = """
class R:
    async def _chunks(self):
        yield "a"

    async def stream(self):
        async for c in self._chunks():
            yield c

    async def collect(self):
        out = []
        async for c in self._chunks():
            out.append(c)
        return out

async def wrapper(agen):
    async def consume():
        return [c async for c in agen]
    return await consume()
"""
    assert find_violations(ast.parse(source)) == []


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: p.name)
def test_no_await_on_async_generator(path: pathlib.Path):
    source = path.read_text(encoding="utf-8-sig", errors="replace")
    violations = find_violations(ast.parse(source))
    assert not violations, (
        f"{path}: async generator consumido de forma invalida -> "
        + ", ".join(f"linea {line} ({kind}) sobre {name}" for line, name, kind in violations)
    )