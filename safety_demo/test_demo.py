#!/usr/bin/env python3
"""Self-test: the false-negative safety demo proves zero real exploits are suppressed."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from false_negative_safety import main, disposition, REAL_INCIDENTS, CERTIFIED, ESCALATES


def test_passes():
    assert main() == 0
    print("ok safety demo passes (exit 0)")


def test_zero_suppression():
    # the cardinal property: no real exploit gets an unsafe (suppress) disposition.
    for inc_id, _loss, verdict, _forge in REAL_INCIDENTS:
        _action, safe = disposition(verdict, ground_truth_is_exploit=True)
        assert safe, "%s (a real exploit) received an UNSAFE disposition" % inc_id
    print("ok no real exploit is ever suppressed")


def test_only_certified_acts_without_review():
    # only a conservation-checked witness clears the bar to act without a human; everything else escalates.
    for inc_id, _loss, verdict, _forge in REAL_INCIDENTS:
        if verdict != CERTIFIED:
            assert verdict in ESCALATES or verdict == "BOUNDED-NEGATIVE", \
                "%s has an unexpected verdict %s" % (inc_id, verdict)
    print("ok only CERTIFIED clears the bar to act without review")


if __name__ == "__main__":
    import traceback
    failed = 0
    for n, f in sorted(dict(globals()).items()):
        if n.startswith("test_") and callable(f):
            try:
                f()
            except Exception:
                failed += 1
                print("FAILED", n)
                traceback.print_exc()
    print(("all safety self-tests passed" if not failed else "%d FAILED" % failed))
    sys.exit(1 if failed else 0)
