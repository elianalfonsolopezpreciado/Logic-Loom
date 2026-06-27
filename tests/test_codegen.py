from logic_loom import parse, to_code


def test_basic_operators():
    e = parse("a*x + b")
    assert to_code(e, "c") == "a * x + b"
    assert to_code(e, "js") == "a * x + b"
    assert to_code(e, "rust") == "a * x + b"


def test_power_per_language():
    e = parse("x ^ 3")
    assert to_code(e, "c") == "pow(x, 3)"
    assert to_code(e, "js") == "Math.pow(x, 3)"
    assert to_code(e, "rust") == "(x).powf(3)"


def test_functions_per_language():
    e = parse("exp(a) + sqrt(b)")
    assert to_code(e, "c") == "exp(a) + sqrt(b)"
    assert to_code(e, "js") == "Math.exp(a) + Math.sqrt(b)"
    assert to_code(e, "rust") == "a.exp() + b.sqrt()"


def test_parentheses_preserved():
    e = parse("(a + b) * c")
    assert to_code(e, "c") == "(a + b) * c"


def test_unary_minus():
    e = parse("-(a + b)")
    assert to_code(e, "c") == "-(a + b)"
