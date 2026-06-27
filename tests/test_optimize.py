from logic_loom import optimize, parse


def opt(src):
    return optimize(src).optimized


def cost_of(src):
    return optimize(src).optimized_cost


def test_factoring():
    # a*b + a*c  must collapse to a single multiply + add
    r = optimize("a*b + a*c")
    assert r.improved
    assert r.optimized_cost < r.original_cost


def test_constant_folding():
    assert str(opt("2*3 + 4")) == "10"
    assert str(opt("2 ^ 10")) == "1024"


def test_identities():
    assert str(opt("x + 0")) == "x"
    assert str(opt("x * 1")) == "x"
    assert str(opt("x * 0")) == "0"


def test_cancellation():
    assert str(opt("x - x")) == "0"
    assert str(opt("x / x")) == "1"
    assert str(opt("a*(b + c) - a*b")) == "a * c" or str(opt("a*(b + c) - a*b")) == "c * a"


def test_like_terms():
    # 2x + 3x -> 5x  (one multiply, no add)
    assert cost_of("2*x + 3*x") < cost_of("0") + 3  # cheaper than original add+2 muls
    r = optimize("2*x + 3*x")
    assert r.optimized_cost < r.original_cost


def test_three_way_factor():
    r = optimize("p*q + p*r + p*s")
    assert r.improved
    # one multiply by p, plus two adds inside
    assert r.optimized_cost <= 5.0


def test_no_regression():
    # An already-optimal expression should not get worse.
    r = optimize("a + b")
    assert r.optimized_cost <= r.original_cost
