import ast
import subprocess
import sys
import time
from typing import Any, Dict


def analyze(code: str) -> Dict[str, Any]:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"status": "error", "syntax_error": str(e), "lineno": e.lineno}
    functions = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    imports = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imports.extend(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            imports.append(n.module or "")
    unsafe = [m for m in imports if m in {"os", "subprocess", "sys", "shutil"}]
    complexity = sum(1 for n in ast.walk(tree) if isinstance(n, (ast.If, ast.For, ast.While, ast.Try, ast.With)))
    return {
        "status": "ok",
        "functions": functions,
        "classes": classes,
        "imports": imports,
        "unsafe_imports": unsafe,
        "branches": complexity,
        "lines": len(code.splitlines()),
    }


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    action = params.get("action", "")
    if action == "analyze":
        return analyze(str(params.get("code", "")))
    if action == "execute":
        code = str(params.get("code", ""))
        timeout = int(params.get("timeout", 10))
        if not code:
            return {"error": "code requerido"}
        syntax = analyze(code)
        if syntax.get("status") == "error":
            return syntax
        start = time.time()
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=timeout)
        return {
            "status": "ok",
            "analysis": syntax,
            "stdout": result.stdout[:3000],
            "stderr": result.stderr[:1000],
            "returncode": result.returncode,
            "duration_ms": round((time.time() - start) * 1000, 1),
        }
    return {"error": f"Unknown action: {action}"}
