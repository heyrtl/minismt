"""CLI entry point: `minismt <file.smt2>` or `python -m minismt <file.smt2>`."""
import sys
from .parser import run


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: minismt <file.smt2>")
        return 0 if argv else 2
    with open(argv[0]) as f:
        print(run(f.read()))
    return 0


if __name__ == "__main__":
    sys.exit(main())