"""Pro-fitted press model for hero Ice Wizard's Frosty Fella (NEW file; nothing live imports it yet).

frosty_fella_press_probability(features) = P(a pro presses within the next 1.0 s | the own hero Ice Wizard is alive,
its ability is unspent, ``age_s`` seconds after its deploy). Per-1 s hazard, the convention of
scratchpad/gauntlet/L70/abilities/ability_policy.py; for a decision interval dt use 1 - (1 - p) ** dt.
Fitted by L70/abilities/ice_wizard_hero/fit_model.py on RoyaleAPI pro replays; coefficients in
ability_ice_wizard_model.json (same folder). The model is a SIGNAL, not a rule: it says how often a pro presses in
a similar PUBLIC context (own deploy age, opponent plays, own plays, phase, elixir), not whether the freeze pays.

``features`` is the dict returned by ``build_features`` (the SAME function the fit used, so live/fit cannot drift).
Plays are dicts: {"t": seconds since match start, "cost": elixir, "kind": "troop"|"spell"|"building",
"mine": True if it landed on the HERO OWNER's half of the arena, "wincon": bool, "card": slug}.
Pure, numpy-free at inference.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

MODEL_PATH = Path(__file__).with_name("ability_ice_wizard_model.json")
KNOTS = [0.0, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 11.0, 15.0, 20.0, 30.0]       # seconds since deploy (piecewise-linear)
BASE_FEATURES = ["t_min", "overtime", "own_elixir", "opp_elixir", "opp_n3", "opp_cost3", "opp_n6", "opp_cost6",
                 "opp_troop6", "opp_spell6", "opp_bld6", "opp_mine_cost6", "opp_theirs_cost6", "opp_mine_cost10",
                 "opp_since_mine", "opp_wincon_mine10", "own_n3", "own_n6", "own_cost6"]
FEATURE_NAMES = BASE_FEATURES + ["age_hat_%g" % k for k in KNOTS[1:]]
WINCON_SLUGS = {"hog-rider", "giant", "golem", "royal-giant", "electro-giant", "balloon", "lava-hound", "ram-rider",
                "battle-ram", "miner", "royal-hogs", "wall-breakers", "elixir-golem", "giant-skeleton", "pekka",
                "mega-knight", "goblin-giant", "goblin-drill", "graveyard", "skeleton-barrel", "goblin-barrel"}


def hat(age_s: float) -> list[float]:
    """Linear-interpolation weights of the knots[1:] (knot 0 is the reference); flat beyond the last knot."""
    a = min(max(age_s, KNOTS[0]), KNOTS[-1])
    out = []
    for j in range(1, len(KNOTS)):
        lo, mid, hi = KNOTS[j - 1], KNOTS[j], KNOTS[j + 1] if j + 1 < len(KNOTS) else None
        if a < lo:
            out.append(0.0)
        elif a <= mid:
            out.append((a - lo) / (mid - lo))
        elif hi is None:
            out.append(1.0)
        else:
            out.append(max(0.0, (hi - a) / (hi - mid)))
    return out


def build_features(age_s: float, t_sec: float, own_elixir: float, opp_elixir: float,
                   opp_plays: list[dict], own_plays: list[dict]) -> dict:
    """Public-context features at a decision time. Only plays with 0 <= t_sec - p['t'] are read."""
    def recent(plays, w):
        return [p for p in plays if 0.0 <= t_sec - p["t"] <= w]
    o3, o6, o10 = recent(opp_plays, 3), recent(opp_plays, 6), recent(opp_plays, 10)
    mine_ts = [t_sec - p["t"] for p in opp_plays if p["mine"] and 0.0 <= t_sec - p["t"] <= 20]
    s = lambda ps, f=lambda p: True: float(sum(p["cost"] for p in ps if f(p)))  # noqa: E731
    f = {"t_min": t_sec / 60.0, "overtime": 1.0 if t_sec >= 180 else 0.0,
         "own_elixir": float(own_elixir), "opp_elixir": float(opp_elixir),
         "opp_n3": float(len(o3)), "opp_cost3": s(o3), "opp_n6": float(len(o6)), "opp_cost6": s(o6),
         "opp_troop6": s(o6, lambda p: p["kind"] == "troop"), "opp_spell6": s(o6, lambda p: p["kind"] == "spell"),
         "opp_bld6": s(o6, lambda p: p["kind"] == "building"),
         "opp_mine_cost6": s(o6, lambda p: p["mine"]), "opp_theirs_cost6": s(o6, lambda p: not p["mine"]),
         "opp_mine_cost10": s(o10, lambda p: p["mine"]),
         "opp_since_mine": min(mine_ts) if mine_ts else 20.0,
         "opp_wincon_mine10": 1.0 if any(p["mine"] and p.get("wincon") for p in o10) else 0.0,
         "own_n3": float(len(recent(own_plays, 3))), "own_n6": float(len(recent(own_plays, 6))),
         "own_cost6": s(recent(own_plays, 6))}
    for k, v in zip(KNOTS[1:], hat(age_s)):
        f["age_hat_%g" % k] = v
    return f


def make_play(slug: str, tick: int, x: float, y: float, now_tick: int, up: bool, cards: dict) -> dict:
    """One opponent play as the model sees it at ``now_tick`` (shared by the fit and the live adapter).
    ``up`` = the hero owner's half is y > 16000 (reader side 1 / replay blue); walking troops are dead-reckoned toward it
    (card speed, 1 s deploy, 12 s cap; fights/deaths ignored) so 'mine' means 'probably already on my half'."""
    cost, kind, n, speed = cards.get(slug, [3, "troop", 1, 0.0])
    kind = kind if kind in ("troop", "spell", "building") else "troop"
    yy = float(y)
    if kind == "troop":
        age = min(12.0, max(0.0, (now_tick - tick) / 20.0 - 1.0))
        yy = min(32000.0, max(0.0, yy + (1 if up else -1) * speed * 1000.0 * age))
    return {"t": tick / 20.0, "cost": float(cost), "kind": kind, "mine": (yy > 16000) == up, "wincon": slug in WINCON_SLUGS,
            "card": slug, "x": float(x), "y": yy, "n": int(n)}


_MODEL = None


def load_model() -> dict:
    global _MODEL
    if _MODEL is None:
        _MODEL = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    return _MODEL


def frosty_fella_press_probability(features: dict, model: dict | None = None) -> float:
    """P(pro presses within the next 1 s | alive, unspent). Raises KeyError on a missing feature, ValueError on NaN."""
    m = model or load_model()
    z = float(m["intercept"])
    for name, mu, sd, w in zip(m["feature_names"], m["mean"], m["scale"], m["coefficients"]):
        x = float(features[name])
        if not math.isfinite(x):
            raise ValueError("non-finite feature %s" % name)
        z += w * (x - mu) / sd
    z = max(-40.0, min(40.0, z + float(m.get("calibration_shift", 0.0))))
    return 1.0 / (1.0 + math.exp(-z))


# ----------------------------------------------------------------------------------------------------------- live adapter
# Policy (L70 calibration on 1,311 pro deployment windows, picked on the training battles; see ice_wizard_hero/policy.json):
# press iff hazard p >= P_STAR(V) AND geometry_ok, where geometry_ok is the live freeze-zone check (>= 2 troops worth >= V
# elixir, or a win condition on my half inside the freeze while Tesla is unaffordable). P_STAR is tied to V.
V_MIN = 2.0
P_STAR_BY_V = {2.0: 0.044746336621534336, 3.0: 0.032585935277788476, 4.0: 0.019618532522310172}      # filled from policy.json by the fit
P_STAR = P_STAR_BY_V[V_MIN]
TICK_S = 0.05


def _slug(key: str) -> str:
    try:
        from pipeline.dataset_gen import card_key
        return card_key(key) or key.replace("_", "-")
    except Exception:                                      # pipeline (torch) not importable: plain rename
        return key.replace("_", "-")


def live_features(pilot, frame, side: int, hero_deploy_tick: int, tick: int | None = None) -> dict:
    """The model's features from live state, at ``tick`` (default: the frame's game_tick).

    pilot.public = pipeline.public_observation.PublicObserver (fed every active frame by GenPilot.observe):
      .plays          opponent play events {card (engine key), form, x, y, tick, side, accepted}
      .own_events     my confirmed plays {card (slug), tick, side, accepted, ability}  (GenPilot.record_play/record_ability)
      .estimate_at(t) opponent elixir counter (public events only)
    frame = reader frame: game_tick, players[...]['elixir_raw'] (1e-4 elixir) -- my elixir; 'own_elixir' key as a fallback.
    ``side`` = my side (0/1); my half is y > 16000 iff side == 1.
    """
    cards = load_model()["cards"]
    now = int(frame["game_tick"]) if tick is None else int(tick)
    up = int(side) == 1
    me = next((p for p in (frame.get("players") or []) if int(p["side"]) == int(side)), None)
    own_el = me["elixir_raw"] / 1e4 if me is not None else float(frame["own_elixir"])
    pub = pilot.public
    opp = [make_play(_slug(e["card"]), int(e["tick"]), e["x"], e["y"], now, up, cards)
           for e in pub.plays if e.get("accepted", True) and int(e["side"]) != int(side) and int(e["tick"]) <= now]
    own = [{"t": int(e["tick"]) * TICK_S, "cost": float(cards.get(e["card"], [3])[0]), "kind": "troop", "mine": False}
           for e in pub.own_events if not e.get("ability") and e.get("accepted", True) and e["card"] != "ice-wizard"
           and int(e["tick"]) <= now]
    return build_features((now - int(hero_deploy_tick)) * TICK_S, now * TICK_S, own_el, float(pub.estimate_at(now)), opp, own)


def should_press_pro(pilot, frame, side: int, hero_deploy_tick: int, geometry_ok: bool, v_min: float = V_MIN,
                     p_star: float | None = None) -> tuple[bool, str]:
    """Combined policy. Features are taken at the whole second since the hero deploy (the 1 s grid P_STAR was calibrated on),
    so calling this every frame does not raise the press rate."""
    tick = int(frame["game_tick"])
    grid = int(hero_deploy_tick) + 20 * ((tick - int(hero_deploy_tick)) // 20)
    p = frosty_fella_press_probability(live_features(pilot, frame, side, hero_deploy_tick, tick=grid))
    # owner 2026-10-08 "switch on the higher bar": live_play --iw-press-pstar overrides the fitted P*(V) (W2 sweep:
    # P* .03 keeps 69% of presses, overspend .29 -> .22; offline approximation, live-only -- the SIM has no hero IW)
    p_star = P_STAR_BY_V[float(v_min)] if p_star is None else float(p_star)
    why = "pro_hazard p=%.4f %s P*=%.4f(V>=%g) geometry=%s age=%.1fs" % (
        p, ">=" if p >= p_star else "<", p_star, v_min, geometry_ok, (tick - hero_deploy_tick) * TICK_S)
    return bool(p >= p_star and geometry_ok), why
