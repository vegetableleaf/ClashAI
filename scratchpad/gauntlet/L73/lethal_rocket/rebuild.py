"""Rebuild the live model batch of every logged decision from a public-audit live log (live_play --public-audit).

EXACT from the log: tok / mask / sc / unit_form (BoardState from the logged model_bodies + model_towers, model tick,
model own elixir, the logged opponent-elixir estimate), hand (own_hand), projectiles / effects (the logged ACTIVE
rows of the actual model batch, zero padded), past (confirmed events: card, form, intended xy, confirm tick).
INFERRED: next card (the first deck index entering the hand after this decision), deck forms (own_hand forms).
APPROXIMATED: opp_past / opp_cycle / own_ability -- PublicObserver fed only the decision snapshots (raw_bodies +
raw_projectiles, ~every 10 ticks; live feeds every reader frame and its effects). Measured by replaying the logged
p_play / card / xy (validate()).
Public information only: nothing of the opponent's player block is in the log or used."""
import json, os, sys
from contextlib import contextmanager
from dataclasses import replace

import numpy as np
import torch

REPO = os.environ.get("CB_REPO") or os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.insert(0, REPO)
from pipeline.model_gen import load_model
from pipeline.obs_contract import BoardState, Tower, Unit, to_tokens, to_unit_forms, DOUBLE_ELIXIR_S, OVERTIME_S
from pipeline.dataset_gen import SC_SLOT_COLS, card_key, opponent_past
from pipeline.dataset import PAST_K
from pipeline.public_observation import PublicObserver, opponent_cycle
from pipeline.projectile_observation import PROJECTILE_K, EFFECT_K
from pipeline.own_ability import tokens as ability_tokens
from pipeline.e1_eval import allowed_slots
from pipeline.train_s1 import MAX_U
from pipeline.decision_options import rocket_radius_tiles, rocket_area_scores, cell_centres_tiles
from pipeline.public_geometry import constants

FORM_PAD = 3
EN_L, EN_R = (3.5, 6.5), (14.5, 6.5)          # enemy princess centres, board frame tiles (decision_options)


def read_log(path):
    ev = []
    for line in open(path):
        try:
            ev.append(json.loads(line))
        except ValueError:
            pass
    return ev


class Match:
    def __init__(self, log, ckpt, device="cpu"):
        self.ev = read_log(log)
        self.start = next(e for e in self.ev if e.get("event") == "start")
        self.model, st = load_model(ckpt, torch.device(device))
        self.model.eval()
        self.gid = {k: i for i, k in enumerate(st["card_vocab"])}
        self.grid = str(st["args"].get("grid", "lattice"))
        self.dec = [e for e in self.ev if e.get("event") == "decision"]
        self.side = self.dec[0]["public"]["observer_side"]
        # deck: deck_index -> (name, form) from every logged hand
        self.deck = {}
        for d in self.dec:
            for h in d["public"]["own_hand"]:
                if h["deck_index"] >= 0:
                    self.deck[h["deck_index"]] = (h["name"], h["form"])
        assert len(self.deck) == 8, self.deck
        self.form_of = {card_key(n): f for n, f in self.deck.values()}
        conf = [e for e in self.ev if e.get("event") == "confirmed"]
        self.past = [(e["tick"], self.gid[card_key(e["name"])], self.form_of[card_key(e["name"])],
                      e["intended"][0], e["intended"][1]) for e in conf]
        # own_events as GenPilot.record_play / record_ability feed PublicObserver.own_events
        hero = [n for n, f in self.deck.values() if f == 2]
        self.own_events = [dict(card=next(k for k, v in self.gid.items() if v == c), tick=t, side=self.side,
                                accepted=True, ability=False) for t, c, f, x, y in self.past]
        ab = [e["tick"] for e in self.ev if e.get("event") == "ability"]
        abc = [e["tick"] for e in self.ev if e.get("event") == "ability_confirmed"]
        for t in ab:   # pressed at t, confirmed later: record_ability(name, ab_pending tick) at confirmation
            c = next((u for u in abc if u >= t), None)
            if c is not None and hero:
                self.own_events.append(dict(card=card_key(hero[0]), tick=t, side=self.side, accepted=True,
                                            ability=True, _confirm=c))
        self._observer_states()

    def _observer_states(self):
        """Feed PublicObserver the decision snapshots in order; keep its plays / ability rows (causal)."""
        obs = PublicObserver(self.side)
        self.obs = obs
        for d in self.dec:
            p = d["public"]
            frame = dict(game_tick=p["raw_tick"], entities=p["raw_bodies"], projectiles=p["raw_projectiles"],
                         effects=[], players=[])
            obs.update(frame, source="reader")

    def next_index(self, i):
        hand = {h["deck_index"] for h in self.dec[i]["public"]["own_hand"]}
        for d in self.dec[i + 1:]:
            new = [h["deck_index"] for h in d["public"]["own_hand"] if h["deck_index"] not in hand and h["deck_index"] >= 0]
            if new:
                return new[0]
        return -1

    def board(self, i):
        p = self.dec[i]["public"]
        t = p["model_tick"] * 0.05
        units = tuple(Unit(**u) for u in p["model_bodies"])
        towers = tuple(Tower(**tw) for tw in p["model_towers"])
        return BoardState(source="live_mem", t_sec=t, t_source="tick", double_elixir=t >= DOUBLE_ELIXIR_S,
                          overtime=t >= OVERTIME_S, my_elixir=float(p["model_own_elixir"]), my_elixir_exact=True,
                          opp_elixir=p["opponent_elixir_estimate"], my_hand=(-1, -1, -1, -1), my_next=-1,
                          towers=towers, units=units, spells=(), deck=())

    def batch(self, i):
        d = self.dec[i]
        p = d["public"]
        raw_tick, mtick = p["raw_tick"], p["model_tick"]
        bs = self.board(i)
        tok, mask, sc = to_tokens(bs, MAX_U)
        sc = sc.copy()
        sc[SC_SLOT_COLS] = 0.0
        hand = [(h["card"], h["form"]) for h in p["own_hand"]]
        nd = self.next_index(i)
        nxt = (self.gid[card_key(self.deck[nd][0])], self.deck[nd][1]) if nd >= 0 else (0, FORM_PAD)
        deck = [self.gid[card_key(self.deck[k][0])] for k in range(8)]
        forms = [self.deck[k][1] for k in range(8)]
        order = np.argsort(deck, kind="stable")
        past = np.tile(np.array([0, FORM_PAD, -1, -1, -1], np.float32), (PAST_K, 1))
        done = [x for x in self.past if x[0] <= raw_tick]
        for k, (tc, c, f, x, y) in enumerate(reversed(done[-PAST_K:])):
            past[k] = (c, f, x, y, bs.t_sec - tc * 0.05)
        proj = np.zeros((PROJECTILE_K, 8), np.float32)
        if p["model_projectiles"]:
            proj[:len(p["model_projectiles"])] = p["model_projectiles"]
        eff = np.zeros((EFFECT_K, 6), np.float32)
        if p["model_effects"]:
            eff[:len(p["model_effects"])] = p["model_effects"]
        o = self.obs
        from bisect import bisect_right
        ai = bisect_right(o.ability_ticks, int(mtick)) - 1
        # own_events known at this decision: confirmed by raw_tick
        evs = [e for e in self.own_events if e.get("_confirm", e["tick"]) <= raw_tick]
        plays = [e for e in o.plays if e["tick"] <= raw_tick]
        T = lambda a, dt=torch.long: torch.as_tensor(np.asarray(a), dtype=dt).unsqueeze(0)  # noqa: E731
        b = {"tok": T(tok, torch.float32), "mask": T(mask, torch.bool), "sc": T(sc, torch.float32),
             "past": T(past, torch.float32), "hand_card": T([h[0] for h in hand]), "hand_form": T([h[1] for h in hand]),
             "next_card": T([nxt[0]]).squeeze(0), "next_form": T([nxt[1]]).squeeze(0),
             "deck_card": T(np.asarray(deck)[order]), "deck_form": T(np.asarray(forms)[order]),
             "unit_form": T(to_unit_forms(bs, MAX_U)),
             "opp_past": T(opponent_past(plays, int(mtick), self.side, self.gid), torch.float32),
             "opp_cycle": T(opponent_cycle(plays, int(mtick), self.side, self.gid), torch.float32),
             "own_ability": T(ability_tokens(o.ability_rows[ai] if ai >= 0 else [], self.gid, evs, int(mtick)), torch.float32),
             "projectiles": T(proj, torch.float32), "effects": T(eff, torch.float32)}
        costs = [h["cost"] for h in p["own_hand"]]
        allowed = allowed_slots(np.array([h[0] > 0 for h in hand]), costs, int(bs.my_elixir))
        return b, dict(hand=hand, names=[h["name"] for h in p["own_hand"]], allowed=allowed, bs=bs)


@contextmanager
def variant(model, name):
    """'full' = as loaded (base + CellRefine + TowerRefine); 'cr' = base + CellRefine; 'base' = neither."""
    saved = (model.cell_refine, getattr(model, "tower_refine", None))
    try:
        if name in ("cr", "base"):
            model.tower_refine = None
        if name == "base":
            model.cell_refine = None
        yield model
    finally:
        model.cell_refine, model.tower_refine = saved


_CX, _CY = cell_centres_tiles("lattice")


def tower_masks(grid="lattice"):
    cx, cy = cell_centres_tiles(grid)
    r = rocket_radius_tiles()
    tr = constants()["tower_radius"]["PrincessTower"] / 1000.0
    out = {}
    for lane, (tx, ty) in (("L", EN_L), ("R", EN_R)):
        dist = np.hypot(cx - tx, cy - ty)
        out[lane] = dist <= r                     # aim point within the Rocket radius of the tower centre
        out[lane + "_hit"] = dist <= r + tr       # the Rocket area touches the tower's collision circle
    return out, r, tr


@torch.no_grad()
def analyse(m, b, info, model, variants=("base", "cr", "full")):
    """Gate p, card distribution over allowed slots, and the Rocket cell distribution per variant."""
    masks, _, _ = tower_masks(m.grid)
    rk = m.gid["rocket"]
    out = {}
    for v in variants:
        with variant(model, v):
            o = model(b)
            p = float(torch.sigmoid(o["gate"][0]))
            lg = o["card"][0].clone()
            lg[~torch.from_numpy(info["allowed"])] = -torch.inf
            pc = torch.softmax(lg, -1).numpy()
            names = info["names"]
            r = dict(p=round(p, 4), card={n: round(float(x), 4) for n, x in zip(names, pc)},
                     top=names[int(lg.argmax())])
            slots = [k for k, h in enumerate(info["hand"]) if h[0] == rk]
            if slots:
                f = info["hand"][slots[0]][1]
                cell = model(b, card=torch.tensor([rk]), form=torch.tensor([f]))["cell"]
                pr = torch.softmax(cell, -1)
                pn = pr[0].numpy()
                area = rocket_area_scores(pr)[0].numpy()
                amax, aarea = int(cell[0].argmax()), None
                mx = area == area.max()
                aarea = int(cell[0].masked_fill(~torch.from_numpy(mx), -torch.inf).argmax())
                lane = lambda c: ("L" if _CX[c] < 9 else "R") + ("_tower" if (masks["L_hit"][c] or masks["R_hit"][c]) else "_off")
                r.update(rk_mass={k: round(float(pn[mk].sum()), 4) for k, mk in masks.items()},
                         rk_argmax=(round(_CX[amax], 2), round(_CY[amax], 2), lane(amax)),
                         rk_area=(round(_CX[aarea], 2), round(_CY[aarea], 2), lane(aarea), round(float(area.max()), 4)),
                         rk_area_at_tower={k: round(float(area[mk].max()), 4) for k, mk in masks.items() if "_" not in k})
            out[v] = r
    return out
