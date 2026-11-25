"""CDCL SAT solver — two-watched literals, 1UIP learning, VSIDS, phase saving."""


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
        # Positive lit → 2*abs(lit), negative lit → 2*abs(lit)+1.
        # Independent of self.n, so watches added before new variables
        # are created stay valid.
        return 2 * abs(lit) + (0 if lit > 0 else 1)
    
    def new_var(self):
        self.n += 1
        self.val.append(None)
        self.level.append(0)
        self.reason.append(None)
        self.act.append(0.0)
        self.phase.append(True)
        while len(self.watches) < 2 * self.n + 2:
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
            if self.propagate() is not None:
                self.ok = False
                return False
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