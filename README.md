# minismt

> DPLL(T) SMT solver for QF_UF in Python: CDCL, congruence closure, SMT-LIB. Educational, zero deps.

`minismt` is an educational SMT solver. It implements the **DPLL(T)** architecture from scratch:

- a **CDCL SAT solver** with two-watched literals, 1UIP clause learning, VSIDS, phase saving, and non-chronological backjumping;
- a **congruence closure** theory solver with explanation tracking;
- a **DPLL(T)** driver that feeds theory conflicts back into the SAT engine as learned clauses;
- a small **SMT-LIB v2** parser for the QF_UF subset.

Zero runtime dependencies. Pure Python 3.8+.

## What it is

- A readable reference implementation of DPLL(T) + congruence closure, split across `sat.py`, `cc.py`, `dpllt.py`, `parser.py`.
- A working QF_UF solver that handles transitivity, symmetry, congruence, negation, and propositional combinations (`and`, `or`, `=>`, `not`, `distinct`).
- A starting point for adding more theories (LRA, bit-vectors, arrays).

## What it is **not**

- **Not** a drop-in replacement for Z3 or cvc5. Not even close on performance.
- **Not** production software. No proofs, no unsat cores, no incremental solving.
- **Not** covering the full SMT-LIB standard. See [Limitations](#limitations).

## Install

```bash
pip install minismt
```

From source:

```bash
git clone https://github.com/heyrtl/minismt.git
cd minismt
python -m pip install -e ".[dev]"
```

## Usage

### CLI

```bash
$ minismt tests/examples/congruence.smt2
unsat
```

### As a library

```python
from minismt import run

result = run("""
(set-logic QF_UF)
(declare-fun x () U)
(declare-fun y () U)
(declare-fun f (U) U)
(assert (= x y))
(assert (not (= (f x) (f y))))
(check-sat)
""")
print(result)   # "unsat"
```

### Getting a model

```python
result = run("""
(set-logic QF_UF)
(declare-fun x () U)(declare-fun y () U)(declare-fun z () U)
(assert (= x y))(assert (not (= x z)))
(check-sat)(get-model)
""")
print(result)
# sat
# (
#   (define-fun x () U x)
#   (define-fun y () U x)
#   (define-fun z () U z)
# )
```

`get-model` prints one `define-fun` per variable, mapping each to its equivalence-class representative.

### Tests

```bash
pytest
```

## Supported SMT-LIB subset

| Construct | Status |
|---|---|
| `set-logic`, `set-info`, `declare-sort` | parsed, ignored (no sort checking) |
| `declare-fun`, `declare-const` | parsed, tracked for `get-model` |
| `assert` | supported |
| `check-sat` | supported |
| `get-model` | supported |
| `exit` | supported |
| `=`, `not`, `and`, `or`, `=>`, `distinct` | supported |
| Function application `(f x y)` | supported |
| `let`, `ite`, `forall`, `exists` | **not** supported |
| `push`, `pop`, `get-unsat-core` | **not** supported |

## How it works

The pipeline is the classic DPLL(T) loop:

```
SMT-LIB  ──parser──▶  AST  ──Tseitin──▶  CNF  ──CDCL──▶  Boolean model
                                                             │
                                                             ▼
                                                    ┌────────────────┐
                                                    │ Congruence     │
                                                    │ closure (EUF)  │
                                                    └────────────────┘
                                                             │
                                              conflict ◀─────┴─────▶ ok
                                                 │                   │
                                        learn + backjump       next decision
```

1. **Encode.** Each theory atom `(= a b)` becomes a SAT variable. Boolean connectives are encoded into CNF with Tseitin-style clauses.
2. **Solve.** The CDCL solver runs as normal.
3. **Check.** After propagation settles, the congruence-closure solver processes all currently-true equalities (union) and all currently-false equalities (disequalities). It also propagates congruence: if `a ≡ b` then `f(a) ≡ f(b)` for every `f`.
4. **Explain.** Every merge in the union-find carries the set of SAT literals that caused it. If a disequality is violated, that reason set plus the disequality itself forms a conflict clause.
5. **Learn.** The conflict clause is fed to `SAT.analyze()` exactly like a SAT conflict. New clause learned, backjump, continue.

For the full breakdown, read the docstrings in `src/minismt/` — `sat.py` (CDCL), `cc.py` (congruence closure), `dpllt.py` (driver), `parser.py` (SMT-LIB).

## Limitations

- **QF_UF only.** No arithmetic, arrays, or bit-vectors.
- **No incremental solving.** `(check-sat)(get-model)` is supported, but calling `(check-sat)` twice in one file re-runs the search and is not guaranteed correct after new assertions.
- **`theory_check()` is non-incremental.** It rebuilds the congruence-closure state on every call — correct but O(n²) per check.
- **`CC.process()` is O(n³) worst case** on terms with large equivalence classes.
- **No proofs or unsat cores.**
- **Parser is minimal.** No `let`, no `ite`, no nested `distinct`, no SMT-LIB round-tripping.

## Roadmap

- [x] **v0.2** — module split + `(get-model)` printing equivalence classes
- [ ] **v0.3** — incremental congruence closure (push/pop on the trail) + multiple `(check-sat)`
- [ ] **v0.4** — `let`, `ite` in the parser
- [ ] **v0.5** — `(get-unsat-core)`
- [ ] **v0.6** — Linear Real Arithmetic via Simplex-for-DPLL(T)
- [ ] **v0.7** — Bit-vectors via bit-blasting
- [ ] **v1.0** — pass a meaningful subset of the SMT-LIB QF_UF benchmark suite

## References

- Kroening & Strichman, *Decision Procedures: An Algorithmic Point of View* — the standard textbook.
- Nieuwenhuis, Oliveras, Tinelli, *Solving SAT and SAT Modulo Theories* (2006) — the DPLL(T) paper.
- Nelson & Oppen, *Fast Decision Procedures Based on Congruence Closure* (1980).
- The "SAT / SMT 學習筆記" tutorial series — the best code-level walkthrough.

## License

MIT. See [LICENSE](LICENSE).