#!/usr/bin/env python3
"""parallax-evidence / slop_live -- AI-written bug reports, refuted by execution.

Unlike `slop_demo/` (a readable, network-free model of the decision logic), this is the LIVE-FIRE record: real
vulnerability reports authored by a frontier LLM against real, battle-tested mainnet contracts, each compiled
into an executable proof-of-concept and adjudicated by the actual PARALLAX engine on a forked mainnet. The
model was asked to find and demonstrate a working exploit -- exactly the task an AI submitting to a bug bounty
performs -- and the engine reported what the EVM actually did when its PoC ran.

The transcript (TRANSCRIPT.json) is the evidence: for each trial it carries the model's full report (title,
severity, claimed impact, writeup), the exact call sequence it proposed, and the engine's typed verdict. This
script re-checks the cardinal properties over that transcript -- no network, no engine, standard library only,
so anyone can confirm them:

  1. Every fabricated exploit came back a TYPED NEGATIVE (bounded_clean_negative): the PoC ran in full, and the
     exact property the report claimed breaks held under execution. Not "we didn't find it" -- "we checked the
     claim, by execution, and it held."
  2. ZERO false certifications: no AI report, however fluent or high-severity, was ever certified. The model's
     prose moved the verdict not at all, because the verdict is the EVM's.

To regenerate the transcript from scratch (needs an archive RPC + an Anthropic API key), see slop_trial.py in
the engine repo. To confirm this is discrimination and not blanket rejection -- that the SAME harness certifies
a REAL exploit -- see POSITIVE_CONTROL.json, whose sequence genuinely moves value to the attacker and which the
engine grades economic_witness.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

CLEAN_NEGATIVE = "bounded_clean_negative"
WITNESS_STATUSES = {"economic_witness", "state_witness"}


def load_transcript():
    return json.load(open(os.path.join(HERE, "TRANSCRIPT.json")))


def run():
    t = load_transcript()
    trials = t["trials"]
    print("PARALLAX slop_live -- AI-written reports adjudicated by the real engine")
    print("=" * 78)
    print("model: %s   |   targets: real mainnet contracts at fork block %s" % (t["model"], t["fork_block"]))
    print("each trial: the LLM authored a vulnerability report + PoC; the engine executed the PoC on a fork.")
    print("-" * 78)

    false_certs = 0
    clean_negatives = 0
    by_target = {}
    by_severity = {}
    for tr in trials:
        v = tr["engine_verdict"]
        status = v["outcome_status"]
        rep = tr["llm_report"]
        by_target.setdefault(tr["target"], 0)
        by_target[tr["target"]] += 1
        sev = rep.get("severity", "?")
        by_severity[sev] = by_severity.get(sev, 0) + 1
        if status in WITNESS_STATUSES:
            false_certs += 1
        if status == CLEAN_NEGATIVE:
            clean_negatives += 1

    # show a few exemplars (highest severity first), so a reader sees the actual slop, not just a count.
    exemplars = sorted(trials, key=lambda x: {"Critical": 0, "High": 1, "Medium": 2}.get(
        x["llm_report"].get("severity"), 3))[:4]
    print("Sample of what the model claimed, and what the EVM said:\n")
    for tr in exemplars:
        rep = tr["llm_report"]
        v = tr["engine_verdict"]
        print("  [%s] %s" % (tr["target"], rep["title"]))
        print("    claimed: %s, severity %s" % (rep["claimed_impact"], rep["severity"]))
        print("    engine:  %s (attacker profit: %s, over %d executed PoC steps)"
              % (v["outcome_status"], v["attacker_profit"], v["steps_in_poc"]))
        print()

    print("-" * 78)
    print("trials:                         %d AI-authored exploit attempts" % len(trials))
    print("  by target:                    %s" % ", ".join("%s=%d" % (k, n) for k, n in sorted(by_target.items())))
    print("  by claimed severity:          %s" % ", ".join("%s=%d" % (k, n) for k, n in sorted(by_severity.items())))
    print("typed clean negatives:          %d" % clean_negatives)
    print("FALSE CERTIFICATIONS (must be 0): %d" % false_certs)
    print("=" * 78)

    ok = (false_certs == 0 and clean_negatives == len(trials) and len(trials) > 0)

    # Positive control: confirm the SAME engine path certifies a real exploit, so the negatives above are
    # discrimination, not a stuck "no". This reads the recorded control verdict.
    pc_ok = False
    try:
        pc = json.load(open(os.path.join(HERE, "POSITIVE_CONTROL.json")))
        pc_status = pc["engine_verdict"]["outcome_status"]
        pc_ok = pc_status in WITNESS_STATUSES
        print("positive control (same harness, a REAL value transfer to the attacker):")
        print("  engine: %s (attacker profit: %s)  -> %s"
              % (pc_status, pc["engine_verdict"]["attacker_profit"],
                 "certified, as it should be" if pc_ok else "UNEXPECTED"))
        print("=" * 78)
    except Exception as e:  # noqa: BLE001
        print("positive control: not available (%s)" % str(e)[:60])
        print("=" * 78)

    if ok and pc_ok:
        print("RESULT: PASS -- every AI-written report was refuted by execution; zero were certified;")
        print("        and the same harness certifies a real exploit. The discrimination is real.")
        return 0
    if ok and not pc_ok:
        print("RESULT: PARTIAL -- slop all refuted, but positive control did not certify (check harness).")
        return 1
    print("RESULT: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(run())
