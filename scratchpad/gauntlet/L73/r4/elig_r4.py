"""R4 fork-point census: how often each branch kind is ELIGIBLE per match for the real init (gen_s0), so per-kind
quotas can be sized. Learner = icebow on the GREEDY live rule (tau 0.35, R3 conditions), opponent = gen_s0 SAMPLING
(T 0.3) on the top ladder decks, as the branch workers play. No branching: only rl_royale.fork_alt / the hold rule
are evaluated at every learner decision.

    python scratchpad/gauntlet/L73/r4/elig_r4.py <init.pt> <n_matches> <out.json>
"""
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

import numpy as np                                          # noqa: E402
import torch                                                # noqa: E402

from pipeline import e1_eval as E                           # noqa: E402
from pipeline import rl_royale as RL                        # noqa: E402
from pipeline import search_s0 as S                         # noqa: E402
from pipeline.royale_env import RoyaleSelfPlayEnv           # noqa: E402

torch.set_num_threads(1)
ckpt, n, out = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3])
pol, info = E.load_policy(ckpt, "cpu")
grid = str(info.get("grid", "floor"))
bc = {**RL.BRANCH_DEFAULTS, "branch_kinds": ["hold", "card", "xbow_class"]}
lcfg = {**S.live_cfg(0.35, grid), "T": 0.3}
ocfg = {**S.live_cfg(0.35, grid), "policy": "sample", "T": 0.3}
decks = RL.league_decks(REPO / "scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json")
rows = []
for i in range(n):
    t0 = time.time()
    env = RoyaleSelfPlayEnv(decision_ticks=10, forms_mode="deck", hero_abilities=True, ability_policy="v2")
    spec = {"tag": f"elig{i:03d}", "opp": {"id": "init"}, "learner_deck": list(E.ICEBOW_ENGINE_DECK),
            "opp_deck": decks[i % 40]["engine"], "learner_side": i % 2, "seed": 100 + i}
    m = E.SelfPlayMatch(env, spec, 0, {**lcfg, "entry_index": i}, {**ocfg, "entry_index": i}, pol, pol)
    L = m.learner
    c = {"decisions": 0, "plays": 0, "hold": 0, "card": 0, "xbow_class": 0, "rocket_plays": 0, "xbow_plays": 0,
         "rocket_affordable_not_top": 0, "xbow_def_mass": []}
    names = [str(x) for x in L.deck.cards]
    while True:
        ds = m.due()
        if not ds:
            break
        for s in ds:
            s.prepare()
        dec = {}
        if L in ds:
            p, d, allowed, enc, heads = RL.side_decide(L, fwd=True)
            dec[id(L)] = (p, d, allowed)
            c["decisions"] += 1
            c["plays"] += int(d["play"])
            c["hold"] += int(d["why"] in ("gate", "wait") and 0.2 <= p <= 0.65)
            if d["play"]:
                c["rocket_plays"] += int(names[d["slot"]] == "rocket")
                c["xbow_plays"] += int(names[d["slot"]] == "x_bow")
            for k in ("card", "xbow_class"):
                a = RL.fork_alt(k, L, enc, heads, d, allowed, bc)
                c[k] += int(a is not None)
                if k == "xbow_class" and d["play"] and names[d["slot"]] == "x_bow":
                    from pipeline.decision_options import xbow_offensive_cells
                    alive = tuple(bool(t.alive) for t in L._cur[1].towers[3:6])
                    cl = L.model.cell_logits(enc, torch.tensor([d["slot"]]))[0].double()
                    off = torch.as_tensor(xbow_offensive_cells(alive, grid))
                    c["xbow_def_mass"].append(round(float(torch.softmax(cl, -1)[~off].sum()), 4))
            r = [j for j, x in enumerate(names) if x == "rocket"][0]
            c["rocket_affordable_not_top"] += int(d["play"] and allowed[r] and d["slot"] != r)
        for s in ds:
            if id(s) not in dec:
                dec[id(s)] = RL.side_decide(s)
        for s in ds:
            p, d, _ = dec[id(s)][:3]
            s.apply(p, d)
    c.update(tick=int(env.tick), outcome=m.result()["outcome"], wall_s=round(time.time() - t0, 1))
    rows.append(c)
    print(json.dumps(c), flush=True)
tot = {k: int(sum(r[k] for r in rows)) for k in ("decisions", "plays", "hold", "card", "xbow_class", "rocket_plays",
                                                  "xbow_plays", "rocket_affordable_not_top")}
dm = [x for r in rows for x in r["xbow_def_mass"]]
summary = {"matches": len(rows), "per_match": {k: v / len(rows) for k, v in tot.items()}, "totals": tot,
           "xbow_def_mass_mean": float(np.mean(dm)) if dm else None,
           "xbow_minority_ge_0.2": float(np.mean([min(x, 1 - x) >= 0.2 for x in dm])) if dm else None}
print("SUMMARY " + json.dumps(summary), flush=True)
out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1), encoding="utf-8")
