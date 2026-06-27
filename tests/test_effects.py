from logic_loom import optimize


def test_pure_baseline_simplifies():
    # Without impurity, these collapse as usual.
    assert str(optimize("rand(s) - rand(s)").optimized) == "0"
    assert optimize("rand(s) + rand(s)").improved


def test_impure_blocks_elimination():
    # Marking rand impure must prevent dropping a call.
    r = optimize("rand(s) - rand(s)", impure={"rand"})
    assert str(r.optimized) == "rand(s) - rand(s)"


def test_impure_blocks_count_change():
    # rand + rand must not become 2*rand (that would call rand once).
    r = optimize("rand(s) + rand(s)", impure={"rand"})
    assert str(r.optimized) == "rand(s) + rand(s)"


def test_impure_blocks_factoring_a_call():
    # Factoring the shared impure call would change how often it runs.
    r = optimize("a*rand(s) + b*rand(s)", impure={"rand"})
    assert "rand(s) * (a + b)" not in str(r.optimized)
    assert str(r.optimized).count("rand(s)") == 2


def test_pure_factor_around_impure_is_allowed():
    # Here the shared factor 'a' is pure, and each impure call still runs
    # exactly once, so factoring is permitted.
    r = optimize("a*f(x) + a*g(y)", impure={"f", "g"})
    assert str(r.optimized).count("f(x)") == 1
    assert str(r.optimized).count("g(y)") == 1
