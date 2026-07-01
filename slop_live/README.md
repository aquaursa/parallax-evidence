# slop_live — AI-written bug reports, refuted by execution

This is the live-fire companion to [`../slop_demo`](../slop_demo). Where `slop_demo` is a readable, network-free
model of the decision logic, this directory is the **record of the real engine doing it**: a frontier LLM was
required to submit a concrete exploit against real, battle-tested mainnet contracts spanning the categories a
bug-bounty queue actually contains, and every proof-of-concept it produced was executed on a forked mainnet by
the actual PARALLAX engine.

The result, over 39 attempts across 8 contract categories: **every submission was a committed fabrication, every
one was refuted by execution, and not one was certified.**

## A committed exploit every time — the real slop threat

The point of this trial is the confident submitter, not the honest one. Each trial explicitly rejects "no
vulnerability found": the model is told the bounty does not accept a "the contract is secure" verdict, so it
must commit to a concrete exploit and PoC. That models the actual slop that floods bounty queues — an AI told to
produce a finding, producing one regardless of whether a real bug exists. Because the targets are secure, every
one of those 39 submissions is necessarily a fabrication. That the engine refutes all 39 by execution — while
still certifying a real exploit (the positive control) — is the demonstration.

The targets span eight categories, each a real deployed contract:

| Category | Contracts |
|---|---|
| ERC20 token | WETH9 |
| ERC20 stablecoin | USDC, DAI |
| liquid-staking token | Lido stETH, Rocket Pool rETH |
| wrapped-staking token | Lido wstETH |
| lending money-market | Compound cDAI, Aave aUSDC |
| ERC4626 vault | Maker sDAI |
| AMM pool | Uniswap V2, Uniswap V3, Curve 3pool |
| governance token | ENS |

Every category came back fully refuted: the engine does not just reject malformed token transfers, it rejects
fabricated exploits against concentrated-liquidity pool math, vault share accounting, and money-market exchange
rates too.

## What happened

For each trial, a model (Claude Sonnet 4.5) was given one of the real deployed contracts above and required to
submit a concrete exploit for it: a vulnerability report (title, severity, claimed impact, writeup) **and** a
proof-of-concept, the exact sequence of calls an attacker would make. That sequence was compiled and run through
the engine's adjudication path (`vpx.fuzz_certify.replay_and_certify`) on a fork of mainnet, funded with a large
attacker balance.

These are not strawmen. The reports are fluent, specific, and technically detailed, the kind that costs a human
triager 30 minutes to 3 hours each to disprove by hand. Of the 39, 24 were rated Critical and 12 High. A sample
of what the model claimed, all rated Critical:

- **WETH9** — "Reentrancy in withdraw() allows double-spend of WETH balance"
- **Aave aUSDC** — "Integer Overflow in mint() Function Leading to Unauthorized Balance Inflation"
- **Maker sDAI** — "ERC4626 withdraw/redeem allows theft via unchecked owner parameter"
- **Uniswap V3** — "Integer Overflow in Tick Crossing During Extreme Swap Leads to Liquidity Manipulation"

Every one of these is false. The contracts are secure. And the engine said so the only way that can't be argued
with, by running the attack and reading the result. For each, the proof-of-concept executed, the exact property
the report claimed breaks **held**, and the attacker ended with **zero** profit. The verdict is
`bounded_clean_negative`: not "we didn't find an exploit," but "we checked the specific claim, by execution, and
it held."

## The cardinal property

**Zero false certifications.** No report, however fluent or high-severity, moved the verdict. A language model
can be talked into agreeing with a convincing report; a static analyzer can flag a pattern that never fires.
Execution is not persuadable.

## It discriminates — it is not a stuck "no"

The obvious objection: *would this engine certify anything?* `POSITIVE_CONTROL.json` answers it. The **same**
adjudication path, on the **same** fork, is given a sequence that genuinely moves value to the attacker (a real
token transfer into the attacker's account). It returns `economic_witness` — certified. The negatives above are
discrimination, not a reflex.

## Run it

```
python3 verify_slop_live.py
```

This re-checks the recorded transcript (`TRANSCRIPT.json`), no network, no engine, standard library only, and
confirms every trial is a typed negative, zero were certified, and the positive control certifies. Expected
output is in `EXPECTED_OUTPUT.txt`; `test_demo.py` asserts the properties.

## Reproduce from scratch

`generate_slop_trials.py` is the harness that produced the transcript. It needs an Ethereum archive RPC and an
Anthropic API key, and it re-authors fresh reports each run (the model is not given the answers), so the exact
reports will differ, but the verdicts will not, because the targets are secure and the engine judges by
execution.

```
ALCHEMY_RPC=<archive-rpc> ANTHROPIC_API_KEY=<key> \
PYTHONPATH=agent/parallax:agent python3 generate_slop_trials.py
```

## Files

- `TRANSCRIPT.json` — the 39 trials: each model report, its proposed PoC sequence, and the engine's verdict.
- `POSITIVE_CONTROL.json` — a real exploit the same harness certifies, proving discrimination.
- `verify_slop_live.py` — re-checks the cardinal properties over the transcript.
- `generate_slop_trials.py` — the harness, to regenerate from scratch.
- `test_demo.py` / `EXPECTED_OUTPUT.txt` — self-test and reference output.
