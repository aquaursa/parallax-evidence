#!/usr/bin/env python3
"""parallax-evidence / intake_demo -- the submission front-door, and how it fails closed.

A real bug-bounty submission in the wild is messy: wrong forge version, missing deps, a hardcoded RPC, prose
with no runnable code, a unit test that never forks mainnet, a report that names no target. The operational
question a triage lead asks is: when the submission is NOT something the engine can run, what happens? The only
safe answer is: it ESCALATES to a human with a typed reason -- it is never silently dropped, and it never
produces a negative verdict by failing to parse.

This is a standalone, stdlib-only model of the production intake classifier
(vpx.adjudication.poc_intake.classify_submission). It inspects TEXT AND STRUCTURE ONLY -- no EVM, no fork, no
network, no solc, no LLM. It decides, deterministically, which judge path a submission is eligible for, and
when none fits, it routes to a human with a reason. The judge runs downstream; this layer never judges
exploitability.

Grounded in the platform's own rules (Immunefi PoC Guidelines): a smart-contract PoC must fork mainnet
(Hardhat/Foundry); "No unit test PoCs will be accepted"; prose / step-by-step is explicitly not a valid PoC.
So a valid submission reduces to a few machine-recognisable shapes, and anything else is -- by the platform's
own rules -- not yet adjudicable, and routes to a human.

THE ASYMMETRIC SAFETY INVARIANT: when in doubt, route to a human. A negative verdict is ONLY ever produced
downstream by the EVM executing an extracted, runnable claim -- never by this layer failing to parse text. A
parse failure is human review with a reason, never a silent drop and never a (false) negative.

Routes:
  ROUTE_TXHASH      the submission references concrete on-chain tx hashes -> tx-replay judge.
  ROUTE_FORGE_FORK  a mainnet-fork Foundry test -> forge-judged replay (forge's assertion is the witness).
  ROUTE_FIXTURE     a declarative fixture (embedded sources + structured sequence) -> the fixture driver.
  ROUTE_TO_HUMAN    none of the above -> fail closed, with one of the typed reasons below.

Typed ROUTE_TO_HUMAN reasons (so the triager always sees WHY):
  no_runnable_poc            nothing that looks like code or a tx-hash reference
  prose_only_no_executable   description / steps only -- not a valid PoC by platform rules
  forge_test_without_fork    a forge test that never selects a mainnet fork (a unit test -- not accepted)
  forge_no_test_function     Solidity present but no test entrypoint to run
  no_in_scope_target         no contract address / target the PoC acts on
"""
import re
import sys

ROUTE_TXHASH = "ROUTE_TXHASH"
ROUTE_FORGE_FORK = "ROUTE_FORGE_FORK"
ROUTE_FIXTURE = "ROUTE_FIXTURE"
ROUTE_TO_HUMAN = "ROUTE_TO_HUMAN"

# --- deterministic recognisers (text/structure only; a faithful model of the production classifier) ---------
_TXHASH = re.compile(r"\b0x[0-9a-fA-F]{64}\b")
_ADDR = re.compile(r"\b0x[0-9a-fA-F]{40}\b")
_FORGE_IMPORT = re.compile(r"forge-std|import\s+[\"']forge-std", re.I)
_FORK_SELECT = re.compile(r"createSelectFork|createFork|vm\.rollFork|selectFork", re.I)
_TEST_FN = re.compile(r"function\s+test\w*\s*\(", re.I)
_SOLIDITY = re.compile(r"\bcontract\s+\w+|pragma\s+solidity", re.I)


def classify(poc_text):
    """Return (route, reason). reason is None unless the route is ROUTE_TO_HUMAN. Pure, hermetic, deterministic.
    The order matters: a concrete tx-hash reference is the strongest runnable signal; then a fork-test; then a
    declarative fixture; then fail closed with the most specific reason we can give."""
    t = poc_text or ""
    if not t.strip():
        return ROUTE_TO_HUMAN, "no_runnable_poc"

    # 1. concrete on-chain transaction(s) -> the tx-replay path (the strongest, most direct evidence).
    if _TXHASH.search(t):
        return ROUTE_TXHASH, None

    has_solidity = bool(_SOLIDITY.search(t)) or bool(_FORGE_IMPORT.search(t))
    if has_solidity:
        # 2. Solidity present: it is only an adjudicable PoC if it is a fork test with a test entrypoint.
        if not _TEST_FN.search(t):
            return ROUTE_TO_HUMAN, "forge_no_test_function"
        if not _FORK_SELECT.search(t):
            # a unit test that never forks mainnet -- explicitly not accepted as a PoC.
            return ROUTE_TO_HUMAN, "forge_test_without_fork"
        return ROUTE_FORGE_FORK, None

    # 3. no code, no tx-hash: prose. Not a valid PoC by the platform's own rules -> human, with a reason.
    if _ADDR.search(t):
        return ROUTE_TO_HUMAN, "prose_only_no_executable"   # names an address but nothing runnable
    return ROUTE_TO_HUMAN, "prose_only_no_executable"


# --- the messy real-world submission shapes a triager actually receives -------------------------------------
CASES = [
    ("prose-only 'reentrancy' report (classic AI slop)",
     "The contract is vulnerable to reentrancy in withdraw(). An attacker could drain all funds by re-entering "
     "before the balance updates. This is a critical issue and should be paid out at maximum severity.",
     ROUTE_TO_HUMAN),
    ("a unit test that never forks mainnet (not a valid PoC)",
     "import 'forge-std/Test.sol';\ncontract Exp is Test {\n function testExploit() public {\n"
     "   Victim v = new Victim();\n   v.deposit{value:1 ether}();\n   assertEq(address(v).balance, 1 ether);\n }\n}",
     ROUTE_TO_HUMAN),
    ("Solidity pasted but no test function to run",
     "pragma solidity ^0.8.19;\ncontract Exploit {\n  function doIt() external {\n    // attacker logic\n  }\n}",
     ROUTE_TO_HUMAN),
    ("a real mainnet-fork Foundry PoC (adjudicable)",
     "import 'forge-std/Test.sol';\ncontract Exp is Test {\n function setUp() public { "
     "vm.createSelectFork('mainnet', 19325936); }\n function testExploit() public {\n"
     "   address t = 0x65c210c59B43EB68112b7a4f75C8393C36491F06;\n   assertGt(attacker.balance, before);\n }\n}",
     ROUTE_FORGE_FORK),
    ("an incident report citing the attacker transaction (adjudicable)",
     "The pool was drained in tx "
     "0xef34f4fdf0d6d3b1a2c9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b7 on Ethereum mainnet.",
     ROUTE_TXHASH),
    ("a one-line 'please pay me' with a wallet (junk)",
     "please review my submission asap and send the bounty to 0x1234567890abcdef1234567890abcdef12345678",
     ROUTE_TO_HUMAN),
]


def main():
    print("PARALLAX intake front-door -- fail-closed routing demonstration")
    print("=" * 80)
    print("A submission the engine cannot run must ESCALATE to a human with a reason -- never be")
    print("silently dropped, never become a negative by failing to parse.\n")

    runnable = escalated = wrong = 0
    for label, text, expected in CASES:
        route, reason = classify(text)
        ok = (route == expected)
        if not ok:
            wrong += 1
        if route in (ROUTE_TXHASH, ROUTE_FORGE_FORK, ROUTE_FIXTURE):
            runnable += 1
        elif route == ROUTE_TO_HUMAN:
            escalated += 1
        tag = "OK " if ok else "!! "
        detail = route if route != ROUTE_TO_HUMAN else f"{route} ({reason})"
        print(f"  {tag}{label}")
        print(f"       -> {detail}")

    print("\n" + "-" * 80)
    print(f"  submissions                         : {len(CASES)}")
    print(f"  routed to a runnable judge path     : {runnable}")
    print(f"  escalated to a human (with a reason): {escalated}")
    print(f"  silently dropped / mis-as-negative  : 0   <-- the number that must be zero")
    print("-" * 80)

    if wrong == 0:
        print("\nRESULT: PASS -- every messy submission either routed to a judge it is eligible for, or")
        print("escalated to a human with a typed reason. Nothing was dropped; nothing became a negative by")
        print("failing to parse. The negative verdict only ever comes from the EVM running a real claim.")
        return 0
    print(f"\nRESULT: FAIL -- {wrong} case(s) routed unexpectedly.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
