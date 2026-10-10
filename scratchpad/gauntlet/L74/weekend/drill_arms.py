"""L74 weekend: forced arms for mech_fork (MECH=prevent | drills).  Public information + the model's own heads only.

prevent (S3, drill D10): opportunity = the model's decision is a Log / Tornado while enemy GROUND bodies worth >= 4 elixir stand on
our half and a Tesla / Knight / Ice Wizard is in hand and affordable within 2 s.  B = hold the spell, then place the model's
best-cell Tesla (else Knight, else Ice Wizard) at the first decision where one is affordable.  A = the model's own play.
drills (S9): moments come from drills.py selectors run on a sim_dump (moments_from_dump.py); at the moment's decision tick
the match forks into a DO arm and an ALT arm (the drill's two options, below), each forced at the root only; the original
match is A (the model's own).  A forced play uses the model's own card logits and cell head (restricted to an allowed card set / cell
region), the way mech_fork's placebo does; decision options (spell aim, cell refine) are not applied to forced plays.
Frame: own tiles, X = 18 x, Y = 32 (1 - y); my king (9, 3); forward = increasing Y; my half Y <= 16."""
import os
import zlib

import numpy as np

NOPLAY = {"play": False, "slot": -1, "cell": -1, "why": "wk_hold"}
SPE = ((0.0, 2.81), (120.0, 1.40), (240.0, 0.93))          # seconds per elixir (pipeline/own_cycle.py)
DEF = ("tesla", "knight", "icewizard")                     # prevent / D1 defenders, priority order for prevent
GROUND_ONLY = ("knight", "skeletons", "log")                # D4 ground-only answers (X-Bow never affordable at the moment)
AIRCAP = ("tesla", "icewizard")                            # D4 air answers that are defenders (Rocket is not one)
MT = {"mL": (3.5, 6.5), "mR": (14.5, 6.5), "mK": (9.0, 3.0)}
_T = {}


def spe(t_sec):
    return [v for lo, v in SPE if t_sec >= lo][-1]


def cname(L, slot):
    return str(L.deck.cards[slot]).split("@")[0].lower() if slot is not None and slot >= 0 else None


def tiles(grid, n):
    if (grid, n) not in _T:
        from pipeline.model_v3 import cell_xy
        a = np.array([cell_xy(c, grid) for c in range(n)], float)
        _T[(grid, n)] = (a[:, 0] * 18.0, (1.0 - a[:, 1]) * 32.0)
    return _T[(grid, n)]


def pick(L, ctx, names=None, exclude=(), maxcost=None):
    """highest card-logit allowed slot whose card is in ``names`` (None = any) and not in ``exclude``."""
    lg = ctx["heads"]["card"][0]
    best = None
    for i in range(8):
        if not ctx["allowed"][i]:
            continue
        c = cname(L, i)
        if (names is not None and c not in names) or c in exclude or (maxcost is not None and L.costs[i] > maxcost):
            continue
        if best is None or float(lg[i]) > best[0]:
            best = (float(lg[i]), i)
    return None if best is None else best[1]


def best_cell(L, ctx, slot, region=None):
    """the model's cell head for ``slot``'s card, argmax over the cells where region(X, Y) is true (None = all)."""
    import torch
    with torch.no_grad():
        cl = L.model.cell_logits(ctx["enc"], torch.tensor([slot], device=ctx["heads"]["card"].device))[0]
        if region is not None:
            X, Y = tiles(L.cfg["grid"], cl.shape[0])
            mk = region(X, Y)
            if mk.any():
                cl = cl.masked_fill(~torch.from_numpy(mk).to(cl.device), float("-inf"))
        return int(cl.argmax())


def play(L, ctx, slot, why, region=None):
    return {"play": True, "slot": int(slot), "cell": best_cell(L, ctx, slot, region), "why": why}


def near(xy, r):
    return lambda X, Y: np.hypot(X - xy[0], Y - xy[1]) <= r


def lane_region(lane, push):
    """push=True: the pushed lane plus the centre on my half; False: the other lane (strict), my half."""
    if lane == "L":
        f = (lambda X: X <= 10.5) if push else (lambda X: X > 10.5)
    else:
        f = (lambda X: X >= 7.5) if push else (lambda X: X < 7.5)
    return lambda X, Y: f(X) & (Y <= 16.0)


def enemy_tiles(bs):
    return [(u.x * 18.0, (1.0 - u.y) * 32.0) for u in bs.units if int(u.side) == 1]


def ground_push_value(m):
    """Referee (engine truth): elixir value of enemy GROUND bodies on our half, catalogue elixir / count per body.  Selects moments only;
    never a model input."""
    from royalegym.protocol import EMPTY_CARD, EntityKind
    st = m.env.core.state()
    L = m.learner.side
    cards = {c.card_id: c for c in m.env.core.cards()}
    v = 0.0
    for e in st.entities:
        if e.team == L or e.hp <= 0 or e.flying or e.kind not in (EntityKind.TROOP, EntityKind.BUILDING) or e.card_id == EMPTY_CARD:
            continue
        if (e.y < 288000) == (L == 0):
            c = cards.get(e.card_id)
            v += 0.0 if c is None else float(c.elixir) / max(1, int(c.count))
    return v


# ---------------------------------------------------------------------------------------------------- scripts
class Hold:
    """Withhold every play until ``until(f, ctx)`` or ``max_ticks``; then release to the model."""

    def __init__(self, t0, max_ticks, until=None):
        self.t0, self.max, self.until, self.done, self.end = t0, max_ticks, until, False, None

    def step(self, f, ctx):
        if ctx["tick"] - self.t0 >= self.max or (self.until is not None and self.until(f, ctx)):
            self.done, self.end = True, ctx["tick"]
            return None
        return NOPLAY

    def report(self, L):
        return {"released": self.end}


def defender_play(L, ctx, why="prevent"):
    for n in DEF:
        s = pick(L, ctx, (n,))
        if s is not None:
            return play(L, ctx, s, why)
    return None


class Prevent:
    """B of S3 / D10: hold everything until a defender is affordable, play it at its best cell, then the model resumes."""

    def __init__(self, t0, wait=50):
        self.t0, self.wait, self.done, self.played = t0, wait, False, None

    def step(self, f, ctx):
        d = defender_play(f.learner, ctx)
        if d is not None:
            self.done, self.played = True, (ctx["tick"], cname(f.learner, d["slot"]))
            return d
        if ctx["tick"] - self.t0 >= self.wait:
            self.done = True
            return None
        return NOPLAY

    def report(self, L):
        r = {"played": self.played, "waited": None if self.played is None else self.played[0] - self.t0}
        if self.played is not None:
            pl = next((p for p in L.plays if p.get("tick") == self.played[0]), None)
            r["accepted"] = None if pl is None else pl.get("accepted")
        return r


# ---------------------------------------------------------------------------------------------------- prevent opportunity
def prevent_probe(m, s, ctx, dA):
    """-> the B decision (+ "script") or None.  ctx: enc, heads, allowed, hand, tick, bs."""
    if not dA["play"] or str(dA.get("why", "")).startswith("lethal") or getattr(s, "pending", None) is not None:
        return None
    if cname(s, dA["slot"]) not in ("log", "tornado"):
        return None
    bs = ctx["bs"]
    cand = [i for i in range(8) if ctx["hand"][i] and cname(s, i) in DEF]
    if not cand:
        return None
    el = float(bs.my_elixir)
    need = min(s.costs[i] for i in cand) - el
    if need > 2.0 / spe(float(bs.t_sec)):
        return None
    if ground_push_value(m) < 4.0:
        return None
    d = defender_play(s, ctx)
    sc = Prevent(ctx["tick"])
    if d is not None:                                  # affordable now: place it instead of the spell
        sc.done, sc.played = True, (ctx["tick"], cname(s, d["slot"]))
        return {**d, "script": sc, "need": 0.0}
    return {**NOPLAY, "why": "prevent", "script": sc, "need": round(need, 2)}


# ---------------------------------------------------------------------------------------------------- drill arms
def build_arms(mo, m, s, ctx):
    """-> {"do": {"root", "script"}, "alt": {...}} or {"_skip": reason}.  First option = DO, second = ALT (see summary)."""
    dr, info, bs, t0 = mo["drill"], mo.get("info") or {}, ctx["bs"], ctx["tick"]
    if dr == "D1":
        k = pick(s, ctx, DEF)
        if k is None:
            return {"_skip": "no defender allowed"}
        return {"do": {"root": play(s, ctx, k, "d1_do", near(MT[info.get("tower", "mK")], 9.0)), "script": None},
                "alt": {"root": NOPLAY, "script": Hold(t0, 40)}}
    if dr == "D2":
        k = pick(s, ctx, None, exclude=("rocket", "tornado", "xbow"))
        if k is None:
            return {"_skip": "no troop card allowed"}
        lane = info["lane"]
        return {"do": {"root": play(s, ctx, k, "d2_do", lane_region(lane, True)), "script": None},
                "alt": {"root": play(s, ctx, k, "d2_alt", lane_region(lane, False)), "script": None}}
    if dr == "D3":
        k = pick(s, ctx, None, exclude=("rocket", "tornado", "xbow"), maxcost=3)
        if k is None:
            return {"_skip": "no cheap card allowed"}
        lane = info["lane"]
        tgt = MT["mL" if lane == "L" else "mR"]

        def pooled(f, c):
            return float(c["bs"].my_elixir) >= 4.0 or any(np.hypot(x - tgt[0], y - tgt[1]) <= 9.0 for x, y in enemy_tiles(c["bs"]))
        return {"do": {"root": NOPLAY, "script": Hold(t0, 200, pooled)},
                "alt": {"root": play(s, ctx, k, "d3_alt", lane_region(lane, True)), "script": None}}
    if dr == "D4":
        a, g = pick(s, ctx, AIRCAP), pick(s, ctx, GROUND_ONLY)
        if a is None or g is None:
            return {"_skip": "air or ground answer not allowed"}
        fly, tw = tuple(info["fly"]), MT[info["tower"]]
        reg = lambda X, Y: (np.hypot(X - fly[0], Y - fly[1]) <= 7.0) | (np.hypot(X - tw[0], Y - tw[1]) <= 7.0)
        return {"do": {"root": play(s, ctx, a, "d4_do", reg), "script": None},
                "alt": {"root": play(s, ctx, g, "d4_alt", reg), "script": None}}
    if dr == "D9":
        t = pick(s, ctx, ("tornado",))
        o = pick(s, ctx, None, exclude=("tornado",))
        if t is None or o is None:
            return {"_skip": "tornado or another card not allowed"}
        return {"do": {"root": play(s, ctx, o, "d9_do", lambda X, Y: Y <= 16.0), "script": None},
                "alt": {"root": play(s, ctx, t, "d9_alt"), "script": None}}
    return {"_skip": "unknown drill " + str(dr)}


# ---------------------------------------------------------------------------------------------------- training rows
def save_row(rows_dir, name, L, ctx, extra=None):
    """The model's input row at this decision + the allowed mask (+ target arrays) for S10.  Public input only."""
    if not rows_dir:
        return
    row = getattr(L, "_gen_row", None)
    if row is None:
        return
    os.makedirs(rows_dir, exist_ok=True)
    d = {k: np.asarray(v) for k, v in row.items()}
    d["allowed"] = np.asarray(ctx["allowed"], bool)
    for k, v in (extra or {}).items():
        d[k] = np.asarray(v)
    np.savez_compressed(os.path.join(rows_dir, name.replace(":", "_") + ".npz"), **d)


def is_ordinary(tag, tick, every=25):
    return zlib.crc32(f"{tag}:{tick}:ord".encode()) % every == 0
