"""L22: does pro P(play | elixir) split on OPPONENT PRESSURE? Third key = a red TROOP card was played
within the last W seconds (a proxy for threat-on-our-half that needs no engine pass). Same elixir
reconstruction as tools/gate_prior.py. Run from icebow/."""
import sys, csv, math, json
sys.path.insert(0, "src"); sys.path.insert(0, "tools")
from collections import defaultdict
from clashrl.config import Config
from clashrl import cards as _cards
import gate_prior as GP

cfg = Config.load(None); db = _cards.load(cfg)
dt, reg, ot = 0.6, 180.0, 120.0
src = cfg.path("data/royaleapi/crawl2/plays_ext.csv")
rows = list(csv.DictReader(open(src, encoding="utf-8")))
by = defaultdict(list)
for r in rows:
    by[r["replay_tag"]].append(r)
SPELLS = {"the_log", "log", "zap", "arrows", "fireball", "rocket", "tornado", "poison", "lightning", "freeze",
          "rage", "earthquake", "giant_snowball", "snowball", "barbarian_barrel", "goblin_barrel", "graveyard",
          "mirror", "clone", "void", "goblin_curse", "royal_delivery", "skeleton_barrel"}
BUILDINGS = {"tesla", "x_bow", "xbow", "mortar", "inferno_tower", "cannon", "bomb_tower", "goblin_cage",
             "goblin_hut", "barbarian_hut", "furnace", "tombstone", "elixir_collector", "goblin_drill"}
seen_red = defaultdict(int)
for W in (6.0, 10.0):
    win = defaultdict(lambda: [0, 0]); n_rep = 0
    for tag, rs in by.items():
        mine = sorted((r for r in rs if r.get("attr_s") == "blue"), key=lambda r: float(r["seconds"]))
        theirs = []
        for r in rs:
            if r.get("attr_s") != "red" or r.get("attr_ability") == "1":
                continue
            b = GP._base(r["attr_card"]).replace("-", "_"); seen_red[b] += 1
            if b not in SPELLS and b not in BUILDINGS:
                theirs.append(float(r["seconds"]))
        theirs.sort()
        if not mine:
            continue
        seq = [(float(r["seconds"]), "mighty_miner_ability" if (r.get("attr_ability") == "1" or r.get("attr_card") == "_invalid")
                else GP._base(r["attr_card"])) for r in mine]
        end = max(float(r["seconds"]) for r in rs) + dt; n_rep += 1
        e, t, j, k = 5.0, 0.0, 0, 0
        while t < end:
            eb = min(10, int(math.floor(e + 1e-9))); ph = GP._phase(t, reg, ot)
            while k < len(theirs) and theirs[k] <= t:
                k += 1
            pressure = int(k > 0 and t - theirs[k - 1] < W)
            played = 0; t2, tt = t + dt, t
            while j < len(seq) and seq[j][0] < t2:
                pt, name = seq[j]; e = min(10.0, e + GP._rate(tt, reg, ot) * (pt - tt)); tt = pt
                cost = db.elixir(name) or 0; e = max(0.0, e - cost); played = 1; j += 1
            e = min(10.0, e + GP._rate(tt, reg, ot) * (t2 - tt)); t = t2
            w = win[(ph, pressure, eb)]; w[0] += 1; w[1] += played
    print(f"\nW={W:.0f}s  ({n_rep} replays)   pro P(play per 0.6 s decision) by elixir bucket 0..10; n windows below")
    for ph in ("single", "double"):
        tot = sum(v[0] for (p, _, _), v in win.items() if p == ph)
        pres = sum(v[0] for (p, q, _), v in win.items() if p == ph and q == 1)
        print(f"  {ph}: pressure on {100 * pres / max(1, tot):.0f}% of windows")
        for q, lab in ((0, "quiet   "), (1, "pressure")):
            print(f"    {lab} " + " ".join(f"{win[(ph, q, b)][1] / max(1, win[(ph, q, b)][0]):6.3f}" for b in range(11)))
            print(f"    {'  n':8s} " + " ".join(f"{win[(ph, q, b)][0]:6d}" for b in range(11)))
    json.dump({f"{p}|{q}|{b}": v for (p, q, b), v in win.items()},
              open(f"../scratchpad/gauntlet/L22/prior_pressure_W{W:.0f}.json", "w"))
print("\nred cards seen (top 25):", sorted(seen_red.items(), key=lambda kv: -kv[1])[:25])
