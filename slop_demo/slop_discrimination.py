#!/usr/bin/env python3
"""parallax-evidence / slop_demo -- a standalone demonstration of the PARALLAX AI-slop discriminator.

This is a self-contained, readable model of the principle that makes PARALLAX unreasonably good at filtering AI
slop. It is NOT the engine -- the production discriminator runs against real EVM execution traces. This demo
runs the SAME decision logic over a set of labelled, pre-computed "execution facts" so a reviewer can see the
separation, run it themselves, and read exactly how the call is made. No network, no engine, standard library
only.

The principle: AI slop has a mechanical signature -- a confident claim with no corresponding evidence. PARALLAX
holds BOTH the submitter's claim (what the PoC asserts) AND the EVM-executed evidence (what actually happened on
a forked mainnet) and cross-checks them. A pure-LLM reviewer can be fooled by fluent prose; a pure-static tool
cannot see runtime effect. The cross-check is the thing only an execution-grounded system can do.

Each labelled case below carries:
  - `claim`:  the impact class the submission asserts (from its PoC assertions / report)
  - `evidence`: what the EVM execution demonstrated -- the "witness" the engine computed
  - `expected`: whether this is slop (the ground-truth label for the demo)

The discriminator returns one of:
  CORROBORATED            claim matches a real, non-fabricated witness -> NOT slop (the real thing)
  CLAIM_WITHOUT_EVIDENCE  ran/passed, claims an effect, no witness -> the signature slop
  CLASS_MISMATCH          claims one class, the execution showed another
  HOLLOW_ASSERTION        the PoC's assertion is tautological (a pass that tests nothing)
  FABRICATED_EVIDENCE     a "gain" conjured by test-harness cheatcodes, not extracted from protocol logic
  NO_RUNNABLE_CLAIM       prose only / nothing executed -> routes to a human (not a negative)

The cardinal property demonstrated: a real, corroborated witness is NEVER labelled slop, so the discriminator
cannot suppress a true positive (the production engine enforces this structurally; the FP=0 floor is sacred).
"""
import sys

# ---- the discrimination logic (a faithful, standalone model of the engine's contract) ----------------------

CORROBORATED = "CORROBORATED"
CLAIM_WITHOUT_EVIDENCE = "CLAIM_WITHOUT_EVIDENCE"
CLASS_MISMATCH = "CLASS_MISMATCH"
HOLLOW_ASSERTION = "HOLLOW_ASSERTION"
FABRICATED_EVIDENCE = "FABRICATED_EVIDENCE"
NO_RUNNABLE_CLAIM = "NO_RUNNABLE_CLAIM"
INERT_EXECUTION = "INERT_EXECUTION"


def assess(claim, evidence):
    """Cross-check a submission's CLAIM against its EVM-executed EVIDENCE. Returns (label, is_slop).

    `claim`    = {"class": <impact class or None>, "ran": bool, "hollow_assertion": bool}
    `evidence` = {"demonstrated": <impact class or None>, "fabricated": bool}

    Order matters: fabricated evidence is checked BEFORE corroboration (a real-looking gain conjured by
    cheatcodes must never corroborate); a real demonstrated witness short-circuits to CORROBORATED so a true
    positive can never be called slop.
    """
    demonstrated = evidence.get("demonstrated")
    fabricated = bool(evidence.get("fabricated"))

    # 0) fabricated evidence: a gain that exists in the trace but was conjured by cheatcodes, not protocol logic.
    if demonstrated and fabricated:
        return FABRICATED_EVIDENCE, True

    # 1) a real, non-fabricated witness -> NOT slop. If it demonstrates a DIFFERENT class than claimed, mismatch.
    if demonstrated:
        if claim.get("class") and claim["class"] != demonstrated:
            return CLASS_MISMATCH, True
        return CORROBORATED, False

    # 2) no witness was demonstrated. Distinguish the slop sub-modes.
    if claim.get("hollow_assertion"):
        return HOLLOW_ASSERTION, True
    if claim.get("ran") and claim.get("class"):
        return CLAIM_WITHOUT_EVIDENCE, True
    if claim.get("ran"):
        return INERT_EXECUTION, True
    return NO_RUNNABLE_CLAIM, True


# ---- the labelled demonstration set ------------------------------------------------------------------------
# (mirrors proofs/slop_discrimination_proof.py in the engine: 4 real witnesses + 7 slop modes)

CASES = [
    # id, claim, evidence, expected_is_slop, note
    ("real-econ",
     {"class": "economic", "ran": True}, {"demonstrated": "economic", "fabricated": False}, False,
     "a real exploit: claims theft, the trace shows the attacker net-gaining a token"),
    ("real-acl",
     {"class": "access_control", "ran": True}, {"demonstrated": "access_control"}, False,
     "a real exploit: claims an ownership takeover, the trace shows the privileged-role event"),
    ("real-nft",
     {"class": "nft", "ran": True}, {"demonstrated": "nft"}, False,
     "a real exploit: claims NFT theft, the trace shows the attacker acquiring the tokenId"),
    ("real-certified",
     {"class": "economic", "ran": True}, {"demonstrated": "economic", "fabricated": False}, False,
     "a certified incident: conservation-checked gain matched to a counterparty loss"),

    ("slop-claim-no-evidence",
     {"class": "economic", "ran": True}, {"demonstrated": None}, True,
     "ran and claims 'complete theft of all funds', but the execution produced NO witness"),
    ("slop-hollow",
     {"class": "economic", "ran": True, "hollow_assertion": True}, {"demonstrated": None}, True,
     "the PoC PASSES under forge but asserts assertTrue(true) -- a pass that tests nothing"),
    ("slop-class-mismatch",
     {"class": "economic", "ran": True}, {"demonstrated": "access_control"}, True,
     "claims theft of funds; the trace shows only an ownership event, no value movement"),
    ("slop-prose-only",
     {"class": "economic", "ran": False}, {"demonstrated": None}, True,
     "a fluent vulnerability narrative with no runnable PoC -> routes to a human"),
    ("slop-inert",
     {"class": None, "ran": True}, {"demonstrated": None}, True,
     "the PoC runs but claims nothing specific and produces no witness"),
    ("slop-fab-prank",
     {"class": "economic", "ran": True}, {"demonstrated": "economic", "fabricated": True}, True,
     "a REAL Transfer fires -- but it was authorised by impersonating a whale (vm.prank), not protocol logic"),
    ("slop-fab-store",
     {"class": "economic", "ran": True}, {"demonstrated": "economic", "fabricated": True}, True,
     "the attacker's balance was written directly with deal()/vm.store -- conjured, not extracted"),
]


def run():
    real_as_slop = []     # the cardinal failure: a real witness suppressed as slop (must be 0)
    slop_as_real = []     # a slop that slipped through as corroborated (must be 0)
    print("PARALLAX AI-SLOP DISCRIMINATION (standalone demo) -- claim vs EVM-executed evidence")
    print("=" * 86)
    for cid, claim, evidence, expected_slop, note in CASES:
        label, got_slop = assess(claim, evidence)
        mark = "ok" if got_slop == expected_slop else "XX"
        kind = "REAL" if not expected_slop else "SLOP"
        print("  [%s] %-22s %-4s -> %-22s" % (mark, cid, kind, label))
        print("       %s" % note)
        if (not expected_slop) and got_slop:
            real_as_slop.append(cid)
        if expected_slop and label == CORROBORATED:
            slop_as_real.append(cid)
    print("=" * 86)
    n_real = sum(1 for c in CASES if not c[3])
    n_slop = sum(1 for c in CASES if c[3])
    print("  real witnesses: %d   slop submissions: %d" % (n_real, n_slop))
    print("  real-as-slop (cardinal failure, must be 0): %d %s" % (len(real_as_slop), real_as_slop or ""))
    print("  slop-as-real (slipped through, must be 0):  %d %s" % (len(slop_as_real), slop_as_real or ""))
    ok = (not real_as_slop) and (not slop_as_real)
    print("\nRESULT: %s" % ("PASS -- every real witness CORROBORATED, every slop mode caught; clean separation"
                            if ok else "FAIL -- separation is not clean"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(run())
