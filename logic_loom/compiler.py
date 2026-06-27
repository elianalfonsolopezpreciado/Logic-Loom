"""High-level API: turn a math string into its cheapest equivalent form."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from .analysis import analyze, reachable_rules
from .cost import DEFAULT_MODEL, CostModel, expr_cost, extract, get_profile
from .egraph import EGraph
from .expr import Expr
from .parser import parse
from .rules import DEFAULT_RULES, Rule
from .saturate import BackoffScheduler, SaturationReport, saturate


@dataclass
class Result:
    source: str
    original: Expr
    optimized: Expr
    original_cost: float
    optimized_cost: float
    report: SaturationReport
    model: CostModel = DEFAULT_MODEL
    assumptions: List[str] = field(default_factory=list)

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


def _resolve_model(model, profile) -> CostModel:
    if profile is not None:
        return get_profile(profile)
    if model is not None:
        return model
    return DEFAULT_MODEL


def _prepare(source, rules, auto, node_limit):
    """Parse and, if auto, statically prune rules and size the limits."""
    original = parse(source)
    rules = list(rules) if rules is not None else list(DEFAULT_RULES)
    if auto:
        rules = reachable_rules(original, rules)
        an = analyze(original)
        nl = node_limit if node_limit is not None else an.node_limit
        scheduler = BackoffScheduler(match_limit=an.match_limit)
    else:
        nl = node_limit if node_limit is not None else 5_000
        scheduler = None
    return original, rules, nl, scheduler


def build_egraph(
    source: str,
    *,
    rules: Optional[List[Rule]] = None,
    auto: bool = True,
    max_iters: int = 30,
    node_limit: Optional[int] = None,
    impure: Optional[Iterable[str]] = None,
):
    """Parse and saturate ``source``; return ``(egraph, root_id, report)``."""
    original, rules, nl, scheduler = _prepare(source, rules, auto, node_limit)
    eg = EGraph()
    root = eg.add_expr(original)
    report = saturate(eg, rules, max_iters=max_iters, node_limit=nl,
                      scheduler=scheduler, impure=set(impure or ()))
    return eg, root, report


def optimize(
    source: str,
    *,
    rules: Optional[List[Rule]] = None,
    model: Optional[CostModel] = None,
    profile: Optional[str] = None,
    impure: Optional[Iterable[str]] = None,
    auto: bool = True,
    max_iters: int = 30,
    node_limit: Optional[int] = None,
) -> Result:
    """Parse, saturate and extract the cheapest equivalent of ``source``.

    Parameters
    ----------
    rules    : rewrite rules to use (defaults to ``DEFAULT_RULES``).
    model    : a :class:`~logic_loom.cost.CostModel` for extraction.
    profile  : name of a built-in cost profile ("x86", "arm", "gpu", ...);
               overrides ``model`` when given.
    impure   : names of side-effecting functions; rewrites that would
               duplicate, drop, or reorder their calls are forbidden.
    auto     : enable static rule pruning and automatic limit sizing.
    """
    cost_model = _resolve_model(model, profile)
    original, used_rules, nl, scheduler = _prepare(source, rules, auto, node_limit)

    eg = EGraph()
    root = eg.add_expr(original)
    report = saturate(eg, used_rules, max_iters=max_iters, node_limit=nl,
                      scheduler=scheduler, impure=set(impure or ()))
    optimized, opt_cost = extract(eg, root, cost_model)

    by_name = {r.name: r for r in used_rules}
    assumptions = sorted({
        a for name in report.fired
        for a in by_name.get(name, Rule(name, original, original)).assumes
    })

    return Result(
        source=source,
        original=original,
        optimized=optimized,
        original_cost=expr_cost(original, cost_model),
        optimized_cost=opt_cost,
        report=report,
        model=cost_model,
        assumptions=assumptions,
    )
