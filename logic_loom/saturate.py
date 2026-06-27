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

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .egraph import EGraph
from .rules import DEFAULT_RULES, Rule, instantiate


@dataclass
class SaturationReport:
    iterations: int
    saturated: bool
    nodes: int
    classes: int
    stop_reason: str
    banned: List[str] = field(default_factory=list)


class BackoffScheduler:
    """Throttle rules that fire explosively (after egg's BackoffScheduler).

    Associative/commutative rules can match thousands of times in a single
    round, drowning the useful rewrites and blowing up the graph.  When a
    rule exceeds its match budget it is *banned* for a few iterations; its
    budget then doubles, so a genuinely productive rule is only delayed,
    never silenced.  This is a far smarter limit than a flat node cap: it
    lets cheap, high-value rules keep working while reining in the ones
    that merely reshuffle the same terms.
    """

    def __init__(self, match_limit: int = 1000, ban_length: int = 4):
        self.match_limit = match_limit
        self.ban_length = ban_length
        self._banned_until: Dict[str, int] = {}
        self._times_banned: Dict[str, int] = {}
        self.ever_banned: set[str] = set()

    def is_banned(self, name: str, iteration: int) -> bool:
        return iteration < self._banned_until.get(name, 0)

    def threshold(self, name: str) -> int:
        return self.match_limit << self._times_banned.get(name, 0)

    def record(self, name: str, n_matches: int, iteration: int) -> bool:
        """Note how often a rule matched. Returns True if it just got banned."""
        if n_matches > self.threshold(name):
            self._times_banned[name] = self._times_banned.get(name, 0) + 1
            self._banned_until[name] = iteration + self.ban_length
            self.ever_banned.add(name)
            return True
        return False


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
    scheduler: Optional[BackoffScheduler] = None,
) -> SaturationReport:
    rules = rules if rules is not None else DEFAULT_RULES
    if scheduler is None:
        scheduler = BackoffScheduler()
    saturated = False
    stop = "max-iters"
    it = 0
    for it in range(1, max_iters + 1):
        # Stop before an expensive search if we are already at the cap.
        # The scheduler curbs most growth, but a hard node cap is the final
        # guarantee of termination.
        if eg.num_nodes() > node_limit:
            stop = "node-limit"
            break

        # 1. search each rule, letting the scheduler throttle explosive ones.
        matches = []
        for r in rules:
            if scheduler.is_banned(r.name, it):
                continue
            found = r.search(eg)
            if scheduler.record(r.name, len(found), it):
                continue          # just banned: skip applying this round
            matches.extend((r, m) for m in found)

        # 2. apply every surviving match, guarding the graph size.
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
            # Nothing learned this round.  If rules are only idle because
            # they are temporarily banned, keep going; otherwise we are done.
            if any(scheduler.is_banned(r.name, it) for r in rules):
                continue
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
        banned=sorted(scheduler.ever_banned),
    )
