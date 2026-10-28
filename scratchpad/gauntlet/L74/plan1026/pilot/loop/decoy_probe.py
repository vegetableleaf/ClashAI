"""LOOP-INT step 3 / LOOP-DECOY (GB-DECOY in the SIM): what production's crforge SIM path shows a policy during an evolved
Goblin Barrel cast, with barrel_decoy_sim off (CRFORGE_BARREL_DECOY_SIM unset = today) and on. Plays the same seeded
sequence of Goblin Barrels from side 0 (every third one evolved) through RoyaleSelfPlayEnv (the e1_eval / rl_royale env)
once per arm and checks, per tick:
  - entity rows (state()'s 'entities') identical in both arms (the mapping only labels the spell object);
  - arm off in flight: no barrel token (today's gap); arm on: the projectile tokens equal live's --barrel-decoy on tokens
    on the same situation (the reader frame live would read: both barrels under the Goblin Barrel card, the real one
    created first = the lower generation key; pipeline.barrel_decoy.objects), for the vocab given (B0's card_vocab when
    --ckpt is given, else {'goblin-barrel': 42}); exactly one barrel token, at the real barrel's landing;
  - plain casts: tokens identical in both arms.
usage (pod, run.sh's env incl. CRFORGE_FACADE_BUILD): python decoy_probe.py [--casts 6] [--seed 5] [--ckpt B0.pt] [--out J]
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[5])]

ap = argparse.ArgumentParser()
ap.add_argument("--casts", type=int, default=6)
ap.add_argument("--seed", type=int, default=5)
ap.add_argument("--ckpt", default=None, help="checkpoint whose card_vocab gives the gid (B0)")
ap.add_argument("--out", default=None)
a = ap.parse_args()
from pipeline.royale_env import RoyaleSelfPlayEnv, SCALE  # noqa: E402
from pipeline import projectile_observation as PO  # noqa: E402
from pipeline import barrel_decoy as B  # noqa: E402
from pipeline.projectile_motion import ProjectileMotion  # noqa: E402

GB_READER = 28000004                     # the reader's Goblin Barrel card id
if a.ckpt:
    import torch
    vocab = torch.load(a.ckpt, map_location="cpu", weights_only=False)["card_vocab"]
    GID = {k: i + 1 for i, k in enumerate(vocab)}          # membership is what matters (tokens_from_objects drops misses)
else:
    GID = {"goblin-barrel": 42}
print("gid has goblin-barrel", "goblin-barrel" in GID, "decoy key", B.DECOY_KEY in GID, flush=True)
d0 = ["GoblinBarrel@evolution", "BarbLog", "Fireball", "Minions", "Rascals", "MovingCannon", "Mortar", "Knight"]
d1 = ["BarbLog", "Fireball", "Minions", "Rascals", "MovingCannon", "Mortar", "Knight", "Goblins"]


def toks(mo, got, tick):
    return PO.tokens_from_objects(mo.update(got, tick), 1, GID)["projectiles"]   # side 1 sees side 0's barrels


def arm(flag):
    if flag:
        os.environ["CRFORGE_BARREL_DECOY_SIM"] = "1"
    else:
        os.environ.pop("CRFORGE_BARREL_DECOY_SIM", None)
    env = RoyaleSelfPlayEnv(decision_ticks=10, forms_mode="deck", hero_abilities=False, ability_features="base")
    env.reset(d0, d1, a.seed)
    spell_obj = {str(k): int(env.core._cf.spellObj.get(k)) for k in env.core._cf.spellObj.keySet()
                 if "GoblinBarrel" in str(k)}
    bi = [i for i, n in enumerate(env.decks[0]) if "GoblinBarrel" in str(n)][0]
    gb = env.ids["GoblinBarrel"]
    casts, tick, rec = 0, int(env.tick), []
    m_sim, m_live = ProjectileMotion(catalog_fallback=True), ProjectileMotion(catalog_fallback=True)
    while casts < a.casts and tick < 9000:
        r = env.act(side=0, deck_index=bi, x=3500, y=26000)    # Blue's barrel at Red's left princess tower
        if r.get("accepted"):
            casts += 1
            evo = json.loads(str(env.core._cf.state()))["players"][0].get("evo")
            for t in range(tick + 1, tick + 45):
                env.advance_to(t)
                st = env.core.state()
                js = json.loads(str(env.core._cf.state()))
                spells = [s for s in st.spells if s.card_id == gb and s.team == 0]
                shots = [p for p in st.projectiles if p.team == 0 and p.firer_card_id == -1]
                got = PO.objects(PO.sim_objects(st, env.names, SCALE), source="sim")
                ts = toks(m_sim, got, t)
                # live's reader frame of the same board: each barrel in flight (a spell row when the key is on), then its
                # mirrored tower shot (an evolved cast's decoy), created right after it
                lv = None
                if flag and spells:
                    rows, g = [], 5000
                    for s in spells:
                        for o in [s] + [p for p in shots if p.aim_x + s.aim_x == 324000 and p.aim_y == s.aim_y]:
                            rows.append(dict(side=o.team, x=o.x / SCALE, y=o.y / SCALE, card_id=GB_READER,
                                             target_x=o.aim_x / SCALE, target_y=o.aim_y / SCALE, generation_key=g))
                            g += 1
                        g += 10                                  # separate casts are not back-to-back objects
                    lv = toks(m_live, B.objects(dict(projectiles=rows, effects=[]), source="reader"), t)
                ts = ts[ts[:, 0] == GID["goblin-barrel"]]          # barrel tokens (other shots: the reader frame lacks them)
                lv = None if lv is None else lv[lv[:, 0] != 0]
                n = len(ts)
                rec.append(dict(cast=casts, t=t, evo=evo, n_tok=n, tok=ts.round(6).tolist(),
                                live_tok=None if lv is None else lv.round(6).tolist(),
                                live_eq=None if lv is None else bool(lv.shape == ts.shape and (lv == ts).all()),
                                spells=[(s.aim_x, s.aim_y) for s in spells], shots=[(p.aim_x, p.aim_y) for p in shots],
                                ents=js["entities"]))
            tick = int(env.tick)
        else:                                                    # cycle: any other card in hand at our own back
            for j in range(8):
                if j != bi and env.act(side=0, deck_index=j, x=9000, y=3000).get("accepted"):
                    break
            tick += 10
            env.advance_to(tick)
    return spell_obj, rec


so0, off = arm(False)
so1, on = arm(True)
print("spellObj GoblinBarrel* off", so0, "on", so1)
assert len(off) == len(on) and [r["t"] for r in off] == [r["t"] for r in on], "the arms diverged in cast timing"
ent_diff = [r["t"] for r, q in zip(off, on) if r["ents"] != q["ents"]]
summary = dict(ticks=len(on), entity_rows_differ_ticks=ent_diff, casts={})
for c in sorted({r["cast"] for r in on}):
    ro, rn = [r for r in off if r["cast"] == c], [r for r in on if r["cast"] == c]
    evo_flight = [r for r in rn if len(r["shots"]) >= 1 and r["spells"] and len(ro[rn.index(r)]["shots"]) >= 2]
    plain = not any(len(r["shots"]) >= 2 for r in ro)
    summary["casts"][c] = dict(
        plain=plain, evo=rn[0]["evo"],
        off_ticks_with_barrel_token=sum(r["n_tok"] > 0 for r in ro),
        on_ticks_with_barrel_token=sum(r["n_tok"] > 0 for r in rn),
        on_ticks_one_token=sum(r["n_tok"] == 1 for r in rn),
        on_ticks_two_plus=sum(r["n_tok"] >= 2 for r in rn),
        evo_flight_ticks=len(evo_flight),
        live_eq=f"{sum(bool(r['live_eq']) for r in rn if r['live_eq'] is not None)}/{sum(r['live_eq'] is not None for r in rn)}",
        plain_tokens_equal=plain and all(x["tok"] == y["tok"] for x, y in zip(ro, rn)),
        sample=next(({k: r[k] for k in ("t", "tok", "live_tok", "spells", "shots")} for r in evo_flight), None),
        live_mismatch=[{k: r[k] for k in ("t", "tok", "live_tok", "spells", "shots")} for r in rn if r["live_eq"] is False][:3])
print(json.dumps(summary, indent=1))
if a.out:
    Path(a.out).write_text(json.dumps(dict(summary=summary, spellObj_off=so0, spellObj_on=so1), indent=1))
print("DONE")
