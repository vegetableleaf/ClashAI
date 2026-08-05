"""Run the bot live: scripted menu navigation + learned in-match card play.

Navigation (HOME -> queue -> exit -> re-queue) is a scripted state machine
reused from trol, so the bot runs match-to-match unattended. In a match, the
trained CNN policy chooses (slot, placement) on a fixed cadence. After RL
fine-tuning, the same loop plays toward the tower/crown/win rewards.
"""
from __future__ import annotations

import random
import signal
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from .actions import ActionSpace
from .capture import WindowCapture
from .controller import Controller
from .reward import TowerTracker, pump_rocket_cell, weaker_princess_cell, xbow_lock_cell
from .states import GameState
from .threats import ThreatTracker, THREAT_DIM
from . import interactions
from . import card_threat
from .cycle import CycleTracker
from .tower_hp import TowerHpTracker
from .vision import Vision


def _pick_device(cfg):
    import torch
    dev = cfg.get("train", "device", default="cuda")
    if dev != "cuda":
        return dev
    if not torch.cuda.is_available():
        return "cpu"
    try:
        _ = (torch.zeros(1, device="cuda") + 1).item()
        return "cuda"
    except Exception:  # noqa: BLE001
        print("[play] GPU present but this torch build can't run on it; using CPU "
              "(install the cu128 build for your RTX 50-series GPU).")
        return "cpu"


class InMatchGrace:
    """Sticky in-match hold: the OVERTIME failsafe.

    At overtime the game replaces the 'Time left:' label, and if the strict OT banner
    template misses too (scale drift), the state reads UNKNOWN mid-match -- the bot would
    freeze and, after ``play.stuck_timeout``, the nav watchdog would start dismiss-tapping
    near the hand tray. Bridge: an UNKNOWN read within ``grace_s`` of the last positive
    IN_MATCH read is HELD as IN_MATCH. Any OTHER positively identified screen
    (MATCH_END / HOME / PARTY) cancels the anchor, so results screens and menus are never
    grace-held; the hold can only bridge UNKNOWN stretches that FOLLOW a real match read.
    """

    def __init__(self, grace_s: float, log):
        self.grace_s = float(grace_s)
        self._log = log
        self._anchor = None          # time of the last positive IN_MATCH detection
        self._holding = False

    def update(self, state: GameState, now: float) -> GameState:
        if state == GameState.IN_MATCH:
            self._anchor = now
            if self._holding:
                self._holding = False
                self._log("[play] in-match read re-acquired -> grace hold released")
        elif state == GameState.UNKNOWN:
            if self.grace_s > 0 and self._anchor is not None:
                gap = now - self._anchor
                if gap <= self.grace_s:
                    if not self._holding:
                        self._holding = True
                        self._log(f"[play] UNKNOWN {gap:.1f}s after in-match -> grace hold "
                                  f"(label lost: overtime / end animation / dropout; up to "
                                  f"{self.grace_s:.0f}s)")
                    return GameState.IN_MATCH
            if self._holding:
                self._holding = False
                self._log("[play] grace hold expired -> UNKNOWN (nav takes over)")
        else:                        # MATCH_END / HOME / PARTY positively identified
            self._anchor = None
            self._holding = False
        return state


def play(cfg) -> None:
    try:
        import torch
        from .model import PolicyNet
    except ImportError as exc:
        print(f"[play] PyTorch required ({exc}). Install the CUDA build "
              "(see README) then retry.")
        return

    ckpt_path = cfg.path(cfg.get("train", "checkpoint", default="data/policy.pt"))
    rl_path = cfg.path(cfg.get("train", "rl_checkpoint", default="data/policy_rl.pt"))
    if rl_path.exists():
        ckpt_path = rl_path   # prefer the RL-fine-tuned policy when available
    if not ckpt_path.exists():
        print(f"[play] no policy at {ckpt_path}. Train one first with `train-bc`.")
        return

    ckpt = torch.load(ckpt_path, map_location="cpu")
    gw, gh = int(ckpt["grid"][0]), int(ckpt["grid"][1])
    n_cards, n_cells = int(ckpt["n_cards"]), int(ckpt["n_cells"])
    threat_dim = int(ckpt.get("threat_dim", 14))
    device = _pick_device(cfg)
    net = PolicyNet(3, n_cards, n_cells, threat_dim=threat_dim).to(device)
    net.load_state_dict(ckpt["model"])
    net.eval()
    # The RL checkpoint also carries the learned WAIT/PLAY gate head (train-rl's no-op). Load it so
    # play is SYNCED with training: without it, play fired a card every act_period regardless (the
    # old trol behaviour). A BC-only checkpoint has no gate -> play just gates on affordability.
    gate = None
    if "gate" in ckpt:
        gate = torch.nn.Linear(net.embed_dim, 2).to(device)
        gate.load_state_dict(ckpt["gate"])
        gate.eval()
    print(f"[play] policy {ckpt_path.name} loaded ({'RL gate ON' if gate is not None else 'BC, no gate'}).")

    capture = WindowCapture(cfg.get("window", "title_contains", default=None),
                            cfg.get("window", "region", default=None))
    if capture.region is None:
        print("[play] no capture region; set window.region in config.yaml.")
        return
    vision = Vision(cfg)
    actions = ActionSpace(cfg)
    controller = Controller(capture, cfg)
    rocket_ids = {i for i, key in enumerate(vision.deck_keys)
                  if (key[:-4] if key.endswith("_evo") else key) == "rocket"}
    hp_tracker = TowerHpTracker(cfg)          # enemy princess HP, for the rocket redirect
    tower_tracker = TowerTracker(cfg)         # tower alive/destroyed flags
    threat_tracker = ThreatTracker(cfg)       # live enemy-threat vector -> policy input
    from .clock import ElixirClock
    clock = ElixirClock(cfg, vision)          # 2x/3x elixir multiplier (feeds the phase machine)
    aim_radius = float(cfg.get("env", "spell_tower_aim_radius", default=0.12))
    anywhere_ids = {i for i, key in enumerate(vision.deck_keys)
                    if (key[:-4] if key.endswith("_evo") else key) in ("rocket", "miner")}
    xbow_ids = {i for i, key in enumerate(vision.deck_keys)
                if (key[:-4] if key.endswith("_evo") else key) == "x_bow"}
    xbow_range = float(cfg.get("env", "xbow_range", default=0.36))
    xbow_defense_front = float(cfg.get("env", "xbow_defense_front", default=0.52))
    # Cell-head DEPLOYABLE mask: anywhere cards (rocket / miner) -> all cells; every other card only
    # YOUR half. Applied before the cell argmax so play never taps an enemy-half cell that can't
    # deploy (the 'impossible coordinate' that made the bot look inactive).
    yourhalf_mask = torch.tensor(actions.deployable_mask(False), dtype=torch.bool, device=device)
    allcells_mask = torch.ones(n_cells, dtype=torch.bool, device=device)
    yourhalf_cells = [c for c in range(n_cells) if bool(yourhalf_mask[c])]
    # Connect each hand-card identity to its ELIXIR COST from the card DB, so play never taps a card
    # it can't afford (and can track its own spend). Indexed by deck/card id, same as the policy heads.
    from .cards import CardDB
    _db = CardDB(cfg)
    # HARD GUARD: the checkpoint must match the CONFIGURED deck (same check as train-rl). After a
    # deck change an old net's heads are the wrong width and its card ids mean different cards --
    # here that would surface as a torch shape error (10-wide hand one-hots into a 9-card net) or,
    # worse, silent nonsense plays.
    _ckpt_deck = ckpt.get("deck")
    if n_cards != len(vision.deck_keys) or (_ckpt_deck and list(_ckpt_deck) != list(vision.deck_keys)):
        print(f"[play] checkpoint/deck MISMATCH -- {ckpt_path.name} was trained for:")
        print(f"[play]   ckpt deck ({n_cards}): {', '.join(map(str, _ckpt_deck or ['?'] * n_cards))}")
        print(f"[play]   config deck ({len(vision.deck_keys)}): {', '.join(vision.deck_keys)}")
        print("[play] train a fresh sim policy for this deck (run.py train-sim), or restore the old")
        print("[play] deck in config/cards.yaml to keep using this checkpoint.")
        return
    card_elixir = [(_db.elixir(k) or _db.elixir(k[:-4] if k.endswith("_evo") else k) or 0)
                   for k in vision.deck_keys]

    # Stage 3: when the checkpoint was trained WITH the identity block (threat_dim > THREAT_DIM),
    # append card_threat's identity features for the RECOGNISED, HIGH-confidence enemy cards the
    # detector names on your half. Gated on the checkpoint width so play always matches the net.
    extra_dim = threat_dim - THREAT_DIM
    want_identity = extra_dim in (card_threat.IDENTITY_DIM + card_threat.OPP_MEMORY_DIM,
                                  card_threat.IDENTITY_DIM + card_threat.OPP_MEMORY_DIM
                                  + interactions.INTERACTION_DIM)
    want_memory = want_identity
    want_interactions = extra_dim in (interactions.INTERACTION_DIM,
                                      card_threat.IDENTITY_DIM + card_threat.OPP_MEMORY_DIM
                                      + interactions.INTERACTION_DIM)
    detector_conf = float(cfg.get("observation", "detector_conf", default=0.75))
    detector_cards = set(cfg.get("observation", "detector_cards", default=[]))
    predict_horizon = float(cfg.get("observation", "predict_horizon_s", default=1.0))
    sight_range = float(cfg.get("sim", "sight_range", default=0.12))
    _detector = None
    if want_identity or want_interactions:
        try:
            from .replay_mine import load_detector
            _det = load_detector(cfg)
            _detector = _det if _det.available else None
        except Exception:
            _detector = None
    _ident_state = {"depth": 0.0, "t": None}   # deepest-threat depth + time, for the approach velocity
    _opp_mem = card_threat.OpponentMemory(_db)  # per-match opponent short-term memory (Stage 3)
    # LIVE team verdicts by evidence fusion (own plays / motion / HP bars / side prior with pocket gating)
    # so your units aren't read as enemy threats -- see replay_mine.TeamTracker.
    from .replay_mine import TeamTracker
    _team_tracker = TeamTracker(
        spawn_radius=float(cfg.get("observation", "team_spawn_radius", default=0.10)),
        spawn_window_s=float(cfg.get("observation", "team_spawn_window_s", default=2.5)),
        enemy_window_s=float(cfg.get("observation", "team_enemy_window_s", default=4.0)),
        track_radius=float(cfg.get("observation", "team_track_radius", default=0.12)),
        forget_s=float(cfg.get("observation", "team_forget_s", default=4.5)),
        motion_min=float(cfg.get("observation", "team_motion_min", default=0.05)),
        deep_mine_y=float(cfg.get("observation", "team_deep_mine_y", default=0.62)),
        deep_enemy_y=float(cfg.get("observation", "team_deep_enemy_y", default=0.38)))
    _cycle_tracker = CycleTracker(n_cards)   # live estimate of the upcoming-card order (graded next_vec)
    # PUMP PUNISH (elixir collector -> rocket): sighting state + king-safe aim assist (mirrors env.py)
    _rocket_ids = {i for i, k in enumerate(vision.deck_keys) if card_threat.base_key(k) == "rocket"}
    _pump = {"t0": None, "last": 0.0, "xy": None}
    _pump_window = float(cfg.get("env", "pump_rocket_window_s", default=12.0))
    _pump_aim_radius = float(cfg.get("env", "pump_aim_radius", default=0.10))
    _pump_pair_gap = float(cfg.get("env", "pump_pair_gap", default=0.11))
    _pump_king_guard = float(cfg.get("env", "pump_king_guard", default=0.15))

    def _threat_extra(frame):
        """The obs blocks appended AFTER the base threat vector when the checkpoint was trained with them,
        sized to the net: the identity block (RECOGNISED enemies on YOUR half) + the opponent MEMORY block
        (whole-match read, BOTH halves). ONE detector pass shared by both. Zeros where unavailable."""
        dets_all = []
        if _detector is not None:
            try:
                dets_all = _detector.detect(frame, conf=detector_conf)
            except Exception:
                dets_all = []
            # a fallen princess opens the deploy POCKET in front of it -> void the side prior for that lane
            _team_tracker.set_towers(tower_tracker.mine_alive, tower_tracker.enemy_alive)
            _team_tracker.tag(dets_all, time.time())     # evidence-fused team (plays/motion/bars/pockets)
            now_p = time.time()                          # pump sighting -> the punish window (see env.py)
            pumps = [d for d in dets_all if d.base == "elixir_collector" and d.team != "mine" and d.gy < 0.5]
            if pumps:
                if _pump["t0"] is None:
                    _pump["t0"] = now_p
                _pump["last"] = now_p
                _pump["xy"] = (pumps[0].cx, pumps[0].gy)
            elif _pump["t0"] is not None and now_p - _pump["last"] > 6.0:
                _pump["t0"] = None
                _pump["xy"] = None
        dets = [d for d in dets_all if d.team == "enemy" and d.base in detector_cards]
        items = [(d.base, (d.gy - 0.5) / 0.5) for d in dets if d.gy >= 0.5]   # identity: YOUR half only
        now = time.time()
        dt = (now - _ident_state["t"]) if _ident_state["t"] else 0.0
        ident = card_threat.identity_threat_vector(items, _db, prev_depth=_ident_state["depth"],
                                                    dt=dt, horizon=predict_horizon)
        _ident_state["depth"] = float(ident[7]); _ident_state["t"] = now
        mem = _opp_mem.update([(d.base, d.gy) for d in dets])                 # memory: BOTH halves (incl. staging)
        blocks = []
        if want_identity:
            blocks.append(ident)
        if want_memory:
            blocks.append(mem)
        if want_interactions:                          # predicted tower pressure from ALL tagged detections
            my_t = [(ax, ay, bool(tower_tracker.mine_alive[i]))
                    for i, (ax, ay) in enumerate(tower_tracker.mine_a[:3])]
            en_t = [(ax, ay, bool(tower_tracker.enemy_alive[i]))
                    for i, (ax, ay) in enumerate(tower_tracker.enemy_a[:3])]
            units = [("mine" if d.team == "mine" else "enemy", d.base, d.cx, d.gy)
                     for d in dets_all if d.team in ("mine", "enemy") and d.base in detector_cards]
            blocks.append(interactions.interaction_vector(units, my_t, en_t, _db))
        return np.concatenate(blocks).astype(np.float32) if blocks else np.zeros(0, np.float32)

    eps = float(cfg.get("play", "epsilon", default=0.0))
    act_period = float(cfg.get("play", "act_period", default=1.5))
    poll_dt = 1.0 / float(cfg.get("nav", "poll_hz", default=6))
    menu_delay = float(cfg.get("nav", "menu_delay", default=1.0))
    battle = cfg.get("buttons", "battle_button", default=[0.5, 0.9])
    quick = cfg.get("buttons", "quick_match", default=[0.5, 0.55])
    results_ok = cfg.get("buttons", "results_ok", default=[0.5, 0.9])
    results_dc = cfg.get("buttons", "results_ok_dc", default=results_ok)
    play_again = cfg.get("buttons", "play_again", default=results_ok)
    _home = cfg.get("states", "home_menu", default={}) or {}
    home_tpl, home_thr = _home.get("template", "home_menu.png"), float(_home.get("threshold", 0.8))

    def act_in_match(frame) -> None:
        hp_tracker.step(frame)                # keep enemy princess HP + alive flags current
        tower_tracker.step(frame)
        obs = vision.observe(frame)
        hand_ids = vision.recognize_hand(frame)
        hand_vec = vision.hand_multihot(hand_ids)
        if hand_vec.sum() == 0:               # no card recognized -> can't act this tick
            return
        next_vec = _cycle_tracker.observe(hand_ids, vision.recognize_next(frame))
        elixir = vision.read_elixir(frame)
        threat_vec = threat_tracker.update(frame, time.time()).vector()
        if want_identity or want_interactions:
            threat_vec = np.concatenate([threat_vec, _threat_extra(frame)]).astype(np.float32)
        x = torch.from_numpy(obs).float().permute(2, 0, 1).unsqueeze(0).to(device) / 255.0
        hv = torch.from_numpy(hand_vec).unsqueeze(0).to(device)
        nv = torch.from_numpy(next_vec).unsqueeze(0).to(device)
        ev = torch.tensor([[elixir / 10.0]], dtype=torch.float32, device=device)
        tv = torch.from_numpy(threat_vec).unsqueeze(0).float().to(device)
        with torch.no_grad():
            z = net.features_vec(x, hv, nv, ev, tv)
            card_logits, cell_logits = net.card_head(z), net.cell_head(z)
            gate_logits = gate(z) if gate is not None else None
        card_logits = card_logits.masked_fill(hv < 0.5, float("-inf"))   # only cards in hand
        # ELIXIR: mask out any card you can't currently AFFORD (cost from the card DB). This is the
        # hand-card -> elixir-cost tracking: play never taps an unaffordable card (the old fixed
        # 1.5s cadence tapped regardless, which just wasted the tap).
        for i in range(n_cards):
            if elixir + 1e-6 < card_elixir[i]:
                card_logits[0, i] = float("-inf")
        # Tesla is deliberately NOT masked: the policy DECIDES when to play vs HOLD it, exactly as in
        # training (no forced choice). It observes 'a win condition is on the board now' (identity block)
        # and 'the enemy has shown a win condition this match' (opponent-memory block), and the correctness
        # reward teaches the tradeoff -- wasting Tesla on a non-wincon earns a threat_miss when the win
        # condition later arrives with no answer in hand. So it can still play Tesla when that's the best
        # current defence (or when the opponent has no win condition at all).
        if bool(torch.isinf(card_logits).all()):
            return                              # nothing in hand is affordable / allowed -> wait
        if random.random() < eps:
            choices = [i for i in range(n_cards) if not bool(torch.isinf(card_logits[0, i]))]
            card_id = random.choice(choices)
            cells = list(range(n_cells)) if card_id in anywhere_ids else (yourhalf_cells or list(range(n_cells)))
            cell = random.choice(cells)
        else:
            card_id = int(card_logits.argmax(1).item())
            cmask = allcells_mask if card_id in anywhere_ids else yourhalf_mask   # DEPLOYABLE cells for this card
            cell_logits_m = cell_logits.masked_fill(~cmask.unsqueeze(0), float("-inf"))
            # GATE (synced with train-rl): value of PLAYING = Q_play + best card + best DEPLOYABLE cell;
            # value of WAITING = Q_wait. If the policy prefers to wait, do nothing this tick (save elixir /
            # cycle) instead of firing every act_period like the old trol bot.
            if gate_logits is not None:
                play_val = gate_logits[0, 1] + card_logits.max() + cell_logits_m.max()
                if gate_logits[0, 0] >= play_val:
                    return
            cell = int(cell_logits_m.argmax(1).item())
        if card_id in anywhere_ids:           # a rocket / offensive miner at a princess -> aim the weaker one
            gx, gy = cell % gw, cell // gw
            cx, cy = actions.cell_center(gx, gy)
            tgt = None
            # PUMP PUNISH aim assist: a rocket already aimed near a FRESH enemy pump is snapped to the
            # king-safe optimum (midpoint with an adjacent princess when one blast covers both).
            if (card_id in _rocket_ids and _pump["t0"] is not None and _pump["xy"] is not None
                    and time.time() - _pump["t0"] <= _pump_window
                    and np.hypot(cx - _pump["xy"][0], cy - _pump["xy"][1]) <= _pump_aim_radius * 1.5):
                tgt = pump_rocket_cell(_pump["xy"][0], _pump["xy"][1], tower_tracker.enemy_a,
                                       tower_tracker.enemy_alive, _pump_pair_gap, _pump_king_guard, actions)
            if tgt is None:
                tgt = weaker_princess_cell(cx, cy, aim_radius, tower_tracker.enemy_a,
                                           hp_tracker.enemy_hp, tower_tracker.enemy_alive, actions)
            if tgt is not None:
                cell = tgt
        # Defensive units (Tesla / Ice Wizard / Ronin) are NO LONGER forced to the centre: the
        # model chooses where to place them (centre is only a rewarded default in training), so it
        # can block a lane or drop a Ronin up front to catch a ranged unit when that's better.
        slot = next((s for s, c in enumerate(hand_ids) if c == card_id), -1)
        if slot < 0:
            return
        cell = actions.deploy_clamp(card_id in anywhere_ids, cell)   # only rocket/miner go anywhere
        if card_id in xbow_ids:               # snap a forward X-Bow onto the nearer lane so it LOCKS the tower
            gx, gy = cell % gw, cell // gw
            cx, cy = actions.cell_center(gx, gy)
            snapped = xbow_lock_cell(cx, cy, tower_tracker.enemy_a, xbow_range, xbow_defense_front, actions)
            if snapped is not None:
                cell = snapped
        gx, gy = cell % gw, cell // gw
        controller.play_card(*actions.decode(slot, gx, gy))
        _cycle_tracker.record_play(card_id)        # a card left the hand -> it rotates to the queue back
        # ANY play (troop or spell) anchors its own detection 'mine' -- base-matched, so your rolling Log
        # is claimed at the cast point while an enemy answer dropped on the same spot is not.
        cx, cy = actions.cell_center(gx, gy)
        _team_tracker.record_play(cx, cy, time.time(),
                                  base=card_threat.base_key(vision.deck_keys[card_id]))

    running = {"v": True}
    signal.signal(signal.SIGINT, lambda *_a: running.update(v=False))

    log_path = Path(cfg.path("data")) / f"play_{datetime.now():%Y%m%d_%H%M%S}.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    def log(msg: str) -> None:
        line = f"{datetime.now():%H:%M:%S} {msg}"
        print(line)
        try:
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError:
            pass

    log(f"[play] running on {device}. Ctrl+C to stop, or slam the mouse into a screen corner "
        "for the failsafe. It navigates menus and plays in-match on its own.")
    log(f"[play] logging to {log_path}")

    from .nav import MenuNavigator
    nav = MenuNavigator(cfg, controller, vision, label="play", log=log)
    grace = InMatchGrace(float(cfg.get("play", "in_match_grace_s", default=150)), log)
    prev = None
    last_act = 0.0
    prev_mult = 1
    while running["v"]:
        try:
            frame = capture.grab()
            if frame is None:
                capture.refresh_region()
                time.sleep(0.3)
                continue
            state = grace.update(vision.detect_state(frame), time.time())
            if state != prev:
                log(f"[play] state: {state.name}")
                if state == GameState.IN_MATCH:   # new match -> reset the tower trackers
                    hp_tracker.reset()
                    tower_tracker.reset()
                    threat_tracker.reset()
                    clock.reset()                 # zero the 2x/3x elixir clock at match start
                    _opp_mem.reset()              # forget the previous opponent's deck/archetype
                    _team_tracker.reset()         # forget last match's own-unit tracks
                    _cycle_tracker.reset()        # forget last match's cycle order
                    prev_mult = 1
                prev = state

            if state == GameState.IN_MATCH:
                nav.reset_state()             # not on a menu -> clear the nav stuck timers
                m = clock.update(frame)       # 2x/3x elixir clock (time + optional badge)
                if m != prev_mult:
                    log(f"[play] elixir x{m}")
                    prev_mult = m
                now = time.time()
                if now - last_act >= act_period:
                    act_in_match(frame)
                    last_act = now
                time.sleep(poll_dt)
            else:
                nav.handle(frame, state)      # HOME / MATCH_END / UNKNOWN: located buttons + escalation + watchdog
        except KeyboardInterrupt:
            break
        except Exception as exc:  # noqa: BLE001 -- log + keep navigating instead of dying silently
            import traceback
            log(f"[play] ERROR in loop: {exc!r}")
            log(traceback.format_exc())
            if type(exc).__name__ == "FailSafeException":
                log("[play] pyautogui failsafe triggered -> stopping")
                break
            time.sleep(poll_dt)

    log("[play] stopped.")
