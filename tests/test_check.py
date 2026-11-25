from minismt import check, UnsoundSatError
import pytest


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


def test_validation_passes_on_sat():
    # If validation ever raises, the test fails — that's the point
    r = check("(= x y)", declarations=("x", "y"))
    assert r.sat is True


def test_validation_distinct():
    r = check("(distinct x y)", declarations=("x", "y"))
    assert r.sat is True


def test_validation_compound():
    r = check(
        "(and (= a b) (= b c))",
        "(not (= a d))",
        declarations=("a", "b", "c", "d"),
    )
    assert r.sat is True


def test_validation_congruence():
    r = check(
        "(= x y)",
        "(= (f x) (f y))",
        declarations=("x", "y"),
    )
    assert r.sat is True
    