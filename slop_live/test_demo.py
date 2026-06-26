#!/usr/bin/env python3
"""Self-test: the live-fire slop trial transcript holds the cardinal properties (no false certs, all typed
negatives) and the positive control certifies. Network-free; runs over the recorded transcript."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_slop_live import run, load_transcript, CLEAN_NEGATIVE, WITNESS_STATUSES
import json

HERE = os.path.dirname(os.path.abspath(__file__))


def test_demo_passes():
    assert run() == 0
    print("ok demo passes (exit 0)")


def test_zero_false_certifications():
    t = load_transcript()
    for tr in t["trials"]:
        assert tr["engine_verdict"]["outcome_status"] not in WITNESS_STATUSES, \
            "%s was certified -- a false certification of AI slop" % tr["id"]
    print("ok zero AI reports were certified")


def test_all_typed_negatives():
    t = load_transcript()
    assert len(t["trials"]) > 0
    for tr in t["trials"]:
        assert tr["engine_verdict"]["outcome_status"] == CLEAN_NEGATIVE, \
            "%s was not a clean typed negative" % tr["id"]
        assert str(tr["engine_verdict"]["attacker_profit"]) == "0", "%s shows nonzero profit" % tr["id"]
    print("ok every trial is a clean typed negative with zero attacker profit")


def test_positive_control_certifies():
    pc = json.load(open(os.path.join(HERE, "POSITIVE_CONTROL.json")))
    assert pc["engine_verdict"]["outcome_status"] in WITNESS_STATUSES, \
        "positive control did not certify -- cannot show discrimination"
    print("ok the positive control certifies (the same harness is not a stuck 'no')")


if __name__ == "__main__":
    import traceback
    failed = 0
    for n, f in sorted(dict(globals()).items()):
        if n.startswith("test_") and callable(f):
            try:
                f()
            except Exception:
                failed += 1
                traceback.print_exc()
    print("all slop_live tests passed" if not failed else "%d test(s) failed" % failed)
    sys.exit(1 if failed else 0)
