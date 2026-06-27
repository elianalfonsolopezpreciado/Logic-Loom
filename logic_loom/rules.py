"""Rewrite rules and e-matching.

A :class:`Rule` is a pair of patterns (lhs, rhs).  ``ematch`` searches
the e-graph for every way the lhs can be instantiated; ``instantiate``
builds the rhs from a substitution.  The saturation engine then unions
each found lhs class with the freshly built rhs class.

Crucially, rules are applied *non-destructively*: rewriting never throws
away the original form, it only adds the new form as an equality.  That
is what lets contradictory-looking rules (distribute **and** factor,
commute both ways) coexist without looping forever or losing the best
answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterator, List

from .egraph import EGraph
from .expr import Expr
from .parser import parse

Subst = Dict[str, int]


# --------------------------------------------------------------------- #
# e-matching
# --------------------------------------------------------------------- #
def ematch(eg: EGraph, pattern: Expr, eid: int, subst: Subst) -> Iterator[Subst]:
    """Yield every extension of ``subst`` that makes ``pattern`` match ``eid``."""
    root = eg.find(eid)

    if pattern.kind == "patvar":
        bound = subst.get(pattern.name)
        if bound is None:
            new = dict(subst)
            new[pattern.name] = root
            yield new
        elif eg.find(bound) == root:
            yield subst
        return

    if pattern.kind == "num":
        for (head, args) in eg.nodes_of(root):
            if not args and head == pattern.value and not isinstance(head, str):
                yield subst
        return

    if pattern.kind == "var":
        for (head, args) in eg.nodes_of(root):
            if not args and head == pattern.name:
                yield subst
        return

    # pattern.kind == "app"
    for (head, args) in eg.nodes_of(root):
        if head == pattern.name and len(args) == len(pattern.args):
            yield from _match_args(eg, pattern.args, args, subst)


def _match_args(eg, pats, eids, subst: Subst) -> Iterator[Subst]:
    if not pats:
        yield subst
        return
    for s in ematch(eg, pats[0], eids[0], subst):
        yield from _match_args(eg, pats[1:], eids[1:], s)


def instantiate(eg: EGraph, pattern: Expr, subst: Subst) -> int:
    """Add ``pattern`` (filled in from ``subst``) to the e-graph."""
    if pattern.kind == "patvar":
        return eg.find(subst[pattern.name])
    if pattern.kind == "num":
        return eg.add_node((pattern.value, ()))
    if pattern.kind == "var":
        return eg.add_node((pattern.name, ()))
    child_ids = tuple(instantiate(eg, a, subst) for a in pattern.args)
    return eg.add_node((pattern.name, child_ids))


# --------------------------------------------------------------------- #
# rules
# --------------------------------------------------------------------- #
@dataclass(frozen=True)
class Rule:
    name: str
    lhs: Expr
    rhs: Expr
    # Domain preconditions under which the rewrite is sound (human readable),
    # e.g. "x != 0".  Empty means valid for all real inputs.
    assumes: Tuple[str, ...] = ()
    # True if the rule changes the left-to-right order of operands, which
    # matters when operands have side effects (see logic_loom/effects.py).
    reorders: bool = False

    def search(self, eg: EGraph):
        out = []
        for eid in eg.eclasses():
            if eid not in eg.classes:        # may have been merged away
                continue
            for subst in ematch(eg, self.lhs, eid, {}):
                out.append((eid, subst))
        return out


def rule(name: str, lhs: str, rhs: str, *,
         assumes: Tuple[str, ...] = (), reorders: bool = False) -> Rule:
    return Rule(name, parse(lhs), parse(rhs), assumes=tuple(assumes),
                reorders=reorders)


# The algebraic "knowledge" of the compiler.  Each line is a theorem the
# engine is allowed to use in either the direction written.
DEFAULT_RULES: List[Rule] = [
    # commutativity (reorders operands)
    rule("comm-add", "?a + ?b", "?b + ?a", reorders=True),
    rule("comm-mul", "?a * ?b", "?b * ?a", reorders=True),
    # associativity (both directions)
    rule("assoc-add",  "(?a + ?b) + ?c", "?a + (?b + ?c)"),
    rule("assoc-add2", "?a + (?b + ?c)", "(?a + ?b) + ?c"),
    rule("assoc-mul",  "(?a * ?b) * ?c", "?a * (?b * ?c)"),
    rule("assoc-mul2", "?a * (?b * ?c)", "(?a * ?b) * ?c"),
    # the distributive law -- the star of the show, both ways
    rule("distribute", "?a * (?b + ?c)", "?a*?b + ?a*?c"),
    rule("factor",     "?a*?b + ?a*?c", "?a * (?b + ?c)"),
    # identities
    rule("add-0",   "?a + 0", "?a"),
    rule("mul-1",   "?a * 1", "?a"),
    rule("mul-0",   "?a * 0", "0"),
    rule("sub-0",   "?a - 0", "?a"),
    rule("div-1",   "?a / 1", "?a"),
    rule("pow-1",   "?a ^ 1", "?a"),
    rule("pow-0",   "?a ^ 0", "1"),
    # cancellation
    rule("sub-self", "?a - ?a", "0"),
    rule("div-self", "?a / ?a", "1", assumes=("?a != 0",)),
    # combine like terms / introduce powers
    rule("self-add",  "?a + ?a", "2 * ?a"),
    rule("self-mul",  "?a * ?a", "?a ^ 2"),
    rule("pow-mul",   "?a^?b * ?a^?c", "?a ^ (?b + ?c)"),
    rule("mul-pow",   "?a * ?a^?b", "?a ^ (?b + 1)"),
    # subtraction <-> negation, distribute over minus
    rule("sub-neg",   "?a - ?b", "?a + neg(?b)"),
    rule("neg-mul",   "neg(?a)", "(-1) * ?a"),
    rule("distribute-sub", "?a * (?b - ?c)", "?a*?b - ?a*?c"),
    rule("factor-sub",     "?a*?b - ?a*?c", "?a * (?b - ?c)"),
    # division distributes / factors over a shared denominator
    rule("split-div", "(?a + ?b) / ?c", "?a/?c + ?b/?c"),
    rule("join-div",  "?a/?c + ?b/?c", "(?a + ?b) / ?c"),
]


# Optional rules for transcendental functions.  These reason about the
# *algebra* of exp / log / sqrt / trig and are validated numerically in
# the test-suite.  They assume the usual real domains (log and sqrt of a
# positive argument), so they live behind an opt-in flag rather than in
# the default set.
EXTENDED_RULES: List[Rule] = [
    # exponentials and logarithms are inverse, and turn products into sums
    rule("exp-prod",   "exp(?a) * exp(?b)", "exp(?a + ?b)"),
    rule("exp-sum",    "exp(?a + ?b)", "exp(?a) * exp(?b)"),
    rule("log-prod",   "log(?a * ?b)", "log(?a) + log(?b)",
         assumes=("?a > 0", "?b > 0")),
    rule("log-sum",    "log(?a) + log(?b)", "log(?a * ?b)",
         assumes=("?a > 0", "?b > 0")),
    rule("log-exp",    "log(exp(?x))", "?x"),
    rule("exp-log",    "exp(log(?x))", "?x", assumes=("?x > 0",)),
    rule("exp-0",      "exp(0)", "1"),
    rule("log-1",      "log(1)", "0"),
    # square root
    rule("sqrt-sq",    "sqrt(?x) * sqrt(?x)", "?x", assumes=("?x >= 0",)),
    rule("sqrt-prod",  "sqrt(?a) * sqrt(?b)", "sqrt(?a * ?b)",
         assumes=("?a >= 0", "?b >= 0")),
    # the Pythagorean identity, in both directions
    rule("pyth",       "sin(?x)^2 + cos(?x)^2", "1"),
    rule("sin0",       "sin(0)", "0"),
    rule("cos0",       "cos(0)", "1"),
]

ALL_RULES: List[Rule] = DEFAULT_RULES + EXTENDED_RULES
