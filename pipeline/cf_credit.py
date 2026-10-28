"""Counterfactual credit from SIM forks (plan1026 Pillar 3 P3, R_fork; rl_royale ``cf_credit``, opt-in: absent / null /
false = the trainer exactly as before, same config hash, same rows). Revised per REWARD_REVIEW.md section 4.

At a TRIGGER (a learner decision of a PPO rollout, below) the actor forks the SIM (search_s0.fork_into: engine
save_state / load_state into pooled envs + deep copies of the env's and both sides' python state, RNGs included) into
K x C copies: C CANDIDATES (candidate 0 = the policy's ACTUAL decision, then up to cf_max_alts alternatives) x K paired
continuations with COMMON RANDOM NUMBERS (continuation 0 keeps the real match's RNG states, so candidate 0's copy replays
the real continuation draw for draw; continuation k >= 1 reseeds every side RNG the same way for every candidate). Every
copy plays its candidate, then both sides play on with their own policies (learner: the rollout's sampler on the same
weights; opponent: the match's own opponent -- model, cfg, decode -- so the pillar-2 human-like opponents fork with the
match once rollouts use them), until the learner's first decision at >= root + cf_horizon_ticks (or the match end; roots
within cf_end_ticks of tick END_TICK always run to the end):
    Q[i, k] = gamma^(T_end - root) R_win          (the copy's match ended: +1 / -1 / 0)
            = gamma^(t - root) (Phi(s_t) + v_scale v_net(s_t))    (stopped at learner decision t)
i.e. the trainer's own return (review fix 1): GAE's per-tick gamma, its V_eff = Phi + s v_net (rl_royale.gae_batch); the
root's own V_eff cancels in every difference. Phi = the config's state potential at the stop (shaping tower_phat, the
fast loop's Phi = P_hat(win) - 0.5, from the same reward_shaping row the actor records; 0 with shaping none); cf_cfg refuses
every other shaping and every in-window reward besides R_win.
Advantage (review fix 2, one baseline per decision): per continuation A[i, k] = Q[i, k] - mean_j Q[j, k] (CRN-paired), A_i
= mean_k A[i, k] = Q_i - mean_j Q_j. Candidate 0's A REPLACES its real row's GAE advantage; each alternative becomes an
extra PPO row (its decision's inputs, its own action and behaviour log-probs) with its A. Noise control: A is shrunk per
trigger by its batch reliability (``reliability``: between-continuation covariance / variance of the K-mean, the empirical
Bayes factor), then scaled to the real rows' units (rl_royale.gae_batch: cf_w x clip(A / sd, +-cf_clip), sd = the std of
the batch's raw real-row GAE advantages).
Coverage (review fix 3): the ``random`` trigger forks a random decision with policy-sampled alternatives.
Audit: a cf_audit_p share of samples runs its continuation-0 copies on to the match end (``q_end``), for the critic-slope
check (``slope_audit``: terminal return on the horizon Q, PLAN band [0.7, 1.3]); training still reads the horizon Q.

Triggers (PLAN P3 table; each fires with probability cf_p[name] when its condition holds, >= cf_gap_ticks after its last
sample; one sample per decision, the first firing trigger in TRIGGERS order that has an alternative):
  rocket_tornado  (opt-in, cf_p 0 unless set) Rocket + Tornado both in hand, 9 elixir by the follow-up and a clump whose
                  pull holds cf_combo_value and more than the best lone blast (decision_options.rocket_tornado_choice,
                  the measured rule set)                       -> combo (Rocket at the pull centre + the Tornado as a
                  follow_ups play), rocket_clump (the best lone blast), wait
  tornado_redirect (opt-in) Tornado affordable, BOTH our princesses alive, a mobile ground unit on the bridge / our bank
                  within cf_redirect_dist_tiles of our nearest princess -> tornado_king (centre toward our king), wait,
                  tornado_on (centre on the unit: no net pull)  rocket_played   the policy plays the Rocket           -> wait, second_card (its best other card)
  rocket          Rocket affordable, not played          -> rocket_clump, rocket_princess (weakest enemy princess)
  wincon          an enemy building-targeting troop on our half -> wait, rocket_on, troop_on (its best troop), cheap_on
  siege           an enemy building locked on our tower, or an enemy X-Bow / Mortar in reach of one
                                                         -> wait, rocket_on, front (best troop in front of the princess), troop_on
  xbow_after_fail X-Bow affordable <= cf_xbow_fail_window_ticks after one of our reach X-Bows died without a lock
                                                         -> wait, xbow_defensive, rocket_princess, xbow_reach
  xbow            the policy plays a reach X-Bow         -> wait, xbow_defensive, xbow_other_lane
  idle_full       the policy waits at >= cf_full_elixir  -> play_now (its best card, argmax cell)
  log_bait        the policy plays the Log after the opponent showed a bait card -> wait
  random          any sampled decision                   -> cf_random_alts policy-sampled actions
A restricted alternative takes the policy's own argmax cell inside its cell set. The combo's alternative row carries its FIRST
play only (the Rocket); its Tornado is a scripted follow_ups play with no row of its own (cf/P6_DESIGN.md: prefix rows).
Not here yet (NOT dropped): P6 macro prefixes (multi-step alternatives with a row per step).

Record (``SelfPlayMatch.result()["cf"]``, the interface the fast loop also produces; JSON-able):
  {"samples": [{"row": traj row index of the decision, "tick", "trigger", "fired": [...], "audit": bool, "to_end": bool,
                "cands": [{"kind", "play", "slot", "cell", "lp_gate", "lp_card", "lp_cell", "q": [K], "end": [K],
                           "terminal": [K], "q_end": float | None (audit, continuation 0)}],   # cands[0] = the decision
                "fork_ticks", "wall_s"}],
   "triggers": {name: samples}, "capped": {name: n}, "decisions", "fork_ticks", "wall_s", "xbow_failed", "k"}"""
from __future__ import annotations

import copy
import math
import os
import random
import time
import zlib
from collections import Counter
from typing import Optional

import numpy as np

TRIGGERS = ("rocket_tornado", "tornado_redirect", "rocket_played", "rocket", "wincon", "siege", "xbow_after_fail", "xbow",
            "idle_full", "log_bait", "random")
# L1 pilots (plan1026/cf/data: pilot2 = 512 matches / 2,907 samples after the critic warm-up, pilot3 = the noise study): the
# pilot's probabilities cost 5.9x the match ticks; these are pilot_report.py's water-filling split of 1.0x match ticks (equal
# fork ticks per trigger, random half) -> 0.08-0.3 samples per match per trigger (cost to be re-measured at these values).
P_DEFAULT = {"rocket_played": 0.5, "rocket": 0.0009, "wincon": 0.008, "siege": 0.028, "xbow_after_fail": 0.0064, "xbow": 0.0175,
             "idle_full": 1.0, "log_bait": 0.07, "rocket_tornado": 0.055, "tornado_redirect": 0.0011, "random": 0.0005}
# rocket_tornado / tornado_redirect (P3-FORK2, lead 10-28: Rocket use and the Tornado king redirect are REQUIRED behaviours, so
# the SIM credits them by default) sit at their measured 1x-budget p (pilot2 / pilot4). OPT_IN = the triggers whose condition is
# read only while their probability is > 0 (probability 0 = no condition read, no RNG draw, as before). The combo needs the
# follow_ups play (action_delay_ticks > 0, no pipeline_decisions / tap_loss / tap_slow): a config without it gets rocket_tornado
# 0.0 unless cf_p sets it (then cf_cfg refuses, naming the keys).
OPT_IN = ("rocket_tornado", "tornado_redirect")
# per-trigger fork horizons (ticks) where the 600-tick Q is too noisy (pilot3, K = 2 at 600 vs 300: idle_full SNR 0.29 -> 0.77,
# log_bait 0.52 -> 0.78, wincon 0.83 -> 1.31, siege 0.68 -> 1.15, random 0.80 -> 1.23; the critic slope of the within-sample
# differences at 300 is 0.84 +- 0.33, inside [0.7, 1.3]) -- half the cost per sample as well
HORIZON_DEFAULT = {"idle_full": 300, "log_bait": 300, "wincon": 300, "siege": 300, "random": 300}
DEFAULTS = {"cf_horizon_ticks": 600, "cf_k": 2, "cf_w": 1.0, "cf_clip": 3.0, "cf_max_alts": 3, "cf_gap_ticks": 100,
            "cf_cap_ticks": 8000, "cf_audit_p": 0.1, "cf_end_ticks": 1200, "cf_shrink": True, "cf_shrink_min": 30,
            "cf_p": None, "cf_random_alts": 2, "cf_rocket_min_value": 2.0, "cf_siege_radius_tiles": 2.0,
            "cf_front_min_tiles": 5.0, "cf_front_max_tiles": 8.0, "cf_xbow_fail_window_ticks": 600, "cf_full_elixir": 9.9,
            "cf_combo_value": 6.0, "cf_redirect_dist_tiles": 12.0, "cf_k_by": None, "cf_horizon_by": None,
            "cf_horizon_sweep": None, "cf_adv_scale": 1.0, "cf_diag": False, "cf_rocket_lead": "off"}
NEW_KEYS = ("cf_combo_value", "cf_redirect_dist_tiles", "cf_k_by", "cf_horizon_by", "cf_horizon_sweep", "cf_adv_scale", "cf_diag", "cf_rocket_lead")   # dropped from the config hash at their
# defaults (older cf-on hashes stay); cf_k_by / cf_horizon_by = {trigger: K / horizon ticks}, the per-trigger noise controls;
# cf_horizon_sweep = [ticks, ...] (< the horizon): the SAME forks also record Q read at those earlier stops ("qh"), so one pilot
# gives the SNR / critic-slope of every candidate horizon (diagnostic, the learner ignores it);
# cf_adv_scale = the slope calibration: every training advantage x this factor (the pilots' within-sample critic slope of the
# terminal return on the horizon return is ~0.72 +- 0.07: the horizon Q exaggerates the difference between two candidates ~1.4x;
# 1.0 = not applied; cf_w scales the same rows afterwards, the calibration differs from it only through cf_clip);
# cf_rocket_lead = "drift": the Rocket alternatives (rocket_clump, rocket_on) aim where the bodies will have walked to when the Rocket
# lands (decision_options.best_rocket_clump lead drift; the static aim covers ~38% of a blast's value vs 46% drifted, oracle 79%);
# "off" = the static aim (cfaud3: a Rocket aimed at a wincon's present position is -0.20 vs the policy's action);
# cf_diag = the P4 audit record (diagnostic, the learner ignores it): per sample the root context ("ctx": elixir, hand, tower
# snapshot, enemy bodies on our half), per fork the state at each stop ("dg": Phi / critic parts of Q + the tower / elixir
# snapshot), per match the opponent ("opp": league spec + style), per candidate a "meta" (clump value ...)
KEYS = ("cf_credit",) + tuple(DEFAULTS)
INTS = ("cf_horizon_ticks", "cf_k", "cf_max_alts", "cf_gap_ticks", "cf_cap_ticks", "cf_end_ticks", "cf_shrink_min",
        "cf_random_alts", "cf_xbow_fail_window_ticks")
END_TICK = 6000                       # royale_env: normal play stops at tick 6000 (2 min overtime)
SIEGE_NAMES = ("xbow", "mortar")
WINCON = frozenset(("giant", "golem", "royalgiant", "hogrider", "ramrider", "battleram", "balloon", "lavahound",
                    "elixirgolem", "goblingiant", "electrogiant", "wallbreakers", "royalhogs", "skeletonbarrel",
                    "runegiant"))  # ponytail: hand list of building-targeting troops; a catalogue target flag replaces it
NO_BUILDING_DAMAGE = ("tornado",)     # ponytail: icebow's one spell that cannot hurt a building
TERRITORY_Y_TILES = 17.0              # my frame: own troop territory starts at row 17; ponytail: an opened pocket is not used
PHI_MODES = ("none", "tower_phat")   # shapings whose Phi the forks compute (reward_shaping.state_record / state_phi)
FORK_FRESH = ("traj",)                # side attributes a fork starts empty (search_s0.fork_into ``fresh``)
TILE = 18000.0                        # RoyaleSim units per tile


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


KEEP = ("cf_shrink", "cf_p", "cf_k_by", "cf_horizon_by", "cf_horizon_sweep", "cf_diag", "cf_rocket_lead")   # values kept as they are (not float())


def combo_ok(cfg: dict) -> bool:
    """The config can play the combo's Tornado as a follow_ups play (e1_eval.SelfPlaySide.apply)."""
    return bool(cfg.get("action_delay_ticks")) and not (cfg.get("pipeline_decisions") or cfg.get("tap_loss") or cfg.get("tap_slow"))


def effective_p(cfg: dict) -> dict:
    """P_DEFAULT merged with the config's cf_p; rocket_tornado is 0.0 when cf_p does not set it and the config cannot play
    the combo (the default must not make an older config unrunnable)."""
    user = cfg.get("cf_p") or {}
    p = {**P_DEFAULT, **{k: float(v) for k, v in user.items()}}
    if "rocket_tornado" not in user and not combo_ok(cfg):
        p["rocket_tornado"] = 0.0
    return p


def cf_cfg(cfg: dict) -> Optional[dict]:
    """The cf keys of a config, validated (SystemExit naming the bad key): None when ``cf_credit`` is absent / null / false
    (the other cf keys must then be unset), else {key: value} with DEFAULTS filled (``cf_p`` merged over P_DEFAULT). Needs
    advantage gae, gae_gamma_unit tick and league; refuses every path whose return the forks cannot value (any shaping,
    spell / crown / habit terms) or whose rows the alternative rows are not wired for."""
    on = cfg.get("cf_credit")
    if on is None or on is False:
        stray = [k for k in DEFAULTS if cfg.get(k) is not None]
        if stray:
            raise SystemExit(f"bad cf_credit config: {stray} set without cf_credit on")
        return None
    c = {k: (v if cfg.get(k) is None else cfg[k]) for k, v in DEFAULTS.items()}
    bad = [] if on is True else [f"cf_credit must be on / off (a bool), got {on!r}"]
    for k in INTS:
        lo = 1 if k in ("cf_horizon_ticks", "cf_k", "cf_max_alts") else 0
        if not (isinstance(c[k], int) and not isinstance(c[k], bool) and c[k] >= lo):
            bad.append(f"{k} must be an integer >= {lo}, got {c[k]!r}")
    for k in ("cf_w", "cf_rocket_min_value", "cf_front_min_tiles", "cf_full_elixir", "cf_combo_value"):
        if not (_num(c[k]) and c[k] >= 0):
            bad.append(f"{k} must be a finite number >= 0, got {c[k]!r}")
    for k in ("cf_clip", "cf_siege_radius_tiles", "cf_front_max_tiles", "cf_redirect_dist_tiles"):
        if not (_num(c[k]) and c[k] > 0):
            bad.append(f"{k} must be a finite number > 0, got {c[k]!r}")
    if not (_num(c["cf_adv_scale"]) and 0 < c["cf_adv_scale"] <= 2):
        bad.append(f"cf_adv_scale must be a finite number in (0, 2], got {c['cf_adv_scale']!r}")
    if c["cf_rocket_lead"] not in ("off", "drift"):
        bad.append(f"cf_rocket_lead must be off or drift, got {c['cf_rocket_lead']!r}")
    if type(c["cf_diag"]) is not bool:
        bad.append(f"cf_diag must be a bool, got {c['cf_diag']!r}")
    if not (_num(c["cf_audit_p"]) and 0 <= c["cf_audit_p"] <= 1):
        bad.append(f"cf_audit_p must be in [0, 1], got {c['cf_audit_p']!r}")
    if type(c["cf_shrink"]) is not bool:
        bad.append(f"cf_shrink must be a bool, got {c['cf_shrink']!r}")
    if _num(c["cf_front_min_tiles"]) and _num(c["cf_front_max_tiles"]) and c["cf_front_min_tiles"] > c["cf_front_max_tiles"]:
        bad.append(f"cf_front_min_tiles {c['cf_front_min_tiles']} > cf_front_max_tiles {c['cf_front_max_tiles']}")
    for key, lo, what in (("cf_k_by", 2, "K >= 2 (the reliability needs two continuations)"),
                          ("cf_horizon_by", 1, "ticks >= 1")):
        v = c[key] if c[key] is not None else {}
        if not isinstance(v, dict) or any(k not in TRIGGERS for k in v) or not all(
                isinstance(x, int) and not isinstance(x, bool) and x >= lo for x in v.values()):
            bad.append(f"{key} must map trigger names {TRIGGERS} to integers with {what}, got {v!r}")
    sw = c["cf_horizon_sweep"] if c["cf_horizon_sweep"] is not None else []
    if not isinstance(sw, (list, tuple)) or not all(isinstance(x, int) and not isinstance(x, bool) and x >= 1 for x in sw):
        bad.append(f"cf_horizon_sweep must be a list of integers >= 1 (ticks), got {sw!r}")
    p = c["cf_p"] if c["cf_p"] is not None else {}
    if not isinstance(p, dict) or any(k not in TRIGGERS for k in p) or not all(_num(v) and 0 <= v <= 1 for v in p.values()):
        bad.append(f"cf_p must map trigger names {TRIGGERS} to probabilities in [0, 1], got {p!r}")
        p = {}
    if p.get("rocket_tornado", 0.0) > 0 and not combo_ok(cfg):
        bad.append("cf_p rocket_tornado > 0 needs action_delay_ticks > 0 and no pipeline_decisions / tap_loss / tap_slow "
                   "(its Tornado is a follow_ups play: e1_eval.SelfPlaySide.apply)")
    if cfg.get("advantage", "match_loo") != "gae" or cfg.get("gae_gamma_unit", "row") != "tick":
        bad.append("cf_credit needs advantage gae and gae_gamma_unit tick (the fork return uses GAE's per-tick gamma)")
    if not cfg.get("league"):
        bad.append("cf_credit needs league true (the forks are self-play matches)")
    for k in ("branch_gate", "posture_head", "posture", "critic_ctx", "kl_ref_gate_max_elixir", "spell_value",
              "habit_reward", "learner_pipeline_frac", "stored_values"):
        if cfg.get(k) not in (None, False, 0, 0.0):
            bad.append(f"cf_credit with {k} is not supported (its rows / rewards are not in the fork return)")
    if cfg.get("shaping", "none") not in PHI_MODES:
        bad.append(f"cf_credit needs shaping in {PHI_MODES} (a Phi the forks do not compute would change the return)")
    from pipeline import reward_terms as RT
    if any(cfg.get(k) not in (None, False) for k in RT.TERMS):
        bad.append("cf_credit with crown terms is not supported (their rewards are not in the fork return)")
    if bad:
        raise SystemExit("bad cf_credit config: " + "; ".join(bad))
    out = {k: (int(v) if k in INTS else v if k in KEEP else float(v)) for k, v in c.items()}
    out["cf_horizon_sweep"] = sorted({int(x) for x in (c["cf_horizon_sweep"] or ())})
    out["cf_p"] = effective_p(cfg)
    out["cf_k_by"], out["cf_horizon_by"] = dict(c["cf_k_by"] or {}), {**HORIZON_DEFAULT, **(c["cf_horizon_by"] or {})}
    return out


def canonical(cfg: dict) -> dict:
    """rl_royale.config_sha's view: off (absent / null / false) = the cf keys dropped (the historical hash); on = every
    default filled (one hash for implicit / explicit)."""
    if cfg.get("cf_credit") is None or cfg.get("cf_credit") is False:
        return {k: v for k, v in cfg.items() if k not in KEYS}
    c = {k: (v if cfg.get(k) is None else cfg[k]) for k, v in DEFAULTS.items()}
    c["cf_p"] = {k: v for k, v in effective_p(cfg).items() if not (k in OPT_IN and v == 0.0)}   # opt-in triggers off: the older hash
    out = {**cfg, "cf_credit": True, **{k: (int(v) if k in INTS else v if k in KEEP else float(v)) for k, v in c.items()}}
    if out.get("cf_horizon_by") is not None:                  # the effective map; the default map is "absent"
        out["cf_horizon_by"] = {**HORIZON_DEFAULT, **out["cf_horizon_by"]}
        if out["cf_horizon_by"] == HORIZON_DEFAULT:
            out["cf_horizon_by"] = {}
    for k in NEW_KEYS:
        v = out.get(k)
        if v is None or (isinstance(v, (dict, list, tuple)) and not v) or (
                not isinstance(v, (dict, list, tuple)) and v == DEFAULTS[k]):
            out.pop(k, None)
    return out


# ------------------------------------------------------------------------------------------------------
# board reading (a prepared learner side + its decision)
# ------------------------------------------------------------------------------------------------------
def _norm(name) -> str:
    from pipeline.archetypes import ALIAS
    n = "".join(ch for ch in str(name).split("@")[0].lower() if ch.isalnum())
    return ALIAS.get(n, n)


def slot_names(s) -> list[str]:
    """Normalised engine card name of each deck slot of side ``s`` (form suffix dropped)."""
    return [_norm(s.engine_deck[s.deck_index_of_slot[k]]) for k in range(len(s.deck_index_of_slot))]


def slot_kinds(s) -> list[str]:
    """RoyaleSim catalogue kind (TROOP / BUILDING / SPELL ...) of each deck slot of ``s`` (cached on its env)."""
    env = s.env
    kinds = getattr(env, "_cf_kinds", None)
    if kinds is None:
        kinds = env._cf_kinds = {int(c.card_id): str(c.card_kind).upper() for c in env.core.cards()}
    return [kinds.get(int(env.deck_ids[s.side][s.deck_index_of_slot[k]]), "") for k in range(len(s.deck_index_of_slot))]


def _crown(es, team_pred) -> dict:
    from royalegym.protocol import EntityKind
    return {e.uid: e for e in es.entities if team_pred(int(e.team)) and e.hp > 0
            and e.kind in (EntityKind.KING_TOWER, EntityKind.PRINCESS_TOWER)}


def _dist(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y) / TILE


def siege_target(env, side: int, es=None) -> Optional[dict]:
    """The enemy building to answer, from the engine state ``es`` (read if None): alive, team != ``side``, and locked on
    one of ``side``'s crown towers (``target_uid``) or an X-Bow / Mortar within XBOW_REACH_TILES (centre to centre) of
    one; locked first, then the closest. -> {uid, name, x, y (engine units), locked, princess: (x, y) of the threatened
    princess -- the locked one, else the alive princess nearest the building; None without one} or None."""
    from royalegym.protocol import EntityKind
    from pipeline.decision_options import XBOW_REACH_TILES
    es = env.core.state() if es is None else es
    towers = _crown(es, lambda t: t == side)
    if not towers:
        return None
    princesses = [t for t in towers.values() if t.kind == EntityKind.PRINCESS_TOWER]
    best = None
    for e in es.entities:
        if int(e.team) == side or e.kind != EntityKind.BUILDING or e.hp <= 0:
            continue
        name = _norm(env.names.get(e.card_id, ""))
        d = min(_dist(e, t) for t in towers.values())
        tu = getattr(e, "target_uid", None)
        locked = tu in towers
        if not (locked or (name in SIEGE_NAMES and d <= XBOW_REACH_TILES)):
            continue
        key = (not locked, d)
        if best is None or key < best[0]:
            pr = towers[tu] if locked and towers[tu].kind == EntityKind.PRINCESS_TOWER else (
                min(princesses, key=lambda t: _dist(e, t)) if princesses else None)
            best = (key, {"uid": int(e.uid), "name": name, "x": float(e.x), "y": float(e.y), "locked": bool(locked),
                          "princess": None if pr is None else (float(pr.x), float(pr.y))})
    return None if best is None else best[1]


def xbow_watch(st: dict, env, side: int, tick: int, es) -> None:
    """Our X-Bows on the engine state ``es`` (one call per learner decision while any is tracked or on the board):
    ``st["xb"]`` uid -> [reach (placed within XBOW_REACH_TILES of an alive enemy crown tower), locked (its target_uid was
    an enemy crown tower at some decision)]; one that is gone counts in ``xb_failed`` (+ ``xb_fail_tick``) when it had
    reach and never locked. ponytail: locks are sampled at the learner's decisions (every >= 10 ticks)."""
    from royalegym.protocol import EntityKind
    from pipeline.decision_options import XBOW_REACH_TILES
    foe = _crown(es, lambda t: t != side)
    seen = set()
    for e in es.entities:
        if int(e.team) != side or e.kind != EntityKind.BUILDING or e.hp <= 0 or _norm(env.names.get(e.card_id, "")) != "xbow":
            continue
        seen.add(int(e.uid))
        w = st["xb"].setdefault(int(e.uid), [any(_dist(e, t) <= XBOW_REACH_TILES for t in foe.values()), False])
        w[1] = w[1] or getattr(e, "target_uid", None) in foe
    for uid in [u for u in st["xb"] if u not in seen]:
        reach, locked = st["xb"].pop(uid)
        if reach and not locked:
            st["xb_failed"] += 1
            st["xb_fail_tick"] = int(tick)


def board_tiles(x: float, y: float, mirror: bool) -> tuple[float, float]:
    """RoyaleSim engine (x, y) -> board tiles in a side's own frame (me at the bottom): obs_contract._engine_xy x (18, 32)."""
    from pipeline.obs_contract import _engine_xy
    bx, by = _engine_xy(float(x) / 18.0, float(y) / 18.0, mirror)
    return bx * 18.0, by * 32.0


def raw_tiles(e: dict, mirror: bool) -> tuple[float, float]:
    """A raw (royale_env.raw) row's x, y -> board tiles in a side's own frame."""
    from pipeline.obs_contract import _engine_xy
    bx, by = _engine_xy(float(e["x"]), float(e["y"]), mirror)
    return bx * 18.0, by * 32.0


def siege_cells(bx: float, by: float, grid: str, kind: str, name: str, radius: float) -> np.ndarray:
    """[2304] bool candidate cells for a card answering a unit at board tiles (bx, by): the Rocket -- cells within
    ``radius`` of it that do not cover the enemy king; any other card -- own-territory cells within ``radius`` of the
    territory's nearest point to it."""
    from pipeline import decision_options as DO
    x, y = DO.cell_centres_tiles(grid)
    d = np.hypot(x - bx, y - by)
    if "SPELL" in kind and name == "rocket":
        return (d <= radius) & ~DO.tower_cover_cells(grid, DO.rocket_radius_tiles())[0]
    own = y >= TERRITORY_Y_TILES
    return own & (d <= d[own].min() + radius)


def front_cells(px: float, py: float, grid: str, lo: float, hi: float) -> np.ndarray:
    """[2304] bool own-territory cells of the lane of my princess at board tiles (px, py), nearer the river than it
    (smaller y: forward is DECREASING y in my frame), lo..hi tiles from it."""
    from pipeline import decision_options as DO
    x, y = DO.cell_centres_tiles(grid)
    d = np.hypot(x - px, y - py)
    return (y >= TERRITORY_Y_TILES) & ((x < 9.0) == (px < 9.0)) & (y < py) & (d >= lo) & (d <= hi)


def xbow_reach_cells(s, grid: str) -> np.ndarray:
    """[2304] bool own-territory cells within XBOW_REACH_TILES of an alive enemy crown tower (side ``s``'s frame)."""
    from pipeline import decision_options as DO
    x, y = DO.cell_centres_tiles(grid)
    reach = np.zeros(len(x), dtype=bool)
    for t in s.state["episode"]["crown_towers"]:
        if int(t["side"]) != s.side and not t.get("destroyed") and t["hp"] > 0:
            tx, ty = raw_tiles(t, s.mirror)
            reach |= np.hypot(x - tx, y - ty) <= DO.XBOW_REACH_TILES
    return reach & (y >= TERRITORY_Y_TILES)


def own_elixir(s) -> float:
    return float(next(pl for pl in s.state["players"] if int(pl["side"]) == s.side)["elixir_exact"])


def snap(x) -> list:
    """cf_diag: a prepared side's tower / elixir snapshot (10 floats): own then foe [princess hp lost (sum of 1 - hp/max over the
    2 princesses), king hp lost, king activated, crowns conceded] (reward_shaping.tower_phat_record), then own and foe elixir."""
    from pipeline import reward_shaping as RS
    el = {int(pl["side"]): float(pl["elixir_exact"]) for pl in x.state["players"]}
    own = el.get(x.side, 0.0)
    foe = next((v for k, v in el.items() if k != x.side), 0.0)
    return [round(float(v), 4) for v in RS.tower_phat_record(x.state, x.side)[:8]] + [round(own, 2), round(foe, 2)]


def root_ctx(s) -> dict:
    """cf_diag: the root decision's context -- tick, snapshot (``snap``), the hand's card names (the 4 in hand), the enemy bodies on our half
    ([name, board x, board y]; my frame, forward = decreasing y)."""
    foe = []
    for e in s.state["entities"]:
        if int(e["side"]) != s.side:
            bx, by = raw_tiles(e, s.mirror)
            if by >= 16.0:
                foe.append([_norm(e.get("name", "")), round(bx, 1), round(by, 1)])
    hand = [_norm(h["name"]) for pl in s.state["players"] if int(pl["side"]) == s.side for h in pl["hand"]]
    return {"tick": int(s._cur[0]), "snap": snap(s), "hand": hand, "foe_half": foe}


def opp_meta(m) -> dict:
    """cf_diag: the match's opponent -- the league spec (opponent id / category / type, decks) and the drawn style."""
    spec = getattr(m, "spec", None) or {}
    o = spec.get("opp") or {}
    return {"opp": {k: o.get(k) for k in ("id", "cat", "type")}, "opp_deck": spec.get("opp_deck_name"),
            "learner_deck": spec.get("learner_deck_name"), "style": dict(m.opp.cfg.get("_opp_style") or {}),
            "opp_T": m.opp.cfg.get("T"), "opp_tau": m.opp.cfg.get("tau")}


def bait_seen(m) -> bool:
    """The opponent has played a log-bait card (archetypes.BAIT) by now: every play is public once it lands."""
    from pipeline.archetypes import BAIT
    return any(_norm(c) in BAIT for _, c in getattr(m.opp, "accepted", ()))


_COMBO_OPTS: dict = {}


def combo_options(value: float):
    """The DecisionOptions the combo trigger reads the Rocket + Tornado plan with: the measured rule set (window, drift, river,
    princess bonus), the combo wherever its pull gathers more than the best lone blast (rocket_tornado_lone combo), any half."""
    if value not in _COMBO_OPTS:
        from pipeline import decision_options as DO
        _COMBO_OPTS[value] = DO.DecisionOptions(
            rocket_tornado="on", rocket_value=float(value), rocket_value_mode="cost", rocket_value_min_y=0.0,
            rocket_value_hitbox="edge", rocket_tornado_window="measured", rocket_tornado_order="rocket",
            rocket_tornado_lone="combo", tornado_river="full", rocket_value_towers="on", rocket_tornado_lead="drift")
    return _COMBO_OPTS[value]


def combo_hit(s, allowed, c: dict):
    """decision_options.rocket_tornado_choice at learner side ``s``'s decision: (rocket slot, tornado slot, cell, plan, value,
    order) when a Rocket + Tornado combo starts now (both in hand, 9 elixir by the follow-up, a clump whose pull holds
    cf_combo_value and more than the best single blast), else None."""
    from pipeline import decision_options as DO
    names = slot_names(s)
    if "rocket" not in names or "tornado" not in names or not allowed.any():
        return None
    hit = DO.rocket_tornado_choice(combo_options(c["cf_combo_value"]), names, allowed, s._cur[1], s.cfg["grid"])
    return hit if hit is not None and hit[5] in ("rocket", "tornado") and hit[2] is not None else None


def drifted(bodies, bx: float, by: float) -> tuple[float, float]:
    """Board tile (bx, by) of a body walked toward my side (+y) at its catalog speed until a Rocket aimed there lands (two
    refinements, decision_options.rocket_lands_in): the speed of the nearest ``rocket_bodies`` row, unchanged when none is near."""
    from pipeline import decision_options as DO
    if not len(bodies):
        return bx, by
    j = int(np.argmin(np.hypot(bodies[:, 1] - bx, bodies[:, 2] - by)))
    if math.hypot(bodies[j, 1] - bx, bodies[j, 2] - by) > 1.5:
        return bx, by
    cy = by
    for _ in range(2):
        cy = min(by + float(bodies[j, 6]) * DO.rocket_lands_in(bx, cy), 31.5)
    return bx, cy


def cell_at(grid: str, bx: float, by: float) -> int:
    """The grid cell whose centre is nearest to board tile (bx, by)."""
    from pipeline import decision_options as DO
    x, y = DO.cell_centres_tiles(grid)
    return int(np.argmin(np.hypot(x - bx, y - by)))


def pull_centre(ux: float, uy: float, tx: float, ty: float, reach: float) -> tuple[float, float]:
    """The Tornado centre that drags a unit at (ux, uy) toward (tx, ty): the point toward it ``reach`` tiles from the unit (or
    the target itself when nearer), kept on the board."""
    d = math.hypot(tx - ux, ty - uy)
    f = min(reach, d)
    cx, cy = (ux + (tx - ux) / d * f, uy + (ty - uy) / d * f) if d > 1e-9 else (ux, uy)
    return min(max(cx, 0.5), 17.5), min(max(cy, 0.5), 31.5)


def redirect_target(s, c: dict) -> Optional[dict]:
    """The enemy ground unit a Tornado could redirect into OUR king while both our princesses stand: a mobile non-flying body
    on the bridge or our bank (board y >= 15: a Tornado holds a ground unit at the river) within cf_redirect_dist_tiles of our
    nearest princess, the nearest such one. -> {name, bx, by, king, princess, d} (tiles) or None."""
    from pipeline import decision_options as DO, vocab
    mine = [t for t in s.state["episode"]["crown_towers"] if int(t["side"]) == s.side and not t.get("destroyed") and t["hp"] > 0]
    pr = [raw_tiles(t, s.mirror) for t in mine if t.get("type") == "princess"]
    kg = [raw_tiles(t, s.mirror) for t in mine if t.get("type") == "king"]
    if len(pr) < 2 or not kg:
        return None
    air, fixed = DO.log_air_traits(), DO.immobile_keys()
    best = None
    for cls, bx, by, *_ in DO.rocket_bodies(s._cur[1], "cost"):
        if air.get(int(cls), (False,))[0] or vocab.base_key(vocab.UNIT_VOCAB[int(cls)]) in fixed or by < 15.0:
            continue
        d, p = min((math.hypot(bx - px, by - py), (px, py)) for px, py in pr)
        if d <= c["cf_redirect_dist_tiles"] and (best is None or d < best["d"]):
            best = {"name": _norm(vocab.UNIT_VOCAB[int(cls)]), "bx": float(bx), "by": float(by), "king": kg[0],
                    "princess": p, "d": float(d)}
    return best


# ------------------------------------------------------------------------------------------------------
# log-probs + candidates
# ------------------------------------------------------------------------------------------------------
def gate_logprob(z_gate: float, d: dict, cfg: dict, play: bool = True) -> float:
    """log P(gate open / closed) under the sampler (decision_options.decide, decode sample): sigmoid((z - logit(tau_row)) /
    T_gate), tau_row = the row's own gate_tau (tau_phase) else cfg tau, overflow-safe; 0.0 for a row whose gate was not
    sampled."""
    if not d.get("gate_sampled"):
        return 0.0
    tau = float(d.get("gate_tau", cfg["tau"]))
    T_gate = float(cfg.get("T_gate") or cfg.get("T", 0.5))
    x = (float(z_gate) - math.log(tau / (1.0 - tau))) / T_gate
    return -float(np.logaddexp(0.0, -x if play else x))


def _card_lp(heads, d: dict, T: float) -> np.ndarray:
    import torch
    with torch.no_grad():
        allowed = torch.from_numpy(np.asarray(d["allowed"], bool)).to(heads["card"].device)
        cl = heads["card"][0].clone().masked_fill(~allowed, float("-inf"))
        return torch.log_softmax(cl.double() / T, dim=-1).cpu().numpy()


def alt_logprobs(model, enc, heads, d: dict, slot: int, cell: int, cfg: dict, cell_logits=None) -> dict:
    """The behaviour policy's log-probs of PLAYING (slot, cell) -- or, slot < 0, of WAITING -- at a decision with forward
    (enc, heads) of ONE row and decision dict ``d`` (allowed, gate_sampled, gate_tau): the sampler's float64 tempered
    distributions (card softmax over allowed / T, cell softmax over 2304 / T), which rl_royale.policy_terms recomputes."""
    import torch
    z = float(heads["gate"].detach().cpu().numpy().astype(np.float64).reshape(-1)[0])
    if slot < 0:
        return {"lp_gate": gate_logprob(z, d, cfg, play=False), "lp_card": 0.0, "lp_cell": 0.0}
    T = float(cfg.get("T", 0.5))
    with torch.no_grad():
        if cell_logits is None:
            cell_logits = model.cell_logits(enc, torch.tensor([int(slot)], device=heads["card"].device))[0]
        px = torch.log_softmax(cell_logits.double() / T, dim=-1).cpu().numpy()
    return {"lp_gate": gate_logprob(z, d, cfg), "lp_card": float(_card_lp(heads, d, T)[int(slot)]),
            "lp_cell": float(px[int(cell)])}


def forward_one(s):
    """(enc, heads) of side ``s``'s decision row as the decide saw it (its ``_gen_row`` / ``_obs``; nothing re-observed)."""
    from pipeline import e1_eval as E
    model = s.model
    if isinstance(model, E.GenPolicy):
        enc, heads, _, _ = model.forward_batch([s._gen_row], s.cfg["device"])
    else:
        enc, heads, _, _ = E.model_forward_batch(model, *zip(*[s._obs]), device=s.cfg["device"])
    return enc, heads


def _slot_of(names, allowed, card) -> Optional[int]:
    return next((k for k in range(len(names)) if names[k] == card and allowed[k]), None)


class _Pol:
    """The decision's forward (computed once, on first use) + the policy's per-card cell logits (cached)."""

    def __init__(self, s, d):
        self.s, self.d, self._f, self._cl = s, d, None, {}

    def f(self):
        if self._f is None:
            self._f = forward_one(self.s)
        return self._f

    def cl(self, slot: int):
        import torch
        if slot not in self._cl:
            enc, heads = self.f()
            with torch.no_grad():
                self._cl[slot] = self.s.model.cell_logits(enc, torch.tensor([slot], device=heads["card"].device))[0]
        return self._cl[slot]

    def best_card(self, ok) -> Optional[int]:
        """The allowed slot (``ok`` mask) with the highest card logit, or None."""
        ok = np.asarray(ok, bool) & np.asarray(self.d["allowed"], bool)
        if not ok.any():
            return None
        z = self.f()[1]["card"][0].detach().double().cpu().numpy()
        return int(np.flatnonzero(ok)[np.argmax(z[ok])])

    def cand(self, kind: str, slot: int, where) -> Optional[dict]:
        """A play of ``slot`` at ``where`` (a cell, a [2304] mask -> the policy's argmax inside, "argmax"), or a wait
        (slot < 0), with its behaviour log-probs; None when the mask is empty."""
        import torch
        from pipeline import decision_options as DO
        enc, heads = self.f()
        if slot < 0:
            return {"kind": kind, "play": False, "slot": -1, "cell": -1,
                    **alt_logprobs(self.s.model, enc, heads, self.d, -1, -1, self.s.cfg)}
        cl = self.cl(slot)
        if isinstance(where, tuple):                       # ("clump", eligible): rocket_value_cell's aim inside the blast
            cell = DO.rocket_value_cell(cl, where[1])
        elif isinstance(where, str):
            cell = int(cl.argmax())
        elif isinstance(where, (int, np.integer)):
            cell = int(where)
        else:
            if not where.any():
                return None
            cell = int(cl.masked_fill(~torch.from_numpy(where).to(cl.device), float("-inf")).argmax())
        if not math.isfinite(float(cl[cell])):
            return None
        return {"kind": kind, "play": True, "slot": int(slot), "cell": int(cell),
                **alt_logprobs(self.s.model, enc, heads, self.d, slot, cell, self.s.cfg, cell_logits=cl)}


def sampled_alts(pol: _Pol, n: int, rng, seen: set) -> list[dict]:
    """``n`` actions drawn from the behaviour policy itself (gate, then card, then cell; tempered as the sampler), each
    distinct from ``seen`` (20 draws at most per action), with the cf RNG (never the policy's streams)."""
    import torch
    s, d = pol.s, pol.d
    enc, heads = pol.f()
    T = float(s.cfg.get("T", 0.5))
    z = float(heads["gate"].detach().cpu().numpy().astype(np.float64).reshape(-1)[0])
    p_open = math.exp(gate_logprob(z, d, s.cfg)) if d.get("gate_sampled") else 1.0
    pc = np.exp(_card_lp(heads, d, T))
    out = []
    for _ in range(n):
        for _try in range(20):
            if rng.random() >= p_open:
                key = (-1, -1)
            else:
                slot = int(rng.choice(len(pc), p=pc / pc.sum()))
                with torch.no_grad():
                    px = torch.softmax(pol.cl(slot).double() / T, dim=-1).cpu().numpy()
                key = (slot, int(rng.choice(len(px), p=px / px.sum())))
            if key not in seen:
                seen.add(key)
                a = pol.cand("sampled", key[0], key[1])
                if a is not None:
                    out.append(a)
                break
    return out


def candidates(m, s, d: dict, trig: str, c: dict) -> list[dict]:
    """[chosen] + the alternatives of trigger ``trig`` at learner side ``s``'s decision ``d`` (prepared, decided, not
    applied), distinct actions, at most cf_max_alts alternatives (module docstring)."""
    from pipeline import decision_options as DO
    allowed = np.asarray(d["allowed"], bool)
    names, kinds = slot_names(s), slot_kinds(s)
    grid = s.cfg["grid"]
    rk, xk = _slot_of(names, allowed, "rocket"), _slot_of(names, allowed, "xbow")
    troop = np.array(["SPELL" not in k for k in kinds])
    chosen = {"kind": "chosen", "play": bool(d["play"]), "slot": int(d["slot"]) if d["play"] else -1,
              "cell": int(d["cell"]) if d["play"] else -1, "lp_gate": float(d["lp_gate"]),
              "lp_card": float(d["lp_card"]), "lp_cell": float(d["lp_cell"])}
    if d.get("follow_ups"):                               # a rule-decided combo of the real decision (cfg rocket_tornado)
        chosen["follow_ups"] = [dict(f) for f in d["follow_ups"]]
    pol = _Pol(s, d)
    meta = (lambda **kw: {"meta": kw}) if c.get("cf_diag") else (lambda **kw: {})   # cf_diag: per-candidate facts for the P4 audit
    lead = (int(s._cur[0]), [], "drift") if c.get("cf_rocket_lead") == "drift" else None   # best_rocket_clump's lead argument
    seen = {(chosen["slot"], chosen["cell"], bool(chosen.get("follow_ups")))}
    if trig == "random":
        return [chosen] + sampled_alts(pol, c["cf_random_alts"], m.cf_state["rng"], seen)
    want = []                                             # (kind, slot, where); slot -1 = wait
    if d["play"] and trig in ("rocket_played", "wincon", "siege", "xbow_after_fail", "xbow", "log_bait", "rocket_tornado",
                              "tornado_redirect"):
        want.append(("wait", -1, None))
    if trig == "rocket_tornado":                          # combo vs the best lone blast (vs the policy's own choice / a wait)
        from pipeline import e1_eval as E
        hit = m.cf_state["combo_hit"]
        first, second = (hit[0], hit[1]) if hit[5] == "rocket" else (hit[1], hit[0])
        after, within = DO.rocket_tornado_timing(hit[3])
        want.append(("combo", first, hit[2], {"follow_ups": [E.follow_up_spec(second, hit[2], after, within)],
                                              **meta(value=float(hit[4]), plan=str(hit[3]))}))
        if rk is not None:
            value, elig = DO.best_rocket_clump(DO.rocket_bodies(s._cur[1], "cost"), grid, "edge", lead, 0.0,
                                               towers=DO.enemy_princesses_alive(s._cur[1]))
            if elig is not None and value >= c["cf_rocket_min_value"]:
                want.append(("rocket_clump", rk, ("clump", elig), meta(value=float(value))))
    if trig == "tornado_redirect":                        # a Tornado that drags the unit into our king vs elsewhere
        tg, tk = m.cf_state["redirect_target"], _slot_of(names, allowed, "tornado")
        reach = DO.tornado_radius_tiles() - 0.75
        want.append(("tornado_king", tk, cell_at(grid, *pull_centre(tg["bx"], tg["by"], *tg["king"], reach))))
        want.append(("tornado_on", tk, cell_at(grid, tg["bx"], tg["by"])))
    if trig == "rocket_played":
        sc = pol.best_card(np.arange(len(names)) != int(d["slot"]))
        if sc is not None:
            want.append(("second_card", sc, "argmax"))
    if trig in ("rocket", "xbow_after_fail") and rk is not None:
        bs = s._cur[1]
        if trig == "rocket":
            value, elig = DO.best_rocket_clump(DO.rocket_bodies(bs, "cost"), grid, "edge", lead, 0.0,
                                               towers=DO.enemy_princesses_alive(bs))
            if elig is not None and value >= c["cf_rocket_min_value"]:
                want.append(("rocket_clump", rk, ("clump", elig), meta(value=float(value))))
        hps = DO.enemy_princess_hps(s.state["episode"]["crown_towers"], s.side)
        if hps:
            weak = min(hps, key=lambda k: (hps[k], k))
            want.append(("rocket_princess", rk, DO.lethal_rocket_cell(weak, grid), meta(hp=float(hps[weak]))))
    if trig in ("wincon", "siege"):
        tg = m.cf_state["target"]
        bx, by = tg["bx"], tg["by"]
        if rk is not None:
            rx, ry = drifted(DO.rocket_bodies(s._cur[1], "cost"), bx, by) if lead is not None else (bx, by)
            want.append(("rocket_on", rk, siege_cells(rx, ry, grid, "SPELL", "rocket", c["cf_siege_radius_tiles"])))
        ok = troop & np.array([n not in NO_BUILDING_DAMAGE for n in names])
        tk = pol.best_card(ok)
        if trig == "siege" and tg.get("princess") is not None and tk is not None:
            want.append(("front", tk, front_cells(*tg["princess"], grid, c["cf_front_min_tiles"],
                                                    c["cf_front_max_tiles"])))
        if tk is not None:
            want.append(("troop_on", tk, siege_cells(bx, by, grid, kinds[tk], names[tk], c["cf_siege_radius_tiles"])))
        costs = getattr(s, "costs", None)
        if trig == "wincon" and costs is not None and (ok & allowed).any():
            ch = int(min(np.flatnonzero(ok & allowed), key=lambda k: (costs[k], k)))
            if ch != tk:
                want.append(("cheap_on", ch, siege_cells(bx, by, grid, kinds[ch], names[ch], c["cf_siege_radius_tiles"])))
    if trig in ("xbow_after_fail", "xbow") and xk is not None:
        reach = xbow_reach_cells(s, grid)
        x, y = DO.cell_centres_tiles(grid)
        want.append(("xbow_defensive", xk, (y >= TERRITORY_Y_TILES) & ~reach))
        if trig == "xbow" and d["play"]:
            want.append(("xbow_other_lane", xk, reach & ((x < 9.0) != (x[int(d["cell"])] < 9.0))))
        if trig == "xbow_after_fail":
            want.append(("xbow_reach", xk, reach))
    if trig == "idle_full":
        b = pol.best_card(np.ones(len(names), bool))
        if b is not None:
            want.append(("play_now", b, "argmax"))
    out = [chosen]
    for kind, slot, where, *extra in want:
        if len(out) > c["cf_max_alts"]:
            break
        a = pol.cand(kind, slot, where)
        if a is not None:
            if extra:
                a.update(extra[0])
            key = (a["slot"], a["cell"], bool(a.get("follow_ups")))
            if key not in seen:
                seen.add(key)
                out.append(a)
    return out


# ------------------------------------------------------------------------------------------------------
# triggers + the actor's runner
# ------------------------------------------------------------------------------------------------------
def new_state(s) -> dict:
    """A match's cf bookkeeping (on the real SelfPlayMatch as ``cf_state``): a trigger RNG of its own (the policy's
    streams are never drawn), last sample tick per trigger, X-Bow watch, the samples, costs."""
    seed = zlib.crc32(f"{s.tag}:cf:{s.k}:{int(s.cfg.get('rollout_index', 0))}:{int(s.cfg.get('update', 0))}".encode())
    return {"seed": seed, "rng": np.random.default_rng(seed), "n": Counter(), "capped": Counter(), "fired": Counter(),
            "last": {}, "target": None, "xb": {}, "xb_failed": 0, "xb_fail_tick": -10 ** 9, "samples": [],
            "wall_s": 0.0, "fork_ticks": 0, "decisions": 0, "k": int((s.cfg.get("cf") or {}).get("cf_k", 2)),
            "cond": Counter(), "cond_ticks": {} if os.environ.get("CF_DUMP") else None}


def match_record(st: dict) -> dict:
    """SelfPlayMatch.result()'s ``cf`` entry (picklable, JSON-able). ``cond`` = decisions per trigger whose condition held
    (before the gap / probability draw); ``cond_ticks`` (only with the CF_DUMP env var, the pilot) = those decisions' ticks,
    for the offline budget model (pilot_report.py: samples per match and fork ticks at any cf_p)."""
    out = {"samples": st["samples"], "wall_s": round(st["wall_s"], 3), "triggers": dict(st["n"]),
           "fired": dict(st["fired"]), "capped": dict(st["capped"]), "decisions": st["decisions"],
           "fork_ticks": st["fork_ticks"], "xbow_failed": st["xb_failed"], "k": st["k"], "cond": dict(st["cond"])}
    if st.get("cond_ticks") is not None:
        out["cond_ticks"] = st["cond_ticks"]
    if st.get("opp") is not None:
        out["opp"] = st["opp"]
    return out


def triggers(m, s, d: dict, c: dict) -> list[str]:
    """The triggers firing at learner decision ``d`` of match ``m``, in TRIGGERS order (draws only the match's own cf
    RNG). Keeps the X-Bow watch current at every decision; reads the engine state only when an enemy building or one of
    our X-Bows is on the board. Sets ``m.cf_state["target"]`` for wincon / siege."""
    st, env, tick = m.cf_state, m.env, int(s._cur[0])
    ents = s.state["entities"]
    es = None
    if st["xb"] or any(int(e["side"]) == s.side and _norm(e.get("name", "")) == "xbow" for e in ents):
        es = env.core.state()
        xbow_watch(st, env, s.side, tick, es)
    allowed = np.asarray(d["allowed"], bool)
    if d.get("forced") or not d.get("gate_sampled") or not allowed.any():
        return []
    names = slot_names(s)
    rk, xk = _slot_of(names, allowed, "rocket"), _slot_of(names, allowed, "xbow")
    played = names[int(d["slot"])] if d["play"] else None
    cond = {"rocket_played": played == "rocket", "rocket": rk is not None and played != "rocket",
            "xbow_after_fail": xk is not None and st["xb_failed"] > 0
            and tick - st["xb_fail_tick"] <= c["cf_xbow_fail_window_ticks"],
            "xbow": played == "xbow" and bool(xbow_reach_cells(s, s.cfg["grid"])[int(d["cell"])]),
            "idle_full": not d["play"] and own_elixir(s) >= c["cf_full_elixir"],
            "log_bait": played == "log" and bait_seen(m), "random": True}
    wc = [e for e in ents if int(e["side"]) != s.side and _norm(e.get("name", "")) in WINCON]
    wc = [(e, raw_tiles(e, s.mirror)) for e in wc]
    wc = [(e, xy) for e, xy in wc if xy[1] >= 16.0]       # on our half (my frame: forward = decreasing y)
    cond["wincon"] = bool(wc)
    sg = None
    if any(int(e["side"]) != s.side and int(e.get("kind", -1)) in (1, 12) for e in ents):
        sg = siege_target(env, s.side, es)
    cond["siege"] = sg is not None
    if c["cf_p"]["rocket_tornado"] > 0:                   # opt-in triggers: read only when their probability is set
        st["combo_hit"] = combo_hit(s, allowed, c)
        cond["rocket_tornado"] = st["combo_hit"] is not None
    tg = None
    if c["cf_p"]["tornado_redirect"] > 0 and _slot_of(names, allowed, "tornado") is not None:
        tg = redirect_target(s, c)
    cond["tornado_redirect"] = tg is not None
    out = []
    for t in TRIGGERS:
        if t in OPT_IN and c["cf_p"][t] <= 0:
            continue
        if cond[t]:
            st["cond"][t] += 1
            if st["cond_ticks"] is not None:
                st["cond_ticks"].setdefault(t, []).append(tick)
        if cond[t] and tick - st["last"].get(t, -10 ** 9) >= c["cf_gap_ticks"] and st["rng"].random() < c["cf_p"][t]:
            out.append(t)
    if "wincon" in out:                                   # the deepest one into our half (largest y)
        e, (bx, by) = max(wc, key=lambda z: z[1][1])
        st["wincon_target"] = {"name": _norm(e["name"]), "bx": bx, "by": by}
    if "siege" in out:
        bx, by = board_tiles(sg["x"], sg["y"], s.mirror)
        st["siege_target"] = {**sg, "bx": bx, "by": by,
                              "princess": None if sg["princess"] is None else board_tiles(*sg["princess"], s.mirror)}
    if "tornado_redirect" in out:
        st["redirect_target"] = tg
    st["fired"].update(out)
    return out


def trigger_k(c: dict, trig: str) -> int:
    """Continuations K of a sample of trigger ``trig``: cf_k_by[trig] else cf_k."""
    return int((c.get("cf_k_by") or {}).get(trig, c["cf_k"]))


def trigger_horizon(c: dict, trig: str) -> int:
    """Fork horizon (ticks) of a sample of trigger ``trig``: cf_horizon_by[trig] else cf_horizon_ticks."""
    return int((c.get("cf_horizon_by") or {}).get(trig, c["cf_horizon_ticks"]))


def reward(word: str) -> float:
    return {"win": 1.0, "loss": -1.0}.get(word, 0.0)


def reseed(f, seed: int, k: int) -> None:
    """Continuation ``k``'s common random numbers: every top-level numpy Generator / random.Random of both fork sides
    replaced by one seeded from (seed, k, side, attribute) -- the same for every candidate of the sample. ponytail: RNGs
    nested inside sub-objects and the engine's own stay copied (common to all k: a little less noise between k)."""
    for s in (f.learner, f.opp):
        for name, v in list(s.__dict__.items()):
            if isinstance(v, (np.random.Generator, random.Random)):
                h = zlib.crc32(f"{seed}:{k}:{s.side}:{name}".encode())
                s.__dict__[name] = np.random.default_rng(h) if isinstance(v, np.random.Generator) else random.Random(h)


class Runner:
    """One per ``e1_eval.run_selfplay_batch`` call with cfg["cf"] (the actor): ``hook(live, todo)`` after every round's
    decide, before any apply. ``make_env`` = the batch's own env factory (forks run on pooled copies of it). ``phi`` =
    the state potential of the return (None = 0; see the module docstring)."""

    def __init__(self, make_env, c: dict, phi=None):
        self.make_env, self.c, self.phi = make_env, c, phi
        self.pool: list = []
        self.last_forks: list = []                        # the last fork set (tests)

    def hook(self, live, todo) -> None:
        by = {id(m.learner): m for m in live}
        c = self.c
        for s, p, d in todo:
            m = by.get(id(s))
            if m is None:
                continue
            t0 = time.perf_counter()
            if getattr(m, "cf_state", None) is None:
                m.cf_state = new_state(s)
                if c.get("cf_diag"):
                    m.cf_state["opp"] = opp_meta(m)
            st = m.cf_state
            st["decisions"] += 1
            cands, trig = None, None
            for t in triggers(m, s, d, c):
                if t in ("wincon", "siege"):
                    st["target"] = st[f"{t}_target"]
                cands = candidates(m, s, d, t, c)
                if len(cands) > 1:
                    trig = t
                    break
            tick = int(s._cur[0])
            to_end = tick >= END_TICK - c["cf_end_ticks"]
            if trig is not None:
                kk, hh = trigger_k(c, trig), trigger_horizon(c, trig)
                est = kk * len(cands) * (max(END_TICK - tick, 1) if to_end else hh)
                if st["fork_ticks"] + est > c["cf_cap_ticks"]:
                    st["capped"][trig] += 1
                    trig = None
            if trig is None:
                st["wall_s"] += time.perf_counter() - t0
                continue
            st["n"][trig] += 1
            st["last"][trig] = tick
            ctx = root_ctx(s) if c.get("cf_diag") else None
            audit = bool(st["rng"].random() < c["cf_audit_p"]) and not to_end
            entries = [(x, px, dx) for x, px, dx in todo if x is m.learner or x is m.opp]
            seed = zlib.crc32(f"{st['seed']}:{len(st['samples'])}".encode())
            res = self.rollouts(m, entries, cands, seed, audit, k=kk, horizon=hh)
            for a, r in zip(cands, res["cands"]):
                a.update(r)
            st["fork_ticks"] += res["fork_ticks"]
            wall = time.perf_counter() - t0
            st["wall_s"] += wall
            smp = {"row": len(s.traj), "tick": tick, "trigger": trig, "audit": audit,
                   "to_end": to_end, "cands": cands, "fork_ticks": res["fork_ticks"],
                   "wall_s": round(wall, 3),
                   "target": dict(st["target"]) if trig in ("wincon", "siege") else None}
            if c.get("cf_diag"):
                smp["ctx"] = ctx
                if trig == "tornado_redirect":
                    smp["target"] = dict(st["redirect_target"])
            st["samples"].append(smp)

    def phi_of(self, x) -> float:
        """Phi(s) of a stopped learner side: ``self.phi`` (tests) or the config's state potential (cf["phi_mode"]), else 0."""
        if self.phi is not None:
            return float(self.phi(x))
        mode = self.c.get("phi_mode")
        if not mode:
            return 0.0
        from pipeline import reward_shaping as RS
        row = RS.state_record(mode, x.state, x.side, x.env, {})
        return float(RS.state_phi(mode, [row], self.c.get("phi_params") or {})[0])

    def _q(self, sides, ticks, root) -> list[float]:
        """gamma^(t - root) (Phi + v_scale v_net) at each stopped learner side (prepared, at its decision tick)."""
        return [q for q, _, _ in self._qparts(sides, ticks, root)]

    def _qparts(self, sides, ticks, root) -> list[tuple]:
        """(Q, Phi, v_scale v_net) per stopped side: Q as ``_q`` (the stored Phi / v are the UNDISCOUNTED parts)."""
        import torch
        from pipeline import e1_eval as E
        from pipeline.rl_royale import value_scalar
        model, dev = sides[0].model, sides[0].cfg["device"]
        if isinstance(model, E.GenPolicy):
            enc, _, _, _ = model.forward_batch([x.gen_row(model) for x in sides], dev)
            net = model.model
        else:
            enc, _, _, _ = E.model_forward_batch(model, *zip(*[x._obs for x in sides]), device=dev)
            net = model
        with torch.no_grad():
            v = value_scalar(net.value_head(enc["g"])).cpu().numpy()
        g, sc = float(self.c.get("gamma_tick", 1.0)), float(self.c.get("v_scale", 1.0))
        out = []
        for x, t, vi in zip(sides, ticks, v):
            ph = self.phi_of(x)
            out.append((g ** (t - root) * (ph + sc * float(vi)), ph, sc * float(vi)))
        return out

    def rollouts(self, m, entries, cands, seed: int, audit: bool = False, k: Optional[int] = None,
                 horizon: Optional[int] = None) -> dict:
        """Fork ``m`` (its due sides prepared and decided as ``entries`` [(side, p, decision)], nothing applied) into K x C
        copies (continuation-major; k >= 1 reseeded by ``reseed``), apply the root (the learner's decision replaced by each
        candidate's action), then lockstep rounds (``e1_eval.selfplay_decide`` over every copy's due sides) until each
        copy's learner decides at >= root + horizon (-> ``_q``) or its match ends (-> gamma^(T - root) R_win). ``audit``:
        the continuation-0 copies run on to the match end (``q_end``; their ``q`` stays the horizon value). ``m`` is never
        touched (its engine is only read by save_state). -> {"cands": [{q, end, terminal, q_end}], "fork_ticks"}."""
        from pipeline import e1_eval as E
        from pipeline.search_s0 import fork_into
        c, env, L = self.c, m.env, m.learner
        K, C = int(k or c["cf_k"]), len(cands)
        while len(self.pool) < K * C:
            self.pool.append(self.make_env())
        blob = env.core.save_state()
        root = int(env.tick)
        stop = 10 ** 9 if root >= END_TICK - c["cf_end_ticks"] else root + int(horizon or c["cf_horizon_ticks"])
        g = float(c.get("gamma_tick", 1.0))
        forks, meta = [], []
        for k in range(K):
            for i, a in enumerate(cands):
                f = fork_into(m, self.pool[len(forks)], blob, fresh=FORK_FRESH)
                if k:
                    reseed(f, seed, k)
                for s, p, d in entries:
                    if s is not L:
                        f.opp.apply(p, dict(d))
                    elif i == 0:
                        f.learner.apply(p, dict(d))
                    else:                                     # (a decided second play belongs to the decision's card)
                        f.learner.apply(p, {**{x: v for x, v in d.items() if x != "follow_ups"}, "play": a["play"],
                                            "slot": a["slot"], "cell": a["cell"], "why": "cf", "lp_gate": a["lp_gate"],
                                            "lp_card": a["lp_card"], "lp_cell": a["lp_cell"],
                                            **({"follow_ups": copy.deepcopy(a["follow_ups"])} if a.get("follow_ups") else {})})
                forks.append(f)
                meta.append((i, k))
        out = [{"q": [None] * K, "end": [None] * K, "terminal": [None] * K, "q_end": None} for _ in cands]
        diag = bool(c.get("cf_diag"))

        n0 = (len(m.learner.accepted), len(m.opp.accepted))

        def put_dg(i, k, key, part, f):                       # cf_diag: Phi / critic parts + snapshot + plays since the root
            slot = out[i].setdefault("dg", {}).setdefault(key, {"phi": [None] * K, "v": [None] * K, "snap": [None] * K,
                                                                 "np": [None] * K})
            slot["phi"][k], slot["v"][k], slot["snap"][k] = float(part[1]), float(part[2]), snap(f.learner)
            slot["np"][k] = [len(f.learner.accepted) - n0[0], len(f.opp.accepted) - n0[1]]   # own, foe plays landed since the root
        sweep = [] if stop >= 10 ** 9 else sorted(h for h in (c.get("cf_horizon_sweep") or ()) if 0 < int(h) < stop - root)
        if sweep:                                             # Q also read at these earlier learner decisions ("qh")
            for o in out:
                o["qh"] = {str(h): [None] * K for h in sweep}
        seen = [set() for _ in forks]
        extend = {fi for fi, (i, k) in enumerate(meta) if audit and k == 0}
        active, done_h = list(range(len(forks))), set()
        while active:
            due, stopping, sweeping = [], [], []
            for fi in list(active):
                f = forks[fi]
                i, k = meta[fi]
                got = f.due()
                if not got:                                   # over: the terminal reward
                    T = int(f.env.tick)
                    q = g ** (T - root) * reward(f.learner._outcome()[0])
                    for h in sweep:                           # ended before that stop: the terminal value, as for q
                        if h not in seen[fi]:
                            out[i]["qh"][str(h)][k] = q
                    if fi in done_h:
                        out[i]["q_end"] = q
                    else:
                        out[i]["q"][k], out[i]["end"][k], out[i]["terminal"][k] = q, T, True
                        if fi in extend:
                            out[i]["q_end"] = q
                    active.remove(fi)
                    continue
                for s in got:
                    s.prepare()
                if sweep and f.learner in got:
                    hs = [h for h in sweep if h not in seen[fi] and int(f.env.tick) >= root + h]
                    if hs:
                        sweeping.append((fi, hs))
                        seen[fi].update(hs)
                if f.learner in got and int(f.env.tick) >= stop and fi not in done_h:
                    stopping.append(fi)
                    if fi not in extend:
                        active.remove(fi)
                        continue
                    done_h.add(fi)
                due += got
            if stopping:
                qs = self._qparts([forks[fi].learner for fi in stopping], [int(forks[fi].env.tick) for fi in stopping], root)
                for fi, part in zip(stopping, qs):
                    i, k = meta[fi]
                    out[i]["q"][k], out[i]["end"][k], out[i]["terminal"][k] = float(part[0]), int(forks[fi].env.tick), False
                    if diag:
                        put_dg(i, k, "stop", part, forks[fi])
            if sweeping:
                qs = self._qparts([forks[fi].learner for fi, _ in sweeping], [int(forks[fi].env.tick) for fi, _ in sweeping], root)
                for (fi, hs), part in zip(sweeping, qs):
                    i, k = meta[fi]
                    for h in hs:
                        out[i]["qh"][str(h)][k] = float(part[0])
                        if diag:
                            put_dg(i, k, str(h), part, forks[fi])
            if due:
                for s, p, d in E.selfplay_decide(due):
                    s.apply(p, d)
        for fi, f in enumerate(forks):                        # a scripted second play: did it fire? (follow_n: fired / cancelled_<why>)
            i, k = meta[fi]
            if cands[i].get("follow_ups"):
                out[i].setdefault("follow", [None] * K)[k] = dict(getattr(f.learner, "follow_n", None) or {})
        self.last_forks = forks
        return {"cands": out, "fork_ticks": int(sum(int(f.env.tick) - root for f in forks))}


# ------------------------------------------------------------------------------------------------------
# the learner side (pure numpy: shared with the fast loop)
# ------------------------------------------------------------------------------------------------------
def sample_adv(cands: list[dict]) -> np.ndarray:
    """[C, K] per-continuation advantages A[i, k] = q[i, k] - mean_j q[j, k] (the K continuations are CRN-paired across
    candidates). The training advantage is the row mean, = Q_i - mean_j Q_j."""
    q = np.asarray([a["q"] for a in cands], dtype=np.float64)
    return q - q.mean(axis=0, keepdims=True)


def reliability(advs: list[np.ndarray]) -> dict:
    """Over [C, K] advantage arrays (one trigger, one batch): signal var = mean covariance between two different
    continuations' advantages (each candidate a draw), total = var of the K-mean. -> {n (candidate values), factor =
    clip(signal / total, 0, 1) (the empirical-Bayes shrink of the K-mean toward 0), snr = sqrt(signal / noise) of the
    K-mean (noise = total - signal), r_split (K = 2: the correlation of the two continuations' advantages)}."""
    if not advs:
        return {"n": 0, "factor": None, "snr": None, "r_split": None}
    kmin = min(a.shape[1] for a in advs)            # triggers may run different K (cf_k_by): the pooled stat uses the first kmin
    A = np.concatenate([a[:, :kmin] for a in advs], axis=0)
    n, K = A.shape
    out = {"n": int(n), "factor": None, "snr": None, "r_split": None}
    if K < 2 or n < 3:
        return out
    m = A.mean(axis=1)
    total = float(np.mean(m ** 2))                     # advantages are centred per sample: mean 0 by construction
    sig = float(np.mean([np.mean(A[:, a] * A[:, b]) for a in range(K) for b in range(K) if a != b]))
    out["factor"] = float(np.clip(sig / total, 0.0, 1.0)) if total > 0 else 0.0
    noise = total - sig
    out["snr"] = float(math.sqrt(max(sig, 0.0) / noise)) if noise > 0 else (math.inf if sig > 0 else 0.0)
    if K == 2:
        sd = math.sqrt(float(np.mean(A[:, 0] ** 2)) * float(np.mean(A[:, 1] ** 2)))
        out["r_split"] = float(np.mean(A[:, 0] * A[:, 1]) / sd) if sd > 0 else None
    return out


def batch_advantages(samples: list[dict], c: dict) -> tuple[list[np.ndarray], dict]:
    """The used samples of one batch -> (per sample the [C] training advantage, shrunk by its trigger's reliability
    factor when cf_shrink and the trigger has >= cf_shrink_min candidate values, else by the pooled factor when that has
    them, else unshrunk), {trigger: reliability}."""
    adv = [sample_adv(s["cands"]) for s in samples]
    by: dict = {}
    for s, a in zip(samples, adv):
        by.setdefault(s["trigger"], []).append(a)
    rel = {t: reliability(v) for t, v in sorted(by.items())}
    pooled = reliability(adv)
    out = []
    for s, a in zip(samples, adv):
        f = 1.0
        if c.get("cf_shrink", True):
            r = rel[s["trigger"]]
            if r["n"] >= c["cf_shrink_min"] and r["factor"] is not None:
                f = r["factor"]
            elif pooled["n"] >= c["cf_shrink_min"] and pooled["factor"] is not None:
                f = pooled["factor"]
        out.append(f * float(c.get("cf_adv_scale", 1.0)) * a.mean(axis=1))
    return out, {**rel, "_pooled": pooled}


def slope_audit(samples: list[dict]) -> dict:
    """The critic-slope audit over audit samples: OLS slope of the terminal return (q_end) on the horizon return (the
    continuation-0 q) over candidates that stopped at the horizon (not terminal), levels and within-sample differences
    (candidate i minus candidate 0). PLAN band [0.7, 1.3]."""
    x, y, dx, dy = [], [], [], []
    for s in samples:
        if not s.get("audit"):
            continue
        cs = [a for a in s["cands"] if a.get("q_end") is not None and not a["terminal"][0]]
        x += [a["q"][0] for a in cs]
        y += [a["q_end"] for a in cs]
        if len(cs) == len(s["cands"]) and len(cs) > 1:
            dx += [a["q"][0] - cs[0]["q"][0] for a in cs[1:]]
            dy += [a["q_end"] - cs[0]["q_end"] for a in cs[1:]]

    def ols(a, b):
        a, b = np.asarray(a, float), np.asarray(b, float)
        if len(a) < 3 or a.var() == 0:
            return {"n": int(len(a)), "slope": None, "se": None}
        sl = float(np.cov(a, b, bias=True)[0, 1] / a.var())
        res = b - b.mean() - sl * (a - a.mean())
        se = float(math.sqrt(float(np.sum(res ** 2)) / (len(a) - 2) / (len(a) * a.var())))
        return {"n": int(len(a)), "slope": sl, "se": se}
    return {"levels": ols(x, y), "diffs": ols(dx, dy)}


def _agg(v) -> dict:
    v = np.asarray(v, dtype=np.float64)
    return {"n": int(len(v)), "a_mean": float(v.mean()) if len(v) else None,
            "a_abs_mean": float(np.abs(v).mean()) if len(v) else None,
            "pos_share": float((v > 0).mean()) if len(v) else None}


def batch_stats(results: list[dict], used: list[dict], adv: list[np.ndarray], rel: dict, rows_added: int) -> dict:
    """Per-update cf monitors: matches with / without a cf record (without = an actor that ran no cf code), samples per
    trigger (fired / capped too), the training advantage (after shrink, value units) of the chosen action and of the
    alternatives by kind, the per-trigger reliability (n = candidate values), fork ticks per match tick (the cost in
    engine ticks) and fork wall seconds per match, the audit slopes."""
    recs = [r["cf"] for r in results if "cf" in r]
    trig, fired, capped = Counter(), Counter(), Counter()
    for x in recs:
        trig.update(x["triggers"])
        fired.update(x.get("fired", {}))
        capped.update(x.get("capped", {}))
    chosen = [float(a[0]) for a in adv]
    by_kind: dict = {}
    for s, a in zip(used, adv):
        for cnd, ai in zip(s["cands"][1:], a[1:]):
            by_kind.setdefault(cnd["kind"], []).append(float(ai))
    allsamples = [smp for x in recs for smp in x["samples"]]
    mt = sum(int(r.get("end_tick") or 0) for r in results if "cf" in r)
    ft = sum(int(x.get("fork_ticks", 0)) for x in recs)
    wall = [x["wall_s"] for x in recs]
    return {"matches": len(recs), "matches_missing": len(results) - len(recs), "triggers": dict(trig),
            "fired": dict(fired), "capped": dict(capped), "samples": len(allsamples), "used": len(used),
            "rows": int(rows_added), "chosen": _agg(chosen), "by_kind": {k: _agg(v) for k, v in sorted(by_kind.items())},
            "reliability": rel, "fork_ticks_per_match_tick": ft / mt if mt else None,
            "wall_s_per_match": float(np.mean(wall)) if wall else None, "audit": slope_audit(allsamples)}
    # (no share of the matches' own wall_s: in-flight matches interleave, so a match's wall counts the others' time)
