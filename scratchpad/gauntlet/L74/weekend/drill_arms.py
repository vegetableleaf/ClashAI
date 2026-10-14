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
    """deck card -> 'tesla', 'knight', 'icewizard', 'xbow', 'log' ...  (the sim deck names are slugs: tesla_evo, ice_wizard, x_bow, the_log)"""
    if slot is None or slot < 0:
        return None
    n = str(L.deck.cards[slot]).split("@")[0].lower()
    for suf in ("_evo", "_hero"):
        if n.endswith(suf):
            n = n[:-len(suf)]
    n = n.replace("_", "")
    return "log" if n == "thelog" else n


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
STAT = {}      # reasons the prevent opportunity did not fire (per process; mech_play copies it into the match record)


def _no(why):
    STAT[why] = STAT.get(why, 0) + 1


def prevent_probe(m, s, ctx, dA):
    """-> the B decision (+ "script") or None.  ctx: enc, heads, allowed, hand, tick, bs."""
    if not dA["play"]:
        return None
    _no("model plays")
    if str(dA.get("why", "")).startswith("lethal") or getattr(s, "pending", None) is not None:
        return _no("lethal/pending") or None
    if cname(s, dA["slot"]) not in ("log", "tornado"):
        return None
    _no("spell Log/Tornado")
    bs = ctx["bs"]
    cand = [i for i in range(8) if ctx["hand"][i] and cname(s, i) in DEF]
    if os.environ.get("WK_DEBUG"):
        print("DBG", [(cname(s, i), bool(ctx["hand"][i]), bool(ctx["allowed"][i])) for i in range(8)], flush=True)
    if not cand:
        return _no("no defender in hand") or None
    el = float(bs.my_elixir)
    need = min(s.costs[i] for i in cand) - el
    if need > 2.0 / spe(float(bs.t_sec)):
        return _no("defender not affordable within 2 s") or None
    if ground_push_value(m) < 4.0:
        return _no("ground push < 4") or None
    _no("OPPORTUNITY")
    d = defender_play(s, ctx)
    sc = Prevent(ctx["tick"])
    if d is not None:                                  # affordable now: place it instead of the spell
        sc.done, sc.played = True, (ctx["tick"], cname(s, d["slot"]))
        return {**d, "script": sc, "need": 0.0}
    return {**NOPLAY, "why": "prevent", "script": sc, "need": round(need, 2)}


# ---------------------------------------------------------------------------------------------------- drill arms
def build_arms(mo, m, s, ctx):
    """-> {"do": {"root", "script"}, "alt": {...}} or {"_skip": reason}.  First option = DO, second = ALT (see summary)."""
    if mo.get("variant"):
        return variant_arms(mo, m, s, ctx)
    if mo["drill"] in ("D5", "D6", "D7", "D8"):
        return xl2_arms(mo, m, s, ctx)
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


def xl2_arms(mo, m, s, ctx):
    """New root-only DO / HOLD arms. HOLD keeps the named spell this decision."""
    dr, bs = mo["drill"], ctx["bs"]
    if getattr(s, "pending", None) is not None:
        return {"_skip": "play pending"}
    if dr == "D5":
        k = pick(s, ctx, ("log",))
        if k is None:
            return {"_skip": "Log not allowed"}
        from pipeline import vocab
        from pipeline.decision_options import rocket_unit_table
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "drills"))
        from sneaky_rule import unit_params
        table = rocket_unit_table()
        targets, small, barrels = [], [], []
        # Maximise public ground value in the whole corridor, including the
        # selected barrel landing point. Air units other than barrels never count.
        for u in bs.units:
            if int(u.side) != 1 or (u.hp_frac is not None and u.hp_frac <= 0):
                continue
            name = vocab.base_key(vocab.UNIT_VOCAB[int(u.cls)])
            row = table.get(name)
            if name in ("goblin_barrel", "skeleton_barrel"):
                value = 3.0
                if (1 - u.y) * 32.0 <= 18:
                    barrels.append((u.x * 18.0, (1 - u.y) * 32.0))
            elif row is not None and unit_params(int(u.cls))[0] == "troop":
                value = float(row[0])
                if value <= 1.0 and (1 - u.y) * 32.0 <= 18:
                    small.append((u.x * 18.0, (1 - u.y) * 32.0))
            else:
                continue
            targets.append((u.x * 18.0, (1 - u.y) * 32.0, value))
        info = mo.get("info") or {}
        if info.get("barrel"):
            targets.append((info["x"], info["y"], 3.0))
            barrels.append((info["x"], info["y"]))
        if not targets:
            return {"_skip": "no Log targets"}
        import torch
        with torch.no_grad():
            logits = s.model.cell_logits(ctx["enc"], torch.tensor([k], device=ctx["heads"]["card"].device))[0]
        X, Y = tiles(s.cfg["grid"], len(logits))
        score = sum(v * ((abs(X - x) <= 2.7) & (Y <= y) & (y - Y <= 10.6)) for x, y, v in targets)
        def corridor(x, y):
            return (abs(X - x) <= 2.7) & (Y <= y) & (y - Y <= 10.6)
        swarm_count = sum((corridor(x, y).astype(int) for x, y in small), np.zeros(len(X), int))
        barrel_hit = sum((corridor(x, y).astype(int) for x, y in barrels), np.zeros(len(X), int)) > 0
        eligible = (Y <= 18) & (score > 0) & ((swarm_count >= 3) | barrel_hit)
        if not eligible.any():
            return {"_skip": "no Log corridor"}
        best = score[eligible].max()
        d = play(s, ctx, k, "d5_do", lambda X, Y: eligible & (score == best))
    elif dr == "D6":
        from pipeline.decision_options import DecisionOptions, rocket_value_choice, rocket_value_cell
        # The deployed drift lead projects catalog movement through flight time;
        # no unobserved engine velocity or enemy state enters the aim.
        options = DecisionOptions(rocket_value=10.0, rocket_value_lead="drift", rocket_value_hitbox="edge")
        hit = rocket_value_choice(options, s.deck.cards, ctx["allowed"], bs, s.cfg["grid"])
        if hit is None:
            return {"_skip": "no >=10 impact clump on own half"}
        import torch
        k, eligible, value = hit
        with torch.no_grad():
            logits = s.model.cell_logits(ctx["enc"], torch.tensor([k], device=ctx["heads"]["card"].device))[0]
        d = dict(play=True, slot=int(k), cell=int(rocket_value_cell(logits, eligible)), why="d6_do")
    elif dr == "D7":
        if str(ctx["d"].get("why", "")).startswith("lethal"):
            return {"_skip": "model already takes lethal"}
        d = rocket_tower_choice(s, ctx["allowed"])
        if d is None:
            return {"_skip": "no late tower Rocket"}
    elif dr == "D8":
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "drills"))
        from sneaky_rule import sneaky_lock_choice
        from types import SimpleNamespace
        hit = sneaky_lock_choice(SimpleNamespace(sneaky_lock="on"), bs, s.deck.cards, ctx["allowed"], s.cfg["grid"])
        if hit is None:
            return {"_skip": "no sneaky-lock plan"}
        d = dict(play=True, slot=int(hit[0]), cell=int(hit[1]), why="sneaky_lock")
    else:
        raise ValueError(dr)
    return {"do": {"root": d, "script": None}, "alt": {"root": dict(NOPLAY), "script": None}}


def variant_arms(mo, m, s, ctx):
    """For search, B is the variant and ALT is exactly A (not a forced wait).

    Build the plain arm before applying q so all q use the same feasible population.
    A rejected WHEN gate retains the opportunity and copies A, including follow-ups.
    """
    variant = mo["variant"]
    arms = build_arms({k: v for k, v in mo.items() if k != "variant"}, m, s, ctx)
    if "_skip" in arms:
        return arms
    if variant == "DO_best_air":
        if mo["drill"] != "D4":
            raise ValueError("best-air variant only belongs to D4")
        slot = pick(s, ctx, ("tesla", "icewizard", "rocket"))
        if slot is None:
            return {"_skip": "no air-capable card allowed"}
        arms["do"] = {"root": play(s, ctx, slot, "d4_best_air"), "script": None}
    if variant.startswith("DO_when_"):
        q = float(variant.removeprefix("DO_when_"))
        if q not in (.3, .5, .7) or "p_pro" not in mo:
            raise ValueError("WHEN variant requires a fitted public probability and q in .3/.5/.7")
        if not 0 <= float(mo["p_pro"]) <= 1:
            raise ValueError("invalid pro probability")
        if float(mo["p_pro"]) < q:
            arms["do"] = {"root": dict(ctx["d"]), "script": None}
    elif variant not in ("DO", "DO_best_air"):
        raise ValueError("unknown XL2 variant: " + variant)
    arms["alt"] = {"root": dict(ctx["d"]), "script": None}
    return arms


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


# Shared verbatim with the original rocket_tower mechanic.
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
