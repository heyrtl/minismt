"""Differential testing: minismt vs Z3 on randomly generated QF_UF programs."""
import pytest
from hypothesis import given, settings, strategies as st, HealthCheck, example

from minismt import check, UnsoundSatError

z3 = pytest.importorskip("z3")


# --- Generator --------------------------------------------------------------

CONSTANTS = ('a', 'b', 'c', 'd')

_constant = st.sampled_from(CONSTANTS)


def _terms():
    return st.recursive(
        _constant,
        lambda children: st.one_of(
            st.builds(lambda c: ('f', c), children),
            st.builds(lambda c: ('g', c), children),
            st.builds(lambda c1, c2: ('h', c1, c2), children, children),
        ),
        max_leaves=4,
    )


def _formulas():
    return st.recursive(
        st.builds(lambda a, b: ('=', a, b), _terms(), _terms()),
        lambda children: st.one_of(
            st.builds(lambda a, b: ('=', a, b), _terms(), _terms()),
            st.builds(lambda c: ('not', c), children),
            st.builds(lambda a, b: ('and', a, b), children, children),
            st.builds(lambda a, b: ('or', a, b), children, children),
            st.builds(lambda a, b: ('=>', a, b), children, children),
            st.lists(_terms(), min_size=2, max_size=4)
              .map(lambda ts: ('distinct', *ts)),
        ),
        max_leaves=4,
    )


@st.composite
def qf_uf_programs(draw, min_size=1, max_size=4):
    n = draw(st.integers(min_size, max_size))
    return [draw(_formulas()) for _ in range(n)]


# --- Serialization ----------------------------------------------------------

def to_smtlib(ast):
    if isinstance(ast, str):
        return ast
    return '(' + ' '.join(to_smtlib(c) for c in ast) + ')'


# --- Z3 translation ---------------------------------------------------------

_SORT = z3.DeclareSort('U')
_CONSTS = {name: z3.Const(name, _SORT) for name in CONSTANTS}
_FUNCS = {
    'f': z3.Function('f', _SORT, _SORT),
    'g': z3.Function('g', _SORT, _SORT),
    'h': z3.Function('h', _SORT, _SORT, _SORT),
}


def ast_to_z3(ast):
    if isinstance(ast, str):
        return _CONSTS[ast]
    op = ast[0]
    if op == '=':
        return ast_to_z3(ast[1]) == ast_to_z3(ast[2])
    if op == 'not':
        return z3.Not(ast_to_z3(ast[1]))
    if op == 'and':
        return z3.And(*[ast_to_z3(c) for c in ast[1:]])
    if op == 'or':
        return z3.Or(*[ast_to_z3(c) for c in ast[1:]])
    if op == '=>':
        return z3.Implies(ast_to_z3(ast[1]), ast_to_z3(ast[2]))
    if op == 'distinct':
        return z3.Distinct(*[ast_to_z3(c) for c in ast[1:]])
    if op in _FUNCS:
        return _FUNCS[op](*[ast_to_z3(c) for c in ast[1:]])
    raise ValueError(f"unknown operator in AST: {op!r}")


def z3_sat(assertions):
    s = z3.Solver()
    for a in assertions:
        s.add(ast_to_z3(a))
    return s.check() == z3.sat


# --- Test -------------------------------------------------------------------

@example(assertions=[('distinct', 'a', 'a'), ('and', ('=', 'a', 'a'), ('=', 'a', 'a'))])
@example(assertions=[('distinct', 'a', 'b', 'c'), ('=', 'a', 'a')])
@example(assertions=[('=', 'a', 'b'), ('distinct', ('h', 'a', 'a'), ('h', 'b', ('f', 'a')))])
@given(qf_uf_programs())
def test_agrees_with_z3(assertions):
    src_lines = [to_smtlib(a) for a in assertions]
    src = '\n'.join(src_lines)

    try:
        result = check(*src_lines, declarations=CONSTANTS)
    except UnsoundSatError as e:
        pytest.fail(f"Unsound sat:\n{e}\n\nprogram:\n{src}")

    expected = z3_sat(assertions)
    assert result.sat == expected, (
        f"disagreement: minismt={result.sat}, z3={expected}\n\nprogram:\n{src}"
    )