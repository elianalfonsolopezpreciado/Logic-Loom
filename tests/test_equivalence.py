"""Soundness tests: an optimization must never change what an expression means.

For each case we optimize, then evaluate the original and the optimized
form on many random assignments and assert they agree.  This is the
property that makes the whole exercise trustworthy -- the compiler is
allowed to be clever, but never wrong.
"""

import random

import pytest

from logic_loom import evaluate, optimize, parse

CASES = [
    "a*b + a*c",
    "p*q + p*r + p*s",
    "a*x*x + b*x + c",
    "a*(b + c) - a*b",
    "2*x + 3*x",
    "(a + b)/c + (a - b)/c",
    "x + 0 - x + 5",
    "(a + b) * (a + b)",
    "a*b*c + a*b*d",
    "x^2 + 2*x + 1",
]

VARS = "abcdpqrsxy"


@pytest.mark.parametrize("src", CASES)
def test_optimization_preserves_value(src):
    r = optimize(src)
    orig, opt = r.original, r.optimized
    rng = random.Random(1234)
    for _ in range(200):
        env = {v: rng.uniform(1.0, 5.0) for v in VARS}
        a = evaluate(orig, env)
        b = evaluate(opt, env)
        assert a == pytest.approx(b, rel=1e-9, abs=1e-9), (
            f"{src!r}: {orig} = {a} but optimized {opt} = {b}"
        )
