"""Static analysis to tame the search before saturation begins.

Equality saturation explores blindly; a little static reasoning about the
input lets us avoid work that provably cannot help.

Two analyses live here:

1. **Reachable-rule pruning.** A rule can only ever fire if the operators
   in its left-hand side are present -- and operators only appear if some
   *other* fireable rule introduces them.  Computing this set as a
   fixed-point lets us drop rules that can never match.  This is sound:
   the pruned rules would have contributed nothing, so the result is
   identical, only reached faster.

2. **Complexity estimate.** Counting associative/commutative operators
   predicts how badly the e-graph might blow up, which we use to size the
   resource limits automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Set

from .expr import Expr


def operators(e: Expr, acc: Set[str] | None = None) -> Set[str]:
    """The set of operator/function heads appearing in ``e``."""
    if acc is None:
        acc = set()
    if e.kind == "app":
        acc.add(e.name)
        for a in e.args:
            operators(a, acc)
    return acc


def _size(e: Expr) -> int:
    return 1 + sum(_size(a) for a in e.args)


def _count_heads(e: Expr, heads) -> int:
    n = 1 if (e.kind == "app" and e.name in heads) else 0
    return n + sum(_count_heads(a, heads) for a in e.args)


@dataclass
class Analysis:
    size: int
    variables: int
    ac_ops: int                 # number of + and * nodes (the explosion driver)
    node_limit: int
    match_limit: int

    def summary(self) -> str:
        return (f"size={self.size} vars={self.variables} ac_ops={self.ac_ops} "
                f"-> node_limit={self.node_limit} match_limit={self.match_limit}")


def reachable_rules(expr: Expr, rules: List) -> List:
    """Keep only rules whose operators can become reachable from ``expr``."""
    reachable = operators(expr)
    rule_ops = [(r, operators(r.lhs), operators(r.rhs)) for r in rules]
    changed = True
    while changed:
        changed = False
        for _r, lhs_ops, rhs_ops in rule_ops:
            if lhs_ops <= reachable and not rhs_ops <= reachable:
                reachable |= rhs_ops
                changed = True
    return [r for r, lhs_ops, _ in rule_ops if lhs_ops <= reachable]


def analyze(expr: Expr) -> Analysis:
    size = _size(expr)
    variables = len({v for v in _vars(expr)})
    ac = _count_heads(expr, {"+", "*"})
    # Small inputs can saturate fully; large AC-heavy ones need tighter
    # budgets so we stop early with the best form found instead of thrashing.
    node_limit = min(20_000, max(2_000, 400 * (ac + 1)))
    match_limit = 2_000 if ac <= 3 else max(300, 2_000 // ac)
    return Analysis(size=size, variables=variables, ac_ops=ac,
                    node_limit=node_limit, match_limit=match_limit)


def _vars(e: Expr, acc: Set[str] | None = None) -> Set[str]:
    if acc is None:
        acc = set()
    if e.kind == "var":
        acc.add(e.name)
    for a in e.args:
        _vars(a, acc)
    return acc
