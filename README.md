# PARALLAX Evidence

Two claims matter most to a bug-bounty platform, and both are reproducible here.

First, PARALLAX does not raise false positives. On a curated, adversarial dataset it returns FP=0 and FN=0 on the adjudication track, and it correctly declines out-of-scope submissions on the scope-routing track.

Second, it tells real exploits apart from confident, AI-written reports that don't reproduce, including the slop that's built to *look* corroborated. It does this by holding the submitter's claim and the EVM-executed evidence side by side and checking that they agree.

Everything in this repo runs on the Python standard library. No network, no engine. This is the evidence, not the engine itself. The production system judges real EVM execution traces; these demos run the same decision logic over labeled, pre-computed facts, so you can watch the separation happen and read exactly how the call gets made.

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

## What's here

- `slop_demo/` — the standalone slop discriminator and its expected output. Open `slop_discrimination.py`; the decision logic is about forty lines and reads the way it runs.
- `curated/DATASET_SUMMARY.json` — the shape of the FP=0 dataset. Eighteen entries across ten economic classes and four out-of-scope categories, with the two-track confusion matrix.

## Why FP=0 actually means something

PARALLAX keeps two questions apart that lesser tools blur together. One is adjudication power: did the EVM judge a real exploit sequence? The other is scope routing: was an out-of-scope submission correctly left uncertified? Blending them lets a tool launder a weak result into a strong-looking number, so we never blend them.

FP=0 lives on the adjudication side, and it's the line we don't cross. A verdict of "exploit" only ever comes from the EVM running a real, runnable claim. A submission that simply couldn't be searched is never written down as a negative. The dataset summary breaks out both tracks so the number says what it should and nothing more.

## What this is for

The demos show the mechanism works and that it's safe. The number that closes a partnership is that same mechanism pointed at *your* archive: FP=0 on the submissions you've already resolved, and the triage hours it would have given back. That's the conversation we're asking for. This repo is what makes the ask worth your time.

The engine is proprietary. The proof format is open. See [`parallax-proof-bundle`](https://github.com/aquaursa/parallax-proof-bundle) for a bundle you can verify byte for byte and re-run against your own node.

---

PARALLAX is built by [AquaUrsa Research](mailto:research@aquaursa.ai).
