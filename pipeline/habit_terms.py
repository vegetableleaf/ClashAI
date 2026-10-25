"""L74 exploit (owner 2026-10-23): OPT-IN habit reward terms for rl_royale. The unleashed drift tests (exploit/drift_test.sh,
drift_check.py on board-recorded E4 evals) show the policy's habits wandering where the SIM's win / loss barely pays: idling
under threats, over-defending. These terms make those habits matter in training (a LEARNED fix, no hand rule).

    habit_reward: on       the switch (gae + league only; absent / null / false = off: no tracker, the same rows, behaviour and
                           config hash). Then, each with its default when absent, 0 = that term off (tracker still runs):
    habit_idle_w   0.1     -w per THREAT (lane enemy value on our half >= 5 elixir for > 3 s) left unanswered >= 4 s while we
                           could afford a play (ape_score's 'idle' kind), on the kept row nearest the 4 s mark; |sum| <= 0.3.
    habit_trade_w  0.01    per enemy PUSH (troops crossing onto our half, grouped until it is clear, >= 3 elixir):
                           +w x clip(push value - our elixir played on our half during it, -5, 0) on the last kept row at or
                           (10-23 lead: PENALTY ONLY -- an unanswered push would otherwise earn + its value with no tower term on)
                           before the push end; summed |reward| <= 0.3 per match.
    (no hazard term: training rollouts never route a learner play through the hazard decoder -- e1_eval.sample_decide_batch
    labels plays gate / stall only; decision_options.decide_batch, the one source of why='hazard', runs only under policy live.)

The definitions ARE the drift metrics: scratchpad/gauntlet/L74/ape/ape_score.py ``score`` (sections 1 and 4), ``hab_match``
and ``sim_value(..., top=)`` (10-23 PUSH_CAL H1 rule), ported here because pipeline code never imports scratchpad/. Samples
follow search_s0 --record-board: the learner's decision stops >= HAB_EVERY ticks apart, the raw board of that stop and the
elixir its decision saw (truth + extrapolate regen). One deliberate difference: a played card's elixir is
opp_elixir_count.card_cost (ape_score's COST table + 3 for any other card: identical on the icebow deck).

HabitTracker (actor side, e1_eval.SelfPlayMatch ``habit_track``): read-only, never touches the engine. row_terms (learner
side, pure): the record + the kept rows' decision ticks -> per-row reward; rl_royale.collate adds it to r_step and the
critic becomes the residual one at shaping_critic_scale, which must cover 1 + ``bound``.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np

REPO = Path(__file__).resolve().parents[1]
TRAITS_PATH = REPO / "research/ext/Royale/RoyaleSim/data/derived/cards-160402017-20261006.json"   # = log_use.SIMCARDS

DEFAULTS = {"habit_idle_w": 0.1,      # per idle threat (win = +1): ~ a third of a typical tower-term event
            "habit_trade_w": 0.01,    # per elixir of push value - our spend (5 over-paid = -0.05). 10-23 scale check: at 0.03
#                                       the 0.3 cap bound in 35% of 128 rollout matches (median 18 elixir of |trade|), and
#                                       ignoring a 6-elixir threat paid idle -0.1 + trade +0.15 > 0; at 0.01 it costs -0.05
            "habit_leak_w": 0.0,      # succ48 10-23: per elixir WASTED (regenerated while at full); 0 = off (no hash change)
            "habit_xbow_w": 0.0}      # succ48 10-25: per FAILED reach X-Bow (no princess -5% in 30 s); 0 = off (no hash change)
KEYS = ("habit_reward",) + tuple(DEFAULTS)
IDLE_MATCH_CAP = TRADE_MATCH_CAP = 0.3   # summed |reward| per match and term (ponytail: fixed)
LEAK_MATCH_CAP = 1.0                      # succ48 10-24 0.6, 10-25 1.0: a leaky match must still feel the (stronger) leak term
FULL_E = 9.95                             # elixir counted as full (the cap is 10; the drift metric uses >= 9.9)
XBOW_MATCH_CAP = 0.3                      # summed |reward| per match of the failed-X-Bow term
XB_REACH, XB_LOCK, XB_WINDOW = 13.5, 0.05, 600   # tiles (INVESTMENT lock reach), share of princess max HP, ticks (30 s;
#                                         ponytail: a fixed window, not the X-Bow's life) -- = succ48/xbow_count.py
TRADE_CLIP_E = 5.0                        # elixir: one push's trade is clipped to [-this, 0] (over-paying only)

# ape_score.py (the drift metrics) -- keep in step with it
THREAT, CLEAR = 5.0, 2.5                  # threat episode: lane enemy value on our half >= 5, ends when < 2.5
ANSWER_T, IDLE_T, GRACE = 60, 80, 20      # answered within 3 s, idle >= 4 s, a play up to 1 s before onset counts
PUSH_WIN, PUSH_CAP, PUSH_MIN, HP_GRACE = 120, 400, 3.0, 40
SIM_MC = 2                                # 'could afford': the Log's cost stands in for the cheapest card (hab_match)
HAB_EVERY = 20                            # search_s0 HAB_EVERY: the board sample spacing (ticks)
CHILD_VALUE = 1 / 3                       # log_use.CHILD_VALUE
BODY_COUNT = {'goblin_barrel': 3, 'skeleton_barrel': 8, 'goblin_gang': 6, 'skeleton_army': 15, 'goblins': 4,   # log_use
              'spear_goblins': 3, 'wall_breakers': 2, 'rascals': 3, 'guards': 3, 'skeletons': 3, 'barbarians': 5,
              'minion_horde': 6, 'royal_recruits': 6, 'royal_hogs': 4, 'elite_barbarians': 2, 'bats': 5, 'minions': 3}


# ------------------------------------------------------------------------------------------------------------ config
def habit_cfg(cfg: dict) -> Optional[dict]:
    """The habit keys of a config, validated (SystemExit naming the bad key): None when ``habit_reward`` is absent / null /
    false (the weight keys must then be unset), else {weight key: float} with the defaults."""
    off = (lambda v: v is None or v is False)
    num = (lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v))
    stray = sorted(k for k in cfg if k.startswith("habit_") and k not in KEYS)
    if stray:
        raise SystemExit(f"bad habit config: unknown key(s) {stray}; keys {list(KEYS)} (there is no hazard term: training "
                         f"rollouts never fire the hazard decoder)")
    if off(cfg.get("habit_reward")):
        bad = [k for k in DEFAULTS if cfg.get(k) is not None]
        if bad:
            raise SystemExit(f"bad habit config: {bad} set without habit_reward on")
        return None
    p = {k: (v if cfg.get(k) is None else cfg[k]) for k, v in DEFAULTS.items()}
    bad = [] if cfg["habit_reward"] is True else [f"habit_reward must be on / off (a bool), got {cfg['habit_reward']!r}"]
    bad += [f"{k} must be a finite number >= 0, got {v!r}" for k, v in p.items() if not (num(v) and v >= 0)]
    if cfg.get("advantage", "match_loo") != "gae":
        bad.append(f"habit terms need advantage gae (refusing {cfg.get('advantage', 'match_loo')!r})")
    if not cfg.get("league"):
        bad.append("habit terms need league true (the tracker rides on self-play matches)")
    if not TRAITS_PATH.is_file():
        bad.append(f"habit terms need the card table {TRAITS_PATH} (the drift metrics' body values)")
    if bad:
        raise SystemExit("bad habit config: " + "; ".join(bad))
    return {k: float(v) for k, v in p.items()}


def bound(p: dict) -> float:
    """max |summed reward| per match (any suffix of it too: each term caps the sum of |reward|)."""
    return (IDLE_MATCH_CAP * (p["habit_idle_w"] > 0) + TRADE_MATCH_CAP * (p["habit_trade_w"] > 0)
            + LEAK_MATCH_CAP * (p.get("habit_leak_w", 0.0) > 0) + XBOW_MATCH_CAP * (p.get("habit_xbow_w", 0.0) > 0))


def canonical(cfg: dict) -> dict:
    """rl_royale.config_sha's input: off = the keys dropped (the historical hash), on = defaults filled (one hash for
    implicit / explicit)."""
    if cfg.get("habit_reward") is None or cfg.get("habit_reward") is False:
        return {k: v for k, v in cfg.items() if k not in KEYS}
    c = {**cfg, "habit_reward": True, **{k: float(v if cfg.get(k) is None else cfg[k]) for k, v in DEFAULTS.items()}}
    return {k: v for k, v in c.items() if k not in ("habit_leak_w", "habit_xbow_w") or v}   # 0 = off = the pre-key hash


# ------------------------------------------------------------------------------------------------------------ values
@lru_cache(maxsize=1)
def _traits() -> dict:
    """card key -> (kind, elixir) from the RoyaleSim card table log_use reads (log_use.sim_traits)."""
    from pipeline import vocab
    cards = json.loads(TRAITS_PATH.read_text(encoding="utf-8"))["cards"]
    return {vocab.engine_key(c["name"]): (c.get("kind"), c.get("elixir") or 0) for c in cards}


@lru_cache(maxsize=None)
def _card(name: str) -> tuple:
    """engine body name (its OWNER card) -> (key, kind, cost): ape_score.sim_value's lookups."""
    from pipeline import vocab
    from pipeline.opp_elixir_count import card_cost
    k = vocab.engine_key(name) or ""
    kind, el = _traits().get(k, (None, 0))
    return k, kind, card_cost(k) or el or 3.0


def body_value(name: str, hp: float, max_hp: float, top: dict) -> Optional[float]:
    """ape_score.sim_value(name, hp, max_hp, top=top): hp-scaled elixir of an enemy body; None for towers / buildings /
    placeholders (max_hp < 20). Role children (max_hp < 45% of the card's biggest body this match) and spell bodies not in
    BODY_COUNT are worth CHILD_VALUE, else card cost / BODY_COUNT."""
    k, kind, cost = _card(name)
    if "tower" in k or max_hp < 20 or kind == "building":
        return None
    child = max_hp < .45 * top.get(k, max_hp) or (kind == "spell" and k not in BODY_COUNT)
    return (CHILD_VALUE if child else cost / BODY_COUNT.get(k, 1)) * max(0, hp) / max(1, max_hp)


def play_cost(card: str) -> float:
    from pipeline.opp_elixir_count import card_cost
    return card_cost(str(card).replace("-", "_").lower().replace("_evo", "")) or 3.0


def own(x: float, y: float, low: bool) -> tuple:
    """engine millitiles -> (own-frame x tiles 0..18, own-frame y 0..1 with own edge 1): hab_match's ``own``."""
    x, y = (x / 1000, y / 1000) if max(abs(x), abs(y)) > 100 else (x, y)
    return (x, 1 - y / 32) if low else (18 - x, y / 32)


# ------------------------------------------------------------------------------------------------------------ events
def events(samples: list, plays: list, low: bool, towers: Optional[list] = None) -> dict:
    """ape_score.score sections 1 (threats) and 4 (pushes) on hab_match's inputs. ``samples`` [(tick, own elixir, enemy
    bodies [(uid, name, hp, max_hp, x, y)] engine millitiles)] in time order; ``plays`` our ACCEPTED plays [(decision tick,
    card, engine X, engine Y)] in order; ``low`` = our king at engine y < 16000. -> {"thr": threats, "idle": [[onset tick,
    lane]], "push": [[t0, t1, value, our spend]]} (plain JSON types)."""
    out = {"thr": 0, "idle": [], "push": [], "leak": [], "xbow": []}
    if not samples:
        return out
    for t0, card, X, Y in plays if towers else ():            # 6 X-BOW: reach X-Bows and whether they locked (xbow_count.py)
        if "bow" not in str(card).lower().replace("-", ""):
            continue
        px, py = (X / 1000, Y / 1000) if max(abs(X), abs(Y)) > 100 else (X, Y)
        before = [tw for t, tw in towers if t <= t0]
        if not before:
            continue
        near = [(x, y, hp) for x, y, hp in before[-1] if hp > 0 and math.hypot(px - x, py - y) <= XB_REACH]
        if not near:
            continue
        top = {(x, y): max(hp for t, tw in towers for x2, y2, hp in tw if (x2, y2) == (x, y)) for x, y, _ in near}
        later = [tw for t, tw in towers if t0 < t <= t0 + XB_WINDOW]
        locked = any(hp0 - min([hp for tw in later for x2, y2, hp in tw if (x2, y2) == (x, y)] or [hp0]) >= XB_LOCK * top[(x, y)]
                     for x, y, hp0 in near)
        out["xbow"].append([int(t0), int(not locked)])
    from pipeline.opp_elixir_count import regen_between      # 5 LEAK: elixir regenerated while full at both ends of a gap
    for (ta, ea, _), (tb, eb, _) in zip(samples, samples[1:]):   # (ponytail: misses the first gap of each full spell)
        if ea >= FULL_E and eb >= FULL_E:
            out["leak"].append([int(tb), round(regen_between(ta, tb), 4)])
    top = {}
    for _, _, en in samples:
        for _, name, _, mx, _, _ in en:
            k = _card(name)[0]
            top[k] = max(top.get(k, 0), mx)
    S = []
    for t, el, en in samples:
        vh, on = [0.0, 0.0], {}
        for uid, name, hp, mx, x, y in en:
            v = body_value(name, hp, mx, top)
            if v is None:
                continue
            ox, oy = own(x, y, low)
            if oy > .5:
                vh[int(ox >= 9)] += v
                on[uid] = v
        S.append((t, vh, el, on))
    P = []
    for t, card, X, Y in plays:
        _, oy = own(X, Y, low)
        P.append((t, oy, card))
    last = S[-1][0]
    for lane in (0, 1):                                       # 1 THREAT: only the idle kind is a reward event
        t0 = None
        for t, vh, _, _ in S + [(10 ** 9, [0.0, 0.0], 0.0, {})]:
            if t0 is None and vh[lane] >= THREAT:
                t0 = t
            elif t0 is not None and vh[lane] < CLEAR:
                start, t0 = t0, None
                if min(t, last) - start <= ANSWER_T:
                    continue                                  # gone within 3 s: not a threat
                out["thr"] += 1
                first = next((q for q in P if q[0] >= start - GRACE), None)
                if first and first[0] <= start + ANSWER_T:
                    continue                                  # answered (or the wrong lane): not idle
                if (not first or first[0] > start + IDLE_T) and any(
                        s[2] >= SIM_MC for s in S if start <= s[0] <= start + IDLE_T):
                    out["idle"].append([int(start), lane])
    seen, cross = set(), []                                   # 4 PUSH: crossings grouped until our half is clear
    for t, _, _, on in S:
        for k, v in on.items():
            if k not in seen:
                seen.add(k)
                cross.append((t, v))
    i = 0
    while i < len(cross):
        t0 = cross[i][0]
        t1 = min(next((s[0] for s in S if s[0] >= t0 + PUSH_WIN and sum(s[1]) < .5), last), t0 + PUSH_CAP)
        val = 0.0
        while i < len(cross) and cross[i][0] <= t1:
            val += cross[i][1]
            i += 1
        if val < PUSH_MIN:
            continue
        spend = sum(play_cost(c) for t, y, c in P if t0 - HP_GRACE <= t <= t1 and y > .5)
        out["push"].append([int(t0), int(t1), round(val, 4), spend])
    return out


class HabitTracker:
    """One match, the learner's side: board samples at its decision stops (e1_eval.SelfPlayMatch.due), events at the end.
    Holds no env / side reference between calls."""

    def __init__(self, side: int):
        self.side, self.low, self.smp, self.tw = int(side), None, [], []

    def observe(self, raw: dict, s) -> None:
        """``raw`` = the stop's env.raw() (the learner decides now), ``s`` = the learner's SelfPlaySide (read only)."""
        from pipeline.opp_elixir_count import MAX_ELIXIR, regen_between
        t = int(raw["tick"])
        if self.smp and t - self.smp[-1][0] < HAB_EVERY:
            return
        if self.low is None:
            self.low = next(float(w["y"]) for w in raw["episode"]["crown_towers"]
                            if int(w["side"]) == self.side and w["type"] == "king") < 16000
        el = next(float(p["elixir_exact"]) for p in raw["players"] if int(p["side"]) == self.side)
        h = s.extrap if s._prev_raw is not None else 0        # the elixir this decision sees (SelfPlaySide.prepare)
        if h:
            el = min(MAX_ELIXIR, el + regen_between(t, t + h))
        self.tw.append((t, [(float(w["x"]) / 1000 if abs(float(w["x"])) > 100 else float(w["x"]),
                             float(w["y"]) / 1000 if abs(float(w["y"])) > 100 else float(w["y"]), int(w["hp"]))
                            for w in raw["episode"]["crown_towers"] if int(w["side"]) != self.side and w["type"] != "king"]))
        self.smp.append((t, el, [(e["entity_id"], e["name"], int(e["hp"]), int(e["max_hp"]), e["x"], e["y"])
                                 for e in raw["entities"] if int(e["side"]) != self.side]))

    def result(self, s) -> dict:
        """``s`` = the learner's SelfPlaySide: its accepted plays at engine x, y (search_s0.hab_plays' rule)."""
        plays = []
        for q in s.plays:
            if q["accepted"]:
                X, Y = s.ep.cell_to_engine(q["cell"], s.mirror, s.cfg["grid"])
                plays.append((int(q["tick"]), q["card"], X, Y))
        out = events(self.smp, plays, bool(self.low), self.tw)
        out["samples"] = len(self.smp)
        return out


# ------------------------------------------------------------------------------------------------------------ learner
def row_terms(rec: dict, ticks, p: dict) -> dict:
    """One match: its habit record + the decision tick of every KEPT row (time order) -> {"r": reward per kept row, "idle" /
    "trade": the terms' sums, "n_idle", "n_push", "thr", "unmapped" (pushes ending before the first kept row)}."""
    ticks = np.asarray(ticks, dtype=np.int64)
    r = np.zeros(len(ticks))
    out = {"idle": 0.0, "trade": 0.0, "leak": 0.0, "n_idle": len(rec["idle"]), "n_push": len(rec["push"]),
           "thr": int(rec["thr"]), "leak_e": float(sum(x[1] for x in rec.get("leak", []))), "unmapped": 0, "r": r,
           "xbow": 0.0, "n_xbow": len(rec.get("xbow", [])), "n_xbow_fail": sum(f for _, f in rec.get("xbow", []))}
    if not len(ticks):
        return out
    w, total = p["habit_idle_w"], 0.0
    for t0, _ in sorted(rec["idle"]) if w > 0 else ():
        e = min(w, IDLE_MATCH_CAP - total)
        if e <= 0:
            break
        r[int(np.argmin(np.abs(ticks - (t0 + IDLE_T))))] -= e      # the row nearest the 4 s mark (a tie: the earlier)
        total += e
    out["idle"] = -total
    w, used = p["habit_trade_w"], 0.0
    for t0, t1, val, spend in sorted(rec["push"], key=lambda x: x[1]) if w > 0 else ():
        i = int(np.searchsorted(ticks, t1, side="right")) - 1
        if i < 0:
            out["unmapped"] += 1
            continue
        d = w * float(np.clip(val - spend, -TRADE_CLIP_E, 0.0))
        e = math.copysign(min(abs(d), TRADE_MATCH_CAP - used), d)
        r[i] += e
        used += abs(e)
        out["trade"] += e
    w, used = p.get("habit_leak_w", 0.0), 0.0
    for t1, wasted in rec.get("leak", []) if w > 0 else ():
        i = max(int(np.searchsorted(ticks, t1, side="right")) - 1, 0)   # the kept row at / before the gap end
        e = min(w * wasted, LEAK_MATCH_CAP - used)
        if e <= 0:
            break
        r[i] -= e
        used += e
    out["leak"] = -used
    w, used = p.get("habit_xbow_w", 0.0), 0.0
    for t0, failed in rec.get("xbow", []) if w > 0 else ():
        if not failed:
            continue
        e = min(w, XBOW_MATCH_CAP - used)
        if e <= 0:
            break
        r[int(np.argmin(np.abs(ticks - (t0 + XB_WINDOW))))] -= e      # the row nearest the end of the lock window
        used += e
    out["xbow"] = -used
    return out


def batch_stats(sums: list) -> dict:
    """Per-update monitors over row_terms dicts: per term the per-match reward mean / min / max / non-zero share, and the
    events per match."""
    n = max(len(sums), 1)
    st = {"matches": len(sums), "thr_per_match": sum(s["thr"] for s in sums) / n,
          "idle_per_match": sum(s["n_idle"] for s in sums) / n, "push_per_match": sum(s["n_push"] for s in sums) / n,
          "unmapped": int(sum(s["unmapped"] for s in sums)),
          "leak_e_per_match": sum(s.get("leak_e", 0.0) for s in sums) / n,
          "xbow_reach_per_match": sum(s.get("n_xbow", 0) for s in sums) / n,
          "xbow_fail_per_match": sum(s.get("n_xbow_fail", 0) for s in sums) / n}
    for k in ("idle", "trade", "leak", "xbow"):
        v = [float(s.get(k, 0.0)) for s in sums] or [0.0]
        st.update({f"{k}_r_mean": sum(v) / n, f"{k}_r_min": min(v), f"{k}_r_max": max(v),
                   f"{k}_r_nz": sum(x != 0 for x in v) / n})
    return st
