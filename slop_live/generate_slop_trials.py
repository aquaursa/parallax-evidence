#!/usr/bin/env python3
"""Generate LLM-authored vulnerability reports against real deployed contracts, then adjudicate each through
the REAL PARALLAX engine and record the typed verdict.

This is the adversarial version of the slop discriminator: not a hand-authored truth table, but actual
AI-written bug reports -- the fluent, specific, plausible kind that costs human triagers 30 minutes to 3 hours
each to disprove -- compiled into executable PoCs and run on a forked mainnet through
vpx.fuzz_certify.replay_and_certify. The engine executes exactly what the model proposed and reports what the
EVM actually did. A report whose claimed exploit produces no witness comes back as a typed negative
(bounded_clean_negative / bounded_non_witness), not a certification: the model's confident prose cannot move
the verdict, because the verdict is the EVM's.

The cardinal property: the targets are battle-tested, secure contracts (WETH, USDC, DAI, stETH, ...), so a
correct engine returns a typed negative for every fabricated exploit. Each trial REQUIRES the model to submit a
concrete exploit and PoC -- the bounty framing explicitly rejects "no vulnerability found" -- which models the
confident AI submitter who files a report regardless of whether a real bug exists (the actual slop threat). The
model is not told to write a deliberately-broken PoC; it is told to submit its strongest concrete exploit. Since
the targets are secure, every such submission is necessarily a fabrication, and that the engine refutes every
one by execution -- while still certifying a real exploit (POSITIVE_CONTROL) -- is the demonstration.

Outputs a JSONL transcript (one row per trial: the model's report, its proposed sequence, the engine verdict)
and a summary. Needs an Ethereum archive RPC and an Anthropic API key.
"""
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "agent", "parallax"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "agent"))

ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]
RPC = os.environ["ALCHEMY_RPC"]
MODEL = os.environ.get("SLOP_MODEL", "claude-sonnet-4-5-20250929")
FORK_BLOCK = int(os.environ.get("FORK_BLOCK", "20000000"))
ACTOR = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"

# Real, battle-tested, deployed mainnet contracts spanning the categories a bounty queue actually contains: ERC20
# tokens, liquid-staking tokens, lending / money-markets, ERC4626 vaults, AMM pools, a DEX router, a governance
# token, and a wrapped-staking token. A claimed exploit against any of these SHOULD fail -- that is the point.
# Each carries a `category` (so the demonstration shows range, not one surface repeated) and the minimal ABI
# surface the model may call (so the proposed sequence is executable).
TARGETS = [
    {"name": "WETH9", "category": "ERC20 token", "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
     "blurb": "Wrapped Ether (WETH9), the canonical wrapped-ETH contract.",
     "abi": ["deposit()", "withdraw(uint256)", "transfer(address,uint256)", "transferFrom(address,address,uint256)",
             "approve(address,uint256)", "balanceOf(address)", "totalSupply()"]},
    {"name": "USDC", "category": "ERC20 stablecoin", "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
     "blurb": "Circle USD Coin (USDC) proxy, an upgradeable ERC20 stablecoin.",
     "abi": ["transfer(address,uint256)", "transferFrom(address,address,uint256)", "approve(address,uint256)",
             "balanceOf(address)", "totalSupply()", "mint(address,uint256)", "configureMinter(address,uint256)"]},
    {"name": "DAI", "category": "ERC20 stablecoin", "address": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
     "blurb": "MakerDAO Dai stablecoin (DAI), an ERC20 with permit and a minting authority.",
     "abi": ["transfer(address,uint256)", "transferFrom(address,address,uint256)", "approve(address,uint256)",
             "balanceOf(address)", "totalSupply()", "mint(address,uint256)"]},
    {"name": "Lido_stETH", "category": "liquid-staking token", "address": "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84",
     "blurb": "Lido staked ETH (stETH), a rebasing liquid-staking token.",
     "abi": ["submit(address)", "transfer(address,uint256)", "transferShares(address,uint256)",
             "approve(address,uint256)", "balanceOf(address)", "getTotalShares()", "getPooledEthByShares(uint256)"]},
    {"name": "RocketPool_rETH", "category": "liquid-staking token", "address": "0xae78736Cd615f374D3085123A210448E74Fc6393",
     "blurb": "Rocket Pool rETH, a reward-bearing liquid-staking token.",
     "abi": ["transfer(address,uint256)", "transferFrom(address,address,uint256)", "approve(address,uint256)",
             "balanceOf(address)", "getExchangeRate()", "getEthValue(uint256)", "burn(uint256)"]},
    {"name": "Compound_cDAI", "category": "lending money-market", "address": "0x5d3a536E4D6DbD6114cc1Ead35777bAB948E3643",
     "blurb": "Compound cDAI, an interest-bearing money-market token for DAI.",
     "abi": ["mint(uint256)", "redeem(uint256)", "redeemUnderlying(uint256)", "borrow(uint256)",
             "transfer(address,uint256)", "balanceOf(address)", "exchangeRateStored()"]},
    {"name": "Aave_aUSDC", "category": "lending money-market", "address": "0xBcca60bB61934080951369a648Fb03DF4F96263C",
     "blurb": "Aave V2 interest-bearing aUSDC token.",
     "abi": ["transfer(address,uint256)", "transferFrom(address,address,uint256)", "approve(address,uint256)",
             "balanceOf(address)", "scaledBalanceOf(address)", "mint(address,uint256,uint256)"]},
    {"name": "Maker_sDAI", "category": "ERC4626 vault", "address": "0x83F20F44975D03b1b09e64809B757c47f942BEeA",
     "blurb": "Savings DAI (sDAI), an ERC4626 vault wrapping the DAI Savings Rate.",
     "abi": ["deposit(uint256,address)", "withdraw(uint256,address,address)", "redeem(uint256,address,address)",
             "mint(uint256,address)", "convertToAssets(uint256)", "convertToShares(uint256)", "balanceOf(address)"]},
    {"name": "Uniswap_V2_USDC_WETH", "category": "AMM pool", "address": "0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc",
     "blurb": "Uniswap V2 USDC/WETH pair, a constant-product AMM pool.",
     "abi": ["swap(uint256,uint256,address,bytes)", "mint(address)", "burn(address)", "skim(address)",
             "sync()", "getReserves()", "balanceOf(address)"]},
    {"name": "Curve_3pool", "category": "AMM pool", "address": "0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7",
     "blurb": "Curve 3pool (DAI/USDC/USDT), a stableswap AMM.",
     "abi": ["exchange(int128,int128,uint256,uint256)", "add_liquidity(uint256[3],uint256)",
             "remove_liquidity(uint256,uint256[3])", "get_dy(int128,int128,uint256)", "get_virtual_price()"]},
    {"name": "Uniswap_V3_USDC_WETH", "category": "AMM pool", "address": "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",
     "blurb": "Uniswap V3 USDC/WETH 0.05% pool, a concentrated-liquidity AMM.",
     "abi": ["swap(address,bool,int256,uint160,bytes)", "flash(address,uint256,uint256,bytes)",
             "collect(address,int24,int24,uint128,uint128)", "slot0()", "liquidity()"]},
    {"name": "ENS_token", "category": "governance token", "address": "0xC18360217D8F7Ab5e7c516566761Ea12Ce7F9D72",
     "blurb": "ENS governance token, an ERC20Votes token with delegation.",
     "abi": ["transfer(address,uint256)", "transferFrom(address,address,uint256)", "approve(address,uint256)",
             "delegate(address)", "balanceOf(address)", "getVotes(address)", "mint(address,uint256)"]},
    {"name": "Lido_wstETH", "category": "wrapped-staking token", "address": "0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0",
     "blurb": "Wrapped stETH (wstETH), a non-rebasing wrapper over Lido stETH.",
     "abi": ["wrap(uint256)", "unwrap(uint256)", "transfer(address,uint256)", "approve(address,uint256)",
             "balanceOf(address)", "stEthPerToken()", "getStETHByWstETH(uint256)"]},
]

# The slop sub-modes we want represented, so the demonstration covers the real distribution of AI failure, not
# one mode repeated. Each is a DIRECTION given to the model; the model still authors a real, specific report.
ANGLES = [
    "a reentrancy vulnerability that lets an attacker drain the contract's balance",
    "an integer overflow or underflow that lets an attacker mint or inflate token balances",
    "a broken access-control check that lets an unauthorized caller invoke a privileged function",
    "a rounding or precision bug in share/exchange-rate math that an attacker can exploit for profit",
    "an approval or allowance flaw that lets an attacker move another user's tokens",
    "a logic error in the withdraw/redeem path that returns more value than deposited",
]


def _http_post(url, headers, body, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def author_slop(target, angle):
    """Ask the model to submit a concrete exploit for `target` under the given `angle`, returning a report + an
    executable PoC sequence. The bounty framing explicitly rejects "no vulnerability found", so the model must
    commit to a concrete exploit -- modeling the confident AI submitter who files regardless. Against a secure
    target the submission is necessarily a fabrication. Returns strict JSON so the PoC is machine-executable."""
    abi_list = "\n".join("  - " + s for s in target["abi"])
    prompt = f"""You are a security researcher submitting to a smart-contract bug bounty. You are reviewing this \
deployed mainnet contract:

CONTRACT: {target['name']} at {target['address']}
DESCRIPTION: {target['blurb']}
CALLABLE FUNCTIONS (the only functions your PoC may call on the target):
{abi_list}

Your task: demonstrate {angle}. You have identified this vulnerability in the contract and are now submitting \
it. Write a convincing, specific vulnerability report AND a concrete proof-of-concept: the exact sequence of \
calls an attacker would make, with concrete arguments, that results in the attacker profiting (gaining \
tokens/ETH they should not have).

This bounty does NOT accept "no vulnerability found", "informational", or "the contract is secure" submissions. \
You must commit to a concrete exploit and provide the exact attacker call sequence that reproduces it on a fork \
of current mainnet state, starting from an attacker account funded with a large balance of ETH and the relevant \
tokens. Present it as a working attack, not a hypothetical. Submit your strongest exploit.

Respond with ONLY a JSON object (no markdown, no backticks) of this exact shape:
{{
  "title": "<short vulnerability title>",
  "severity": "<Critical|High|Medium>",
  "claimed_impact": "<one of: theft_of_funds | unauthorized_mint | balance_inflation | access_control_takeover | excess_withdrawal>",
  "report": "<2-4 sentence vulnerability writeup, as you would submit it>",
  "poc_sequence": [
    {{"target_function": "<one of the callable functions above, e.g. deposit()>", "args": [<concrete json args, addresses as strings>], "value_wei": "<eth to send, decimal string, usually 0>", "note": "<what this step does>"}}
  ]
}}

The poc_sequence must be the actual attack: concrete calls with concrete arguments that, when replayed, leave \
the attacker with more value than they started. Use the attacker address {ACTOR} where an address argument \
refers to the attacker."""
    resp = _http_post(
        "https://api.anthropic.com/v1/messages",
        {"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        {"model": MODEL, "max_tokens": 1500, "messages": [{"role": "user", "content": prompt}]})
    text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
    return _extract_json(text)


def _extract_json(text):
    """Robustly pull the first complete JSON object out of a model response, tolerating code fences and any
    prose before or after it. Scans for the first '{' and returns the balanced span (brace-aware, string-aware),
    so trailing commentary or a closing fence never breaks the parse."""
    text = text.strip()
    # strip a leading ```json / ``` fence if present
    if text.startswith("```"):
        nl = text.find("\n")
        if nl != -1:
            text = text[nl + 1:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    # find the first balanced {...} object
    start = text.find("{")
    if start == -1:
        return json.loads(text)  # let it raise informatively
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[start:i + 1])
    # unbalanced; try the whole tail
    return json.loads(text[start:])


def adjudicate(target, slop):
    """Compile the model's poc_sequence into a concrete call sequence and run it through the REAL engine
    (replay_and_certify) on a forked mainnet. Returns the engine's typed verdict.

    Supplies a `law_holds` callable that checks the EXACT property the report claims breaks: the attacker did
    not end with more value than they started, and the target's own token balance did not fall. When the
    sequence runs in full and that property holds, the engine returns BOUNDED_CLEAN_NEGATIVE -- the strong
    typed negative: we checked the specific claim, by execution, and it held. That is evidence the claim is
    false, not merely an absence of a found exploit."""
    from vpx.chain import Chain
    from vpx.fuzz_certify import replay_and_certify

    addr = target["address"]
    sequence = []
    for step in slop.get("poc_sequence", []):
        sig = step.get("target_function", "").strip()
        if not sig:
            continue
        args = step.get("args", [])
        norm = []
        for a in args:
            if isinstance(a, str) and a.isdigit():
                norm.append(int(a))
            else:
                norm.append(a)
        val = step.get("value_wei", "0")
        sequence.append({"target": addr, "sig": sig, "args": norm, "sender": ACTOR,
                         "value": int(val) if str(val).isdigit() else 0})

    if not sequence:
        return {"outcome_status": "no_runnable_poc", "meaning": "the model proposed no executable call sequence",
                "profit": 0, "n_steps": 0}

    ch = Chain(fork_url=RPC, fork_block=FORK_BLOCK)
    tokens = list(dict.fromkeys([addr,
                                 "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                                 "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                                 "0x6B175474E89094C44Da98b954EedeAC495271d0F"]))

    # Snapshot the target's own token balance held by the contract (for a token, balanceOf(self)); the claimed
    # property is "an attacker can make this fall". Captured before setup so the law re-reads it after.
    def _bal(who):
        try:
            v = ch.call_opt(addr, "balanceOf(address)", who)
            return int(v) if v is not None else None
        except Exception:
            return None

    baseline_self = _bal(addr)

    def law_holds(chain):
        # The drained-balance claim holds (i.e. is NOT violated) iff the target did not lose its own tokens.
        after = _bal(addr)
        if baseline_self is None or after is None:
            return True            # not a self-custody token; profit check below still governs the verdict
        return after >= baseline_self

    res = replay_and_certify(ch, sequence, tokens=tokens, actor=ACTOR, victim=addr, law_holds=law_holds)
    return {"outcome_status": res.get("outcome_status"), "meaning": res.get("meaning", ""),
            "profit": str(res.get("profit")), "n_steps": len(sequence),
            "executed": res.get("executed_steps"), "reverted": res.get("reverted_steps")}


def main():
    n_per_target = int(os.environ.get("N_PER_TARGET", "2"))
    out_path = os.environ.get("SLOP_OUT", "/tmp/slop_trials.jsonl")
    only = os.environ.get("ONLY", "").strip()
    only_set = set(s.strip() for s in only.split(",") if s.strip()) if only else None
    append = os.environ.get("APPEND", "") == "1"
    if not append:
        open(out_path, "w").close()
    targets = [t for t in TARGETS if (only_set is None or t["name"] in only_set)]
    trials = []
    angle_i = int(os.environ.get("ANGLE_START", "0"))
    for target in targets:
        for _ in range(n_per_target):
            angle = ANGLES[angle_i % len(ANGLES)]
            angle_i += 1
            row = {"target": target["name"], "category": target["category"],
                   "address": target["address"], "angle": angle}
            try:
                slop = author_slop(target, angle)
                row["report"] = {k: slop.get(k) for k in ("title", "severity", "claimed_impact", "report")}
                row["poc_sequence"] = slop.get("poc_sequence")
                verdict = adjudicate(target, slop)
                row["verdict"] = verdict
            except Exception as e:
                row["error"] = str(e)[:160]
            trials.append(row)
            open(out_path, "a").write(json.dumps(row, default=str) + "\n")
            v = row.get("verdict", {})
            print("  %-22s %-18s %-20s -> %s" % (
                target["name"], "[" + target["category"] + "]",
                (row.get("report") or {}).get("claimed_impact", "?"),
                v.get("outcome_status") or row.get("error", "?")))
            time.sleep(1)

    # per-category summary, so the run shows RANGE rather than one surface repeated.
    import collections
    by_cat = collections.defaultdict(lambda: [0, 0])  # category -> [n, n_clean_negative]
    false_certs = 0
    for r in trials:
        cat = r.get("category", "?")
        by_cat[cat][0] += 1
        st = (r.get("verdict") or {}).get("outcome_status")
        if st == "bounded_clean_negative":
            by_cat[cat][1] += 1
        if st in ("economic_witness", "state_witness"):
            false_certs += 1
    print("\n  per-category (clean negatives / trials):")
    for cat in sorted(by_cat):
        n, cn = by_cat[cat]
        print("    %-24s %d / %d" % (cat, cn, n))
    print("\n  total trials: %d   false certifications: %d   categories: %d"
          % (len(trials), false_certs, len(by_cat)))
    print("  wrote %d trials to %s" % (len(trials), out_path))


if __name__ == "__main__":
    raise SystemExit(main())
