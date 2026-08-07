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
from collections import deque
from pathlib import Path

import numpy as np


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


def _build_net(cfg, device, n_cards, n_cells, threat_dim=14):
    import torch.nn as nn
    from .model import PolicyNet

    class DQN(nn.Module):
        def __init__(self):
            super().__init__()
            self.policy = PolicyNet(3, n_cards, n_cells, threat_dim=threat_dim)
            self.gate = nn.Linear(self.policy.embed_dim, 2)  # [wait, play]

        def forward(self, x, hand, nxt=None, elx=None, thr=None):
            z = self.policy.features_vec(x, hand, nxt, elx, thr)
            return self.policy.card_head(z), self.policy.cell_head(z), self.gate(z)

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
    deck = ckpt.get("deck")

    # Per-card elixir cost (by deck identity) so the policy can't select a card it can't PAY for --
    # an unaffordable pick just wastes the turn on a "Not enough Elixir!" no-op. Mirrors play.py's
    # live affordability mask; card_elixir all-zero (unknown deck) makes the mask a harmless no-op.
    from .cards import CardDB
    _db = CardDB(cfg)

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
    allcells_mask = torch.ones(n_cells, dtype=torch.bool, device=device)
    yourhalf_cells = [c for c in range(n_cells) if bool(yourhalf_mask[c])]
    anywhere_ids_t = torch.tensor(sorted(anywhere_ids), dtype=torch.long, device=device)

    net = _build_net(cfg, device, n_cards, n_cells, threat_dim)
    net.policy.load_state_dict(ckpt["model"])
    if "gate" in ckpt:
        net.gate.load_state_dict(ckpt["gate"])
    target = _build_net(cfg, device, n_cards, n_cells, threat_dim)
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
            if len(self.buf) >= self.n:
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

    def choose(obs, hand_vec, next_vec, elixir_vec, threat_vec, eps, elixir):
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
            c = random.choice(playable)
            cells = list(range(n_cells)) if c in anywhere_ids else (yourhalf_cells or list(range(n_cells)))
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
        ceq = ceq.masked_fill(~cmask.unsqueeze(0), float("-inf"))
        play_val = gq[0, 1] + cq[0].max() + ceq[0].max()
        wait_val = gq[0, 0]
        if wait_val >= play_val:
            return (0, 0, 0)
        return (1, card_id, int(ceq.argmax()))

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
        q_wait = gq[:, 0]
        q_play = gq[:, 1] + cq.gather(1, card).squeeze(1) + ceq.gather(1, cell).squeeze(1)
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
            unplayable = (nhand < 0.5) | (afford_costs.unsqueeze(0) > nelx * 10.0 + 1e-6)
            cqn = cqn.masked_fill(unplayable, float("-inf"))            # in hand AND affordable
            sel_card = cqn.argmax(1, keepdim=True)                       # online greedy card
            # cell mask per selected next-card: a your-half-only card can't bootstrap value from an
            # enemy-half cell it could never place on (matches the deployable mask used in choose()).
            if anywhere_ids_t.numel():
                any_next = (sel_card == anywhere_ids_t.view(1, -1)).any(1, keepdim=True)
            else:
                any_next = torch.zeros_like(sel_card, dtype=torch.bool)
            cellmask_next = torch.where(any_next, allcells_mask.unsqueeze(0), yourhalf_mask.unsqueeze(0))
            ceqn = ceqn.masked_fill(~cellmask_next, float("-inf"))
            sel_cell = ceqn.argmax(1, keepdim=True)                     # online greedy DEPLOYABLE cell
            play_next = (gqn[:, 1] + cqn.max(1).values + ceqn.max(1).values) > gqn[:, 0]
            cq2, ceq2, gq2 = target(nobs, nhand, nnxt, nelx, nthr)
            cq2 = cq2.masked_fill(unplayable, float("-inf"))
            ceq2 = ceq2.masked_fill(~cellmask_next, float("-inf"))
            q_play_next = (gq2[:, 1] + cq2.gather(1, sel_card).squeeze(1)
                           + ceq2.gather(1, sel_cell).squeeze(1))
            v_next = torch.where(play_next, q_play_next, gq2[:, 0])      # eval the online-chosen action
            y = rew + gpow * v_next * (1.0 - done)                       # n-step: gamma^k bootstrap
        loss = F.smooth_l1_loss(q_sa, y)
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(), grad_clip)     # cap noisy TD gradients
        opt.step()
        return float(loss.item())

    def save():
        rl_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            "model": net.policy.state_dict(),
            "gate": net.gate.state_dict(),
            "grid": [gw, gh], "n_cards": n_cards, "n_cells": n_cells,
            "threat_dim": threat_dim,
            "deck": deck,
            "arena_size": ckpt.get("arena_size", list(cfg.get("observation", "arena_size", default=[64, 96]))),
        }, rl_path)

    print("[train-rl] running. Ctrl+C to stop and save. Make sure Clash Royale is on "
          "the HOME screen; it will queue, play, and re-queue on its own.")
    step = 0
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
            ep_reward = 0.0
            plays = 0
            hand = env.hand_vec.copy()
            nxt = env.next_vec.copy()
            elx = env.elixir_vec.copy()
            thr = env.threat_vec.copy()
            while running["v"]:
                eps = epsilon(step)
                action = choose(obs, hand, nxt, elx, thr, eps, env.elixir)
                nobs, reward, done, info = env.step(action)
                if tl is not None:
                    tl.add(env._last_frame)         # collect a frame for the training timelapse
                if collector is not None:
                    collector.maybe_capture(env._last_frame)   # harvest an annotation frame (every ~5s, capped)
                nhand = env.hand_vec.copy()
                nnxt = env.next_vec.copy()
                nelx = env.elixir_vec.copy()
                nthr = env.threat_vec.copy()
                raw = (obs, hand, action, reward, float(done), nobs, nhand, nxt, nnxt, elx, nelx, thr, nthr)
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
                    break
            if match % save_every == 0:
                save()
                if tl is not None:
                    tl.save()
    except KeyboardInterrupt:
        pass
    finally:
        save()
        if tl is not None:
            p = tl.save()
            if p is not None:
                print(f"[train-rl] timelapse -> {p}  "
                      f"({tl.target} frames @ {tl.fps}fps = {tl.target / tl.fps:.0f}s, "
                      f"from {tl.seen} captured)")
        if collector is not None and collector.session_count:
            print(f"[train-rl] harvested {collector.session_count} annotation frame(s) -> {collector.root} "
                  f"(re-sync Label Studio Local Storage to pick them up)")
        print(f"[train-rl] stopped after {match} match(es); saved policy to {rl_path}")
