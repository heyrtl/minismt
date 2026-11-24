"""SMT-LIB 2 parser and CLI driver."""
from .dpllt import SMT


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
    declared = set()
    out = []
    while i < len(toks):
        cmd, i = parse_expr(toks, i)
        op = cmd[0]
        if op in ('set-logic', 'set-info', 'declare-sort'):
            continue
        if op == 'declare-const':
            declared.add(cmd[1])
            continue
        if op == 'declare-fun':
            if len(cmd[2]) == 0:
                declared.add(cmd[1])
            continue
        if op == 'assert':
            smt.assert_f(cmd[1])
        elif op == 'check-sat':
            out.append('sat' if smt.solve() else 'unsat')
        elif op == 'get-model':
            m = smt.model(declared)
            if m is None:
                out.append('(error "no model available")')
            else:
                lines = ['(']
                for v in sorted(m.keys(), key=str):
                    lines.append(f'  (define-fun {v} () U {m[v]})')
                lines.append(')')
                out.append('\n'.join(lines))
        elif op == 'exit':
            break
    return '\n'.join(out)