"""Logic-Loom showcase.

Run with:  python examples/demo.py
(from the repository root, or after `pip install -e .`)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running straight from a checkout without installing.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from logic_loom import ALL_RULES, optimize, to_code  # noqa: E402

SHOWCASE = [
    ("The distributive law (factoring)", "a*b + a*c"),
    ("Factoring three shared terms",      "p*q + p*r + p*s"),
    ("Horner's scheme, discovered",       "a*x*x + b*x + c"),
    ("Algebraic cancellation",            "a*(b + c) - a*b"),
    ("Constant folding + identities",     "2*3 + 4*x*0 + a*1"),
    ("Like terms collapse",               "2*x + 3*x"),
    ("Self-inverse vanishes",             "x + 0 - x + 5"),
    ("Division cancels to one",           "x/x + y - y"),
    ("Combine over a denominator",        "(a+b)/c + (a-b)/c"),
]

# Transcendental rules (opt-in): exp / log / sqrt / trig identities.
EXTENDED_SHOWCASE = [
    ("Logs turn products into sums",   "log(a*b)"),
    ("exp and log are inverse",        "log(exp(x))"),
    ("Two exponentials become one",    "exp(a) * exp(b)"),
    ("Pythagorean identity",           "sin(x)^2 + cos(x)^2"),
    ("Square root squared",            "sqrt(x) * sqrt(x)"),
]


def banner(text: str) -> None:
    print("\n" + "=" * 64)
    print(f"  {text}")
    print("=" * 64)


def main() -> None:
    print("Logic-Loom -- a compiler that reasons about algebra\n")
    for title, expr in SHOWCASE:
        banner(title)
        r = optimize(expr)
        arrow = "==>" if r.improved else "==="
        print(f"  in   : {r.original}")
        print(f"  out  : {r.optimized}    {arrow}")
        print(f"  cost : {r.original_cost:.1f}  ->  {r.optimized_cost:.1f} "
              f"  ({r.speedup:.2f}x cheaper)")
        print(f"  graph: {r.report.nodes} e-nodes explored "
              f"in {r.report.iterations} rounds ({r.report.stop_reason})")

    banner("Extended domain: transcendental functions (--extended)")
    for title, expr in EXTENDED_SHOWCASE:
        r = optimize(expr, rules=ALL_RULES)
        print(f"  {title:32} {r.original}  ->  {r.optimized}")

    banner("Code generation: optimize once, emit anywhere")
    e = optimize("a*x*x + b*x + c").optimized
    print(f"  optimized: {e}")
    for lang in ("c", "rust", "js"):
        print(f"    {lang:4}: {to_code(e, lang)}")
    print()


if __name__ == "__main__":
    main()
