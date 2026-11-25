"""Congruence closure theory solver with explanation tracking."""
from collections import defaultdict


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
        """Propagate congruence: if f(a1,...,an) and f(b1,...,bn) are terms
        and ai ≡ bi for all i, then the two terms are equal."""
        changed = True
        while changed:
            changed = False
            # Index every function application by (name, tuple of arg roots).
            # Two terms with the same signature MUST be in the same class.
            sig_index = defaultdict(list)
            for t in self.terms:
                info = self.func.get(t)
                if info is None:
                    continue
                fname, args = info
                sig = (fname, tuple(self.find(a) for a in args))
                sig_index[sig].append(t)
            # Merge everything that shares a signature.
            for sig, terms in sig_index.items():
                if len(terms) < 2:
                    continue
                # Reason = equalities of the arguments + reasons of the terms
                # themselves. Conservative (may include extra literals), sound.
                r = frozenset()
                for arg_root in sig[1]:
                    r = r | self.reason[arg_root]
                for t in terms:
                    r = r | self.reason[self.find(t)]
                for t in terms[1:]:
                    r0 = self.find(terms[0])
                    rt = self.find(t)
                    if rt != r0:
                        self.union_raw(r0, rt, r)
                        changed = True