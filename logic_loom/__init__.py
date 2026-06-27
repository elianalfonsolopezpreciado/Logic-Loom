"""Logic-Loom: a compiler that understands mathematics.

Instead of peephole-optimizing instructions, Logic-Loom reasons about
the *algebra* of an expression.  It uses equality saturation over an
e-graph to discover the whole space of equivalent forms, then extracts
the cheapest one under a configurable, hardware-aware cost model.

    >>> from logic_loom import optimize
    >>> print(optimize("a*b + a*c"))
    a * b + a * c  =>  a * (b + c)
      cost 5.4 -> 3.3  (1.64x)
"""

from .analysis import Analysis, analyze, reachable_rules
from .codegen import free_vars, to_code, to_llvm
from .compiler import Result, build_egraph, optimize
from .cost import (
    DEFAULT_MODEL,
    PROFILES,
    CostModel,
    expr_cost,
    extract,
    get_profile,
)
from .effects import is_effect_safe, tainted_classes
from .egraph import EGraph
from .expr import Expr, evaluate
from .parser import parse
from .rules import ALL_RULES, DEFAULT_RULES, EXTENDED_RULES, Rule, rule
from .saturate import BackoffScheduler, SaturationReport, saturate
from .viz import to_dot

__version__ = "0.3.0"

__all__ = [
    "optimize",
    "build_egraph",
    "Result",
    "Expr",
    "evaluate",
    "parse",
    "EGraph",
    "Rule",
    "rule",
    "DEFAULT_RULES",
    "EXTENDED_RULES",
    "ALL_RULES",
    "saturate",
    "SaturationReport",
    "BackoffScheduler",
    "extract",
    "expr_cost",
    "CostModel",
    "PROFILES",
    "DEFAULT_MODEL",
    "get_profile",
    "to_code",
    "to_llvm",
    "free_vars",
    "to_dot",
    "analyze",
    "Analysis",
    "reachable_rules",
    "tainted_classes",
    "is_effect_safe",
    "__version__",
]
