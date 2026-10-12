"""Opt-in training opponents. No simulator imports or hidden opponent state.

PFSP replaces category mixing with a draw over every retained opponent. Ratings
are learner win-score EMAs (draw = .5), updated in deterministic match order.
"""
from __future__ import annotations

import math
import zlib
import numpy as np

DEFAULTS = {
    "league_pfsp": "off", "league_pfsp_gamma": 2.0, "league_pfsp_floor": 0.05,
    "league_external": [], "league_frozen_opponent": None,
    "opp_style": "off", "opp_style_aggression": [-0.08, 0.08],
    "opp_style_lane_bias": [-0.7, 0.7], "opp_style_temperature": [0.8, 1.2],
    "opp_style_spell_delay": [0, 4], "opp_style_bank": [0.0, 4.0],
}
STYLE_KEYS = tuple(k for k in DEFAULTS if k.startswith("opp_style"))


def mode(value):
    # YAML 1.1 parses unquoted off/on as booleans, including CLI overrides.
    return "on" if value is True else "off" if value is False else value


def validate(cfg):
    if mode(cfg.get("league_pfsp", "off")) not in ("off", "hard"):
        raise ValueError("league_pfsp must be off or hard")
    if mode(cfg.get("opp_style", "off")) not in ("off", "on"):
        raise ValueError("opp_style must be off or on")
    if mode(cfg.get("opp_style", "off")) == "on" and cfg.get("branch_gate"):
        raise ValueError("opp_style requires branch_gate=false (branch forks have a separate decoder)")
    for key in ("league_pfsp_gamma", "league_pfsp_floor"):
        v = cfg.get(key, DEFAULTS[key])
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            raise ValueError(f"{key} must be finite and positive")
    for key in STYLE_KEYS[1:]:
        v = cfg.get(key, DEFAULTS[key])
        if (not isinstance(v, (list, tuple)) or len(v) != 2 or
                any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in v)
                or v[0] > v[1]):
            raise ValueError(f"{key} must be an ordered finite range")
        if key == "opp_style_temperature" and v[0] <= 0:
            raise ValueError("opp_style_temperature must be positive")
        if key in ("opp_style_spell_delay", "opp_style_bank") and v[0] < 0:
            raise ValueError(f"{key} must be nonnegative")
        if key == "opp_style_spell_delay" and any(type(x) is not int for x in v):
            raise ValueError("opp_style_spell_delay must contain integer ticks")
        if key == "opp_style_bank" and v[1] > 10:
            raise ValueError("opp_style_bank must be <= 10")
    ext = cfg.get("league_external", [])
    if not isinstance(ext, list) or any(not isinstance(p, str) or not p for p in ext):
        raise ValueError("league_external must be a list of checkpoint paths")
    frozen = cfg.get("league_frozen_opponent")
    if frozen is not None and (not isinstance(frozen, str) or not frozen):
        raise ValueError("league_frozen_opponent must be a checkpoint path")
    if (mode(cfg.get("league_pfsp", "off")) == "hard" or mode(cfg.get("opp_style", "off")) == "on" or ext or frozen):
        if not cfg.get("league"):
            raise ValueError("adaptive opponents require league=true")
        if cfg.get("opp_elixir") not in ("counter", "counter_all"):
            raise ValueError("adaptive opponents require a public opp_elixir counter")
    if ext and mode(cfg.get("league_pfsp", "off")) != "hard" and not frozen:
        raise ValueError("league_external requires league_pfsp=hard")


def canonical_config(cfg):
    """Strip disabled options so old config hashes and resume checks stay exact."""
    c = dict(cfg)
    if mode(c.get("league_pfsp", "off")) == "off":
        for k in ("league_pfsp", "league_pfsp_gamma", "league_pfsp_floor"):
            c.pop(k, None)
    if mode(c.get("opp_style", "off")) == "off":
        for k in STYLE_KEYS:
            c.pop(k, None)
    else:
        c["opp_style"] = "on"
    for k in ("league_external", "league_frozen_opponent"):
        if not c.get(k):
            c.pop(k, None)
    return c


def update_rating(previous, outcome, alpha=0.05):
    """Learner win-score EMA; a fresh opponent starts at .5."""
    score = {"win": 1.0, "draw": 0.5, "loss": 0.0}[outcome]
    return (1 - alpha) * previous + alpha * score


def pfsp_weights(probabilities, gamma=2.0, floor=0.05):
    p = np.asarray(probabilities, dtype=np.float64)
    if p.size == 0 or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("PFSP needs probabilities in [0, 1]")
    if not math.isfinite(gamma) or gamma <= 0 or not math.isfinite(floor) or floor <= 0:
        raise ValueError("PFSP gamma and floor must be positive")
    w = (1 - p) ** gamma + floor
    return w / w.sum()


def sync_pool(state, cfg):
    if mode(cfg.get("league_pfsp", "off")) == "hard":
        state.setdefault("ratings", {})
        external = state.setdefault("external", [])
        for path in cfg.get("league_external", []):
            if path not in external:
                external.append(path)
        for opponent in opponent_pool(state.get("snapshots", []), cfg, state):
            state["ratings"].setdefault(opponent["id"], {"p": 0.5, "games": 0})


def opponent_pool(snaps, cfg, state):
    def entry(id_, path, type_):
        return dict(id=id_, path=path, type=type_, cat=type_)
    frozen = cfg.get("league_frozen_opponent")
    if frozen:
        return [entry("frozen:" + frozen, frozen, "frozen")]
    mix = cfg.get("league_mix", {"init": 1, "s1": 1})
    pool = [entry("init", cfg["init"], "init")]
    if mix.get("s1", 0) > 0:
        pool.append(entry("s1", cfg["league_specialist"], "s1"))
    pool += [entry(s["id"], s["path"], "snapshot") for s in snaps]
    paths = list(dict.fromkeys(state.get("external", []) + cfg.get("league_external", [])))
    return pool + [entry("external:" + p, p, "exploiter") for p in paths]


def sample_opponent(rng, snaps, cfg, state):
    pool = opponent_pool(snaps, cfg, state)
    if cfg.get("league_frozen_opponent"):
        return pool[0]
    ratings = state.get("ratings", {})
    p = [ratings.get(o["id"], {}).get("p", 0.5) for o in pool]
    w = pfsp_weights(p, cfg.get("league_pfsp_gamma", 2.0), cfg.get("league_pfsp_floor", 0.05))
    return pool[int(rng.choice(len(pool), p=w))]


def update_ratings(state, results):
    ratings = state.setdefault("ratings", {})
    for r in sorted(results, key=lambda r: (r["league"]["tag"], r["k"])):
        id_ = r["league"]["opp"]["id"]
        old = ratings.get(id_, {"p": 0.5, "games": 0})
        ratings[id_] = {"p": update_rating(old["p"], r["outcome"]), "games": old["games"] + 1}


def draw_style(cfg, seed, rollout=0):
    if mode(cfg.get("opp_style", "off")) != "on":
        return None
    rng = np.random.default_rng(zlib.crc32(f"opp-style:{seed}:{rollout}".encode()))
    out = {}
    for key in STYLE_KEYS[1:]:
        lo, hi = cfg.get(key, DEFAULTS[key])
        out[key.removeprefix("opp_style_")] = (int(rng.integers(lo, hi + 1)) if key.endswith("spell_delay")
                                               else float(rng.uniform(lo, hi)))
    return out


def style_config(cfg, seed, rollout):
    style = draw_style(cfg, seed, rollout)
    if style is None:
        return cfg
    return {**cfg, "_opp_style": style,
            "tau": float(np.clip(float(cfg["tau"]) - style["aggression"], .01, .99)),
            "T": max(.01, float(cfg["T"]) * style["temperature"])}


def bank_wait(view, style):
    # Defensive situation = a visible enemy body on our half. Uses only the
    # side-relative public board and our OWN elixir; never the other hand/bar.
    defensive = any(u.side == 1 and u.y >= .5 for u in view.units)
    return view.my_elixir < style["bank"] and not defensive


class LanePolicy:
    def __init__(self, model, bias, temperature):
        self.model, self.bias, self.temperature = model, bias, temperature

    def cell_logits(self, enc, slot):
        import torch
        from pipeline.model_v3 import GRID_X
        logits = self.model.cell_logits(enc, slot)
        x = torch.arange(logits.shape[-1], device=logits.device) % GRID_X
        # Multiplicative left/right probability preference exp(+/- bias).
        shift = torch.where(x < GRID_X / 2, self.bias, -self.bias)
        return logits + shift * self.temperature


def styled_decisions(model, enc, heads, p, allowed, stalled, sides):
    """Shared model forward, per-match decode. Called only for styled opponents."""
    from pipeline import e1_eval as E
    out = []
    for i, s in enumerate(sides):
        c, style = s.cfg, s.cfg["_opp_style"]
        a = allowed[i:i + 1].copy()
        banking = bank_wait(s._cur[2], style)
        if banking:
            a[:] = False
        net = LanePolicy(model, style["lane_bias"], c["T"] if c["policy"] == "sample" else 1.0)
        en, hd = ({k: v[i:i + 1] for k, v in block.items()} for block in (enc, heads))
        if c["policy"] == "sample":
            d = E.sample_decide_batch(net, en, hd, p[i:i + 1], a, stalled[i:i + 1], [s], c)[0]
        else:
            d = E.live_decide_batch(net, en, hd, p[i:i + 1], a, stalled[i:i + 1], tau=c["tau"], device=c["device"])[0]
        if banking:
            d["why"] = "style_bank"
        if d["play"] and E.vocab.is_spell(s.deck.card_ids[d["slot"]]):
            d["_style_delay"] = style["spell_delay"]
        out.append(d)
    return out
