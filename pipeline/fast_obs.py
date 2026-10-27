"""Opt-in fast observation paths for batched rollouts (plan1026 Pillar 4b, ticket S1b). Each function returns exactly
what the original returns (tests: pipeline/tests/test_fast_obs.py, and the rollout identity check in
scratchpad/gauntlet/L74/speed/SPEED.md section f); nothing here is imported by the trainer or live path unless a caller
installs it (``install``).

``sim_cue_rows(match)`` == ``e1_eval.sim_cue_rows``. The original calls ``sim_unit_state.extract`` at every learner
decision: a full ``Battle.save()`` (about 3 ms, a 36 KB JSON) + two JSON parses + projectile / area / catalogue
decoding the cue rows never read. Here:
  1. no unit token to match (``ti`` empty) -> zeros WITHOUT ``save()``; the per-match buff-duration memo that extract
     keeps is still updated, from ``state_json`` alone (the memo reads only uid + buffs, which state_json carries);
  2. otherwise the units only (extract's own unit loop, verbatim), parsed with orjson.
"""
from __future__ import annotations

import sys

import numpy as np


def _loads():
    try:
        import orjson
        return orjson.loads
    except ImportError:                                # pragma: no cover -- the stdlib parse gives the same objects
        import json
        return json.loads


LOADS = _loads()


def _memo_update(battle, memo: dict, st: dict, T: dict) -> None:
    """``extract``'s memo side effect (memo[uid, alias] = max of the remaining ms seen and the table total), only."""
    from pipeline.sim_unit_state import SENTINEL_MS
    F = sys.modules["royalesim"].ENTITY_FIELDS
    iu, ib = F.index("uid"), F.index("buffs")
    for row in st["entities"]:
        u = row[iu]
        for alias, ms in row[ib]:
            if ms < SENTINEL_MS:
                memo[u, alias] = max(ms, memo.get((u, alias), 0), *(T["totals"].get(a, 0) for a in alias.split("|")))


def extract_units(battle, memo=None, hit_window_ms=None) -> list:
    """``sim_unit_state.extract(...)["units"]``: the same unit dicts, same order, same memo updates."""
    from pipeline import sim_unit_state as SU
    hit_window_ms = SU.HIT_WINDOW_MS if hit_window_ms is None else hit_window_ms
    sim = sys.modules["royalesim"]
    T, names = SU._tbl(sim), SU._unit_names(battle)
    sv, st = LOADS(battle.save()), LOADS(battle.state_json())
    E, F = sv["ents"], sim.ENTITY_FIELDS
    slots = [i for i, a in enumerate(E["alive"]) if a]
    if len(slots) != len(st["entities"]):
        raise ValueError("save/state_json entity lists disagree")
    uid, units = {}, []
    K, SENTINEL_MS, _KINDS, _statuses = SU.K, SU.SENTINEL_MS, SU._KINDS, SU._statuses
    for i, row in zip(slots, st["entities"]):
        e = dict(zip(F, row))
        if (e["x"], e["y"]) != (E["pos"][i]["x"], E["pos"][i]["y"]):
            raise ValueError("save/state_json entity order disagree")
        uid[i] = e["uid"]
        name = names[e["unit_type"]]
        ct = T["char"].get(name, {})
        hs = ct.get("hit_speed_ms")
        flags = {n for b, n in enumerate(sim.STATUS_BITS) if e["status_flags"] >> b & 1}
        tgt = e["target_uid"] if e["target_uid"] >= 0 else None
        prog, load = E["attack_ms"][i], E["attack_load_ms"][i]
        if tgt is None or prog <= 0:
            phase = "idle"
        else:
            phase = "hit" if hs and prog % hs < hit_window_ms else "windup"
        jumping = E["jumping"][i] or E["dash_state"][i] not in ("None", "Standing")
        if "underground" in flags:
            state = "tunnelling"
        elif e["deploy_ticks"] > 0:
            state = "deploying"
        elif jumping:
            state = "jumping"
        elif "ability_windup" in flags:
            state = "casting"
        elif tgt is not None and E["attack_phase"][i] != "Idle":
            state = "engaged"
        elif E["kind"][i] == "Troop" and E["speed"][i] > 0:
            state = "moving"
        else:
            state = "idle"
        hide = E["hide"][i].lower() if ct.get("hides_when_not_attacking") and state != "deploying" else None
        status = dict.fromkeys(("stunned", "frozen", "slowed", "raged", "taunted", "invisible", "shielded"), False)
        status["frozen"] = e["stun_ticks"] > 0
        status["invisible"] = "invisible" in flags
        status["shielded"] = e["shield"] > 0
        slow_frac, buffs = None, []
        for alias, ms in e["buffs"]:
            frac = None
            if memo is not None and ms < SENTINEL_MS:
                total = memo[uid[i], alias] = max(ms, memo.get((uid[i], alias), 0),
                                                  *(T["totals"].get(a, 0) for a in alias.split("|")))
                frac = round(ms / total, 3) if total else None
            for tag in _statuses(alias, T["buffs"]):
                status[tag] = True
                if tag == "slowed" and frac is not None:
                    slow_frac = max(slow_frac or 0, frac)
            buffs.append({"name": alias, "ms": ms, "frac": frac})
        ib = ct.get("idle_buff")
        if ib and state != "engaged":
            for tag in _statuses(ib["buff_name"], T["buffs"]):
                status[tag] = True
            buffs.append({"name": ib["buff_name"], "ms": ib["time_ms"], "frac": None})
        status["slow_frac"] = slow_frac
        units.append({
            "uid": e["uid"], "team": e["team"], "kind": _KINDS[E["kind"][i]], "name": name,
            "x": round(e["x"] / K, 3), "y": round(e["y"] / K, 3), "hp": e["hp"], "max_hp": e["max_hp"],
            "state": state, "charging": bool(E["charged"][i]), "charge_frac": round(e["charge"] / 1000, 3),
            "hide": hide,
            "attack": {"target": tgt, "phase": phase, "frac": round(prog % hs / hs, 3) if hs and phase != "idle" else None,
                       "progress_ms": prog, "hit_speed_ms": hs, "load_ms": load},
            "status": status, "buffs": buffs})
    units.sort(key=lambda u: u["uid"])
    return units


def sim_cue_rows(match) -> np.ndarray:
    """``e1_eval.sim_cue_rows`` (same rows, same memo): skips ``save()`` when no unit token can take a cue."""
    from pipeline import e1_eval as E
    from pipeline import sim_unit_state as SU
    from pipeline.model_gen import CUE_N, cue_vector
    E.require_cue_runtime()
    tok, mask = match._obs[0], match._obs[1]
    out = np.zeros((len(tok), CUE_N), np.float32)
    memo = match.__dict__.setdefault("_cue_memo", {})
    battle = match.env.core._battle
    ti = np.flatnonzero(mask & (tok[:, 13] == 0) & ((tok[:, 1] > 0) | (tok[:, 2] > 0)))
    if not len(ti):
        _memo_update(battle, memo, LOADS(battle.state_json()), SU._tbl(sys.modules["royalesim"]))
        return out
    units = extract_units(battle, memo, hit_window_ms=100)
    towers = {u["uid"] for u in units if u["kind"] in ("princess_tower", "king_tower")}
    bodies = [u for u in units if u["uid"] not in towers]
    if not bodies:
        return out
    bx = np.array([u["x"] / 18.0 for u in bodies])
    by = np.array([1.0 - u["y"] / 32.0 for u in bodies])
    if match.side == 1:
        bx, by = 1.0 - bx, 1.0 - by
    mine = np.array([u["team"] == match.side for u in bodies])
    d = np.hypot((tok[ti, 4:5] - bx) * 18.0, (tok[ti, 5:6] - by) * 32.0)
    d[(tok[ti, 1:2] > 0) != mine] = np.inf
    while True:
        i, j = np.unravel_index(np.argmin(d), d.shape)
        if not d[i, j] <= E.CUE_MATCH_TILES:
            return out
        u = bodies[j]
        out[ti[i]] = cue_vector(u, u["attack"]["target"] in towers)
        d[i, :] = np.inf
        d[:, j] = np.inf


def install(names=("cue",)) -> None:
    """Swap the fast paths into the running process (a batched-rollout worker): e1_eval.gen_row looks
    ``sim_cue_rows`` up as a module global at each call."""
    from pipeline import e1_eval as E
    if "cue" in names:
        E.sim_cue_rows = sim_cue_rows
