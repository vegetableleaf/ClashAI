"""Counterfactual credit from SIM forks (owner 10-26; rl_royale ``cf_credit``, opt-in: absent / null / false = the trainer
exactly as before, same config hash, same rows).

Why: the live model never Rocket-cycles, rarely Rockets on defence, leaves enemy siege buildings (Mortar, X-Bow) to lock and
pummel a tower, and repeats X-Bows MORE after a failed lock (live: 39% within 30 s vs 10.5% after a locked one). Hand-made
reward terms for these were exploitable (paying a Rocket on a win condition also pays Rocketing a lone Golem). Instead, at
selected learner decisions of a PPO rollout the actor forks the SIM state (search_s0.fork_into: RoyaleSim save_state /
load_state into pooled engines + deep copies of the env's and both sides' python state, RNGs included), plays the policy's
ACTUAL decision in one copy (the baseline) and an ALTERNATIVE action in each other, rolls every copy forward with the same
policies (learner: the rollout's own sampler on the same weights; opponent: the match's real opponent, its own model / cfg /
decode), and compares the learner critic's value where each copy stops:
    DeltaQ(alt) = V(alt end) - V(baseline end)
V = v_scale x value_scalar(value head) at the learner's first decision at or after root + cf_horizon_ticks -- the same row
kind GAE values (``v_scale`` = shaping_critic_scale under the residual critic with Phi = 0, else 1) -- or the terminal reward
(+1 / -1 / 0) when the copy's match ended first. A Rocket that truly helps there earns credit; one that does not, does not.

Random numbers: every fork starts from a deep copy of the real match's RNG states (rng_behave, rng_obs, rng_ability, ...)
and engine state (its Rng included), so the baseline copy replays the real continuation draw for draw (pipeline/tests/
test_cf_credit.py measures it), and an alternative shares the streams until the decisions diverge.

Triggers (per learner decision of a rollout; each with its own per-match budget and sampling probability):
  rocket_played    the policy plays its Rocket now                    (cf_rocket_played_per_match, probability 1)
  rocket           Rocket in hand and affordable, not played           (cf_rocket_per_match, cf_rocket_p)
  siege            an enemy building alive and locked on one of our crown towers (engine target_uid), or an enemy X-Bow /
                   Mortar within reach of one (centre to centre <= decision_options.XBOW_REACH_TILES)
                                                                       (cf_siege_per_match, cf_siege_p, >= cf_siege_gap_ticks
                                                                        after the last siege trigger)
  xbow_after_fail  X-Bow in hand and affordable within cf_xbow_fail_window_ticks after one of our REACH X-Bows (placed within
                   XBOW_REACH_TILES of an enemy crown tower) died without ever locking a crown tower (``xbow_watch``)
                                                                       (cf_xbow_fail_per_match, probability 1)
  xbow             X-Bow in hand and affordable                        (cf_xbow_per_match, cf_xbow_p); both X-Bow triggers
                                                                        >= cf_xbow_gap_ticks after the last one
Alternatives (concrete actions; one equal to the baseline action is dropped):
  rocket_clump     Rocket at the best troop-value blast (decision_options.best_rocket_clump on the decision's own look-ahead
                   board, any half, never covering the enemy king, + the princess-in-blast value; >= cf_rocket_min_value
                   elixir), the policy's cell inside that blast (decision_options.rocket_value_cell)
  rocket_princess  Rocket at the lowest-HP alive enemy princess (decision_options.lethal_rocket_cell)
  siege_<card>     each affordable card that can hurt a building (not the Tornado: buildings are immobile, its pull is all
                   it does) ON the building: Rocket -- cells within cf_siege_radius_tiles of it that do not cover the
                   enemy king; any other card -- own-territory cells (y >= TERRITORY_Y_TILES) within cf_siege_radius_tiles
                   of the territory's nearest point to it
  front_<card>     each affordable non-spell card IN FRONT of the threatened princess (pro-style distraction: pros answer
                   an in-range Mortar with Knight / Tesla / Skeletons / Ice Wizard ~7 tiles in front within ~2 s, the
                   Mortar itself only 12% of the time): own-territory cells of that princess's lane, nearer the river than
                   it, cf_front_min_tiles..cf_front_max_tiles from it
  xbow_cell        X-Bow at the policy's own X-Bow cell (its cell argmax)
  wait             the gate closed (do not play now), whenever the baseline plays: a played Rocket / X-Bow / answer is
                   compared with not playing it
The policy's own cell head picks the cell inside every restricted set (argmax). Each alternative becomes an extra PPO row at
its decision (rl_royale collate): the decision's inputs, the alternative's action, its log-prob under the behaviour policy
(``alt_logprobs``: the sampler's own tempered gate x card x cell) and advantage cf_w x clip(DeltaQ / sd, -cf_clip, cf_clip),
sd = the std of the same batch's real-row GAE advantages before their normalisation (so cf_w 1 weighs an alternative row like
a real one); kept out of the value loss, the KL terms and GAE."""
from __future__ import annotations

import math
import time
import zlib
from collections import Counter
from typing import Optional

import numpy as np

DEFAULTS = {"cf_horizon_ticks": 300, "cf_w": 1.0, "cf_clip": 3.0,
            "cf_rocket_p": 0.03, "cf_rocket_per_match": 3, "cf_rocket_played_per_match": 4, "cf_rocket_min_value": 2.0,
            "cf_siege_p": 0.25, "cf_siege_per_match": 3, "cf_siege_gap_ticks": 100, "cf_siege_radius_tiles": 2.0,
            "cf_front_min_tiles": 5.0, "cf_front_max_tiles": 8.0,
            "cf_xbow_p": 0.03, "cf_xbow_per_match": 2, "cf_xbow_fail_per_match": 4, "cf_xbow_fail_window_ticks": 600,
            "cf_xbow_gap_ticks": 100}
KEYS = ("cf_credit",) + tuple(DEFAULTS)
INTS = ("cf_horizon_ticks", "cf_rocket_per_match", "cf_rocket_played_per_match", "cf_siege_per_match", "cf_siege_gap_ticks",
        "cf_xbow_per_match", "cf_xbow_fail_per_match", "cf_xbow_fail_window_ticks", "cf_xbow_gap_ticks")
SIEGE_NAMES = ("xbow", "mortar")
NO_BUILDING_DAMAGE = ("tornado",)     # ponytail: the icebow deck's one spell that cannot hurt a building; other decks' pull /
#                                       buff spells would need their own entry (the learner plays icebow: league share 1.0)
TERRITORY_Y_TILES = 17.0              # my frame: own troop territory starts at row 17 (decision_options.LOG_CAST_Y_TILES 17.5
#                                       is that row's centre); ponytail: an opened pocket is not used
FORK_FRESH = ("traj",)                # side attributes a fork starts empty (search_s0.fork_into ``fresh``)
TILE = 18000.0                        # RoyaleSim units per tile (royale_env.SCALE x 1000)


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def cf_cfg(cfg: dict) -> Optional[dict]:
    """The cf keys of a config, validated (SystemExit naming the bad key): None when ``cf_credit`` is absent / null / false
    (the other cf keys must then be unset), else {key: value} with DEFAULTS filled. Needs advantage gae and league; refuses
    the paths the alternative rows are not wired for (branch_gate, posture_head, critic_ctx, kl_ref_gate_max_elixir) and a
    non-zero Phi (shaping other than none, princess_redirect potential): the fork value is v_scale x v_net, no Phi term."""
    on = cfg.get("cf_credit")
    if on is None or on is False:
        stray = [k for k in DEFAULTS if cfg.get(k) is not None]
        if stray:
            raise SystemExit(f"bad cf_credit config: {stray} set without cf_credit on")
        return None
    c = {k: (v if cfg.get(k) is None else cfg[k]) for k, v in DEFAULTS.items()}
    bad = [] if on is True else [f"cf_credit must be on / off (a bool), got {on!r}"]
    for k in INTS:
        lo = 1 if k == "cf_horizon_ticks" else 0
        if not (isinstance(c[k], int) and not isinstance(c[k], bool) and c[k] >= lo):
            bad.append(f"{k} must be an integer >= {lo}, got {c[k]!r}")
    for k in ("cf_w", "cf_rocket_min_value", "cf_front_min_tiles"):
        if not (_num(c[k]) and c[k] >= 0):
            bad.append(f"{k} must be a finite number >= 0, got {c[k]!r}")
    for k in ("cf_clip", "cf_siege_radius_tiles", "cf_front_max_tiles"):
        if not (_num(c[k]) and c[k] > 0):
            bad.append(f"{k} must be a finite number > 0, got {c[k]!r}")
    if _num(c["cf_front_min_tiles"]) and _num(c["cf_front_max_tiles"]) and c["cf_front_min_tiles"] > c["cf_front_max_tiles"]:
        bad.append(f"cf_front_min_tiles {c['cf_front_min_tiles']} > cf_front_max_tiles {c['cf_front_max_tiles']}")
    for k in ("cf_rocket_p", "cf_siege_p", "cf_xbow_p"):
        if not (_num(c[k]) and 0 <= c[k] <= 1):
            bad.append(f"{k} must be in [0, 1], got {c[k]!r}")
    if cfg.get("advantage", "match_loo") != "gae":
        bad.append(f"cf_credit needs advantage gae (refusing {cfg.get('advantage', 'match_loo')!r})")
    if not cfg.get("league"):
        bad.append("cf_credit needs league true (the forks are self-play matches)")
    for k in ("branch_gate", "posture_head", "critic_ctx", "kl_ref_gate_max_elixir"):
        if cfg.get(k) not in (None, False):
            bad.append(f"cf_credit with {k} is not supported (the alternative rows are not wired for it)")
    if cfg.get("shaping", "none") != "none" or cfg.get("princess_redirect") == "potential":
        bad.append("cf_credit needs shaping none and no princess_redirect potential (the fork value has no Phi term)")
    if bad:
        raise SystemExit("bad cf_credit config: " + "; ".join(bad))
    return {k: (int(v) if k in INTS else float(v)) for k, v in c.items()}


def canonical(cfg: dict) -> dict:
    """rl_royale.config_sha's view: off (absent / null / false) = the cf keys dropped (the historical hash); on = every
    default filled (one hash for implicit / explicit)."""
    if cfg.get("cf_credit") is None or cfg.get("cf_credit") is False:
        return {k: v for k, v in cfg.items() if k not in KEYS}
    return {**cfg, "cf_credit": True,
            **{k: (int if k in INTS else float)(v if cfg.get(k) is None else cfg[k]) for k, v in DEFAULTS.items()}}


# ------------------------------------------------------------------------------------------------------
# board reading (engine state; pure on a prepared learner side + its decision)
# ------------------------------------------------------------------------------------------------------
def _norm(name) -> str:
    return "".join(ch for ch in str(name).split("@")[0].lower() if ch.isalnum())


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
    """RoyaleSim (x, y) -> board tiles in a side's own frame (me at the bottom): obs_contract._engine_xy x (18, 32)."""
    from pipeline.obs_contract import _engine_xy
    bx, by = _engine_xy(float(x) / 18.0, float(y) / 18.0, mirror)
    return bx * 18.0, by * 32.0


def siege_cells(bx: float, by: float, grid: str, kind: str, name: str, radius: float) -> np.ndarray:
    """[2304] bool candidate cells for a card answering a building at board tiles (bx, by) (module docstring)."""
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


# ------------------------------------------------------------------------------------------------------
# log-probs + alternatives
# ------------------------------------------------------------------------------------------------------
def gate_logprob(z_gate: float, d: dict, cfg: dict, play: bool = True) -> float:
    """log P(gate open / closed) under the sampler (e1_eval.sample_decide_batch): sigmoid((z - logit(tau_row)) / T_gate),
    tau_row = the row's own gate_tau (tau_phase) else cfg tau, in the overflow-safe log-sigmoid form (a closed gate at
    P(open) ~ 1 is a finite, very negative log-prob); 0.0 for a row whose gate was not sampled (forced / impossible)."""
    if not d.get("gate_sampled"):
        return 0.0
    tau = float(d.get("gate_tau", cfg["tau"]))
    T_gate = float(cfg.get("T_gate") or cfg.get("T", 0.5))
    x = (float(z_gate) - math.log(tau / (1.0 - tau))) / T_gate
    return -float(np.logaddexp(0.0, -x if play else x))


def alt_logprobs(model, enc, heads, d: dict, slot: int, cell: int, cfg: dict, cell_logits=None) -> dict:
    """The behaviour policy's log-probs of PLAYING (slot, cell) -- or, slot < 0, of WAITING -- at a decision with forward
    (enc, heads) of ONE row and decision dict ``d`` (its allowed mask, gate_sampled, gate_tau): sample_decide_batch's
    float64 tempered distributions (card softmax over allowed / T, cell softmax over 2304 / T), which
    rl_royale.policy_terms recomputes."""
    import torch
    z = float(heads["gate"].detach().cpu().numpy().astype(np.float64).reshape(-1)[0])
    if slot < 0:
        return {"lp_gate": gate_logprob(z, d, cfg, play=False), "lp_card": 0.0, "lp_cell": 0.0}
    T = float(cfg.get("T", 0.5))
    with torch.no_grad():
        allowed = torch.from_numpy(np.asarray(d["allowed"], bool)).to(heads["card"].device)
        cl = heads["card"][0].clone().masked_fill(~allowed, float("-inf"))
        pc = torch.log_softmax(cl.double() / T, dim=-1).cpu().numpy()
        if cell_logits is None:
            cell_logits = model.cell_logits(enc, torch.tensor([int(slot)], device=heads["card"].device))[0]
        px = torch.log_softmax(cell_logits.double() / T, dim=-1).cpu().numpy()
    return {"lp_gate": gate_logprob(z, d, cfg), "lp_card": float(pc[int(slot)]), "lp_cell": float(px[int(cell)])}


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


def alternatives(m, s, d: dict, trig: list, c: dict) -> list[dict]:
    """The alternative actions of learner side ``s`` (prepared, decided ``d``, not applied) of match ``m`` for the fired
    triggers ``trig`` -> [{trigger, kind, play, slot, cell, lp_gate, lp_card, lp_cell}], actions distinct and != the
    baseline's (module docstring)."""
    import torch
    from pipeline import decision_options as DO
    allowed = np.asarray(d["allowed"], bool)
    names, kinds = slot_names(s), slot_kinds(s)
    grid = s.cfg["grid"]
    rk, xk = _slot_of(names, allowed, "rocket"), _slot_of(names, allowed, "xbow")
    want = []                                             # (trigger, kind, slot, cell | candidate mask | "argmax")
    rt = [t for t in trig if t.startswith("rocket")]
    if rk is not None and rt:
        bs = s._cur[1]
        value, elig = DO.best_rocket_clump(DO.rocket_bodies(bs, "cost"), grid, "edge", None, 0.0,
                                           towers=DO.enemy_princesses_alive(bs))
        if elig is not None and value >= c["cf_rocket_min_value"]:
            want.append((rt[0], "rocket_clump", rk, elig))
        hps = DO.enemy_princess_hps(s.state["episode"]["crown_towers"], s.side)
        if hps:
            want.append((rt[0], "rocket_princess", rk, DO.lethal_rocket_cell(min(hps, key=lambda k: (hps[k], k)), grid)))
    if "siege" in trig:
        tg = m.cf_state["target"]
        bx, by = board_tiles(tg["x"], tg["y"], s.mirror)
        front = None
        if tg["princess"] is not None:
            front = front_cells(*board_tiles(*tg["princess"], s.mirror), grid, c["cf_front_min_tiles"],
                                c["cf_front_max_tiles"])
        for k in range(len(names)):
            if not allowed[k] or names[k] in NO_BUILDING_DAMAGE:
                continue
            want.append(("siege", "siege_rocket" if k == rk else f"siege_{names[k]}", k,
                         siege_cells(bx, by, grid, kinds[k], names[k], c["cf_siege_radius_tiles"])))
            if front is not None and "SPELL" not in kinds[k]:
                want.append(("siege", f"front_{names[k]}", k, front))
    xt = [t for t in trig if t.startswith("xbow")]
    if xk is not None and xt:
        want.append((xt[0], "xbow_cell", xk, "argmax"))
    out, seen = [], {(int(d["slot"]), int(d["cell"]))} if d.get("play") else {(-1, -1)}
    if not want and not d.get("play"):
        return []
    enc, heads = forward_one(s)
    cls: dict = {}
    for t, kind, slot, cell in want:
        if slot not in cls:
            with torch.no_grad():
                cls[slot] = s.model.cell_logits(enc, torch.tensor([slot], device=heads["card"].device))[0]
        cl = cls[slot]
        if kind == "rocket_clump":
            cell = DO.rocket_value_cell(cl, cell)
        elif isinstance(cell, str):                       # "argmax": the policy's own cell for that card
            cell = int(cl.argmax())
        elif not isinstance(cell, int):                   # a candidate mask: the policy's own argmax inside it
            if not cell.any():
                continue
            cell = int(cl.masked_fill(~torch.from_numpy(cell).to(cl.device), float("-inf")).argmax())
        if (slot, cell) in seen or not math.isfinite(float(cl[cell])):
            continue
        seen.add((slot, cell))
        out.append({"trigger": t, "kind": kind, "play": True, "slot": int(slot), "cell": int(cell),
                    **alt_logprobs(s.model, enc, heads, d, slot, cell, s.cfg, cell_logits=cl)})
    if d.get("play") and d.get("gate_sampled"):           # every trigger: the baseline play vs not playing now
        out.append({"trigger": "+".join(trig), "kind": "wait", "play": False, "slot": -1, "cell": -1,
                    **alt_logprobs(s.model, enc, heads, d, -1, -1, s.cfg)})
    return out


# ------------------------------------------------------------------------------------------------------
# triggers + the actor's runner
# ------------------------------------------------------------------------------------------------------
def new_state(s) -> dict:
    """A match's cf bookkeeping (on the real SelfPlayMatch as ``cf_state``): trigger RNG of its own (the policy's streams
    are never drawn), budgets used, X-Bow watch, the samples, wall time."""
    seed = zlib.crc32(f"{s.tag}:cf:{s.k}:{int(s.cfg.get('rollout_index', 0))}:{int(s.cfg.get('update', 0))}".encode())
    return {"rng": np.random.default_rng(seed), "n": Counter(), "last_siege": -10 ** 9, "last_xbow": -10 ** 9,
            "target": None, "xb": {}, "xb_failed": 0, "xb_fail_tick": -10 ** 9, "samples": [], "wall_s": 0.0,
            "decisions": 0}


def match_record(st: dict) -> dict:
    """SelfPlayMatch.result()'s ``cf`` entry (picklable, JSON-able)."""
    return {"samples": st["samples"], "wall_s": round(st["wall_s"], 3), "triggers": dict(st["n"]),
            "decisions": st["decisions"], "xbow_failed": st["xb_failed"]}


def triggers(m, s, d: dict, c: dict) -> list[str]:
    """The triggers firing at learner decision ``d`` of match ``m`` (draws only the match's own cf RNG; budgets are spent
    by the hook once an alternative exists). Reads the engine state only when an enemy building or one of our X-Bows is
    on the board (raw kind 1 = building, 12 = deploying)."""
    st, env, tick = m.cf_state, m.env, int(s._cur[0])
    ents = s.state["entities"]
    es = None
    if st["xb"] or any(int(e["side"]) == s.side and _norm(e.get("name", "")) == "xbow" for e in ents):
        es = env.core.state()
        xbow_watch(st, env, s.side, tick, es)
    allowed = np.asarray(d["allowed"], bool)
    if not allowed.any():
        return []
    names, out = slot_names(s), []
    rk, xk = _slot_of(names, allowed, "rocket"), _slot_of(names, allowed, "xbow")
    if rk is not None:
        if d.get("play") and int(d["slot"]) == rk:
            if st["n"]["rocket_played"] < c["cf_rocket_played_per_match"]:
                out.append("rocket_played")
        elif st["n"]["rocket"] < c["cf_rocket_per_match"] and st["rng"].random() < c["cf_rocket_p"]:
            out.append("rocket")
    if (st["n"]["siege"] < c["cf_siege_per_match"] and tick - st["last_siege"] >= c["cf_siege_gap_ticks"]
            and any(int(e["side"]) != s.side and int(e.get("kind", -1)) in (1, 12) for e in ents)):
        tg = siege_target(env, s.side, es)
        if tg is not None and st["rng"].random() < c["cf_siege_p"]:
            st["target"] = tg
            out.append("siege")
    if xk is not None and tick - st["last_xbow"] >= c["cf_xbow_gap_ticks"]:
        if (st["xb_failed"] and tick - st["xb_fail_tick"] <= c["cf_xbow_fail_window_ticks"]
                and st["n"]["xbow_after_fail"] < c["cf_xbow_fail_per_match"]):
            out.append("xbow_after_fail")
        elif st["n"]["xbow"] < c["cf_xbow_per_match"] and st["rng"].random() < c["cf_xbow_p"]:
            out.append("xbow")
    return out


def reward(word: str) -> float:
    return {"win": 1.0, "loss": -1.0}.get(word, 0.0)


class Runner:
    """One per ``e1_eval.run_selfplay_batch`` call with cfg["cf"] (the actor): ``hook(live, todo)`` after every round's
    decide, before any apply. ``make_env`` = the batch's own env factory (forks run on pooled copies of it)."""

    def __init__(self, make_env, c: dict):
        self.make_env, self.c = make_env, c
        self.pool: list = []
        self.last_forks: list = []                        # the last fork set (tests)

    def hook(self, live, todo) -> None:
        by = {id(m.learner): m for m in live}
        for s, p, d in todo:
            m = by.get(id(s))
            if m is None:
                continue
            t0 = time.perf_counter()
            if getattr(m, "cf_state", None) is None:
                m.cf_state = new_state(s)
            st = m.cf_state
            st["decisions"] += 1
            trig = triggers(m, s, d, self.c)
            alts = alternatives(m, s, d, trig, self.c) if trig else []
            if not alts:
                st["wall_s"] += time.perf_counter() - t0
                continue
            for t in trig:
                st["n"][t] += 1
            tick = int(s._cur[0])
            if "siege" in trig:
                st["last_siege"] = tick
            if any(t.startswith("xbow") for t in trig):
                st["last_xbow"] = tick
            entries = [(x, px, dx) for x, px, dx in todo if x is m.learner or x is m.opp]
            ends = self.rollouts(m, entries, alts)
            vb = ends[0]
            for a, e in zip(alts, ends[1:]):
                a.update(v=e["v"], dq=e["v"] - vb["v"], end=e["tick"], terminal=e["terminal"])
            wall = time.perf_counter() - t0
            st["wall_s"] += wall
            st["samples"].append({
                "row": len(s.traj), "tick": tick, "triggers": trig, "v_base": vb["v"], "base_end": vb["tick"],
                "base_terminal": vb["terminal"], "base": {"play": bool(d["play"]), "slot": int(d["slot"]),
                                                          "cell": int(d["cell"])},
                "target": dict(st["target"]) if "siege" in trig else None, "alts": alts, "wall_s": round(wall, 3)})

    def rollouts(self, m, entries, alts) -> list[dict]:
        """Fork ``m`` (its due sides prepared and decided as ``entries`` [(side, p, decision)], nothing applied) into the
        baseline + one copy per alternative; apply the root (the learner's decision replaced by the alternative's
        action), then lockstep rounds (``e1_eval.selfplay_decide`` over every fork's due sides) until each copy's learner
        decides at >= root + horizon (-> its value) or its match ends (-> the terminal reward). -> [{v, tick, terminal}]
        in [baseline] + alts order. ``m`` is never touched (its engine is only read by save_state)."""
        import torch
        from pipeline import e1_eval as E
        from pipeline.rl_royale import value_scalar
        from pipeline.search_s0 import fork_into
        env, L = m.env, m.learner
        while len(self.pool) < 1 + len(alts):
            self.pool.append(self.make_env())
        blob = env.core.save_state()
        forks = [fork_into(m, e2, blob, fresh=FORK_FRESH) for e2 in self.pool[:1 + len(alts)]]
        root, H = int(env.tick), int(self.c["cf_horizon_ticks"])
        for f, a in zip(forks, [None] + alts):
            for s, p, d in entries:
                if s is not L:
                    f.opp.apply(p, dict(d))
                elif a is None:
                    f.learner.apply(p, dict(d))
                else:
                    f.learner.apply(p, {**d, "play": a["play"], "slot": a["slot"], "cell": a["cell"], "why": "cf",
                                        "lp_gate": a["lp_gate"], "lp_card": a["lp_card"], "lp_cell": a["lp_cell"]})
        out: list = [None] * len(forks)
        ends, active = [], list(range(len(forks)))
        while active:
            due = []
            for i in list(active):
                f = forks[i]
                got = f.due()
                if not got:
                    out[i] = {"v": reward(f.learner._outcome()[0]), "tick": int(f.env.tick), "terminal": True}
                    active.remove(i)
                    continue
                for s in got:
                    s.prepare()
                if f.learner in got and int(f.env.tick) >= root + H:
                    ends.append(i)
                    active.remove(i)
                    continue
                due += got
            for s, p, d in E.selfplay_decide(due):
                s.apply(p, d)
        if ends:
            model, dev = L.model, L.cfg["device"]
            sides = [forks[i].learner for i in ends]
            if isinstance(model, E.GenPolicy):
                enc, _, _, _ = model.forward_batch([x.gen_row(model) for x in sides], dev)
                net = model.model
            else:
                enc, _, _, _ = E.model_forward_batch(model, *zip(*[x._obs for x in sides]), device=dev)
                net = model
            with torch.no_grad():
                v = value_scalar(net.value_head(enc["g"])).cpu().numpy()
            for i, vi in zip(ends, v):
                out[i] = {"v": float(self.c.get("v_scale", 1.0)) * float(vi), "tick": int(forks[i].env.tick),
                          "terminal": False}
        self.last_forks = forks
        return out


# ------------------------------------------------------------------------------------------------------
# learner side: the per-update monitors
# ------------------------------------------------------------------------------------------------------
def _agg(v) -> dict:
    v = np.asarray(v, dtype=np.float64)
    return {"n": int(len(v)), "dq_mean": float(v.mean()) if len(v) else None,
            "pos_share": float((v > 0).mean()) if len(v) else None}


def batch_stats(results: list[dict], rows_added: int) -> dict:
    """Per-update cf monitors over the rollout records: matches with / without a cf record (without = an actor that ran
    no cf code), triggers fired, alternatives evaluated, DeltaQ (raw, critic units) mean / share positive overall, per
    trigger and per alternative kind, fork wall seconds per match and their share of the match wall time, the rows added."""
    recs = [r["cf"] for r in results if "cf" in r]
    alts = [a for x in recs for smp in x["samples"] for a in smp["alts"]]
    dq = [a["dq"] for a in alts]
    by_kind: dict = {}
    by_trig: dict = {}
    for a in alts:
        by_kind.setdefault(a["kind"], []).append(a["dq"])
        by_trig.setdefault(a["trigger"], []).append(a["dq"])
    trig = Counter()
    for x in recs:
        trig.update(x["triggers"])
    wall = [x["wall_s"] for x in recs]
    match_s = sum(float(r.get("wall_s") or 0.0) for r in results if "cf" in r)
    return {"matches": len(recs), "matches_missing": len(results) - len(recs), "triggers": dict(trig),
            "samples": sum(len(x["samples"]) for x in recs), "alts": len(alts), "rows": int(rows_added),
            **_agg(dq), "dq_abs_mean": float(np.abs(dq).mean()) if dq else None,
            "by_trigger": {k: _agg(v) for k, v in sorted(by_trig.items())},
            "by_kind": {k: _agg(v) for k, v in sorted(by_kind.items())},
            "xbow_failed": sum(x.get("xbow_failed", 0) for x in recs),
            "wall_s_per_match": float(np.mean(wall)) if wall else None,
            "wall_share": float(sum(wall) / match_s) if match_s > 0 else None}
