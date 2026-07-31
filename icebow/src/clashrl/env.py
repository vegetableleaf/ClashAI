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
        """Recognize the hand -> deck ids per slot + multi-hot (for identity actions),
        and the next (preview) card -> one-hot (so the policy can plan cycles)."""
        self.hand_ids = self.vision.recognize_hand(frame)
        self.hand_vec = self.vision.hand_multihot(self.hand_ids)
        self.next_id = self.vision.recognize_next(frame)
        self.next_vec = self.vision.next_onehot(self.next_id)

    def _update_threat(self, frame) -> None:
        """Advance the live enemy-threat read from the current frame -> policy input vector."""
        self._last_threat = self.threat_tracker.update(frame, time.time())
        self.threat_vec = self._last_threat.vector()

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
                self._read_hand(frame)
                self.threat_tracker.reset()
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

    def _recommended_defense_cell(self, card_id: int):
        """The RECOMMENDED central defensive spot for a defensive card given the current threat
        -- a suggestion the reward gently nudges toward, NOT a hard override. The model is free to
        place elsewhere (block a lane, drop a Ronin up front to catch a ranged unit off guard) and
        the troop-defeat / Tesla-kill rewards will favour that when it is the better play. Returns
        a grid cell, or None when the card isn't a defender or there's no clear threat to react to."""
        kind = self.defensive_kind.get(card_id)
        if kind is None or self._last_frame is None:
            return None
        if kind == "musketeer_evo":
            return defensive_cell(kind, 0, 0.0, self.gw, self.gh, self.defense_params)
        side = threat_side(self._last_frame, self.cfg, self.threat_min_frac)
        if side == 0:
            return None
        front = threat_front(self._last_frame, side, self.cfg, self.threat_min_frac)
        if front is None:
            return None
        return defensive_cell(kind, side, front, self.gw, self.gh, self.defense_params)

    def _defense_placement_reward(self, card_id: int, cell: int) -> float:
        """Small bonus for placing a defender at (or next to) the RECOMMENDED central spot -- a
        soft DEFAULT, not a mandate. Placing elsewhere isn't penalised here; a better lane block
        or forward play earns more through the troop-defeat + Tesla-kill rewards instead, so the
        model can deviate from the centre whenever that's the stronger move."""
        rec = self._recommended_defense_cell(card_id)
        if rec is None:
            return 0.0
        gx, gy = cell % self.gw, cell // self.gw
        rx, ry = rec % self.gw, rec // self.gw
        if abs(gx - rx) <= 1 and abs(gy - ry) <= 1:      # within a cell of the recommended centre
            return self.defense_center_bonus
        return 0.0

    def _building_place_reward(self, card_id: int, cell: int, threatened: bool) -> float:
        """Shape a BUILDING (Tesla) toward the strategic defensive zone: a MODERATE depth in FRONT of
        your towers (not shoved to the bridge, not dumped behind them) and toward the CENTRE, where
        both princess towers support it and it pulls ground troops to the middle. A Tesla at the
        bridge gets bypassed / focused; one behind your towers can't reach the push in time -- both
        are penalised. The central reward only counts when there's actually a push to defend (a
        premature building on a quiet board is handled by the premature-defense penalty)."""
        if card_id not in self.building_ids:
            return 0.0
        gx, gy = cell % self.gw, cell // self.gw
        cx, cy = self.actions.cell_center(gx, gy)
        if cy < self.building_front_y or cy > self.building_back_y:
            return self.building_misplace_penalty            # at the bridge (too forward) OR behind your towers (too deep)
        if not threatened:
            return 0.0                                       # in-band but nothing to defend yet
        central = max(0.0, 1.0 - abs(cx - 0.48) / self.building_center_span)
        return self.building_center_reward * central          # in-band + a real push -> reward central x

    def _xbow_place_reward(self, cell: int) -> float:
        """Shape the X-Bow, the deck's WIN CONDITION. It reaches ~11.5 tiles, so from just behind the
        bridge (on YOUR side) it can lock the enemy PRINCESS tower -- the offensive play. Reward placing
        it WITHIN firing range (env.xbow_range) of the nearer enemy princess (a real forward win
        condition); give a SMALLER reward for a BACK-CENTRE defensive X-Bow within a depth BAND (the
        rocket-cycle fallback, sniping troops when the offensive X-Bow can't break through -- but NOT
        shoved onto your king, too far back to do anything); and PENALISE any other out-of-range drop
        (forward but short of the tower, or king-hugging) -- wasted / exposed (the classic misplace).
        HARD EXCEPTION (checked FIRST): an X-Bow dropped right ON an oncoming enemy push gets swarmed
        and demolished before it lands a shot -- 6 elixir wasted and undefendable -- so that is
        penalised regardless of how good the spot would otherwise be."""
        gx, gy = cell % self.gw, cell // self.gw
        cx, cy = self.actions.cell_center(gx, gy)
        frame = self._last_frame                              # where the push was when the model decided
        if frame is not None and troop_size_at(frame, cx, cy, self.xbow_ontop_radius, self.cfg) >= self.ontop_size:
            return self.xbow_exposed_penalty                  # dropped INTO a live push -> demolished with no tower chip
        _, enemy_a, _ = _anchors(self.cfg)
        princesses = enemy_a[:2] if len(enemy_a) >= 2 else enemy_a
        d = min((math.hypot(cx - ax, cy - ay) for ax, ay in princesses), default=1.0)
        back_centre = self.xbow_defense_y <= cy <= self.xbow_defense_back and abs(cx - 0.48) <= 0.18
        if self._defensive:                                   # DEFENSIVE phase: the offensive WC is abandoned --
            return self.xbow_defense_reward if back_centre else self.xbow_misplace_penalty  # only the back-centre snipe is right
        if d <= self.xbow_range:
            return self.xbow_wc_reward                        # OFFENSIVE: in range of a tower -> a real win condition
        if back_centre:
            return self.xbow_defense_reward                   # back-centre BAND -> defensive snipe (rocket-cycle mode)
        return self.xbow_misplace_penalty                     # out of range: too forward to chip OR shoved onto your king

    def _miner_reward(self, cell: int) -> float:
        """Miner deploys ANYWHERE; its bread-and-butter is chipping the enemy PRINCESS tower, so reward
        dropping it on/near a princess. The enemy KING is the EXCEPTION -- a Miner on the king tower
        wakes it early (activates their defence for the rest of the match), so that is penalised.
        Dumping it deep behind YOUR OWN towers with no push to defend is wasted elixir (the model's
        'safe' idle habit) -> penalised too; a Miner defending a real push there (troop present) is
        exempt, and its defensive snipe/tank value is still credited by troop_defeat + defense-kill.
        (Phase 2: sniping a support card behind an enemy tank.)"""
        gx, gy = cell % self.gw, cell // self.gw
        cx, cy = self.actions.cell_center(gx, gy)
        if near_enemy_king(cx, cy, self.cfg, self.spell_aim_radius):
            return self.miner_king_penalty          # Miner on the enemy KING wakes it early -> bad trade
        if near_enemy_princess(cx, cy, self.cfg, self.spell_aim_radius):
            return self.miner_chip_reward           # chip the enemy princess -- its bread-and-butter
        frame = self._last_frame
        if (cy >= self.own_backfield_y and frame is not None
                and troop_size_at(frame, cx, cy, self.ontop_radius, self.cfg) < self.ontop_size):
            return self.miner_backfield_penalty      # dumped behind your own towers with NO push to defend = wasted
        return 0.0

    def _placement_penalty(self, play: bool, card_id: int, cell: int, raw_cell: int) -> float:
        """Punish clearly BAD placements, judged against the pre-action frame (where the enemy was
        when the model decided):
          * WRONG LANE (hard): ANY card committed to the lane OPPOSITE the enemy push -- wasted
            elixir and an undefended push. Cheap cyclers (Ice Spirit / Skeletons) pay only a
            wrong_lane_cheap_frac SHARE (dropping them anywhere to cycle is forgivable). A ROCKET is
            EXEMPT when it chips/finishes the opposite enemy PRINCESS tower OR erases a big troop
            clump there (a split-lane push wipe) -- both are real strategic plays. (A rocket that
            does NEITHER, then leaves you unable to defend, is caught by the elixir-investment
            bad-rocket penalty instead.)
          * ROYAL DELIVERY ON THE ENEMY HALF: Royal Delivery can only be cast on YOUR half; the
            deploy clamp silently pulls an enemy-half attempt back, so penalise the ATTEMPT (the raw
            pre-clamp cell) to teach the model to stop aiming it over there.
          * RANGED ON TOP (moderate): a ranged unit (Ice Wizard) dropped right on top of an enemy
            troop instead of a kiting distance behind it -- it gets run down before it shoots. EXCEPT
            once the push has reached your towers (cy >= close_defense_y): then body-blocking it
            directly is the correct last-ditch defence, so the on-top penalty is waived.
          * BACK CORNER (slight): any NON-cheap card dumped in the far back corner (deep AND against an
            edge). Cheap cyclers (The Log / Skeletons) are EXEMPT -- the back corner is exactly
            where you park them to cycle when they aren't needed for an immediate defence.
        """
        if not play:
            return 0.0
        gx, gy = cell % self.gw, cell // self.gw
        cx, cy = self.actions.cell_center(gx, gy)
        r = 0.0
        if (card_id not in self.cheap_ids and cy >= self.back_corner_y
                and (cx <= self.back_corner_x or cx >= 1.0 - self.back_corner_x)):
            r += self.back_corner_penalty            # far-back corner DUMP -- cheap cyclers exempt (the corner IS the cycle spot)
        if card_id in self.royal_delivery_ids:                   # RD can ONLY be cast on your half
            rcy = self.actions.cell_center(raw_cell % self.gw, raw_cell // self.gw)[1]
            if rcy < self.offensive_half:
                r += self.rd_enemy_half_penalty                  # penalise the ATTEMPT (pre-clamp)
        frame = self._last_frame
        if frame is None:
            return r
        if card_id in self.ranged_ids and cy < self.close_defense_y:  # RANGED unit dropped ON a troop, but only
            if troop_size_at(frame, cx, cy, self.ontop_radius, self.cfg) >= self.ontop_size:  # while the push is still
                r += self.ranged_ontop_penalty                        # forward (room to kite); waived once it's in close
        side = threat_side(frame, self.cfg, self.threat_min_frac)   # WRONG LANE
        off = cx - self.lane_split_x
        opposite = side != 0 and abs(off) > self.wrong_lane_margin and (off < 0) == (side > 0)
        if opposite and card_id not in self.miner_ids:               # Miner deploys ANYWHERE -> never wrong-lane
            if card_id in self.xbow_ids:
                # An opposite-lane X-Bow is the deck's PUNISH of an over-committed / FAILED push -- fine once
                # the push is spent. But if a REAL push is still LIVE, siting the X-Bow away from it leaves it
                # undefendable -> a REDUCED penalty (the X-Bow still applies counter-pressure of its own).
                if enemy_mass(frame, self.cfg) >= self.threat_mass:
                    r += self.wrong_lane_penalty * self.xbow_wrong_lane_frac
            else:
                rocket_ok = card_id in self.rocket_ids and (         # a rocket in the opposite lane is VALID when it
                    near_enemy_princess(cx, cy, self.cfg, self.spell_aim_radius)   # chips/finishes that tower, OR
                    or self._rocket_cleared)                         # erased a big clump there (split-lane push wipe)
                if not rocket_ok:
                    scale = self.wrong_lane_cheap_frac if card_id in self.cheap_ids else 1.0
                    r += self.wrong_lane_penalty * scale             # committed to the lane OPPOSITE the push
        return r

    def _bonus(self, credit: float) -> float:
        """Cap the CUMULATIVE positive shaping bonus (defense-kill / cycle / foresight counters) per
        match at shaping_match_cap so these repeatable one-sided rewards can't sum past a loss.
        Penalties (<=0) pass through untouched."""
        if credit <= 0.0:
            return credit
        allowed = min(credit, max(0.0, self.shaping_match_cap - self._match_bonus))
        self._match_bonus += allowed
        return allowed

    def _defense_kill_reward(self, frame, play: bool, card_id: int, cell: int) -> float:
        """Reward a placed DEFENSIVE card (Tesla / Ice Wizard / Skeletons / Miner played defensively) by
        the enemy troops that die near it over its life -- a DIRECT kill (the card attacks the troop)
        or an INDIRECT one (it blocks/distracts the troop long enough that your princess tower
        finishes it off near the card). Both show up as the local enemy (red) mass dropping around
        the card's spot, so one proxy credits either. Tracked per placement for tesla_track_steps
        steps and capped at defense_kill_cap, so a single card -- e.g. a Tesla catching a whole
        Skeletons group -- can't farm enough to flip a lost match net-positive. A dead card stops
        killing, so its credit naturally ends; if the troop instead reaches and damages your tower,
        the (separate) gradual own-tower penalty fires, so the NET only rewards a kill that actually
        SAVED the tower. Placement stays the model's (no forced spot); the blue placement tint doesn't
        pollute the red enemy-mass read. (Post-Stage-3: swap the mass proxy for real per-unit damage
        from the detector.)"""
        r = 0.0
        alive = []
        for d in self._defenders:
            cur = enemy_mass_at(frame, d["cx"], d["cy"], self.tesla_radius, self.cfg)
            drop = d["prev"] - cur
            if drop > self.defeat_min and d["earned"] < self.defense_kill_cap:
                credit = min(min(drop, self.defeat_cap) * d["weight"],
                             self.defense_kill_cap - d["earned"])   # per-placement anti-farm cap
                r += credit
                d["earned"] += credit
            d["prev"] = cur
            d["steps"] -= 1
            if d["steps"] > 0:
                alive.append(d)
        self._defenders = alive
        if play and card_id in self.defense_kill_ids:   # start tracking a freshly placed defender
            gx, gy = cell % self.gw, cell // self.gw
            tx, ty = self.actions.cell_center(gx, gy)
            self._defenders.append({
                "cx": tx, "cy": ty, "steps": self.tesla_track_steps,
                "weight": self.defense_kill_ids[card_id], "earned": 0.0,
                "prev": enemy_mass_at(frame, tx, ty, self.tesla_radius, self.cfg)})
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

    def _threat_counter_reward(self, play: bool, card_id: int, cell: int) -> float:
        """Foresight counters keyed off the enemy-threat read at action-selection time:
        * Royal Delivery dropped ON a landing goblin (green) swarm, or onto the tower a
          projectile (e.g. a thrown Goblin Barrel) is arcing toward -> threat_counter_delivery.
        * Tornado near YOUR king while a goblin swarm is present -> threat_tornado_pull
          (pull the goblins onto the king to tank + kill them as they land).
        These teach the small-foresight plays the CNN can't read off the tiny arena image."""
        if not play:
            return 0.0
        thr = self._last_threat
        gx, gy = cell % self.gw, cell // self.gw
        cx, cy = self.actions.cell_center(gx, gy)
        goblins = thr.color_label() == "green" and thr.size_label() in ("swarm", "single_big")
        r = 0.0
        if card_id in self.royal_delivery_ids:
            on_threat = (thr.centroid is not None
                         and abs(cx - thr.centroid[0]) <= self.spell_radius
                         and abs(cy - thr.centroid[1]) <= self.spell_radius)
            proj = thr.proj
            proj_at_my_tower = (proj is not None and proj.toward_tower
                                and str(proj.target or "").startswith("M"))
            if (goblins and on_threat) or proj_at_my_tower:
                r += self.threat_counter_delivery
        if card_id in self.tornado_ids and goblins and near_my_king(cx, cy, self.cfg):
            r += self.threat_tornado_pull
        # counter a SITTING behind-bridge siege (X-Bow / Mortar / Princess chipping your
        # towers from the enemy side): land a spell on it -- the rocket is the only card that
        # reaches across the river, so this teaches "rocket the siege".
        if thr.siege and card_id in self.spell_ids and thr.behind_centroid is not None:
            bx, by = thr.behind_centroid
            if abs(cx - bx) <= self.spell_radius and abs(cy - by) <= self.spell_radius:
                r += self.siege_counter
        return r

    def _resolve_pending_rocket(self, my_hp: float, princess_fell: bool) -> float:
        """Resolve a DEFERRED rocket-chip investment. The chip is paid out only once the AI
        survives the defence window WITHOUT your towers taking more damage than the rocket dealt
        the enemy tower; if your towers lose MORE HP than the rocket removed (or a princess
        falls) within the window, the chip is WITHHELD and an extra penalty applies (a bad
        elixir trade -- you lost more than you gained)."""
        p = self._pending_rocket
        if p is None:
            return 0.0
        if princess_fell:
            p["destroyed"] = True
        own_hp = max(0.0, p["hp0"] - my_hp)                    # HP your towers lost since the rocket
        rocket_hp = p["rocket_frac"] * self.tower_hp.full     # HP the rocket took off the enemy tower
        # BAD investment: a tower fell, OR your towers lost MORE than the rocket dealt AND that loss is
        # HEAVY (>= rocket_bad_min_hp) -- you spent 6 elixir on the rocket and then couldn't defend.
        if p["destroyed"] or own_hp > max(rocket_hp, self.rocket_bad_min_hp):
            self._pending_rocket = None
            return self.bad_rocket_penalty                    # chip withheld + extra penalty
        p["steps"] -= 1
        if p["steps"] <= 0:
            self._pending_rocket = None
            return p["chip"]                                 # survived the window as a good trade -> chip earned
        return 0.0

    def step(self, action: Action):
        play, card_id, cell = action
        raw_cell = cell                           # the model's ATTEMPTED cell, before aim + deploy-clamp
        if play:                                  # rocket -> aim the weaker enemy princess tower
            cell = self._aim_rocket(card_id, cell)
            cell = self.actions.deploy_clamp(card_id in self.anywhere_ids, cell)  # rocket + miner go anywhere; rest = your half
            if card_id in self.xbow_ids and not self._defensive:  # OFFENSIVE phase only: snap a forward X-Bow onto the nearer lane so it LOCKS
                gx, gy = cell % self.gw, cell // self.gw
                cx, cy = self.actions.cell_center(gx, gy)
                _, enemy_a, _ = _anchors(self.cfg)
                snapped = xbow_lock_cell(cx, cy, enemy_a, self.xbow_range, self.xbow_defense_y, self.gw, self.gh)
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
            full_bar = cur_elixir >= self.full_elixir          # post-action bar (used by the not-play branch)
            pre_full = pre_elixir >= self.full_elixir          # pre-action bar (used by the play offense reward)
            my_alive_n = sum(1 for a in self.tower.mine_alive[:2] if a)
            en_alive_n = sum(1 for a in self.tower.enemy_alive[:2] if a)
            my_hps = [h for h, a in zip(self.tower_hp.my_hp, self.tower.mine_alive[:2]) if a]
            en_hps = [h for h, a in zip(self.tower_hp.enemy_hp, self.tower.enemy_alive[:2]) if a]
            behind = (my_alive_n < en_alive_n) or bool(my_hps and en_hps and min(my_hps) < min(en_hps))
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
            # The Log chip-cycle is only justified as a LAST RESORT: Skeletons not in hand (no cheaper
            # cycle), the board quiet (nothing to Log defensively), AND a near-full bar (won't starve a
            # defence). self._prev_mass = enemy mass on the PRE-action frame; elixir read pre-action too.
            log_cycle_ok = False
            if is_log and self._prev_mass < self.quiet_frac and not any(c in self.skeletons_ids for c in self.hand_ids):
                log_cycle_ok = pre_elixir >= self.defense_setup_elixir
            spell_r = 0.0
            if eval_spell and before is not None and spell_samples:
                spell_r = self._spell_effect_reward(before, spell_samples, cell, is_rocket, is_rd, is_log, log_cycle_ok)
                reward += spell_r
            else:
                # POTENTIAL-BASED troop shaping: reward the SIGNED change in on-board enemy
                # mass (mass falling = troops cleared -> +; mass rising = a push building -> -).
                # Because it is symmetric it telescopes over a match, so idling CANNOT farm it:
                # the old rectified `max(0, drop)` paid out every down-swing of the noisy
                # enemy-mass signal but never charged the matching up-swings, so a hesitant agent
                # banked a large positive sum from enemy troops naturally ebbing / dying at the
                # towers -- even while being three-crowned (the bulk of the bogus "+reward for
                # losing"). Clipped both ways for artifact robustness.
                delta = self._prev_mass - cur_mass
                if abs(delta) > self.defeat_min:
                    reward += float(np.clip(delta, -self.defeat_cap, self.defeat_cap)) * self.troop_defeat
                if not play:
                    if cur_mass >= self.threat_mass:
                        reward += self.idle_penalty      # a real push is on the board and you did nothing -> defend
                        if full_bar:
                            reward += self.elixir_waste_penalty  # full bar + a push, still nothing = wasted elixir
                    elif cur_mass >= self.quiet_frac:
                        # the enemy has COMMITTED a card (units on the board). At a full bar, sitting there
                        # both leaks elixir AND ignores the developing threat -> penalise. (Was the reported
                        # gap: the penalty only fired at threat_mass, so a full bar vs a small/medium push
                        # was free -- "does nothing at a full bar when the enemy played a card".)
                        if full_bar:
                            reward += self.idle_penalty + self.elixir_waste_penalty
                    elif full_bar and behind:
                        # QUIET board but we're BEHIND with a full bar -> we must ATTACK to catch up; sitting
                        # on a full bar is wrong here (the play-side offense reward pays the alternative).
                        reward += self.idle_penalty + self.elixir_waste_penalty
                    else:
                        reward += self.patience          # quiet board, nothing forcing a play -> saving elixir is fine
            reward += self._bonus(self._defense_kill_reward(frame, bool(play), card_id, cell))
            if play and card_id in self.tesla_ids:
                # keep the Tesla for the enemy's win condition (a tower-targeting troop)
                if self.threat_tracker.wc_active:
                    reward += self._bonus(self.wc_tesla_defend)   # defend an ACTIVE win condition -- good (capped: can't farm)
                elif self.threat_tracker.should_hold_tesla():
                    reward += self.tesla_hold_penalty  # spent early with none on the board -- save it
            if play and card_id in self.building_ids:  # Tesla -> intercept-zone placement (central, moderate depth)
                reward += self._bonus(self._building_place_reward(card_id, cell, cur_mass >= self.quiet_frac))
            if play and card_id in self.xbow_ids:      # X-Bow -> forward win condition (in tower range) vs back-centre defence
                reward += self._bonus(self._xbow_place_reward(cell))
            if play and card_id in self.rocket_ids and self._defensive:  # DEFENSIVE: rocket-cycle IS the sanctioned tower damage
                gx, gy = cell % self.gw, cell // self.gw
                cx, cy = self.actions.cell_center(gx, gy)
                if near_enemy_princess(cx, cy, self.cfg, self.spell_aim_radius):
                    reward += self._bonus(self.defensive_rocket_reward)
            if play and card_id in self.miner_ids:     # Miner -> chip the enemy princess (deployed anywhere)
                reward += self._bonus(self._miner_reward(cell))
            # OFFENSE WHEN BEHIND: full bar (pre-action) + we're behind (towers/damage) + the enemy was
            # idle at decision time -> committing a win-condition / chip card (X-Bow, Miner, Rocket) to
            # rack up damage is the right call. Capped via _bonus so it can't farm.
            if (play and pre_full and behind and self._prev_mass < self.quiet_frac
                    and card_id in (self.xbow_ids | self.miner_ids | self.rocket_ids)):
                reward += self._bonus(self.offense_when_behind)
            if play and card_id in self.defensive_kind:
                reward += self._bonus(self._defense_placement_reward(card_id, cell))  # soft nudge to the recommended centre (capped)
            reward += self._bonus(self._blocker_reward(frame, bool(play), card_id, cell))  # shield a ranged unit (capped)
            if (play and card_id not in self.rocket_ids and card_id not in self.cheap_ids
                    and card_id not in self.miner_ids and card_id not in self.xbow_ids):
                if self.actions.cell_center(cell % self.gw, cell // self.gw)[1] < self.offensive_half:
                    reward += self.offensive_penalty  # non-rocket/miner/xbow card in the enemy half = offence
            reward += self._placement_penalty(bool(play), card_id, cell, raw_cell)  # wrong-lane / on-top / corner / RD-half
            if play and card_id in self.reactive_ids and cur_mass < self.quiet_frac:
                if pre_elixir < self.defense_setup_elixir:      # at/near a FULL bar, a defensive SETUP avoids leaking -> allowed
                    reward += self.premature_defense_penalty   # else a defender / Royal Delivery on a QUIET board = premature
            if (play and card_id in self.cheap_ids and pre_elixir >= self.cycle_min_elixir
                    and not any(c in self.rocket_ids for c in self.hand_ids)):
                reward += self._bonus(self.cycle_reward)   # cheap card + SPARE elixir + rocket not in hand -> cycling to it (not spam)
            reward += self._bonus(self._threat_counter_reward(bool(play), card_id, cell))   # foresight counters
            # rocket = a 6-elixir OFFENSIVE investment: resolve any prior rocket (pay its chip
            # only after a successful defence; withhold it + penalise if heavy own-tower damage
            # followed), then defer THIS rocket's chip if it was a tower chip.
            if self._pending_rocket is not None and self.tower_hp.last_enemy_chip > 0.0:
                # the rocket's own HP chip confirms a frame or two after impact -> fold it into
                # the deferred amount + its measured tower damage so both wait on a good defence.
                reward -= self.tower_hp.last_enemy_chip
                self._pending_rocket["chip"] += self.tower_hp.last_enemy_chip
                self._pending_rocket["rocket_frac"] += self.tower_hp.last_enemy_frac
            reward += self._resolve_pending_rocket(my_hp, princess_fell)
            if is_rocket and play and eval_spell:
                if self._pending_rocket is not None:     # a new rocket supersedes an unresolved one -> pay it (it survived)
                    reward += self._pending_rocket["chip"]
                    self._pending_rocket = None
                if self._last_spell_chip:                 # rocket-at-tower CHIP -> withhold until a good defence
                    chip = max(0.0, spell_r) + max(0.0, self.tower_hp.last_enemy_chip)
                    if chip > 0.0:
                        reward -= chip                    # withhold the chip until a successful defence follows
                        self._pending_rocket = {"chip": chip, "steps": self.rocket_window, "hp0": my_hp,
                                                "rocket_frac": self.tower_hp.last_enemy_frac, "destroyed": False}
                elif not self._rocket_cleared:            # neither chipped a tower NOR erased a clump = a wasted
                    self._pending_rocket = {"chip": 0.0, "steps": self.rocket_window, "hp0": my_hp,  # 6-elixir bet
                                            "rocket_frac": 0.0, "destroyed": False}                  # -> bad if punished
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

    def _log_reward(self, cx, cy, present, drop, size_frame, cycle_ok) -> float:
        """The Log -- a cheap 2-elixir ROLLING, ground-only knockback/reset spell with poor tower chip.
        Its job is DEFENSIVE: clear a ground SWARM / barrel-spawn (Skeleton or Goblin Barrel, Skeleton
        Army, Goblin Gang) and KNOCK the push BACK once it has crossed to YOUR side of the river, where
        the princess towers help finish it off. So the reset/clear is only rewarded when the Log lands on
        YOUR side onto a real push; a big mass wiped earns a swarm/barrel counter bonus. A Log with
        nothing to hit is a small whiff (2 elixir, not rocket-scale) unless it's a justified last-resort
        cycle. An enemy-side / pre-crossing Log (offensive chip -- weak) is neutral, not the wanted use."""
        if present and cy >= self.log_defense_y:      # a push on YOUR side -> knock it back toward the river
            size = min(troop_size_at(size_frame, cx, cy, self.spell_radius, self.cfg), self.spell_size_cap)
            r = self.log_reset_reward                 # knockback/reset buys the towers + defenders time
            if drop >= self.spell_min_drop:
                r += size * self.spell_hit            # troops actually cleared
                if drop >= self.log_swarm_drop:
                    r += self.log_swarm_reward        # a big swarm / barrel-spawn wiped = the Log's premium use
            return r
        if present:                                   # a push, but enemy-side / not yet crossed -> not the defensive Log
            return 0.0
        return 0.0 if cycle_ok else self.log_whiff    # nothing to hit: a waste, unless a justified cycle-chip

    def _spell_effect_reward(self, before, samples, cell, is_rocket: bool, is_rd: bool = False,
                             is_log: bool = False, log_cycle_ok: bool = False) -> float:
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
        self._last_spell_chip = False             # set True only if this resolves as a rocket-at-princess chip
        self._rocket_cleared = False              # set True if this rocket erases a real troop clump
        b = enemy_mass_at(before, cx, cy, self.spell_radius, self.cfg)
        masses = [enemy_mass_at(f, cx, cy, self.spell_radius, self.cfg) for f in samples]
        if not masses:
            if is_rocket:
                self._recent_rocket = None
            return 0.0
        peak_i = int(np.argmax(masses))
        if is_rocket or is_rd:
            # A rocket / Royal Delivery makes its OWN fiery impact, which the red mask reads as
            # "enemy mass" -- so the peak DURING the window is the fireball, not troops, and its
            # fade to the last sample looks like a kill. Measure instead the enemy mass present
            # just BEFORE impact (the cast frame + the pre-impact sample) and how much of it was
            # removed. This stops an EMPTY-ground rocket scoring its own explosion as a kill (the
            # model was farming that by rocketing a safe spot on its own side).
            pre = max(b, masses[0]) if len(masses) >= 3 else b
            peak = pre
            drop = max(0.0, pre - masses[-1])
            size_frame = samples[0] if len(samples) >= 3 else before
        else:
            peak = masses[peak_i]
            drop = peak - masses[-1]
            size_frame = samples[peak_i]
        present = peak >= self.spell_present
        if is_rocket:
            self._rocket_cleared = drop >= self.rocket_clear_min   # removed a real clump, not just a graze
        if is_log:                                    # THE LOG: cheap ROLLING knockback/reset -- its own shaping
            return self._log_reward(cx, cy, present, drop, size_frame, log_cycle_ok)

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
            if not present:                           # landed on empty ground -> a whiff (random Royal Delivery)
                return self.spell_whiff
            cap = self.spell_size_cap * 2.0
            return min(peak, cap) * self.rd_hit + min(max(0.0, drop), cap) * self.rd_kill
        if (is_tornado and present and near_my_king(cx, cy, self.cfg, self.spell_aim_radius)
                and all(self.tower.mine_alive[:2])):
            frac = self._my_king_hp_frac(samples[-1])
            if frac is not None:                      # tornado that PULLS a real push onto YOUR king: tank it,
                return self.king_tank_reward * frac   # worth less as the king's own HP falls
        if near_enemy_princess(cx, cy, self.cfg, self.spell_aim_radius):
            if is_rocket:
                self._last_spell_chip = True              # a rocket-at-tower CHIP -> its reward is deferred
                r = self.rocket_tower_reward              # launching a rocket at the enemy princess tower
                if drop >= self.spell_min_drop or peak >= self.spell_combo_present:
                    r += self.spell_combo                 # ...that also caught troops
                return r
            if is_tornado:                                # a LONE tornado on a tower (a valid combo returned earlier)
                return self.tornado_chip_penalty          # tornado is NOT a chip tool -> penalise
            return 0.0                                    # chip -> tower_hp handles it
        # scale by the size of the biggest unit caught (swarm -> small, fat unit -> large)
        size = min(troop_size_at(size_frame, cx, cy, self.spell_radius, self.cfg),
                   self.spell_size_cap)
        # Reward ONLY a real mass DROP (troops actually removed). "present" alone was farmable: a
        # spell aimed at a static enemy structure or the reddish enemy-side floor reads red and used
        # to pay size*spell_hit for nothing -- the top-left-corner rocket loophole. A rocket that
        # removes nothing = a wasted 6 elixir -> whiff.
        if drop >= self.spell_min_drop:
            return size * (self.spell_troop_damage if is_rocket else self.spell_hit)
        if is_rocket:
            return self.spell_whiff
        return self.spell_whiff if b < self.spell_present else 0.0

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
