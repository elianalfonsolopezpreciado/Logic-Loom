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


# --------------------------------------------------------------------- #
# LLVM IR transpiler
# --------------------------------------------------------------------- #
# This lets Logic-Loom plug into a real toolchain: emit the optimized
# expression as an LLVM IR function that clang/opt can compile, inline,
# and vectorize alongside the rest of a C/C++/Rust program.
_LLVM_BINOP = {"+": "fadd", "-": "fsub", "*": "fmul", "/": "fdiv"}
_LLVM_INTRINSIC = {
    "sin": "@llvm.sin.f64", "cos": "@llvm.cos.f64",
    "exp": "@llvm.exp.f64", "log": "@llvm.log.f64",
    "sqrt": "@llvm.sqrt.f64", "^": "@llvm.pow.f64",
}


def _llvm_const(v) -> str:
    return f"{float(v):e}"


def free_vars(e: Expr):
    """Sorted list of variable names in ``e`` (the function parameters)."""
    seen = set()

    def walk(node):
        if node.kind == "var":
            seen.add(node.name)
        for a in node.args:
            walk(a)

    walk(e)
    return sorted(seen)


def to_llvm(e: Expr, name: str = "f") -> str:
    """Render ``e`` as an LLVM IR function ``double @name(double, ...)``."""
    params = free_vars(e)
    body: list[str] = []
    counter = [0]
    used: set[str] = set()

    def fresh() -> str:
        counter[0] += 1
        return f"%t{counter[0]}"

    def emit(node: Expr) -> str:
        if node.kind == "num":
            return _llvm_const(node.value)
        if node.kind == "var":
            return f"%{node.name}"
        if node.kind == "patvar":
            raise ValueError("cannot generate IR from a pattern variable")

        op = node.name
        if op == "neg":
            x = emit(node.args[0])
            r = fresh()
            body.append(f"  {r} = fneg double {x}")
            return r
        if op in _LLVM_BINOP:
            a = emit(node.args[0])
            b = emit(node.args[1])
            r = fresh()
            body.append(f"  {r} = {_LLVM_BINOP[op]} double {a}, {b}")
            return r
        if op in _LLVM_INTRINSIC:
            args = [emit(a) for a in node.args]
            fn = _LLVM_INTRINSIC[op]
            used.add(op)
            r = fresh()
            joined = ", ".join(f"double {a}" for a in args)
            body.append(f"  {r} = call double {fn}({joined})")
            return r
        # external function fallback
        args = [emit(a) for a in node.args]
        used.add(op)
        r = fresh()
        joined = ", ".join(f"double {a}" for a in args)
        body.append(f"  {r} = call double @{op}({joined})")
        return r

    ret = emit(e)
    sig = ", ".join(f"double %{p}" for p in params)

    decls = []
    for op in sorted(used):
        if op in _LLVM_INTRINSIC:
            fn = _LLVM_INTRINSIC[op]
            arity = 2 if op == "^" else 1
            decls.append(f"declare double {fn}({', '.join(['double'] * arity)})")
        else:
            decls.append(f"declare double @{op}(double)")

    lines = []
    lines.extend(decls)
    if decls:
        lines.append("")
    lines.append(f"define double @{name}({sig}) {{")
    lines.append("entry:")
    lines.extend(body)
    lines.append(f"  ret double {ret}")
    lines.append("}")
    return "\n".join(lines)
