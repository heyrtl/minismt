"""DPLL(T) driver — Tseitin encoding + SAT + congruence closure."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from .sat import SAT
from .cc import CC


class SMT:
    def __init__(self):
        self.sat = SAT()
        self.atoms = {}
        self.v2a = {}
        self.top = []
        self.assertion_asts = []        # ← new
        self._last_cc = None
        self._solved = False
        self._declared = set()

    def atom_eq(self, a, b):
        if repr(a) > repr(b):
            a, b = b, a
        key = ('=', a, b)
        if key not in self.atoms:
            v = self.sat.new_var()
            self.atoms[key] = v
            self.v2a[v] = key
        return self.atoms[key]

    def enc(self, f):
        op = f[0]
        if op == '=':
            return self.atom_eq(f[1], f[2])
        if op == 'not':
            inner = f[1]
            if isinstance(inner, tuple) and inner[0] == '=':
                return -self.atom_eq(inner[1], inner[2])
            if isinstance(inner, tuple) and inner[0] == 'not':
                return self.enc(inner[1])
            v = self.sat.new_var()
            l = self.enc(inner)
            self.sat.add_clause([-v, -l]); self.sat.add_clause([v, l])
            return v
        if op == 'and':
            v = self.sat.new_var()
            ls = [self.enc(c) for c in f[1:]]
            for l in ls: self.sat.add_clause([-v, l])
            self.sat.add_clause([v] + [-l for l in ls])
            return v
        if op == 'or':
            v = self.sat.new_var()
            ls = [self.enc(c) for c in f[1:]]
            self.sat.add_clause([-v] + ls)
            for l in ls: self.sat.add_clause([-l, v])
            return v
        if op == '=>':
            a = self.enc(f[1]); b = self.enc(f[2])
            v = self.sat.new_var()
            self.sat.add_clause([-v, -a, b])
            self.sat.add_clause([a, v])
            self.sat.add_clause([-b, v])
            return v
        if op == 'distinct':
            terms = f[1:]
            # Fast path: any duplicate term makes the whole formula trivially false
            if len(set(map(repr, terms))) != len(terms):
                v = self.sat.new_var()
                self.sat.add_clause([-v])   # forces v = False at enc time
                return v
            neqs = []
            for i in range(len(terms)):
                for j in range(i + 1, len(terms)):
                    neqs.append(-self.atom_eq(terms[i], terms[j]))
            v = self.sat.new_var()
            for l in neqs: self.sat.add_clause([-v, l])
            self.sat.add_clause([v] + [-l for l in neqs])
            return v
        raise ValueError(f"unknown operator: {op}")

    def assert_f(self, f):
        self.top.append(self.enc(f))
        self.assertion_asts.append(f)   # ← new

    def theory_check(self):
        cc = CC()
        neqs = []
        for v in range(1, self.sat.n + 1):
            if self.sat.val[v] is None: continue
            atom = self.v2a.get(v)
            if not atom or atom[0] != '=': continue
            a, b = atom[1], atom[2]
            cc.add_term(a); cc.add_term(b)
            if self.sat.val[v] is False:
                neqs.append((a, b, v))
        for v in range(1, self.sat.n + 1):
            if self.sat.val[v] is not True: continue
            atom = self.v2a.get(v)
            if not atom or atom[0] != '=': continue
            cc.union_raw(cc.find(atom[1]), cc.find(atom[2]), frozenset([v]))
        cc.process()
        self._last_cc = cc
        for (a, b, v) in neqs:
            if cc.find(a) == cc.find(b):
                return [-r for r in cc.reason[cc.find(a)]] + [v]
        return None

    def solve(self):
        sat = self.sat
        self._solved = False
        for lit in self.top:
            sat.add_clause([lit])
        if not sat.ok: return False
        while True:
            confl = sat.propagate()
            if confl is not None:
                if not sat.tlim: return False
                learnt, bt = sat.analyze(confl)
            else:
                tconfl = self.theory_check()
                if tconfl is None:
                    v = sat.pick()
                    if v is None:
                        self._solved = True
                        return True
                    sat.tlim.append(len(sat.trail))
                    sat.enq(v if sat.phase[v] else -v, None)
                    continue
                if len(tconfl) == 0:
                    return False
                if max(sat.level[abs(l)] for l in tconfl) == 0:
                    return False
                # TODO(v0.3): if max_lvl < len(sat.tlim), backjump to max_lvl
                # before analyzing, to handle conflicts below the current level.
                cidx = len(sat.clauses)
                sat.clauses.append(list(tconfl))
                learnt, bt = sat.analyze(cidx)
            sat.backtrack(bt)
            if len(learnt) == 1:
                sat.enq(learnt[0], None)
            else:
                cidx = len(sat.clauses)
                sat.clauses.append(learnt)
                sat.watches[sat._i(learnt[0])].append(cidx)
                sat.watches[sat._i(learnt[1])].append(cidx)
                sat.enq(learnt[0], cidx)
            sat.inc /= sat.decay

    def model(self, declared=()):
        """Return {var: representative}. Valid only after solve() returned True."""
        if not self._solved or self._last_cc is None:
            return None
        cc = self._last_cc
        all_vars = set(declared)
        for t in cc.terms:
            if not isinstance(t, tuple):
                all_vars.add(t)
        classes = defaultdict(list)
        for v in all_vars:
            root = cc.find(v) if v in cc.terms else v
            classes[root].append(v)
        result = {}
        for members in classes.values():
            rep = min(members, key=str)
            for v in members:
                result[v] = rep
        return result

    def declare_const(self, name: str) -> None:
        """Register a constant symbol (for get-model / model())."""
        self._declared.add(name)


@dataclass
class Result:
    """Result of a satisfiability check."""
    sat: bool
    model: dict[str, Any] | None = None
    reason: str | None = None      # "unsat" | "level-0" | "theory" — for debugging


def check(*assertions: str, declarations: tuple[str, ...] = ()) -> Result:
    """Check satisfiability of SMT-LIB assertion strings.

    >>> check("(= x y)", "(not (= y x))", declarations=("x", "y")).sat
    False
    >>> check("(= x y)", declarations=("x", "y")).sat
    True
    """
    from .parser import tokenize, parse_expr

    smt = SMT()
    for d in declarations:
        smt.declare_const(d)
    for a in assertions:
        toks = tokenize(a)
        expr, idx = parse_expr(toks, 0)
        if idx != len(toks):
            raise ValueError(f"trailing tokens in assertion: {a!r}")
        smt.assert_f(expr)

    sat = smt.solve()
    if not sat:
        return Result(sat=False)

    failures = validate_model(smt)
    if failures:
        raise UnsoundSatError(
            f"sat returned but {len(failures)} assertion(s) fail under model: {failures}"
        )
    return Result(sat=True, model=smt.model(declarations))
class UnsoundSatError(Exception):
    """Raised when the solver returns sat but the model does not satisfy the assertions."""


def _eval(cc, term):
    """Representative of `term` under the current congruence closure."""
    if term in cc.terms:
        return cc.find(term)
    return term


def _eval_bool(cc, expr):
    op = expr[0]
    if op == '=':
        return _eval(cc, expr[1]) == _eval(cc, expr[2])
    if op == 'not':
        return not _eval_bool(cc, expr[1])
    if op == 'and':
        return all(_eval_bool(cc, e) for e in expr[1:])
    if op == 'or':
        return any(_eval_bool(cc, e) for e in expr[1:])
    if op == '=>':
        return (not _eval_bool(cc, expr[1])) or _eval_bool(cc, expr[2])
    if op == 'distinct':
        reps = [_eval(cc, t) for t in expr[1:]]
        return len(set(reps)) == len(reps)
    raise ValueError(f"unknown operator: {op}")


def validate_model(smt: SMT) -> list[str]:
    """Return a list of assertion strings that fail under the current model.

    Empty list means every assertion holds — the sat answer is sound.
    Non-empty means the solver returned an unsound sat.
    """
    if not smt._solved or smt._last_cc is None:
        return ["no solved model to validate"]
    cc = smt._last_cc
    return [repr(ast) for ast in smt.assertion_asts if not _eval_bool(cc, ast)]