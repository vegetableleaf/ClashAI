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


def train_rl(cfg) -> None:
    try:
        import torch
        import torch.nn.functional as F
    except ImportError as exc:  # noqa: BLE001
        print(f"[train-rl] PyTorch required ({exc}). Install the CUDA build (see README).")
        return

    from .env import LiveMatchEnv

    bc_path = cfg.path(cfg.get("train", "checkpoint", default="data/policy.pt"))
    rl_path = cfg.path(cfg.get("train", "rl_checkpoint", default="data/policy_rl.pt"))
    init_path = rl_path if rl_path.exists() else bc_path
    if not init_path.exists():
        print(f"[train-rl] no policy to start from ({bc_path}). Run `train-bc` first.")
        return

    device = _pick_device(cfg)
    ckpt = torch.load(init_path, map_location="cpu")
    gw, gh = int(ckpt["grid"][0]), int(ckpt["grid"][1])
    n_cards, n_cells = int(ckpt["n_cards"]), int(ckpt["n_cells"])
    threat_dim = int(ckpt.get("threat_dim", 14))
    deck = ckpt.get("deck")

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
    eps_start = float(cfg.get("train", "epsilon_start", default=1.0))
    eps_end = float(cfg.get("train", "epsilon_end", default=0.05))
    eps_steps = int(cfg.get("train", "epsilon_decay_steps", default=3000))
    wait_prob = float(cfg.get("train", "explore_wait_prob", default=0.4))
    min_play_elixir = int(cfg.get("train", "min_play_elixir", default=3))
    save_every = int(cfg.get("train", "save_every_matches", default=1))

    opt = torch.optim.Adam(net.parameters(), lr=lr)
    replay: deque = deque(maxlen=replay_size)

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

    running = {"v": True}
    signal.signal(signal.SIGINT, lambda *_a: running.update(v=False))

    def epsilon(step):
        if step >= eps_steps:
            return eps_end
        return eps_start + (eps_end - eps_start) * (step / eps_steps)

    def obs_to_tensor(obs):
        return torch.from_numpy(obs).float().permute(2, 0, 1).unsqueeze(0).to(device) / 255.0

    def hand_to_tensor(hand_vec):
        return torch.from_numpy(np.asarray(hand_vec, np.float32)).unsqueeze(0).to(device)

    def choose(obs, hand_vec, next_vec, elixir_vec, threat_vec, eps, elixir):
        in_hand = [i for i, v in enumerate(hand_vec) if v > 0.5]
        if not in_hand:                      # no card recognized -> can only wait
            return (0, 0, 0)
        if random.random() < eps:
            # don't fritter cards when starved; wait to cycle/save elixir
            if elixir < min_play_elixir or random.random() < wait_prob:
                return (0, 0, 0)
            return (1, random.choice(in_hand), random.randrange(n_cells))
        net.eval()
        hv = hand_to_tensor(hand_vec)
        nv = hand_to_tensor(next_vec)
        ev = hand_to_tensor(elixir_vec)
        tv = hand_to_tensor(threat_vec)
        with torch.no_grad():
            cq, ceq, gq = net(obs_to_tensor(obs), hv, nv, ev, tv)
        cq = cq.masked_fill(hv < 0.5, float("-inf"))     # only cards in hand
        play_val = gq[0, 1] + cq.max() + ceq.max()
        wait_val = gq[0, 0]
        if wait_val >= play_val:
            return (0, 0, 0)
        return (1, int(cq.argmax()), int(ceq.argmax()))

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
            cqn = cqn.masked_fill(nhand < 0.5, float("-inf"))            # only cards in hand
            sel_card = cqn.argmax(1, keepdim=True)                       # online greedy card
            sel_cell = ceqn.argmax(1, keepdim=True)                      # online greedy cell
            play_next = (gqn[:, 1] + cqn.max(1).values + ceqn.max(1).values) > gqn[:, 0]
            cq2, ceq2, gq2 = target(nobs, nhand, nnxt, nelx, nthr)
            cq2 = cq2.masked_fill(nhand < 0.5, float("-inf"))
            q_play_next = (gq2[:, 1] + cq2.gather(1, sel_card).squeeze(1)
                           + ceq2.gather(1, sel_cell).squeeze(1))
            v_next = torch.where(play_next, q_play_next, gq2[:, 0])      # eval the online-chosen action
            y = rew + gamma * v_next * (1.0 - done)
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
                print("[train-rl] lost the game window; retrying...")
                time.sleep(1.0)
                continue
            match += 1
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
                nhand = env.hand_vec.copy()
                nnxt = env.next_vec.copy()
                nelx = env.elixir_vec.copy()
                nthr = env.threat_vec.copy()
                replay.append((obs, hand, action, reward, float(done), nobs, nhand, nxt, nnxt, elx, nelx, thr, nthr))
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
        print(f"[train-rl] stopped after {match} match(es); saved policy to {rl_path}")
