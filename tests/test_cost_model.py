import json

from logic_loom import CostModel, PROFILES, optimize, parse
from logic_loom.cost import expr_cost


def test_profiles_exist():
    for name in ("default", "x86", "arm", "gpu"):
        assert name in PROFILES


def test_profile_changes_cost_magnitude():
    e = parse("a / b")
    # division is much more expensive on the GPU profile than the default
    assert expr_cost(e, PROFILES["gpu"]) > expr_cost(e, PROFILES["default"])


def test_cost_model_changes_extracted_form():
    # When powers are cheap, x*x*x should extract as x^3; by default it stays
    # as multiplications.
    cheap_pow = CostModel("cheap-pow", {"+": 1, "-": 1, "*": 2, "/": 4, "^": 1})
    assert str(optimize("x*x*x", model=cheap_pow).optimized) == "x^3"
    assert str(optimize("x*x*x").optimized) != "x^3"


def test_profile_by_name():
    r = optimize("a*b + a*c", profile="gpu")
    assert r.model.name == "gpu"
    assert r.improved


def test_from_json(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({
        "name": "tiny", "leaf_cost": 0.0, "func_cost": 9,
        "op_cost": {"+": 1, "*": 2, "/": 3, "^": 4},
    }))
    m = CostModel.from_json(str(path))
    assert m.name == "tiny"
    assert m.op_cost["/"] == 3.0
