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

from .actions import ActionSpace
from .capture import WindowCapture
from .controller import Controller
from .reward import TowerTracker, weaker_princess_cell
from .states import GameState
from .threats import ThreatTracker
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
    aim_radius = float(cfg.get("env", "spell_tower_aim_radius", default=0.12))
    anywhere_ids = {i for i, key in enumerate(vision.deck_keys)
                    if (key[:-4] if key.endswith("_evo") else key) in ("rocket", "tornado")}
    tesla_ids = {i for i, key in enumerate(vision.deck_keys)
                 if (key[:-4] if key.endswith("_evo") else key) == "tesla"}

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
        x = torch.from_numpy(obs).float().permute(2, 0, 1).unsqueeze(0).to(device) / 255.0
        hv = torch.from_numpy(hand_vec).unsqueeze(0).to(device)
        nv = torch.from_numpy(next_vec).unsqueeze(0).to(device)
        ev = torch.tensor([[elixir / 10.0]], dtype=torch.float32, device=device)
        tv = torch.from_numpy(threat_vec).unsqueeze(0).float().to(device)
        with torch.no_grad():
            card_logits, cell_logits = net(x, hv, nv, ev, tv)
        card_logits = card_logits.masked_fill(hv < 0.5, float("-inf"))   # only cards in hand
        # SAVE THE TESLA for a win condition: if the enemy runs a tower-targeting troop and none
        # is on the board right now, don't let the model spend Tesla -- mask it out so it defends
        # win conditions only. Tesla plays normally once one is active, or if the enemy has none.
        hold_tesla = threat_tracker.should_hold_tesla()
        if hold_tesla:
            for i in tesla_ids:
                card_logits[0, i] = float("-inf")
        if random.random() < eps:
            choices = [c for c in hand_ids if c >= 0 and not (hold_tesla and c in tesla_ids)]
            if not choices:
                return                          # only a held Tesla in hand -> wait, save it
            card_id = random.choice(choices)
            cell = random.randrange(n_cells)
        else:
            if bool(torch.isinf(card_logits).all()):
                return                          # only a held Tesla in hand -> wait, save it
            card_id = int(card_logits.argmax(1).item())
            cell = int(cell_logits.argmax(1).item())
        if card_id in rocket_ids:             # a rocket at a princess -> aim the weaker one
            gx, gy = cell % gw, cell // gw
            cx, cy = actions.cell_center(gx, gy)
            tgt = weaker_princess_cell(cx, cy, aim_radius, tower_tracker.enemy_a,
                                       hp_tracker.enemy_hp, tower_tracker.enemy_alive, gw, gh)
            if tgt is not None:
                cell = tgt
        # Defensive units (Tesla / Ice Wizard / Ronin) are NO LONGER forced to the centre: the
        # model chooses where to place them (centre is only a rewarded default in training), so it
        # can block a lane or drop a Ronin up front to catch a ranged unit when that's better.
        slot = next((s for s, c in enumerate(hand_ids) if c == card_id), -1)
        if slot < 0:
            return
        cell = actions.deploy_clamp(card_id in anywhere_ids, cell)   # only rocket/tornado go anywhere
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

    prev = None
    last_act = 0.0
    stuck_since = None
    stuck_timeout = float(cfg.get("play", "stuck_timeout", default=25.0))
    stuck_tap = cfg.get("play", "stuck_tap", default=results_ok)
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
                prev = state

            if state == GameState.HOME:
                stuck_since = None
                located = vision.locate(frame, home_tpl, home_thr)
                tgt = located or battle
                log(f"[play] HOME -> tap {'home_tpl' if located else 'battle'} "
                    f"({tgt[0]:.3f},{tgt[1]:.3f})")
                controller.tap(*tgt)
                time.sleep(menu_delay)
            elif state == GameState.MATCH_END:
                stuck_since = None
                log(f"[play] MATCH_END -> tap play_again ({play_again[0]:.3f},{play_again[1]:.3f})")
                controller.tap(*play_again)   # 1v1: re-queue immediately (loop continues)
                time.sleep(menu_delay)
            elif state == GameState.IN_MATCH:
                stuck_since = None
                now = time.time()
                if now - last_act >= act_period:
                    act_in_match(frame)
                    last_act = now
                time.sleep(poll_dt)
            else:  # UNKNOWN / QUEUING: normally just wait -- BUT if we sit on an unrecognised screen
                   # too long it's a post-match popup (chest / level-up / season pass / shop offer) the
                   # state templates don't cover; tap to dismiss it (also cancels a hung search so the
                   # loop re-queues from HOME) instead of hanging here forever.
                now = time.time()
                if stuck_since is None:
                    stuck_since = now
                elif now - stuck_since >= stuck_timeout:
                    log(f"[play] stuck on {state.name} ~{stuck_timeout:.0f}s -> "
                        f"tap dismiss ({stuck_tap[0]:.3f},{stuck_tap[1]:.3f})")
                    controller.tap(*stuck_tap)
                    stuck_since = now          # re-arm: keep tapping until a known screen
                    time.sleep(menu_delay)
                else:
                    time.sleep(poll_dt)
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
