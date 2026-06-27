"""Extended-rule tests, including numeric validation on safe domains."""

import math
import random

import pytest

from logic_loom import ALL_RULES, evaluate, optimize


def opt(src):
    return optimize(src, rules=ALL_RULES).optimized


def test_log_exp_inverse():
    assert str(opt("log(exp(x))")) == "x"
    assert str(opt("exp(log(x))")) == "x"


def test_pythagorean_identity():
    assert str(opt("sin(x)^2 + cos(x)^2")) == "1"


def test_sqrt_squared():
    assert str(opt("sqrt(x) * sqrt(x)")) == "x"


def test_exp_product_to_sum():
    # exp(a)*exp(b) collapses two calls into one
    r = optimize("exp(a) * exp(b)", rules=ALL_RULES)
    assert r.optimized_cost < r.original_cost


# Numeric soundness on the natural (positive) domains for log / sqrt.
CASES = [
    "log(a*b)",
    "log(a) + log(b)",
    "exp(a) * exp(b)",
    "log(exp(x))",
    "sqrt(a) * sqrt(b)",
    "sin(x)^2 + cos(x)^2",
]


@pytest.mark.parametrize("src", CASES)
def test_extended_preserves_value(src):
    r = optimize(src, rules=ALL_RULES)
    rng = random.Random(7)
    for _ in range(100):
        env = {v: rng.uniform(0.5, 3.0) for v in "abx"}
        a = evaluate(r.original, env)
        b = evaluate(r.optimized, env)
        assert a == pytest.approx(b, rel=1e-9, abs=1e-9)
