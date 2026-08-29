"""RL fine-tune (DQN) of the behaviour-cloned policy on live matches.

Starts from the imitation policy and improves it toward the reward: take enemy
towers, defend your own (per-step shaping) and, above all, **win** (the terminal
win/loss reward read off the results scoreboard). This is on-policy-ish live
learning -- one real match at a time -- so expect it to be slow; it is a
framework to keep improving a decent BC start, not a from-scratch trainer.

Network: the BC `PolicyNet` reused as a factored Q-function -- the slot and cell
heads are Q-values over hand slots and placement cells -- plus a small **gate**
head that learns a no-op (wait / save elixir). The value of a state is

    V(s) = max( Q_gate(wait),  Q_gate(play) + max_slot Q_slot + max_cell Q_cell )

so a placement's value factors additively across the two heads. The gate starts
fresh; the rest is initialised from the BC checkpoint, so RL fine-tunes it.
"""
from __future__ import annotations

import random
import signal
import time

from . import threat_value
from .llm_advisor import HOLD as _HOLD
from .replay_mine import SPAWN_SPELLS
from collections import deque
from pathlib import Path

import numpy as np


# A SWALLOWED EXCEPTION MUST NOT READ AS WORKING (I9). The threat gate below calls
# `enemy_tracks(..., with_base=True)` and catches TypeError, so a tracker whose signature loses
# `with_base` does not fail -- the gate simply stops triaging REMEMBERED enemies and keeps
# returning an answer. That is precisely how the hogeq PerceptionLoop passthrough was recorded as
# "silently inert" for weeks. The catch stays (a perception hiccup must never break training), but
# it now says so once, and it counts, so a test can prove the path is cold.
_MEMORY_GATE_INERT = 0


def _memory_gate_inert(tracker) -> None:
    """One loud line the first time the gate's memory half goes dark, then a counter."""
    global _MEMORY_GATE_INERT
    _MEMORY_GATE_INERT += 1
    if _MEMORY_GATE_INERT == 1:
        print("[train-rl]   WARNING: %s.enemy_tracks() rejected with_base=True -- the threat "
              "gate's REMEMBERED-enemy half is inert for the rest of this run, and it will "
              "still return an answer. See tests/test_perception_with_base_i9.py."
              % type(tracker).__name__, flush=True)


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
        print("[train-rl] GPU present but this torch build can't run on it; using CPU "
              "(install the cu128 build for your RTX 50-series GPU).")
        return "cpu"


def _build_net(cfg, device, n_cards, n_cells, threat_dim=14, in_ch=3):
    import torch.nn as nn
    from .model import PolicyNet

    class DQN(nn.Module):
        def __init__(self):
            super().__init__()
            self.policy = PolicyNet(in_ch, n_cards, n_cells, threat_dim=threat_dim)
            self.gate = nn.Linear(self.policy.embed_dim, 2)  # [wait, play]

        def forward(self, x, hand, nxt=None, elx=None, thr=None):
            z, cards, cells = self.policy.forward_parts(x, hand, nxt, elx, thr)
            return cards, cells, self.gate(z)

    return DQN().to(device)


def train_rl(cfg, init: str | None = None) -> None:
    try:
        import torch
        import torch.nn.functional as F
    except ImportError as exc:  # noqa: BLE001
        print(f"[train-rl] PyTorch required ({exc}). Install the CUDA build (see README).")
        return

    from .env import LiveMatchEnv

    bc_path = cfg.path(cfg.get("train", "checkpoint", default="data/policy.pt"))
    rl_path = cfg.path(cfg.get("train", "rl_checkpoint", default="data/policy_rl.pt"))
    if init:                                            # explicit warm-start (e.g. the 34-dim SIM policy)
        init_path = cfg.path(init)
        if not init_path.exists():
            print(f"[train-rl] --init checkpoint not found: {init_path}")
            return
    else:
        init_path = rl_path if rl_path.exists() else bc_path
    if not init_path.exists():
        print(f"[train-rl] no policy to start from ({bc_path}). Run `train-bc` first.")
        return
    if rl_path.exists():
        # Live RL OVERWRITES policy_rl.pt every save_every matches with NO keep-best gate (there is no
        # cheap live benchmark to gate on) -- and play.py auto-prefers policy_rl.pt. Bank the current
        # one so a degraded fine-tune can always be rolled back.
        prev = rl_path.with_name(rl_path.stem + "_prev" + rl_path.suffix)
        import shutil
        shutil.copy2(rl_path, prev)
        print(f"[train-rl] backed up {rl_path.name} -> {prev.name} (rollback point; play.py prefers "
              f"policy_rl.pt, so restore the backup if this session makes things worse)")

    device = _pick_device(cfg)
    ckpt = torch.load(init_path, map_location="cpu")
    gw, gh = int(ckpt["grid"][0]), int(ckpt["grid"][1])
    n_cards, n_cells = int(ckpt["n_cards"]), int(ckpt["n_cells"])
    threat_dim = int(ckpt.get("threat_dim", 14))
    # Image-branch width: 3 (RGB) or 3 + detect_obs's semantic canvas. Read from the CONFIG, not the
    # checkpoint, because LiveMatchEnv builds its observation from the same gate -- a checkpoint from
    # before the flip simply will not load here, which is the intended loud failure (flipping the
    # canvas is a fresh-train event, exactly like widening threat_dim).
    from .detect_obs import obs_in_channels
    in_ch = obs_in_channels(cfg)
    deck = ckpt.get("deck")

    # Per-card elixir cost (by deck identity) so the policy can't select a card it can't PAY for --
    # an unaffordable pick just wastes the turn on a "Not enough Elixir!" no-op. Mirrors play.py's
    # live affordability mask; card_elixir all-zero (unknown deck) makes the mask a harmless no-op.
    from .cards import CardDB
    _db = CardDB(cfg)
    _tower_level = int(cfg.get("env", "my_tower_level", default=15) or 15)

    def _base_key(k):
        k = str(k)
        return k[:-4] if k.endswith("_evo") else k

    # HARD GUARD: the checkpoint must match the CONFIGURED deck. After a deck change (e.g. the
    # icebow switch: 9 -> 10 identities, miner -> knight/knight_evo) an old net's hand/card heads
    # are the wrong WIDTH and its card ids mean different cards -- without this check that
    # surfaces as a cryptic IndexError (card_elixir[i]) mid-match.
    current_deck = _db.deck_identities()
    if n_cards != len(current_deck) or (deck and list(deck) != list(current_deck)):
        print(f"[train-rl] checkpoint/deck MISMATCH -- {init_path.name} was trained for:")
        print(f"[train-rl]   ckpt deck ({n_cards}): {', '.join(map(str, deck or ['?'] * n_cards))}")
        print(f"[train-rl]   config deck ({len(current_deck)}): {', '.join(current_deck)}")
        print("[train-rl] a policy cannot act on a deck it wasn't trained for. Either train a fresh")
        print("[train-rl] sim policy for this deck first:")
        print("[train-rl]   run.py train-sim --size 432 --matches 200000 --envs 32")
        print("[train-rl]   run.py train-rl --init data/policy_sim_best.pt")
        print("[train-rl] or restore the old deck in config/cards.yaml to keep using this checkpoint.")
        return

    if deck and len(deck) == n_cards:
        card_elixir = [float(_db.elixir(k) or _db.elixir(_base_key(k)) or 0.0) for k in deck]
    else:
        card_elixir = [0.0] * n_cards
    afford_costs = torch.tensor(card_elixir, dtype=torch.float32, device=device)  # [n_cards]
    # ANYWHERE cards (rocket / miner) may target any cell; every other card can only deploy on YOUR
    # half. Mask the cell head to DEPLOYABLE cells before the argmax so the policy never selects an
    # enemy-half cell that would just clamp / no-op -- the 'impossible coordinate' the model kept
    # trying (which also made it look inactive). Applied at action selection AND in the DDQN target.
    from .actions import ActionSpace
    _acts = ActionSpace(cfg)
    anywhere_ids = {i for i, k in enumerate(deck) if _base_key(k) in ("rocket", "miner")} if deck else set()
    yourhalf_mask = torch.tensor(_acts.deployable_mask(False), dtype=torch.bool, device=device)  # [n_cells]
    # "Anywhere" is NOT every cell: it excludes the enemy king keep-out. Rocketing their king is a
    # self-inflicted penalty -- six elixir to hand them a third defensive tower -- so it is masked
    # out of SELECTION rather than merely priced badly, for the greedy action and for exploration
    # alike. This used to be torch.ones(), which is how a raised epsilon put a rocket on the king
    # within minutes (user, 2026-08-16).
    allcells_mask = torch.tensor(_acts.deployable_mask(True), dtype=torch.bool, device=device)
    yourhalf_cells = [c for c in range(n_cells) if bool(yourhalf_mask[c])]
    anywhere_cells = [c for c in range(n_cells) if bool(allcells_mask[c])]
    anywhere_ids_t = torch.tensor(sorted(anywhere_ids), dtype=torch.long, device=device)

    net = _build_net(cfg, device, n_cards, n_cells, threat_dim, in_ch)
    net.policy.load_state_dict(ckpt["model"])
    if "gate" in ckpt:
        net.gate.load_state_dict(ckpt["gate"])
    target = _build_net(cfg, device, n_cards, n_cells, threat_dim, in_ch)
    target.load_state_dict(net.state_dict())
    target.eval()
    print(f"[train-rl] initialised from {init_path.name} on {device} "
          f"(cards={n_cards}, cells={n_cells})")

    gamma = float(cfg.get("train", "gamma", default=0.99))
    lr = float(cfg.get("train", "lr", default=1e-4))
    batch_size = int(cfg.get("train", "batch_size", default=64))
    replay_size = int(cfg.get("train", "replay_size", default=100000))
    min_replay = int(cfg.get("train", "min_replay", default=200))
    target_sync = int(cfg.get("train", "target_sync", default=500))
    grad_clip = float(cfg.get("train", "grad_clip", default=10.0))
    eps_start = float(cfg.get("train", "rl_epsilon_start",
                              default=cfg.get("train", "epsilon_start", default=1.0)))
    eps_end = float(cfg.get("train", "rl_epsilon_end",
                            default=cfg.get("train", "epsilon_end", default=0.05)))
    eps_steps = int(cfg.get("train", "rl_epsilon_decay_steps",
                            default=cfg.get("train", "epsilon_decay_steps", default=3000)))
    n_step = max(1, int(cfg.get("train", "n_step", default=1)))
    wait_prob = float(cfg.get("train", "explore_wait_prob", default=0.4))
    min_play_elixir = int(cfg.get("train", "min_play_elixir", default=3))
    save_every = int(cfg.get("train", "save_every_matches", default=1))

    opt = torch.optim.Adam(net.parameters(), lr=lr)
    # HEAD RAIL GUARD + SHARPNESS CAP (2026-08-14, ported from train_sim_ppo). The live trainer
    # had NEITHER: policy_rl.pt was fine-tuned all morning with unbounded head weights, and the
    # session's cell head sat railed at one edge column (63/69 live plays in grid column 0).
    # Weight-space guard here (no env probe available pre-loop): if the head weight norms are
    # far beyond a healthy scale, rescale; then clamp every step like the sim trainer.
    _card_ref = float(net.policy.card_head.weight.norm()) or 1.0
    _cell_ref = float(net.policy.cell_conv[-1].weight.norm()) or 1.0
    _HEAD_NORM_MULT = float(cfg.get("sim", "ppo_head_norm_mult", default=2.0))

    def _clamp_heads():
        with torch.no_grad():
            for mod, ref in ((net.policy.card_head, _card_ref), (net.policy.cell_conv[-1], _cell_ref)):
                n = float(mod.weight.norm())
                cap_n = _HEAD_NORM_MULT * ref
                if n > cap_n:
                    mod.weight.mul_(cap_n / n)
                    if mod.bias is not None:
                        mod.bias.mul_(cap_n / n)
    replay: deque = deque(maxlen=replay_size)

    class _NStep:
        """n-step return accumulator (port of train_sim's): emits (s_t, a_t, sum_j gamma^j r_{t+j},
        s_{t+n}, gamma^n) once the window fills; on terminal, flushes every remaining head with
        done=1. n=1 reproduces plain 1-step exactly. Live rewards are SPARSE (tower chips seconds
        after the causal play) -- n-step bridges the gap the same way it does in the sim."""

        def __init__(self, n: int, gamma: float):
            self.n, self.g = n, gamma
            self.buf: list = []

        def _emit(self, k: int, done: float):
            head, tail = self.buf[0], self.buf[k - 1]
            R = sum((self.g ** j) * self.buf[j][3] for j in range(k))
            # head keeps its state/action/current-side vectors; tail supplies the NEXT-side vectors
            return (head[0], head[1], head[2], R, done, tail[5], tail[6], head[7], tail[8],
                    head[9], tail[10], head[11], tail[12], self.g ** k)

        def push(self, tr):
            self.buf.append(tr)
            # `not done` guard (2026-08-20 audit): without it exactly one transition per episode
            # bootstraps off the POST-TERMINAL state while carrying done=0 -- and that is the
            # window holding the win/loss reward. train_sim.py has always had this guard; the
            # live port dropped it.
            if len(self.buf) >= self.n and float(self.buf[-1][4]) < 0.5:
                out = self._emit(self.n, 0.0)
                self.buf.pop(0)
                return [out]
            return []

        def flush(self):
            out = []
            while self.buf:
                out.append(self._emit(len(self.buf), 1.0))
                self.buf.pop(0)
            return out

    nstep = _NStep(n_step, gamma)

    env = LiveMatchEnv(cfg)
    # ---- LIVE ROLLOUT SEARCH, shared with play.py (sim.live_search_enabled, OFF by default) ----
    # train-rl makes live decisions too, so the hook belongs here as well. DDQN is OFF-POLICY, so
    # transitions produced by a searcher are legitimate training data -- no importance ratio to
    # break, which is precisely what forced the PPO side to exclude searched steps from its
    # surrogate. Ceiling is measured at 13-27% of the sim gain and poorly determined; every guard
    # inside falls back to the POLICY's action.
    _live_search = None
    try:
        if bool(cfg.get("sim", "live_search_enabled", default=False)):
            from .sim.live_search import LiveSearch
            from .cards import CardDB
            _live_search = LiveSearch(
                cfg, CardDB(path=cfg.path("config/cards.yaml")), random.Random(0),
                net, device, env.actions,
                horizon=float(cfg.get("sim", "live_search_horizon", default=12.0)),
                cells=int(cfg.get("sim", "live_search_cells", default=3)),
                gate_tau=float(cfg.get("sim", "ppo_gate_threshold", default=0.25)),
                timeout_ms=float(cfg.get("sim", "live_search_timeout_ms", default=120.0)),
                min_confidence=float(cfg.get("sim", "live_search_min_confidence", default=0.5)),
                enabled=True)
            print("[train-rl] LIVE SEARCH ENABLED -- searched transitions are legitimate DDQN "
                  "training data (off-policy); the policy remains the fallback on every skip path")
    except Exception as _e:                                    # noqa: BLE001
        print(f"[train-rl] live search unavailable ({_e}); continuing on the policy alone")
        _live_search = None
    if not env.region_ready():
        print("[train-rl] no capture region; set window.region in config.yaml.")
        return

    from .monitor import DiscordMonitor
    monitor = DiscordMonitor(cfg, label="train-rl")
    monitor.start()

    tl = None
    if bool(cfg.get("train", "timelapse", default=True)):
        from .timelapse import TimelapseRecorder
        tl_dir = cfg.path(cfg.get("train", "timelapse_dir", default="data/timelapses"))
        stamp = time.strftime("%Y%m%d_%H%M%S")           # index each run's timelapse by date+time
        tl = TimelapseRecorder(
            tl_dir / f"timelapse_{stamp}.mp4",
            seconds=float(cfg.get("train", "timelapse_seconds", default=30.0)),
            fps=int(cfg.get("train", "timelapse_fps", default=30)),
            width=int(cfg.get("train", "timelapse_width", default=640)))
        print(f"[train-rl] recording a {tl.target // tl.fps}s @ {tl.fps}fps timelapse to "
              f"{tl.path} (whole run compressed to a fixed-length video)")

    # Optionally harvest annotation frames into data/detect during the session (empty labels to hand-label).
    collector = None
    if bool(cfg.get("detect", "capture_during_train", default=True)):
        from .detect import TrainFrameCollector
        collector = TrainFrameCollector(
            cfg,
            every_s=float(cfg.get("detect", "capture_every_s", default=5.0)),
            per_match=int(cfg.get("detect", "capture_per_match", default=20)),
            session_max=int(cfg.get("detect", "capture_session_max", default=200)))
        print(f"[train-rl] harvesting annotation frames to {collector.root} "
              f"(every {collector.every_s:.0f}s, <= {collector.per_match}/match, <= {collector.session_max}/session)")

    running = {"v": True}

    def _on_sigint(*_a):
        """First Ctrl+C = stop cleanly and save. Second = abort NOW.

        A handler that only sets a flag silently disarms Ctrl+C anywhere the flag is not polled --
        which is every menu-navigation loop between matches. Restoring the default handler on the
        second press guarantees an escape hatch no matter where execution is parked."""
        if running["v"]:
            running["v"] = False
            print("\n[train-rl] stop requested -- finishing the current match/step and saving. "
                  "Press Ctrl+C again to abort immediately.", flush=True)
        else:
            signal.signal(signal.SIGINT, signal.SIG_DFL)
            raise KeyboardInterrupt

    signal.signal(signal.SIGINT, _on_sigint)
    env.stop_requested = lambda: not running["v"]     # lets reset() bail out of menu navigation

    def epsilon(step):
        if step >= eps_steps:
            return eps_end
        return eps_start + (eps_end - eps_start) * (step / eps_steps)

    def obs_to_tensor(obs):
        return torch.from_numpy(obs).float().permute(2, 0, 1).unsqueeze(0).to(device) / 255.0

    def hand_to_tensor(hand_vec):
        return torch.from_numpy(np.asarray(hand_vec, np.float32)).unsqueeze(0).to(device)

    # ---- LLM exploration advisor (train.llm_advisor; OFF unless switched on) ----------------
    card_names = list(deck) if deck and len(deck) == n_cards else ["card%d" % i for i in range(n_cards)]
    # Everything our own side can possibly be, evolutions folded onto their base -- the sanity
    # check for detections tagged "mine" (see _situation).
    own_cards = set(card_names) | {_base_key(k) for k in card_names}
    advisor = None
    advisor_log = bool(cfg.get("train", "llm_advisor_log", default=True))
    plan: list = []          # the advisor's remaining ordered cards for this board
    wheels_on = bool(cfg.get("train", "training_wheels", default=True))
    # THE COUNTER TABLE (config/counters.yaml): researched threat -> ordered response, each with
    # WHEN and WHERE. Empty when the deck has no table yet, and every consumer below then keeps
    # the behaviour it had before -- so this is additive, never a new failure mode.
    from .counters import load as _load_counters
    counter_table = _load_counters(cfg)
    if len(counter_table):
        print("[train-rl] counter table: %d researched rows" % len(counter_table), flush=True)
    offense_leak_guard = float(cfg.get("train", "offense_leak_guard", default=9.5))
    advisor_plan = bool(cfg.get("train", "llm_advisor_plan", default=False))
    # ASYNC (2026-08-23). MEASURED live: 10 calls, 0 answered, mean 565 ms against a 550 ms budget
    # -- the SYNCHRONOUS advisor never once answered, because play.act_period went 1.0 -> 0.6 on
    # 2026-08-20 and the budget was never revisited. The bot is blind during the call, so no
    # timeout that fits a 600 ms period also fits a ~590 ms model. Asking in the BACKGROUND costs
    # the decision loop nothing; the answer simply arrives a decision or two later.
    advisor_async = bool(cfg.get("train", "llm_advisor_async", default=True))
    advisor_max_age = float(cfg.get("train", "llm_advisor_max_age_s", default=1.5) or 1.5)
    if bool(cfg.get("train", "llm_advisor", default=False)):
        from .llm_advisor import LLMAdvisor  # noqa: F401  (HOLD imported at module scope below)
        # ⚠ THE BUDGET MUST GROW WITH ASYNC OR NOTHING CHANGES. `llm_advisor_timeout_s` (0.55) is
        # sized so a SYNCHRONOUS call fits inside act_period while the bot is blind. Off the
        # critical path that constraint is gone -- and if the HTTP timeout stayed at 0.55 the
        # background call would keep timing out at 565 ms exactly as it does today, so the whole
        # exercise would be a no-op. The async budget is bounded by usefulness instead: an answer
        # older than llm_advisor_max_age_s is discarded on collection anyway.
        _t_async = float(cfg.get("train", "llm_advisor_async_timeout_s", default=5.0) or 5.0)
        advisor = LLMAdvisor(cfg, timeout=_t_async if advisor_async else None)
        if advisor_async:
            print("[train-rl] advisor mode: ASYNC -- ask in background, spend the answer up to "
                  "%.1fs later; HTTP budget %.1fs (sync budget %.2fs is bypassed)"
                  % (advisor_max_age, _t_async,
                     float(cfg.get("train", "llm_advisor_timeout_s", default=0.55) or 0.55)))
        # A REACHABILITY CHECK, not just a banner. The advisor is meant to fail silently to random
        # during a match, which is right for the live loop and useless at startup: a dead Ollama, a
        # model that was never pulled, or a wrong name would all look identical to "it is working"
        # until the session ended. So ask it one question now, while there is someone watching.
        print("[train-rl] LLM exploration advisor ON: %s, %.0f ms budget -- replaces the RANDOM "
              "card on epsilon steps only, never the greedy action."
              % (advisor.model, 1000 * advisor.timeout))
        t_warm = time.time()
        probe = advisor.warmup()          # loads the model NOW, not on the first exploration step
        if probe is None:
            print("[train-rl]   WARNING: the advisor did not answer even with a long warm-up (%s). "
                  "Every epsilon step will silently fall back to a random card. Check `ollama list` "
                  "and that train.llm_advisor_model names a pulled model."
                  % (advisor.last_error or "no reason given"))
        else:
            print("[train-rl]   warmed up in %.1fs (answered %r); in-match calls run against the "
                  "%.0f ms budget" % (time.time() - t_warm, probe, 1000 * advisor.timeout))
    else:
        # Say so explicitly. "No line at all" is ambiguous between OFF and BROKEN, and that
        # ambiguity cost a debugging round (user, 2026-08-16).
        print("[train-rl] LLM exploration advisor OFF (set train.llm_advisor: true to enable); "
              "epsilon steps pick a random card")


    def _visible_enemy_bases(env):
        """Every enemy the ADVISOR WAS TOLD ABOUT, by the same filter `_situation` describes them.

        Deliberately NOT depth-filtered, because this answers a different question from
        `_counted_threats`. That one asks "is this worth a card", where a threat still on their
        own half correctly reads as "not yet". This asks "can the card the advisor named even
        touch what it was shown", and a Balloon is equally untouchable by The Log on either side
        of the river. Keeping one filter for both questions is what let a lone Balloon draw a Log:
        the prompt described it, the group did not contain it, and the veto had nothing to test.
        """
        out = []
        for d in (getattr(env, "_last_dets_all", None) or ()):
            if getattr(d, "team", "") != "enemy":
                continue
            if int(getattr(d, "trk_hits", 2) or 2) < 2:
                continue                 # 1-frame phantom: the prompt skips these too
            b = str(getattr(d, "base", "") or "")
            if not b or (_db.kind(b) == "spell" and b not in SPAWN_SPELLS):
                continue                 # nothing counters a fireball; spawn-spells DO count
            out.append(b)
        return tuple(out)

    def _counted_threats(env):
        """The triaged enemy group as base names: live corroborated non-spell dets + the
        tracker's remembered enemies, deduplicated. None = the detector is blind (callers must
        not read blind as quiet). Shared by _needs_answer and the advisor pick gate so both
        argue about the SAME group."""
        return _needs_answer(env, _group_only=True)

    def _needs_answer(env, _group_only: bool = False):
        """Is anything on the board actually worth spending a card on?

        DECIDED IN CODE, NOT BY THE MODEL. This is exactly computable from our own card DB -- an
        ignored Skeletons costs 0.4% of a Princess Tower -- and a 7B model asked the same question
        got it wrong repeatedly on tools/llm_eval.py even with the rule stated first and in
        capitals: it answered `the_log` to a lone Skeletons, which is the textbook waste. Asking a
        language model to do arithmetic it cannot check, when the answer is a table lookup, is the
        wrong division of labour. So the advisor is only consulted once there is a real decision,
        which also means a quiet board costs NO llm call at all.

        Threats ADD -- three ignorable units arriving together are one real push -- so this
        triages the group.
        """
        dets = getattr(env, "_last_dets_all", None)
        if not dets:
            return None if _group_only else True   # blind -> never suppress; not "quiet"
        seen = []                    # (x, y, base) counted so far, for de-duplication below
        bases = []
        for d in dets:
            if (d.team == "enemy" and float(getattr(d, "gy", 0.0)) >= 0.42
                    and int(getattr(d, "trk_hits", 2) or 2) >= 2
                    and not (_db.kind(str(d.base)) == "spell"
                             and str(d.base) not in SPAWN_SPELLS)):
                # trk_hits < 2 = a single-frame sighting: the tracker refuses to SERVE those
                # (track_min_hits) and the gate must refuse to TRIAGE them for the same reason --
                # a 1-frame phantom used to open this gate and buy a spell (default 2 keeps dets
                # from sources that don't annotate corroboration counting, e.g. tests).
                bases.append(str(d.base))
                seen.append((float(d.cx), float(getattr(d, "gy", 0.0)), str(d.base)))
        # BRIDGED MEMORY (2026-08-19, user report: "the advisor suggests HOLD despite the enemy
        # making several plays"). Two holes, both real: (a) the detector misses a unit in ~31% of
        # its passes, so a threat that blinked out on exactly the decision tick made the board
        # read "quiet" -- the gate FORGOT an enemy it had already seen; (b) a freshly played
        # enemy card is team "unknown" for its first seconds (no motion, no bar, no side evidence
        # yet), which is precisely the answer window, and unknowns were silently dropped. The
        # team tracker already solves (a) -- it carries tracks across misses for forget_s -- so
        # the gate now triages its remembered enemies too, de-duplicated against the live
        # detections by proximity. (b) stays deliberately unfixed HERE: after the 553fe5c team
        # fixes, residual unknowns on our side are overwhelmingly OUR OWN deck cards, and
        # counting them would re-create the phantom-threat bug in the opposite direction. The
        # tracker resolves a real enemy to "enemy" within a second or two, and the memory above
        # keeps it counted from then on even when the detector blinks.
        try:
            tracker = (env._ploop if (getattr(env, "_ploop", None) is not None
                                      and env._ploop.running) else env._team_tracker)
            for tr in tracker.enemy_tracks(time.time(), with_base=True):
                x, y, b = float(tr[0]), float(tr[1]), (str(tr[4]) if len(tr) > 4 and tr[4] else "")
                if y < 0.42 or not b:
                    continue
                if any(abs(x - sx) + abs(y - sy) < 0.06 and b == sb for sx, sy, sb in seen):
                    continue         # the same unit is already counted from the live pass
                bases.append(b)
                seen.append((x, y, b))
        except TypeError:
            _memory_gate_inert(tracker)   # never silent: see `_memory_gate_inert` above
        except Exception:  # noqa: BLE001 -- perception hiccup must not break the gate
            pass
        if _group_only:
            return bases
        if not bases:
            # A BACK BUILD IS NOT A QUIET BOARD (2026-08-20, user). This gate only ever triaged
            # what was on OUR half, so a golem assembling behind their king read as "nothing to
            # answer" and the loop went hunting for a PRESSURE play -- which is exactly how the
            # offensive X-Bow came to look correct against a push that was already paid for. The
            # board is not quiet, it is pre-defensive: say so, and the defensive answer follows.
            try:
                units = [(t[0], t[1], (t[4] if len(t) > 4 else ""))
                         for t in tracker.enemy_tracks(time.time(), with_base=True)]
                if threat_value.massing_in_back(_db, units):
                    return True
            except Exception:  # noqa: BLE001 -- perception hiccup must not break the gate
                pass
            return False             # nothing of theirs on our side of the river
        return threat_value.bodies_ignore_frac(
            _db, bases, tower_level=_tower_level) >= threat_value.IGNORE_FRAC

    def _situation(env) -> str:
        """The board in words, from the DETECTOR -- named cards, lanes and depths.

        The first version used only the identity-threat block: roles and a depth number. That is
        what the reward terms need, but it is thin for an advisor -- "a tank threat 60% in" cannot
        distinguish a Golem from a Giant Skeleton, and says nothing about what YOU already have
        defending, which is where every synergy in this deck lives. `_last_dets_all` already
        carries per-unit team, card name, position and confidence, and the same BoardWarp the
        observation canvas uses converts those to board coordinates -- so the advisor can be told
        the same thing the canvas shows the network.

        Falls back to the role summary when detections are unavailable, so a detector hiccup
        degrades the description instead of breaking the call.
        """
        dets = getattr(env, "_last_dets_all", None) or []
        groups, mine, dropped, seen_xy = {}, {}, [], []
        try:
            w = env.actions.warp
            for d in dets:
                if d.team not in ("mine", "enemy"):
                    continue
                if d.team == "enemy":
                    # THE LAST PHANTOM-CAST PATH (2026-08-20). The gate got the trk_hits >= 2
                    # corroboration filter; this string did not -- so a 1-frame phantom was still
                    # DESCRIBED to the advisor, which answered with a spell: live_20260819_230129
                    # shows tornado casts at board mass 0.009 (empty screen). Same filter here.
                    if int(getattr(d, "trk_hits", 2) or 2) < 2:
                        continue
                    # ...and enemy SPELLS are effects, not units: nothing counters a fireball, so
                    # telling the advisor about one buys a wasted answer (user rule; spawn-spells
                    # like graveyard/goblin_barrel DO demand an answer and stay).
                    if (_db.kind(str(d.base)) == "spell"
                            and str(d.base) not in SPAWN_SPELLS):
                        continue
                bx, by = w.frame_to_board(d.cx, d.gy)
                name = str(d.base).replace("_", " ")
                if d.team == "mine":
                    # A unit of OURS can only be a card from OUR deck. The detector's team tag is
                    # not reliable: a live session reported "YOUR units already out: goblin cage"
                    # and "... earthquake", neither of which is in this deck, and the earthquake
                    # was most likely our own king tower (user, 2026-08-16). Telling the advisor
                    # that is worse than telling it nothing -- it then reasons about a board that
                    # does not exist. Deck membership is a HARD constraint, so anything failing it
                    # is a misclassification and gets dropped rather than reported.
                    if str(d.base) not in own_cards:
                        dropped.append(str(d.base))
                        continue
                    mine[name] = mine.get(name, 0) + 1
                    continue
                where = ("deep in your half" if by > 0.66 else
                         "in your half" if by > 0.52 else
                         "at the bridge" if by > 0.44 else "on their side")
                lane = "left" if bx < 0.42 else "right" if bx > 0.58 else "centre"
                k = (name, where, lane)
                groups[k] = groups.get(k, 0) + 1
                seen_xy.append((float(d.cx), float(d.gy), str(d.base)))
        except Exception:  # noqa: BLE001
            groups = {}
        # REMEMBERED enemies (2026-08-19, same report as the _needs_answer fix: "the advisor
        # suggests HOLD despite the enemy making several plays"). This string read ONE detector
        # pass, and the detector misses a unit in ~31% of them -- so an enemy that blinked out on
        # the advisor tick was simply not mentioned and the advisor reasoned about an empty board.
        # The tracker carries those units across misses; whatever it remembers that the live pass
        # did not report is appended, labelled so the advisor knows the position is memory.
        try:
            w = env.actions.warp
            tracker = (env._ploop if (getattr(env, "_ploop", None) is not None
                                      and env._ploop.running) else env._team_tracker)
            for tr in tracker.enemy_tracks(time.time(), with_base=True):
                x, y, b = float(tr[0]), float(tr[1]), (str(tr[4]) if len(tr) > 4 and tr[4] else "")
                if not b:
                    continue
                if any(abs(x - sx) + abs(y - sy) < 0.06 and b == sb for sx, sy, sb in seen_xy):
                    continue         # already told from the live pass
                seen_xy.append((x, y, b))
                bx, by = w.frame_to_board(x, y)
                where = ("deep in your half" if by > 0.66 else
                         "in your half" if by > 0.52 else
                         "at the bridge" if by > 0.44 else "on their side")
                lane = "left" if bx < 0.42 else "right" if bx > 0.58 else "centre"
                k = (b.replace("_", " "), where + ", briefly out of sight", lane)
                groups[k] = groups.get(k, 0) + 1
        except Exception:  # noqa: BLE001 -- memory is a bonus; never break the description
            pass
        if groups or mine:
            en = "; ".join("%s%s %s (%s lane)" % (n, " x%d" % c if c > 1 else "", wh, ln)
                           for (n, wh, ln), c in list(groups.items())[:5]) or "nothing"
            ours = ", ".join("%s%s" % (n, " x%d" % c if c > 1 else "")
                             for n, c in mine.items()) or "nothing"
            note = ("" if not dropped else
                    "  [dropped %d impossible ally detection(s): %s]"
                    % (len(dropped), ", ".join(sorted(set(dropped))[:4])))
            return "ENEMY on the board: %s\nYOUR units already out: %s%s" % (en, ours, note)
        # fallback: the role block the reward terms use
        tid = getattr(env, "_threat_id", None)
        if tid is None or len(tid) < 10 or tid[0] < 0.5:
            return "ENEMY: nothing recognised on your half."
        roles = [n for n, i in (("tank", 1), ("swarm", 2), ("air", 3), ("building/siege", 4),
                                ("win condition", 5), ("building-targeting", 6)) if tid[i] >= 0.5]
        depth, vel = float(tid[7]), float(tid[8])
        pace = "closing fast" if vel > 0.15 else ("advancing" if vel > 0.02 else "not advancing")
        return ("ENEMY: a %s threat is %.0f%% of the way to your king and %s."
                % ("/".join(roles) or "recognised", 100.0 * depth, pace))


    def _pick_invalid(base, threat_bases):
        """Why this card cannot answer THIS threat group (None = valid).

        The rules live in threat_value (KB-grounded, shared with the sim's doctrine) because the
        advisor prompt already forbade both failures IN WORDS and produced them anyway: a
        ground-only card against an all-air group ("knight can't even see the balloon") and a
        spell far pricier than what it erases ("rocketing wall breakers", 6-for-2)."""
        return threat_value.pick_invalid(_db, base, threat_bases)

    def _kb_answer(playable, threat_bases):
        """The doctrine answer for this threat, else the cheapest card that VALIDLY engages it.

        DOCTRINE FIRST (2026-08-20): the researched counter table knows that Wall Breakers want
        Skeletons at the tower and a Balloon wants a Tornado into the King -- specifics no
        role-matcher can express. Only when the table has no opinion does this fall back to
        cheapest-valid (troops and buildings before spells: a body defends and survives, a spell
        is spent). Falling back to RANDOM, which is what happened before the veto existed, would
        re-teach the exact habit the veto exists to remove."""
        if len(counter_table) and threat_bases:
            want = counter_table.best_card(
                threat_bases, hand_bases=[_base_key(card_names[i]) for i in playable])
            if want:
                for i in playable:
                    if _base_key(card_names[i]) == want and not _pick_invalid(want, threat_bases):
                        return i
        best = None
        for i in playable:
            base = _base_key(card_names[i])
            if _pick_invalid(base, threat_bases):
                continue
            key = (1 if _db.kind(base) == "spell" else 0, card_elixir[i])
            if best is None or key < best[0]:
                best = (key, i)
        return None if best is None else best[1]

    def choose(obs, hand_vec, next_vec, elixir_vec, threat_vec, eps, elixir, situation="",
               needs_answer=True, threat_bases=(), seen_bases=()):
        # playable = in hand AND affordable (mirrors play.py) -> the policy never selects a card it
        # can't pay for, which otherwise wastes the turn on a "Not enough Elixir!" no-op.
        playable = [i for i, v in enumerate(hand_vec)
                    if v > 0.5 and card_elixir[i] <= elixir + 1e-6]
        if not playable:                     # nothing in hand affordable -> can only wait
            return (0, 0, 0)
        if random.random() < eps:
            # don't fritter cards when starved; wait to cycle/save elixir
            if elixir < min_play_elixir or random.random() < wait_prob:
                return (0, 0, 0)
            # INFORMED EXPLORATION. Uniform-random over the hand is what fills the replay buffer
            # during epsilon steps, and it is the reason a live "rocket play" was a random card on
            # a random tile. Double-DQN is OFF-POLICY, so the behaviour policy may be anything --
            # no importance correction is needed, unlike the sim's PPO. A local model answers in
            # ~0.59 s inside the 1.0 s budget and is right far more often than uniform noise; when
            # it cannot answer in time it returns None and this falls straight back to random.
            c = None
            if not needs_answer:
                # NOT A DEFENCE DECISION. The tower handles what is out there, so the elixir goes
                # into the win condition -- "with a quiet enemy board and 6+ elixir the play is
                # the X-Bow; otherwise cycle the cheapest card or hold". Same rule the sim's
                # doctrine applies, so exploration means the same thing on both sides.
                bow = next((i for i in playable if _base_key(card_names[i]) == "x_bow"), None)
                if bow is not None and elixir >= 6.0:
                    c = bow
                else:
                    if advisor_log:
                        print("[train-rl]   explore: HOLD (nothing on the board needs an answer)")
                    return (0, 0, 0)
            if c is None and needs_answer and len(counter_table) and threat_bases:
                # THE FAST PATH, and also the accurate one (2026-08-20). A defence decision is
                # where latency actually costs towers, and the advisor's ~0.5 s sits between
                # seeing the threat and answering it. The researched table resolves in
                # microseconds and was validated against the card DB, so when it has an in-hand
                # answer for THIS threat there is nothing to ask an LLM about. The advisor still
                # gets every board the table has no row for.
                _want = counter_table.best_card(
                    threat_bases, hand_bases=[_base_key(card_names[i]) for i in playable])
                if _want:
                    for _i in playable:
                        if (_base_key(card_names[_i]) == _want
                                and not _pick_invalid(_want, threat_bases)):
                            c = _i
                            if advisor_log:
                                print("[train-rl]   explore: DOCTRINE %s (table hit, advisor "
                                      "skipped)" % _want)
                            break
            if c is None and advisor is not None:
                # A DEFENCE IS USUALLY MORE THAN ONE CARD, and the live loop plays one card per
                # decision -- so the answer is a SEQUENCE spent over consecutive turns. Ask once,
                # then spend the plan in order. This also means the opening card can be the one
                # that must land FIRST rather than the one that scores best alone (a Knight in
                # front only makes sense if the Log is coming behind it), which a per-decision
                # single-card question can never express.
                if advisor_async:
                    # COLLECT FIRST, THEN ASK. The answer waiting here was computed for a board
                    # one or two decisions old, so it is a SUGGESTION about a situation that has
                    # moved -- which is exactly why it falls through to the same `_pick_invalid` /
                    # `misses_primary` validation below as a synchronous answer, against the
                    # CURRENT threat group. Age is only the first filter.
                    _got = advisor.poll_async(max_age_s=advisor_max_age)
                    if _got:
                        _cards, _age, _key = _got
                        pick = _cards[0] if _cards else None
                        if pick is not None and advisor_log:
                            print("[train-rl]   explore: ASYNC %s (%.0f ms old%s)"
                                  % (pick, 1000 * _age,
                                     "" if _key == tuple(threat_bases) else ", board CHANGED"))
                    else:
                        pick = None
                    # ...and start the next one for the board in front of us. Keyed on the threat
                    # group so the answer can be recognised as belonging to a different board.
                    advisor.ask_async(situation, [card_names[i] for i in playable], elixir,
                                      key=tuple(threat_bases), plan=False)
                elif advisor_plan:
                    # MULTI-CARD MODE, off by default. The longer answer costs ~150 ms more
                    # (582 -> 735 ms mean) against a 900 ms budget, which pushed the TAIL past the
                    # timeout and made nearly every call fall back to random -- the advisor looked
                    # dead and play went back to noise. And it bought nothing: qwen2.5 7B returns a
                    # single card even when asked for a sequence. Paying latency for a capability
                    # the model does not use is the worst of both, so the fast single-card path is
                    # the default until a model actually produces sequences.
                    while plan and plan[0] != _HOLD and (
                            plan[0] not in card_names or card_names.index(plan[0]) not in playable):
                        plan.pop(0)          # cycled away or unaffordable -> that step is spent
                    if not plan:
                        plan[:] = advisor.suggest_plan(
                            situation, [card_names[i] for i in playable], elixir) or []
                        if plan and advisor_log:
                            print("[train-rl]   plan: %s" % " -> ".join(plan))
                    pick = plan.pop(0) if plan else None
                else:
                    pick = advisor.suggest(situation,
                                           [card_names[i] for i in playable], elixir)
                # HOLD IS AN ANSWER, not a failure. "Is this even worth a card" is the first
                # question the doctrine asks, and a lone Skeletons costs 0.4% of a tower if
                # ignored -- so the advisor must be able to spend nothing, and that decision
                # belongs in the replay buffer as a real no-op the Q-learner can learn from.
                # Falling through to a random card here would teach the exact habit we are
                # trying to remove.
                if pick == _HOLD:
                    if advisor_log:
                        print("[train-rl]   explore: HOLD (nothing worth answering) | %s"
                              % situation.replace("\n", " | ")[:90])
                    return (0, 0, 0)
                if pick is not None and pick in card_names:
                    idx = card_names.index(pick)
                    if idx in playable:
                        pbase = _base_key(pick)
                        # VALIDATE AGAINST WHAT THE ADVISOR WAS SHOWN, not only against what
                        # triage counted. `threat_bases` is depth-filtered (>= 0.42), so a Balloon
                        # still on their side made it empty -> needs_answer False -> the pick was
                        # accepted with no validation whatsoever. "Can this card touch that" is
                        # not conditional on "is that worth a card": a ground-only spell misses a
                        # flyer on either side of the river.
                        _val = tuple(threat_bases) or tuple(seen_bases or ())
                        why = _pick_invalid(pbase, _val) if _val else None
                        if why is None and _val:
                            # ...AND DOES IT ANSWER THE THING THAT MATTERS? `pick_invalid` only
                            # rejects a card that can touch NOTHING in the group, so one skeleton
                            # walking beside a Balloon made The Log a "legal" answer to a Balloon
                            # -- the user's repeated report, and the reason it kept surviving: a
                            # Balloon essentially never arrives alone, so the all-air test almost
                            # never fired on the board it was written for.
                            #
                            # Only a veto when the hand can actually do better. If nothing here
                            # reaches the Balloon then logging the skeletons IS the best available
                            # play, and rejecting it would drop through to a RANDOM card, which is
                            # strictly worse than deliberate mitigation.
                            miss = threat_value.misses_primary(_db, pbase, _val)
                            if miss:
                                better = [i for i in playable
                                          if not _pick_invalid(_base_key(card_names[i]), _val)
                                          and not threat_value.misses_primary(
                                              _db, _base_key(card_names[i]), _val)]
                                if better:
                                    why = miss
                        if why is None:
                            c = idx
                        else:
                            alt = _kb_answer(playable, _val)
                            if alt is not None and threat_value.misses_primary(
                                    _db, _base_key(card_names[alt]), _val):
                                alt = next((i for i in playable
                                            if not _pick_invalid(_base_key(card_names[i]), _val)
                                            and not threat_value.misses_primary(
                                                _db, _base_key(card_names[i]), _val)), alt)
                            if advisor_log:
                                print("[train-rl]   advisor pick %s REJECTED (%s) -> %s"
                                      % (pick, why,
                                         card_names[alt] if alt is not None else
                                         "nothing better in hand, KEEPING it as mitigation"))
                            # NO VALID ALTERNATIVE -> KEEP THE ADVISOR'S PICK. Leaving c as None
                            # here fell through to "advisor gave nothing -> RANDOM card", which
                            # both mis-reported what happened (the advisor gave plenty) and threw
                            # away a deliberate play for a coin flip.
                            c = alt if alt is not None else idx
            if c is None and needs_answer and len(counter_table) and threat_bases:
                # THE ADVISOR GAVE NOTHING (timeout, cooldown, dead server) and there IS a threat.
                # Before the table the only fallback was a uniform-random card -- the measured
                # cause of the user's "the model plays randomly" sessions. The researched answer
                # is a far better exploration sample than noise, and Double-DQN is off-policy so
                # any behaviour policy is legal here.
                c = _kb_answer(playable, threat_bases)
                if c is not None and advisor_log:
                    # SAY WHICH CASE IT IS. This branch does not check `advisor`, so with the
                    # advisor OFF (llm_advisor false, the shipped default) it fires on every
                    # exploration step with a threat and used to report "advisor silent" -- which
                    # reads as "it was asked and did not answer" when it was never enabled.
                    # `llm_advisor_log` defaults to TRUE independently of `llm_advisor`, so the
                    # message survives the advisor being switched off. The behaviour was always
                    # right: this is the doctrine table picking a researched counter instead of a
                    # random card. Only the label was wrong.
                    print("[train-rl]   explore: %s -> DOCTRINE %s"
                          % ("advisor OFF" if advisor is None else "advisor silent",
                             card_names[c]))
            if c is None and advisor is not None and advisor_log:
                # The fallback is invisible otherwise, and "the plays look random" is exactly what
                # a silent fallback produces. Say which it was.
                print("[train-rl]   explore: advisor gave nothing (%s) -> RANDOM card"
                      % (advisor.last_error or "no suggestion"))
            if c is not None:
                # EXPLORE THE CARD, EXPLOIT THE PLACEMENT. Once the advisor has chosen WHAT to
                # play, a uniform-random tile throws the suggestion away -- at epsilon 0.4 that
                # was most of the session's plays, and it is why an advisor-chosen rocket still
                # landed nowhere useful. The cell head is trained and already knows where a card
                # wants to go, so exploration is confined to the card axis, which is the axis the
                # advisor actually improves.
                net.eval()
                with torch.no_grad():
                    _, ceq_e, _ = net(obs_to_tensor(obs), hand_to_tensor(hand_vec),
                                      hand_to_tensor(next_vec), hand_to_tensor(elixir_vec),
                                      hand_to_tensor(threat_vec))
                emask = allcells_mask if c in anywhere_ids else yourhalf_mask
                cell = int(ceq_e[0, c].masked_fill(~emask, float("-inf")).argmax())
                if advisor_log:
                    # WHAT it chose and WHERE it went, so "the plays look random" becomes a thing
                    # that can be read rather than guessed at. The card comes from the advisor; the
                    # cell from the trained head -- if the cards read sensibly and the cells do not,
                    # the placement head is the problem, and vice versa.
                    print("[train-rl]   explore: %-11s -> cell %3d (col %2d,row %2d) | %s"
                          % (card_names[c], cell, cell % gw, cell // gw,
                             situation.replace("\n", " | ")[:90]))
                return (1, c, cell)
            c = random.choice(playable)
            cells = anywhere_cells if c in anywhere_ids else (yourhalf_cells or anywhere_cells)
            return (1, c, random.choice(cells))
        net.eval()
        hv = hand_to_tensor(hand_vec)
        nv = hand_to_tensor(next_vec)
        ev = hand_to_tensor(elixir_vec)
        tv = hand_to_tensor(threat_vec)
        with torch.no_grad():
            cq, ceq, gq = net(obs_to_tensor(obs), hv, nv, ev, tv)
        playable_mask = torch.zeros_like(cq, dtype=torch.bool)
        playable_mask[0, playable] = True
        cq = cq.masked_fill(~playable_mask, float("-inf"))   # in hand AND affordable
        card_id = int(cq.argmax())
        cmask = allcells_mask if card_id in anywhere_ids else yourhalf_mask   # DEPLOYABLE cells for this card
        ceq = ceq[0, card_id].masked_fill(~cmask, float("-inf"))
        play_val = gq[0, 1]
        wait_val = gq[0, 0]
        # DUELING-STYLE IDENTIFIABILITY. The card and cell heads express only the RELATIVE preference
        # among LEGAL options (their advantage is <= 0 and exactly 0 at their own argmax), so
        #     max over (card, cell) of Q(s, play, card, cell) == gate[play]
        # and the play/wait decision is ONE head against ONE head. It used to be
        #     play_val = gate[play] + max_card + max_cell   vs   wait_val = gate[wait]
        # -- three heads against one. All three are trained on the SAME TD error, so any systematic
        # negative return on plays pushed all three down together and the no-op won by construction,
        # independently of how the reward was tuned. That is the passivity ratchet; this removes it.
        # The chosen card/cell are unchanged (still each head's masked argmax).
        _pol = (0, 0, 0) if wait_val >= play_val else (1, card_id, int(ceq.argmax()))
        # ---- LIVE SEARCH OVERRIDE (sim.live_search_enabled, OFF by default) -------------------
        # Wired here as well as in play.py because train-rl makes live decisions too, and DDQN is
        # OFF-POLICY: learning from search-chosen transitions is legitimate with no importance
        # ratio to break. That is why the PPO side had to EXCLUDE searched steps from its surrogate
        # and this side does not -- the replay buffer simply stores a better behaviour policy.
        # EPSILON STEPS ARE LEFT ALONE: they return above, so exploration stays exploration.
        if _live_search is not None:
            try:
                # POSITIONED TRACKS, WITH BASE NAMES. This used to pass `threat_bases`,
                # which is a tuple of base NAME STRINGS -- so the bridge parsed "knight" as
                # tr[0..2] = 'k','n','i', produced zero bodies, and every decision skipped.
                # with_base=True is required: without it there is no card identity in the track.
                _tk = (env._ploop if (getattr(env, "_ploop", None) is not None
                                      and env._ploop.running) else env._team_tracker)
                _tr = _tk.enemy_tracks(time.time(), with_base=True)
                _sa = _live_search.decide(_tr, None, float(elixir), (_pol[1], _pol[2]))
                if _sa == _live_search.WAIT:
                    return (0, 0, 0)
                if _sa is not None:
                    return (1, int(_sa[0]), int(_sa[1]))
            except Exception:                                  # noqa: BLE001
                pass                                           # never take the run down
        return _pol

    def _card_map(ceq, idx):
        """(B, n_cards, n_cells) + card index -> that CARD's placement map, (B, n_cells).

        The cell head emits one map per card now (see PolicyNet.cell_conv), so every consumer has
        to say which card it is placing. Reducing over cards instead would silently restore the
        shared-map behaviour this replaced."""
        return ceq.gather(1, idx.view(-1, 1, 1).expand(-1, 1, ceq.shape[-1])).squeeze(1)

    def _masked_max(q, mask):
        """Max over the ALLOWED entries per row. Rows with nothing allowed return 0 -- their play
        branch is unused (the agent can only wait there) and a finite value keeps gradients clean."""
        neg = torch.finfo(q.dtype).min
        m = q.masked_fill(~mask, neg).max(1).values
        return torch.where(mask.any(1), m, torch.zeros_like(m))

    def _masked_argmax(q, mask):
        neg = torch.finfo(q.dtype).min
        return q.masked_fill(~mask, neg).argmax(1, keepdim=True)

    def optimise():
        if len(replay) < max(min_replay, batch_size):
            return None
        batch = random.sample(replay, batch_size)
        obs = torch.stack([obs_to_tensor(b[0])[0] for b in batch])
        hand = torch.cat([hand_to_tensor(b[1]) for b in batch])
        nobs = torch.stack([obs_to_tensor(b[5])[0] for b in batch])
        nhand = torch.cat([hand_to_tensor(b[6]) for b in batch])
        nxt = torch.cat([hand_to_tensor(b[7]) for b in batch])
        nnxt = torch.cat([hand_to_tensor(b[8]) for b in batch])
        elx = torch.cat([hand_to_tensor(b[9]) for b in batch])
        nelx = torch.cat([hand_to_tensor(b[10]) for b in batch])
        thr = torch.cat([hand_to_tensor(b[11]) for b in batch])
        nthr = torch.cat([hand_to_tensor(b[12]) for b in batch])
        play = torch.tensor([b[2][0] for b in batch], device=device)
        card = torch.tensor([b[2][1] for b in batch], device=device).unsqueeze(1)
        cell = torch.tensor([b[2][2] for b in batch], device=device).unsqueeze(1)
        rew = torch.tensor([b[3] for b in batch], dtype=torch.float32, device=device)
        done = torch.tensor([b[4] for b in batch], dtype=torch.float32, device=device)
        gpow = torch.tensor([b[13] for b in batch], dtype=torch.float32, device=device)  # gamma^k (n-step)

        net.train()
        cq, ceq, gq = net(obs, hand, nxt, elx, thr)
        # CURRENT-state legality, rebuilt exactly as choose() had it at action time, so the greedy
        # action's advantage is exactly 0 and Q(play, greedy) == gate[play].
        playable_cur = ~((hand < 0.5) | (afford_costs.unsqueeze(0) > elx * 10.0 + 1e-6))
        if anywhere_ids_t.numel():
            any_cur = (card == anywhere_ids_t.view(1, -1)).any(1, keepdim=True)
        else:
            any_cur = torch.zeros_like(card, dtype=torch.bool)
        cellmask_cur = torch.where(any_cur, allcells_mask.unsqueeze(0), yourhalf_mask.unsqueeze(0))
        q_wait = gq[:, 0]
        q_play = (gq[:, 1]
                  + (cq.gather(1, card).squeeze(1) - _masked_max(cq, playable_cur))
                  + (_card_map(ceq, card).gather(1, cell).squeeze(1)
                     - _masked_max(_card_map(ceq, card), cellmask_cur)))
        q_sa = torch.where(play == 1, q_play, q_wait)
        with torch.no_grad():
            # DOUBLE DQN: the ONLINE net selects the greedy next action (gate / card / cell); the
            # TARGET net only EVALUATES it. Vanilla DQN took max() from the target for BOTH, which
            # systematically OVERESTIMATES Q -- the bias behind the value-inflation / reward-farming
            # this project keeps hitting. Off-policy replay (the sample-efficiency win that keeps this
            # a DQN and not PPO) is untouched; this only de-biases the bootstrap.
            cqn, ceqn, gqn = net(nobs, nhand, nnxt, nelx, nthr)
            # playable-next = in hand AND affordable at the NEXT-state elixir (nelx = elixir/10).
            # Affordability is a hard constraint just like "in hand", so the bootstrap never values a
            # card the policy couldn't actually cast (consistent with choose(); a row where nothing is
            # playable falls through to the WAIT value, same as the empty-hand case).
            playable_next = ~((nhand < 0.5) | (afford_costs.unsqueeze(0) > nelx * 10.0 + 1e-6))
            sel_card = _masked_argmax(cqn, playable_next)                 # online greedy card
            # cell mask per selected next-card: a your-half-only card can't bootstrap value from an
            # enemy-half cell it could never place on (matches the deployable mask used in choose()).
            if anywhere_ids_t.numel():
                any_next = (sel_card == anywhere_ids_t.view(1, -1)).any(1, keepdim=True)
            else:
                any_next = torch.zeros_like(sel_card, dtype=torch.bool)
            cellmask_next = torch.where(any_next, allcells_mask.unsqueeze(0), yourhalf_mask.unsqueeze(0))
            sel_cell = _masked_argmax(_card_map(ceqn, sel_card), cellmask_next)   # greedy DEPLOYABLE cell
            # Under the dueling form the greedy play's advantages are 0, so its value IS gate[play].
            # A state where nothing is affordable can only WAIT -- previously that fell out of the
            # -inf masking, so it now has to be said explicitly.
            play_next = playable_next.any(1) & (gqn[:, 1] > gqn[:, 0])
            cq2, ceq2, gq2 = target(nobs, nhand, nnxt, nelx, nthr)
            q_play_next = (gq2[:, 1]
                           + (cq2.gather(1, sel_card).squeeze(1) - _masked_max(cq2, playable_next))
                           + (_card_map(ceq2, sel_card).gather(1, sel_cell).squeeze(1)
                              - _masked_max(_card_map(ceq2, sel_card), cellmask_next)))
            v_next = torch.where(play_next, q_play_next, gq2[:, 0])      # eval the online-chosen action
            y = rew + gpow * v_next * (1.0 - done)                       # n-step: gamma^k bootstrap
        loss = F.smooth_l1_loss(q_sa, y)
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(), grad_clip)     # cap noisy TD gradients
        opt.step()
        _clamp_heads()                                   # heads can rank, not rail (see above)
        return float(loss.item())

    # KEEP-BEST GATE. Live RL used to overwrite policy_rl.pt unconditionally every `save_every`
    # matches -- and play.py PREFERS that file -- so a session that made the policy WORSE silently
    # became the deployed policy. The gate promotes only when the recent window is at least as good
    # as the best window seen this session; every save still lands in policy_rl_last.pt, so no work
    # is ever lost and a promotion can always be done by hand.
    # SCORED ON WIN RATE, GUARDED BY PLAYS/MATCH. The known failure mode -- the policy stops playing
    # -- RAISES mean episode reward, because a shorter match accrues fewer per-step penalties, so a
    # reward-scored gate would actively endorse the collapse. A window whose activity has fallen
    # below `min_play_frac` of the best window is never promoted however good its win rate looks.
    keep_window = max(1, int(cfg.get("train", "rl_keep_best_window", default=10)))
    keep_min_play_frac = float(cfg.get("train", "rl_keep_best_min_play_frac", default=0.5))
    recent_wins: deque = deque(maxlen=keep_window)
    recent_plays: deque = deque(maxlen=keep_window)
    best = {"score": None, "plays": 0.0}
    last_path = rl_path.with_name(rl_path.stem + "_last" + rl_path.suffix)

    def keep_best_verdict():
        """(promote?, why) -- should this checkpoint become the DEPLOYED policy_rl.pt?"""
        if len(recent_wins) < keep_window:
            return True, f"warm-up ({len(recent_wins)}/{keep_window} matches)"
        score = sum(recent_wins) / len(recent_wins)
        pl = sum(recent_plays) / len(recent_plays)
        if best["score"] is None:
            best["score"], best["plays"] = score, pl
            return True, f"first window: {score:.0%} win, {pl:.1f} plays/match"
        if pl < keep_min_play_frac * best["plays"]:
            return False, f"activity collapsed: {pl:.1f} plays/match vs best {best['plays']:.1f}"
        if score < best["score"]:
            return False, f"win rate {score:.0%} < best {best['score']:.0%}"
        best["score"], best["plays"] = score, max(best["plays"], pl)
        return True, f"new best: {score:.0%} win, {pl:.1f} plays/match"

    def save(promote: bool = True, why: str = "") -> None:
        rl_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": net.policy.state_dict(),
            "gate": net.gate.state_dict(),
            "grid": [gw, gh], "n_cards": n_cards, "n_cells": n_cells,
            "threat_dim": threat_dim,
            "in_ch": in_ch,
            "deck": deck,
            "arena_size": ckpt.get("arena_size", list(cfg.get("observation", "arena_size", default=[64, 96]))),
            # EXPLORATION PROGRESS, so --resume continues the schedule instead of restarting it.
            # Without this every launch went back to rl_epsilon_start: the counter is a local that
            # begins at 0, and a decay measured in thousands of steps (~200 steps a match at a 1.0 s
            # act_period) never finished inside one session. The practical effect was that only
            # rl_epsilon_start mattered and the end value was close to unreachable.
            "explore_step": int(step),
        }
        torch.save(payload, last_path)          # ALWAYS -- this session's weights are never lost
        tail = f" ({why})" if why else ""
        if promote:
            torch.save(payload, rl_path)
            print(f"[train-rl] promoted -> {rl_path.name}{tail}")
        else:
            print(f"[train-rl] NOT promoted{tail}: {rl_path.name} left as-is; "
                  f"this session's weights are in {last_path.name}")

    print("[train-rl] running. Ctrl+C to stop and save. Make sure Clash Royale is on "
          "the HOME screen; it will queue, play, and re-queue on its own.")
    # RESUME the exploration schedule where the last session left it (see save()). A fresh init from
    # a SIM checkpoint has no explore_step and correctly starts at rl_epsilon_start.
    step = int(ckpt.get("explore_step", 0) or 0)
    if step:
        print("[train-rl] resuming exploration at step %d -> epsilon %.2f (start %.2f, end %.2f "
              "over %d steps)" % (step, epsilon(step), eps_start, eps_end, eps_steps))
    match = 0
    wins = losses = 0
    try:
        while running["v"]:
            obs = env.reset()
            if obs is None:
                if getattr(env, "stopped", False):
                    break                    # Ctrl+C while navigating menus -- not a lost window
                print("[train-rl] lost the game window; retrying...")
                time.sleep(1.0)
                continue
            match += 1
            if collector is not None:
                collector.new_match()
            nstep.buf.clear()                    # never bridge transitions across matches
            plan.clear()                         # a plan is about ONE board; never carry it into a new match
            ep_reward = 0.0
            plays = 0
            hand = env.hand_vec.copy()
            nxt = env.next_vec.copy()
            elx = env.elixir_vec.copy()
            thr = env.threat_vec.copy()
            while running["v"]:
                eps = epsilon(step)
                tb = _counted_threats(env)
                na = True if tb is None else (bool(tb) and threat_value.bodies_ignore_frac(
                    _db, tb, tower_level=_tower_level) >= threat_value.IGNORE_FRAC)
                action = choose(obs, hand, nxt, elx, thr, eps, env.elixir,
                                _situation(env) if advisor is not None else "",
                                needs_answer=na, threat_bases=tuple(tb or ()),
                                seen_bases=_visible_enemy_bases(env))
                # LEAK-GUARD OFFENSE WHEEL (2026-08-20, user request: "the model should pressure
                # with x-bow when possible... defending all game won't work"). The quiet-board
                # pressure rule above lives on EXPLORATION steps only, so a greedy policy at full
                # elixir just leaked -- banking is doctrine, leaking never is. On a quiet board at
                # offense_leak_guard elixir a greedy WAIT becomes the bow: the punish/outcycle
                # window (they overspent elsewhere or we outcycled them; a second bow lands before
                # their answer recycles). This is the ONE sanctioned wait->play conversion, sound
                # only because the buffer stores the EXECUTED action (a683d46) -- the model learns
                # the bow it actually played. The bow's own lane/lock/depth assists fix the cell.
                if wheels_on and action[0] == 0 and env.elixir >= offense_leak_guard:
                    _bow = next((i for i, v in enumerate(env.hand_vec)
                                 if v > 0.5 and _base_key(card_names[i]) == "x_bow"
                                 and card_elixir[i] <= env.elixir + 1e-6), None)
                    # WHICH BOW -- pressure or defence? (2026-08-20, user rule.) A full bar with
                    # a genuinely empty board is the punish window and the bow goes forward. A
                    # full bar while they are BUILDING IN THE BACK is the opposite play: the
                    # offensive bow is blocked by a push that is already paid for, so the same
                    # six elixir goes into the back-centre band as a DEFENSIVE bow that shreds
                    # the push as it lands. env.step skips its forward snap on the same
                    # condition, so the defensive cell survives to the tap.
                    building = env._enemy_massing_back()
                    if _bow is not None and (building or not na):
                        if building:
                            mid = 0.5 * (env.xbow_defense_front + env.xbow_defense_back)
                            gx, gy = env.actions.coords_to_grid(0.48, mid)
                        else:
                            gx, gy = env.actions.coords_to_grid(0.5, 0.45)
                        action = (1, _bow, int(gy) * env.gw + int(gx))
                        if advisor_log:
                            print("[train-rl]   wheels: X-Bow at %.1f elixir (%s) -> %s"
                                  % (env.elixir,
                                     "they are BUILDING in the back" if building else "quiet board",
                                     "DEFENSIVE bow" if building else "pressure"))
                nobs, reward, done, info = env.step(action)
                if tl is not None:
                    tl.add(env._last_frame)         # collect a frame for the training timelapse
                if collector is not None:
                    collector.maybe_capture(env._last_frame)   # harvest an annotation frame (every ~5s, capped)
                nhand = env.hand_vec.copy()
                nnxt = env.next_vec.copy()
                nelx = env.elixir_vec.copy()
                nthr = env.threat_vec.copy()
                # THE EXECUTED ACTION, not the chosen one (2026-08-19). env.step rewrites the
                # CELL through the aim assists and the doctrine training wheels, so storing the
                # policy's original cell credits a placement that never happened -- the model
                # would learn that its own bad cell earned the corrected cell's reward, which is
                # exactly how a training wheel becomes permanent. Q-learning is off-policy, so the
                # executed action is the correct thing to learn from.
                taken = getattr(env, "_last_exec_action", None)
                if taken is None:
                    taken = action
                raw = (obs, hand, taken, reward, float(done), nobs, nhand, nxt, nnxt, elx, nelx, thr, nthr)
                for tr in nstep.push(raw):
                    replay.append(tr)
                if done:
                    for tr in nstep.flush():
                        replay.append(tr)
                obs, hand, nxt, elx, thr = nobs, nhand, nnxt, nelx, nthr
                ep_reward += reward
                plays += action[0]
                loss = optimise()
                step += 1
                if step % target_sync == 0:
                    target.load_state_dict(net.state_dict())
                if done:
                    outcome = info.get("outcome")
                    wins += outcome == "win"
                    losses += outcome == "loss"
                    bc, rc = info.get("crowns", (None, None))
                    sb, tw = info.get("scoreboard"), info.get("towers")
                    cs = f" crowns={bc}-{rc}" if bc is not None else ""
                    dbg = "" if not sb or sb == tw else f" (sb={sb[0]}-{sb[1]} tw={tw[0]}-{tw[1]})"
                    ls = f" loss={loss:.3f}" if loss is not None else ""
                    print(f"[train-rl] match {match}: {outcome}{cs}{dbg} reward={ep_reward:+.1f} "
                          f"plays={plays} eps={eps:.2f} replay={len(replay)}{ls}  "
                          f"record {wins}W-{losses}L")
                    recent_wins.append(1.0 if outcome == "win" else 0.0)
                    recent_plays.append(float(plays))
                    break
            if match % save_every == 0:
                save(*keep_best_verdict())
                if tl is not None:
                    tl.save()
    except KeyboardInterrupt:
        pass
    finally:
        save(*keep_best_verdict())
        if tl is not None:
            p = tl.save()
            if p is not None:
                print(f"[train-rl] timelapse -> {p}  "
                      f"({tl.target} frames @ {tl.fps}fps = {tl.target / tl.fps:.0f}s, "
                      f"from {tl.seen} captured)")
        if collector is not None and collector.session_count:
            print(f"[train-rl] harvested {collector.session_count} annotation frame(s) -> {collector.root} "
                  f"(re-sync Label Studio Local Storage to pick them up)")
        if advisor is not None:
            # Print it even when it never answered: an advisor that quietly stopped responding
            # looks exactly like one that was never on, and the session would silently be plain
            # random exploration with no sign of it.
            print("[train-rl] " + advisor.stats())
            advisor.close()
        print(f"[train-rl] stopped after {match} match(es); deployed policy is {rl_path.name}, "
              f"this session's final weights are in {last_path.name}")
