r"""Headless RL training in the SIMULATOR (`run.py train-sim`), VECTORIZED.

Trains the SAME `PolicyNet`/DQN used live, against the fast headless engine (clashrl.sim) -- no vision,
no real-time waits, and (unlike live RL) FROM SCRATCH. Runs `--envs K` match instances that step
together and feed ONE learner: the network does a single BATCHED forward for all K envs' action choices
and one optimiser step per tick over a shared replay, so the GPU is used efficiently and K matches
progress at once. The checkpoint (`data/policy_sim.pt`) is a PRIOR: warm-start live RL from it, then
fine-tune on real matches. See real/DECK_SWITCH.md.

Note: single-process (Python GIL) -- the K engine steps run serially, so this is VECTORIZED (batched
inference + shared replay + sample diversity), not multi-core engine parallelism. The engine is cheap,
so the win is GPU amortisation + throughput. (Multiprocess actors could saturate all cores later.)

Usage (PowerShell), from real/:
    .\.venv\Scripts\python.exe run.py train-sim --matches 20000 --envs 16   # start (from scratch)
    .\.venv\Scripts\python.exe run.py train-sim --resume                    # continue policy_sim.pt
    #  ...watch the rolling win-rate; Ctrl+C stops + saves any time.
"""
from __future__ import annotations

import random
import signal
import time
from collections import deque

import numpy as np


def train_sim(cfg, matches: int = 2000, resume: bool = False, seed: int = 0, envs=None) -> None:
    try:
        import torch
        import torch.nn.functional as F
    except ImportError as exc:  # noqa: BLE001
        print(f"[train-sim] PyTorch required ({exc}). Install the CUDA build (see README).")
        return

    from .train_rl import _build_net, _pick_device
    from .sim.env import SimMatchEnv

    K = max(1, int(envs if envs is not None else cfg.get("sim", "envs", default=8)))
    pool = [SimMatchEnv(cfg, seed=seed + i) for i in range(K)]
    e0 = pool[0]
    n_cards, n_cells, threat_dim = e0.n_cards, e0.n_cells, e0.threat_dim
    gw, gh = e0.gw, e0.gh
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

    def to_obs_t(o):
        return torch.from_numpy(o).float().permute(2, 0, 1).to(device) / 255.0

    def to_vec_t(v):
        return torch.from_numpy(np.asarray(v, np.float32)).to(device)

    def choose_batch(obs_b, hand_b, nxt_b, elx_b, thr_b, eps):
        """One batched forward for all K envs; per-env epsilon-greedy with its own hand mask/elixir."""
        net.eval()
        obs_t = torch.stack([to_obs_t(o) for o in obs_b])
        hand_t = torch.stack([to_vec_t(h) for h in hand_b])
        with torch.no_grad():
            cq, ceq, gq = net(obs_t, hand_t, torch.stack([to_vec_t(n) for n in nxt_b]),
                              torch.stack([to_vec_t(e) for e in elx_b]),
                              torch.stack([to_vec_t(t) for t in thr_b]))
        cq = cq.masked_fill(hand_t < 0.5, float("-inf"))
        acts = []
        for i in range(len(obs_b)):
            in_hand = [j for j, v in enumerate(hand_b[i]) if v > 0.5]
            if not in_hand:
                acts.append((0, 0, 0)); continue
            if random.random() < eps:
                if pool[i].elixir < min_play_elixir or random.random() < wait_prob:
                    acts.append((0, 0, 0))
                else:
                    acts.append((1, random.choice(in_hand), random.randrange(n_cells)))
                continue
            if gq[i, 0] >= gq[i, 1] + cq[i].max() + ceq[i].max():
                acts.append((0, 0, 0))
            else:
                acts.append((1, int(cq[i].argmax()), int(ceq[i].argmax())))
        return acts

    def optimise():
        if len(replay) < max(min_replay, batch_size):
            return None
        b = random.sample(replay, batch_size)
        obs = torch.stack([to_obs_t(x[0]) for x in b]); hand = torch.stack([to_vec_t(x[1]) for x in b])
        nobs = torch.stack([to_obs_t(x[5]) for x in b]); nhand = torch.stack([to_vec_t(x[6]) for x in b])
        nxt = torch.stack([to_vec_t(x[7]) for x in b]); nnxt = torch.stack([to_vec_t(x[8]) for x in b])
        elx = torch.stack([to_vec_t(x[9]) for x in b]); nelx = torch.stack([to_vec_t(x[10]) for x in b])
        thr = torch.stack([to_vec_t(x[11]) for x in b]); nthr = torch.stack([to_vec_t(x[12]) for x in b])
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
                    "threat_dim": threat_dim, "deck": e0.deck_keys,
                    "arena_size": list(cfg.get("observation", "arena_size", default=[64, 96]))}, sim_path)

    # per-env current state
    cobs = [e.reset() for e in pool]
    chand = [e.hand_vec.copy() for e in pool]; cnxt = [e.next_vec.copy() for e in pool]
    celx = [e.elixir_vec.copy() for e in pool]; cthr = [e.threat_vec.copy() for e in pool]
    ep_r = [0.0] * K

    running = {"v": True}
    signal.signal(signal.SIGINT, lambda *_a: running.update(v=False))
    print(f"[train-sim] {device}: {K} vectorized env(s), up to {matches} matches "
          f"(cards={n_cards}, cells={n_cells}). Ctrl+C to stop + save.")
    step = 0
    done_n = wins = losses = draws = 0
    win_hist: deque = deque(maxlen=max(log_every, 50))
    rew_hist: deque = deque(maxlen=max(log_every, 50))
    last_loss = None
    t0 = time.time()
    try:
        while running["v"] and done_n < matches:
            eps = epsilon(step)
            acts = choose_batch(cobs, chand, cnxt, celx, cthr, eps)
            for i, env in enumerate(pool):
                nobs, reward, done, info = env.step(acts[i])
                nhand, nnxt = env.hand_vec.copy(), env.next_vec.copy()
                nelx, nthr = env.elixir_vec.copy(), env.threat_vec.copy()
                replay.append((cobs[i], chand[i], acts[i], reward, float(done),
                               nobs, nhand, cnxt[i], nnxt, celx[i], nelx, cthr[i], nthr))
                ep_r[i] += reward
                if done:
                    oc = info.get("outcome")
                    wins += oc == "win"; losses += oc == "loss"; draws += oc == "draw"
                    win_hist.append(1 if oc == "win" else 0); rew_hist.append(ep_r[i])
                    done_n += 1; ep_r[i] = 0.0
                    cobs[i] = env.reset()
                    chand[i], cnxt[i] = env.hand_vec.copy(), env.next_vec.copy()
                    celx[i], cthr[i] = env.elixir_vec.copy(), env.threat_vec.copy()
                    if done_n % log_every == 0:
                        wr = 100.0 * sum(win_hist) / max(1, len(win_hist))
                        ar = sum(rew_hist) / max(1, len(rew_hist))
                        mps = done_n / max(1e-6, time.time() - t0)
                        ls = f" loss={last_loss:.3f}" if last_loss is not None else ""
                        print(f"[train-sim] {done_n} matches: winrate={wr:4.0f}% avg_rew={ar:+.1f} "
                              f"eps={eps:.2f} replay={len(replay)} {mps:.1f} m/s "
                              f"total {wins}W-{losses}L-{draws}D{ls}", flush=True)
                    if done_n % save_every == 0:
                        save()
                else:
                    cobs[i] = nobs; chand[i], cnxt[i] = nhand, nnxt
                    celx[i], cthr[i] = nelx, nthr
            loss = optimise()
            if loss is not None:
                last_loss = loss
            step += 1
            if step % target_sync == 0:
                target.load_state_dict(net.state_dict())
    except KeyboardInterrupt:
        pass
    finally:
        save()
        print(f"[train-sim] stopped after {done_n} match(es); saved -> {sim_path} "
              f"({wins}W-{losses}L-{draws}D)")
