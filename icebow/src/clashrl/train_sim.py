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

Throughput: host->device transfers are BATCHED (one copy per batch, uint8 converted on the GPU),
which measured ~2x end-to-end vs the per-sample form. Raising --envs amortises the optimiser step
over more matches and measured 2.30 / 3.33 / 4.60 / 4.76 matches/s at 8 / 16 / 32 / 48 envs on a
RTX 3070 -- flattening out because the engine steps still share one core. `run.py sim-bench`
re-measures both on your machine.

Usage (PowerShell), from icebow/:
    .\.venv\Scripts\python.exe run.py train-sim --matches 20000 --envs 16   # start (from scratch)
    .\.venv\Scripts\python.exe run.py train-sim --resume                    # continue policy_sim.pt
    #  ...watch the rolling win-rate; Ctrl+C stops + saves any time.
"""
from __future__ import annotations

import math
import random
import signal
import time
from collections import deque

import numpy as np


def pfsp_weights(snaps, power: float, floor: float = 0.05, min_games: int = 5):
    """Tier-2 PFSP 'hard-opponent' weights: each league snapshot weighs (1 - winrate_vs_it)^power
    (+ a floor so nothing starves) -- sparring time concentrates on the past selves that BEAT the
    current policy instead of uniformly re-farming beaten ones, which is where the learning signal
    is. Snapshots with fewer than `min_games` recorded matches count as winrate 0.5 (unknown =
    medium priority). Reads each snapshot's `._pfsp` rolling record (1 win / 0.5 draw / 0 loss)."""
    w = []
    for s in snaps:
        rec = getattr(s, "_pfsp", None)
        wr = (sum(rec) / len(rec)) if rec and len(rec) >= min_games else 0.5
        w.append(max(floor, (1.0 - wr) ** power))
    return w


def train_sim(cfg, matches: int = 2000, resume: bool = False, seed: int = 0, envs=None,
              time_limit_s=None, quiet: bool = False):
    """Train in the simulator. Returns a {matches, seconds, mps} summary.

    `time_limit_s` stops the run after N wall-clock seconds (the same save path as
    Ctrl+C) -- that is what `sim-bench` uses to time identical work at different
    `--envs`; None keeps the old behaviour of running until `matches`.
    """
    try:
        import torch
        import torch.nn.functional as F
    except ImportError as exc:  # noqa: BLE001
        print(f"[train-sim] PyTorch required ({exc}). Install the CUDA build (see README).")
        return None

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
    # per-card elixir costs: greedy + random picks are masked to AFFORDABLE cards (an unaffordable
    # pick just no-ops in the env = a wasted turn -- the eval audit showed rejected tornado attempts)
    card_costs = [float(s.elixir) for s in e0.specs]
    card_costs_t = torch.tensor(card_costs, dtype=torch.float32, device=device)
    # count-based exploration: play counts per card id (starts at 1; inverse-sqrt weights the random
    # branch toward under-played cards so situational tools -- tornado -- actually get trialled)
    count_explore = bool(cfg.get("sim", "explore_count_based", default=True))
    play_counts = [1.0] * n_cards

    sim_path = cfg.path(cfg.get("train", "sim_checkpoint", default="data/policy_sim.pt"))
    resumed_best_wr = -1.0                                    # prior peak benchmark (so --resume won't clobber a better best.pt)
    if resume and sim_path.exists():
        ck = torch.load(sim_path, map_location="cpu", weights_only=False)
        net.policy.load_state_dict(ck["model"])
        if "gate" in ck:
            net.gate.load_state_dict(ck["gate"])
        resumed_best_wr = float(ck.get("best_wr", -1.0))
        if not quiet:
            print(f"[train-sim] resumed {sim_path.name}"
                  + (f" (best so far {resumed_best_wr:.0f}%)" if resumed_best_wr >= 0
                     else " (no stored best -- back up policy_sim_best.pt once before relying on it)"))
    elif not quiet:
        print(f"[train-sim] training FROM SCRATCH ({sim_path.name} will be written)")
    target = _build_net(cfg, device, n_cards, n_cells, threat_dim)
    target.load_state_dict(net.state_dict())
    target.eval()

    gamma = float(cfg.get("train", "gamma", default=0.99))
    n_step = max(1, int(cfg.get("train", "n_step", default=3)))
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

    class _NStep:
        """Per-env N-STEP return aggregator = stronger CAUSE-AND-EFFECT credit assignment. A 1-step TD
        target credits an action only with its IMMEDIATE reward + a bootstrap, so a consequence that
        lands a few seconds later (overspend -> undefendable counter-push -> tower damage) crawls back
        one update at a time. With n-step, each stored transition's target contains the next n REAL
        rewards (R = sum gamma^j r_j) + the bootstrap n states ahead -- the punishment arrives INSIDE
        the causing action's learning target. Emits the same replay tuple + gpow (= gamma^k, k = the
        actual horizon: n normally, shorter on a terminal flush). n=1 reproduces the old behaviour."""

        def __init__(self, n: int, g: float):
            self.n, self.g, self.buf = n, g, []

        def _emit(self, k: int, nstate, done_f: float):
            (obs, hand, nxtv, elx, thr), act, _ = self.buf[0]
            r_acc = sum((self.g ** j) * self.buf[j][2] for j in range(k))
            nobs, nhand, nnxtv, nelx, nthr = nstate
            return (obs, hand, act, r_acc, done_f, nobs, nhand, nxtv, nnxtv, elx, nelx, thr, nthr,
                    self.g ** k)

        def push(self, state, act, r: float, nstate, done: bool):
            """Add one raw transition; return the list of AGGREGATED transitions ready for the replay."""
            self.buf.append((state, act, float(r)))
            out = []
            if not done and len(self.buf) >= self.n:
                out.append(self._emit(self.n, nstate, 0.0))
                self.buf.pop(0)
            if done:                                   # terminal: flush the whole window against the end state
                while self.buf:
                    out.append(self._emit(len(self.buf), nstate, 1.0))
                    self.buf.pop(0)
            return out

    def epsilon(s):
        return eps_end if s >= eps_steps else eps_start + (eps_end - eps_start) * (s / eps_steps)

    # BATCHED host->device transfer. Converting per sample issues one CUDA copy per element:
    # K per action choice and 2*batch_size per optimiser step (obs + next-obs), which at
    # batch 64 is 128 tiny transfers whose launch overhead dwarfs the payload. Stacking first
    # means ONE copy, and the uint8 frame is converted to float ON the GPU, so a quarter of
    # the bytes crosses PCIe. Mathematically identical to the per-sample form.
    def obs_batch(obs_list):
        return (torch.from_numpy(np.stack(obs_list)).to(device)
                .permute(0, 3, 1, 2).float() / 255.0)

    def vec_batch(vec_list):
        return torch.from_numpy(np.stack([np.asarray(v, np.float32) for v in vec_list])).to(device)

    def choose_batch(obs_b, hand_b, nxt_b, elx_b, thr_b, eps):
        """One batched forward for all K envs; per-env epsilon-greedy with its own hand mask/elixir."""
        net.eval()
        obs_t = obs_batch(obs_b)
        hand_t = vec_batch(hand_b)
        with torch.no_grad():
            cq, ceq, gq = net(obs_t, hand_t, vec_batch(nxt_b), vec_batch(elx_b), vec_batch(thr_b))
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
                    playable = [j for j in in_hand if card_costs[j] <= pool[i].elixir + 1e-6]
                    if not playable:
                        acts.append((0, 0, 0)); continue
                    if count_explore:
                        # COUNT-BASED exploration: weight random picks toward UNDER-PLAYED cards
                        # (inverse-sqrt of play count). Rarely-chosen situational cards (tornado!)
                        # get their trials; without this, uniform-random exploration almost never
                        # strings the rare pull + follow-up sequences their value lives in.
                        wts = [1.0 / math.sqrt(play_counts[j]) for j in playable]
                        c = random.choices(playable, weights=wts, k=1)[0]
                    else:
                        c = random.choice(playable)
                    play_counts[c] += 1.0
                    cells = list(range(n_cells)) if c in anywhere_ids else (yourhalf_cells or list(range(n_cells)))
                    acts.append((1, c, random.choice(cells)))
                continue
            # greedy: only cards that are in hand AND affordable (an unaffordable pick just no-ops in
            # the env = a wasted turn the policy can't learn from)
            cq_i = cq[i].masked_fill(card_costs_t > pool[i].elixir + 1e-6, float("-inf"))
            if not torch.isfinite(cq_i).any():
                acts.append((0, 0, 0)); continue
            ci = int(cq_i.argmax())
            cmask = allcells_mask if ci in anywhere_ids else yourhalf_mask   # DEPLOYABLE cells for this card
            ceq_i = ceq[i].masked_fill(~cmask, float("-inf"))
            if gq[i, 0] >= gq[i, 1] + cq_i.max() + ceq_i.max():
                acts.append((0, 0, 0))
            else:
                play_counts[ci] += 1.0
                acts.append((1, ci, int(ceq_i.argmax())))
        return acts

    def optimise():
        if len(replay) < max(min_replay, batch_size):
            return None
        b = random.sample(replay, batch_size)
        obs = obs_batch([x[0] for x in b]); hand = vec_batch([x[1] for x in b])
        nobs = obs_batch([x[5] for x in b]); nhand = vec_batch([x[6] for x in b])
        nxt = vec_batch([x[7] for x in b]); nnxt = vec_batch([x[8] for x in b])
        elx = vec_batch([x[9] for x in b]); nelx = vec_batch([x[10] for x in b])
        thr = vec_batch([x[11] for x in b]); nthr = vec_batch([x[12] for x in b])
        play = torch.tensor([x[2][0] for x in b], device=device)
        card = torch.tensor([x[2][1] for x in b], device=device).unsqueeze(1)
        cell = torch.tensor([x[2][2] for x in b], device=device).unsqueeze(1)
        rew = torch.tensor([x[3] for x in b], dtype=torch.float32, device=device)
        done = torch.tensor([x[4] for x in b], dtype=torch.float32, device=device)
        gpow = torch.tensor([x[13] for x in b], dtype=torch.float32, device=device)  # gamma^k of each n-step return

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
            y = rew + gpow * v_next * (1.0 - done)     # n-step: rew = sum gamma^j r_j, bootstrap gamma^k ahead
        loss = F.smooth_l1_loss(q_sa, y)
        opt.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(), grad_clip); opt.step()
        return float(loss.item())

    def save(path=None):
        p = path if path is not None else sim_path
        p.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"model": net.policy.state_dict(), "gate": net.gate.state_dict(),
                    "grid": [gw, gh], "n_cards": n_cards, "n_cells": n_cells,
                    "threat_dim": threat_dim, "deck": e0.deck_keys, "best_wr": best_wr,
                    "matches": done_n,     # matches played when this file was written (checkpoint inventory)
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
    pfsp_on = bool(cfg.get("sim", "selfplay_pfsp", default=True))
    pfsp_power = float(cfg.get("sim", "selfplay_pfsp_power", default=2.0))
    league: deque = deque(maxlen=max(1, sp_league_size))
    _best_snap = {"net": None}       # a frozen copy of the BEST-benchmark policy (an always-available sparring partner)
    _prog = {"n": 0}

    def snapshot(store=True):
        snap = _build_net(cfg, device, n_cards, n_cells, threat_dim)
        snap.load_state_dict(net.state_dict())
        snap.eval()
        for p in snap.parameters():
            p.requires_grad_(False)
        snap._pfsp = deque(maxlen=40)    # recent results vs this snapshot (1 win / 0.5 draw / 0 loss)
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
            if pfsp_on and len(snaps) > 1:            # Tier-2 PFSP: prefer the snapshots that BEAT us
                pick = random.choices(snaps, weights=pfsp_weights(snaps, pfsp_power), k=1)[0]
            else:
                pick = random.choice(snaps)
            return SelfPlayOpponent(cfg, env, pick, env.rng)
        # TRAINING scripted bots may be ADAPTIVE (anti-siege / counter-hold / punish / split-push);
        # the eval benchmark never sets this flag, so eval curves stay comparable across runs.
        return make_opponent(cfg, env.db, env.rng, env.meta_pool, adaptive=True)

    if sp_prob > 0:
        for e in pool:
            e.opponent_provider = opponent_provider
        if resume and sim_path.exists():
            seed = snapshot()                                    # a resumed policy seeds the league
            if keep_best:
                _best_snap["net"] = seed                         # ...and the best-self sparring slot
        if not quiet:
            print(f"[train-sim] self-play ON: prob {sp_prob:.2f} (ramp {sp_ramp} matches), "
                  f"snapshot every {sp_snap_every}, league size {sp_league_size}"
                  + (", +best-self" if keep_best else "")
                  + (f", PFSP p={pfsp_power:g}" if pfsp_on else ""))

    # -- benchmark eval vs the FIXED scripted meta pool --------------------
    # A STABLE plateau signal (unlike the self-play win-rate, which self-references to ~50%): every
    # `eval_every_matches` run the GREEDY policy (no exploration, scripted opponents only) over a fixed
    # set of meta decks and report win-rate. Watch this curve flatten to judge when DDQN has topped out
    # (the PPO-integration trigger; see DECK_SWITCH.md). 0 = off.
    eval_every = int(cfg.get("sim", "eval_every_matches", default=500))
    eval_matches = int(cfg.get("sim", "eval_matches", default=24))
    eval_envs = min(K, max(1, int(cfg.get("sim", "eval_envs", default=4))))
    eval_pool = [SimMatchEnv(cfg, seed=100000 + i) for i in range(eval_envs)] if eval_every > 0 else []
    for _e in eval_pool:
        _e.domain_rand.enabled = False     # the BENCHMARK renders canonical: comparable + noise-free
        _e.domain_rand.resample()
    eval_hist: deque = deque(maxlen=max(1, int(cfg.get("sim", "eval_smooth_window", default=5))))
    eval_hist_fair: deque = deque(maxlen=eval_hist.maxlen)
    run_fair = bool(cfg.get("sim", "fair_eval", default=True))
    _fair_cfg = cfg.get("sim", "fair_eval_level", default=None)
    _agent_lv = list(e0.deck_card_levels) or [11]
    fair_level = int(_fair_cfg) if _fair_cfg else int(round(sum(_agent_lv) / len(_agent_lv)))
    _el = cfg.get("sim", "enemy_levels", default=[13, 14, 15, 16])
    ladder_lbl = f"L{min(_el)}-{max(_el)}"
    best_path = sim_path.with_name(sim_path.stem + "_best" + sim_path.suffix)   # keep the PEAK-benchmark policy
    best_wr = resumed_best_wr                                                   # remember the prior peak across --resume (won't clobber a better best.pt)

    def choose_greedy(obs_b, hand_b, nxt_b, elx_b, thr_b):
        """Greedy action per env (no epsilon, no `random` draw, no replay) for benchmarking."""
        net.eval()
        obs_t = obs_batch(obs_b); hand_t = vec_batch(hand_b)
        with torch.no_grad():
            cq, ceq, gq = net(obs_t, hand_t, vec_batch(nxt_b), vec_batch(elx_b), vec_batch(thr_b))
        cq = cq.masked_fill(hand_t < 0.5, float("-inf"))
        acts = []
        for i in range(len(obs_b)):
            if not any(v > 0.5 for v in hand_b[i]):
                acts.append((0, 0, 0)); continue
            cq_i = cq[i].masked_fill(card_costs_t > eval_pool[i].elixir + 1e-6, float("-inf"))
            if not torch.isfinite(cq_i).any():                   # nothing affordable -> wait
                acts.append((0, 0, 0)); continue
            ci = int(cq_i.argmax())
            cmask = allcells_mask if ci in anywhere_ids else yourhalf_mask
            ceq_i = ceq[i].masked_fill(~cmask, float("-inf"))
            if gq[i, 0] >= gq[i, 1] + cq_i.max() + ceq_i.max():
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
    nstep = [_NStep(n_step, gamma) for _ in range(K)]   # per-env n-step return aggregators

    running = {"v": True}
    try:
        signal.signal(signal.SIGINT, lambda *_a: running.update(v=False))
    except ValueError:                                 # called from a worker thread (sim-bench)
        pass
    if not quiet:
        print(f"[train-sim] {device}: {K} vectorized env(s), up to {matches} matches "
              f"(cards={n_cards}, cells={n_cells})"
              + (f", time limit {time_limit_s:.0f}s" if time_limit_s else "")
              + ". Ctrl+C to stop + save.")
    step = 0
    done_n = wins = losses = draws = 0
    win_hist: deque = deque(maxlen=max(log_every, 50))
    rew_hist: deque = deque(maxlen=max(log_every, 50))
    last_loss = None
    t0 = time.time()
    deadline = (t0 + float(time_limit_s)) if time_limit_s else None
    try:
        while running["v"] and done_n < matches:
            if deadline is not None and time.time() >= deadline:
                break
            eps = epsilon(step)
            acts = choose_batch(cobs, chand, cnxt, celx, cthr, eps)
            for i, env in enumerate(pool):
                nobs, reward, done, info = env.step(acts[i])
                nhand, nnxt = env.hand_vec.copy(), env.next_vec.copy()
                nelx, nthr = env.elixir_vec.copy(), env.threat_vec.copy()
                for tr in nstep[i].push((cobs[i], chand[i], cnxt[i], celx[i], cthr[i]), acts[i],
                                        reward, (nobs, nhand, nnxt, nelx, nthr), bool(done)):
                    replay.append(tr)
                ep_r[i] += reward
                if done:
                    oc = info.get("outcome")
                    # Tier-2 PFSP: attribute the result to the league snapshot that piloted the opponent
                    # (BEFORE reset() replaces env.opponent) -- its rolling record drives the sampling.
                    opp = getattr(env, "opponent", None)
                    if isinstance(opp, SelfPlayOpponent) and hasattr(opp.net, "_pfsp"):
                        opp.net._pfsp.append(1.0 if oc == "win" else (0.5 if oc == "draw" else 0.0))
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
                            # Keep the PEAK policy (guards vs late-training decay) -- but only once the
                            # smoothing window has >=3 points: eval_hist restarts EMPTY on every --resume,
                            # so an avg-1/avg-2 print is a single noisy eval (+-4pp) wearing an "avg" label,
                            # and banking it freezes best.pt at an inflated bar no honest avg-5 can beat
                            # (measured: a resume banked avg-1 88% while the true plateau was ~80%).
                            if smooth > best_wr and len(eval_hist) >= min(3, eval_hist.maxlen):
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
        secs = time.time() - t0
        if not quiet:
            print(f"[train-sim] stopped after {done_n} match(es); saved -> {sim_path} "
                  f"({wins}W-{losses}L-{draws}D)")
    return {"matches": done_n, "seconds": secs, "mps": done_n / max(1e-6, secs),
            "steps": step, "envs": K, "wins": wins, "losses": losses, "draws": draws}
