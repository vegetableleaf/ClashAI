"""Forked "same moment, two choices" test for ONE mechanic (L74 mechanic_fork; owner 2026-10-09).

    cd <worktree of the mechanic's branch>
    MECH=sneaky MECH_OUT=<dir> [MECH_CHECK=N] python scratchpad/gauntlet/L74/mechanic_fork/mech_fork.py <search_s0 args>

The search_s0 args are the benchmark's own (--arms plain, live checkpoint, gen opponent sampling at T .3, census, the
deployed decision flags).  Module-level patch of search_s0.Runner (spawned workers re-import this module first), no
tracked file changes: the match is played exactly as the plain arm plays it (same round order, same decide calls), and
at every OUR decision a PROBE copy of our side decides again with the mechanic switched on (``mech_cfg``).  The probe
is a deep copy, so its RNG draws and per-match state updates never reach the real match.

OPPORTUNITY (``trigger``) = the probe's decision is the mechanic's and differs from the model's own in the way the
mechanic means (sneaky: the probe's why is 'sneaky_lock'; patience: the model plays a card costing < 4 and the probe
waits).  Consecutive trigger decisions less than GAP ticks apart are ONE episode; only an episode's first decision is
forked.  There, after every side of the round has decided and before any applies, the full state is forked
(search_s0.fork_into: engine save_state + deep copies of both sides' python state, RNG generators included; global
random / numpy / torch RNG states saved and restored around every branch):
    A = the original match itself, continuing with the model's own decision (the instrument proves A == a replayed
        fork at MECH_CHECK opportunities per process: same engine-state hash at +10 s, +20 s and the end);
    B = a fork whose our-side decision this round is the probe's.  sneaky: that one Tornado, then the model as usual.
        patience: the wait is HELD -- our side decides with the patience gate on until the first decision where the gate
        no longer withholds a play the model would make (then the gate is off again).
Both branches then run to the match end with the real opponent (its own model, its own sampling RNG) and our own live
path.  Recorded per branch: crown-tower HP (ours / theirs), elixir, units alive, crowns at the first decision boundary
>= +10 s / +20 s, the end, the outcome; sneaky also the X-Bow's target at every boundary for 15 s (lock metric).
Engine truth is used only as the referee here; no model input changes."""
import copy
import hashlib
import json
import os
import random
import sys

sys.path.insert(0, os.getcwd())
import numpy as np  # noqa: E402

from pipeline import e1_eval as E  # noqa: E402
from pipeline import search_s0 as S  # noqa: E402
from pipeline.decision_options import match_kwargs as MK  # noqa: E402

MECH = os.environ.get("MECH", "sneaky")
CHECK = int(os.environ.get("MECH_CHECK", "0"))        # A-replay faithfulness forks per process
GAP = int(os.environ.get("MECH_GAP", "30"))           # ticks: triggers closer than this are one episode
H = (200, 400)                                         # +10 s, +20 s
OBS_TICKS = 300                                        # X-Bow target sampled for 15 s after the root
LOCK_WIN, LOCK_NEED, DELAY = 80, 40, 26                # owner's success: on a princess 2 s in a row, starting <= 4 s after landing
_CHECKS = [0]


def mech_cfg(cfg):
    if MECH == "sneaky":
        return {**cfg, "sneaky_lock": "on"}
    if MECH == "patience":
        return {**cfg, "patience": (4.0, 0.5)}
    if MECH == "combo":            # rocket_value2 variants.json "cb9" (branch a67f26ce f5ba591)
        return {**cfg, "rocket_value": 9.0, "rocket_tornado": "only", "rocket_value_mode": "damage",
                "rocket_value_hitbox": "edge"}
    if MECH == "rocket_tower":     # no decision option: the probe is rocket_tower_choice (the cfg is unchanged)
        return cfg
    raise ValueError(MECH)


REARM = int(os.environ.get("MECH_REARM", "200" if MECH == "rocket_tower" else "0"))   # > 0: a persisting trigger re-arms after this many ticks


def rocket_tower_choice(s, allowed):
    """Owner 2026-10-09 ("rocket an enemy tower to gain or maintain a damage lead in 2x and overtime"): 2x or overtime
    (decision_options.phase_index of the decision board's time >= 1), nothing pending, an affordable Rocket slot, an
    alive ENEMY PRINCESS. Tower = the lowest-HP alive enemy princess (lethal_rocket_target's order, any HP); never the
    king (tower doctrine; a lethal king is not handled here). Aim = lethal_rocket_cell (the princess centre).
    -> decision dict or None. Public: the decision board's time, my hand / elixir mask, the public crown towers."""
    from pipeline.decision_options import lethal_rocket_cell, phase_index
    from pipeline.obs_contract import _engine_xy
    bs = s._cur[1]
    if getattr(s, "pending", None) is not None or phase_index([float(bs.t_sec)])[0] < 1:
        return None
    slots = [i for i, n in enumerate(s.deck.cards) if n is not None and str(n).lower() == "rocket" and allowed[i]]
    if not slots:
        return None
    crown = ((s.state or {}).get("episode") or {}).get("crown_towers", [])
    best = None
    for t in crown:
        if int(t["side"]) == s.side or t.get("type") != "princess" or t.get("destroyed") or not t["hp"] > 0:
            continue
        x, _ = _engine_xy(float(t["x"]), float(t["y"]), s.side == 1)
        if best is None or t["hp"] < best[1]:
            best = ("L" if x < .5 else "R", int(t["hp"]))
    if best is None:
        return None
    return {"play": True, "slot": slots[0], "cell": int(lethal_rocket_cell(best[0], s.cfg["grid"])),
            "why": "rocket_tower", "lane": best[0], "tower_hp": best[1]}


def card(side, slot):
    return str(side.deck.cards[slot]).split("@")[0].lower() if slot is not None and slot >= 0 else None


def trigger(side, dA, dB):
    if MECH == "sneaky":
        return dB.get("why") == "sneaky_lock"
    if MECH == "combo":
        return dB.get("why") == "rocket_tornado"
    if MECH == "rocket_tower":     # the deployed lethal rules already Rocket that moment: not an opportunity
        return dB.get("why") == "rocket_tower" and not str(dA.get("why")).startswith("lethal")
    return (dA["play"] and dA["why"] not in ("stall", "lethal_rocket", "lethal_log") and side.costs[dA["slot"]] < 4
            and not dB["play"])


def same(a, b):
    return a["play"] == b["play"] and (not a["play"] or (a["slot"] == b["slot"] and a["cell"] == b["cell"]
                                                         and bool(a.get("follow_ups")) == bool(b.get("follow_ups"))))


# ------------------------------------------------------------------------------------------------------------------
def side_copy(s, cfg):
    c = object.__new__(type(s))
    c.__dict__.update({k: (v if k in S.SHARED_SIDE else copy.deepcopy(v)) for k, v in s.__dict__.items()})
    c.cfg = cfg
    return c


def decide(m, s, p, enc, heads, allowed, stalled):
    """Runner.round's per-side decision for the plain arm (bit-identical call)."""
    if s is not m.learner and s.cfg.get("policy") == "sample":
        return E.sample_decide_batch(s.model, enc, heads, [p], allowed[None], np.array([stalled]), [s], s.cfg)[0]
    return E.live_decide_batch(s.model, enc, heads, [p], allowed[None], np.array([stalled]), tau=s.cfg["tau"],
                               device=s.cfg["device"], **MK([s]))[0]


def decide_round(m, ds, probe_cfg=None):
    """Prepare all, decide each (Runner.round order). -> (todo [[side, p, d]], ctx of our side or None)."""
    for s in ds:
        s.prepare()
    todo, ctx = [], None
    for s in ds:
        p, enc, heads, hand = S.forward(s)
        _, allowed, stalled = s.pre(hand)
        probe = None
        if s is m.learner and probe_cfg is not None and MECH == "rocket_tower":
            probe = rocket_tower_choice(s, allowed) or {"play": False, "slot": -1, "cell": -1, "why": "none"}
        elif s is m.learner and probe_cfg is not None:    # before the real decide mutates per-match state
            c = side_copy(s, probe_cfg)
            probe = decide(m, c, p, enc, heads, allowed, stalled)
        d = decide(m, s, p, enc, heads, allowed, stalled)
        if s is m.learner:
            ctx = {"p": float(p), "d": d, "probe": probe, "tick": int(s._cur[0])}
        todo.append([s, p, d])
    return todo, ctx


def snap(m):
    from royalegym.protocol import EMPTY_CARD, EntityKind
    import msgspec
    st = m.env.core.state()
    L = m.learner.side
    unit = (EntityKind.TROOP, EntityKind.BUILDING)

    def units(t):
        return sum(1 for e in st.entities if e.team == t and e.hp > 0 and e.kind in unit and e.card_id != EMPTY_CARD)
    return {"tick": int(st.tick), "hp_us": S.tower_hp(st, L), "hp_them": S.tower_hp(st, 1 - L),
            "el_us": st.players[L].elixir_milli / 1000.0, "el_them": st.players[1 - L].elixir_milli / 1000.0,
            "u_us": units(L), "u_them": units(1 - L), "cr_us": int(st.players[L].crowns),
            "cr_them": int(st.players[1 - L].crowns), "over": bool(m.env.done),
            "h": hashlib.sha1(msgspec.json.encode(st)).hexdigest()[:16]}


def root_blockers(m):
    """Engine uids of the enemy ground troops inside my X-Bow's reach at the root (12.1 tiles + their radius, as
    sneaky_lock.ScenarioProbe): the bodies the Tornado has to pull out."""
    import math
    from royalegym.protocol import EntityKind
    st = m.env.core.state()
    L = m.learner.side
    xid = m.env.ids.get("Xbow")
    out = set()
    for xb in (e for e in st.entities if e.team == L and e.card_id == xid and e.kind == EntityKind.BUILDING and e.hp > 0):
        for e in st.entities:
            if e.team != L and e.kind == EntityKind.TROOP and e.hp > 0 and not e.flying and                     math.hypot(e.x - xb.x, e.y - xb.y) / 18000.0 <= 12.1 + e.radius / 18000.0:
                out.add(e.uid)
    return out


def xbow_on_princess(m, blockers=()):
    """(an X-Bow of mine stands, its target is an enemy PRINCESS tower, a root blocker is still alive)."""
    from royalegym.protocol import EntityKind
    st = m.env.core.state()
    L = m.learner.side
    xid = m.env.ids.get("Xbow")
    xbs = [e for e in st.entities if e.team == L and e.card_id == xid and e.kind == EntityKind.BUILDING and e.hp > 0]
    pr = {e.uid for e in st.entities if e.team != L and e.kind == EntityKind.PRINCESS_TOWER and e.hp > 0}
    alive = any(e.uid in blockers and e.hp > 0 for e in st.entities)
    return bool(xbs), any(e.target_uid in pr for e in xbs), alive


class Track:
    """Per-branch bookkeeping from the root tick t0: snapshots at +10 / +20 s, X-Bow samples."""

    def __init__(self, t0, blockers=()):
        self.t0, self.caps, self.xb, self.blockers = t0, {h: None for h in H}, [], set(blockers)

    def boundary(self, m, t, over):
        for h in H:
            if self.caps[h] is None and (t >= self.t0 + h or over):
                self.caps[h] = snap(m)
        if MECH == "sneaky" and t <= self.t0 + OBS_TICKS:
            self.xb.append((t,) + xbow_on_princess(m, self.blockers))

    def lock(self):
        """Owner's success: from landing (t0 + 26) to +4 s a run of on-princess samples spanning >= 2 s starts."""
        land, runs, r0, last = self.t0 + DELAY, [], None, None
        for t, _, on, _a in self.xb:
            if on:
                r0 = t if r0 is None else r0
                last = t
            elif r0 is not None:
                runs.append((r0, last))
                r0 = None
        if r0 is not None:
            runs.append((r0, last))
        # a run already on the tower before landing counts from the landing (ScenarioProbe.lock_after_cast)
        return any(max(a, land) <= land + LOCK_WIN and b - max(a, land) >= LOCK_NEED for a, b in runs)

    def out(self, m):
        o, cr = m.env.outcome(m.learner.side)
        r = {"10": self.caps[200], "20": self.caps[400], "end": snap(m), "outcome": o}
        rp = next((p for p in m.learner.plays if p.get("tick") == self.t0), None)   # our play decided at the root
        r["root_play"] = None if rp is None else {k: rp.get(k) for k in ("card", "accepted", "reason")}
        if MECH == "sneaky":
            r["lock"] = self.lock()
            land = self.t0 + DELAY
            r["xb_on_any"] = any(on for t, _, on, _a in self.xb if t >= land)
            # the pull worked: the X-Bow is on a princess while a root blocker still lives, within 4 s of landing
            r["lock_live"] = any(on and a for t, _, on, a in self.xb if land <= t <= land + LOCK_WIN)
            on_t = [t for t, _, on, _a in self.xb if on and t >= land]
            r["first_on"] = (on_t[0] - self.t0) if on_t else None
            r["n_blockers"] = len(self.blockers)
        return r


def run_branch(m, todo, d_ours, blob, t0, pool_env, hold, blockers=()):
    """Fork ``m`` (post-decide, pre-apply), apply this round with our decision ``d_ours``, run to the end."""
    G = (random.getstate(), np.random.get_state(), _torch_state())
    f = S.fork_into(m, pool_env, blob)
    tel = getattr(m.env, "behaviour_telemetry", None)
    if tel is not None:                               # same stepping granularity as the original (one tick per step)
        pool_env.behaviour_telemetry = copy.deepcopy(tel)
    mp = {id(m.learner): f.learner, id(m.opp): f.opp}
    cfg_off = f.learner.cfg
    held = 0
    for s, p, d in todo:
        mp[id(s)].apply(p, d_ours if s is m.learner else d)
    if hold:
        f.learner.cfg = mech_cfg(cfg_off)
    tr = Track(t0, blockers)
    while True:
        ds = f.due()
        tr.boundary(f, int(f.env.tick), not ds)
        if not ds:
            break
        holding = hold and f.learner.cfg is not cfg_off
        todo2, ctx = decide_round(f, ds, cfg_off if holding else None)
        if holding and ctx is not None:
            if ctx["probe"]["play"] and not ctx["d"]["play"]:
                held += 1                             # the gate still withholds a play the model would make
            else:
                f.learner.cfg = cfg_off               # released: this decision is the model's own (gate off)
                for row in todo2:
                    if row[0] is f.learner:
                        row[2] = ctx["probe"]
        for s, p, d in todo2:
            s.apply(p, d)
    r = tr.out(f)
    if hold:
        r["held_decisions"] = held
    random.setstate(G[0]), np.random.set_state(G[1]), _torch_set(G[2])
    return r


def _torch_state():
    import torch
    return torch.get_rng_state()


def _torch_set(s):
    import torch
    torch.set_rng_state(s)


# ------------------------------------------------------------------------------------------------------------------
_orig_play = S.Runner.play


def mech_round(self, m, ds, arm, st, rng):
    mm = m._mech
    for o in mm["open"]:
        o["track"].boundary(m, int(m.env.tick), False)
    todo, ctx = decide_round(m, ds, mm["cfg_on"])
    if ctx is not None and ctx["probe"] is not None and trigger(m.learner, ctx["d"], ctx["probe"]):
        mm["triggers"] += 1
        t = ctx["tick"]
        new = mm["last"] is None or t - mm["last"] > GAP
        rearm = not new and REARM > 0 and t - mm["start"] >= REARM
        mm["last"] = t
        if new or rearm:
            mm["start"] = t
            self._mech_fork(m, todo, ctx, first=new)
    for s, p, d in todo:
        s.apply(p, d)


def push_value(m):
    """Referee only (engine truth, never a model input): the elixir value of the enemy bodies standing on OUR half,
    each body at catalogue elixir / count (search_s0.Scorer's per-body price). Engine frame: team 0 owns y < 288000."""
    from royalegym.protocol import EMPTY_CARD, EntityKind
    st = m.env.core.state()
    L = m.learner.side
    cards = {c.card_id: c for c in m.env.core.cards()}
    v = 0.0
    for e in st.entities:
        if e.team == L or e.hp <= 0 or e.kind not in (EntityKind.TROOP, EntityKind.BUILDING) or e.card_id == EMPTY_CARD:
            continue
        if (e.y < 288000) == (L == 0):
            c = cards.get(e.card_id)
            v += 0.0 if c is None else float(c.elixir) / max(1, int(c.count))
    return v


def mech_fork(self, m, todo, ctx, first=True):
    dA, dB, t0 = ctx["d"], ctx["probe"], ctx["tick"]
    L = m.learner
    bs = L._cur[1]
    rec = {"t0": t0, "first": bool(first), "p": round(ctx["p"], 4), "elixir": float(bs.my_elixir), "t_sec": float(bs.t_sec),
           "A": {k: dA.get(k) for k in ("play", "slot", "cell", "why")}, "A_card": card(L, dA["slot"] if dA["play"] else -1),
           "B": {k: dB.get(k) for k in ("play", "slot", "cell", "why")}, "B_card": card(L, dB["slot"] if dB["play"] else -1),
           "same": same(dA, dB), "n_done0": len(L.done_plays)}
    if MECH == "sneaky":
        try:
            from pipeline.sneaky_lock import sneaky_lock_plan
            pl = sneaky_lock_plan(bs, L.cfg["grid"])
            rec["plan"] = None if pl is None else {k: pl[k] for k in ("blocker", "d_xbow", "margin", "king_touch")}
        except Exception as ex:                       # noqa: BLE001 -- bookkeeping only
            rec["plan"] = repr(ex)
    if MECH == "patience":
        from pipeline.decision_options import enemy_near_tower
        rec["near8"] = bool(enemy_near_tower(bs, 8.0))          # --patience-exempt 8 would NOT hold this one
    if MECH == "rocket_tower":
        r0 = snap(m)
        rec.update(lane=dB.get("lane"), tower_hp=dB.get("tower_hp"), push_val=round(push_value(m), 2),
                   tau_threat=bool(getattr(L, "tau_threat", False)), hazard_threat=bool(getattr(L, "threatened", False)),
                   cr_us=r0["cr_us"], cr_them=r0["cr_them"], hp_us0=r0["hp_us"], hp_them0=r0["hp_them"])
        dB = {k: dB[k] for k in ("play", "slot", "cell", "why")}
    blk = root_blockers(m) if MECH == "sneaky" else ()
    blob = m.env.core.save_state()
    envs = self._pool(1)
    if not rec["same"]:
        rec["Bres"] = run_branch(m, todo, dB, blob, t0, envs[0], hold=(MECH == "patience"), blockers=blk)
    if _CHECKS[0] < CHECK:
        _CHECKS[0] += 1
        rec["Acheck"] = run_branch(m, todo, dA, blob, t0, envs[0], hold=False, blockers=blk)
    m._mech["open"].append({"rec": rec, "track": Track(t0, blk)})


def mech_play(self, arm, m, deadline=None):
    cfg = m.learner.cfg
    m._mech = {"cfg_on": mech_cfg(cfg), "triggers": 0, "last": None, "start": None, "open": []}
    out = _orig_play(self, arm, m, deadline)
    recs = []
    for o in m._mech["open"]:
        o["track"].boundary(m, int(m.env.tick), True)
        r = o["rec"]
        r["Ares"] = o["track"].out(m)
        if MECH == "sneaky":       # did the model play a Tornado itself within 2 s of the root (landing <= t0 + 66)?
            r["A_tornado_2s"] = any(card(m.learner, s) == "tornado" and r["t0"] <= land <= r["t0"] + 40 + DELAY
                                    for land, s, _, _ in m.learner.done_plays[r["n_done0"]:])
        recs.append(r)
    out["mech"] = _plain({"name": MECH, "trigger_decisions": m._mech["triggers"], "episodes": len(recs), "opps": recs})
    return out


def _plain(x):
    """JSON-safe (numpy scalars -> python)."""
    return json.loads(json.dumps(x, default=lambda o: o.item() if hasattr(o, "item") else str(o)))


S.Runner.play, S.Runner.round, S.Runner._mech_fork = mech_play, mech_round, mech_fork

if __name__ == "__main__":
    sys.exit(S.main(sys.argv[1:]))
