#!/usr/bin/env python3
"""Self-test: the intake demo fails closed -- nothing is dropped, nothing becomes a negative by parse failure."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from intake_failclosed import main, classify, CASES, ROUTE_TXHASH, ROUTE_FORGE_FORK, ROUTE_FIXTURE, ROUTE_TO_HUMAN

_RUNNABLE = {ROUTE_TXHASH, ROUTE_FORGE_FORK, ROUTE_FIXTURE}


def test_passes():
    assert main() == 0
    print("ok intake demo passes (exit 0)")


def test_every_route_is_runnable_or_human():
    # the front door only ever emits a runnable-path route or a route-to-human; never a verdict, never a drop.
    for _label, text, _expected in CASES:
        route, reason = classify(text)
        assert route in _RUNNABLE or route == ROUTE_TO_HUMAN, "unexpected route %s" % route
    print("ok every submission routes to a judge path or to a human")


def test_human_routes_carry_a_reason():
    # a route-to-human must always carry a typed reason, so the triager never sees a silent drop.
    for _label, text, _expected in CASES:
        route, reason = classify(text)
        if route == ROUTE_TO_HUMAN:
            assert reason, "ROUTE_TO_HUMAN with no typed reason"
    print("ok every route-to-human carries a typed reason")


def test_expected_routes_match():
    for label, text, expected in CASES:
        route, _reason = classify(text)
        assert route == expected, "%s -> %s, expected %s" % (label, route, expected)
    print("ok all cases route as expected")


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
    print(("all intake self-tests passed" if not failed else "%d FAILED" % failed))
    sys.exit(1 if failed else 0)
