"""Logic-Loom: a compiler that understands mathematics.

Instead of peephole-optimizing instructions, Logic-Loom reasons about
the *algebra* of an expression.  It uses equality saturation over an
e-graph to discover the whole space of equivalent forms, then extracts
the cheapest one.

    >>> from logic_loom import optimize
    >>> print(optimize("a*b + a*c"))
    a * b + a * c  =>  a * (b + c)
      cost 5.2 -> 3.2  (1.62x)
"""

from .compiler import Result, optimize
from .cost import expr_cost, extract
from .egraph import EGraph
from .expr import Expr, evaluate
from .parser import parse
from .rules import DEFAULT_RULES, Rule, rule
from .saturate import SaturationReport, saturate

__version__ = "0.1.0"

__all__ = [
    "optimize",
    "Result",
    "Expr",
    "evaluate",
    "parse",
    "EGraph",
    "Rule",
    "rule",
    "DEFAULT_RULES",
    "saturate",
    "SaturationReport",
    "extract",
    "expr_cost",
    "__version__",
]
