"""Spell NICHE probe on a sim checkpoint (GAUNTLET L16 / HANDOFF 5bq). Greedy, SEARCH-FREE, NO spell mask
-> the policy's own casts. For every log / tornado / rocket: (1) LANDING ZONE in the pro crawl's buckets,
(2) what enemy bodies the cast covers at engine ground truth (killed outright / chip only / tower only /
nothing), (3) the opponent's plays in the previous 6 s by class -- the SAME descriptor as
pro_spell_niche.py -- plus the sim's own outcome ledger for tornado/defence terms.
usage (from icebow/): PYTHONHASHSEED=0 .venv/Scripts/python.exe ../scratchpad/gauntlet/L16/sim_spell_niche.py <ckpt> <matches> <seeds,csv> <out.json>"""
import collections, json, os, pathlib, sys, time
_ROOT = pathlib.Path(__file__).resolve().parents[3] / "icebow"
sys.path.insert(0, str(_ROOT / "src")); os.chdir(_ROOT)
import torch
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
from clashrl.sim import rollout_search as RS
from clashrl.sim.engine import tile_dist

W = 6.0
SWARM = {"skeletons", "goblins", "spear_goblins", "goblin_gang", "bats", "minions", "minion_horde", "skeleton_army",
         "guards", "goblin_barrel", "princess", "dart_goblin", "skeleton_barrel", "barbarian_barrel", "fire_spirit",
         "electro_spirit", "ice_spirit", "heal_spirit", "rascals", "archers", "firecracker", "wall_breakers",
         "royal_recruits", "zappies", "three_musketeers", "barbarian"}
TANK = {"hog_rider", "battle_ram", "ram_rider", "giant", "royal_giant", "golem", "elite_barbarians", "royal_hogs",
        "balloon", "lava_hound", "pekka", "mega_knight", "electro_giant", "goblin_giant", "giant_skeleton", "sparky",
        "barbarians", "elixir_golem", "miner", "graveyard", "boss_bandit", "rune_giant"}


def cls(u):
    k = u.spec.key
    if getattr(u.spec, "kind", "") == "building":
        return "building"
    if k in TANK:
        return "tank/wincon"
    if k in SWARM or float(getattr(u.spec, "elixir", 3)) <= 2.0:
        return "swarm/cheap"
    return "medium"


def zone(ny):
    return ("ENEMY princess-tower zone" if ny < 0.25 else "enemy half" if ny < 0.5
            else "own half, bridge side" if ny < 0.75 else "own back / king zone")


def run(ckpt, matches, seed):
    cfg = Config.load(); env = SimMatchEnv(cfg); env.rng.seed(seed); env.reset()
    net = RS.load_net(str(ckpt), env, torch.device("cpu"))
    sr = RS.Searcher(env, net, torch.device("cpu"), 12.0, 0, 4, 1.0, 0.25, cells=3)
    spell_ids = {i for i, s in enumerate(env.specs) if getattr(s, "kind", "") == "spell"}
    # The sim folds nado_king_activate / clump / retarget / combo into ONE ledger key "nado" (sim/env.py:3073).
    # Split them here by re-evaluating the same predicates on the watch records just before the sim does.
    nado = collections.Counter(); _orig = env._nado_shaping
    def _split():
        kt = env.eng.towers[0][2]
        for w in env._nado_watch:
            age = env.eng.t - w["t0"]
            if (w["king_was_asleep"] and not env._nado_king_credited
                    and any(getattr(u, "target", None) is kt for u in w["pulled"] if u.hp > 0)):
                nado["king_activate"] += 1
            if age >= 2.0 and not w["early_done"]:
                close = [u for u in w["pulled"] if u.hp > 0 and tile_dist(u.x, u.y, w["cx"], w["cy"]) <= 2.2]
                worth = lambda u: float(u.spec.elixir) / max(1, u.spec.squad_count or u.spec.count)
                if sum(1 for u in close if worth(u) >= env.nado_clump_medium_worth) >= 2:
                    nado["clump"] += 1
                if any(u.hp > 0 and tile_dist(u.x, u.y, tw.x, tw.y) >= d0 + 1.6 and worth(u) >= env.nado_retarget_min_worth
                       for u, tw, d0 in w["targeters"]):
                    nado["retarget"] += 1
            if age >= 3.5:
                nado["evaluated"] += 1
                if sum(1 for u in w["pulled"] if u.hp <= 0) >= 2:
                    nado["combo"] += 1
                if not w["pulled"]:
                    nado["pulled_nothing"] += 1
        return _orig()
    env._nado_shaping = _split
    gw = int(env.actions.gw); done = 0; plays = 0
    seen = set(); opp_plays = []                           # (t, class, key) of enemy bodies appearing
    casts = []                                             # one record per spell cast
    while done < matches:
        act, _ = sr.act(0)
        if act[0] == 1:
            plays += 1; ci = int(act[1]); cell = int(act[2]); key = env.deck_keys[ci]
            if ci in spell_ids:
                sp = env.specs[ci]; nx, ny = env.actions.cell_center(cell % gw, cell // gw)
                enemies = [u for u in env.eng.units if u.team == 1 and u.hp > 0]
                if key == "the_log":                       # rolls ~10 tiles toward the enemy (lower y)
                    hit = [u for u in enemies if abs(u.x - nx) * 18.0 <= 2.5 and -1.0 <= (ny - u.y) * 32.0 <= 10.0
                           and not getattr(u.spec, "flying", False)]
                elif key == "tornado":
                    hit = [u for u in enemies if tile_dist(nx, ny, u.x, u.y) <= float(getattr(sp, "pull_radius", 5.5))]
                else:
                    hit = [u for u in enemies if tile_dist(nx, ny, u.x, u.y) <= float(sp.spell_radius) + 0.5]
                dmg = float(getattr(sp, "spell_dmg", 0.0))
                killed = [u for u in hit if dmg > 0 and u.hp + float(getattr(u, "shield_left", 0.0)) <= dmg]
                prin = [t for t in env.eng.towers[1][:2] if t.alive]
                on_tower = any(tile_dist(nx, ny, t.x, t.y) <= float(env.spell_aim_radius) for t in prin)
                king0 = env.eng.towers[0][2]
                own_towers = set(id(t) for t in env.eng.towers[0])
                prev = [(c, k) for (t, c, k) in opp_plays if 0.0 <= env.eng.t - t <= W]
                rec = {"spell": key, "t": round(float(env.eng.t), 1), "zone": zone(ny), "n_hit": len(hit),
                       "hit": sorted(collections.Counter(cls(u) for u in hit).items()),
                       "hit_keys": sorted(collections.Counter(u.spec.key for u in hit).items())[:6],
                       "killed": len(killed),
                       "elixir_hit": round(sum(float(getattr(u.spec, "elixir", 0)) / max(1, int(getattr(u.spec, "count", 1))) for u in hit), 1),
                       "on_tower": bool(on_tower), "king_asleep": not bool(king0.active),
                       "near_own_king": bool(tile_dist(nx, ny, king0.x, king0.y) <= 6.0),
                       "pull_locked_on_tower": (any(id(getattr(u, "target", None)) in own_towers for u in hit)
                                               if key == "tornado" else None),
                       "prev_opp_classes": sorted({c for c, _ in prev}), "prev_opp_last": (prev[-1][1] if prev else None)}
                casts.append(rec)
        _o, _r, d, info = env.step(act)
        for u in env.eng.units:
            if u.team == 1 and id(u) not in seen:
                seen.add(id(u)); opp_plays.append((float(env.eng.t), cls(u), u.spec.key))
        if d:
            done += 1; env.reset(); seen.clear(); opp_plays.clear()
    led = env.rw_stats.run_summary()["terms"]
    t = lambda k: (led[k]["fires"], round(led[k]["total"], 2)) if k in led else (0, 0.0)
    return {"ckpt": str(ckpt), "matches": matches, "seed": seed, "plays": plays, "casts": casts,
            "ledger": {k: t(k) for k in ("spell_waste", "spell_defence", "nado", "nado_bad", "log_hits", "chip_offence")},
            "nado_split": dict(nado)}


def summarise(out):
    lines = []
    allc = [c for r in out for c in r["casts"]]
    for sp in ("the_log", "tornado", "rocket"):
        cs = [c for c in allc if c["spell"] == sp]; n = len(cs)
        lines.append(f"== {sp}: {n} casts over {sum(r['matches'] for r in out)} matches ({len(out)} seeds)")
        if not n:
            continue
        z = collections.Counter(c["zone"] for c in cs)
        lines.append("   zone: " + ", ".join(f"{k} {100*v/n:.0f}%" for k, v in z.most_common()))
        cov = collections.Counter("nothing" if c["n_hit"] == 0 and not c["on_tower"] else
                                  "tower only" if c["n_hit"] == 0 else
                                  "kills >=1 body" if c["killed"] else "chip only" for c in cs)
        lines.append("   covers at cast: " + ", ".join(f"{k} {100*v/n:.0f}%" for k, v in cov.most_common()))
        hc = collections.Counter(k for c in cs for k, v in c["hit"])
        lines.append("   body classes covered (share of casts): " + ", ".join(f"{k} {100*v/n:.0f}%" for k, v in hc.most_common()))
        hk = collections.Counter(k for c in cs for k, v in c["hit_keys"])
        lines.append("   top keys covered: " + ", ".join(f"{k} {v}" for k, v in hk.most_common(8)))
        pc = collections.Counter(k for c in cs for k in c["prev_opp_classes"]); none = sum(1 for c in cs if not c["prev_opp_classes"])
        lines.append("   opp play in prev 6 s (any): " + ", ".join(f"{k} {100*v/n:.0f}%" for k, v in pc.most_common()) + f", (nothing) {100*none/n:.0f}%")
        if sp == "tornado":
            lines.append(f"   king asleep at cast {100*sum(c['king_asleep'] for c in cs)/n:.0f}%; cast within 6 tiles of own king {100*sum(c['near_own_king'] for c in cs)/n:.0f}%; "
                         f"pulls a tower-locked unit {100*sum(bool(c['pull_locked_on_tower']) for c in cs)/n:.0f}%; >=2 bodies {100*sum(c['n_hit']>=2 for c in cs)/n:.0f}%")
        if sp == "rocket":
            lines.append(f"   on tower {100*sum(c['on_tower'] for c in cs)/n:.0f}%; elixir covered p50 {sorted(c['elixir_hit'] for c in cs)[n//2]}")
    led = collections.Counter()
    for r in out:
        for k, (f, tot) in r["ledger"].items():
            led[k] += f
    lines.append("   ledger fires (all seeds): " + ", ".join(f"{k} {v}" for k, v in led.items()))
    ns = collections.Counter()
    for r in out:
        ns.update(r["nado_split"])
    lines.append("   tornado split (probe-side, same predicates as sim): " + ", ".join(f"{k} {v}" for k, v in sorted(ns.items())))
    lines.append("   plays per seed: " + ", ".join(str(r["plays"]) for r in out) + "; casts per seed: " + ", ".join(str(len(r["casts"])) for r in out))
    return "\n".join(lines)


if __name__ == "__main__":
    ck = sys.argv[1]; n = int(sys.argv[2]); seeds = [int(s) for s in sys.argv[3].split(",")]
    out = []
    for s in seeds:
        t0 = time.time(); r = run(ck, n, s); r["wall_s"] = round(time.time() - t0, 1); out.append(r)
        print(f"seed {s}: plays {r['plays']} casts {len(r['casts'])} wall {r['wall_s']}s", flush=True)
    pathlib.Path(sys.argv[4]).write_text(json.dumps(out, indent=1))
    txt = summarise(out); print(txt); pathlib.Path(sys.argv[4]).with_suffix(".txt").write_text(txt)
