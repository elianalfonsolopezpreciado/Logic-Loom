"""Cost model and extraction.

Equality saturation produces a graph containing *all* discovered forms.
Extraction is the step that asks: of every equivalent term, which is the
"best"?  We use a simple, transparent cost model -- the weighted number
of operations -- and a fixed-point that computes the cheapest term in
each e-class.

The weights below encode a rough hardware reality: multiplies cost more
than adds, divisions and powers more still.  Change them and the
compiler's notion of "optimal" changes with it.
"""

from __future__ import annotations

from typing import Dict, Tuple

from .egraph import ENode, EGraph
from .expr import Expr

OP_COST = {
    "+": 1.0,
    "-": 1.0,
    "neg": 1.0,
    "*": 2.0,
    "/": 4.0,
    "^": 6.0,
}
LEAF_COST = 0.1          # tiny, so leaves are essentially free
DEFAULT_FUNC_COST = 5.0  # sin, cos, log, ... unknown funcs


def node_cost(node: ENode) -> float:
    head, args = node
    if not args:
        return LEAF_COST
    return OP_COST.get(head, DEFAULT_FUNC_COST)


def extract(eg: EGraph, root: int) -> Tuple[Expr, float]:
    """Return the cheapest expression equivalent to e-class ``root``."""
    best_cost: Dict[int, float] = {}
    best_node: Dict[int, ENode] = {}

    changed = True
    while changed:
        changed = False
        for eid in eg.eclasses():
            if eid not in eg.classes:
                continue
            cid = eg.find(eid)
            for node in eg.nodes_of(cid):
                head, args = node
                # A node is only extractable once all its children are.
                if any(eg.find(a) not in best_cost for a in args):
                    continue
                total = node_cost(node) + sum(best_cost[eg.find(a)] for a in args)
                if cid not in best_cost or total < best_cost[cid] - 1e-12:
                    best_cost[cid] = total
                    best_node[cid] = node
                    changed = True

    return _build(eg, eg.find(root), best_node), best_cost[eg.find(root)]


def _build(eg: EGraph, eid: int, best_node: Dict[int, ENode]) -> Expr:
    head, args = best_node[eid]
    if not args:
        if isinstance(head, str):
            return Expr.var(head)
        return Expr.num(head)
    children = tuple(_build(eg, eg.find(a), best_node) for a in args)
    return Expr.app(head, *children)


def expr_cost(e: Expr) -> float:
    """Cost of a concrete tree, using the same weights (for reporting)."""
    if e.is_leaf:
        return LEAF_COST
    return OP_COST.get(e.name, DEFAULT_FUNC_COST) + sum(expr_cost(a) for a in e.args)
