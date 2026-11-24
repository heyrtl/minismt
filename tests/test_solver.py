import pytest
from pathlib import Path
from minismt import run

CASES = [
    ("reflexive-equality",
     "(set-logic QF_UF)(declare-fun x () U)(declare-fun y () U)"
     "(assert (= x y))(assert (not (= y x)))(check-sat)",
     "unsat"),
    ("transitivity",
     "(set-logic QF_UF)(declare-fun x () U)(declare-fun y () U)(declare-fun z () U)"
     "(assert (= x y))(assert (= y z))(assert (not (= x z)))(check-sat)",
     "unsat"),
    ("congruence",
     "(set-logic QF_UF)(declare-fun x () U)(declare-fun y () U)(declare-fun f (U) U)"
     "(assert (= x y))(assert (not (= (f x) (f y))))(check-sat)",
     "unsat"),
    ("satisfiable",
     "(set-logic QF_UF)(declare-fun x () U)(declare-fun y () U)(declare-fun z () U)"
     "(assert (= x y))(assert (not (= x z)))(check-sat)",
     "sat"),
    ("deeper-congruence",
     "(set-logic QF_UF)(declare-fun a () U)(declare-fun b () U)(declare-fun c () U)"
     "(declare-fun f (U) U)(declare-fun g (U) U)"
     "(assert (= a b))(assert (= (f a) c))(assert (not (= (f b) c)))(check-sat)",
     "unsat"),
    ("disjunction",
     "(set-logic QF_UF)(declare-fun x () U)(declare-fun y () U)(declare-fun z () U)"
     "(assert (or (= x y) (= y z)))(assert (not (= x y)))(assert (not (= y z)))"
     "(check-sat)",
     "unsat"),
]

@pytest.mark.parametrize("name,src,expected", CASES, ids=[c[0] for c in CASES])
def test_solver(name, src, expected):
    assert run(src) == expected


EXAMPLES = Path(__file__).parent / "examples"

@pytest.mark.parametrize(
    "path", sorted(EXAMPLES.glob("*.smt2")), ids=lambda p: p.stem
)
def test_example_files(path):
    assert run(path.read_text()) in ("sat", "unsat")