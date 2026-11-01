# -*- coding: utf-8 -*-
"""Skill ARIA: calculadora segura (sin eval, solo AST con operadores permitidos)."""
import re
import ast
import operator

SKILL_ENABLED = True

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow,
        ast.FloorDiv: operator.floordiv, ast.USub: operator.neg, ast.UAdd: operator.pos}


def _ev(node):
    if isinstance(node, ast.Expression):
        return _ev(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_ev(node.left), _ev(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_ev(node.operand))
    raise ValueError("expresion no permitida")


def _expr(msg):
    s = msg.lower()
    for p in ["cuanto es", "cuánto es", "calcula", "resultado de", "="]:
        if p in s:
            s = s.split(p, 1)[1]
    s = s.replace("x", "*").replace("×", "*").replace("÷", "/").replace("^", "**").replace(",", ".")
    m = re.search(r"[-+*/%().\d\s*]+", s)
    return (m.group(0).strip() if m else "")


def match(msg):
    low = msg.lower()
    if any(k in low for k in ["cuanto es", "cuánto es", "calcula", "resultado de"]):
        return True
    return bool(re.fullmatch(r"\s*[-+*/%^×÷().\d\s]+\s*", msg)) and any(c in msg for c in "+-*/%^×÷")


def run(msg):
    expr = _expr(msg)
    if not expr or not any(c in expr for c in "+-*/%"):
        return ""
    try:
        val = _ev(ast.parse(expr, mode="eval"))
    except Exception:
        return ""
    if isinstance(val, float) and val.is_integer():
        val = int(val)
    return "= %s" % val
