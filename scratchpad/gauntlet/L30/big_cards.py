"""L30: the owner's observation -- sim opponents "rarely play their 6+ elixir cards" (RG never fielded, Recruits never
fielded). Count the opponent's deploys by cost at floor 0 vs 7, same policy/instrument as L29's cadence_floor.py, and per
match whether a >=6-elixir NON-spell card in the deck was ever played. usage: <ckpt> <matches> <seed> <floor> <out.json>"""
import sys, json
sys.path.insert(0, "src"); sys.path.insert(0, "tools")
import numpy as np, torch
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
from clashrl.sim import rollout_search as RS
from clashrl.sim.opponents import make_opponent
ckpt, matches, seed, floor, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4]), sys.argv[5]
cfg = Config.load("data/bench/gate05_run.yaml"); cfg.data.setdefault("sim", {})["bot_attack_floor"] = floor
env = SimMatchEnv(cfg); env.rng.seed(seed)
env.opponent_provider = lambda e: make_opponent(cfg, e.db, e.rng, e.meta_pool, adaptive=True)
env.reset(); net = RS.load_net(ckpt, env, torch.device("cpu"))
sr = RS.Searcher(env, net, torch.device("cpu"), 12.0, 0, 4, 1.0, 0.25, cells=3)
rng = np.random.RandomState(seed)
per_match, plays, seen_t, done = [], [], -1.0, 0
while done < matches:
    cq_m, ceq, gq_m, playable = sr._forward()
    pp = float(torch.softmax(gq_m, 0)[1]) if bool(playable.any()) else 0.0
    if rng.rand() < pp:
        pc = torch.softmax(cq_m, 0).numpy(); ci = int(rng.choice(len(pc), p=pc / pc.sum()))
        act = (1, ci, sr._cell_for(ceq, ci))
    else:
        act = (0, 0, 0)
    e = env.eng; d = e.last_deploy.get(1)
    if d and d[3] != seen_t:
        seen_t = d[3]; plays.append((d[0].base, float(d[0].elixir), d[0].kind, float(e.t)))
    _o, _r, dn, info = env.step(act)
    if dn:
        done += 1; bot = env.opponent
        big = [s for s in bot.specs if s.elixir >= 6 and s.kind != "spell"]
        played = {b for b, _c, _k, _t in plays}
        per_match.append({"style": bot.style, "deck": getattr(bot, "deck_name", "?"), "n_plays": len(plays),
                          "cost_hist": {str(int(c)): sum(1 for _b, cc, _k, _t in plays if int(cc) == int(c)) for c in range(1, 10)},
                          "big_cards": [s.base for s in big], "big_played": [s.base for s in big if s.base in played],
                          "big_plays": sum(1 for _b, c, k, _t in plays if c >= 6 and k != "spell"),
                          "single_plays": sum(1 for _b, _c, _k, t in plays if t < 120.0)})
        plays, seen_t = [], -1.0; env.reset()
json.dump({"floor": floor, "seed": seed, "per_match": per_match}, open(out, "w"), indent=1)
tot = sum(m["n_plays"] for m in per_match); bigp = sum(m["big_plays"] for m in per_match)
decks_big = [m for m in per_match if m["big_cards"]]; never = [m for m in decks_big if not m["big_played"]]
print(f"floor {floor:.0f} seed {seed}: {tot} opponent deploys, >=6 non-spell {bigp} ({100*bigp/max(1,tot):.1f}%); decks holding a >=6 card {len(decks_big)}/{matches}, "
      f"never played it {len(never)} " + str([(m['style'], m['big_cards']) for m in never]))
