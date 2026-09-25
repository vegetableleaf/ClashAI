"""Dead reckoning of a RAW observation H ticks ahead (L68 T10): counter the play->land lag at decision time.

after the frame we decided on. ``extrapolate`` guesses the board at landing from the last two observations, BEFORE

    ``board_side.to_observe``'s output): ``tick``, entity id ``entity_id``, my elixir ``players[].elixir_exact``;

Advanced:
    address from pairing two different bodies) moves pos + v * H, v = displacement / tick gap, clamped to the
    board 0..18000 x 0..32000 (engine units, 1,000 per tile);
  * the clock: ``tick`` / ``game_tick`` + H (so from_engine's t_sec / double-elixir / overtime phase follow);
  * MY elixir: + ``opp_elixir_count.regen_between(tick, tick + H)``, capped at 10.
NOT advanced / simulated: entities without a previous sighting (new or deploying bodies stay put), towers (crown
towers are never moved: ``episode.crown_towers`` is not touched and card_id < 0 entities stay put), HP, deaths,
spawns, targets and retargeting (a unit that stops to attack mid-window overshoots), spells / effects /
projectiles, hand / next card, and the OPPONENT's elixir (left to the caller, which must not read the true value).
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

from pipeline.opp_elixir_count import MAX_ELIXIR, regen_between

BOARD_X, BOARD_Y = 18000.0, 32000.0


def _tick_key(obs: Mapping[str, Any]) -> str:
    return "tick" if "tick" in obs else "game_tick"


def _eid(e: Mapping[str, Any]):
    return e.get("entity_id", e.get("uid"))


def extrapolate(obs: Mapping[str, Any], prev: Optional[Mapping[str, Any]], h: int, my_side: int) -> dict:
    """``obs`` advanced ``h`` ticks (a new dict; the inputs are not modified). ``prev`` = an earlier observation of
    the same match (None -> no motion, clock + my elixir still advance). See the module docstring."""
    h = int(h)
    tk = _tick_key(obs)
    tick = int(obs[tk])
    out = dict(obs)
    out[tk] = tick + h
    gap = tick - int(prev[_tick_key(prev)]) if prev is not None else 0
    before = {}
    if gap > 0:
        before = {_eid(e): e for e in prev.get("entities") or () if _eid(e) is not None}
    ents = []
    for e in obs.get("entities") or ():
        e = dict(e)
        p = before.get(_eid(e)) if int(e.get("card_id", -1)) >= 0 else None
        if p is not None and p.get("side") == e.get("side") and p.get("card_id") == e.get("card_id"):
            e["x"] = min(max(e["x"] + (e["x"] - p["x"]) * h / gap, 0.0), BOARD_X)
            e["y"] = min(max(e["y"] + (e["y"] - p["y"]) * h / gap, 0.0), BOARD_Y)
        ents.append(e)
    if "entities" in obs:
        out["entities"] = ents
    g = regen_between(tick, tick + h)
    players = []
    for p in obs.get("players") or ():
        p = dict(p)
        if int(p["side"]) == int(my_side):
            if "elixir_exact" in p:
                p["elixir_exact"] = min(MAX_ELIXIR, float(p["elixir_exact"]) + g)
            if "elixir_raw" in p:
                p["elixir_raw"] = min(MAX_ELIXIR * 1e4, float(p["elixir_raw"]) + g * 1e4)
        players.append(p)
    if "players" in obs:
        out["players"] = players
    return out
