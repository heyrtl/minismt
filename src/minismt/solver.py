#!/usr/bin/env python3
"""
minismt — A minimal SMT solver for QF_UF.

DPLL(T) architecture:
  * CDCL SAT solver (2-watched literals, 1UIP learning, VSIDS, phase saving)
  * Congruence closure theory solver with explanation tracking
  * SMT-LIB 2 subset parser
"""
from collections import defaultdict


# ============================================================================
# CDCL SAT solver
# ============================================================================
class SAT:
    def __init__(self):
        self.n = 0
        self.clauses = []
        self.watches = [[]]
        self.val = [None]
        self.level = [0]
        self.reason = [None]
        self.trail = []
        self.tlim = []
        self.qhead = 0
        self.act = [0.0]
        self.inc = 1.0
        self.decay = 0.95
        self.ok = True
        self.phase = [True]

    def _i(self, lit):
        v = abs(lit)
        return v if lit > 0 else v + self.n

    def new_var(self):
        self.n += 1
        self.val.append(None)
        self.level.append(0)
        self.reason.append(None)
        self.act.append(0.0)
        self.phase.append(True)
        while len(self.watches) < 2 * self.n + 1:
            self.watches.append([])
        return self.n

    def lv(self, lit):
        v = self.val[abs(lit)]
        if v is None:
            return None
        return v if lit > 0 else (not v)

    def enq(self, lit, reason):
        v = abs(lit)
        self.val[v] = (lit > 0)
        self.level[v] = len(self.tlim)
        self.reason[v] = reason
        self.trail.append(lit)

    def add_clause(self, lits):
        if not self.ok:
            return False
        s = set(lits)
        if any(-l in s for l in s):
            return True
        new = []
        for l in s:
            lv = self.lv(l)
            if lv is True:
                return True
            if lv is None:
                new.append(l)
        if not new:
            self.ok = False
            return False
        if len(new) == 1:
            self.enq(new[0], None)
            self.propagate()
            return self.ok
        cidx = len(self.clauses)
        self.clauses.append(new)
        self.watches[self._i(new[0])].append(cidx)
        self.watches[self._i(new[1])].append(cidx)
        return True

    def propagate(self):
        while self.qhead < len(self.trail):
            p = self.trail[self.qhead]
            self.qhead += 1
            fl = -p
            ws = self.watches[self._i(fl)]
            i = j = 0
            while i < len(ws):
                cidx = ws[i]
                c = self.clauses[cidx]
                if c[0] == fl:
                    c[0], c[1] = c[1], c[0]
                if c[1] != fl:
                    i += 1
                    continue
                if self.lv(c[0]) is True:
                    ws[j] = cidx; i += 1; j += 1
                    continue
                found = False
                for k in range(2, len(c)):
                    if self.lv(c[k]) is not False:
                        c[1], c[k] = c[k], c[1]
                        self.watches[self._i(c[1])].append(cidx)
                        found = True
                        break
                if found:
                    i += 1
                    continue
                ws[j] = cidx; i += 1; j += 1
                if self.lv(c[0]) is False:
                    while i < len(ws):
                        ws[j] = ws[i]; i += 1; j += 1
                    del ws[j:]
                    return cidx
                self.enq(c[0], cidx)
            del ws[j:]
        return None

    def bump(self, v):
        self.act[v] += self.inc
        if self.act[v] > 1e100:
            for i in range(1, self.n + 1):
                self.act[i] *= 1e-100
            self.inc *= 1e-100

    def analyze(self, confl):
        learnt = [0]
        seen = [False] * (self.n + 1)
        pathC = 0
        p = None
        idx = len(self.trail) - 1
        c = self.clauses[confl]
        while True:
            for q in c:
                if q == p:
                    continue
                v = abs(q)
                if not seen[v] and self.level[v] > 0:
                    seen[v] = True
                    self.bump(v)
                    if self.level[v] >= len(self.tlim):
                        pathC += 1
                    else:
                        learnt.append(q)
            while not seen[abs(self.trail[idx])]:
                idx -= 1
            p = self.trail[idx]; idx -= 1
            seen[abs(p)] = False
            pathC -= 1
            if pathC <= 0:
                break
            c = self.clauses[self.reason[abs(p)]]
        learnt[0] = -p
        if len(learnt) == 1:
            return learnt, 0
        mi = 1
        for i in range(2, len(learnt)):
            if self.level[abs(learnt[i])] > self.level[abs(learnt[mi])]:
                mi = i
        learnt[1], learnt[mi] = learnt[mi], learnt[1]
        return learnt, self.level[abs(learnt[1])]

    def backtrack(self, level):
        if len(self.tlim) <= level:
            return
        lim = self.tlim[level]
        for i in range(len(self.trail) - 1, lim - 1, -1):
            v = abs(self.trail[i])
            self.phase[v] = self.val[v]
            self.val[v] = None
            self.reason[v] = None
            self.level[v] = 0
        del self.trail[lim:]
        del self.tlim[level:]
        self.qhead = len(self.trail)

    def pick(self):
        best, ba = None, -1.0
        for v in range(1, self.n + 1):
            if self.val[v] is None and self.act[v] > ba:
                ba = self.act[v]; best = v
        return best


# ============================================================================
# Congruence closure (EUF theory solver, with explanation tracking)
# ============================================================================
class CC:
    def __init__(self):
        self.parent = {}
        self.rank = {}
        self.reason = {}
        self.func = {}
        self.use = {}
        self.terms = set()

    def add_term(self, t):
        if t in self.terms:
            return
        self.terms.add(t)
        self.parent[t] = t
        self.rank[t] = 0
        self.reason[t] = frozenset()
        self.use.setdefault(t, [])
        if isinstance(t, tuple):
            self.func[t] = (t[0], t[1:])
            for arg in t[1:]:
                self.add_term(arg)
                self.use[arg].append(t)
        else:
            self.func[t] = None

    def find(self, t):
        path = []
        while self.parent[t] != t:
            path.append(t); t = self.parent[t]
        for p in path:
            self.parent[p] = t
        return t

    def union_raw(self, ra, rb, r):
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        self.reason[ra] = self.reason[ra] | self.reason[rb] | r

    def process(self):
        changed = True
        while changed:
            changed = False
            classes = defaultdict(list)
            for t in self.terms:
                classes[self.find(t)].append(t)
            for root, members in classes.items():
                r = self.reason[self.find(root)]
                for i in range(len(members)):
                    for j in range(i + 1, len(members)):
                        for p1 in self.use.get(members[i], []):
                            for p2 in self.use.get(members[j], []):
                                f1 = self.func.get(p1)
                                f2 = self.func.get(p2)
                                if not f1 or not f2 or f1[0] != f2[0]:
                                    continue
                                r1, r2 = self.find(p1), self.find(p2)
                                if r1 != r2:
                                    self.union_raw(r1, r2, r)
                                    changed = True
                                    break
                            if changed: break
                        if changed: break
                    if changed: break


# ============================================================================
# SMT layer (DPLL(T))
# ============================================================================
class SMT:
    def __init__(self):
        self.sat = SAT()
        self.atoms = {}
        self.v2a = {}
        self.top = []

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
            terms = f[1:]; neqs = []
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
        for (a, b, v) in neqs:
            if cc.find(a) == cc.find(b):
                return [-r for r in cc.reason[cc.find(a)]] + [v]
        return None

    def solve(self):
        sat = self.sat
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
                    if v is None: return True
                    sat.tlim.append(len(sat.trail))
                    sat.enq(v if sat.phase[v] else -v, None)
                    continue
                if len(tconfl) == 0:
                    return False
                # A theory conflict entirely at decision level 0 means UNSAT:
                # CDCL analyze() expects at least one literal at the current
                # decision level, and level-0 vars are excluded from "seen".
                if max(sat.level[abs(l)] for l in tconfl) == 0:
                    return False
                # Treat theory lemma as a conflict clause and run analyze
                # TODO(v0.2): if max_lvl < len(sat.tlim), backjump to max_lvl
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


# ============================================================================
# SMT-LIB parser + driver
# ============================================================================
def tokenize(s):
    return s.replace('(', ' ( ').replace(')', ' ) ').split()

def parse_expr(toks, i):
    if toks[i] == '(':
        i += 1; r = []
        while toks[i] != ')':
            sub, i = parse_expr(toks, i); r.append(sub)
        return tuple(r), i + 1
    return toks[i], i + 1

def run(text):
    toks = tokenize(text)
    i = 0
    smt = SMT()
    out = []
    while i < len(toks):
        cmd, i = parse_expr(toks, i)
        op = cmd[0]
        if op in ('set-logic', 'set-info', 'declare-sort', 'declare-fun', 'declare-const'):
            continue
        if op == 'assert':
            smt.assert_f(cmd[1])
        elif op == 'check-sat':
            out.append('sat' if smt.solve() else 'unsat')
            break
        elif op == 'exit':
            break
    return '\n'.join(out)