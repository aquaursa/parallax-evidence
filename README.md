# PARALLAX Evidence

Three claims matter most to a bug-bounty platform, and all three are reproducible here, in seconds, on the Python standard library.

**It does not raise false positives.** On a curated, adversarial dataset it returns FP=0 and FN=0 on the adjudication track, and correctly declines out-of-scope submissions on the scope-routing track. It tells real exploits apart from confident, AI-written reports that don't reproduce — including slop built to *look* corroborated — by holding the submitter's claim and the EVM-executed evidence side by side and checking they agree. (`slop_demo/`)

**It beats real AI slop, live.** Beyond the logic model above, [`slop_live/`](slop_live) is the record of the *actual engine* doing it: a frontier LLM was asked to find and demonstrate working exploits against real, battle-tested mainnet contracts (WETH, USDC, DAI, stETH, Compound), and every proof-of-concept it wrote was executed on a forked mainnet. Across 35 attempts — many rated Critical, all fluent and specific — **every fabricated exploit was refuted by execution and not one was certified.** A positive control proves the same harness certifies a *real* exploit, so the negatives are discrimination, not a reflex.

**It does not suppress real bugs.** The fear that actually matters in triage is the opposite of a false positive: silently closing a genuine vulnerability. Over the real-incident outcomes, every exploit the engine cannot certify is *escalated to a human with a reason*, never auto-closed. A missed Critical cannot happen on this path by construction. (`safety_demo/`)

**It fails closed on messy input.** A real submission in the wild is a mess — prose with no code, a unit test that never forks mainnet, a report naming no target. When a submission isn't something the engine can run, it routes to a human with a typed reason; it is never dropped and never becomes a negative by failing to parse. (`intake_demo/`)

Everything here runs on the Python standard library. No network, no engine. This is the evidence, not the engine itself. The production system judges real EVM execution traces; these demos run the same decision logic over labeled, pre-computed facts, so you can watch the call get made and read exactly how.

## Run it

```sh
git clone https://github.com/aquaursa/parallax-evidence
cd parallax-evidence
python3 slop_demo/slop_discrimination.py
```

You'll see eleven labeled cases: four real exploits and seven distinct ways a submission can be slop. Each is classified, and it ends here:

```
real-as-slop (cardinal failure, must be 0): 0
slop-as-real (slipped through, must be 0):  0
RESULT: PASS -- every real witness CORROBORATED, every slop mode caught; clean separation
```

The hard cases are in there. A PoC that **passes under forge** while asserting `assertTrue(true)`. A submission that claims theft but moves no money. Slop that manufactures a real-looking gain with test-harness cheatcodes, pranking a whale or writing a balance with `deal()`. A filter that only asks "did the test pass?" falls for all three. The claim-versus-evidence check doesn't.

For the live-fire version — real AI-written reports run through the real engine — see `slop_live/`:

```sh
python3 slop_live/verify_slop_live.py
```

```
trials:                         35 AI-authored exploit attempts
typed clean negatives:          35
FALSE CERTIFICATIONS (must be 0): 0
positive control: economic_witness  -> certified, as it should be
RESULT: PASS -- every AI-written report was refuted by execution; zero were certified.
```

Then the two demos that answer the questions a triage lead actually asks:

```sh
python3 safety_demo/false_negative_safety.py     # does it ever silently miss a real bug?
python3 intake_demo/intake_failclosed.py         # what happens when a submitted PoC is a mess?
```

The safety demo runs the disposition contract over thirteen real, occurred Ethereum exploits: nine certify automatically, four escalate to a human as confirmed-runnable facts, and **zero are suppressed** — a real bug is never told "safe to close" unless the EVM proved it. The intake demo runs six messy submission shapes through the front door: the two runnable ones route to a judge, the four that aren't route to a human *with a typed reason*, and **none are dropped**.

## What's here

- `slop_demo/` — the standalone slop discriminator and its expected output. Open `slop_discrimination.py`; the decision logic is about forty lines and reads the way it runs.
- `safety_demo/` — the false-negative / no-suppression demonstration: real exploits are escalated, never silently closed. `false_negative_safety.py` plus its expected output and self-tests.
- `intake_demo/` — the fail-closed front door: messy submissions route to a human with a typed reason, never dropped, never mis-recorded as a negative. `intake_failclosed.py` plus its expected output and self-tests.
- `curated/DATASET_SUMMARY.json` — the shape of the FP=0 dataset. Eighteen entries across ten economic classes and four out-of-scope categories, with the two-track confusion matrix.

## Why FP=0 actually means something

PARALLAX keeps two questions apart that lesser tools blur together. One is adjudication power: did the EVM judge a real exploit sequence? The other is scope routing: was an out-of-scope submission correctly left uncertified? Blending them lets a tool launder a weak result into a strong-looking number, so we never blend them.

FP=0 lives on the adjudication side, and it's the line we don't cross. A verdict of "exploit" only ever comes from the EVM running a real, runnable claim. A submission that simply couldn't be searched is never written down as a negative. The dataset summary breaks out both tracks so the number says what it should and nothing more.

## What this is for

The demos show the mechanism works and that it's safe. The number that closes a partnership is that same mechanism pointed at *your* archive: FP=0 on the submissions you've already resolved, and the triage hours it would have given back. That's the conversation we're asking for. This repo is what makes the ask worth your time.

The engine is proprietary. The proof format is open. See [`parallax-proof-bundle`](https://github.com/aquaursa/parallax-proof-bundle) for a bundle you can verify byte for byte and re-run against your own node.

---

PARALLAX is built by [AquaUrsa Research](mailto:research@aquaursa.ai).
