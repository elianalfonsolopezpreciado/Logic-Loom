"""Command-line interface:  python -m logic_loom "a*b + a*c"."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .codegen import to_code
from .compiler import build_egraph, optimize
from .rules import ALL_RULES, DEFAULT_RULES
from .viz import to_dot


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="logic_loom",
        description="A compiler that understands mathematics. "
        "Give it an expression; it returns the cheapest equivalent form.",
    )
    p.add_argument("expression", nargs="*", help="math expression, e.g. 'a*b + a*c'")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="show saturation statistics")
    p.add_argument("--extended", action="store_true",
                   help="enable transcendental-function rules (exp/log/sqrt/trig)")
    p.add_argument("--lang", choices=["c", "rust", "js"],
                   help="also emit the optimized form as source code")
    p.add_argument("--dot", action="store_true",
                   help="print the saturated e-graph as Graphviz DOT")
    p.add_argument("--max-iters", type=int, default=30)
    p.add_argument("--node-limit", type=int, default=5000)
    p.add_argument("--version", action="version", version=f"logic-loom {__version__}")
    args = p.parse_args(argv)

    rules = ALL_RULES if args.extended else DEFAULT_RULES
    sources = [" ".join(args.expression)] if args.expression else _read_stdin()
    if not sources:
        p.print_help()
        return 1

    for src in sources:
        src = src.strip()
        if not src:
            continue

        if args.dot:
            eg, root, _ = build_egraph(
                src, rules=rules, max_iters=args.max_iters,
                node_limit=args.node_limit)
            print(to_dot(eg, root))
            continue

        r = optimize(src, rules=rules, max_iters=args.max_iters,
                     node_limit=args.node_limit)
        print(r)
        if args.lang:
            print(f"  {args.lang}: {to_code(r.optimized, args.lang)}")
        if args.verbose:
            rep = r.report
            print(f"  [{rep.stop_reason}] iterations={rep.iterations} "
                  f"e-nodes={rep.nodes} e-classes={rep.classes}")
            if rep.banned:
                print(f"  throttled rules: {', '.join(rep.banned)}")
    return 0


def _read_stdin():
    if sys.stdin.isatty():
        return []
    return sys.stdin.read().splitlines()


if __name__ == "__main__":
    raise SystemExit(main())
