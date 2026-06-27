from logic_loom import analyze, parse, reachable_rules
from logic_loom.rules import ALL_RULES, DEFAULT_RULES


def test_pruning_drops_unreachable_rules():
    # A pure polynomial can never reach exp/log/sqrt/trig: no operator in it
    # introduces those functions, so the transcendental rules are dropped.
    expr = parse("a*b + a*c")
    kept = reachable_rules(expr, ALL_RULES)
    names = {r.name for r in kept}
    assert "factor" in names
    assert "log-prod" not in names
    assert "sqrt-sq" not in names
    assert "exp-prod" not in names
    assert len(kept) < len(ALL_RULES)


def test_pruning_keeps_reachable_function_rules():
    # When sqrt actually appears, its rules survive pruning.
    kept = reachable_rules(parse("sqrt(a) + sqrt(b)"), ALL_RULES)
    assert "sqrt-prod" in {r.name for r in kept}


def test_pruning_is_result_preserving():
    # Pruning must not change the optimization outcome.
    from logic_loom import optimize
    expr = "a*b + a*c"
    full = optimize(expr, auto=False)
    pruned = optimize(expr, auto=True)
    assert str(pruned.optimized) == str(full.optimized)


def test_analysis_scales_limits_with_complexity():
    small = analyze(parse("a + b"))
    big = analyze(parse("a*b + c*d + e*f + g*h + i*j"))
    assert big.ac_ops > small.ac_ops
    assert big.node_limit >= small.node_limit
