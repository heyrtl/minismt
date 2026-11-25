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
    
    
def test_regression_distinct_duplicate():
    # Found by differential fuzzing, seed preserved in git log.
    # (distinct a a) is semantically unsat; must not return sat.
    r = check("(distinct a a)", declarations=("a",))
    assert r.sat is False


def test_regression_distinct_duplicate_compound():
    # Same bug, nested in a conjunction
    r = check(
        "(distinct a a)",
        "(and (= a a) (= a a))",
        declarations=("a", "b", "c", "d"),
    )
    assert r.sat is False


def test_distinct_duplicate_under_not():
    # (not (distinct a a)) IS satisfiable
    r = check("(not (distinct a a))", declarations=("a",))
    assert r.sat is True


def test_distinct_three_terms_duplicate():
    r = check("(distinct a a b)", declarations=("a", "b"))
    assert r.sat is False
    
def test_regression_distinct_three_distinct():
    # (distinct a b c) ∧ (a = a) is SAT; a, b, c must be pairwise distinct
    r = check("(distinct a b c)", "(= a a)", declarations=("a", "b", "c"))
    assert r.sat is True
    assert r.model["a"] != r.model["b"]
    assert r.model["a"] != r.model["c"]
    assert r.model["b"] != r.model["c"]


def test_regression_distinct_three_with_equality():
    # (distinct a b c) ∧ (a = b) is UNSAT
    r = check("(distinct a b c)", "(= a b)", declarations=("a", "b", "c"))
    assert r.sat is False
    
def test_regression_congruence_second_arg():
    r = check(
        "(= a b)",
        "(distinct (h a a) (h b (f a)))",
        declarations=("a", "b"),
    )
    assert r.sat is True


def test_regression_congruence_all_args_equal():
    r = check(
        "(= a b)",
        "(= a c)",
        "(distinct (h a b) (h b c))",
        declarations=("a", "b", "c"),
    )
    assert r.sat is False


def test_regression_congruence_three_args():
    r = check(
        "(= a b)",
        "(distinct (h a a a) (h b b b))",
        declarations=("a", "b"),
    )
    assert r.sat is False


def test_regression_congruence_three_args_partial():
    r = check(
        "(= a b)",
        "(distinct (h a a a) (h b b (f a)))",
        declarations=("a", "b"),
    )
    assert r.sat is True