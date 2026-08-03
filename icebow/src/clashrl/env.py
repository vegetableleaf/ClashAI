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
from .reward import (TowerTracker, _anchors, defensive_cell, enemy_mass, enemy_mass_at,
                     near_enemy_king, near_enemy_princess, near_my_king, threat_front,
                     threat_side, troop_size_at, weaker_princess_cell, xbow_lock_cell)
from .clock import ElixirClock
from .states import GameState
from .nav import MenuNavigator
from .threats import ThreatTracker, Threat
from . import card_threat
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
        self.spell_ids = set()
        self.rocket_ids = set()
        self.tornado_ids = set()
        self.royal_delivery_ids = set()
        self.cheap_ids = set()
        self.tesla_ids = set()
        self.ranged_ids = set()
        self.blocker_ids = set()
        self.building_ids = set()
        self.miner_ids = set()
        self.xbow_ids = set()
        self.log_ids = set()
        self.skeletons_ids = set()
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
            elif base == "miner":                   # tank/chip -> deployed ANYWHERE (enemy tower, behind a tank)
                self.miner_ids.add(i)
            elif base == "x_bow":                   # siege WIN CONDITION -> forward (in tower range) or back-centre defence
                self.xbow_ids.add(i)
            if base in ("the_log", "skeletons"):     # cheap cyclers (The Log = 2-elixir spell) -- OK to play anytime
                self.cheap_ids.add(i)
            if base == "the_log":                    # 2-elixir rolling knockback/reset spell (poor tower chip) -- own shaping
                self.log_ids.add(i)
            elif base == "skeletons":
                self.skeletons_ids.add(i)
            if base == "tesla":                      # Tesla: kill-reward tracked + intercept-zone placement
                self.tesla_ids.add(i)
                self.defensive_kind[i] = "tesla"
                self.building_ids.add(i)             # the DEFENSIVE building; X-Bow is OFFENSIVE -> its own shaping
            elif base == "ice_wizard":
                self.defensive_kind[i] = "ice_wizard"
            if base == "ice_wizard":                 # MOBILE ranged troop (kited/shielded). Tesla is a BUILDING ->
                self.ranged_ids.add(i)               # excluded (you WANT it in the push's path).
            elif base in ("skeletons", "miner"):     # cheap tanks/blockers that shield a ranged unit
                self.blocker_ids.add(i)              # (The Log is a SPELL -> can't tank/block, so it's excluded)
        # ROCKET and MINER may target ANYWHERE (miner chips the enemy tower / tanks behind an enemy
        # unit); every other card (troops, buildings incl. X-Bow, royal delivery) is your-half only.
        self.anywhere_ids = self.rocket_ids | self.miner_ids
        # cards that should only be played to REACT to a threat (defensive troops + Royal Delivery);
        # playing them on a QUIET board is premature -> penalised. Miner/X-Bow are PROACTIVE -> excluded.
        self.reactive_ids = set(self.defensive_kind) | self.royal_delivery_ids
        self.spell_troop_damage = float(cfg.get("rewards", "spell_troop_damage", default=5.0))
        self.spell_hit = float(cfg.get("rewards", "spell_hit", default=0.15))
        self.spell_combo = float(cfg.get("rewards", "spell_combo", default=0.6))
        self.spell_whiff = float(cfg.get("rewards", "spell_whiff", default=-0.5))
        self.log_reset_reward = float(cfg.get("rewards", "log_reset_reward", default=0.3))  # The Log rolled through a real push (knockback/reset buys time)
        self.log_whiff = float(cfg.get("rewards", "log_whiff", default=-0.3))               # The Log cast with nothing to hit (small waste; 2 elixir, not rocket-scale)
        # The Log's job is DEFENSIVE: clear a ground SWARM / barrel-spawn (Skeleton/Goblin Barrel, Skeleton
        # Army, Goblin Gang) and knock a push BACK once it has crossed to YOUR side, where the princess
        # towers help finish it. Reward the reset/clear only on your side; a big mass wiped = a swarm bonus.
        self.log_defense_y = float(cfg.get("env", "log_defense_y", default=0.46))   # the push has crossed to YOUR side of the river
        self.log_swarm_drop = float(cfg.get("env", "log_swarm_drop", default=0.10)) # this much enemy mass wiped = a swarm / barrel
        self.log_swarm_reward = float(cfg.get("rewards", "log_swarm_reward", default=0.5))
        self.log_air_penalty = float(cfg.get("rewards", "log_air_penalty", default=-0.5))  # Log (ground-only) on AIR units = wasted (needs the detector to SEE air)
        self.spell_king_penalty = float(cfg.get("rewards", "spell_king_penalty", default=-1.5))
        self.tesla_kill = float(cfg.get("rewards", "tesla_kill", default=1.5))
        self.defense_kill = float(cfg.get("rewards", "defense_kill", default=0.5))
        self.defense_kill_cap = float(cfg.get("rewards", "defense_kill_cap", default=1.5))
        # Per-defender kill-credit weight: the Tesla plus a TINY credit for the other defenders.
        # Covers a DIRECT kill (the card attacks the troop) and an INDIRECT one (it blocks/distracts
        # the troop so your tower finishes it off near the card) -- both read as the local red-mass drop.
        # The MINER is included here too (defense_kill weight): played defensively it snipes an enemy
        # support troop or tanks/distracts for your defenders, and either way the enemy it kills/holds
        # dies as a local red-mass drop near its spot -- the same proxy. Its OFFENSIVE tower chip is
        # scored separately by _miner_reward, and the per-placement + per-match anti-farm caps below
        # keep this small (a coarse local-mass proxy; a true support-vs-tank read waits for Stage 3).
        self.defense_kill_ids = {}
        for _i, _key in enumerate(self.vision.deck_keys):
            _base = _key[:-4] if _key.endswith("_evo") else _key
            if _base == "tesla":
                self.defense_kill_ids[_i] = self.tesla_kill
            elif _base in ("ice_wizard", "ice_spirit", "skeletons", "ronin", "miner"):
                self.defense_kill_ids[_i] = self.defense_kill
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
            "back_limit": float(cfg.get("env", "defense_back_limit", default=0.58)),
            "close_defense_y": float(cfg.get("env", "close_defense_y", default=0.58)),
            "close_side_bias": float(cfg.get("env", "defense_close_side_bias", default=0.13)),
            "close_depth": float(cfg.get("env", "defense_close_depth", default=0.03)),
            # buildings keep the capped central spot (their own reward shapes depth); only MOBILE
            # defenders switch to the between-push-and-king body-block when a push breaks in close.
            "building_kinds": {self.defensive_kind[i] for i in self.building_ids if i in self.defensive_kind},
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
        # centre is only the RECOMMENDED default defensive spot (a small reward), never forced
        self.defense_center_bonus = float(cfg.get("rewards", "defense_center_bonus", default=0.15))
        # BAD-PLACEMENT penalties (judged vs the pre-action frame -- where the enemy was when the
        # model chose): defend the wrong (empty) lane, drop a ranged unit on top of a troop, or dump
        # a card in the far back corner (see _placement_penalty).
        self.wrong_lane_penalty = float(cfg.get("rewards", "wrong_lane_penalty", default=-1.5))
        self.wrong_lane_cheap_frac = float(cfg.get("rewards", "wrong_lane_cheap_frac", default=0.3))
        self.ranged_ontop_penalty = float(cfg.get("rewards", "ranged_ontop_penalty", default=-0.75))
        self.rd_enemy_half_penalty = float(cfg.get("rewards", "rd_enemy_half_penalty", default=-0.75))
        self.back_corner_penalty = float(cfg.get("rewards", "back_corner_penalty", default=-0.25))
        self.lane_split_x = 0.48                       # left/right split -- matches reward.threat_side
        self.wrong_lane_margin = float(cfg.get("env", "wrong_lane_margin", default=0.12))
        self.ontop_radius = float(cfg.get("env", "ranged_ontop_radius", default=0.08))
        self.ontop_size = float(cfg.get("env", "ranged_ontop_size", default=0.06))
        self.back_corner_y = float(cfg.get("env", "back_corner_y", default=0.72))
        self.back_corner_x = float(cfg.get("env", "back_corner_x", default=0.20))
        # a push whose deepest troop is at/below this y has reached your towers -> defenders stop
        # kiting and body-block it (the on-top penalty is waived; the recommended cell moves between
        # the push and your king). Above it (push still forward) the kiting rules apply as normal.
        self.close_defense_y = float(cfg.get("env", "close_defense_y", default=0.58))
        # a lone tornado on the enemy princess (chip attempt, not a combo) is wasteful; a reactive
        # card (defender / Royal Delivery) on a QUIET board (nothing to react to) is premature.
        self.tornado_chip_penalty = float(cfg.get("rewards", "tornado_chip_penalty", default=-1.0))
        self.premature_defense_penalty = float(cfg.get("rewards", "premature_defense_penalty", default=-0.5))
        # ...but at/above this elixir a pre-placed defensive card is an elixir-efficient SETUP (a full
        # bar leaks otherwise), not premature -> the premature penalty is waived (judged on the
        # PRE-action bar, since playing the card has already spent elixir by the post-action frame).
        self.defense_setup_elixir = float(cfg.get("env", "defense_setup_elixir", default=9.0))
        # per-match ceiling on the repeatable one-sided shaping bonuses (defense-kill / cycle /
        # foresight counters) so they can't accumulate past a loss -- see _bonus().
        self.shaping_match_cap = float(cfg.get("rewards", "shaping_match_cap", default=8.0))
        self._match_bonus = 0.0
        # BUILDING (Tesla) placement: shape it toward the strategic INTERCEPT zone -- a moderate depth in
        # FRONT of your towers (not shoved to the bridge, not dumped behind them) and toward the CENTRE.
        self.building_front_y = float(cfg.get("env", "building_front_y", default=0.53))
        self.building_back_y = float(cfg.get("env", "building_back_y", default=0.65))
        self.building_center_span = float(cfg.get("env", "building_center_span", default=0.25))
        self.building_center_reward = float(cfg.get("rewards", "building_center_reward", default=0.6))
        self.building_misplace_penalty = float(cfg.get("rewards", "building_misplace_penalty", default=-1.0))
        # Miner X-Bow control deck: X-Bow is the WIN CONDITION (forward, in tower range) with a back-centre
        # defensive mode; Miner chips the enemy tower / tanks anywhere. All positive parts go through _bonus.
        self.xbow_wc_reward = float(cfg.get("rewards", "xbow_wc_reward", default=1.0))
        self.xbow_defense_reward = float(cfg.get("rewards", "xbow_defense_reward", default=0.3))
        self.xbow_misplace_penalty = float(cfg.get("rewards", "xbow_misplace_penalty", default=-0.75))
        self.xbow_exposed_penalty = float(cfg.get("rewards", "xbow_exposed_penalty", default=-1.0))  # X-Bow dropped ON an oncoming push -> demolished before it chips
        self.miner_chip_reward = float(cfg.get("rewards", "miner_chip_reward", default=0.6))
        self.miner_king_penalty = float(cfg.get("rewards", "miner_king_penalty", default=-2.0))
        self.miner_backfield_penalty = float(cfg.get("rewards", "miner_backfield_penalty", default=-0.75))  # Miner dumped behind your own towers with NO push = wasted
        self.own_backfield_y = float(cfg.get("env", "own_backfield_y", default=0.62))  # at/below this depth (behind your princess line) is your backfield
        self.xbow_wrong_lane_frac = float(cfg.get("rewards", "xbow_wrong_lane_frac", default=0.6))  # X-Bow leaving a LIVE push pays this share of wrong_lane_penalty
        self.xbow_range = float(cfg.get("env", "xbow_range", default=0.36))          # ~11.5 tiles, normalized
        self.xbow_defense_y = float(cfg.get("env", "xbow_defense_y", default=0.62))  # a defensive X-Bow sits WITHIN a back-centre band...
        self.xbow_defense_back = float(cfg.get("env", "xbow_defense_back", default=0.70))  # ...no DEEPER than this (past it = shoved onto your king)
        self.xbow_ontop_radius = float(cfg.get("env", "xbow_ontop_radius", default=0.10))  # enemy troops within this of the X-Bow drop = dropped INTO a push -> demolished
        self.xbow_success_frac = float(cfg.get("env", "xbow_success_frac", default=0.30))  # X-Bow 'broke through' if it chipped >= this fraction of a tower by 2x elixir
        self.defensive_rocket_reward = float(cfg.get("rewards", "defensive_rocket_reward", default=0.3))  # once DEFENSIVE, rocket-at-tower is the sanctioned chip
        self.rocket_tower_reward = float(cfg.get("rewards", "rocket_tower_reward", default=1.0))
        self.cycle_reward = float(cfg.get("rewards", "cycle_reward", default=0.15))
        # only reward cycling a cheap card when you have SPARE elixir (near-full) -- below this, rewarding
        # a cheap play just teaches compulsive card SPAM that starves your defence. Above it, cycling is
        # genuinely free (you'd leak otherwise). Neutral (no bonus, no penalty) below the threshold.
        self.cycle_min_elixir = float(cfg.get("env", "cycle_min_elixir", default=7.0))
        # clumped group. Waives the enemy-king penalty (when the rocket hit a princess tower and
        # killed >=2 medium troops) and rewards wiping a push, anywhere on the board.
        self.combo_reward = float(cfg.get("rewards", "rocket_tornado_combo", default=15.0))
        self.combo_window = int(cfg.get("env", "combo_window_steps", default=2))
        self.combo_radius = float(cfg.get("env", "combo_radius", default=0.10))
        self.combo_kill_min = float(cfg.get("env", "combo_kill_min", default=0.06))
        # A rocket is a 6-elixir OFFENSIVE investment: its chip reward is DEFERRED and only paid
        # out if a successful defence follows. If heavy own-tower damage lands within the window
        # after a rocket, the chip is withheld AND an extra penalty applies (a bad investment).
        self.rocket_window = int(cfg.get("env", "rocket_defense_window", default=3))
        self.bad_rocket_penalty = float(cfg.get("rewards", "bad_rocket_penalty", default=-3.0))
        # a rocket "erased a clump" (a valid opposite-lane wipe) if it removed at least this much enemy
        # (red) mass; a rocket is a BAD 6-elixir investment if it neither chipped a tower nor erased a
        # clump AND your towers then lose >= rocket_bad_min_hp within the defence window (couldn't defend).
        self.rocket_clear_min = float(cfg.get("env", "rocket_clear_min", default=0.10))
        self.rocket_bad_min_hp = float(cfg.get("env", "rocket_bad_min_hp", default=700.0))
        self._pending_rocket = None       # deferred rocket chip: {"chip", "steps", "hp0", "destroyed"}
        self._last_spell_chip = False     # did the last spell resolve as a rocket-at-princess chip?
        self._rocket_cleared = False      # did the last rocket erase a real troop clump?
        self._recent_rocket = None
        self._recent_ranged = None
        self._steps = 0
        self.quiet_frac = float(cfg.get("env", "enemy_quiet_frac", default=0.02))
        self.idle_penalty = float(cfg.get("rewards", "idle_penalty", default=-0.3))
        self.threat_mass = float(cfg.get("env", "threat_mass", default=0.10))
        self.elixir_waste_penalty = float(cfg.get("rewards", "elixir_waste_penalty", default=-0.3))
        self.full_elixir = int(cfg.get("env", "elixir_full", default=10))
        # OFFENSE-WHEN-BEHIND: at a FULL bar, if we're behind (a princess down, or our weakest standing
        # tower has less HP than the enemy's) AND the enemy is idle, committing a win-condition / chip
        # card to catch up is correct -> reward it (the idle branch penalises sitting instead).
        self.offense_when_behind = float(cfg.get("rewards", "offense_when_behind", default=0.5))
        self.defeat_min = float(cfg.get("env", "defeat_min", default=0.005))
        self.defeat_cap = float(cfg.get("env", "defeat_cap", default=0.15))
        self.tesla_track_steps = int(cfg.get("env", "tesla_track_steps", default=10))
        self.tesla_radius = float(cfg.get("env", "tesla_radius", default=0.16))
        self._prev_mass = 0.0
        self._prev_my_hp = 0.0
        self._defenders = []          # active defensive-card kill trackers (tesla + ice wizard/spirit/skeletons/ronin)
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
        self.w_take = rw("take_enemy_tower", 0.5); self.w_lose = rw("lose_own_tower", -0.5)
        self.tower_chip_scale = rw("tower_chip_scale", 0.5)   # tiny tower-chip proxy (correctness carries the signal)
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
        self._team_tracker = TeamTracker(                # LIVE: tag your own plays 'mine' (vs the colour guess)
            spawn_radius=float(cfg.get("observation", "team_spawn_radius", default=0.10)),
            spawn_window_s=float(cfg.get("observation", "team_spawn_window_s", default=2.5)),
            enemy_window_s=float(cfg.get("observation", "team_enemy_window_s", default=4.0)),
            track_radius=float(cfg.get("observation", "team_track_radius", default=0.12)))
        self._cycle_tracker = CycleTracker(self.n_cards)   # live estimate of the upcoming-card order (graded next_vec)
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
        self.threat_counter_delivery = float(cfg.get("rewards", "threat_counter_delivery", default=4.0))
        self.threat_tornado_pull = float(cfg.get("rewards", "threat_tornado_pull", default=4.0))
        self.siege_counter = float(cfg.get("rewards", "siege_counter", default=4.0))
        # save the Tesla for the enemy's win condition (a tower-targeting troop): reward using it
        # against an ACTIVE one, penalise spending it early when one is known but not on the board.
        self.wc_tesla_defend = float(cfg.get("rewards", "wc_tesla_defend", default=2.0))
        self.tesla_hold_penalty = float(cfg.get("rewards", "tesla_hold_penalty", default=-1.5))

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
            self.threat_vec = base
            return
        dets = self._detect_enemies(frame)                                   # ONE detector pass this frame
        now = time.time()
        dt = (now - self._prev_ident_t) if self._prev_ident_t else 0.0
        items = [(d.base, (d.gy - 0.5) / 0.5) for d in dets if d.gy >= 0.5]   # identity: YOUR half only
        self._threat_id = card_threat.identity_threat_vector(
            items, self.db, prev_depth=self._prev_ident_depth, dt=dt, horizon=self.predict_horizon)
        self._prev_ident_depth = float(self._threat_id[7])
        self._prev_ident_t = now
        mem = self._opp_mem.update([(d.base, d.gy) for d in dets])           # memory: BOTH halves (incl. staging)
        self.threat_vec = np.concatenate([base, self._threat_id, mem]).astype(np.float32)

    def _detect_enemies(self, frame):
        """ONE detector pass -> whitelisted ENEMY detections (both halves; each has .base + .gy in [0,1]).
        [] if the detector is off/unavailable. Shared by the identity block (your half) and the opponent
        memory (both halves) so live inference runs the detector only ONCE per frame."""
        if self._detector is None:
            return []
        try:
            dets = self._detector.detect(frame, conf=self.detector_conf)
        except Exception:
            return []
        self._team_tracker.tag(dets, time.time())     # correct team from your own plays BEFORE filtering
        return [d for d in dets if d.team == "enemy" and d.base in self.detector_cards]

    # -- episode lifecycle --------------------------------------------
    def reset(self) -> Optional[np.ndarray]:
        """Navigate menus until a match starts; return the first observation."""
        self.tower.reset()
        self.tower_hp.reset()
        self._defensive = False           # icebow phase: False = offensive X-Bow win condition; True = defence + rocket-cycle
        self._enemy_chip_total = 0.0      # cumulative enemy-tower HP chipped (the X-Bow 'did it break through?' gauge)
        self._defenders = []
        self._recent_ranged = None
        self._recent_rocket = None
        self._pending_rocket = None
        self._match_bonus = 0.0
        self._nav.reset_state()
        while True:
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
                self._team_tracker.reset()
                self._cycle_tracker.reset()
                self._read_hand(frame)
                self._update_threat(frame)
                self._last_obs = self.vision.observe(frame)
                self._last_frame = frame
                self._prev_mass = enemy_mass(frame, self.cfg)
                self._prev_my_hp = float(sum(self.tower_hp.my_hp))
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
        if card_id not in self.spell_ids:             # a TROOP you played -> tag its spawn as YOURS (team fix)
            cx, cy = self.actions.cell_center(gx, gy)
            self._team_tracker.record_play(cx, cy, time.time())

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
        tgt = weaker_princess_cell(cx, cy, self.spell_aim_radius, self.tower.enemy_a,
                                   self.tower_hp.enemy_hp, self.tower.enemy_alive,
                                   self.actions)
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
            back_centre = self.xbow_defense_y <= cy <= self.xbow_defense_back and abs(cx - 0.48) <= 0.18
            if self._defensive:
                return self.w_wincon if back_centre else self.w_wincon_mis
            if d <= self.xbow_range:
                return self.w_wincon
            return self.w_wincon * 0.4 if back_centre else self.w_wincon_mis
        if card_id in self.rocket_ids:
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
            cell = self._aim_weaker_tower(card_id, cell)
            cell = self.actions.deploy_clamp(card_id in self.anywhere_ids, cell)  # rocket + miner go anywhere; rest = your half
            if card_id in self.xbow_ids and not self._defensive:  # OFFENSIVE phase only: snap a forward X-Bow onto the nearer lane so it LOCKS
                gx, gy = cell % self.gw, cell // self.gw
                cx, cy = self.actions.cell_center(gx, gy)
                _, enemy_a, _ = _anchors(self.cfg)
                snapped = xbow_lock_cell(cx, cy, enemy_a, self.xbow_range, self.xbow_defense_y, self.actions)
                if snapped is not None:
                    cell = snapped
            action = (play, card_id, cell)
        eval_spell = bool(play) and card_id in self.spell_ids and self.spell_effect
        is_rocket = card_id in self.rocket_ids
        is_rd = card_id in self.royal_delivery_ids
        is_log = card_id in self.log_ids
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
            prev_princess = list(self.tower.mine_alive[:2])
            prev_enemy = list(self.tower.enemy_alive[:2])
            reward = self.tower.step(frame) + self.tower_hp.step(frame)
            # a felled princess -> top its GRADUAL HP penalty up to the full lose_own_tower
            # (covers a tower bursted faster than its HP could be read, or hp_reward off)
            princess_fell = False
            for i in range(len(prev_princess)):
                if prev_princess[i] and not self.tower.mine_alive[i]:
                    reward += self.tower_hp.on_my_tower_destroyed(i)
                    princess_fell = True
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
