"""
teach_datasets  —  command-line form of Vio's `learn everything`.

Kept so scripts and the Docker deployment (`python teach_datasets.py`) keep working,
but it no longer has its own loading logic: it runs the same self-learning pass as
typing  learn everything  in the chat — built-in knowledge, the bundled datasets,
trusted sources and GitHub skill collections (web + licence-gated, only with
VIO_ALLOW_NET=1), knowledge gaps, consolidation, and the behaviour/golden gate.

Safe to re-run: passages already in the library are skipped.

    python teach_datasets.py
"""
import sys

from reasoner import Mind


def main():
    r = Mind().learn_everything()
    print(r["answer"])
    return 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.exit(main())
