r"""Headless RL training in the SIMULATOR (`run.py train-sim`).

Trains the SAME `PolicyNet`/DQN used live, but against the fast headless engine (clashrl.sim) --
so it can play THOUSANDS of matches with no vision, no real-time waits, and (unlike live RL) FROM
SCRATCH. The resulting checkpoint (`data/policy_sim.pt`) is a PRIOR: warm-start live RL from it,
then fine-tune on real matches to close the sim-to-real gap. See real/DECK_SWITCH.md.

Usage (PowerShell), from real/:
    .\.venv\Scripts\python.exe run.py train-sim --matches 5000      # start (from scratch)
    .\.venv\Scripts\python.exe run.py train-sim --resume            # continue policy_sim.pt
    #  ...watch the rolling win-rate it prints; press Ctrl+C to stop + save at any time.
"""
from __future__ import annotations

import random
import signal
import time
from collections import deque
from pathlib import Path

import numpy as np


def train_sim(cfg, matches: int = 2000, resume: bool = False, seed: int = 0) -> None:
    try:
        import torch
        import torch.nn.functional as F
    except ImportError as exc:  # noqa: BLE001
        print(f"[train-sim] PyTorch required ({exc}). Install the CUDA build (see README).")
        return

    from .train_rl import _build_net, _pick_device
    from .sim.env import SimMatchEnv

    env = SimMatchEnv(cfg, seed=seed)
    n_cards, n_cells, threat_dim = env.n_cards, env.n_cells, env.threat_dim
    gw, gh = env.gw, env.gh
    device = _pick_device(cfg)
    net = _build_net(cfg, device, n_cards, n_cells, threat_dim)

    sim_path = cfg.path(cfg.get("train", "sim_checkpoint", default="data/policy_sim.pt"))
    if resume and sim_path.exists():
        ck = torch.load(sim_path, map_location="cpu")
        net.policy.load_state_dict(ck["model"])
        if "gate" in ck:
            net.gate.load_state_dict(ck["gate"])
        print(f"[train-sim] resumed {sim_path.name}")
    else:
        print(f"[train-sim] training FROM SCRATCH ({sim_path.name} will be written)")
    target = _build_net(cfg, device, n_cards, n_cells, threat_dim)
    target.load_state_dict(net.state_dict())
    target.eval()

    gamma = float(cfg.get("train", "gamma", default=0.99))
    lr = float(cfg.get("train", "lr", default=1e-4))
    batch_size = int(cfg.get("train", "batch_size", default=64))
    replay_size = int(cfg.get("train", "replay_size", default=100000))
    min_replay = int(cfg.get("train", "min_replay", default=1000))
    target_sync = int(cfg.get("train", "target_sync", default=500))
    grad_clip = float(cfg.get("train", "grad_clip", default=10.0))
    eps_start = float(cfg.get("sim", "epsilon_start", default=1.0))
    eps_end = float(cfg.get("sim", "epsilon_end", default=0.05))
    eps_steps = int(cfg.get("sim", "epsilon_decay_steps", default=40000))
    wait_prob = float(cfg.get("train", "explore_wait_prob", default=0.4))
    min_play_elixir = int(cfg.get("train", "min_play_elixir", default=3))
    log_every = int(cfg.get("sim", "log_every_matches", default=25))
    save_every = int(cfg.get("sim", "save_every_matches", default=50))

    opt = torch.optim.Adam(net.parameters(), lr=lr)
    replay: deque = deque(maxlen=replay_size)

    def epsilon(s):
        return eps_end if s >= eps_steps else eps_start + (eps_end - eps_start) * (s / eps_steps)

    def to_obs(o):
        return torch.from_numpy(o).float().permute(2, 0, 1).unsqueeze(0).to(device) / 255.0

    def to_vec(v):
        return torch.from_numpy(np.asarray(v, np.float32)).unsqueeze(0).to(device)

    def choose(obs, hand, nxt, elx, thr, eps, elixir):
        in_hand = [i for i, v in enumerate(hand) if v > 0.5]
        if not in_hand:
            return (0, 0, 0)
        if random.random() < eps:
            if elixir < min_play_elixir or random.random() < wait_prob:
                return (0, 0, 0)
            return (1, random.choice(in_hand), random.randrange(n_cells))
        net.eval()
        hv = to_vec(hand)
        with torch.no_grad():
            cq, ceq, gq = net(to_obs(obs), hv, to_vec(nxt), to_vec(elx), to_vec(thr))
        cq = cq.masked_fill(hv < 0.5, float("-inf"))
        if gq[0, 0] >= gq[0, 1] + cq.max() + ceq.max():
            return (0, 0, 0)
        return (1, int(cq.argmax()), int(ceq.argmax()))

    def optimise():
        if len(replay) < max(min_replay, batch_size):
            return None
        b = random.sample(replay, batch_size)
        obs = torch.stack([to_obs(x[0])[0] for x in b]); hand = torch.cat([to_vec(x[1]) for x in b])
        nobs = torch.stack([to_obs(x[5])[0] for x in b]); nhand = torch.cat([to_vec(x[6]) for x in b])
        nxt = torch.cat([to_vec(x[7]) for x in b]); nnxt = torch.cat([to_vec(x[8]) for x in b])
        elx = torch.cat([to_vec(x[9]) for x in b]); nelx = torch.cat([to_vec(x[10]) for x in b])
        thr = torch.cat([to_vec(x[11]) for x in b]); nthr = torch.cat([to_vec(x[12]) for x in b])
        play = torch.tensor([x[2][0] for x in b], device=device)
        card = torch.tensor([x[2][1] for x in b], device=device).unsqueeze(1)
        cell = torch.tensor([x[2][2] for x in b], device=device).unsqueeze(1)
        rew = torch.tensor([x[3] for x in b], dtype=torch.float32, device=device)
        done = torch.tensor([x[4] for x in b], dtype=torch.float32, device=device)

        net.train()
        cq, ceq, gq = net(obs, hand, nxt, elx, thr)
        q_sa = torch.where(play == 1,
                           gq[:, 1] + cq.gather(1, card).squeeze(1) + ceq.gather(1, cell).squeeze(1),
                           gq[:, 0])
        with torch.no_grad():                                  # Double DQN (online selects, target evals)
            cqn, ceqn, gqn = net(nobs, nhand, nnxt, nelx, nthr)
            cqn = cqn.masked_fill(nhand < 0.5, float("-inf"))
            sel_card = cqn.argmax(1, keepdim=True); sel_cell = ceqn.argmax(1, keepdim=True)
            play_next = (gqn[:, 1] + cqn.max(1).values + ceqn.max(1).values) > gqn[:, 0]
            cq2, ceq2, gq2 = target(nobs, nhand, nnxt, nelx, nthr)
            cq2 = cq2.masked_fill(nhand < 0.5, float("-inf"))
            q_play_next = gq2[:, 1] + cq2.gather(1, sel_card).squeeze(1) + ceq2.gather(1, sel_cell).squeeze(1)
            v_next = torch.where(play_next, q_play_next, gq2[:, 0])
            y = rew + gamma * v_next * (1.0 - done)
        loss = F.smooth_l1_loss(q_sa, y)
        opt.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(), grad_clip); opt.step()
        return float(loss.item())

    def save():
        sim_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"model": net.policy.state_dict(), "gate": net.gate.state_dict(),
                    "grid": [gw, gh], "n_cards": n_cards, "n_cells": n_cells,
                    "threat_dim": threat_dim, "deck": env.deck_keys,
                    "arena_size": list(cfg.get("observation", "arena_size", default=[64, 96]))}, sim_path)

    running = {"v": True}
    signal.signal(signal.SIGINT, lambda *_a: running.update(v=False))
    print(f"[train-sim] {device}: up to {matches} matches (cards={n_cards}, cells={n_cells}). "
          "Ctrl+C to stop + save.")
    step = 0
    wins = losses = draws = 0
    win_hist: deque = deque(maxlen=log_every)
    rew_hist: deque = deque(maxlen=log_every)
    t0 = time.time()
    last_loss = None
    match = 0
    try:
        while running["v"] and match < matches:
            obs = env.reset()
            match += 1
            hand, nxt, elx, thr = (env.hand_vec.copy(), env.next_vec.copy(),
                                   env.elixir_vec.copy(), env.threat_vec.copy())
            ep_r = 0.0
            while running["v"]:
                eps = epsilon(step)
                action = choose(obs, hand, nxt, elx, thr, eps, env.elixir)
                nobs, reward, done, info = env.step(action)
                nhand, nnxt, nelx, nthr = (env.hand_vec.copy(), env.next_vec.copy(),
                                           env.elixir_vec.copy(), env.threat_vec.copy())
                replay.append((obs, hand, action, reward, float(done), nobs, nhand, nxt, nnxt, elx, nelx, thr, nthr))
                obs, hand, nxt, elx, thr = nobs, nhand, nnxt, nelx, nthr
                ep_r += reward
                loss = optimise()
                if loss is not None:
                    last_loss = loss
                step += 1
                if step % target_sync == 0:
                    target.load_state_dict(net.state_dict())
                if done:
                    oc = info.get("outcome")
                    wins += oc == "win"; losses += oc == "loss"; draws += oc == "draw"
                    win_hist.append(1 if oc == "win" else 0)
                    rew_hist.append(ep_r)
                    break
            if match % log_every == 0:
                wr = 100.0 * sum(win_hist) / max(1, len(win_hist))
                ar = sum(rew_hist) / max(1, len(rew_hist))
                mps = match / max(1e-6, time.time() - t0)
                ls = f" loss={last_loss:.3f}" if last_loss is not None else ""
                print(f"[train-sim] match {match}: winrate({log_every})={wr:4.0f}% avg_rew={ar:+.1f} "
                      f"eps={epsilon(step):.2f} replay={len(replay)} {mps:.1f} m/s "
                      f"total {wins}W-{losses}L-{draws}D{ls}", flush=True)
            if match % save_every == 0:
                save()
    except KeyboardInterrupt:
        pass
    finally:
        save()
        print(f"[train-sim] stopped after {match} match(es); saved -> {sim_path} "
              f"({wins}W-{losses}L-{draws}D)")
