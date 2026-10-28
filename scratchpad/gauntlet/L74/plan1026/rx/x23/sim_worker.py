"""RX-X23 SIM worker (X2 farm audit + X3 SIM calibration): gap.py's D3 worker (all16 levels, the deployed LIVE_OPTIONS
decision stack) with two read-mostly hooks, nothing in pipeline/ edited, nothing wired into training.

1. Recorder: every 10 engine ticks (each decision round that crosses a 10-tick boundary, plus the final state) one
   snapshot of the raw SIM state in the HF re-drive's format (hf_traces.frames_of input: bodies with native card ids,
   towers, BOTH sides' exact elixir; SIM features may be exact). At match end the same r_exchange code as the HF traces
   (running_losses, public_streams, 1 row per s) -> OUT/x23/<seed>.npz {t, L, C, LT, E}, observer = our side.
2. Policy (env X23_POLICY): a scripted override of OUR final decision d (after the whole live stack), applied in
   SelfPlaySide.apply; the opponent is untouched.
     clxiii      no override (also used for the imitation model: --ckpt = that model)
     hold10      A3's hold_to_10 (preflight_a1a2.py): WAIT below 10 elixir; at 10 the model's play if it plays, else the
                 model's top (card, cell) (search_s0.shortlist top-1)
     nospell     a play of Rocket / Log / Tornado -> WAIT
     rocket_tower  Rocket in hand and affordable -> Rocket the enemy princess tower with the least HP (king when both
                 are down); otherwise the model's decision
     alldef      a play is kept only while an enemy troop is on our half AND its cell is on our half; else WAIT
     xbow_spam   X-Bow in hand and affordable -> X-Bow at the live bridge point (board 0.139 / 0.861, 0.609; median
                 of 841 live Ranked X-Bows, opp_model/w18/xbow_states.json) in the lane of the weaker enemy princess
     rocket_tank Rocket in hand and affordable and an enemy tank (TANKS) on the board -> Rocket the tank's position
   Each override is counted into the match row (x23.over).

    python sim_worker.py --worker-x23 <livecal worker args>      (spawned by run_x23.py through gap.py's run_arm)
"""
import collections
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
L74 = ROOT / "scratchpad/gauntlet/L74"
sys.path[:0] = [str(ROOT), str(L74 / "livecal"), str(L74 / "heroiw"), str(HERE.parent)]

POLICIES = ("clxiii", "hold10", "nospell", "rocket_tower", "alldef", "xbow_spam", "rocket_tank")
SPELLS = {"rocket", "log", "thelog", "tornado"}                      # the icebow deck's spells (E.ICEBOW_ENGINE_DECK)
TANKS = {"golem", "giant", "pekka", "megaknight", "royalgiant", "lavahound", "electrogiant", "goblingiant",
         "giantskeleton", "elixirgolem", "runegiant", "goblinstein", "bossbandit"}
BRIDGE = {0: (0.139, 0.609), 1: (0.861, 0.609)}                       # my-frame board x, y; 0 = left lane
EX, EY = 18000.0, 32000.0                                            # raw() units (obs_contract ENGINE_X / ENGINE_Y)
WAIT = {"play": False, "slot": -1, "cell": -1, "why": "x23_wait"}


def norm(n):
    return "".join(ch for ch in str(n).split("@")[0].lower() if ch.isalnum())


def card_catalog():
    """pro2/build_rows.card_catalog (copied: its module imports pro2/convert -> phase_stats, absent from pod trees)."""
    import json
    from pipeline import vocab
    cards = json.loads((ROOT / "research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json")
                       .read_text(encoding="utf-8"))["cards"]
    out = {}
    for c in sorted(cards, key=lambda c: not c.get("standard_1v1")):
        if vocab.engine_key(c["display_name"]):
            out.setdefault(vocab.base_key(vocab.engine_key(c["display_name"])).replace("_", "-"), c)
    return out


def snap(raw, catalog):
    """build_rows.snapshot's fields (entities with native card ids, towers, elixir), unmapped bodies -> card id -1
    (hf_traces.frames_of drops them) instead of raising."""
    from pipeline import vocab
    from pipeline.obs_contract import entity_form

    def lookup(name, form):
        c = catalog.get(vocab.base_key(vocab.engine_key(name) or "").replace("_", "-"))
        v = None if c is None else c.get(("card_id", "evolution_form_id", "hero_form_id")[form])
        return -1 if v is None else v
    ents = [[e["side"], e["x"], e["y"], e["name"], e["hp"], e["max_hp"], e.get("kind", -1),
             e.get("public_card_id") or lookup(e["name"], entity_form(e)), e["entity_id"]] for e in raw["entities"]]
    # the Hero IW body carries public_card_id 203000023 (royale_env.raw; build.HERO_IW, valued as the Ice Wizard)
    towers = [[e["side"], e["type"], None, e["x"], e["y"], e["hp"], e["max_hp"]] for e in raw["episode"]["crown_towers"]]
    return {"tick": int(raw["tick"]), "entities": ents, "towers": towers, "elixir": [p["elixir_exact"] for p in raw["players"]]}


def as_side0(f, L):
    """observer L -> side 0 (hf_traces.frames_of's observer): sides swapped, y mirrored (threat halves), elixir swapped."""
    if L == 0:
        return f
    return {"tick": f["tick"], "elixir": f["elixir"][::-1],
            "entities": [[1 - e[0], e[1], EY - e[2], *e[3:]] for e in f["entities"]],
            "towers": [[1 - t[0], t[1], t[2], t[3], EY - t[4], *t[5:]] for t in f["towers"]]}


def board(X, Y, mirror):
    """raw / engine position -> my-frame board (x, y) in [0, 1] (inverse of engine_play.board_to_engine)."""
    if mirror:
        X, Y = EX - X, EY - Y
    return X / EX, 1.0 - Y / EY


_CENTERS = {}


def cell_at(x, y, grid):
    if grid not in _CENTERS:
        from pipeline import engine_play as ep
        from pipeline.model_v3 import GRID_X, GRID_Y
        _CENTERS[grid] = np.array([ep.cell_center(c, grid) for c in range(GRID_X * GRID_Y)])
        # ponytail: nearest cell centre; a cell the engine refuses (river, tower) is the engine's refusal, as live
    c = _CENTERS[grid]
    return int(np.argmin((c[:, 0] - x) ** 2 + (c[:, 1] - y) ** 2))


def override(s, d):
    """-> the decision our side carries out under X23_POLICY (d itself when unchanged)."""
    from pipeline import e1_eval as E
    from pipeline import search_s0 as S
    pol = POL
    if pol == "clxiii":
        return d
    el, allowed, _ = s._x23_pre
    slot = lambda name: s.deck.slot_of(E.vocab.engine_key(name))                    # noqa: E731
    can = lambda name: bool(allowed[slot(name)])                                    # noqa: E731
    play = lambda name, x, y, why: {"play": True, "slot": int(slot(name)), "cell": cell_at(x, y, s.cfg["grid"]),  # noqa: E731
                                    "why": why}
    card = S._slug(s.deck.cards[d["slot"]]) if d["play"] else None
    if pol == "hold10":
        if el < 10 or not allowed.any():
            return WAIT if d["play"] else d
        if d["play"]:
            return d
        _, enc, heads, _ = s._x23_fw
        return {**S.shortlist(s.model, enc, heads, allowed, 1, 1)[0], "why": "x23_hold10"}
    if pol == "nospell":
        return WAIT if card in SPELLS else d
    raw = s.env.raw()
    towers = [t for t in raw["episode"]["crown_towers"] if t["side"] != s.side and t["hp"] > 0]
    if pol == "rocket_tower":
        if not can("Rocket") or not towers:
            return d
        pr = [t for t in towers if t["type"] == "princess"] or towers
        t = min(pr, key=lambda t: t["hp"] / max(1, t["max_hp"]))
        return play("Rocket", *board(t["x"], t["y"], s.mirror), "x23_rocket_tower")
    if pol == "rocket_tank":
        tanks = [e for e in raw["entities"] if e["side"] != s.side and norm(e["name"]) in TANKS]
        if not can("Rocket") or not tanks:
            return d
        e = max(tanks, key=lambda e: e["hp"])
        return play("Rocket", *board(e["x"], e["y"], s.mirror), "x23_rocket_tank")
    if pol == "xbow_spam":
        if not can("Xbow"):
            return d
        pr = {round(board(t["x"], t["y"], s.mirror)[0]): t["hp"] / max(1, t["max_hp"])
              for t in towers if t["type"] == "princess"}                          # 0 = left, 1 = right (my frame)
        lane = min(pr, key=lambda k: (pr[k], -k)) if pr else 1
        return play("Xbow", *BRIDGE[lane], "x23_xbow_spam")
    if pol == "alldef":
        if not d["play"]:
            return d
        mine = (lambda Y: Y < EY / 2) if s.side == 0 else (lambda Y: Y > EY / 2)
        threat = any(e["side"] != s.side and mine(e["y"]) for e in raw["entities"])
        from pipeline import engine_play as ep
        on_mine = ep.cell_center(d["cell"], s.cfg["grid"])[1] >= 0.5
        return d if threat and on_mine else WAIT
    raise ValueError(f"X23_POLICY {pol!r} not in {POLICIES}")


def install():
    from pipeline import search_s0 as S
    import build
    import hf_traces as HT
    from pipeline import r_exchange as RX
    catalog, values = card_catalog(), build.load_values()
    forward0, play0, round0 = S.forward, S.Runner.play, S.Runner.round

    def forward(s):
        out = forward0(s)
        s._x23_fw = out
        return out

    def record(m, final=False):
        t = int(m.env.tick)
        if final or t // 10 != m._x23_last:
            m._x23_frames.append(snap(m.env.raw(), catalog))
            m._x23_last = t // 10

    def round_(self, m, ds, arm, st, rng):
        record(m)
        return round0(self, m, ds, arm, st, rng)

    def play(self, arm, m, deadline=None):
        s = m.learner
        m._x23_frames, m._x23_last = [], None
        over = collections.Counter()
        cls_apply, cls_pre = type(s).apply, type(s).pre

        def pre(hand):
            r = s._x23_pre = cls_pre(s, hand)
            return r

        def apply(p, d):
            d2 = override(s, d)
            if d2 is not d:
                over[d2["why"]] += 1
            return cls_apply(s, p, d2)
        s.pre, s.apply = pre, apply
        row = play0(self, arm, m, deadline)
        record(m, final=True)
        L = s.side
        fr = HT.frames_of({"frames": [as_side0(f, L) for f in m._x23_frames]})
        ticks, Ls = RX.running_losses(fr, values)
        _, C, LT = RX.public_streams(fr)
        keep = np.r_[np.nonzero(np.diff(ticks // build.SAMPLE, prepend=-1))[0], len(ticks) - 1]
        E2 = np.array([[f["elixir"], f["opp_elixir"]] for f in fr], np.float32)
        dest = Path(OUT) / "x23"
        dest.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(dest / f"{row['seed']}.npz", t=ticks[keep], L=Ls[keep].astype(np.float32),
                            C=C[keep].astype(np.float32), LT=LT[keep].astype(np.float32), E=E2[keep])
        unk = collections.Counter(str(e[3]) for f in m._x23_frames for e in f["entities"] if e[7] == -1)
        row["x23"] = {"policy": POL, "frames": len(fr), "unmapped_bodies": dict(unk), "over": dict(over)}
        return row

    S.forward, S.Runner.play, S.Runner.round = forward, play, round_


def main():
    global POL, OUT
    assert sys.argv[1] == "--worker-x23"
    POL = os.environ.get("X23_POLICY", "clxiii")
    if POL not in POLICIES:
        raise SystemExit(f"X23_POLICY {POL!r} not in {POLICIES}")
    OUT = sys.argv[sys.argv.index("--out") + 1]
    from pipeline import search_s0 as S
    from pipeline.rl_royale import _live_level_table
    original = S._init_worker

    def init_worker(args):                       # gap.worker_all16's all16 levels
        original(args)
        S._W["runner"].live_levels = _live_level_table("all16")
    S._init_worker = init_worker
    install()
    import livecal
    return livecal.worker()


POL = OUT = None
if __name__ == "__main__":
    raise SystemExit(main())
