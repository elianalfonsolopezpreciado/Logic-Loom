from logic_loom import parse, to_code, to_llvm


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


def test_llvm_signature_and_ops():
    ir = to_llvm(parse("a*x + b"), "f")
    assert "define double @f(double %a, double %b, double %x)" in ir
    assert "fmul double %a, %x" in ir
    assert "fadd double" in ir
    assert ir.strip().endswith("}")


def test_llvm_declares_intrinsics():
    ir = to_llvm(parse("sqrt(x) + exp(y)"))
    assert "declare double @llvm.sqrt.f64(double)" in ir
    assert "declare double @llvm.exp.f64(double)" in ir
    assert "call double @llvm.sqrt.f64(double %x)" in ir

