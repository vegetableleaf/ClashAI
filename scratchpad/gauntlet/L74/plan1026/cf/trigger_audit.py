"""P3-FORK trigger audit: do cf_credit's trigger detectors fire where they should on real crforge matches?

    ROYALE_ENGINE=crforge ... python scratchpad/gauntlet/L74/plan1026/cf/trigger_audit.py --n 24 --out OUT.json

CLXIII (rollout sampler) vs CLXIII on census decks (sampling opponent), no forks: at EVERY learner decision the hook runs
cf_credit.triggers with every probability 1 and no gap, and an INDEPENDENT re-derivation of each condition straight from
the engine state in engine coordinates (no own-frame conversion, no cf_credit helper), then tallies agreement per
trigger: both / only_cf (false positive) / only_ref (miss). ``random`` is always on and not audited."""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO))

import numpy as np                                                         # noqa: E402

from pipeline import cf_credit as CF                                       # noqa: E402
from pipeline import e1_eval as E                                          # noqa: E402
from pipeline import search_s0 as S                                        # noqa: E402

TILE = 18000.0
REACH = 13.0384 + 1e-4            # decision_options.XBOW_REACH_TILES (the standard bridge cell sits at 13.0384)
CLXIII = "icebow/data/bench/rl_royale/rlarm_succ48_o_s91/rlarm_succ48_o_s91_u0075.pt"
BAIT = {"goblinbarrel", "skeletonarmy", "goblingang", "princess", "dartgoblin", "blowdartgoblin", "rascals",
        "minionhorde", "bats"}


def nm(x) -> str:
    return "".join(ch for ch in str(x).split("@")[0].lower() if ch.isalnum())


def ref_conditions(m, s, d, st_ref, c) -> set:
    """The trigger conditions from the engine state (engine units, Blue = side 0 at low y), written independently."""
    from royalegym.protocol import EntityKind as K
    env, side, tick = m.env, s.side, int(s._cur[0])
    es = env.core.state()
    names = {int(e.card_id): nm(env.names.get(e.card_id, "")) for e in es.entities}
    mine = [e for e in es.entities if int(e.team) == side and e.hp > 0 and e.kind in (K.KING_TOWER, K.PRINCESS_TOWER)]
    foe = [e for e in es.entities if int(e.team) != side and e.hp > 0 and e.kind in (K.KING_TOWER, K.PRINCESS_TOWER)]
    dist = (lambda a, b: math.hypot(a.x - b.x, a.y - b.y) / TILE)
    for e in es.entities:                                   # our X-Bows: reach at first sight, lock ever, death
        if int(e.team) == side and e.kind == K.BUILDING and e.hp > 0 and names[int(e.card_id)] == "xbow":
            w = st_ref["xb"].setdefault(int(e.uid), [any(dist(e, t) <= REACH for t in foe), False])
            w[1] = w[1] or getattr(e, "target_uid", None) in {t.uid for t in foe}
    alive = {int(e.uid) for e in es.entities if e.hp > 0}
    for u in [u for u in st_ref["xb"] if u not in alive]:
        r, lk = st_ref["xb"].pop(u)
        if r and not lk:
            st_ref["fail_tick"] = tick
    allowed = np.asarray(d["allowed"], bool)
    if d.get("forced") or not d.get("gate_sampled") or not allowed.any():
        return set()
    card = [nm(s.engine_deck[s.deck_index_of_slot[k]]) for k in range(len(allowed))]
    played = card[int(d["slot"])] if d["play"] else None
    out = set()
    if played == "rocket":
        out.add("rocket_played")
    if any(card[k] == "rocket" and allowed[k] for k in range(len(card))) and played != "rocket":
        out.add("rocket")
    half = (lambda y: y < 16 * TILE) if side == 0 else (lambda y: y > 16 * TILE)
    raw = env.raw()["entities"]                             # the board the learner saw (deploying bodies included)
    if any(int(e["side"]) != side and nm(e["name"]) in CF.WINCON and half(e["y"] * 18.0) for e in raw):
        out.add("wincon")
    mine_uid = {t.uid for t in mine}
    for e in es.entities:
        if int(e.team) != side and e.kind == K.BUILDING and e.hp > 0 and mine and (
                getattr(e, "target_uid", None) in mine_uid
                or (names[int(e.card_id)] in ("xbow", "mortar") and min(dist(e, t) for t in mine) <= REACH)):
            out.add("siege")
    if played == "xbow":
        X, Y = (18.0 * v for v in s.ep.cell_to_engine(int(d["cell"]), s.mirror, s.cfg["grid"]))   # 1000 -> 18000 / tile
        if any(math.hypot(X - t.x, Y - t.y) / TILE <= REACH for t in foe if t.hp > 0) and half(Y):
            out.add("xbow")
    if any(card[k] == "xbow" and allowed[k] for k in range(len(card))) and tick - st_ref["fail_tick"] <= 600:
        out.add("xbow_after_fail")
    if not d["play"] and es.players[side].elixir_milli / 1000.0 >= 9.9:
        out.add("idle_full")
    if played == "log" and any(nm(c) in BAIT for _, c in m.opp.accepted):
        out.add("log_bait")
    return out


class Audit(CF.Runner):
    def __init__(self, make_env, c):
        super().__init__(make_env, c)
        self.tab = defaultdict(Counter)
        self.examples = defaultdict(list)
        self.ref = {}

    def hook(self, live, todo):
        by = {id(m.learner): m for m in live}
        for s, p, d in todo:
            m = by.get(id(s))
            if m is None:
                continue
            if getattr(m, "cf_state", None) is None:
                m.cf_state = CF.new_state(s)
                self.ref[id(m)] = {"xb": {}, "fail_tick": -10 ** 9}
            got = set(CF.triggers(m, s, d, self.c)) - {"random"}
            want = ref_conditions(m, s, d, self.ref[id(m)], self.c)
            for t in CF.TRIGGERS[:-1]:
                key = ("both" if t in got and t in want else "only_cf" if t in got else "only_ref" if t in want
                       else None)
                if key:
                    self.tab[t][key] += 1
                    if key != "both" and len(self.examples[t]) < 5:
                        ex = {"tick": int(s._cur[0]), "side": s.side, "key": key}
                        if t == "xbow_after_fail":
                            r = self.ref[id(m)]
                            ex.update(cf_xb={str(k): v for k, v in m.cf_state["xb"].items()},
                                      cf_failed=m.cf_state["xb_failed"], cf_fail_tick=m.cf_state["xb_fail_tick"],
                                      ref_xb={str(k): v for k, v in r["xb"].items()}, ref_fail_tick=r["fail_tick"])
                        self.examples[t].append(ex)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--in-flight", type=int, default=4)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    from pipeline.rl_royale import league_decks
    from pipeline.royale_env import RoyaleSelfPlayEnv
    gen, gi = E.load_policy(REPO / CLXIII, "cpu")
    opp, oi = E.load_policy(REPO / CLXIII, "cpu")
    c = CF.cf_cfg({**CF.DEFAULTS, "cf_credit": True, "advantage": "gae", "gae_gamma_unit": "tick", "league": True,
                   "cf_gap_ticks": 0, "cf_p": {t: 1.0 for t in CF.TRIGGERS}})
    lcfg = {**S.live_cfg(0.35, gi["grid"]), "policy": "sample", "record": True, "record_tick": True, "T": 0.5,
            "T_gate": 0.3, "tau_phase": [0.35, 0.45, 0.55], "rollout_index": 0, "update": 0, "cf": c}
    ocfg = {**S.live_cfg(S.TAU_OPP, oi["grid"]), "policy": "sample", "T": 0.5}
    census = league_decks(REPO / "icebow/data/rltest/decks_rl.json")
    jobs = []
    for i in range(a.n):
        d = S.opp_deck_for(741200 + i, census)
        jobs.append((i, {"tag": f"trig{i}", "opp": {"id": "gen"}, "learner_deck": list(E.ICEBOW_ENGINE_DECK),
                         "opp_deck": list(d["engine"]), "learner_side": i % 2, "seed": 741200 + i}, 0))
    holder = {}

    def mk(make_env, cc):
        holder["r"] = Audit(make_env, cc)
        return holder["r"]
    import unittest.mock as um
    res = []
    with um.patch.object(CF, "Runner", mk):
        E.run_selfplay_batch(lambda: RoyaleSelfPlayEnv(decision_ticks=10, tail_cap=7200), gen, {"gen": (opp, ocfg)},
                             jobs, lcfg, a.in_flight, on_result=res.append, skip=(Exception,))
    r = holder["r"]
    out = {"matches": len(res), "table": {t: dict(v) for t, v in r.tab.items()},
           "examples": {t: v for t, v in r.examples.items()},
           "agree": {t: v["both"] / max(1, v["both"] + v["only_cf"] + v["only_ref"]) for t, v in r.tab.items()}}
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps(out["table"]), json.dumps(out["agree"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
