from minismt import check


def test_unsat_reflexive():
    r = check("(= x y)", "(not (= y x))", declarations=("x", "y"))
    assert r.sat is False
    assert r.model is None


def test_sat_with_model():
    r = check("(= x y)", declarations=("x", "y"))
    assert r.sat is True
    assert r.model is not None
    assert r.model["x"] == r.model["y"]


def test_unsat_congruence():
    r = check("(= x y)", "(not (= (f x) (f y)))", declarations=("x", "y"))
    assert r.sat is False