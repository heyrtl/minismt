"""minismt — a minimal SMT solver for QF_UF.

CDCL SAT core + congruence closure, wired together in a DPLL(T) loop.
"""
from .solver import run, SMT, SAT, CC

__version__ = "0.1.0"
__all__ = ["run", "SMT", "SAT", "CC", "__version__"]