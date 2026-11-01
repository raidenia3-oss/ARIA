"""Gate que verifica que los otros gates sigan siendo gates.

 inspired by strix/AGENTS.md: a zero exit code does not mean "clean", it means
"finished without crashing". The verdict lives in the artifact, so read it.

Here the artifacts are the gate sources themselves. A gate that quietly stops
gating is the failure this catches:

- a gate file deleted or emptied
- a test switched to skip or xfail with no reason, which turns a red gate green
- a decorator commented out

This test parses the sources with ast. It does not shell out to pytest, because a
test that runs pytest would recurse.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
GATES_DIR = ROOT / "tests" / "gates"

# Every gate that must exist and gate. Deleting one is a decision, not an
# accident, and should require deleting it here too.
REQUIRED_GATES = (
    "tests/gates/test_no_await_on_asyncgen.py",
    "tests/gates/test_tool_rate_limit.py",
    "tests/gates/test_ai_providers_sync.py",
    "tests/gates/test_doc_links.py",
    "tests/gates/test_aria_no_service_dependency.py",
    "tests/test_aria_eyes.py",
    "tests/test_ai_providers_local_model.py",
    "tests/test_no_tracked_secret_literals.py",
    "tests/test_raphael_core_hud.py",
)

# Marks that legitimately exist. Anything else marked skip/xfail is undeclared.
DECLARED_MARKS = {
    ("skipif", "sys.platform"),
    ("skipif", "not HAS_"),
}


def _gate_sources():
    for rel in REQUIRED_GATES:
        yield rel, ROOT / rel


def _parse(path: pathlib.Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


@pytest.mark.parametrize("rel", REQUIRED_GATES, ids=lambda p: p)
def test_required_gate_exists_and_is_not_empty(rel):
    path = ROOT / rel
    assert path.is_file(), f"gate borrado: {rel}"
    text = path.read_text(encoding="utf-8")
    assert len(text.strip()) > 0, f"gate vacio: {rel}"


@pytest.mark.parametrize("rel", REQUIRED_GATES, ids=lambda p: p)
def test_required_gate_actually_asserts_something(rel):
    """An empty assert-free file passes every run and catches nothing."""
    path = ROOT / rel
    tree = _parse(path)
    asserts = [n for n in ast.walk(tree) if isinstance(n, ast.Assert)]
    raises = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "raises"
    ]
    assert asserts or raises, f"{rel} no tiene ningun assert ni pytest.raises"


@pytest.mark.parametrize("rel", REQUIRED_GATES, ids=lambda p: p)
def test_required_gate_defines_at_least_one_test(rel):
    tree = _parse(ROOT / rel)
    tests = [
        n
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")
    ]
    assert tests, f"{rel} no define ningun test_"


def _own_disable_problems(rel: str) -> list:
    """Problems in the gates named by rel, including rel itself."""
    tree = _parse(ROOT / rel)
    problems = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        for dec in node.decorator_list:
            # @pytest.mark.skip / @pytest.mark.xfail without a reason
            if isinstance(dec, ast.Call) and _dotted(dec.func) in (
                "pytest.mark.skip",
                "pytest.mark.xfail",
            ):
                if not dec.keywords and not dec.args:
                    problems.append(f"{rel}::{node.name} sin reason=")
            elif isinstance(dec, ast.Attribute):
                if _dotted(dec) in ("pytest.mark.skip", "pytest.mark.xfail"):
                    problems.append(f"{rel}::{node.name} decorado sin motivo")
        # bare pytest.skip() with no reason at all. pytest.skip takes the reason
        # as its first positional argument, so pytest.skip("no ffmpeg") is fine;
        # only a call with nothing to say is a silent disable.
        for sub in ast.walk(node):
            if (
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and _dotted(sub.func) == "pytest.skip"
                and not sub.args
                and not sub.keywords
            ):
                problems.append(f"{rel}::{node.name} llama pytest.skip() sin motivo")
    return problems


@pytest.mark.parametrize("rel", REQUIRED_GATES, ids=lambda p: p)
def test_gate_does_not_silently_skip_or_xfail(rel):
    """Undocumented skip/xfail turns a red gate green without anyone noticing."""
    problems = _own_disable_problems(rel)
    assert not problems, "gates desactivados sin documentar:\n  " + "\n  ".join(problems)


def _dotted(node) -> str:
    parts = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def test_gates_dir_exists_and_is_importable():
    assert GATES_DIR.is_dir()
    assert (GATES_DIR / "__init__.py").is_file(), "tests/gates necesita __init__.py"


def test_this_gate_is_not_self_excluded():
    """Si este archivo se desactiva, el resto de este gate tampoco."""
    problems = _own_disable_problems("tests/gates/test_gate_integrity.py")
    assert not problems, "este gate se desactivo a si mismo:\n  " + "\n  ".join(problems)
