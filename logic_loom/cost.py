"""Cost models and extraction.

Equality saturation produces a graph containing *all* discovered forms.
Extraction is the step that asks: of every equivalent term, which is the
"best"?  "Best" is defined by a :class:`CostModel` -- a table of weights
for each operation -- and a fixed-point that computes the cheapest term
in each e-class under that model.

The weights matter.  On real hardware the cost of an operation depends on
the architecture (FPU latency, whether a fused multiply-add exists, how
expensive a division or a transcendental call is, vector throughput, and
so on).  Logic-Loom ships several illustrative profiles calibrated to the
*relative* latencies typical of each target, and you can load your own
profile measured with micro-benchmarks.

    cost(x86) of a division ~= 4 multiplies
    cost(gpu) of a division ~= 8 multiplies, transcendental calls ~= 16

Change the profile and the compiler's notion of "optimal" changes with it
-- the same input can extract to different code for a CPU and a GPU.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, Tuple

from .egraph import ENode, EGraph
from .expr import Expr


@dataclass(frozen=True)
class CostModel:
    """Weights used to score expressions.

    ``op_cost`` maps an operator/function head to its weight; anything not
    listed falls back to ``func_cost`` (for transcendental calls) or, for
    leaves, ``leaf_cost``.
    """

    name: str
    op_cost: Dict[str, float]
    leaf_cost: float = 0.1
    func_cost: float = 5.0

    def node_weight(self, node: ENode) -> float:
        head, args = node
        if not args:
            return self.leaf_cost
        return self.op_cost.get(head, self.func_cost)

    def expr_weight(self, e: Expr) -> float:
        if e.is_leaf:
            return self.leaf_cost
        own = self.op_cost.get(e.name, self.func_cost)
        return own + sum(self.expr_weight(a) for a in e.args)

    @staticmethod
    def from_json(path: str) -> "CostModel":
        """Load a measured cost profile from a JSON file.

        Expected shape::

            {"name": "my-cpu", "leaf_cost": 0.1, "func_cost": 12,
             "op_cost": {"+": 1, "*": 3, "/": 14, "^": 20, "sin": 18}}
        """
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return CostModel(
            name=data.get("name", path),
            op_cost={k: float(v) for k, v in data["op_cost"].items()},
            leaf_cost=float(data.get("leaf_cost", 0.1)),
            func_cost=float(data.get("func_cost", 5.0)),
        )


# Illustrative profiles.  The numbers are *relative* latencies in the
# spirit of published instruction tables; replace with micro-benchmarked
# values for production use.
_TRIG = {"sin": 12.0, "cos": 12.0, "tan": 18.0, "exp": 12.0, "log": 14.0, "sqrt": 6.0}

PROFILES: Dict[str, CostModel] = {
    # Balanced default: the historical Logic-Loom weights.
    "default": CostModel("default",
                         {"+": 1.0, "-": 1.0, "neg": 1.0, "*": 2.0, "/": 4.0, "^": 6.0},
                         func_cost=5.0),
    # Modern x86: FMA makes mul/add cheap and roughly equal; div is costly.
    "x86": CostModel("x86",
                     {"+": 1.0, "-": 1.0, "neg": 0.5, "*": 1.0, "/": 4.0, "^": 8.0,
                      **_TRIG},
                     func_cost=12.0),
    # ARM (e.g. Apple/Cortex): similar, slightly cheaper div, pricier trig.
    "arm": CostModel("arm",
                     {"+": 1.0, "-": 1.0, "neg": 0.5, "*": 1.0, "/": 3.0, "^": 8.0,
                      **{k: v * 1.2 for k, v in _TRIG.items()}},
                     func_cost=14.0),
    # GPU: arithmetic is cheap and parallel; division and transcendentals
    # are comparatively very expensive (special-function units).
    "gpu": CostModel("gpu",
                     {"+": 1.0, "-": 1.0, "neg": 0.5, "*": 1.0, "/": 8.0, "^": 16.0,
                      **{k: v * 1.5 for k, v in _TRIG.items()}},
                     func_cost=16.0),
}

DEFAULT_MODEL = PROFILES["default"]


def get_profile(name: str) -> CostModel:
    if name not in PROFILES:
        raise ValueError(f"unknown profile {name!r}; choose from {list(PROFILES)}")
    return PROFILES[name]


def _node_key(node: ENode):
    """Stable sort key for an e-node (heads may be str or numeric)."""
    head, args = node
    return (0, head) if isinstance(head, str) else (1, head), args


def node_cost(node: ENode, model: CostModel = DEFAULT_MODEL) -> float:
    return model.node_weight(node)


def expr_cost(e: Expr, model: CostModel = DEFAULT_MODEL) -> float:
    """Cost of a concrete tree under ``model`` (for reporting)."""
    return model.expr_weight(e)


def extract(eg: EGraph, root: int, model: CostModel = DEFAULT_MODEL) -> Tuple[Expr, float]:
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
            # Sort nodes so that cost ties break deterministically, making
            # the extracted form reproducible regardless of hash seed.
            for node in sorted(eg.nodes_of(cid), key=_node_key):
                head, args = node
                # A node is only extractable once all its children are.
                if any(eg.find(a) not in best_cost for a in args):
                    continue
                total = model.node_weight(node) + sum(
                    best_cost[eg.find(a)] for a in args)
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
