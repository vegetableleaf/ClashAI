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

import math
import time
from typing import Optional, Tuple

import numpy as np

from .actions import ActionSpace
from .capture import WindowCapture
from .controller import Controller
from .outcome import outcome_reward, read_scoreboard
from .reward import (TowerTracker, _anchors, enemy_mass, near_enemy_king, near_enemy_princess,
                     pump_rocket_cell, spell_intercept_cell, threat_side, weaker_princess_cell,
                     xbow_lock_cell)
from .clock import ElixirClock
from .states import GameState
from .nav import MenuNavigator
from .threats import ThreatTracker, Threat
from . import card_threat
from . import interactions
from .cycle import CycleTracker
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
        self.clock = ElixirClock(cfg, self.vision)   # 2x/3x elixir multiplier (feeds the phase machine)
        self.elixir_mult = 1
        self.gw, self.gh = int(self.actions.gw), int(self.actions.gh)
        self.n_slots, self.n_cells = self.actions.n_slots, self.actions.n_cells

        self.act_period = float(cfg.get("play", "act_period", default=1.5))
        self.react_min_gap = float(cfg.get("play", "react_min_gap_s", default=0.3))
        self.poll_dt = 1.0 / float(cfg.get("nav", "poll_hz", default=6))
        self.menu_delay = float(cfg.get("nav", "menu_delay", default=1.0))
        self.results_timeout = float(cfg.get("env", "results_timeout", default=30.0))

        self.battle = cfg.get("buttons", "battle_button", default=[0.5, 0.9])
        self.quick = cfg.get("buttons", "quick_match", default=[0.5, 0.55])
        self.results_ok = cfg.get("buttons", "results_ok", default=[0.5, 0.9])
        self.results_dc = cfg.get("buttons", "results_ok_dc", default=self.results_ok)
        self.play_again = cfg.get("buttons", "play_again", default=self.results_ok)
        _home = cfg.get("states", "home_menu", default={}) or {}
        self._home_tpl = _home.get("template", "home_menu.png")
        self._home_thr = float(_home.get("threshold", 0.8))
        self._nav = MenuNavigator(cfg, self.controller, self.vision, label="train-rl")

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
        # card-role id sets the reward + deploy logic still need (rocket/miner = anywhere; spell = eval;
        # x_bow = win condition; royal_delivery = defensive area spell; defensive_kind feeds reactive_ids).
        self.spell_ids = set()
        self.rocket_ids = set()
        self.royal_delivery_ids = set()
        self.tornado_ids = set()
        self.miner_ids = set()
        self.xbow_ids = set()
        self.defensive_kind = {}                        # id -> defender kind (Tesla / Ice Wizard) for reactive_ids
        for i, key in enumerate(self.vision.deck_keys):
            base = key[:-4] if key.endswith("_evo") else key
            c = db.get(base)
            if c and c.get("kind") == "spell":
                self.spell_ids.add(i)
            if base == "rocket":
                self.rocket_ids.add(i)
            elif base == "royal_delivery":          # defensive area spell on your half (long fixed delay)
                self.royal_delivery_ids.add(i)
            elif base == "tornado":                 # defensive PULL spell -> reacts to a push (near-immediate)
                self.tornado_ids.add(i)
            elif base == "miner":                   # tank/chip -> deployed ANYWHERE (enemy tower, behind a tank)
                self.miner_ids.add(i)
            elif base == "x_bow":                   # siege WIN CONDITION -> forward (in range) or back-centre defence
                self.xbow_ids.add(i)
            if base == "tesla":
                self.defensive_kind[i] = "tesla"
            elif base == "ice_wizard":
                self.defensive_kind[i] = "ice_wizard"
        # ROCKET and MINER may target ANYWHERE; every other card (troops, X-Bow, royal delivery) is your-half only.
        self.anywhere_ids = self.rocket_ids | self.miner_ids
        # cards played only to REACT to a threat (defenders + Royal Delivery / Tornado); on a QUIET board they're premature.
        self.reactive_ids = set(self.defensive_kind) | self.royal_delivery_ids | self.tornado_ids
        # --- perception geometry the reward + spell-impact timing still use ---
        self.spell_effect = bool(cfg.get("env", "spell_effect_reward", default=True))   # gate: sample frames at spell impact
        self.spell_eval_time = float(cfg.get("env", "spell_eval_time", default=2.4))
        self.spell_aim_radius = float(cfg.get("env", "spell_tower_aim_radius", default=0.12))
        # rocket / spell IMPACT timing -- predict when to grab the effect frame (see _impact_time)
        self.rocket_origin = cfg.get("env", "rocket_origin", default=[0.5, 1.05])
        self.rocket_base_time = float(cfg.get("env", "rocket_base_time", default=0.3))
        self.rocket_travel_rate = float(cfg.get("env", "rocket_travel_rate", default=2.2))
        self.tornado_time = float(cfg.get("env", "tornado_time", default=1.2))
        self.royal_delivery_time = float(cfg.get("env", "royal_delivery_time", default=3.0))
        # lane read for the threat-response intercept (_same_lane)
        self.threat_min_frac = float(cfg.get("env", "defense_threat_frac", default=0.02))
        self.lane_split_x = 0.48                       # left/right split -- matches reward.threat_side
        self.wrong_lane_margin = float(cfg.get("env", "wrong_lane_margin", default=0.12))
        self._match_bonus = 0.0
        # X-Bow win-condition geometry (offence forward-in-range / defence back-centre) + the phase gauge
        self.xbow_range = float(cfg.get("env", "xbow_range", default=0.36))
        self.xbow_defense_front = float(cfg.get("env", "xbow_defense_front", default=0.52))
        self.xbow_defense_back = float(cfg.get("env", "xbow_defense_back", default=0.62))
        self.xbow_deep_frac = float(cfg.get("rewards", "xbow_deep_frac", default=0.25))
        self.xbow_success_frac = float(cfg.get("env", "xbow_success_frac", default=0.30))
        # thresholds the correctness terms use
        self.quiet_frac = float(cfg.get("env", "enemy_quiet_frac", default=0.02))       # 'quiet board' enemy-mass gate
        self.full_elixir = int(cfg.get("env", "elixir_full", default=10))               # leak / cycle threshold
        self.defeat_cap = float(cfg.get("env", "defeat_cap", default=0.15))             # 'full push' mass scale for the trade term
        self._prev_mass = 0.0
        self._prev_my_hp = 0.0
        # --- reactive play: live enemy-threat vector (policy input) + foresight rewards ---
        self.threat_tracker = ThreatTracker(cfg)
        self.threat_vec = Threat.zeros()          # normalized threat features -> policy input
        self._last_threat = Threat()              # threat at action-selection time (for reward)
        # Stage 3: identity-grounded threat block from the DETECTOR (only RECOGNISED, HIGH-confidence
        # enemy cards fire). Loaded lazily so torch/ultralytics stay out of the loop when it's off.
        self.use_detector = bool(cfg.get("observation", "use_detector", default=False))
        self.detector_conf = float(cfg.get("observation", "detector_conf", default=0.75))
        self.detector_cards = set(cfg.get("observation", "detector_cards", default=[]))
        self.predict_horizon = float(cfg.get("observation", "predict_horizon_s", default=1.0))
        self.db = db
        # your deck's KB profiles (played-card role) for the role-based COUNTER reward
        self._deck_profiles = [card_threat.profile(db, (k[:-4] if k.endswith("_evo") else k))
                               for k in self.vision.deck_keys]
        # --- CORRECTNESS-FIRST reward weights (mirror the sim; see sim/env.py). ONE coherent score of a
        # few bounded sub-terms replaces the old ~40 patchwork rewards; the assembly is in step(). ---
        rw = lambda k, d: float(cfg.get("rewards", k, default=d))  # noqa: E731
        self.w_threat_response = rw("threat_response", 1.0)   # (1) KB counter to the assessed threat, placed to intercept
        self.w_threat_miss = rw("threat_miss", -1.0)          # wrong counter / wrong lane / ignored an ANSWERABLE threat
        self.w_elixir_trade = rw("elixir_trade", 1.0)         # (2) (enemy value eliminated - elixir spent), normalised
        self.w_wincon = rw("wincon_exec", 0.8)                # (3) win-condition executed right for the phase
        self.w_wincon_mis = rw("wincon_misplace", -0.6)       # win-condition thrown away
        self.w_cycle_plan = rw("cycle_plan", 0.4)             # (4) cheap play advancing toward a NEEDED upcoming counter
        self.w_cycle_waste = rw("cycle_waste", -0.4)          # purposeless cheap spam
        self.w_leak = rw("leak_penalty", -0.2)                # (5) sitting at elixir capacity, leaking
        self.correctness_cap = rw("correctness_cap", 20.0)    # per-match cap on POSITIVE shaping (anti-farm)
        self.w_take = rw("take_enemy_tower", 1.0); self.w_lose = rw("lose_own_tower", -1.0)   # the CROWN jump on a take/loss
        self.tower_chip_scale = rw("tower_chip_scale", 0.3)   # convex chip POOL per tower (small; the crown is the jump)
        self.chip_power = float(cfg.get("env", "tower_chip_power", default=2.0))   # >1 -> partial chip sub-proportional
        self.combo_mult = rw("rocket_combo_mult", 3.0)
        self.intercept_lane = float(cfg.get("env", "intercept_lane", default=0.15))
        self.cycle_cheap_max = int(cfg.get("env", "cycle_cheap_max", default=3))
        self.cycle_spare_elixir = float(cfg.get("env", "cycle_spare_elixir", default=7.0))
        self.value_norm = float(cfg.get("env", "value_norm", default=10.0))
        self.trade_cap = float(cfg.get("env", "trade_cap", default=1.0))
        self.card_elixir = [(db.elixir(k) or db.elixir(k[:-4] if k.endswith("_evo") else k) or 0)
                            for k in self.vision.deck_keys]   # per-card elixir cost (the trade-term spend)
        self._detector = None
        self._threat_id = np.zeros(card_threat.IDENTITY_DIM, np.float32)   # last identity block (for reward)
        self._prev_ident_depth = 0.0        # deepest recognised-threat depth last step (for velocity)
        self._prev_ident_t = None
        self._opp_mem = card_threat.OpponentMemory(db)   # per-match opponent short-term memory (Stage 3)
        from .replay_mine import TeamTracker
        self._team_tracker = TeamTracker(                # LIVE: evidence-fused teams (plays/motion/bars/pockets)
            spawn_radius=float(cfg.get("observation", "team_spawn_radius", default=0.10)),
            spawn_window_s=float(cfg.get("observation", "team_spawn_window_s", default=2.5)),
            enemy_window_s=float(cfg.get("observation", "team_enemy_window_s", default=4.0)),
            track_radius=float(cfg.get("observation", "team_track_radius", default=0.12)),
            forget_s=float(cfg.get("observation", "team_forget_s", default=4.5)),
            motion_min=float(cfg.get("observation", "team_motion_min", default=0.05)),
            deep_mine_y=float(cfg.get("observation", "team_deep_mine_y", default=0.62)),
            deep_enemy_y=float(cfg.get("observation", "team_deep_enemy_y", default=0.38)))
        # Stage-3b gate: the troop-INTERACTION block (predicted tower pressure) -- live twin of the sim's
        self.use_interactions = bool(cfg.get("observation", "use_interactions", default=False))
        self.sight_range = float(cfg.get("sim", "sight_range", default=0.12))
        self._last_dets_all = []                         # every tagged detection this frame (both teams)
        # PUMP PUNISH (elixir collector -> rocket): sighting state for the reward + the aim assist
        self.pump_window = float(cfg.get("env", "pump_rocket_window_s", default=12.0))
        self.pump_aim_radius = float(cfg.get("env", "pump_aim_radius", default=0.10))
        self.pump_pair_gap = float(cfg.get("env", "pump_pair_gap", default=0.11))
        self.pump_king_guard = float(cfg.get("env", "pump_king_guard", default=0.15))
        self.combo_mult = float(cfg.get("rewards", "rocket_combo_mult", default=3.0))
        self.spell_lead_radius = float(cfg.get("env", "spell_lead_radius", default=0.12))
        self._pump_seen_t = None                         # when a pump was FIRST sighted (window anchor)
        self._pump_last_t = 0.0                          # last read that still saw it
        self._pump_xy = None                             # its latest (cx, gy)
        self._cycle_tracker = CycleTracker(self.n_cards)   # live estimate of the upcoming-card order (graded next_vec)
        # Optional callable -> True when the caller wants to stop. reset() navigates menus in an
        # UNBOUNDED loop waiting for a match, so without this a trainer whose SIGINT handler only sets
        # a flag can never be interrupted between matches: the flag is set and nothing ever reads it.
        self.stop_requested = None
        if self.use_detector:
            self.threat_vec = np.concatenate(
                [self.threat_vec, self._threat_id,
                 np.zeros(card_threat.OPP_MEMORY_DIM, np.float32)]).astype(np.float32)
            try:
                from .replay_mine import load_detector
                det = load_detector(cfg)
                self._detector = det if det.available else None
            except Exception:
                self._detector = None
        if self.use_interactions:                        # widen by the interaction block (zeros until read)
            self.threat_vec = np.concatenate(
                [self.threat_vec, np.zeros(interactions.INTERACTION_DIM, np.float32)]).astype(np.float32)
        # live side-window: each frame + the detector's team-coloured boxes (train-rl babysitting).
        from .detect import LivePreview
        self._preview = LivePreview(cfg)
        # CONTINUOUS PERCEPTION (~10Hz): a background thread runs the detector + team tracker so the
        # act loop reads a <=1-period-old snapshot instead of being blind between decisions, tracker
        # velocities are finely sampled (rocket lead / motion team evidence), and the preview is live.
        self._ploop = None
        hz = float(cfg.get("observation", "perception_hz", default=10.0))
        if self._detector is not None and hz > 0:
            from .perception import PerceptionLoop
            self._ploop = PerceptionLoop(cfg, self._detector, self._team_tracker,
                                         self.detector_conf, hz, preview=self._preview)
            self._ploop.start()

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
        """Recognize the hand -> deck ids per slot + multi-hot (for identity actions), and the next
        (preview) card, then fold both through the cycle tracker into a graded UPCOMING-order vector
        (Next=1.0 grading down for the hidden cards) so the policy can plan which cards to cycle to."""
        self.hand_ids = self.vision.recognize_hand(frame)
        self.hand_vec = self.vision.hand_multihot(self.hand_ids)
        self.next_id = self.vision.recognize_next(frame)
        self.next_vec = self._cycle_tracker.observe(self.hand_ids, self.next_id)

    def _update_threat(self, frame) -> None:
        """Advance the live enemy-threat read from the current frame -> policy input vector. When
        use_detector, append card_threat's identity block (RECOGNISED, HIGH-confidence enemy cards on
        YOUR half) + the opponent SHORT-TERM MEMORY block (whole-match read, both halves). All-zero if
        the detector is unavailable."""
        self._last_threat = self.threat_tracker.update(frame, time.time())
        base = self._last_threat.vector()
        if not self.use_detector:
            self.threat_vec = base if not self.use_interactions else np.concatenate(
                [base, np.zeros(interactions.INTERACTION_DIM, np.float32)]).astype(np.float32)
            self._preview.update(frame, [], self.capture.region)      # plain frame (no detector loaded)
            return
        dets = self._detect_enemies(frame)                                   # ONE detector pass this frame
        now = time.time()
        self._track_pump(now)                                                # pump sighting -> punish window
        dt = (now - self._prev_ident_t) if self._prev_ident_t else 0.0
        items = [(d.base, (d.gy - 0.5) / 0.5) for d in dets if d.gy >= 0.5]   # identity: YOUR half only
        self._threat_id = card_threat.identity_threat_vector(
            items, self.db, prev_depth=self._prev_ident_depth, dt=dt, horizon=self.predict_horizon)
        self._prev_ident_depth = float(self._threat_id[7])
        self._prev_ident_t = now
        mem = self._opp_mem.update([(d.base, d.gy) for d in dets], dt=dt)    # memory: BOTH halves (incl. staging)
        parts = [base, self._threat_id, mem]
        if self.use_interactions:                        # predicted tower pressure from ALL tagged detections
            mine_a, enemy_a, _ = _anchors(self.cfg)
            my_t = [(ax, ay, bool(self.tower.mine_alive[i])) for i, (ax, ay) in enumerate(mine_a[:3])]
            en_t = [(ax, ay, bool(self.tower.enemy_alive[i])) for i, (ax, ay) in enumerate(enemy_a[:3])]
            units = [("mine" if d.team == "mine" else "enemy", d.base, d.cx, d.gy)
                     for d in self._last_dets_all
                     if d.team in ("mine", "enemy") and d.base in self.detector_cards]
            parts.append(interactions.interaction_vector(units, my_t, en_t, self.db))
        self.threat_vec = np.concatenate(parts).astype(np.float32)
        if self._ploop is None:      # side window (perception loop feeds it at 10Hz itself when active)
            self._preview.update(frame, self._last_dets_all, self.capture.region)

    def _detect_enemies(self, frame):
        """Whitelisted ENEMY detections (both halves; each has .base + .gy in [0,1]). With the
        perception loop running this is the latest ~10Hz SNAPSHOT (already team-tagged in the
        thread); otherwise one synchronous detector pass. [] if the detector is off/unavailable."""
        if self._detector is None:
            return []
        if self._ploop is not None and self._ploop.running:
            self._ploop.set_towers(self.tower.mine_alive, self.tower.enemy_alive)  # pocket gating stays fresh
            dets, age = self._ploop.snapshot()
            if age <= 2.0:                                # healthy loop -> use the snapshot
                self._last_dets_all = dets
                return [d for d in dets if d.team == "enemy" and d.base in self.detector_cards]
        try:
            dets = self._detector.detect(frame, conf=self.detector_conf)
        except Exception:
            return []
        # a fallen princess opens the deploy POCKET in front of it -> void the side prior for that lane
        self._team_tracker.set_towers(self.tower.mine_alive, self.tower.enemy_alive)
        self._team_tracker.tag(dets, time.time())     # evidence-fused team (plays/motion/bars/pockets)
        self._last_dets_all = dets                    # kept for the interaction block (both teams)
        return [d for d in dets if d.team == "enemy" and d.base in self.detector_cards]

    # -- episode lifecycle --------------------------------------------
    def reset(self) -> Optional[np.ndarray]:
        """Navigate menus until a match starts; return the first observation.

        Returns None if the game window is lost OR ``stop_requested()`` goes True -- callers use
        ``self.stopped`` to tell the two apart.
        """
        self.stopped = False
        self.tower.reset()
        self.tower_hp.reset()
        self._defensive = False           # icebow phase: False = offensive X-Bow win condition; True = defence + rocket-cycle
        self._enemy_chip_total = 0.0      # cumulative enemy-tower HP chipped (the X-Bow 'did it break through?' gauge)
        self._match_bonus = 0.0
        self._nav.reset_state()
        while True:
            if self.stop_requested is not None and self.stop_requested():
                self.stopped = True          # a deliberate stop, NOT a lost window
                return None
            frame = self._grab()
            if frame is None:
                return None
            state = self.vision.detect_state(frame)
            if state == GameState.IN_MATCH:
                self.clock.reset()               # zero the 2x/3x elixir clock at match start
                self.elixir_mult = 1
                self.elixir = self.vision.read_elixir(frame)
                self.elixir_vec = np.asarray([self.elixir / 10.0], dtype=np.float32)
                self.threat_tracker.reset()
                self._prev_ident_depth = 0.0
                self._prev_ident_t = None
                self._opp_mem.reset()
                if self._ploop is not None and self._ploop.running:
                    self._ploop.reset_tracker()       # forget last match's tracks (thread-safe)
                else:
                    self._team_tracker.reset()
                self._pump_seen_t = None                  # forget last match's pump sighting
                self._pump_xy = None
                self._cycle_tracker.reset()
                self._read_hand(frame)
                self._update_threat(frame)
                self._last_obs = self.vision.observe(frame)
                self._last_frame = frame
                self._prev_mass = enemy_mass(frame, self.cfg)
                self._prev_my_hp = float(sum(self.tower_hp.my_hp))
                self._prev_chip_prog = 0.0        # convex enemy-tower chip progress (offense)
                self._prev_chip_prog_def = 0.0    # convex own-tower chip progress (defense)
                return self._last_obs
            self._nav.handle(frame, state)   # robust menu nav: located buttons + MATCH_END escalation + popup watchdog + logging

    def _execute(self, action: Action) -> None:
        play, card_id, cell = action
        if not play:
            return
        slot = next((s for s, c in enumerate(self.hand_ids) if c == card_id), -1)
        if slot < 0:                          # chosen card not in hand (unrecognized) -> skip
            return
        gx, gy = cell % self.gw, cell // self.gw
        self.controller.play_card(*self.actions.decode(slot, gx, gy))
        self._cycle_tracker.record_play(card_id)      # a card left the hand -> it rotates to the queue back
        # ANY play (troop or spell) anchors its own detection 'mine' -- base-matched, so your rolling Log
        # is claimed at the cast point while an enemy answer dropped on the same spot is not.
        cx, cy = self.actions.cell_center(gx, gy)
        base = card_threat.base_key(self.vision.deck_keys[card_id])
        if self._ploop is not None and self._ploop.running:
            self._ploop.record_play(cx, cy, time.time(), base=base)
        else:
            self._team_tracker.record_play(cx, cy, time.time(), base=base)

    def _track_pump(self, now: float) -> None:
        """Watch the tagged detections for an enemy ELIXIR COLLECTOR on their half: the FIRST sighting
        anchors the punish window (env.pump_rocket_window_s -- a pump left alive past it has already
        paid out, especially against a control deck); the sighting expires after ~6s without one."""
        pumps = [d for d in self._last_dets_all
                 if d.base == "elixir_collector" and d.team != "mine" and d.gy < 0.5]
        if pumps:
            if self._pump_seen_t is None:
                self._pump_seen_t = now
            self._pump_last_t = now
            self._pump_xy = (pumps[0].cx, pumps[0].gy)
        elif self._pump_seen_t is not None and now - self._pump_last_t > 6.0:
            self._pump_seen_t = None
            self._pump_xy = None

    def _pump_fresh(self) -> bool:
        """A sighted enemy pump still inside the punish window (rocketing it is still worth it)."""
        return (self._pump_seen_t is not None and self._pump_xy is not None
                and time.time() - self._pump_seen_t <= self.pump_window)

    def _aim_weaker_tower(self, card_id: int, cell: int) -> int:
        """A ROCKET or an offensive MINER aimed at an enemy princess is redirected to the lower-HP
        princess so it finishes off the WEAKER tower (more efficient) instead of splitting damage --
        the same chip logic for both. The policy can't read tower HP (it isn't in the observation), so
        the env picks the weaker tower mechanically. No-op for other cards, other targets, or while a
        princess is down / both are at equal HP (then the model's own aim / lane stands)."""
        if card_id not in self.rocket_ids and card_id not in self.miner_ids:
            return cell
        gx, gy = cell % self.gw, cell // self.gw
        cx, cy = self.actions.cell_center(gx, gy)
        # PUMP PUNISH aim assist: a rocket the policy ALREADY aims near a fresh enemy pump is snapped to
        # the king-safe optimum -- midpoint with an adjacent princess tower when one blast covers both,
        # else the pump itself; never within pump_king_guard of the king (then the policy's aim stands).
        if card_id in self.rocket_ids and self._pump_fresh():
            pxy = self._pump_xy
            if pxy is not None and math.hypot(cx - pxy[0], cy - pxy[1]) <= self.pump_aim_radius * 1.5:
                tgt = pump_rocket_cell(pxy[0], pxy[1], self.tower.enemy_a, self.tower.enemy_alive,
                                       self.pump_pair_gap, self.pump_king_guard, self.actions)
                if tgt is not None:
                    return tgt
        tgt = weaker_princess_cell(cx, cy, self.spell_aim_radius, self.tower.enemy_a,
                                   self.tower_hp.enemy_hp, self.tower.enemy_alive,
                                   self.actions)
        return tgt if tgt is not None else cell

    def _aim_rocket_intercept(self, cell: int) -> int:
        """ROCKET LEAD ASSIST: the policy aims its 2-tile blast at troops it perceived ~an act period
        ago, and the flight adds 1-2s more -- a marching push walks clean out of the blast by impact.
        Snap the aim to the PREDICTED-at-impact centroid of the tracked enemies near it (TeamTracker
        positions + lifetime velocity). No tracked enemy near the aim (tower chip, pre-aimed spots) ->
        the aim stands. Tornado is deliberately NOT led: its placement is a DESTINATION (where you want
        the clump dragged), not a hit-them point."""
        gx, gy = cell % self.gw, cell // self.gw
        cx, cy = self.actions.cell_center(gx, gy)
        tracks = (self._ploop.enemy_tracks(time.time()) if self._ploop is not None and self._ploop.running
                  else self._team_tracker.enemy_tracks(time.time()))
        tgt = spell_intercept_cell(cx, cy, tracks, self._impact_time(cx, cy, is_rocket=True),
                                   self.spell_lead_radius, self.actions)
        return tgt if tgt is not None else cell

    # ============ CORRECTNESS-FIRST reward helpers (mirror the sim; from live perception) ============
    def _same_lane(self, cx: float) -> bool:
        """True when a placement at horizontal ``cx`` is in the threatened lane (or there is no clear
        lane). Reuses the coarse push-lane read from the pre-action frame."""
        frame = self._last_frame
        if frame is None:
            return True
        side = threat_side(frame, self.cfg, self.threat_min_frac)   # -1 left / 0 none / +1 right
        if side == 0:
            return True
        off = cx - self.lane_split_x
        opposite = abs(off) > self.wrong_lane_margin and (off < 0) == (side > 0)
        return not opposite

    def _threat_response_live(self, card_id: int, cx: float, cy: float, cur_mass: float) -> float:
        """(1) THREAT-RESPONSE: the KB-correct counter to the RECOGNISED threat, placed to intercept
        (its lane, your half). Wrong role dropped as a defence -> penalty; a defender on a QUIET board
        (nothing recognised, no mass) -> premature. Offensive placements are judged by wincon_exec / trade."""
        prof = self._deck_profiles[card_id] if 0 <= card_id < len(self._deck_profiles) else None
        if prof is None:
            return 0.0
        tid = self._threat_id
        has_threat = tid is not None and len(tid) >= card_threat.IDENTITY_DIM and tid[0] >= 0.5
        if not has_threat:
            if cur_mass < self.quiet_frac and cy >= 0.5 and card_id in self.reactive_ids:
                return self.w_threat_miss * 0.4        # a defender on a quiet board = premature (small)
            return 0.0
        intercept = self._same_lane(cx) and cy >= 0.5
        if prof.pull:
            return 0.0        # PULL spells are graded by their delayed clump payoff, not by role match
                              # (see sim/env._threat_response) -- spell_waste still punishes an empty cast
        if card_threat.counters(prof, tid):
            return self.w_threat_response if intercept else 0.0
        return self.w_threat_miss if intercept else 0.0

    def _threat_miss_idle_live(self, cur_mass: float) -> float:
        """No play while an ANSWERABLE threat is recognised (a KB counter is in hand AND affordable) =
        a missed defence (uncapped penalty)."""
        tid = self._threat_id
        if tid is None or len(tid) < card_threat.IDENTITY_DIM or tid[0] < 0.5:
            return 0.0
        for cid in self.hand_ids:
            if (0 <= cid < len(self._deck_profiles) and card_threat.counters(self._deck_profiles[cid], tid)
                    and self.card_elixir[cid] <= self.elixir):
                return self.w_threat_miss
        return 0.0

    def _wincon_exec_live(self, card_id: int, cx: float, cy: float) -> float:
        """(3) WIN-CONDITION execution: X-Bow forward-in-range (offence) / back-centre (defence), Miner
        chipping the princess (not the king), the defensive rocket-cycle chip. + right, - thrown away."""
        if card_id in self.xbow_ids:
            _, enemy_a, _ = _anchors(self.cfg)
            princesses = enemy_a[:2] if len(enemy_a) >= 2 else enemy_a
            d = min((math.hypot(cx - ax, cy - ay) for ax, ay in princesses), default=1.0)
            # "back-centre" = the CENTER INTERCEPT band behind the bridge (the Tesla area), NOT behind your
            # princess towers; deeper than the towers earns only a small fraction (soft shaping).
            central = abs(cx - 0.48) <= 0.18
            in_band = central and self.xbow_defense_front <= cy <= self.xbow_defense_back
            behind = central and cy > self.xbow_defense_back
            frac = 1.0 if in_band else (self.xbow_deep_frac if behind else 0.0)
            if self._defensive:
                return self.w_wincon * frac if frac > 0.0 else self.w_wincon_mis
            if d <= self.xbow_range:
                return self.w_wincon
            return self.w_wincon * 0.4 * frac if frac > 0.0 else self.w_wincon_mis
        if card_id in self.rocket_ids:
            pxy = self._pump_xy if self._pump_fresh() else None   # PUMP PUNISH mirror (perception-gated)
            if pxy is not None and math.hypot(cx - pxy[0], cy - pxy[1]) <= self.pump_aim_radius:
                _, enemy_a, _ = _anchors(self.cfg)
                kx, ky = enemy_a[2] if len(enemy_a) >= 3 else (0.48, 0.11)
                if math.hypot(cx - kx, cy - ky) <= self.pump_king_guard:
                    return self.w_wincon_mis              # blast would wake the king -- never for a pump
                both = any(bool(self.tower.enemy_alive[i])
                           and math.hypot(cx - ax, cy - ay) <= self.spell_aim_radius
                           for i, (ax, ay) in enumerate(enemy_a[:2]))
                return self.w_wincon * (self.combo_mult if both else 1.0)
            if self._defensive and near_enemy_princess(cx, cy, self.cfg, self.spell_aim_radius):
                return self.w_wincon * 0.6
            return 0.0
        if card_id in self.miner_ids:
            if near_enemy_king(cx, cy, self.cfg, self.spell_aim_radius):
                return self.w_wincon_mis
            if near_enemy_princess(cx, cy, self.cfg, self.spell_aim_radius):
                return self.w_wincon
        return 0.0

    def _needed_counter_coming(self, hand) -> bool:
        """True when the hand holds NO KB counter to the assessed threat but the deck DOES (upcoming)."""
        if (self._pump_fresh() and not (set(hand) & self.rocket_ids)
                and any(r not in hand for r in self.rocket_ids)):
            return True                                       # a fresh enemy PUMP is a rocket job: cycle to it
        tid = self._threat_id
        if tid is None or len(tid) < card_threat.IDENTITY_DIM or tid[0] < 0.5:
            return False
        if any(0 <= c < len(self._deck_profiles) and card_threat.counters(self._deck_profiles[c], tid)
               for c in hand):
            return False
        return any(card_threat.counters(self._deck_profiles[c], tid)
                   for c in range(self.n_cards) if c not in hand)

    def _cycle_plan_live(self, card_id: int, pre_elixir: float) -> float:
        """(4) CYCLE-PLAN: a CHEAP play at spare elixir that advances toward a NEEDED counter you don't
        hold but the deck does -> +; purposeless cheap spam -> -."""
        if not (0 <= card_id < self.n_cards) or self.card_elixir[card_id] > self.cycle_cheap_max:
            return 0.0
        hand = [c for c in self.hand_ids if 0 <= c < self.n_cards]
        if self._needed_counter_coming(hand):
            return self.w_cycle_plan if pre_elixir >= self.cycle_spare_elixir else 0.0
        return self.w_cycle_waste if pre_elixir < self.cycle_spare_elixir else 0.0

    def _trade_reward(self, mass_delta: float, spent: float) -> float:
        """(2) ELIXIR-TRADE: potential-based enemy-mass change (clipped to a 'full push' fraction so it
        telescopes -> idling can't farm it) MINUS the elixir committed this step. Trading up -> +,
        overspending / whiffing -> -."""
        killed = float(np.clip(mass_delta / self.defeat_cap, -1.0, 1.0))
        return (killed - spent / self.value_norm) * self.w_elixir_trade

    def _forced_expensive_spend(self, card_id: int, cy: float) -> bool:
        """A defensive spend is FORCED (waive its elixir-trade penalty) when a threat is recognised, the
        play is on your defensive half, and NO CHEAPER card in hand or the NEXT slot could counter it --
        e.g. rocket the hogs/balloon, or centre X-Bow to pull a wincon, when Tesla is too deep in the cycle.
        Overspending when a cheaper answer WAS immediately available is NOT waived."""
        if cy < 0.5:
            return False                                  # offensive placements pay their spend normally
        tid = self._threat_id
        if tid is None or len(tid) < card_threat.IDENTITY_DIM or tid[0] < 0.5:
            return False
        if not (0 <= card_id < self.n_cards):
            return False
        my_elix = self.card_elixir[card_id]
        avail = [c for c in self.hand_ids if 0 <= c < self.n_cards]
        if 0 <= self.next_id < self.n_cards:
            avail.append(self.next_id)                    # the NEXT (preview) card counts as immediately available
        for c in avail:
            if (c != card_id and self.card_elixir[c] < my_elix
                    and card_threat.counters(self._deck_profiles[c], tid)):
                return False                             # a cheaper counter was in hand / next -> not forced
        return True

    def _chip_progress(self, hp_list, full: float) -> float:
        """Convex chip 'progress' over a side's princess towers: sum of (damage_fraction ** chip_power) so
        PARTIAL chip is worth sub-proportionally LESS than finishing the tower. Most of a tower's value is
        the CROWN (take/lose), so the reward JUMPS when it is actually destroyed -- a tower at 1-2 HP still
        fully works, so it's worth far less than one at 0."""
        prog = 0.0
        for hp in list(hp_list)[:2]:
            if full > 0:
                d = max(0.0, min(1.0, 1.0 - hp / full))
                prog += d ** self.chip_power
        return prog

    def _bonus(self, credit: float) -> float:
        """Cap the CUMULATIVE positive correctness shaping per match (anti-farm); penalties (<=0) pass
        through untouched."""
        if credit <= 0.0:
            return credit
        allowed = min(credit, max(0.0, self.correctness_cap - self._match_bonus))
        self._match_bonus += allowed
        return allowed

    def step(self, action: Action):
        play, card_id, cell = action
        raw_cell = cell                           # the model's ATTEMPTED cell, before aim + deploy-clamp
        if play:                                  # rocket / offensive miner -> aim the weaker enemy princess tower
            pre_aim = cell
            cell = self._aim_weaker_tower(card_id, cell)
            if cell == pre_aim and card_id in self.rocket_ids:    # no tower/pump snap -> LEAD tracked troops
                cell = self._aim_rocket_intercept(cell)
            cell = self.actions.deploy_clamp(card_id in self.anywhere_ids, cell)  # rocket + miner go anywhere; rest = your half
            if card_id in self.xbow_ids and not self._defensive:  # OFFENSIVE phase only: snap a forward X-Bow onto the nearer lane so it LOCKS
                gx, gy = cell % self.gw, cell // self.gw
                cx, cy = self.actions.cell_center(gx, gy)
                _, enemy_a, _ = _anchors(self.cfg)
                snapped = xbow_lock_cell(cx, cy, enemy_a, self.xbow_range, self.xbow_defense_front, self.actions)
                if snapped is not None:
                    cell = snapped
            action = (play, card_id, cell)
        eval_spell = bool(play) and card_id in self.spell_ids and self.spell_effect
        is_rocket = card_id in self.rocket_ids
        is_rd = card_id in self.royal_delivery_ids
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
            if self._ploop is not None and self._ploop.running:
                # EVENT-DRIVEN: wake the moment perception spots a new enemy commitment (reaction
                # ~0.3-0.45s = perception period + inference + tap) instead of sleeping the full period;
                # min_gap rate-limits so quiet-board cadence stays at the trained act_period.
                self._ploop.wait_event(self.act_period, self.react_min_gap)
            else:
                time.sleep(self.act_period)
            frame = self._grab()
        if frame is None:
            return self._last_obs, 0.0, True, {"outcome": None, "error": "capture_lost"}

        state = self.vision.detect_state(frame)
        if state == GameState.IN_MATCH:
            prev_princess = list(self.tower.mine_alive[:2])
            prev_enemy = list(self.tower.enemy_alive[:2])
            # OUTCOME compass: the CROWN is the big JUMP (enemy tower taken -> +take, my king lost -> +lose);
            # tower_hp.step still READS/updates per-tower HP -- its own linear return is unused now.
            crown_r = self.tower.step(frame)
            self.tower_hp.step(frame)
            # CONVEX chip proxy: partial chip is worth sub-proportionally little (a tower at 1-2 HP still
            # works), so the reward JUMPS on the crown, not gradually with damage.
            ep = self._chip_progress(self.tower_hp.enemy_hp, self.tower_hp.full)
            reward = crown_r + (ep - self._prev_chip_prog) * self.tower_chip_scale
            self._prev_chip_prog = ep
            mp = self._chip_progress(self.tower_hp.my_hp, self.tower_hp.my_full)
            reward -= (mp - self._prev_chip_prog_def) * self.tower_chip_scale
            self._prev_chip_prog_def = mp
            for i in range(len(prev_princess)):              # a felled princess -> the big defensive jump
                if prev_princess[i] and not self.tower.mine_alive[i]:
                    reward += self.w_lose
            cur_mass = enemy_mass(frame, self.cfg)
            my_hp = float(sum(self.tower_hp.my_hp))
            cur_elixir = self.vision.read_elixir(frame)
            new_mult = self.clock.update(frame)                  # 2x/3x elixir clock (time + optional badge)
            if new_mult != self.elixir_mult:
                print(f"[env] elixir x{new_mult}")               # 1x -> 2x (double) -> 3x (overtime)
            self.elixir_mult = new_mult
            # BEHIND + FULL-BAR read (for the idle penalty + the offense-when-behind reward below):
            # behind = a princess is down that the enemy still has, OR our weakest STANDING tower has
            # less HP than the enemy's weakest. pre_elixir = the bar at DECISION time (post-action the
            # card's cost is already spent, so a played card would read a non-full bar).
            pre_elixir = self.vision.read_elixir(self._last_frame) if self._last_frame is not None else cur_elixir
            # OFFENSE -> DEFENSE phase (icebow): once you TAKE a tower (defend the lead), OR double elixir
            # has arrived and the X-Bow never broke through (cumulative enemy chip < xbow_success_frac of a
            # tower), give up the offensive X-Bow -> the reward moves to a back-centre X-Bow + rocket-cycle.
            # (The matchup-from-start branch -- defensive vs cycle/beatdown/split-lane decks -- and the
            # beatdown-punish need the opponent's cards, so they wait on the detector / Stage 3.)
            self._enemy_chip_total += max(0.0, self.tower_hp.last_enemy_chip)
            took_tower = any(prev_enemy[i] and not self.tower.enemy_alive[i] for i in range(len(prev_enemy)))
            if not self._defensive and (took_tower or (self.elixir_mult >= 2
                    and self._enemy_chip_total < self.tower_hp.full * self.xbow_success_frac)):
                self._defensive = True
                print("[env] phase -> DEFENSIVE (X-Bow back-centre + rocket-cycle)")
            # --- CORRECTNESS score (mirrors the sim; from live perception) ---
            gx, gy = cell % self.gw, cell // self.gw
            cx, cy = self.actions.cell_center(gx, gy)
            spent = float(self.card_elixir[card_id]) if (play and 0 <= card_id < self.n_cards) else 0.0
            if play and self._forced_expensive_spend(card_id, cy):
                spent = 0.0            # forced defensive counter (no cheaper answer available) -> waive its spend
            if play:
                reward += self._bonus(self._threat_response_live(card_id, cx, cy, cur_mass))   # (1) counter the assessed threat
                reward += self._bonus(self._wincon_exec_live(card_id, cx, cy))                  # (3) win-condition executed right
                reward += self._bonus(self._cycle_plan_live(card_id, pre_elixir))              # (4) deliberate cycling
            else:
                reward += self._threat_miss_idle_live(cur_mass)                                 # (1) ignored an ANSWERABLE threat
            # (2) ELIXIR-TRADE: potential-based enemy-mass change (telescopes, anti-farm) minus the elixir spent.
            reward += self._trade_reward(self._prev_mass - cur_mass, spent)
            if not play and cur_elixir >= self.full_elixir:
                reward += self.w_leak                                                            # (5) leaking at capacity
            self._prev_mass = cur_mass
            self._prev_my_hp = my_hp
            self.elixir = cur_elixir
            self.elixir_vec = np.asarray([cur_elixir / 10.0], dtype=np.float32)
            self._read_hand(frame)
            self._update_threat(frame)
            self._last_obs = self.vision.observe(frame)
            self._last_frame = frame
            return self._last_obs, reward, False, {"elixir": self.elixir, "elixir_mult": self.elixir_mult}

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
        while time.time() < deadline:
            frame = self._grab()
            if frame is None:
                break
            sb = read_scoreboard(frame, self.cfg)
            if sb.present:
                red = [max(a, b) for a, b in zip(red, sb.red_fracs)]
                blue = [max(a, b) for a, b in zip(blue, sb.blue_fracs)]
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
        # A KING kill is a full 3-crown victory. The king ends the match the instant it falls, so its
        # (and the last princess's) destruction latch often can't confirm before the frame cuts to the
        # results screen -- which showed a real 3-0 as "1-0". For the WINNER only, force the count to 3
        # when a king kill is evident (latched OR trending-destroyed at the cut). Display-only:
        # outcome_reward keys off win/loss, not the crown count, so this cannot change the reward.
        ek_soft, mk_soft = self.tower.king_trending_down()
        if outcome == "win" and (enemy_king or ek_soft):
            blue_c = 3
        elif outcome == "loss" and (my_king or mk_soft):
            red_c = 3
        reward = outcome_reward(outcome, self.cfg) if outcome else 0.0
        # leave the results screen by re-queueing (1v1 "Play Again") so the next match
        # starts without a detour through HOME; reset() then picks up QUEUING/IN_MATCH.
        self.controller.tap(*self.play_again)
        time.sleep(self.menu_delay)
        detail = {"crowns": (blue_c, red_c), "scoreboard": (sb_blue, sb_red), "towers": (t_blue, t_red)}
        return reward, outcome, detail
