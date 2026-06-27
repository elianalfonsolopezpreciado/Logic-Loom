"""The equality-saturation engine.

Repeatedly:  search every rule against the e-graph, apply all matches at
once, fold constants, and rebuild congruence -- until nothing new is
learned (the graph is *saturated*) or a resource limit is hit.

Applying every match in lock-step (rather than one rewrite at a time)
is what makes the result independent of rule ordering: the engine is not
"choosing" a rewrite path, it is discovering the entire space of
equivalent forms and only later extracting the best one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .egraph import EGraph
from .rules import DEFAULT_RULES, Rule, instantiate


@dataclass
class SaturationReport:
    iterations: int
    saturated: bool
    nodes: int
    classes: int
    stop_reason: str


# arithmetic that constant folding knows how to perform
def _const_of(eg: EGraph, eid: int) -> Optional[float]:
    for (head, args) in eg.nodes_of(eid):
        if not args and not isinstance(head, str):
            return head
    return None


def _fold(eg: EGraph) -> bool:
    """Evaluate any node whose operands are all constants. Returns True if changed."""
    changed = False
    for eid in eg.eclasses():
        if eid not in eg.classes:
            continue
        for (head, args) in list(eg.nodes_of(eg.find(eid))):
            if not isinstance(head, str) or not args:
                continue
            vals = [_const_of(eg, a) for a in args]
            if any(v is None for v in vals):
                continue
            result = _apply_op(head, vals)
            if result is None:
                continue
            new_id = eg.add_node((_normalize_num(result), ()))
            if eg.merge(new_id, eid):
                changed = True
    if changed:
        eg.rebuild()
    return changed


def _apply_op(head: str, vals: List[float]) -> Optional[float]:
    try:
        if head == "+" and len(vals) == 2:
            return vals[0] + vals[1]
        if head == "-" and len(vals) == 2:
            return vals[0] - vals[1]
        if head == "*" and len(vals) == 2:
            return vals[0] * vals[1]
        if head == "/" and len(vals) == 2:
            if vals[1] == 0:
                return None
            return vals[0] / vals[1]
        if head == "neg" and len(vals) == 1:
            return -vals[0]
        if head == "^" and len(vals) == 2:
            if vals[0] == 0 and vals[1] < 0:
                return None
            return vals[0] ** vals[1]
    except (OverflowError, ValueError, ZeroDivisionError):
        return None
    return None


def _normalize_num(x: float):
    if isinstance(x, float) and x.is_integer():
        return int(x)
    return x


def saturate(
    eg: EGraph,
    rules: Optional[List[Rule]] = None,
    *,
    max_iters: int = 30,
    node_limit: int = 5_000,
) -> SaturationReport:
    rules = rules if rules is not None else DEFAULT_RULES
    saturated = False
    stop = "max-iters"
    it = 0
    for it in range(1, max_iters + 1):
        # Stop before an expensive search if we are already at the cap.
        # Associativity + commutativity make the search space grow without
        # bound, so a resource limit is what guarantees termination.
        if eg.num_nodes() > node_limit:
            stop = "node-limit"
            break

        # 1. search: collect all matches before touching the graph.
        matches = [(r, m) for r in rules for m in r.search(eg)]

        # 2. apply every match, guarding the graph size as we grow it.
        changed = False
        hit_limit = False
        for i, (r, (eid, subst)) in enumerate(matches):
            new_id = instantiate(eg, r.rhs, subst)
            if eg.merge(new_id, eid):
                changed = True
            if i % 500 == 0 and eg.num_nodes() > node_limit:
                hit_limit = True
                break
        eg.rebuild()

        # 3. fold constants.
        folded = _fold(eg)

        if hit_limit:
            stop = "node-limit"
            break
        if not changed and not folded:
            saturated = True
            stop = "saturated"
            break
        if eg.num_nodes() > node_limit:
            stop = "node-limit"
            break

    return SaturationReport(
        iterations=it,
        saturated=saturated,
        nodes=eg.num_nodes(),
        classes=len(eg.classes),
        stop_reason=stop,
    )
