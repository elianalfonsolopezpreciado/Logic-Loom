"""Expression AST for Logic-Loom.

A single immutable tree type represents both *concrete* expressions
(``a*b + a*c``) and *rule patterns* (``?a*?b + ?a*?c``).  The only
difference is the presence of ``patvar`` nodes, which can only ever
appear inside rewrite-rule patterns.

Node kinds
----------
``num``    -> numeric literal,        carries ``value``
``var``    -> named symbol (e.g. x),  carries ``name``
``patvar`` -> pattern variable (?a),  carries ``name`` (rules only)
``app``    -> operator/function,      carries ``name`` (head) + ``args``

Representing everything with one tiny type keeps the parser, the
e-graph and the pattern matcher in perfect agreement about what a
"sub-expression" is.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Tuple, Union

Number = Union[int, float]


@dataclass(frozen=True)
class Expr:
    kind: str                      # 'num' | 'var' | 'patvar' | 'app'
    value: Number = 0              # for 'num'
    name: str = ""                # for 'var' | 'patvar' | 'app' (head)
    args: Tuple["Expr", ...] = field(default_factory=tuple)

    # -- constructors -------------------------------------------------
    @staticmethod
    def num(value: Number) -> "Expr":
        return Expr("num", value=value)

    @staticmethod
    def var(name: str) -> "Expr":
        return Expr("var", name=name)

    @staticmethod
    def patvar(name: str) -> "Expr":
        return Expr("patvar", name=name)

    @staticmethod
    def app(head: str, *args: "Expr") -> "Expr":
        return Expr("app", name=head, args=tuple(args))

    # -- introspection ------------------------------------------------
    @property
    def is_leaf(self) -> bool:
        return self.kind in ("num", "var", "patvar")

    def __str__(self) -> str:  # human-readable, infix where possible
        return render(self)


# Operators that should be printed infix, with precedence + symbol.
_INFIX = {
    "+": (1, "+"),
    "-": (1, "-"),
    "*": (2, "*"),
    "/": (2, "/"),
    "^": (3, "^"),
}


def render(e: Expr, parent_prec: int = 0) -> str:
    """Pretty-print an expression with the minimum number of parens."""
    if e.kind == "num":
        v = e.value
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        return str(v)
    if e.kind == "var":
        return e.name
    if e.kind == "patvar":
        return "?" + e.name

    # application
    if e.name == "neg" and len(e.args) == 1:
        inner = render(e.args[0], 3)
        return f"-{inner}"

    if e.name in _INFIX and len(e.args) == 2:
        prec, sym = _INFIX[e.name]
        # '^' is right-associative; the others left-associative.
        left = render(e.args[0], prec + (1 if e.name == "^" else 0))
        right = render(e.args[1], prec + (0 if e.name == "^" else 1))
        s = f"{left} {sym} {right}" if e.name != "^" else f"{left}{sym}{right}"
        return f"({s})" if prec < parent_prec else s

    # generic function application: f(a, b, ...)
    inner = ", ".join(render(a, 0) for a in e.args)
    return f"{e.name}({inner})"


_FUNCS = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "exp": math.exp, "log": math.log, "sqrt": math.sqrt,
}


def evaluate(e: Expr, env: Dict[str, float]) -> float:
    """Numerically evaluate a concrete expression given variable values.

    Used by the test-suite to *prove* that an optimization preserved the
    expression's meaning: optimize, then check both forms agree on many
    random inputs.
    """
    if e.kind == "num":
        return float(e.value)
    if e.kind == "var":
        return float(env[e.name])
    if e.kind == "patvar":
        raise ValueError("cannot evaluate a pattern variable")

    a = [evaluate(c, env) for c in e.args]
    op = e.name
    if op == "+":
        return a[0] + a[1]
    if op == "-":
        return a[0] - a[1]
    if op == "*":
        return a[0] * a[1]
    if op == "/":
        return a[0] / a[1]
    if op == "^":
        return a[0] ** a[1]
    if op == "neg":
        return -a[0]
    if op in _FUNCS:
        return _FUNCS[op](*a)
    raise ValueError(f"unknown operator {op!r}")
