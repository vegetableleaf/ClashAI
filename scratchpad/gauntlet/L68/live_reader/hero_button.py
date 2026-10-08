"""Hero ability button for live_play.py (MuMu): sensor + actuator + receipt, policy as a pluggable rule.

The generalist has no ability action (neither S1 nor GenModel was trained with one), so -- like play.py (L67ag) --
the press is decided OUTSIDE the model: ``should_press`` is the one hook an RL ability head would replace.
Availability is read from the button's own pixels with play.py's measured classifier
(icebow/src/clashrl/hero_ability.ability_button_state: blue disc = ready, grey = unaffordable, neither = absent),
because the memory reader's verified contract has NO ability availability / cooldown fields.

Calibration: the button centre (0.909, 0.765) of the game frame was MEASURED on Google Play Games (run17, Hough
circle; config.yaml hero.button). MuMu shows the same 9:16 game full-screen, so it maps to (818, 1224) on 900x1600 --
PROVISIONAL until a hero match: while a hero is decked, the first 'ready' and first 'grey' button crops of each
match are saved to ability_crops/ so the position and thresholds can be checked, and every classification is logged.
Screenshots are `adb exec-out screencap` (raw RGBA) on a background thread, only while the deck holds a hero.
"""
from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / "icebow" / "src"))
if str(HERE.parents[3]) not in sys.path:
    sys.path.insert(0, str(HERE.parents[3]))             # pipeline.* (reader aliases, catalog names)
from clashrl.hero_ability import ability_button_state  # noqa: E402

BUTTON = (0.909, 0.765)            # frame fractions, GPG-measured (config.yaml hero.button)
STATE_RADIUS, BLUE_MIN, GREY_MIN = 0.045, 0.30, 0.35
HERO_FORM = 2                      # reader deck_form_flags: 0 base / 1 evo / 2 hero


def parse_raw_screencap(data: bytes) -> np.ndarray | None:
    """`screencap` raw output -> BGR image. Header = w, h, format (+ colour space on newer Android): its length is
    whatever precedes the w*h*4 RGBA pixels."""
    if len(data) < 12:
        return None
    w, h = int.from_bytes(data[0:4], "little"), int.from_bytes(data[4:8], "little")
    head = len(data) - w * h * 4
    if w <= 0 or h <= 0 or head not in (12, 16):
        return None
    rgba = np.frombuffer(data, np.uint8, offset=head).reshape(h, w, 4)
    return cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)


def hero_ids(me: dict) -> set[int]:
    """Card ids my deck holds in HERO form (empty = no hero decked)."""
    return {int(c) for c, f in zip(me.get("deck_card_ids") or [], me.get("deck_form_flags") or []) if int(f) == HERO_FORM}


ICE_WIZARD = 26000023
# Owner rule 2026-10-04 (interim, HAND-WRITTEN until pro Frosty Fella data can be crawled -- RoyaleAPI now sits behind a
# Cloudflare human check): freeze CLUMPS of troops, or stop an enemy WIN CONDITION reaching the tower when the Tesla is
# not in hand or not affordable. Frosty Fella spawns its snowman behind the Ice Wizard's current target and freezes
# every enemy within 2.5 tiles, so the freeze centre ~ that target ~ the nearest enemy inside his 5.5-tile range.
IW_RANGE, FREEZE_R, CLUMP_MIN, TESLA_COST = 5.5, 2.5, 3, 4.0
# owner 2026-10-06 (interim, until the pro Frosty Fella model): a clump must be WORTH the 2-elixir ability -- >= 2 enemy
# troops in the freeze zone totalling >= CLUMP_VALUE_MIN elixir (card cost / units it spawns, unit_values.json; unknown
# or spawned units 0.5). Live 10-05/06: 73 of 145 clump presses were exactly 3 bodies, 37 on Skeletons / Skeleton Army /
# Minions / Goblin Gang.
CLUMP_BODIES_MIN, CLUMP_VALUE_MIN, UNKNOWN_UNIT_VALUE = 2, 4.0, 0.5
_UNIT_VALUES = None


def unit_values() -> dict:
    global _UNIT_VALUES
    if _UNIT_VALUES is None:
        import json
        _UNIT_VALUES = json.loads((HERE / "unit_values.json").read_text(encoding="utf-8"))["value_per_unit"]
    return _UNIT_VALUES
WINCONS = {"HogRider", "SuperHogRider", "Giant", "GoblinGiant", "Golem", "RoyalGiant", "ElectroGiant", "Balloon",
           "LavaHound", "RamRider", "BattleRam", "Miner", "RoyalHogs", "Wallbreakers", "ElixirGolem", "GiantSkeleton",
           "SkeletonBalloon", "Pekka", "MegaKnight"}
BUILDINGS = {"Cannon", "Tesla", "InfernoTower", "BombTower", "Mortar", "Xbow", "Tombstone", "GoblinHut", "Furnace",
             "FirespiritHut", "BarbarianHut", "Elixir Collector", "GoblinCage", "GoblinDrill", "GoblinPartyHut"}


def hero_form_ids(card_ids: set[int]) -> set[int]:
    """Board ids of hero-form troops: reader v2 reports a hero unit as 203000000 + the base card number (hero Ice
    Wizard 26000023 -> 203000023, measured in L70/reader/sidebyside frames 2026-10-04). Before this, live never found
    the hero (every 10-03 press logged hero_unseen) and the fallback pressed on ANY enemy on my half."""
    return {203000000 + c % 1000000 for c in card_ids if 26000000 <= c < 27000000}


def _names() -> dict:
    from pipeline.obs_contract import _catalog_names   # lazy: live_play has the repo root on sys.path
    return _catalog_names()


def ice_wizard_should_press(f: dict, side: int, hero: dict | None, names: dict | None = None) -> tuple[bool, str]:
    names = names if names is not None else _names()
    if hero is None:
        return False, "iw_unseen"
    nm = lambda e: names.get(int(e["card_id"]), "")  # noqa: E731
    d = lambda a, b: ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2) ** 0.5 / 1000  # noqa: E731
    foes = [e for e in f["entities"] if e["side"] != side and int(e["card_id"]) >= 0]
    in_range = [e for e in foes if d(e, hero) <= IW_RANGE]
    if not in_range:
        return False, "iw_no_target"
    target = min(in_range, key=lambda e: d(e, hero))
    frozen = [e for e in foes if d(e, target) <= FREEZE_R and nm(e) not in BUILDINGS]
    vals = unit_values()
    value = sum(vals.get(nm(e), UNKNOWN_UNIT_VALUE) for e in frozen)
    if len(frozen) >= CLUMP_BODIES_MIN and value >= CLUMP_VALUE_MIN:
        return True, f"iw_clump n={len(frozen)} value={value:.1f} target={nm(target)}"
    me = next(p for p in f["players"] if p["side"] == side)
    hand = [names.get(int(me["deck_card_ids"][i]), "") for i in me["hand_deck_indices"] if i >= 0]
    elixir = me["elixir_raw"] / 1e4
    tesla_ok = "Tesla" in hand and elixir >= TESLA_COST
    for e in frozen:
        if nm(e) in WINCONS and (e["y"] > 16000) == (side == 1):   # a win condition on my half, inside the freeze
            if tesla_ok:
                return False, f"iw_wincon {nm(e)} but tesla ready"
            return True, f"iw_wincon {nm(e)} tesla_in_hand={'Tesla' in hand} elixir={elixir:.1f}"
    return False, f"iw_hold frozen={len(frozen)}"


def should_press(f: dict, side: int, hero_card_ids: set[int], reach_tiles: float = 5.5, pilot=None,
                 p_star: float | None = None) -> tuple[bool, str]:
    """PLACEHOLDER policy (the RL ability head's slot): press when an enemy troop is within ``reach_tiles`` of my hero
    (reader positions, 1000 units per tile); if the hero entity cannot be found, when an enemy troop is on my half.
    Deliberately generic -- no per-hero stats -- so it only guarantees the button is USED, not used well.
    Hero Ice Wizard uses ``ice_wizard_should_press`` (owner's interim rule) instead."""
    from pipeline.reader_identity_aliases import dedupe_hero_bodies
    f = dedupe_hero_bodies(f)                  # 2026-10-06: a hero + its FloatingCube share 203000023
    ids = hero_card_ids | hero_form_ids(hero_card_ids)
    if ICE_WIZARD in hero_card_ids:
        ok, why = ice_wizard_should_press(f, side, next((e for e in f["entities"] if e["side"] == side
                                                         and int(e["card_id"]) in ids), None))
        pub = getattr(pilot, "public", None) if pilot is not None else None
        if pub is None:
            return ok, why
        # lead 2026-10-06: PRO TIMING GATE (L70/abilities/ice_wizard_hero: 1,320 pro deployments, hold-out AUC .82) --
        # press only when pros would (hazard >= P*(V=4)) AND the freeze check above passes. Off: --no-iw-pro-gate.
        dep = [int(e["tick"]) for e in pub.own_events if e.get("card") == "ice-wizard" and not e.get("ability")
               and e.get("accepted", True)]
        if not dep:
            return ok, why + " (pro gate: no deploy tick)"
        from ability_ice_wizard import should_press_pro
        ok2, why2 = should_press_pro(pilot, f, side, dep[-1], geometry_ok=ok, v_min=CLUMP_VALUE_MIN, p_star=p_star)
        return ok2, why + " | " + why2
    hero = next((e for e in f["entities"] if e["side"] == side and int(e["card_id"]) in ids), None)
    foes = [e for e in f["entities"] if e["side"] != side and int(e["card_id"]) >= 0]
    if hero is not None:
        d = min((((e["x"] - hero["x"]) ** 2 + (e["y"] - hero["y"]) ** 2) ** 0.5 / 1000 for e in foes), default=99.0)
        return d <= reach_tiles, f"nearest_enemy_to_hero={d:.1f}t"
    mine_half = [e for e in foes if (e["y"] > 16000) == (side == 1)]
    return bool(mine_half), f"hero_unseen enemies_on_my_half={len(mine_half)}"


class HeroButton:
    def __init__(self, adb: list[str], w: int, h: int, crops_dir: Path, period_s: float = 0.5, on_frame=None):
        self.adb, self.w, self.h, self.period = adb, w, h, period_s
        self.on_frame = on_frame                # e.g. friend_nav.MenuGuard.feed: one screencap serves both
        self.point = (round(BUTTON[0] * w), round(BUTTON[1] * h))
        self.crops = crops_dir
        self.want = False                       # set by the controller: a hero is decked this match
        self.state, self.blue, self.grey, self.ts = "absent", 0.0, 0.0, 0.0
        self.saved: set[str] = set()
        self._stop = False
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        while not self._stop:
            if not self.want:
                time.sleep(0.2)
                continue
            t0 = time.time()
            try:
                raw = subprocess.run(self.adb + ["exec-out", "screencap"], capture_output=True, timeout=5).stdout
                img = parse_raw_screencap(raw)
            except Exception:                   # noqa: BLE001 -- a missed grab is a missed reading, not a crash
                img = None
            if img is not None and self.on_frame:
                try:
                    self.on_frame(img, t0)
                except Exception:               # noqa: BLE001 -- a guard error must not kill the button thread
                    pass                        # (the guard then records no success and blocks taps: fails closed)
            if img is not None:
                st, b, g = ability_button_state(img, BUTTON, STATE_RADIUS, BLUE_MIN, GREY_MIN)
                self.state, self.blue, self.grey, self.ts = st, b, g, time.time()
                if st in ("ready", "grey") and st not in self.saved:     # calibration evidence, once per state
                    self.crops.mkdir(parents=True, exist_ok=True)
                    x, y, r = self.point[0], self.point[1], int(0.08 * self.w)
                    cv2.imwrite(str(self.crops / f"{time.strftime('%Y%m%d_%H%M%S')}_{st}.png"),
                                img[max(0, y - r):y + r, max(0, x - r):x + r])
                    self.saved.add(st)
            time.sleep(max(0.0, self.period - (time.time() - t0)))

    def fresh_state(self, max_age_s: float = 1.0) -> str:
        return self.state if time.time() - self.ts <= max_age_s else "stale"

    def tap(self) -> None:
        subprocess.run(self.adb + ["shell", f"input tap {self.point[0]} {self.point[1]}"], capture_output=True,
                       timeout=5)

    def new_match(self) -> None:
        self.saved.clear()

    def stop(self) -> None:
        self._stop = True


if __name__ == "__main__":          # self-check: raw parse + placeholder policy (no device needed)
    img = np.zeros((1600, 900, 4), np.uint8)
    img[..., 2] = 255                                   # pure blue in RGBA
    for head in (12, 16):
        raw = (900).to_bytes(4, "little") + (1600).to_bytes(4, "little") + bytes(head - 8) + img.tobytes()
        bgr = parse_raw_screencap(raw)
        assert bgr.shape == (1600, 900, 3) and bgr[0, 0].tolist() == [255, 0, 0]
    assert ability_button_state(parse_raw_screencap(raw), BUTTON, STATE_RADIUS, BLUE_MIN, GREY_MIN)[0] == "ready"
    me = {"deck_card_ids": [26000000, 26000014], "deck_form_flags": [0, 2]}
    assert hero_ids(me) == {26000014}
    ent = lambda s, x, y, c: {"side": s, "x": x, "y": y, "card_id": c}  # noqa: E731
    f = {"entities": [ent(1, 9000, 24000, 26000014), ent(0, 9000, 20000, 26000000), ent(0, 9000, 3000, -1)]}
    assert should_press(f, 1, {26000014})[0] is True                  # enemy 4 tiles from my hero
    f["entities"][1]["y"] = 10000
    assert should_press(f, 1, {26000014})[0] is False                 # enemy 14 tiles away
    assert should_press({"entities": [ent(0, 9000, 20000, 1)]}, 1, {26000014})[0] is True   # hero unseen, foe on my half
    # Ice Wizard interim rule (names injected; no catalog needed): I am side 1 (my half y > 16000), IW at (9000, 24000)
    N = {1: "Skeletons", 2: "HogRider", 3: "Tesla", 4: "Knight", 5: "Cannon", 6: "Barbarians"}
    iw = ent(1, 9000, 24000, ICE_WIZARD)
    pl = lambda hand, el: [{"side": 1, "deck_card_ids": [3, 4, 4, 4], "hand_deck_indices": hand, "elixir_raw": el * 10000}]  # noqa: E731
    clump = {"entities": [iw] + [ent(0, 9000 + 300 * k, 21000, 1) for k in range(3)], "players": pl([1, 2, 3, -1], 9)}
    assert ice_wizard_should_press(clump, 1, iw, N)[0] is False                      # 3 skeletons = 1 elixir: not worth it
    barbs = {"entities": [iw] + [ent(0, 9000 + 300 * k, 21000, 6) for k in range(4)], "players": pl([1, 2, 3, -1], 9)}
    assert ice_wizard_should_press(barbs, 1, iw, N)[0] is True                       # 4 Barbarians = 4 elixir in the freeze
    hog = {"entities": [iw, ent(0, 9000, 21000, 2)], "players": pl([1, 2, 3, -1], 9)}  # hand has no Tesla (index 0)
    assert ice_wizard_should_press(hog, 1, iw, N)[0] is True                         # wincon, Tesla not in hand
    hog["players"] = pl([0, 1, 2, -1], 9)
    assert ice_wizard_should_press(hog, 1, iw, N)[0] is False                        # Tesla in hand + affordable
    hog["players"] = pl([0, 1, 2, -1], 3)
    assert ice_wizard_should_press(hog, 1, iw, N)[0] is True                         # Tesla in hand, 3 elixir
    lone = {"entities": [iw, ent(0, 9000, 21000, 4)], "players": pl([1, 2, 3, -1], 9)}
    assert ice_wizard_should_press(lone, 1, iw, N)[0] is False                       # one Knight: hold
    far = {"entities": [iw] + [ent(0, 9000 + 300 * k, 12000, 1) for k in range(3)], "players": pl([1, 2, 3, -1], 9)}
    assert ice_wizard_should_press(far, 1, iw, N)[0] is False                        # clump out of range
    bld = {"entities": [iw, ent(0, 9000, 21000, 5), ent(0, 9300, 21000, 5), ent(0, 9600, 21000, 4)],
           "players": pl([1, 2, 3, -1], 9)}
    assert ice_wizard_should_press(bld, 1, iw, N)[0] is False                        # buildings are not a troop clump
    assert hero_form_ids({ICE_WIZARD}) == {203000023}
    assert should_press({"entities": [ent(1, 9000, 24000, 203000014), ent(0, 9000, 10000, 26000000)]}, 1,
                        {26000014})[0] is False                               # hero found by its FORM id: no fallback
    print("hero_button self-check OK; MuMu button point", (round(BUTTON[0] * 900), round(BUTTON[1] * 1600)))
