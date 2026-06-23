#!/usr/bin/env python3
"""Self-test: the standalone slop demo separates cleanly (0 real-as-slop, 0 slipped through)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from slop_discrimination import run, assess, CASES, CORROBORATED

def test_clean_separation():
    assert run() == 0
    print("ok clean separation (exit 0)")

def test_no_real_is_slop():
    for cid, claim, ev, expected_slop, _ in CASES:
        label, got = assess(claim, ev)
        if not expected_slop:
            assert got is False, "%s (real) was flagged slop" % cid
    print("ok no real witness is ever flagged as slop")

def test_no_slop_corroborates():
    for cid, claim, ev, expected_slop, _ in CASES:
        label, _ = assess(claim, ev)
        if expected_slop:
            assert label != CORROBORATED, "%s (slop) corroborated" % cid
    print("ok no slop submission is ever CORROBORATED")

if __name__ == "__main__":
    import traceback
    failed = 0
    for n, f in sorted(dict(globals()).items()):
        if n.startswith("test_") and callable(f):
            try: f()
            except Exception:
                failed += 1; print("FAILED", n); traceback.print_exc()
    print(("all demo self-tests passed" if not failed else "%d FAILED" % failed))
    sys.exit(1 if failed else 0)
