"""Spell usage + WHIFF probe (GAUNTLET L38).

Same rollout as continuation_report.py / L35's cardmix.py -- greedy Searcher, same SEEDS,
same match count -- so its plays ARE those reports' plays. MUST be run with PYTHONHASHSEED=0
(HANDOFF standing rule; real_run_gates.py:65 sets it for every gate report).

WHAT IT MEASURES, per spell cast by team 0 (us):
  * casts, casts/match, casts/min of match time
  * enemy UNITS damaged by that cast (unique bodies), total unit damage, tower damage
  * WHIFF = the cast damaged zero enemy units AND zero enemy towers.
Attribution is done on the engine, not on the reward: SimEngine._resolve_spell / _resolve_roll /
_tick_vortex / _tick_roll are wrapped so every _hurt / _damage_tower call that happens inside
them is credited to the cast that produced that roll/vortex. Nothing else can enter the count.
"""
import argparse, collections, pathlib, sys
import torch

ROOT = pathlib.Path(__file__).resolve().parents[3] / "icebow"
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "tools"))

from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
from clashrl.sim import rollout_search as RS
from clashrl.sim import engine as E
import continuation_report as CR

SPELL = ("the_log", "tornado", "rocket")

# THE SEARCH FORKS THE ENGINE. rollout_search.Searcher deepcopies (eng, opponent) at every
# search decision and plays candidate futures on the COPY -- and those copies cast spells too.
# Counting them inflated every number (7 log casts against 6 log plays on a 2-match smoke run,
# with one cast duplicated at the same t and the same damage). Only the live engine object is
# counted: `self is REAL["eng"]`, an IDENTITY test, which a deepcopy cannot satisfy.
REAL = {"eng": None}
RECS = []            # one dict per team-0 spell cast
OWNER = {}           # id(vortex|roll) -> rec
CUR = {"rec": None}


def _install():
    Eng = E.SimEngine
    if getattr(Eng, "_l38", False):
        return
    o_rs, o_roll, o_tv, o_tr = Eng._resolve_spell, Eng._resolve_roll, Eng._tick_vortex, Eng._tick_roll
    o_hurt, o_dt = Eng._hurt, Eng._damage_tower

    def rs(self, s):
        if s.team != 0 or self is not REAL["eng"]:
            return o_rs(self, s)
        rec = {"key": s.spec.key, "t": float(self.t), "units": set(), "dmg": 0.0, "tower": 0.0}
        RECS.append(rec)
        before = {id(x) for x in list(self.vortices) + list(self.rolls)}
        CUR["rec"] = rec
        try:
            return o_rs(self, s)
        finally:
            CUR["rec"] = None
            for x in list(self.vortices) + list(self.rolls):
                if id(x) not in before:
                    OWNER[id(x)] = rec

    def roll(self, s):
        r = o_roll(self, s)
        if CUR["rec"] is not None:
            OWNER[id(r)] = CUR["rec"]
        return r

    def tv(self, v, dt):
        if self is not REAL["eng"]:
            return o_tv(self, v, dt)
        prev, CUR["rec"] = CUR["rec"], OWNER.get(id(v))
        try:
            return o_tv(self, v, dt)
        finally:
            CUR["rec"] = prev

    def tr(self, r, dt):
        if self is not REAL["eng"]:
            return o_tr(self, r, dt)
        prev, CUR["rec"] = CUR["rec"], OWNER.get(id(r))
        try:
            return o_tr(self, r, dt)
        finally:
            CUR["rec"] = prev

    def hurt(self, u, dmg, hits_hidden=False, source=None):
        rec = CUR["rec"]
        if rec is not None and getattr(u, "team", 0) != 0 and dmg > 0.0:
            rec["units"].add(id(u)); rec["dmg"] += float(dmg)
        return o_hurt(self, u, dmg, hits_hidden, source)

    def dtw(self, tw, dmg, by_team):
        rec = CUR["rec"]
        if rec is not None and by_team == 0 and dmg > 0.0:
            rec["tower"] += float(dmg)
        return o_dt(self, tw, dmg, by_team)

    Eng._resolve_spell, Eng._resolve_roll = rs, roll
    Eng._tick_vortex, Eng._tick_roll = tv, tr
    Eng._hurt, Eng._damage_tower = hurt, dtw
    Eng._l38 = True


def run(ckpt, cfg, matches, offset=0):
    env = SimMatchEnv(cfg)
    net = RS.load_net(str(ckpt), env, torch.device("cpu"))
    sr = RS.Searcher(env, net, torch.device("cpu"), 12.0, 0, 4, 1.0, 0.25, cells=3)
    RECS.clear(); OWNER.clear()
    plays = collections.Counter()
    total_plays = 0
    outc = collections.Counter(); my_cr = op_cr = 0   # L41: outcome tally on the same rollout
    secs = 0.0
    for seed in CR.SEEDS[offset:offset + matches]:
        env.rng.seed(seed); env.reset(); REAL["eng"] = env.eng; done = False
        while not done:
            act, _ = sr.act(0)
            if act[0] == 1:
                plays[CR._base(env.deck_keys[act[1]])] += 1; total_plays += 1
            _o, _r, done, _i = env.step(act)
        secs += float(env.eng.t)
        outc[_i.get("outcome")] += 1; my_cr += _i["crowns"][0]; op_cr += _i["crowns"][1]
    mins = secs / 60.0
    print(f"  {ckpt.name}: {matches} matches (seed slice {offset}:{offset+matches}), {mins:.1f} min of match time, {total_plays} plays")
    by = collections.defaultdict(list)
    for r in RECS:
        by[r["key"]].append(r)
    print(f"  {'spell':<10}{'casts':>7}{'/match':>8}{'/min':>7}{'whiff':>8}{'bodies':>8}"
          f"{'unit dmg':>10}{'tower dmg':>11}")
    for k in SPELL:
        rs_ = [r for r in by if CR._base(r) == k]
        recs = [r for kk in rs_ for r in by[kk]]
        n = len(recs)
        if n == 0:
            print(f"  {k:<10}{0:>7}{0.0:>8.2f}{0.0:>7.2f}{'--':>8}{'--':>8}{'--':>10}{'--':>11}")
            continue
        whiff = sum(1 for r in recs if not r["units"] and r["tower"] <= 0.0)
        bodies = sum(len(r["units"]) for r in recs)
        print(f"  {k:<10}{n:>7}{n/matches:>8.2f}{n/mins:>7.2f}{100.0*whiff/n:>7.0f}%"
              f"{bodies/n:>8.2f}{sum(r['dmg'] for r in recs)/n:>10.0f}"
              f"{sum(r['tower'] for r in recs)/n:>11.0f}")
    sp = sum(plays[k] for k in SPELL)
    print(f"  OUTCOME  win {outc['win']}  loss {outc['loss']}  draw {matches-outc['win']-outc['loss']}  of {matches} (greedy, search-free)  crowns {my_cr}-{op_cr}")
    print(f"  SPELL share of plays: {100.0*sp/max(total_plays,1):.1f}%  "
          + "  ".join(f"{k} {100.0*plays[k]/max(total_plays,1):.1f}%" for k in SPELL))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", nargs="+", required=True)
    ap.add_argument("--matches", type=int, default=16)
    # DISJOINT SEED SLICE. CR.SEEDS is fixed, so re-running a checkpoint reproduces its numbers
    # exactly -- which measures nothing about sampling noise. --offset 16 runs the SAME policy on
    # 16 DIFFERENT matches, and the gap between the two reads is this instrument's noise band.
    ap.add_argument("--offset", type=int, default=0)
    a = ap.parse_args()
    _install()
    cfg = Config.load()
    for c in a.ckpt:
        run(pathlib.Path(c), cfg, a.matches, a.offset)
