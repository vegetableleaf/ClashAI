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
from .reward import TowerTracker, weaker_princess_cell, xbow_lock_cell
from .states import GameState
from .threats import ThreatTracker, THREAT_DIM
from . import card_threat
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
    tesla_ids = {i for i, key in enumerate(vision.deck_keys)
                 if (key[:-4] if key.endswith("_evo") else key) == "tesla"}
    xbow_ids = {i for i, key in enumerate(vision.deck_keys)
                if (key[:-4] if key.endswith("_evo") else key) == "x_bow"}
    xbow_range = float(cfg.get("env", "xbow_range", default=0.36))
    xbow_defense_y = float(cfg.get("env", "xbow_defense_y", default=0.62))
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
    card_elixir = [(_db.elixir(k) or _db.elixir(k[:-4] if k.endswith("_evo") else k) or 0)
                   for k in vision.deck_keys]

    # Stage 3: when the checkpoint was trained WITH the identity block (threat_dim > THREAT_DIM),
    # append card_threat's identity features for the RECOGNISED, HIGH-confidence enemy cards the
    # detector names on your half. Gated on the checkpoint width so play always matches the net.
    want_identity = threat_dim > THREAT_DIM
    detector_conf = float(cfg.get("observation", "detector_conf", default=0.75))
    detector_cards = set(cfg.get("observation", "detector_cards", default=[]))
    predict_horizon = float(cfg.get("observation", "predict_horizon_s", default=1.0))
    _detector = None
    if want_identity:
        try:
            from .replay_mine import load_detector
            _det = load_detector(cfg)
            _detector = _det if _det.available else None
        except Exception:
            _detector = None
    _ident_state = {"depth": 0.0, "t": None}   # deepest-threat depth + time, for the approach velocity

    def _identity_block(frame):
        """KB identity + MOTION block for RECOGNISED (whitelisted, >= detector_conf) enemy units on
        your half (approach velocity + predicted post-deploy depth via cross-frame depth tracking)."""
        if _detector is None:
            return np.zeros(card_threat.IDENTITY_DIM, np.float32)
        try:
            dets = _detector.detect(frame, conf=detector_conf)
        except Exception:
            return np.zeros(card_threat.IDENTITY_DIM, np.float32)
        items = [(d.base, (d.gy - 0.5) / 0.5) for d in dets           # d.gy = shadow-corrected ground y
                 if d.team == "enemy" and d.gy >= 0.5 and d.base in detector_cards]
        now = time.time()
        dt = (now - _ident_state["t"]) if _ident_state["t"] else 0.0
        vec = card_threat.identity_threat_vector(items, _db, prev_depth=_ident_state["depth"],
                                                 dt=dt, horizon=predict_horizon)
        _ident_state["depth"] = float(vec[7]); _ident_state["t"] = now
        return vec

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
        next_vec = vision.next_onehot(vision.recognize_next(frame))
        elixir = vision.read_elixir(frame)
        threat_vec = threat_tracker.update(frame, time.time()).vector()
        if want_identity:
            threat_vec = np.concatenate([threat_vec, _identity_block(frame)]).astype(np.float32)
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
        # SAVE THE TESLA for a win condition: enemy runs a tower-targeting troop and none is on the
        # board now -> mask Tesla so it defends win conditions only.
        hold_tesla = threat_tracker.should_hold_tesla()
        if hold_tesla:
            for i in tesla_ids:
                card_logits[0, i] = float("-inf")
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
        if card_id in rocket_ids:             # a rocket at a princess -> aim the weaker one
            gx, gy = cell % gw, cell // gw
            cx, cy = actions.cell_center(gx, gy)
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
        cell = actions.deploy_clamp(card_id in anywhere_ids, cell)   # only rocket/tornado go anywhere
        if card_id in xbow_ids:               # snap a forward X-Bow onto the nearer lane so it LOCKS the tower
            gx, gy = cell % gw, cell // gw
            cx, cy = actions.cell_center(gx, gy)
            snapped = xbow_lock_cell(cx, cy, tower_tracker.enemy_a, xbow_range, xbow_defense_y, actions)
            if snapped is not None:
                cell = snapped
        gx, gy = cell % gw, cell // gw
        controller.play_card(*actions.decode(slot, gx, gy))

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
            state = vision.detect_state(frame)
            if state != prev:
                log(f"[play] state: {state.name}")
                if state == GameState.IN_MATCH:   # new match -> reset the tower trackers
                    hp_tracker.reset()
                    tower_tracker.reset()
                    threat_tracker.reset()
                    clock.reset()                 # zero the 2x/3x elixir clock at match start
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
