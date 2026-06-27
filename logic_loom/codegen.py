"""Emit an optimized expression as source code in a real language.

The whole point of optimizing an expression is to *run* it. This module
turns an :class:`Expr` tree into a snippet of C, Rust or JavaScript, so
the optimized form can be pasted straight into a program.

    >>> from logic_loom import optimize, to_code
    >>> e = optimize("a*x*x + b*x + c").optimized
    >>> print(to_code(e, "c"))
    x * (a * x + b) + c
"""

from __future__ import annotations

from .expr import Expr

# Per-language rendering of operators and functions.
_LANGS = {
    "c": {
        "pow": lambda a, b: f"pow({a}, {b})",
        "funcs": {"sin": "sin", "cos": "cos", "tan": "tan",
                  "exp": "exp", "log": "log", "sqrt": "sqrt"},
    },
    "rust": {
        "pow": lambda a, b: f"({a}).powf({b})",
        "funcs": {"sin": "{0}.sin()", "cos": "{0}.cos()", "tan": "{0}.tan()",
                  "exp": "{0}.exp()", "log": "{0}.ln()", "sqrt": "{0}.sqrt()"},
    },
    "js": {
        "pow": lambda a, b: f"Math.pow({a}, {b})",
        "funcs": {"sin": "Math.sin", "cos": "Math.cos", "tan": "Math.tan",
                  "exp": "Math.exp", "log": "Math.log", "sqrt": "Math.sqrt"},
    },
}

_INFIX = {"+": "+", "-": "-", "*": "*", "/": "/"}
_PREC = {"+": 1, "-": 1, "*": 2, "/": 2, "neg": 3, "^": 4}


def to_code(e: Expr, lang: str = "c") -> str:
    """Render ``e`` as an expression in ``lang`` (``"c"``, ``"rust"`` or ``"js"``)."""
    lang = lang.lower()
    if lang not in _LANGS:
        raise ValueError(f"unsupported language {lang!r}; choose from {list(_LANGS)}")
    return _emit(e, _LANGS[lang], 0)


def _emit(e: Expr, spec, parent_prec: int) -> str:
    if e.kind == "num":
        v = e.value
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        return str(v)
    if e.kind == "var":
        return e.name
    if e.kind == "patvar":
        raise ValueError("cannot generate code from a pattern variable")

    op = e.name
    if op == "neg":
        return f"-{_emit(e.args[0], spec, _PREC['neg'])}"

    if op == "^":
        a = _emit(e.args[0], spec, 0)
        b = _emit(e.args[1], spec, 0)
        return spec["pow"](a, b)

    if op in _INFIX:
        prec = _PREC[op]
        left = _emit(e.args[0], spec, prec)
        right = _emit(e.args[1], spec, prec + 1)
        s = f"{left} {_INFIX[op]} {right}"
        return f"({s})" if prec < parent_prec else s

    # function call
    funcs = spec["funcs"]
    if op in funcs:
        args = [_emit(a, spec, 0) for a in e.args]
        tmpl = funcs[op]
        if "{0}" in tmpl:                     # method style (Rust)
            return tmpl.format(*args)
        return f"{tmpl}({', '.join(args)})"   # call style (C / JS)

    # unknown function: emit verbatim
    args = ", ".join(_emit(a, spec, 0) for a in e.args)
    return f"{op}({args})"
