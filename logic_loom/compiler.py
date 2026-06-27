"""High-level API: turn a math string into its cheapest equivalent form."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .cost import expr_cost, extract
from .egraph import EGraph
from .expr import Expr
from .parser import parse
from .rules import DEFAULT_RULES, Rule
from .saturate import SaturationReport, saturate


@dataclass
class Result:
    source: str
    original: Expr
    optimized: Expr
    original_cost: float
    optimized_cost: float
    report: SaturationReport

    @property
    def improved(self) -> bool:
        return self.optimized_cost < self.original_cost - 1e-9

    @property
    def speedup(self) -> float:
        if self.optimized_cost <= 0:
            return float("inf")
        return self.original_cost / self.optimized_cost

    def __str__(self) -> str:
        arrow = "=>" if self.improved else "=="
        return (
            f"{self.original}  {arrow}  {self.optimized}\n"
            f"  cost {self.original_cost:.1f} -> {self.optimized_cost:.1f}"
            f"  ({self.speedup:.2f}x)"
        )


def optimize(
    source: str,
    *,
    rules: Optional[List[Rule]] = None,
    max_iters: int = 30,
    node_limit: int = 10_000,
) -> Result:
    """Parse, saturate and extract the cheapest equivalent of ``source``."""
    original = parse(source)
    eg = EGraph()
    root = eg.add_expr(original)
    report = saturate(
        eg,
        rules if rules is not None else DEFAULT_RULES,
        max_iters=max_iters,
        node_limit=node_limit,
    )
    optimized, opt_cost = extract(eg, root)
    return Result(
        source=source,
        original=original,
        optimized=optimized,
        original_cost=expr_cost(original),
        optimized_cost=opt_cost,
        report=report,
    )
