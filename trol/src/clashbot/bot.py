"""The main bot loop: queue -> emote -> spell-cycle -> emote -> exit -> repeat."""
from __future__ import annotations

import random
import signal
import time

from .states import GameState


class ClashBot:
    def __init__(self, capture, vision, controller, learner, cfg):
        self.capture = capture
        self.vision = vision
        self.controller = controller
        self.learner = learner
        self.cfg = cfg

        self.running = True
        self.prev_state = GameState.UNKNOWN
        self.match_emoted = False   # sent "Good game!" at match start?
        self.end_emoted = False     # sent "Good game!" at match end?
        self.loop_dt = 1.0 / float(cfg.get("timing", "loop_hz", default=10))

    # ------------------------------------------------------------------
    def stop(self, *_args) -> None:
        self.running = False

    def run(self) -> None:
        signal.signal(signal.SIGINT, self.stop)
        print("[bot] running. Ctrl+C to stop, or slam the mouse into a screen "
              "corner for PyAutoGUI's emergency failsafe.")
        while self.running:
            frame = self.capture.grab()
            if frame is None:
                self.capture.refresh_region()
                time.sleep(0.5)
                continue
            state, _score = self.vision.detect_state(frame)
            if state != self.prev_state:
                print(f"[bot] state: {state.name}")
            self._handle(state, frame)
            self.prev_state = state
            time.sleep(self.loop_dt)
        print("[bot] stopped.")

    # ------------------------------------------------------------------
    def _handle(self, state: GameState, frame) -> None:
        if state == GameState.HOME:
            self._on_home()
        elif state == GameState.PARTY:
            self._on_party()
        elif state == GameState.IN_MATCH:
            self._on_match(frame)
        elif state == GameState.MATCH_END:
            self._on_match_end(frame)
        else:
            # UNKNOWN / QUEUING: try to dismiss a known popup, else keep polling.
            self._on_unknown(frame)

    def _await_state(self, target: GameState, timeout: float) -> bool:
        t0 = time.time()
        while self.running and time.time() - t0 < timeout:
            frame = self.capture.grab()
            if frame is not None:
                s, _ = self.vision.detect_state(frame)
                if s == target:
                    return True
            time.sleep(self.loop_dt)
        return False

    # ------------------------------------------------------------------
    def _on_home(self) -> None:
        """From the home page, open the 2v2 party menu (game keeps 2v2 selected)."""
        arm, delay = self.learner.choose("home_to_party")
        self.controller.tap(*self.cfg.get("buttons", "battle_button", default=[0.5, 0.9]))
        time.sleep(delay)
        reached = self._await_state(
            GameState.PARTY, timeout=self.cfg.get("timing", "menu_timeout", default=8)
        )
        self.learner.update("home_to_party", arm, reached, delay)

    def _on_party(self) -> None:
        """From the 2v2 party menu, start a quick match and wait for the battle."""
        arm, delay = self.learner.choose("party_to_queue")
        self.controller.tap(*self.cfg.get("buttons", "quick_match", default=[0.5, 0.55]))
        time.sleep(delay)
        started = self._await_state(
            GameState.IN_MATCH, timeout=self.cfg.get("timing", "queue_timeout", default=25)
        )
        self.learner.update("party_to_queue", arm, started, delay)
        if started:
            self.match_emoted = False
            self.end_emoted = False

    def _on_match(self, frame) -> None:
        if not self.match_emoted:
            self.controller.emote_good_game()
            self.match_emoted = True
        self._spell_cycle(frame)

    def _spell_cycle(self, frame) -> None:
        """Play every affordable spell in hand onto the spell target, in random slot order."""
        slots = self.cfg.get("hand", "slots", default=[])
        if not slots:
            return
        elixir = self.vision.read_elixir(frame)
        hand = self.vision.identify_hand(frame)

        plays = []
        for i, info in enumerate(hand):
            if info is not None:
                _name, cost = info
                plays.append((i, cost))
        if not plays:
            # Fallback (no card templates): try each slot when elixir is high.
            costs = [c["cost"] for c in self.cfg.get("deck", "cards", default=[{"cost": 2}])]
            min_cost = min(costs) if costs else 2
            if elixir >= min_cost:
                plays = [(i, min_cost) for i in range(len(slots))]

        random.shuffle(plays)  # random slot order so play isn't biased toward the leftmost card
        remaining = elixir
        cooldown = self.cfg.get("timing", "spell_replay_cooldown", default=0.25)
        for slot_i, cost in plays:
            if cost > remaining or slot_i >= len(slots):
                continue
            tnx, tny = self.vision.tower_target()
            snx, sny = slots[slot_i]
            self.controller.play_card(snx, sny, tnx, tny)
            remaining -= cost
            time.sleep(cooldown)

    def _on_match_end(self, frame) -> None:
        if not self.end_emoted:
            self.controller.emote_good_game()
            self.end_emoted = True
            # Give the "Good game!" emote a moment to actually send before exiting.
            time.sleep(self.cfg.get("emote", "send_delay", default=0.6))

        # The 2v2 results screen differs by whether the teammate stayed:
        #   match_end    (teammate online)      -> "Exit" button (results_ok)
        #   match_end_dc (teammate disconnected) -> "OK" button   (results_ok_dc)
        # Detect which is showing and tap its matching button.
        end_spec = self.cfg.get("states", "match_end", default={}) or {}
        threshold = end_spec.get("threshold", 0.8)
        templates = end_spec.get("templates") or [end_spec.get("template")]
        dc_template = next((t for t in templates if t and "_dc" in t), None)
        if dc_template and self.vision.find(frame, dc_template, threshold).found:
            button = self.cfg.get("buttons", "results_ok_dc", default=[0.49, 0.87])
        else:
            button = self.cfg.get("buttons", "results_ok", default=[0.5, 0.9])

        arm, delay = self.learner.choose("results_to_home")
        self.controller.tap(*button)
        time.sleep(delay)
        back = self._await_state(
            GameState.HOME, timeout=self.cfg.get("timing", "exit_timeout", default=15)
        )
        self.learner.update("results_to_home", arm, back, delay)

    # ------------------------------------------------------------------
    def _on_unknown(self, frame) -> None:
        """On an unrecognized screen, dismiss a known popup if one is showing.

        Handles reward / level-up / announcement / reconnect dialogs that would
        otherwise leave the bot stuck. Populate `recovery.popups` in the config
        (capture each with `capture-template <name>`). If nothing matches, the
        loop just keeps polling — no timeout, no auto-stop.
        """
        if not self.cfg.get("recovery", "enabled", default=True):
            return
        for popup in self.cfg.get("recovery", "popups", default=[]) or []:
            tmpl = popup.get("template")
            thr = popup.get("threshold", 0.8)
            if tmpl and self.vision.find(frame, tmpl, thr).found:
                print(f"[bot] recovery: dismissing popup {tmpl!r}")
                self.controller.tap(*popup.get("dismiss", [0.5, 0.9]))
                time.sleep(0.5)
                return
