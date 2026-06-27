"""Command-line interface:  python -m logic_loom "a*b + a*c"."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .compiler import optimize


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="logic_loom",
        description="A compiler that understands mathematics. "
        "Give it an expression; it returns the cheapest equivalent form.",
    )
    p.add_argument("expression", nargs="*", help="math expression, e.g. 'a*b + a*c'")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="show saturation statistics")
    p.add_argument("--max-iters", type=int, default=30)
    p.add_argument("--node-limit", type=int, default=5000)
    p.add_argument("--version", action="version", version=f"logic-loom {__version__}")
    args = p.parse_args(argv)

    sources = [" ".join(args.expression)] if args.expression else _read_stdin()
    if not sources:
        p.print_help()
        return 1

    for src in sources:
        src = src.strip()
        if not src:
            continue
        r = optimize(src, max_iters=args.max_iters, node_limit=args.node_limit)
        print(r)
        if args.verbose:
            rep = r.report
            print(f"  [{rep.stop_reason}] iterations={rep.iterations} "
                  f"e-nodes={rep.nodes} e-classes={rep.classes}")
    return 0


def _read_stdin():
    if sys.stdin.isatty():
        return []
    return sys.stdin.read().splitlines()


if __name__ == "__main__":
    raise SystemExit(main())
