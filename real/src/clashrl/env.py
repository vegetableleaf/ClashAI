"""Live 2v2 match environment for RL fine-tuning.

Wraps the same capture / vision / controller stack the policy plays on into a
minimal RL loop:

* `reset()` drives the scripted menu navigation (HOME -> party -> quick match)
  until a match starts, then returns the first observation.
* `step(action)` plays a card (or waits), advances one action period, and returns
  `(obs, reward, done, info)`. Reward = per-step tower shaping while in a match;
  on match end it resolves the **win/loss terminal reward** off the results
  scoreboard and drives the exit tap.

Actions are `(play, slot, cell)` where `play=0` is a deliberate no-op (wait /
save elixir) and `play=1` places hand `slot` at grid `cell` (decoded exactly like
the labeler/`play`).
"""
from __future__ import annotations

import time
from typing import Optional, Tuple

import numpy as np

from .actions import ActionSpace
from .capture import WindowCapture
from .controller import Controller
from .outcome import outcome_reward, read_scoreboard
from .reward import (TowerTracker, defensive_cell, enemy_mass, enemy_mass_at,
                     near_enemy_king, near_enemy_princess, near_my_king, threat_front,
                     threat_side, troop_size_at, weaker_princess_cell)
from .states import GameState
from .tower_hp import TowerHpTracker
from .vision import Vision

Action = Tuple[int, int, int]  # (play 0/1, card_id, cell)


class LiveMatchEnv:
    def __init__(self, cfg):
        self.cfg = cfg
        self.capture = WindowCapture(cfg.get("window", "title_contains", default=None),
                                     cfg.get("window", "region", default=None))
        self.vision = Vision(cfg)
        self.actions = ActionSpace(cfg)
        self.controller = Controller(self.capture, cfg)
        self.tower = TowerTracker(cfg)
        self.tower_hp = TowerHpTracker(cfg)
        self.gw, self.gh = int(self.actions.gw), int(self.actions.gh)
        self.n_slots, self.n_cells = self.actions.n_slots, self.actions.n_cells

        self.act_period = float(cfg.get("play", "act_period", default=1.5))
        self.poll_dt = 1.0 / float(cfg.get("nav", "poll_hz", default=6))
        self.menu_delay = float(cfg.get("nav", "menu_delay", default=1.0))
        self.results_timeout = float(cfg.get("env", "results_timeout", default=30.0))

        self.battle = cfg.get("buttons", "battle_button", default=[0.5, 0.9])
        self.quick = cfg.get("buttons", "quick_match", default=[0.5, 0.55])
        self.results_ok = cfg.get("buttons", "results_ok", default=[0.5, 0.9])
        self.results_dc = cfg.get("buttons", "results_ok_dc", default=self.results_ok)
        _home = cfg.get("states", "home_menu", default={}) or {}
        self._home_tpl = _home.get("template", "home_menu.png")
        self._home_thr = float(_home.get("threshold", 0.8))

        ow, oh = cfg.get("observation", "arena_size", default=[64, 96])
        self.obs_shape = (int(oh), int(ow), 3)
        self._last_obs = np.zeros(self.obs_shape, dtype=np.uint8)
        self.last_outcome: Optional[str] = None
        self.elixir = 0                 # your current elixir (0-10), updated each step
        self.elixir_vec = np.zeros(1, np.float32)   # normalized elixir [0,1] -> policy input
        self.n_cards = max(1, len(self.vision.deck_keys))
        self.hand_ids = [-1] * self.n_slots            # deck index in each tray slot
        self.hand_vec = np.zeros(self.n_cards, np.float32)   # multi-hot of cards in hand
        self.next_id = -1                              # deck index of the next (preview) card
        self.next_vec = np.zeros(self.n_cards, np.float32)   # one-hot of the next card
        self._last_frame = None                        # last full BGR frame (spell before/after)

        # spell-effect + patience rewards
        from .cards import CardDB
        db = CardDB(cfg)
        self.spell_ids = set()
        self.rocket_ids = set()
        self.tornado_ids = set()
        self.royal_delivery_ids = set()
        self.cheap_ids = set()
        self.tesla_ids = set()
        self.ranged_ids = set()
        self.blocker_ids = set()
        self.defensive_kind = {}
        for i, key in enumerate(self.vision.deck_keys):
            base = key[:-4] if key.endswith("_evo") else key
            c = db.get(base)
            if c and c.get("kind") == "spell":
                self.spell_ids.add(i)
            if base == "rocket":
                self.rocket_ids.add(i)
            elif base == "tornado":
                self.tornado_ids.add(i)
            elif base == "royal_delivery":          # defensive area spell on your half
                self.royal_delivery_ids.add(i)
            if base in ("ice_spirit", "skeletons"):  # cheap cyclers -- OK to play anytime
                self.cheap_ids.add(i)
            if base == "tesla":                      # Tesla: kill-reward tracked + range-aware placement
                self.tesla_ids.add(i)
                self.defensive_kind[i] = "tesla"
            elif base == "ice_wizard":
                self.defensive_kind[i] = "ice_wizard"
            elif base == "ronin":                    # melee mini-tank -> placed to block the push
                self.defensive_kind[i] = "ronin"
            elif key == "musketeer":
                self.defensive_kind[i] = "musketeer"
            elif key == "musketeer_evo":
                self.defensive_kind[i] = "musketeer_evo"
            if base in ("tesla", "musketeer", "ice_wizard"):
                self.ranged_ids.add(i)               # ranged units worth shielding
            elif base in ("ronin", "skeletons", "ice_spirit"):
                self.blocker_ids.add(i)              # tanks/blockers that shield them
        # only ROCKET and TORNADO may be cast ANYWHERE; every other card (troops, buildings,
        # royal delivery) is restricted to YOUR half of the map.
        self.anywhere_ids = self.rocket_ids | self.tornado_ids
        self.spell_troop_damage = float(cfg.get("rewards", "spell_troop_damage", default=5.0))
        self.spell_hit = float(cfg.get("rewards", "spell_hit", default=0.15))
        self.spell_combo = float(cfg.get("rewards", "spell_combo", default=0.6))
        self.spell_whiff = float(cfg.get("rewards", "spell_whiff", default=-0.5))
        self.spell_king_penalty = float(cfg.get("rewards", "spell_king_penalty", default=-1.5))
        self.tesla_kill = float(cfg.get("rewards", "tesla_kill", default=3.0))
        self.patience = float(cfg.get("rewards", "patience", default=0.02))
        self.troop_defeat = float(cfg.get("rewards", "troop_defeat", default=3.0))
        self.clean_kill_bonus = float(cfg.get("rewards", "clean_kill_bonus", default=2.0))
        self.spell_effect = bool(cfg.get("env", "spell_effect_reward", default=True))
        self.spell_radius = float(cfg.get("env", "spell_radius", default=0.12))
        self.spell_min_drop = float(cfg.get("env", "spell_min_drop", default=0.03))
        self.spell_present = float(cfg.get("env", "spell_present", default=0.04))
        self.spell_combo_present = float(cfg.get("env", "spell_combo_present", default=0.18))
        self.spell_size_cap = float(cfg.get("env", "spell_size_cap", default=0.20))
        self.spell_eval_time = float(cfg.get("env", "spell_eval_time", default=2.4))
        self.spell_aim_radius = float(cfg.get("env", "spell_tower_aim_radius", default=0.12))
        # rocket travel time scales ~linearly with distance from its launch point;
        # predict the impact moment per cast instead of a fixed wait.
        self.rocket_origin = cfg.get("env", "rocket_origin", default=[0.5, 1.05])
        self.rocket_base_time = float(cfg.get("env", "rocket_base_time", default=0.3))
        self.rocket_travel_rate = float(cfg.get("env", "rocket_travel_rate", default=2.2))
        self.tornado_time = float(cfg.get("env", "tornado_time", default=1.2))
        # defensive placement: ranged units go toward CENTRE (horizontal gap counts) a
        # reduced depth behind the enemy front; Evo Musketeer to the very back.
        self.musketeer_evo_center = cfg.get("env", "musketeer_evo_center", default=[0.48, 0.82])
        self.threat_min_frac = float(cfg.get("env", "defense_threat_frac", default=0.02))
        _rmap = cfg.get("env", "range_offsets", default={"long": 0.15, "short": 0.12, "melee": 0.05})
        _roff = {k: float(_rmap.get(db.attack_range(k) or "long", 0.13))
                 for k in ("tesla", "ice_wizard", "musketeer", "ronin")}
        self.defense_params = {
            "musketeer_evo": self.musketeer_evo_center, "range_offsets": _roff,
            "a_bot": self.actions.a_bot,
            "center_bias": float(cfg.get("env", "defense_center_bias", default=0.10)),
            "center_depth_frac": float(cfg.get("env", "defense_center_depth_frac", default=0.6)),
        }
        # king HP boxes (only shown once a king is hit): enemy -> spell penalty; mine -> tank reward
        self._king_box = cfg.get("env", "enemy_king_hp_box", default=[0.41, 0.015, 0.55, 0.08])
        self.king_hp_margin = float(cfg.get("env", "king_hp_margin", default=40.0))
        self._my_king_box = cfg.get("env", "my_king_hp_box", default=[0.41, 0.69, 0.55, 0.77])
        self.my_king_full = float(cfg.get("env", "my_king_full", default=4824.0))
        self.king_tank_reward = float(cfg.get("rewards", "king_tank_reward", default=1.0))
        self.blocker_protect = float(cfg.get("rewards", "blocker_protect", default=1.0))
        self.blocker_window = int(cfg.get("env", "blocker_combo_steps", default=3))
        self.blocker_threat_size = float(cfg.get("env", "blocker_threat_size", default=0.08))
        # Royal Delivery: a delayed (~3s) area spell on YOUR half -> reward troops HIT + KILLED.
        self.royal_delivery_time = float(cfg.get("env", "royal_delivery_time", default=3.0))
        self.rd_hit = float(cfg.get("rewards", "royal_delivery_hit", default=3.0))
        self.rd_kill = float(cfg.get("rewards", "royal_delivery_kill", default=5.0))
        # play defensively: penalise a non-rocket, non-cycle card placed in the ENEMY half.
        self.offensive_penalty = float(cfg.get("rewards", "offensive_penalty", default=-0.5))
        self.offensive_half = float(cfg.get("env", "offensive_half_y", default=0.45))
        self.rocket_tower_reward = float(cfg.get("rewards", "rocket_tower_reward", default=1.0))
        self.cycle_reward = float(cfg.get("rewards", "cycle_reward", default=0.15))
        # rocket -> tornado combo: a tornado at the SAME spot right after a rocket that killed a
        # clumped group. Waives the enemy-king penalty (when the rocket hit a princess tower and
        # killed >=2 medium troops) and rewards wiping a push, anywhere on the board.
        self.combo_reward = float(cfg.get("rewards", "rocket_tornado_combo", default=15.0))
        self.combo_window = int(cfg.get("env", "combo_window_steps", default=2))
        self.combo_radius = float(cfg.get("env", "combo_radius", default=0.10))
        self.combo_kill_min = float(cfg.get("env", "combo_kill_min", default=0.06))
        self._recent_rocket = None
        self._recent_ranged = None
        self._steps = 0
        self.quiet_frac = float(cfg.get("env", "enemy_quiet_frac", default=0.02))
        self.idle_penalty = float(cfg.get("rewards", "idle_penalty", default=-0.3))
        self.threat_mass = float(cfg.get("env", "threat_mass", default=0.10))
        self.elixir_waste_penalty = float(cfg.get("rewards", "elixir_waste_penalty", default=-0.3))
        self.full_elixir = int(cfg.get("env", "elixir_full", default=10))
        self.defeat_min = float(cfg.get("env", "defeat_min", default=0.005))
        self.defeat_cap = float(cfg.get("env", "defeat_cap", default=0.15))
        self.tesla_track_steps = int(cfg.get("env", "tesla_track_steps", default=10))
        self.tesla_radius = float(cfg.get("env", "tesla_radius", default=0.16))
        self._prev_mass = 0.0
        self._prev_my_hp = 0.0
        self._tesla = None

    # -- capture helper ------------------------------------------------
    def _grab(self, retries: int = 20):
        for _ in range(retries):
            frame = self.capture.grab()
            if frame is not None:
                return frame
            self.capture.refresh_region()
            time.sleep(0.3)
        return None

    def region_ready(self) -> bool:
        return self.capture.region is not None

    def _read_hand(self, frame) -> None:
        """Recognize the hand -> deck ids per slot + multi-hot (for identity actions),
        and the next (preview) card -> one-hot (so the policy can plan cycles)."""
        self.hand_ids = self.vision.recognize_hand(frame)
        self.hand_vec = self.vision.hand_multihot(self.hand_ids)
        self.next_id = self.vision.recognize_next(frame)
        self.next_vec = self.vision.next_onehot(self.next_id)

    # -- episode lifecycle --------------------------------------------
    def reset(self) -> Optional[np.ndarray]:
        """Navigate menus until a match starts; return the first observation."""
        self.tower.reset()
        self.tower_hp.reset()
        self._tesla = None
        self._recent_ranged = None
        self._recent_rocket = None
        while True:
            frame = self._grab()
            if frame is None:
                return None
            state = self.vision.detect_state(frame)
            if state == GameState.IN_MATCH:
                self.elixir = self.vision.read_elixir(frame)
                self.elixir_vec = np.asarray([self.elixir / 10.0], dtype=np.float32)
                self._read_hand(frame)
                self._last_obs = self.vision.observe(frame)
                self._last_frame = frame
                self._prev_mass = enemy_mass(frame, self.cfg)
                self._prev_my_hp = float(sum(self.tower_hp.my_hp))
                return self._last_obs
            if state == GameState.HOME:
                # tap the Battle button where its template actually matched (robust to the
                # home layout shifting) -- fall back to the configured point if not located.
                # 1v1: the Battle button queues a match directly (no party/quick-match step).
                pt = self.vision.locate(frame, self._home_tpl, self._home_thr) or self.battle
                self.controller.tap(*pt)
                time.sleep(self.menu_delay)
            elif state == GameState.MATCH_END:
                self.controller.tap(*(self.results_dc if self.vision.match_end_is_dc(frame) else self.results_ok))
                time.sleep(self.menu_delay)
            else:  # UNKNOWN / QUEUING -> wait for a known screen
                time.sleep(self.poll_dt)

    def _execute(self, action: Action) -> None:
        play, card_id, cell = action
        if not play:
            return
        slot = next((s for s, c in enumerate(self.hand_ids) if c == card_id), -1)
        if slot < 0:                          # chosen card not in hand (unrecognized) -> skip
            return
        gx, gy = cell % self.gw, cell // self.gw
        self.controller.play_card(*self.actions.decode(slot, gx, gy))

    def _aim_rocket(self, card_id: int, cell: int) -> int:
        """A rocket aimed at an enemy princess is redirected to the lower-HP princess so
        it finishes off the weaker tower (more efficient). No-op for other cards, other
        targets, or while either princess is down / both are at equal HP."""
        if card_id not in self.rocket_ids:
            return cell
        gx, gy = cell % self.gw, cell // self.gw
        cx, cy = self.actions.cell_center(gx, gy)
        tgt = weaker_princess_cell(cx, cy, self.spell_aim_radius, self.tower.enemy_a,
                                   self.tower_hp.enemy_hp, self.tower.enemy_alive,
                                   self.gw, self.gh)
        return tgt if tgt is not None else cell

    def _place_defensive(self, card_id: int, cell: int) -> int:
        """Ranged defenders (Tesla / Ice Wizard / Musketeer) are placed a unit's attack reach
        BEHIND the enemy front on the threatened lane, so the push closes the gap under fire
        instead of landing on top of the unit; Evo Musketeer goes to the very back. Only
        overrides when there's a clear threat -- otherwise the model places it (so Tesla stays
        reward-shaped when there's nothing to defend)."""
        kind = self.defensive_kind.get(card_id)
        if kind is None or self._last_frame is None:
            return cell
        if kind == "musketeer_evo":
            return defensive_cell(kind, 0, 0.0, self.gw, self.gh, self.defense_params)
        side = threat_side(self._last_frame, self.cfg, self.threat_min_frac)
        if side == 0:
            return cell
        front = threat_front(self._last_frame, side, self.cfg, self.threat_min_frac)
        if front is None:
            return cell
        return defensive_cell(kind, side, front, self.gw, self.gh, self.defense_params)

    def _tesla_reward(self, frame, play: bool, card_id: int, cell: int) -> float:
        """Reward a placed Tesla by the enemy troops it kills near it over its life. A
        Tesla that survives and defends longer keeps killing (so keeps earning), which a
        central placement does best -- troops funnel to it where both towers help. A dead
        Tesla stops killing, so the reward naturally stops. Placement is the model's; this
        just shapes it (no forced spot). Tesla's blue placement tint doesn't pollute the
        red enemy-mass read."""
        r = 0.0
        if self._tesla is not None:
            tx, ty = self._tesla["cx"], self._tesla["cy"]
            cur = enemy_mass_at(frame, tx, ty, self.tesla_radius, self.cfg)
            drop = self._tesla["prev"] - cur
            if drop > self.defeat_min:
                r += min(drop, self.defeat_cap) * self.tesla_kill
            self._tesla["prev"] = cur
            self._tesla["steps"] -= 1
            if self._tesla["steps"] <= 0:
                self._tesla = None
        if play and card_id in self.tesla_ids:        # (re)start tracking a freshly placed Tesla
            gx, gy = cell % self.gw, cell // self.gw
            tx, ty = self.actions.cell_center(gx, gy)
            self._tesla = {"cx": tx, "cy": ty, "steps": self.tesla_track_steps,
                           "prev": enemy_mass_at(frame, tx, ty, self.tesla_radius, self.cfg)}
        return r

    def _my_king_hp_frac(self, frame) -> Optional[float]:
        """Your king's HP as a fraction of full (0..1), or None if it isn't active (no HP
        number shown). Used to reward a defensive tornado-to-your-king less as it wears down."""
        r = self.tower_hp.reader
        if frame is None or r is None or not getattr(r, "ok", False):
            return None
        from .tower_hp import _crop
        v, c = r.read(_crop(frame, self._my_king_box))
        if v is None or c < self.tower_hp.min_conf:
            return None
        return min(max(v / self.my_king_full, 0.0), 1.0)

    def _blocker_reward(self, frame, play: bool, card_id: int, cell: int) -> float:
        """Reward SHIELDING a ranged unit: a blocker (Ronin / Skeletons / Ice Spirit) played
        soon after a ranged unit (Musketeer / Ice Wizard / Tesla) while a BIG enemy troop (a
        Mega Knight / PEKKA-sized red blob) sits on that spot -- so the tank soaks the melee
        and the ranged unit survives, instead of the ranged unit dying alone. Coarse (no
        troop ID): a large single red blob stands in for a heavy melee threat."""
        r = 0.0
        self._steps += 1
        if play and card_id in self.ranged_ids:
            gx, gy = cell % self.gw, cell // self.gw
            cx, cy = self.actions.cell_center(gx, gy)
            self._recent_ranged = (self._steps, cx, cy)
        elif play and card_id in self.blocker_ids and self._recent_ranged is not None:
            st, rx, ry = self._recent_ranged
            if self._steps - st <= self.blocker_window:
                if troop_size_at(frame, rx, ry, self.spell_radius, self.cfg) >= self.blocker_threat_size:
                    r += self.blocker_protect
                    self._recent_ranged = None            # credit the combo once
        return r

    def step(self, action: Action):
        play, card_id, cell = action
        if play:                                  # rocket -> weaker princess; Tesla/Ice Wizard -> defence
            cell = self._aim_rocket(card_id, cell)
            cell = self._place_defensive(card_id, cell)
            cell = self.actions.deploy_clamp(card_id in self.anywhere_ids, cell)  # only rocket/tornado go anywhere
            action = (play, card_id, cell)
        eval_spell = bool(play) and card_id in self.spell_ids and self.spell_effect
        is_rocket = card_id in self.rocket_ids
        is_rd = card_id in self.royal_delivery_ids
        before = self._last_frame if eval_spell else None
        self._execute(action)
        spell_samples = []
        if eval_spell:
            # Predict the impact time (rocket travel ~ distance; tornado ~immediate) and
            # sample a short window around it, so troops are caught in the radius whatever
            # the target distance is.
            gx, gy = cell % self.gw, cell // self.gw
            cx, cy = self.actions.cell_center(gx, gy)
            it = self._impact_time(cx, cy, is_rocket, is_rd)
            prev = 0.0
            for off in (max(0.4, it - 0.7), it, it + 0.6):
                time.sleep(max(0.0, off - prev))
                prev = off
                f = self._grab()
                if f is not None:
                    spell_samples.append(f)
            frame = spell_samples[-1] if spell_samples else self._grab()
        else:
            time.sleep(self.act_period)
            frame = self._grab()
        if frame is None:
            return self._last_obs, 0.0, True, {"outcome": None, "error": "capture_lost"}

        state = self.vision.detect_state(frame)
        if state == GameState.IN_MATCH:
            reward = self.tower.step(frame) + self.tower_hp.step(frame)
            cur_mass = enemy_mass(frame, self.cfg)
            my_hp = float(sum(self.tower_hp.my_hp))
            cur_elixir = self.vision.read_elixir(frame)
            if eval_spell and before is not None and spell_samples:
                reward += self._spell_effect_reward(before, spell_samples, cell, is_rocket, is_rd)
            else:
                # general troop-defeat reward: enemy-troop mass removed since last step
                # (by any means), scaled by the amount; a clean kill (your towers took
                # no HP that step -- defeated before it could damage you) is worth more.
                drop = max(0.0, self._prev_mass - cur_mass)
                if drop > self.defeat_min:
                    clean = my_hp >= self._prev_my_hp
                    reward += min(drop, self.defeat_cap) * self.troop_defeat * (
                        self.clean_kill_bonus if clean else 1.0)
                if not play:
                    if cur_mass < self.quiet_frac:
                        reward += self.patience          # holding cards while the board is quiet is fine
                    elif cur_mass >= self.threat_mass:
                        reward += self.idle_penalty      # a real push is on the board and you did nothing -> defend
                        if cur_elixir >= self.full_elixir:
                            reward += self.elixir_waste_penalty  # full bar + a push, still nothing = wasted elixir
            reward += self._tesla_reward(frame, bool(play), card_id, cell)
            reward += self._blocker_reward(frame, bool(play), card_id, cell)
            if play and card_id not in self.rocket_ids and card_id not in self.cheap_ids:
                if self.actions.cell_center(cell % self.gw, cell // self.gw)[1] < self.offensive_half:
                    reward += self.offensive_penalty  # non-rocket card played in the enemy half = offence
            if play and card_id in self.cheap_ids and not any(c in self.rocket_ids for c in self.hand_ids):
                reward += self.cycle_reward           # cheap card played while rocket isn't in hand -> cycling to it
            self._prev_mass = cur_mass
            self._prev_my_hp = my_hp
            self.elixir = cur_elixir
            self.elixir_vec = np.asarray([cur_elixir / 10.0], dtype=np.float32)
            self._read_hand(frame)
            self._last_obs = self.vision.observe(frame)
            self._last_frame = frame
            return self._last_obs, reward, False, {"elixir": self.elixir}

        # match is over -> resolve win/loss terminal reward, then exit
        reward, outcome, detail = self._resolve_terminal()
        self.last_outcome = outcome
        return self._last_obs, reward, True, {"outcome": outcome, **detail}

    def _impact_time(self, cx: float, cy: float, is_rocket: bool, is_rd: bool = False) -> float:
        """Seconds from cast to effect. A rocket's flight time grows ~linearly with the
        distance from its launch point to the target; a tornado activates almost immediately;
        Royal Delivery lands after a long fixed delay."""
        if is_rd:
            return self.royal_delivery_time
        if not is_rocket:
            return self.tornado_time
        ox, oy = self.rocket_origin
        d = ((cx - ox) ** 2 + (cy - oy) ** 2) ** 0.5
        return min(max(self.rocket_base_time + self.rocket_travel_rate * d, 0.6), self.spell_eval_time)

    def _spell_hit_king(self, before, after) -> bool:
        """True if the enemy KING tower's HP number shows it took damage across the spell --
        the king only prints its HP once it's been hit. Reads the tower-HP digit model on
        enemy_king_hp_box; if that box isn't calibrated it just reads nothing (no false
        penalty), and the positional king check still covers it."""
        r = self.tower_hp.reader
        if before is None or after is None or r is None or not getattr(r, "ok", False):
            return False
        from .tower_hp import _crop
        ka, ca = r.read(_crop(after, self._king_box))
        if ka is None or ca < self.tower_hp.min_conf:
            return False                              # king shows no HP number -> undamaged
        kb, cb = r.read(_crop(before, self._king_box))
        if kb is None or cb < self.tower_hp.min_conf:
            return True                               # HP number appeared this spell -> newly hit
        return ka < kb - self.king_hp_margin          # HP dropped -> hit again

    def _spell_effect_reward(self, before, samples, cell, is_rocket: bool, is_rd: bool = False) -> float:
        """Reward a spell by what it does at the target, sampled over the impact window.

        Rocket -> Tornado COMBO: a tornado cast at the SAME spot right after a rocket that
        killed a clumped group is treated as one play -- it WAIVES the enemy-king penalty
        (when that rocket hit a princess tower and killed >=2 medium troops) and is rewarded
        for wiping the push, anywhere on the board (not just at a tower). NOTE: the env
        evaluates each spell in a blocking window through its flight, so it can't cast the
        tornado mid-rocket-flight; this rewards the rocket->tornado PATTERN + the troops the
        rocket killed (which teaches the sequence). Otherwise: enemy-king damage -> penalty;
        Royal Delivery -> mass hit + killed; a defensive tornado onto YOUR king (both your
        princesses up) -> tank reward; else the rocket size/kill/combo/whiff logic.
        """
        gx, gy = cell % self.gw, cell // self.gw
        cx, cy = self.actions.cell_center(gx, gy)
        b = enemy_mass_at(before, cx, cy, self.spell_radius, self.cfg)
        masses = [enemy_mass_at(f, cx, cy, self.spell_radius, self.cfg) for f in samples]
        if not masses:
            if is_rocket:
                self._recent_rocket = None
            return 0.0
        peak_i = int(np.argmax(masses))
        peak = masses[peak_i]
        drop = peak - masses[-1]
        present = peak >= self.spell_present

        # is this tornado the second half of a rocket->tornado combo (same spot, right after a
        # rocket that actually killed a clump)?
        is_tornado = not is_rocket and not is_rd
        combo = None
        if is_tornado and self._recent_rocket is not None:
            rk = self._recent_rocket
            near = ((cx - rk["cx"]) ** 2 + (cy - rk["cy"]) ** 2) ** 0.5 <= self.combo_radius
            if (self._steps - rk["step"]) <= self.combo_window and near and rk["kills"] >= self.combo_kill_min:
                combo = rk

        king_here = self._spell_hit_king(before, samples[-1]) or near_enemy_king(
            cx, cy, self.cfg, self.spell_aim_radius)
        if king_here and not (combo is not None and combo["hit_tower"]):
            return self.spell_king_penalty            # aimed at / damaged the enemy king -> waste
            #   (waived only for a valid rocket[hit tower + kills]->tornado combo)
        if is_rocket:                                 # remember this rocket for a following tornado
            self._recent_rocket = {
                "step": self._steps, "cx": cx, "cy": cy, "kills": max(0.0, drop),
                "hit_tower": near_enemy_princess(cx, cy, self.cfg, self.spell_aim_radius),
            }
        if combo is not None:                         # rocket->tornado wiped a clumped push
            self._recent_rocket = None                # credit the combo once
            killed = min(max(combo["kills"], drop), self.spell_size_cap * 2.0)
            return self.combo_reward * killed

        if is_rd:                                     # Royal Delivery: reward the GROUP it hits + kills
            cap = self.spell_size_cap * 2.0
            return min(peak, cap) * self.rd_hit + min(max(0.0, drop), cap) * self.rd_kill
        if (is_tornado and near_my_king(cx, cy, self.cfg, self.spell_aim_radius)
                and all(self.tower.mine_alive[:2])):
            frac = self._my_king_hp_frac(samples[-1])
            if frac is not None:                      # tornado onto YOUR king (princesses up): tank it,
                return self.king_tank_reward * frac   # worth less as the king's own HP falls
        if near_enemy_princess(cx, cy, self.cfg, self.spell_aim_radius):
            if is_rocket:
                r = self.rocket_tower_reward              # launching a rocket at the enemy princess tower
                if drop >= self.spell_min_drop or peak >= self.spell_combo_present:
                    r += self.spell_combo                 # ...that also caught troops
                return r
            return 0.0                                    # chip -> tower_hp handles it
        # scale by the size of the biggest unit caught (swarm -> small, fat unit -> large)
        size = min(troop_size_at(samples[peak_i], cx, cy, self.spell_radius, self.cfg),
                   self.spell_size_cap)
        if is_rocket and drop >= self.spell_min_drop:
            return size * self.spell_troop_damage         # killed a unit -> reward by its size
        if present:
            return size * self.spell_hit                  # unit caught but survived -> by its size
        if b < self.spell_present:
            return self.spell_whiff                       # cast on empty ground / king
        return 0.0                                        # aimed at troops that moved away

    def _resolve_terminal(self) -> Tuple[float, Optional[str], dict]:
        """Read the result: end-of-match scoreboard crowns cross-checked against the
        towers felled in-match (crowns == towers destroyed). Taking the max per side
        recovers crowns the scoreboard misses (which otherwise reads a loss as a
        draw); a felled king tower is decisive. Then tap to exit."""
        deadline = time.time() + self.results_timeout
        thr = float(self.cfg.get("outcome", "gold_frac", default=0.10))
        settle = int(self.cfg.get("outcome", "settle_reads", default=8))
        red = [0.0, 0.0, 0.0]
        blue = [0.0, 0.0, 0.0]
        seen = stable = 0
        last_total = -1
        dc = False
        while time.time() < deadline:
            frame = self._grab()
            if frame is None:
                break
            sb = read_scoreboard(frame, self.cfg)
            if sb.present:
                red = [max(a, b) for a, b in zip(red, sb.red_fracs)]
                blue = [max(a, b) for a, b in zip(blue, sb.blue_fracs)]
                dc = self.vision.match_end_is_dc(frame)
                seen += 1
                # Crowns animate in one-by-one, so keep reading (taking the max per
                # cushion) until the crown total holds steady -- not just until the
                # board first appears -- or the deciding crown of a 3-0 gets missed.
                total = sum(f >= thr for f in red) + sum(f >= thr for f in blue)
                stable = stable + 1 if total == last_total else 0
                last_total = total
                if seen >= 4 and stable >= settle:
                    break
            time.sleep(self.poll_dt)

        sb_blue = sum(f >= thr for f in blue)
        sb_red = sum(f >= thr for f in red)
        # crowns == towers destroyed: latched in-match, independent of the scoreboard
        t_blue, t_red, enemy_king, my_king = self.tower.crown_counts()
        blue_c, red_c = max(sb_blue, t_blue), max(sb_red, t_red)
        if enemy_king and not my_king:            # a felled king tower is decisive
            outcome: Optional[str] = "win"
        elif my_king and not enemy_king:
            outcome = "loss"
        elif seen == 0 and t_blue == 0 and t_red == 0:
            outcome = None                        # never saw the scoreboard, no towers fell
        else:
            outcome = "win" if blue_c > red_c else "loss" if red_c > blue_c else "draw"
        reward = outcome_reward(outcome, self.cfg) if outcome else 0.0
        # leave the results screen so reset() can queue the next match
        self.controller.tap(*(self.results_dc if dc else self.results_ok))
        time.sleep(self.menu_delay)
        detail = {"crowns": (blue_c, red_c), "scoreboard": (sb_blue, sb_red), "towers": (t_blue, t_red)}
        return reward, outcome, detail
