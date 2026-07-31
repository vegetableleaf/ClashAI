r"""Headless RL training in the SIMULATOR (`run.py train-sim`), VECTORIZED.

Trains the SAME `PolicyNet`/DQN used live, against the fast headless engine (clashrl.sim) -- no vision,
no real-time waits, and (unlike live RL) FROM SCRATCH. Runs `--envs K` match instances that step
together and feed ONE learner: the network does a single BATCHED forward for all K envs' action choices
and one optimiser step per tick over a shared replay, so the GPU is used efficiently and K matches
progress at once. The checkpoint (`data/policy_sim.pt`) is a PRIOR: warm-start live RL from it, then
fine-tune on real matches. See icebow/DECK_SWITCH.md.

Note: single-process (Python GIL) -- the K engine steps run serially, so this is VECTORIZED (batched
inference + shared replay + sample diversity), not multi-core engine parallelism. The engine is cheap,
so the win is GPU amortisation + throughput. (Multiprocess actors could saturate all cores later.)

Usage (PowerShell), from icebow/:
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
    from .sim.opponents import SelfPlayOpponent, make_opponent

    K = max(1, int(envs if envs is not None else cfg.get("sim", "envs", default=8)))
    pool = [SimMatchEnv(cfg, seed=seed + i) for i in range(K)]
    e0 = pool[0]
    n_cards, n_cells, threat_dim = e0.n_cards, e0.n_cells, e0.threat_dim
    gw, gh = e0.gw, e0.gh
    device = _pick_device(cfg)
    net = _build_net(cfg, device, n_cards, n_cells, threat_dim)

    # DEPLOYABLE cell mask (impossible-coordinate fix, mirrors train_rl + play): anywhere cards
    # (rocket / miner) -> any cell; every other card only YOUR half. Applied before the cell argmax in
    # choose_batch / choose_greedy AND in the DDQN target, so the policy never selects (or bootstraps
    # from) an enemy-half cell that would just clamp / no-op.
    anywhere_ids = set(e0.anywhere_ids)
    yourhalf_mask = torch.tensor(e0.actions.deployable_mask(False), dtype=torch.bool, device=device)
    allcells_mask = torch.ones(n_cells, dtype=torch.bool, device=device)
    yourhalf_cells = [c for c in range(n_cells) if bool(yourhalf_mask[c])]
    anywhere_ids_t = torch.tensor(sorted(anywhere_ids), dtype=torch.long, device=device)

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
                    c = random.choice(in_hand)
                    cells = list(range(n_cells)) if c in anywhere_ids else (yourhalf_cells or list(range(n_cells)))
                    acts.append((1, c, random.choice(cells)))
                continue
            ci = int(cq[i].argmax())
            cmask = allcells_mask if ci in anywhere_ids else yourhalf_mask   # DEPLOYABLE cells for this card
            ceq_i = ceq[i].masked_fill(~cmask, float("-inf"))
            if gq[i, 0] >= gq[i, 1] + cq[i].max() + ceq_i.max():
                acts.append((0, 0, 0))
            else:
                acts.append((1, ci, int(ceq_i.argmax())))
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
            sel_card = cqn.argmax(1, keepdim=True)
            if anywhere_ids_t.numel():                          # DEPLOYABLE cells for the selected next-card
                any_next = (sel_card == anywhere_ids_t.view(1, -1)).any(1, keepdim=True)
            else:
                any_next = torch.zeros_like(sel_card, dtype=torch.bool)
            cellmask_next = torch.where(any_next, allcells_mask.unsqueeze(0), yourhalf_mask.unsqueeze(0))
            ceqn = ceqn.masked_fill(~cellmask_next, float("-inf"))
            sel_cell = ceqn.argmax(1, keepdim=True)
            play_next = (gqn[:, 1] + cqn.max(1).values + ceqn.max(1).values) > gqn[:, 0]
            cq2, ceq2, gq2 = target(nobs, nhand, nnxt, nelx, nthr)
            cq2 = cq2.masked_fill(nhand < 0.5, float("-inf"))
            ceq2 = ceq2.masked_fill(~cellmask_next, float("-inf"))
            q_play_next = gq2[:, 1] + cq2.gather(1, sel_card).squeeze(1) + ceq2.gather(1, sel_cell).squeeze(1)
            v_next = torch.where(play_next, q_play_next, gq2[:, 0])
            y = rew + gamma * v_next * (1.0 - done)
        loss = F.smooth_l1_loss(q_sa, y)
        opt.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(), grad_clip); opt.step()
        return float(loss.item())

    def save(path=None):
        p = path if path is not None else sim_path
        p.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"model": net.policy.state_dict(), "gate": net.gate.state_dict(),
                    "grid": [gw, gh], "n_cards": n_cards, "n_cells": n_cells,
                    "threat_dim": threat_dim, "deck": e0.deck_keys,
                    "arena_size": list(cfg.get("observation", "arena_size", default=[64, 96]))}, p)

    # -- self-play league --------------------------------------------------
    # Mix the scripted meta bots with a FROZEN past copy of the agent's own policy (a self-mirror,
    # see sim/opponents.SelfPlayOpponent). Snapshots go into a small league; each match reset picks a
    # league snapshot with prob `selfplay_prob` (ramped in over `selfplay_ramp_matches`), else a
    # scripted bot. Disabled with selfplay_prob <= 0 (then this is exactly the old scripted-only run).
    sp_prob = float(cfg.get("sim", "selfplay_prob", default=0.5))
    sp_ramp = int(cfg.get("sim", "selfplay_ramp_matches", default=5000))
    sp_snap_every = int(cfg.get("sim", "selfplay_snapshot_every", default=1000))
    sp_league_size = int(cfg.get("sim", "selfplay_league_size", default=5))
    keep_best = bool(cfg.get("sim", "selfplay_keep_best", default=True))
    league: deque = deque(maxlen=max(1, sp_league_size))
    _best_snap = {"net": None}       # a frozen copy of the BEST-benchmark policy (an always-available sparring partner)
    _prog = {"n": 0}

    def snapshot(store=True):
        snap = _build_net(cfg, device, n_cards, n_cells, threat_dim)
        snap.load_state_dict(net.state_dict())
        snap.eval()
        for p in snap.parameters():
            p.requires_grad_(False)
        if store:
            league.append(snap)
        return snap

    def sp_prob_now():
        return sp_prob if sp_ramp <= 0 else sp_prob * min(1.0, _prog["n"] / sp_ramp)

    def opponent_provider(env):
        snaps = list(league)
        if keep_best and _best_snap["net"] is not None:
            snaps.append(_best_snap["net"])          # spar against the BEST self, not only the degrading recent ones
        if sp_prob > 0 and snaps and random.random() < sp_prob_now():
            return SelfPlayOpponent(cfg, env, random.choice(snaps), env.rng)
        return make_opponent(cfg, env.db, env.rng, env.meta_pool)

    if sp_prob > 0:
        for e in pool:
            e.opponent_provider = opponent_provider
        if resume and sim_path.exists():
            seed = snapshot()                                    # a resumed policy seeds the league
            if keep_best:
                _best_snap["net"] = seed                         # ...and the best-self sparring slot
        print(f"[train-sim] self-play ON: prob {sp_prob:.2f} (ramp {sp_ramp} matches), "
              f"snapshot every {sp_snap_every}, league size {sp_league_size}"
              + (", +best-self" if keep_best else ""))

    # -- benchmark eval vs the FIXED scripted meta pool --------------------
    # A STABLE plateau signal (unlike the self-play win-rate, which self-references to ~50%): every
    # `eval_every_matches` run the GREEDY policy (no exploration, scripted opponents only) over a fixed
    # set of meta decks and report win-rate. Watch this curve flatten to judge when DDQN has topped out
    # (the PPO-integration trigger; see DECK_SWITCH.md). 0 = off.
    eval_every = int(cfg.get("sim", "eval_every_matches", default=500))
    eval_matches = int(cfg.get("sim", "eval_matches", default=24))
    eval_envs = min(K, max(1, int(cfg.get("sim", "eval_envs", default=4))))
    eval_pool = [SimMatchEnv(cfg, seed=100000 + i) for i in range(eval_envs)] if eval_every > 0 else []
    eval_hist: deque = deque(maxlen=max(1, int(cfg.get("sim", "eval_smooth_window", default=5))))
    eval_hist_fair: deque = deque(maxlen=eval_hist.maxlen)
    run_fair = bool(cfg.get("sim", "fair_eval", default=True))
    _fair_cfg = cfg.get("sim", "fair_eval_level", default=None)
    _agent_lv = list(e0.deck_card_levels) or [11]
    fair_level = int(_fair_cfg) if _fair_cfg else int(round(sum(_agent_lv) / len(_agent_lv)))
    _el = cfg.get("sim", "enemy_levels", default=[13, 14, 15, 16])
    ladder_lbl = f"L{min(_el)}-{max(_el)}"
    best_path = sim_path.with_name(sim_path.stem + "_best" + sim_path.suffix)   # keep the PEAK-benchmark policy
    best_wr = -1.0

    def choose_greedy(obs_b, hand_b, nxt_b, elx_b, thr_b):
        """Greedy action per env (no epsilon, no `random` draw, no replay) for benchmarking."""
        net.eval()
        obs_t = torch.stack([to_obs_t(o) for o in obs_b]); hand_t = torch.stack([to_vec_t(h) for h in hand_b])
        with torch.no_grad():
            cq, ceq, gq = net(obs_t, hand_t, torch.stack([to_vec_t(n) for n in nxt_b]),
                              torch.stack([to_vec_t(e) for e in elx_b]),
                              torch.stack([to_vec_t(t) for t in thr_b]))
        cq = cq.masked_fill(hand_t < 0.5, float("-inf"))
        acts = []
        for i in range(len(obs_b)):
            if not any(v > 0.5 for v in hand_b[i]):
                acts.append((0, 0, 0)); continue
            ci = int(cq[i].argmax())
            cmask = allcells_mask if ci in anywhere_ids else yourhalf_mask
            ceq_i = ceq[i].masked_fill(~cmask, float("-inf"))
            if gq[i, 0] >= gq[i, 1] + cq[i].max() + ceq_i.max():
                acts.append((0, 0, 0))
            else:
                acts.append((1, ci, int(ceq_i.argmax())))
        return acts

    def evaluate(fair=False):
        if not eval_pool:
            return None
        for j, e in enumerate(eval_pool):
            e.rng.seed(777 + j)          # SAME benchmark decks + engine rolls each eval (and across fair/ladder)
            if fair:                     # FAIR: same meta decks but enemy cards at YOUR level (handicap removed)
                e.opponent_provider = lambda env: make_opponent(cfg, env.db, env.rng, env.meta_pool, level=fair_level)
            else:
                e.opponent_provider = None   # rolled ladder levels (the handicapped benchmark)
        eo = [e.reset() for e in eval_pool]
        eh = [e.hand_vec.copy() for e in eval_pool]; en = [e.next_vec.copy() for e in eval_pool]
        ee = [e.elixir_vec.copy() for e in eval_pool]; et = [e.threat_vec.copy() for e in eval_pool]
        wins = played = 0
        while played < eval_matches:
            acts = choose_greedy(eo, eh, en, ee, et)
            for i, e in enumerate(eval_pool):
                nobs, _r, done, info = e.step(acts[i])
                if done:
                    wins += info.get("outcome") == "win"; played += 1
                    eo[i] = e.reset()
                else:
                    eo[i] = nobs
                eh[i], en[i] = e.hand_vec.copy(), e.next_vec.copy()
                ee[i], et[i] = e.elixir_vec.copy(), e.threat_vec.copy()
        return 100.0 * wins / max(1, played)

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
                    done_n += 1; _prog["n"] = done_n; ep_r[i] = 0.0
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
                    if sp_prob > 0 and done_n % sp_snap_every == 0:
                        snapshot()
                    if eval_every > 0 and done_n % eval_every == 0:
                        wr = evaluate(fair=False)
                        if wr is not None:
                            eval_hist.append(wr); smooth = sum(eval_hist) / len(eval_hist)
                            line = (f"[train-sim] EVAL @ {done_n}: ladder({ladder_lbl}) {wr:4.0f}% "
                                    f"(avg-{len(eval_hist)} {smooth:4.0f}%)")
                            if run_fair:
                                fwr = evaluate(fair=True)
                                eval_hist_fair.append(fwr); fsmooth = sum(eval_hist_fair) / len(eval_hist_fair)
                                line += (f" | fair(L{fair_level}) {fwr:4.0f}% "
                                         f"(avg-{len(eval_hist_fair)} {fsmooth:4.0f}%)")
                            print(line + f" | {eval_matches} matches each", flush=True)
                            if smooth > best_wr:                 # keep the PEAK policy (guards vs late-training decay)
                                best_wr = smooth
                                save(best_path)
                                if keep_best:                    # add the best self to the sparring league
                                    _best_snap["net"] = snapshot(store=False)
                                print(f"[train-sim] new BEST ladder avg {smooth:4.0f}% -> saved {best_path.name}",
                                      flush=True)
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
