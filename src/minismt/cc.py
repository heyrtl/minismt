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