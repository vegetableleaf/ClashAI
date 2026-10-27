"""F1 diag: one census match (index argv[1]) with CLXIII both sides on the crforge facade; per-decision gate p and the
learner's elixir / hand as the observation shows them -> why some matches stay near-idle."""
import json, os, sys
os.environ.setdefault("ROYALE_RUNTIME", "fin16-linux")
sys.path[:0] = ["/workspace/cfspeed/pylib", "/workspace/f1/cb", "/workspace/f1"]
import numpy as np
import accept_f1 as A
from pipeline import e1_eval as E
from pipeline import search_s0 as S
from pipeline.opp_elixir_count import REGEN_SCHEDULE
from pipeline.royale_env import RoyaleSelfPlayEnv
from pipeline.crforge_core import CrforgeCore

i = int(sys.argv[1])
model, info = E.load_policy(A.CLXIII)
cfg = S.live_cfg(0.5, info["grid"]); cfg.update(action_delay_ticks=6, feature_version=6)
pair = A.census()[i % 223]
spec = {"tag": f"f1obs{i}", "seed": 3000 + i, "learner_side": i % 2, "learner_deck": list(E.ICEBOW_ENGINE_DECK),
        "opp_deck": [n + A.SFX[f] for n, f in zip(pair[2], pair[3])], "opp": {"id": "x"}}
env = RoyaleSelfPlayEnv(decision_ticks=10, forms_mode="deck")
if sys.argv[2:] == ["rs"]:
    cfg.update(action_delay_ticks=26)     # RoyaleSim runs commands at once: the live 26 all in e1_eval
else:
    env.core = CrforgeCore(); env.elixir_regen_schedule = REGEN_SCHEDULE
m = E.SelfPlayMatch(env, spec, 0, dict(cfg), dict(cfg), model, model)
log = []
while True:
    ds = m.due()
    if not ds:
        break
    for s in ds:
        s.prepare()
    enc, heads, p, hand = model.forward_batch([s.gen_row(model) for s in ds], "cpu")
    pre = [s.pre(hand[r]) for r, s in enumerate(ds)]
    dec = E.live_decide_batch(model, enc, heads, p, np.stack([x[1] for x in pre]), np.array([x[2] for x in pre]),
                              tau=cfg["tau"], device="cpu")
    for r, s in enumerate(ds):
        tick, bs, view = s._cur
        log.append(dict(t=int(tick), side=s.side, p=round(float(p[r]), 3), el=round(float(view.my_elixir), 2),
                        allowed=int(pre[r][1].sum()), play=bool(dec[r]["play"]), n_tok=int(s._obs[1].sum())))
    for r, s in enumerate(ds):
        s.apply(p[r], dec[r])
for side in (0, 1):
    L = [x for x in log if x["side"] == side]
    ps = np.array([x["p"] for x in L])
    print(side, "decisions", len(L), "plays", sum(x["play"] for x in L), "p mean/p90", ps.mean().round(3), np.percentile(ps, 90).round(3),
          "elixir mean", np.mean([x["el"] for x in L]).round(2), "allowed mean", np.mean([x["allowed"] for x in L]).round(2),
          "tokens mean", np.mean([x["n_tok"] for x in L]).round(1))
print(json.dumps(log[:12]))
print(json.dumps([x for x in log if x["t"] in (600, 1200, 2400)]))
