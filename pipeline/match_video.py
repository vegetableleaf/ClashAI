"""Render a recorded engine match (`engine_play.py --record-every N`) as a vertical MP4.

This is NOT the game's graphics -- the sandbox engine has no renderer and no art. It draws the engine's
own state, the way the old `sim-view` debugger drew the Python sim: every body with its name, hp bar,
shape (circle = troop, square = building, dotted while still deploying) and a movement tick; its ATTACK
range (solid ring) and AGGRO / sight radius (dotted ring); a line from every attacker to the thing it is
targeting (bright while a hit is loading); every projectile in flight with its name and a line to where
it will land; spell / effect objects as rings; both elixir bars, the model's hand, its gate probability,
a flash and a rolling log at every placement.

Where the numbers come from (say so when you show it):
  * positions, hp, kind, target, projectiles, effects -- the engine's `observe()` every N ticks;
  * attack range -- `<deck>/config/cards_stats.json` (wiki level-11 import, `range_tiles`);
  * aggro / sight -- the game-data table copied from `clashrl/cards.py:_SIGHT_TILES` (5.5 tiles unless
    listed), princess tower 7.5 / king 7.0 tiles (game data, NOT the old sim's 8.0 / 8.5 which folded in
    the collision radius);
  * the engine reports no range of its own, so a ring is a wiki number drawn around an engine body.

Output is 1080x1920 (Instagram's vertical frame) at the recording's own rate, so a 3-minute match at
`--record-every 2` is a ~3-minute clip. `--speed` drops frames to fit a shorter slot.

Usage:
    python pipeline/match_video.py <frames_*.json> -o clip.mp4 [--speed 3] [--label "icebow v4 - 19.8% top-1"]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from pipeline import vocab  # noqa: E402

ENGINE_X, ENGINE_Y = 18000.0, 32000.0
UNITS_PER_TILE = 1000.0                   # 18 x 32 tiles, engine units are milli-tiles
TILES_X, TILES_Y = 18, 32

W, H = 1080, 1920
TILE = 45                                 # px per tile -- square tiles, so a range ring is a circle
BOARD_W, BOARD_H = TILES_X * TILE, TILES_Y * TILE          # 810 x 1440
BOARD_X0 = (W - BOARD_W) // 2                                # 135
BOARD_TOP = 240
BOARD_BOT = BOARD_TOP + BOARD_H                              # 1680
PALETTE = {
    "bg":     (24, 22, 20),
    "ground": (58, 74, 52),
    "grid":   (68, 86, 60),
    "river":  (140, 108, 60),
    "bridge": (92, 120, 130),
    "line":   (96, 96, 92),
    "text":   (238, 236, 228),
    "muted":  (150, 148, 140),
    "me":     (210, 132, 44),               # BGR: blue-ish = the model
    "them":   (58, 68, 208),                # BGR: red = opponent
    "flash":  (120, 235, 250),
    "reject": (60, 60, 220),
    "elx":    (200, 80, 190),
    "proj":   (80, 220, 250),
    "fx":     (210, 200, 90),
}
FONT = cv2.FONT_HERSHEY_SIMPLEX

# AGGRO / SIGHT radius in tiles, copied from icebow/src/clashrl/cards.py:_SIGHT_TILES (RoyaleAPI
# cr-api-data characters.sight_range, 1000 units = 1 tile). Everything not listed is 5.5.
SIGHT_TILES = {
    "pekka": 5.0, "giant_skeleton": 5.0,
    "musketeer": 6.0, "three_musketeers": 6.0, "elite_barbarians": 6.0,
    "golem": 7.0, "golemite": 7.0, "ice_golem": 7.0,
    "giant": 7.5, "goblin_giant": 7.5, "royal_giant": 7.5, "electro_giant": 7.5,
    "elixir_golem": 7.5, "elixir_golemite": 7.5, "elixir_blob": 7.5, "dart_goblin": 7.5,
    "balloon": 7.7, "skeleton_barrel": 7.7,
    "firecracker": 8.5,
    "hog_rider": 9.5, "royal_hogs": 9.5, "princess": 9.5,
}
SIGHT_DEFAULT = 5.5
TOWER_RANGE = {"king": 7.0, "princess": 7.5}                 # tiles, game data

KIND_BUILDING = {12, 13}
KIND_DEPLOYING = {12, 14}                 # dormant building / troop still in its deploy timer


# ------------------------------------------------------------------------------------------------------
# card naming and stats
# ------------------------------------------------------------------------------------------------------
class Cards:
    """card_id / engine internal name -> display name, attack range, sight, spell radius."""

    def __init__(self, stats_path: Path, catalog_path: Path):
        self.stats = json.loads(stats_path.read_text(encoding="utf-8"))["cards"] if stats_path.exists() else {}
        self.by_id: dict[int, str] = {}
        if catalog_path.exists():
            for it in json.loads(catalog_path.read_text(encoding="utf-8"))["cards"]:
                nm = it.get("internal_name")
                for k in ("card_id", "evolution_form_id", "hero_form_id"):
                    if it.get(k) is not None:
                        self.by_id[int(it[k])] = nm

    def key(self, engine_name) -> str | None:
        return vocab.engine_key(engine_name) if engine_name else None

    def key_of_id(self, card_id) -> str | None:
        if card_id is None or int(card_id) < 0:
            return None
        return self.key(self.by_id.get(int(card_id)))

    def display(self, engine_name) -> str:
        k = self.key(engine_name)
        st = self.stats.get(k or "")
        if st and st.get("display"):
            return st["display"]
        if k:
            return k.replace("_", " ")
        return re.sub(r"(?<!^)(?=[A-Z])", " ", str(engine_name or ""))

    def display_of_id(self, card_id) -> str:
        if card_id is None or int(card_id) < 0:
            return "tower"
        nm = self.by_id.get(int(card_id))
        return self.display(nm) if nm else str(card_id)

    def attack_range(self, engine_name) -> float:
        st = self.stats.get(self.key(engine_name) or "") or {}
        v = st.get("range_tiles")
        return float(v) if v else 0.0

    def sight(self, engine_name) -> float:
        k = self.key(engine_name) or ""
        base = vocab.base_key(k)
        return SIGHT_TILES.get(k, SIGHT_TILES.get(base, SIGHT_DEFAULT))

    def spell_radius(self, card_id) -> float:
        st = self.stats.get(self.key_of_id(card_id) or "") or {}
        v = st.get("radius_tiles") or st.get("splash_radius")
        return float(v) if v else 0.0


# ------------------------------------------------------------------------------------------------------
# drawing helpers
# ------------------------------------------------------------------------------------------------------
def board_px(x: float, y: float, mirror: bool) -> tuple[int, int]:
    """Engine units -> pixels. The model always plays from the BOTTOM, so mirror when it is side 1."""
    tx, ty = x / UNITS_PER_TILE, y / UNITS_PER_TILE
    if mirror:
        tx, ty = TILES_X - tx, TILES_Y - ty
    return int(round(BOARD_X0 + tx * TILE)), int(round(BOARD_BOT - ty * TILE))


def tiles_px(t: float) -> int:
    return int(round(t * TILE))


def text(img, s: str, org, scale: float, col, thick: int = 1) -> None:
    """Outlined text so a label stays readable over any body or ring. The outline is the SAME thickness
    drawn at four 1 px offsets: cv2 widens the glyph advance with thickness (measured: 102 px at 1,
    108 px at 2+), so a thicker black pass drifts right of the coloured one and leaves a ghost tail."""
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        cv2.putText(img, s, (org[0] + dx, org[1] + dy), FONT, scale, (0, 0, 0), thick, cv2.LINE_AA)
    cv2.putText(img, s, org, FONT, scale, col, thick, cv2.LINE_AA)


def dim(col, k: float = 0.55):
    return tuple(int(c * k) for c in col)


def dotted_circle(img, c, r: int, col, step_deg: int = 12, arc_deg: int = 6, thick: int = 1) -> None:
    for a in range(0, 360, step_deg):
        cv2.ellipse(img, c, (r, r), 0, a, a + arc_deg, col, thick, cv2.LINE_AA)


def dotted_rect(img, p0, p1, col, thick: int = 1, dash: int = 6) -> None:
    (x0, y0), (x1, y1) = p0, p1
    for x in range(x0, x1, dash * 2):
        cv2.line(img, (x, y0), (min(x + dash, x1), y0), col, thick)
        cv2.line(img, (x, y1), (min(x + dash, x1), y1), col, thick)
    for y in range(y0, y1, dash * 2):
        cv2.line(img, (x0, y), (x0, min(y + dash, y1)), col, thick)
        cv2.line(img, (x1, y), (x1, min(y + dash, y1)), col, thick)


def draw_arena(img) -> None:
    cv2.rectangle(img, (BOARD_X0, BOARD_TOP), (BOARD_X0 + BOARD_W, BOARD_BOT), PALETTE["ground"], -1)
    for i in range(1, TILES_X):
        x = BOARD_X0 + i * TILE
        cv2.line(img, (x, BOARD_TOP), (x, BOARD_BOT), PALETTE["grid"], 1)
    for j in range(1, TILES_Y):
        y = BOARD_TOP + j * TILE
        cv2.line(img, (BOARD_X0, y), (BOARD_X0 + BOARD_W, y), PALETTE["grid"], 1)
    ymid = BOARD_TOP + BOARD_H // 2                              # the river: one tile either side
    cv2.rectangle(img, (BOARD_X0, ymid - TILE), (BOARD_X0 + BOARD_W, ymid + TILE), PALETTE["river"], -1)
    for bx in (3, 14):                                           # bridges at tiles 3-4 and 14-15
        cv2.rectangle(img, (BOARD_X0 + bx * TILE, ymid - TILE), (BOARD_X0 + (bx + 1) * TILE, ymid + TILE),
                      PALETTE["bridge"], -1)
    cv2.rectangle(img, (BOARD_X0, BOARD_TOP), (BOARD_X0 + BOARD_W, BOARD_BOT), PALETTE["line"], 2)


def team_col(side: int, me: int):
    return PALETTE["me"] if side == me else PALETTE["them"]


def body_radius(e: dict, is_tower: bool, is_building: bool) -> int:
    if is_tower:
        return 24 if (e.get("max_hp") or 0) > 4000 else 20    # king / princess
    hp = float(e.get("max_hp") or e.get("hp") or 0)
    r = 8 + 12 * math.sqrt(max(hp, 1.0) / 3000.0)
    return int(max(8, min(20, r))) + (2 if is_building else 0)


# ------------------------------------------------------------------------------------------------------
# one frame
# ------------------------------------------------------------------------------------------------------
class Renderer:
    def __init__(self, cards: Cards, me: int, mirror: bool, label: str, radii: bool, aggro: bool):
        self.cards, self.me, self.mirror, self.label = cards, me, mirror, label
        self.radii, self.aggro = radii, aggro
        self.log: list[tuple[float, str, bool, str | None]] = []   # (clock, card, accepted, reason)
        self.p_gate: float | None = None
        self.flash: tuple[int, dict] | None = None                  # (frames left, play)

    # -- layers ----------------------------------------------------------------------------------------
    def _rings(self, img, ents: list[dict]) -> None:
        """Attack range (solid) and aggro / sight (dotted) for every alive body, drawn first so bodies
        sit on top. Spells have no ring; a deploying body has none yet."""
        for e in ents:
            if e["_deploying"] or e.get("hp", 1) <= 0:
                continue
            c, col = e["_px"], dim(e["_col"], 0.45)
            if e["_tower"]:
                r = TOWER_RANGE["king" if body_radius(e, True, True) == 24 else "princess"]
                cv2.circle(img, c, tiles_px(r), col, 1, cv2.LINE_AA)
                continue
            r_atk = self.cards.attack_range(e.get("name"))
            if r_atk > 0:
                cv2.circle(img, c, tiles_px(r_atk), col, 1, cv2.LINE_AA)
            if not e["_building"]:
                dotted_circle(img, c, tiles_px(self.cards.sight(e.get("name"))), dim(e["_col"], 0.32))

    def _aggro_lines(self, img, ents: list[dict], by_id: dict[str, dict]) -> None:
        for e in ents:
            t = by_id.get(e.get("target") or "")
            if t is None or e["_deploying"]:
                continue
            loading = (e.get("attack_progress_ms") or 0) > 0
            col = e["_col"] if loading else dim(e["_col"], 0.6)
            cv2.line(img, e["_px"], t["_px"], col, 2 if loading else 1, cv2.LINE_AA)
            if loading:
                cv2.circle(img, t["_px"], 6, col, 1, cv2.LINE_AA)

    def _effects(self, img, fr: dict, proj_ids: set[str]) -> None:
        for q in fr.get("effects", []):
            if q.get("id") in proj_ids or q.get("x") is None:
                continue
            c = board_px(float(q["x"]), float(q["y"]), self.mirror)
            r = self.cards.spell_radius(q.get("card_id")) or 1.5
            col = PALETTE["fx"]
            cv2.circle(img, c, tiles_px(r), col, 2, cv2.LINE_AA)
            text(img, self.cards.display_of_id(q.get("card_id")), (c[0] - 30, c[1] - tiles_px(r) - 6), 0.5, col)

    def _bodies(self, img, ents: list[dict]) -> None:
        for e in ents:
            c, col, r = e["_px"], e["_col"], e["_r"]
            hp, mx = float(e.get("hp") or 0), float(e.get("max_hp") or 0) or 1.0
            if e["_tower"] or e["_building"]:
                p0, p1 = (c[0] - r, c[1] - r), (c[0] + r, c[1] + r)
                if e["_deploying"]:
                    dotted_rect(img, p0, p1, col, 2)
                else:
                    cv2.rectangle(img, p0, p1, col, -1)
                    cv2.rectangle(img, p0, p1, dim(col, 0.5), 1)
            elif e["_deploying"]:
                dotted_circle(img, c, r, col, 20, 10, 2)
            else:
                cv2.circle(img, c, r, col, -1, cv2.LINE_AA)
                cv2.circle(img, c, r, dim(col, 0.5), 1, cv2.LINE_AA)
                dx, dy = float(e.get("movement_direction_x") or 0), float(e.get("movement_direction_y") or 0)
                if dx or dy:                                  # movement tick: engine units, so mirroring is free
                    n = math.hypot(dx, dy)
                    tip = board_px(float(e["x"]) + dx / n * 700.0, float(e["y"]) + dy / n * 700.0, self.mirror)
                    cv2.line(img, c, tip, PALETTE["text"], 2, cv2.LINE_AA)
            # hp bar under the body; towers also get the number
            bw = max(30, 2 * r)
            x0, y0 = c[0] - bw // 2, c[1] + r + 4
            cv2.rectangle(img, (x0, y0), (x0 + bw, y0 + 5), (30, 30, 30), -1)
            cv2.rectangle(img, (x0, y0), (x0 + int(bw * max(0.0, min(1.0, hp / mx))), y0 + 5), col, -1)
            if e["_tower"]:
                text(img, "%s %d" % ("King" if r == 24 else "Princess", int(hp)), (x0 - 6, y0 + 20), 0.45, PALETTE["text"])
            else:
                nm = e["_name"]
                if e.get("form_name", "").endswith("_hero"):
                    nm += " (hero)"
                text(img, nm, (c[0] - min(len(nm) * 5, 60), y0 + 19), 0.42, PALETTE["text"])
                st = e.get("ability_state_name")
                if st and st not in ("ready", "deploying", "unknown_native_state"):
                    text(img, st, (c[0] - 20, c[1] - r - 8), 0.42, PALETTE["flash"])

    def _projectiles(self, img, fr: dict) -> None:
        for q in fr.get("projectiles", []):
            if q.get("x") is None:
                continue
            c = board_px(float(q["x"]), float(q["y"]), self.mirror)
            col = team_col(int(q.get("side", 0)), self.me)
            if q.get("target_x") is not None:
                t = board_px(float(q["target_x"]), float(q["target_y"]), self.mirror)
                cv2.line(img, c, t, dim(PALETTE["proj"], 0.6), 1, cv2.LINE_AA)
                cv2.circle(img, t, 4, dim(PALETTE["proj"], 0.6), 1, cv2.LINE_AA)
            cv2.circle(img, c, 5, PALETTE["proj"], -1, cv2.LINE_AA)
            cv2.circle(img, c, 5, col, 1, cv2.LINE_AA)
            cid = q.get("card_id")
            if cid is not None and int(cid) >= 0:            # tower shots stay a bare dot, no label spam
                text(img, self.cards.display_of_id(cid), (c[0] + 8, c[1] - 6), 0.42, PALETTE["proj"])

    def _flash(self, img) -> None:
        if self.flash is None:
            return
        left, play = self.flash
        if play.get("x") is None:
            return
        c = board_px(float(play["x"]) * ENGINE_X, float(play["y"]) * ENGINE_Y, self.mirror)
        col = PALETTE["flash"] if play.get("accepted") else PALETTE["reject"]
        for rad in (26, 40, 54):
            cv2.circle(img, c, rad + (3 - left) * 4, col, 2, cv2.LINE_AA)
        s = self.cards.display(play.get("card", "")) if play.get("card") else ""
        if not play.get("accepted"):
            s += "  x %s" % (play.get("reason") or "refused")
        text(img, s, (c[0] - 60, c[1] - 66), 0.65, col, 2)
        self.flash = (left - 1, play) if left > 1 else None

    def _hud(self, img, fr: dict, clock: float, crowns) -> None:
        me = self.me
        text(img, self.label, (BOARD_X0, 70), 1.0, PALETTE["text"], 2)
        text(img, "engine state, not game art -- solid ring = attack range, dotted = aggro, line = target",
             (BOARD_X0, 108), 0.48, PALETTE["muted"])
        text(img, "%d:%02d" % (int(clock // 60), int(clock % 60)), (W - BOARD_X0 - 120, 70), 1.0, PALETTE["text"], 2)
        if crowns is not None:
            text(img, "crowns %d - %d" % (crowns[0], crowns[1]), (W - BOARD_X0 - 220, 108), 0.6, PALETTE["text"])
        elx = {int(p.get("side", i)): float(p.get("elixir_exact", p.get("elixir")) or 0)
               for i, p in enumerate(fr.get("players", []))}
        hands = {int(p.get("side", i)): [h.get("name", "") for h in p.get("hand", [])]
                 for i, p in enumerate(fr.get("players", []))}
        for side, y0, who in ((1 - me, 150, "opponent"), (me, BOARD_BOT + 22, "model")):
            v = elx.get(side, 0.0)
            cv2.rectangle(img, (BOARD_X0, y0), (BOARD_X0 + BOARD_W, y0 + 30), (44, 42, 40), -1)
            w = int(BOARD_W * max(0.0, min(1.0, v / 10.0)))
            cv2.rectangle(img, (BOARD_X0, y0), (BOARD_X0 + w, y0 + 30), PALETTE["elx"], -1)
            for k in range(1, 10):
                x = BOARD_X0 + int(BOARD_W * k / 10)
                cv2.line(img, (x, y0), (x, y0 + 30), (30, 28, 26), 1)
            text(img, "%s  %.1f" % (who, v), (BOARD_X0 + 8, y0 + 22), 0.6, PALETTE["text"])
        # the model's hand, the card just played highlighted
        just = self.flash[1].get("card") if self.flash else None
        cw = BOARD_W // 4
        for i, nm in enumerate(hands.get(me, [])[:4]):
            x0 = BOARD_X0 + i * cw
            k = vocab.engine_key(nm) if nm else None
            hot = just is not None and k is not None and vocab.base_key(just) == vocab.base_key(k)
            cv2.rectangle(img, (x0 + 4, BOARD_BOT + 66), (x0 + cw - 4, BOARD_BOT + 130),
                          PALETTE["flash"] if hot else (44, 42, 40), -1)
            text(img, self.cards.display(nm)[:14], (x0 + 12, BOARD_BOT + 106), 0.52,
                 (20, 20, 20) if hot else PALETTE["text"])
        if self.p_gate is not None:                             # the gate head: "how much it wants to play now"
            x0, y0 = BOARD_X0, BOARD_BOT + 150
            cv2.rectangle(img, (x0, y0), (x0 + 300, y0 + 16), (44, 42, 40), -1)
            cv2.rectangle(img, (x0, y0), (x0 + int(300 * self.p_gate), y0 + 16), PALETTE["me"], -1)
            text(img, "gate %.2f" % self.p_gate, (x0 + 6, y0 + 13), 0.45, PALETTE["text"])
        # rolling placement log, newest last
        for j, (t, card, acc, reason) in enumerate(self.log[-4:]):
            s = "%d:%02d %s %s" % (int(t // 60), int(t % 60), self.cards.display(card),
                                   "ok" if acc else "x " + (reason or "refused"))
            text(img, s, (BOARD_X0 + 400, BOARD_BOT + 152 + 18 * j), 0.45,
                 PALETTE["text"] if acc else PALETTE["reject"])

    # -- the frame -------------------------------------------------------------------------------------
    def draw(self, fr: dict, clock: float, crowns) -> np.ndarray:
        board = np.full((H, W, 3), PALETTE["bg"], np.uint8)     # board layers, clipped to the arena below
        draw_arena(board)
        if "p_gate" in fr:
            self.p_gate = float(fr["p_gate"])
        if fr.get("play") is not None:
            p = fr["play"]
            self.flash = (3, p)
            self.log.append((clock, p.get("card", ""), bool(p.get("accepted")), p.get("reason")))

        ents = []
        for e in fr.get("entities", []):
            if e.get("x") is None or e.get("y") is None:
                continue
            kind = int(e.get("kind", 15))
            raw_name = e.get("name")
            is_tower = raw_name is None or int(e.get("card_id", 0)) == -1  # crown towers are the unnamed bodies
            d = dict(e)
            d["_tower"] = is_tower
            d["_building"] = kind in KIND_BUILDING and not is_tower
            d["_deploying"] = kind in KIND_DEPLOYING and not is_tower
            d["_px"] = board_px(float(e["x"]), float(e["y"]), self.mirror)
            d["_col"] = team_col(int(e.get("side", 0)), self.me)
            d["_r"] = body_radius(e, is_tower, d["_building"])
            d["_name"] = "" if is_tower else self.cards.display(raw_name)
            ents.append(d)
        by_id = {d["id"]: d for d in ents if d.get("id")}
        proj_ids = {q.get("id") for q in fr.get("projectiles", [])}

        if self.radii:
            self._rings(board, ents)
        if self.aggro:
            self._aggro_lines(board, ents, by_id)
        self._effects(board, fr, proj_ids)
        self._bodies(board, ents)
        self._projectiles(board, fr)
        self._flash(board)
        # a tower's 7-tile ring reaches past the arena edge; keep the rings inside it, the HUD clean
        img = np.full((H, W, 3), PALETTE["bg"], np.uint8)
        img[BOARD_TOP - 2:BOARD_BOT + 2, BOARD_X0 - 2:BOARD_X0 + BOARD_W + 2] =             board[BOARD_TOP - 2:BOARD_BOT + 2, BOARD_X0 - 2:BOARD_X0 + BOARD_W + 2]
        self._hud(img, fr, clock, crowns)
        return img


def crowns_of(fr: dict, me: int):
    """Crowns from the tower list: a destroyed enemy tower is a crown for the other side."""
    tws = (fr.get("episode") or {}).get("crown_towers") or []
    if not tws:
        return None
    mine = sum(1 for t in tws if int(t.get("side", -1)) != me and (t.get("destroyed") or (t.get("hp") or 0) <= 0))
    theirs = sum(1 for t in tws if int(t.get("side", -1)) == me and (t.get("destroyed") or (t.get("hp") or 0) <= 0))
    return mine, theirs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("frames", type=Path, help="frames_<tag>_m<N>.json from engine_play --record-every")
    ap.add_argument("-o", "--out", type=Path, default=None)
    ap.add_argument("--speed", type=int, default=1, help="keep every Nth frame (3 = 3x faster)")
    ap.add_argument("--fps", type=int, default=0, help="override output fps (default: the recording's own rate)")
    ap.add_argument("--label", default="", help="HUD line, e.g. the checkpoint and its top-1")
    ap.add_argument("--hold", type=float, default=2.0, help="seconds to hold the final frame")
    ap.add_argument("--no-radii", action="store_true", help="drop the attack / aggro rings")
    ap.add_argument("--no-aggro", action="store_true", help="drop the attacker -> target lines")
    ap.add_argument("--stats", type=Path, default=REPO / "icebow" / "config" / "cards_stats.json",
                    help="wiki stat table (range_tiles, display names); the pair decks hold identical copies")
    ap.add_argument("--catalog", type=Path,
                    default=REPO / "research" / "ext" / "cr-native-sandbox" / "native_core" / "data" / "live_card_catalog.json")
    a = ap.parse_args()

    d = json.loads(a.frames.read_text(encoding="utf-8"))
    frames = d["frames"]
    if not frames:
        print("no frames in %s -- was --record-every set?" % a.frames, file=sys.stderr)
        return 2
    if not any("kind" in e for fr in frames[:20] for e in fr.get("entities", [])):
        print("note: frames carry no entity kind / target / projectiles (recorded before vis_raw) -- "
              "rings and names still draw, aggro lines and projectiles cannot", file=sys.stderr)
    me = int(d.get("side", 1))
    # Side 1 sits at HIGH engine y (its king tower is at y=29000, side 0's at y=3000), and this
    # renderer puts low y at the bottom -- so side 1 is the one that needs flipping.
    mirror = me == 1
    tick_s = 0.05
    fps = a.fps or max(1, min(30, int(round(1.0 / (d.get("record_every", 2) * tick_s)))))
    out = a.out or a.frames.with_suffix(".mp4")
    label = a.label or "%s  %s" % (d.get("tag", ""), d.get("outcome", ""))
    cards = Cards(a.stats, a.catalog)
    rend = Renderer(cards, me, mirror, label, radii=not a.no_radii, aggro=not a.no_aggro)

    tmp = out.with_suffix(".raw.mp4")
    vw = cv2.VideoWriter(str(tmp), cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    if not vw.isOpened():
        print("cv2 could not open a writer for %s" % tmp, file=sys.stderr)
        return 3
    kept = 0
    last = None
    for i, fr in enumerate(frames):
        # decision frames carry the play / gate: a skipped one still updates the gate, a play is never skipped
        if i % max(1, a.speed):
            if "p_gate" in fr:
                rend.p_gate = float(fr["p_gate"])
            if "play" not in fr:
                continue
        clock = float(fr.get("tick", 0)) * tick_s
        last = rend.draw(fr, clock, crowns_of(fr, me))
        vw.write(last)
        kept += 1
    for _ in range(int(a.hold * fps)):     # hold the final board so the result is readable
        if last is not None:
            vw.write(last)
    vw.release()

    # mp4v plays nowhere reliably; H.264 + faststart is what Instagram and phones want.
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                        str(out)], check=True)
        tmp.unlink()
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print("ffmpeg re-encode skipped (%s); raw file left at %s" % (type(e).__name__, tmp), file=sys.stderr)
        out = tmp
    print(json.dumps({"out": str(out), "frames": kept, "fps": fps,
                      "seconds": round(kept / fps + a.hold, 1), "tag": d.get("tag"),
                      "outcome": d.get("outcome"), "crowns": [d.get("crowns_for"), d.get("crowns_against")]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
