"""Logic-Loom: a compiler that understands mathematics.

Instead of peephole-optimizing instructions, Logic-Loom reasons about
the *algebra* of an expression.  It uses equality saturation over an
e-graph to discover the whole space of equivalent forms, then extracts
the cheapest one.

    >>> from logic_loom import optimize
    >>> print(optimize("a*b + a*c"))
    a * b + a * c  =>  a * (b + c)
      cost 5.4 -> 3.3  (1.64x)
"""

from .codegen import to_code
from .compiler import Result, build_egraph, optimize
from .cost import expr_cost, extract
from .egraph import EGraph
from .expr import Expr, evaluate
from .parser import parse
from .rules import ALL_RULES, DEFAULT_RULES, EXTENDED_RULES, Rule, rule
from .saturate import BackoffScheduler, SaturationReport, saturate
from .viz import to_dot

__version__ = "0.2.0"

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
    "to_code",
    "to_dot",
    "__version__",
]
