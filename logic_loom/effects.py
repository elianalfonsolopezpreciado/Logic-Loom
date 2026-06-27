"""Side-effect awareness.

By default Logic-Loom assumes expressions are *pure*: a term can be freely
duplicated, dropped, or reordered because evaluating it has no observable
effect beyond its value.  That assumption breaks for something like

    a*b + func()

if ``func`` reads input, draws a random number, or mutates state.  Then
``factor``-ing must not turn two calls into one, ``a - a`` must not erase a
call, and commuting must not change the order effects happen in.

You opt in by naming the impure functions.  Logic-Loom then *taints* every
e-class that can contain such a call and refuses any rewrite that would
change how many times a tainted term runs, or in what order:

    optimize("f() - f()", impure={"f"})   # stays f() - f(), NOT 0

The check is deliberately conservative -- when in doubt it keeps the
effect -- which is exactly what soundness in the presence of side effects
requires.
"""

from __future__ import annotations

from typing import Dict, Set

from .egraph import EGraph
from .expr import Expr


def count_patvars(e: Expr, acc: Dict[str, int] | None = None) -> Dict[str, int]:
    """How many times each pattern variable occurs in a rule side."""
    if acc is None:
        acc = {}
    if e.kind == "patvar":
        acc[e.name] = acc.get(e.name, 0) + 1
    else:
        for a in e.args:
            count_patvars(a, acc)
    return acc


def tainted_classes(eg: EGraph, impure: Set[str]) -> Set[int]:
    """Return the set of e-classes that can contain an impure call.

    Impurity propagates upward: a class is tainted if it holds an impure
    call directly, or any of its e-nodes has a tainted child.
    """
    if not impure:
        return set()
    tainted: Set[int] = set()
    changed = True
    while changed:
        changed = False
        for cid in eg.eclasses():
            if cid not in eg.classes:
                continue
            c = eg.find(cid)
            if c in tainted:
                continue
            for (head, args) in eg.nodes_of(c):
                # A class is tainted if it names an impure function (with or
                # without arguments) or builds on a tainted operand.
                is_impure_call = isinstance(head, str) and head in impure
                if is_impure_call or any(eg.find(a) in tainted for a in args):
                    tainted.add(c)
                    changed = True
                    break
    return tainted


def is_effect_safe(rule, subst: Dict[str, int], eg: EGraph,
                   tainted: Set[int]) -> bool:
    """True if applying ``rule`` under ``subst`` cannot disturb side effects."""
    if not tainted:
        return True
    counts_l = count_patvars(rule.lhs)
    counts_r = count_patvars(rule.rhs)
    for var, cid in subst.items():
        if eg.find(cid) in tainted:
            # Duplicating or dropping a tainted term changes how often it runs.
            if counts_l.get(var, 0) != counts_r.get(var, 0):
                return False
            # Reordering a tainted term changes the order of effects.
            if rule.reorders:
                return False
    return True
