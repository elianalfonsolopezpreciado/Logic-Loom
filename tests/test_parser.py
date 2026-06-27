from logic_loom import parse


def roundtrip(src, expected):
    assert str(parse(src)) == expected


def test_precedence():
    roundtrip("a + b * c", "a + b * c")
    roundtrip("(a + b) * c", "(a + b) * c")
    roundtrip("a * b + c", "a * b + c")


def test_right_assoc_power():
    # ^ is right-associative: a^b^c == a^(b^c)
    roundtrip("a ^ b ^ c", "a^b^c")
    assert str(parse("a ^ b ^ c")) == str(parse("a ^ (b ^ c)"))


def test_unary_minus():
    roundtrip("-x + 1", "-x + 1")
    roundtrip("-(a + b)", "-(a + b)")


def test_function_call():
    roundtrip("sin(x) + cos(y)", "sin(x) + cos(y)")
    roundtrip("log(x, 2)", "log(x, 2)")


def test_numbers():
    assert parse("3").value == 3
    assert parse("3.5").value == 3.5
