r"""PPO training in the SIMULATOR (`run.py train-sim-ppo`), VECTORIZED.

The on-policy sibling of train_sim.py's Double-DQN: the SAME PolicyNet trunk + card/cell/gate heads
are read as LOGITS of a factored categorical policy (gate -> card -> cell), a small VALUE head is
added for GAE, and updates use the PPO clipped surrogate. Built once the DDQN benchmark plateaued
(~83/84 avg-5) as the documented "PPO era" candidate: clip + GAE attack the chronic value-oscillation
pathology and the stochastic policy explores the 432-cell action space better than epsilon-greedy.

Everything AROUND the algorithm is deliberately identical to train_sim.py so curves are comparable:
the frozen scripted eval benchmark (ladder + fair, re-seeded 777+j), eval smoothing + keep-best (min
3-window), the PFSP self-play league (snapshots are DQN-class wrappers so SelfPlayOpponent works
unchanged; tagged `_ppo` so its greedy gate compares LOGITS, not summed Q), adaptive training bots,
domain randomization (eval canonical), and the deployable/affordable masks.

Checkpoints go to train.sim_ppo_checkpoint (data/policy_sim_ppo.pt) + a _best twin -- the DDQN
policy_sim.pt / policy_sim_best.pt baseline is NEVER touched. The saved dict keeps the standard
keys (model/gate/grid/...) plus "value" + algo="ppo", so play.py can deploy it live (its greedy
gate branches on the algo tag).

Usage (PowerShell), from icebow/:
    .\.venv\Scripts\python.exe run.py train-sim-ppo --matches 200000 --envs 32          # from scratch
    .\.venv\Scripts\python.exe run.py train-sim-ppo --resume                            # continue
    .\.venv\Scripts\python.exe run.py train-sim-ppo --init data\policy_sim_best.pt ...  # warm-start
"""
from __future__ import annotations

import random
import signal
import time
from collections import deque
from pathlib import Path

import numpy as np

from .ppo_monitor import should_intervene  # noqa: F401  (kept importable for offline analysis;
# the automatic stop it used to drive was REMOVED -- it fired far too eagerly on ordinary early-training
# dips and killed healthy runs. Diagnose plateaus from the printed winrate/eval curve instead.)

_NEG = -1e9   # finite mask value (avoids -inf NaNs through log_softmax / entropy)


def compute_gae(rew, val, done, boot, gamma: float, lam: float, trunc=None):
    """Generalized Advantage Estimation over a [T][K] rollout grid.

    rew/val/done: length-T sequences of K-sized float arrays; boot: [K] bootstrap values for the
    states AFTER the last step. Returns (adv, ret) as [T, K] float32 (ret = adv + val).

    TERMINAL vs TRUNCATED, and the difference is not cosmetic. A match that ENDS is terminal: the
    future really is worth nothing, so the bootstrap is 0. An episode that was CUT SHORT -- a drill
    whose predicate fired or whose time limit elapsed -- is truncated: the position was still worth
    something, and telling the critic it was worth zero is a lie about an ordinary mid-match state.

    Drills are played on the same state space as matches, so before this split every drill ending
    asserted "this position is terminal and worth 0" and `delta` collapsed to `rew - val[t]` -- a
    large negative wherever the critic had (correctly) valued the state above the drill's small
    payoff. At drill_frac 0.4 that was 40% of episodes, which is why a higher drill mix made the
    run worse rather than better.

    `trunc` marks those steps. V(s_final) would need a forward pass on an observation the auto-reset
    has already discarded, so V(s_t) stands in for it -- one decision apart, and a far better
    estimate than zero. The GAE trace is cut at BOTH kinds of ending, because the next step belongs
    to a different episode either way.
    """
    T = len(rew)
    K = len(boot)
    adv = np.zeros((T, K), np.float32)
    last = np.zeros(K, np.float32)
    for t in reversed(range(T)):
        nxt_v = boot if t == T - 1 else val[t + 1]
        ended = np.asarray(done[t], np.float32)
        cut = np.zeros(K, np.float32) if trunc is None else np.asarray(trunc[t], np.float32)
        # bootstrap: 0 at a true terminal, V(s_t) at a truncation, V(s_next) mid-episode
        v_next = np.where(cut > 0.5, np.asarray(val[t], np.float32),
                          np.asarray(nxt_v, np.float32) * (1.0 - ended))
        delta = np.asarray(rew[t], np.float32) + gamma * v_next - np.asarray(val[t], np.float32)
        last = delta + gamma * lam * (1.0 - ended) * last     # trace cut at ANY episode boundary
        adv[t] = last
    ret = adv + np.asarray(val, np.float32)
    return adv, ret


def train_sim_ppo(cfg, matches: int = 2000, resume: bool = False, seed: int = 0, envs=None,
                  init: str | None = None, device: str | None = None,
                  reset_gate: bool = False, workers: int = 0) -> None:
    try:
        import torch
        import torch.nn as nn
        import torch.nn.functional as F
    except ImportError as exc:  # noqa: BLE001
        print(f"[train-sim-ppo] PyTorch required ({exc}). Install the CUDA build (see README).")
        return

    from .model import PolicyNet
    from .train_rl import _build_net, _pick_device
    from .wincon_bank import apply_wincon_bank
    from .train_sim import pfsp_weights
    from .sim.env import SimMatchEnv
    from .sim.opponents import SelfPlayOpponent, make_opponent

    K = max(1, int(envs if envs is not None else cfg.get("sim", "envs", default=8)))
    # ⚠ `is not None`, NOT truthiness. `--workers 0` is FALSY, so `workers if workers else ...`
    # silently replaced an explicit 0 with sim.rollout_workers, took the REMOTE path, and made
    # "in-process, no workers" unreachable from the CLI -- a banner asserting one thing while the
    # counters said another. Same family as `--drill-frac 0.0`.
    workers = int(workers if workers is not None
                  else cfg.get("sim", "rollout_workers", default=0))
    remote = workers > 1
    if remote:
        # SUBPROCESS ENGINE SHARDS (2026-08-14): the pure-Python engine is one core per process,
        # so rollouts run in `workers` child processes while this process keeps the batched
        # action selection + PPO updates. The parent pins its own torch threads low -- the old
        # 16-thread pool burned ~7 cores of churn on these tiny tensors (measured).
        import torch as _t
        _t.set_num_threads(max(2, 4))
        from .sim.remote_pool import RemotePool
        # ALWAYS PASS THE RESOLVED FLOAT. `float(...) or None` was here, and `0.0 or None`
        # is None -- RemotePool's "no override, re-read config.yaml in the worker" sentinel --
        # so an explicit 0.0 evaporated on the way out and each worker went back to disk. Fixed
        # in icebow when it cost two `--drill-frac 0.0` runs (HANDOFF §3q); a no-op while disk
        # and parent agree, which is why it survived here unnoticed.
        rpool = RemotePool(
            K, workers, seed=seed,
            drill_frac=float(cfg.get("sim", "drill_frac", default=0.0)),
            # the same rule for the spell veto: a resolved float, never a sentinel, so the
            # workers refuse exactly what this process thinks they refuse (ruling 30).
            spell_min_value=float(cfg.get("sim", "ppo_spell_min_value", default=0.0)))
        pool = []                                   # rollout envs live in the workers
        e0 = SimMatchEnv(cfg, seed=seed + 10_000)   # local metadata/mask twin (never stepped)
        print(f"[train-sim-ppo] ROLLOUT WORKERS: {len(rpool.procs)} processes x "
              f"~{K // max(1, len(rpool.procs))} envs (K={K}); learner stays in-parent")
    else:
        rpool = None
        # through the drill factory: a plain SimMatchEnv unless sim.drill_frac asks for a mix
        from .sim.drill_env import make_train_env
        pool = [make_train_env(cfg, seed=seed + i) for i in range(K)]
        e0 = pool[0]
    n_cards, n_cells, threat_dim = e0.n_cards, e0.n_cells, e0.threat_dim
    in_ch = int(e0.obs_shape[2])      # 3 (RGB) or 3 + the semantic canvas (observation.use_detector_canvas)
    gw, gh = e0.gw, e0.gh
    # MEASURED 2026-08-08: this trainer is FASTER ON CPU -- 1.0 match/s vs 0.2 on the GPU while a
    # detector run shared it. The match engine is pure Python (CPU-bound whatever the net does) and
    # the policy is ~2 MB, so every tiny forward pass pays more in kernel-launch + transfer overhead
    # than it saves, and it also competes for VRAM. `--device cpu` therefore both speeds this up and
    # lets it run alongside a detector train without an OOM risk.
    device = torch.device(device) if device else _pick_device(cfg)

    class PPONet(nn.Module):
        """Actor-critic over the SAME PolicyNet trunk/heads the DQN uses (logits, not Q) + a value head."""

        def __init__(self):
            super().__init__()
            self.policy = PolicyNet(in_ch, n_cards, n_cells, threat_dim=threat_dim)
            self.gate = nn.Linear(self.policy.embed_dim, 2)    # [wait, play] logits
            self.value = nn.Linear(self.policy.embed_dim, 1)   # V(s) for GAE

        def forward(self, x, hand, nxt=None, elx=None, thr=None):
            z, cards, cells = self.policy.forward_parts(x, hand, nxt, elx, thr)
            return cards, cells, self.gate(z), self.value(z).squeeze(-1)

    net = PPONet().to(device)

    # masks shared with train_sim: anywhere cards -> all cells, else YOUR half; affordability by cost
    anywhere_ids = set(e0.anywhere_ids)
    yourhalf_mask = torch.tensor(e0.actions.deployable_mask(False), dtype=torch.bool, device=device)
    allcells_mask = torch.ones(n_cells, dtype=torch.bool, device=device)
    anywhere_ids_t = torch.tensor(sorted(anywhere_ids), dtype=torch.long, device=device)
    card_costs_t = torch.tensor([float(s.elixir) for s in e0.specs], dtype=torch.float32, device=device)
    # WIN-CONDITION BANK: the deck's win conditions (sim.wincon_cards) and the elixir needed for the
    # cheapest of them. bank_floor 0 disables the rule entirely (the original always-affordable mask).
    wincon_ids = sorted(e0.wincon_ids)
    wincon_ids_t = torch.tensor(wincon_ids, dtype=torch.long, device=device)
    wincon_cost = min((float(e0.specs[i].elixir) for i in wincon_ids), default=0.0)
    bank_floor = float(cfg.get("sim", "wincon_bank_floor", default=0.0)) if wincon_ids else 0.0
    if bank_floor > 0.0:
        print(f"[train-sim-ppo] win-condition bank ON: holding {wincon_cost:.0f}-elixir "
              f"{'/'.join(e0.deck_keys[i] for i in wincon_ids)} masks cheaper cards from "
              f"{bank_floor:.0f} elixir up, so the bar can actually reach them")

    ppo_path = cfg.path(cfg.get("train", "sim_ppo_checkpoint", default="data/policy_sim_ppo.pt"))
    resumed_best_wr = -1.0
    warm_loaded = False
    # RESUME only into a MATCHING architecture. Flipping observation.use_detector_canvas changes the
    # image width (3 -> 9), so an older checkpoint's conv1 cannot load -- and because the watchdog
    # relaunches this trainer with --resume, a hard failure here would crash-loop instead of
    # training. Fall through to a fresh run and say so.
    _ck_probe = torch.load(ppo_path, map_location="cpu") if (resume and ppo_path.exists()) else {}
    stale_resume = (resume and ppo_path.exists()
                    and (int(_ck_probe.get("in_ch", 3)) != in_ch
                         or int(_ck_probe.get("threat_dim", threat_dim)) != threat_dim))
    if stale_resume:
        print(f"[train-sim-ppo] {ppo_path.name} was trained with a different observation width "
              f"(in_ch != {in_ch}) -- the obs-canvas gate changed, so it CANNOT be resumed. "
              f"Training from scratch; the old file is left untouched until the first save.")
    if resume and ppo_path.exists() and not stale_resume:
        ck = torch.load(ppo_path, map_location="cpu")
        net.policy.load_state_dict(ck["model"])
        net.gate.load_state_dict(ck["gate"])
        if "value" in ck:
            net.value.load_state_dict(ck["value"])
        resumed_best_wr = float(ck.get("best_wr", -1.0))
        print(f"[train-sim-ppo] resumed {ppo_path.name}"
              + (f" (best so far {resumed_best_wr:.0f}%)" if resumed_best_wr >= 0 else ""))
        # RAIL GUARD (2026-08-14). A checkpoint whose RAW head logits sit far beyond the tanh cap
        # is FROZEN: softmax saturated at the rails, zero gradient, suppressed cards (tornado,
        # x_bow) unrecoverable forever -- and it LOOKS alive (placement varies, matches play).
        # That exact state shipped once: the manual repair_card_head.py run never landed (wrong
        # cwd / autosave overwrite) and the resumed run trained a frozen head for hours. The
        # trainer now refuses to resume one silently -- it measures and rescales itself.
        try:
            from .model import _LOGIT_CAP
            penv = SimMatchEnv(cfg, seed=101)
            pobs = penv.reset()
            worst_card = worst_cell = 0.0
            with torch.no_grad():
                for _ in range(8):
                    px = torch.from_numpy(np.asarray(pobs, np.float32)).unsqueeze(0).permute(0, 3, 1, 2)
                    pv = [torch.from_numpy(getattr(penv, k).astype(np.float32)).unsqueeze(0)
                          for k in ("hand_vec", "next_vec", "elixir_vec", "threat_vec")]
                    fmap = net.policy.features(px)
                    z = net.policy._embed(fmap, *pv)
                    worst_card = max(worst_card, float(net.policy.card_head(z).abs().max()))
                    worst_cell = max(worst_cell, float(net.policy._cell_logits(fmap, z).abs().max()))
                    po = penv.step((True, 0, 200))
                    pobs = po[0] if not po[2] else penv.reset()
                fixed = []
                if worst_card > 2.0 * _LOGIT_CAP:
                    a = 3.0 / worst_card
                    net.policy.card_head.weight.mul_(a)
                    net.policy.card_head.bias.mul_(a)
                    fixed.append(f"card head x{a:.4f} (raw absmax {worst_card:.0f})")
                if worst_cell > 2.0 * _LOGIT_CAP:
                    a = 4.5 / worst_cell
                    last = net.policy.cell_conv[-1]
                    last.weight.mul_(a)
                    if last.bias is not None:
                        last.bias.mul_(a)
                    fixed.append(f"cell head x{a:.4f} (raw absmax {worst_cell:.0f})")
            if fixed:
                print("[train-sim-ppo] RAIL GUARD: resumed head(s) saturated beyond the tanh cap -- "
                      f"rescaled into the linear region: {', '.join(fixed)}. Rankings preserved; "
                      "suppressed cards are gradient-reachable again. (For the neutral-prior lift, "
                      "run tools/repair_card_head.py --lift manually.)")
        except Exception as exc:  # noqa: BLE001 -- the guard must never block a resume
            print(f"[train-sim-ppo] rail guard skipped ({exc})")
    elif init:
        # WARM-START from any compatible checkpoint (e.g. the DDQN champion policy_sim_best.pt).
        # Q-heads read as logits = a Boltzmann policy over the learned Q values (greedy behaviour is
        # preserved as the mode); the value head starts FRESH -- value warmup below trains the
        # critic alone first, so a RANDOM critic never gets to shove the warm policy (2026-08-19;
        # before that, only advantage normalization stood between them).
        p = cfg.path(init)
        if p.exists():
            ck = torch.load(p, map_location="cpu")
            ok = (int(ck.get("n_cards", -1)) == n_cards and int(ck.get("n_cells", -1)) == n_cells
                  and int(ck.get("threat_dim", -1)) == threat_dim
                  and int(ck.get("in_ch", 3)) == in_ch)
            if ok:
                dropped = PolicyNet.load_compat(net.policy, ck["model"])
                if "gate" in ck and not reset_gate:
                    net.gate.load_state_dict(ck["gate"])
                print(f"[train-sim-ppo] warm-started policy{'' if reset_gate else '+gate'} from "
                      f"{p.name} (value head fresh"
                      + (", gate RESET -- the source gate had collapsed to always-play)" if reset_gate
                         else ")"))
                warm_loaded = True
                if dropped:
                    # Say it loudly. A partially-loaded net looks warm and behaves fresh in the
                    # part that was dropped, and that is exactly the confusion worth preventing.
                    print(f"[train-sim-ppo]   NOTE: {len(dropped)} tensor(s) did NOT carry over and "
                          f"start from random init: {', '.join(dropped[:6])}"
                          + (" ..." if len(dropped) > 6 else ""))
                    print("[train-sim-ppo]   (expected when warm-starting across the per-card cell "
                          "head change -- the placement head has to relearn from scratch)")
            else:
                print(f"[train-sim-ppo] --init {p.name} shape-incompatible -> training from scratch")
        else:
            print(f"[train-sim-ppo] --init {init} not found -> training from scratch")
    else:
        print(f"[train-sim-ppo] training FROM SCRATCH ({ppo_path.name} will be written)")

    gamma = float(cfg.get("train", "gamma", default=0.99))
    horizon = int(cfg.get("sim", "ppo_horizon", default=128))
    n_epochs = int(cfg.get("sim", "ppo_epochs", default=4))
    minibatch = int(cfg.get("sim", "ppo_minibatch", default=512))
    clip_eps = float(cfg.get("sim", "ppo_clip", default=0.2))
    # A PLAY's ratio is a product over gate x card x cell; a WAIT's is the gate alone. One bound
    # cannot be the same trust region for both -- measured, plays clip 12-25x more often, and since
    # clipping caps positive-advantage updates while negative ones keep pushing, the gate decays
    # toward waiting no matter what the reward says. See ppo_clip_play_mult in config.yaml.
    clip_play_mult = float(cfg.get("sim", "ppo_clip_play_mult", default=1.0))
    lr = float(cfg.get("sim", "ppo_lr", default=0.00025))
    ent_coef = float(cfg.get("sim", "ppo_entropy", default=0.01))
    vf_coef = float(cfg.get("sim", "ppo_vf_coef", default=0.5))
    gae_lambda = float(cfg.get("sim", "ppo_gae_lambda", default=0.95))
    max_grad = float(cfg.get("sim", "ppo_max_grad_norm", default=0.5))
    head_norm_mult = float(cfg.get("sim", "ppo_head_norm_mult", default=2.0))
    value_warmup = int(cfg.get("sim", "ppo_value_warmup", default=30))
    gate_tau = float(cfg.get("sim", "ppo_gate_threshold", default=0.25))
    # CARD-SAMPLING EXPLORATION FLOOR (PPO port of sim.explore_count_based, which only ever fed the
    # DDQN epsilon path). Mixes the policy's card distribution with a uniform over the PLAYABLE cards
    # so a card whose probability has collapsed to ~0 keeps being sampled -- measured on the flipped
    # checkpoint tornado/rocket/tesla_evo were IN HAND thousands of steps yet played 0 times, and a
    # never-sampled action gets zero policy gradient, so the collapse is self-reinforcing. 0 = off.
    explore_floor = float(cfg.get("sim", "ppo_explore_floor", default=0.0))
    # ...and the same protection for the CELL head, which had none (see choose_sample).
    cell_floor = float(cfg.get("sim", "ppo_cell_explore_floor", default=0.0))
    # A DRILL GETS ITS OWN FLOOR. At the match floor (0.15 x doctrine_frac 0.6 = 9% of cell mass)
    # nine of the 28 drills produced 0-3 passes in 60 episodes even with their reference cell in
    # the prior -- too rare to learn from. A drill exists to make a rare state common, so it is
    # explored differently from a match, where the point is to evaluate the policy's own head.
    # SELF-IMITATION on drill successes -- a gradient channel that does NOT pass through the PPO
    # importance ratio. See ppo_sil_coef in config.yaml for the measurement that motivates it.
    sil_coef = float(cfg.get("sim", "ppo_sil_coef", default=0.0))
    drill_cell_floor = float(cfg.get("sim", "ppo_drill_cell_floor", default=0.75))
    # ...AND IT ANNEALS, for the same reason the cell-entropy coefficient does. A high fixed floor
    # buys the rare success and then throws away its gradient: the stored log-prob is the mixture's,
    # so PPO forms r = pi/mu, and at floor 0.75 the sampler puts 0.28 on the prior's cell while pi
    # is 0.010 -- r ~ 0.0125, i.e. the drill's advantage arrives at ~1% strength (measured on the
    # 4000-match checkpoint, whose cell head was still indistinguishable from untrained). Decaying
    # the floor lets mu approach pi so those successes finally teach.
    drill_cell_floor_end = float(cfg.get("sim", "ppo_drill_cell_floor_end", default=drill_cell_floor))
    drill_cell_floor_anneal = float(cfg.get("sim", "ppo_drill_cell_floor_anneal", default=0.0))
    # ...and the GATE gets one too, inside a drill. Without it the timing drills are unreachable:
    # holding for N steps happens with probability ~0.5^N, so `hold_the_tesla_for_their_wincon`
    # (twelve steps) recorded zero passes in 60 episodes and could not be learned at all.
    drill_gate_floor = float(cfg.get("sim", "ppo_drill_gate_floor", default=0.6))
    # DOCTRINE-PRIOR EXPLORATION (DOCTRINE.md; log 2026-08-14): when a doctrine rule matches the
    # current (card, board), this share of the CELL FLOOR's mass samples from the doctrine
    # distribution instead of uniform -- known-good placements get their outcomes SEEN early, and
    # the policy keeps them only if the returns justify it. Rollout-only; the stored log-prob is
    # the full mixture's, so the PPO ratio stays exact. Anneal to 0 to remove the scaffold.
    doctrine_frac = float(cfg.get("sim", "doctrine_frac", default=0.0))
    from .sim.doctrine import doctrine_cells as _doctrine_cells
    from .sim.doctrine import doctrine_cards as _doctrine_cards
    if doctrine_frac > 0.0:
        print(f"[train-sim-ppo] DOCTRINE prior ON: {doctrine_frac:.0%} of the cell floor samples "
              f"from DOCTRINE.md placements when a rule matches (rollout-only, annealable)")
    cell_ent_coef0 = float(cfg.get("sim", "ppo_cell_entropy", default=ent_coef))
    cell_ent_floor = float(cfg.get("sim", "ppo_cell_entropy_floor", default=cell_ent_coef0))
    cell_ent_anneal = float(cfg.get("sim", "ppo_cell_entropy_anneal", default=0.0))
    cell_ent_coef = cell_ent_coef0
    log_every = int(cfg.get("sim", "log_every_matches", default=25))
    save_every = int(cfg.get("sim", "save_every_matches", default=50))
    opt = torch.optim.Adam(net.parameters(), lr=lr, eps=1e-5)
    # HEAD SHARPNESS CAP (2026-08-14). Measured: after a head repair the value function is still
    # calibrated to the OLD policy, advantages spike, and Adam's normalized steps sprint the raw
    # card logits from +/-2.8 to +/-119 in under ten minutes -- through the grad clip -- freezing
    # the head at the tanh rails again (x_bow -109 within one autosave). Scale adds SHARPNESS,
    # not expressiveness: rankings need relative differences only. So the heads' weight norms are
    # clamped to head_norm_mult x their (healthy, post-guard) startup norms after every step, and
    # the first value_warmup minibatches on a resume OR --init warm start train the VALUE head
    # alone so the critic
    # recalibrates before it is allowed to shove the policy.
    _card_ref = float(net.policy.card_head.weight.norm()) or 1.0
    _cell_ref = float(net.policy.cell_conv[-1].weight.norm()) or 1.0
    _warm = {"left": value_warmup if ((resume and ppo_path.exists()) or warm_loaded) else 0}
    if _warm["left"]:
        print(f"[train-sim-ppo] value warmup: first {_warm['left']} minibatches train the critic only")

    def _clamp_heads():
        with torch.no_grad():
            for mod, ref in ((net.policy.card_head, _card_ref), (net.policy.cell_conv[-1], _cell_ref)):
                n = float(mod.weight.norm())
                cap_n = head_norm_mult * ref
                if n > cap_n:
                    mod.weight.mul_(cap_n / n)
                    if mod.bias is not None:
                        mod.bias.mul_(cap_n / n)

    def to_obs_t(o):
        return torch.from_numpy(o).float().permute(2, 0, 1).to(device) / 255.0

    def to_vec_t(v):
        return torch.from_numpy(np.asarray(v, np.float32)).to(device)

    def masked_logits(cq, ceq, gq, hand_t, elx_t, card_idx=None):
        """Apply the SAME masking at sampling and update time (deterministic from stored inputs):
        card = in-hand AND affordable; no playable card -> the PLAY gate is masked (forced wait, so
        the stored log-prob stays consistent); cell = the DEPLOYABLE set of the (sampled) card."""
        elixir = elx_t * 10.0
        playable = (hand_t > 0.5) & (card_costs_t.view(1, -1) <= elixir + 1e-6)
        if bank_floor > 0.0 and wincon_ids_t.numel():
            # WIN-CONDITION BANK -- see clashrl/wincon_bank.py for WHY this exists (a masked action
            # gets zero policy gradient, so an unaffordable win condition is unlearnable, not merely
            # unrewarded). Shared with the greedy benchmark and policy-stats so all three agree.
            playable = apply_wincon_bank(
                playable, elixir.squeeze(-1), card_costs_t,
                (hand_t > 0.5)[:, wincon_ids_t].any(1), wincon_cost, bank_floor)
        cq_m = cq.masked_fill(~playable, _NEG)
        gq_m = gq.clone()
        none_play = ~playable.any(1)
        gq_m[:, 1] = torch.where(none_play, torch.full_like(gq_m[:, 1], _NEG), gq_m[:, 1])
        if card_idx is None:                                   # sampling path: mask cells per-row later
            return cq_m, None, gq_m, playable
        is_any = (card_idx.view(-1, 1) == anywhere_ids_t.view(1, -1)).any(1) if anywhere_ids_t.numel() \
            else torch.zeros_like(card_idx, dtype=torch.bool)
        cellmask = torch.where(is_any.unsqueeze(1), allcells_mask.unsqueeze(0), yourhalf_mask.unsqueeze(0))
        # PER-CARD map: ceq is (B, n_cards, n_cells) now, so pick the row for the card that was
        # actually played. Everything downstream keeps the old (B, n_cells) shape, which is what
        # makes the log-prob gather and the PPO ratio identical to before.
        sel = ceq.gather(1, card_idx.view(-1, 1, 1).expand(-1, 1, ceq.shape[-1])).squeeze(1)
        return cq_m, sel.masked_fill(~cellmask, _NEG), gq_m, playable

    # ------------------------------------------------------------------ SPELL CARD VETO
    # `research/sim_parity/ledger/spell_experiments.md` §7.5: promote the spell mask from a CELL
    # mask to a CARD veto. Measured at eval on icebow, n=300 paired GREEDY, the >=3-body clump form
    # is +0.233 tower fractions (3.58σ) over the baseline and +0.207 (2.98σ) over a VOLUME-MATCHED
    # random spell ban, so the criterion and not merely the volume cut is doing the work. The
    # BODY-COUNT form was rejected by the owner -- it refuses every single-body reference line the
    # deck owns -- so the shipped criterion is on VALUE in tower fractions plus an exemption set:
    # SimMatchEnv.spell_card_ok, enumerated in decisions.md ruling 30.
    #
    # ⚠ APPLIED IN BOTH `choose_sample` AND `choose_greedy`. Until now `choose_greedy` applied no
    # spell restriction of any kind, so eval graded behaviour that training never produced.
    spell_min_value = float(cfg.get("sim", "ppo_spell_min_value", default=0.0))
    spell_ids_all = {i for i in range(n_cards)
                     if getattr(e0.specs[i], "kind", "") == "spell"}

    def _spell_veto(env, playable_row, cellmask_of):
        """Card ids this board refuses, as a list. Empty when the knob is off or unavailable."""
        if spell_min_value <= 0.0 or env is None or not spell_ids_all:
            return ()
        out = []
        for si in spell_ids_all:
            if not bool(playable_row[si]):
                continue
            try:
                ok, _why = env.spell_card_ok(int(si), spell_min_value,
                                             legal=cellmask_of(si).detach().cpu().numpy())
            except Exception:                     # noqa: BLE001 -- never break a rollout
                continue
            if not ok:
                out.append(int(si))
        return out

    def _apply_veto(cq_m, gq_m, playable, i, banned):
        """Strike the vetoed cards out of row `i` and send the gate to WAIT if nothing is left."""
        for si in banned:
            cq_m[i, si] = _NEG
            playable[i, si] = False
        if not bool(playable[i].any()):
            gq_m[i, 1] = _NEG

    def choose_sample(obs_b, hand_b, nxt_b, elx_b, thr_b):
        """Sample (gate, card, cell) from the factored policy for all K envs; return acts, logps, values."""
        net.eval()
        obs_t = torch.stack([to_obs_t(o) for o in obs_b])
        hand_t = torch.stack([to_vec_t(h) for h in hand_b])
        elx_t = torch.stack([to_vec_t(e) for e in elx_b])
        with torch.no_grad():
            cq, ceq, gq, val = net(obs_t, hand_t, torch.stack([to_vec_t(n) for n in nxt_b]),
                                   elx_t, torch.stack([to_vec_t(t) for t in thr_b]))
            cq_m, _, gq_m, playable = masked_logits(cq, ceq, gq, hand_t, elx_t)
            # CARD VETO, before the gate is sampled: a board on which every remaining card is
            # refused must be able to reach WAIT, and the gate is drawn first. Struck HERE, before
            # p_c is formed, so the STORED log-prob is the vetoed behaviour policy's -- mu is what
            # actually sampled, and the PPO ratio pi_new/mu stays exact importance sampling (the
            # same convention the exploration floors document below; the update deliberately
            # recomputes the PURE policy, never the scaffolding).
            if spell_min_value > 0.0:
                cq_m, playable = cq_m.clone(), playable.clone()
                for i in range(len(obs_b)):
                    # REMOTE IS THE NORMAL CASE. `remote = workers > 1` and every real run is
                    # --workers 12, where `pool` is EMPTY -- so a parent-side-only veto would
                    # train UNMASKED while eval and the drill report ran masked, which is
                    # ruling 30's own asymmetry inverted. The worker decides it against its
                    # own env (remote_pool.spell_veto_ids) and ships it in the payload.
                    _apply_veto(cq_m, gq_m, playable, i,
                                rpool.spell_veto(i) if remote else _spell_veto(
                                    pool[i], playable[i],
                                    lambda si: (allcells_mask if si in anywhere_ids
                                                else yourhalf_mask)))
            # GATE SAMPLING, with a DRILL TIMING PRIOR mixed in. Same shape as the card and cell
            # floors below and for the same reason: a head that never samples an action gets no
            # gradient for it. Here the unsampled action is HOLDING -- the gate sits near 50/50
            # early in training, so a drill passed by waiting twelve steps and then playing is
            # reached with probability ~0.5^12, and every timing drill measured zero passes in 60
            # episodes. The prior is the drill's own reference line, which records when each card
            # is played. Stored log-prob is the MIXTURE's, so the PPO ratio stays exact.
            p_g = F.log_softmax(gq_m, dim=1).exp()
            if drill_gate_floor > 0.0:
                for i in range(p_g.shape[0]):
                    if not in_drill[i]:
                        continue
                    pg = rpool.drill_gate(i) if remote else _drill_gate(pool[i])
                    if pg is None or float(p_g[i, 1]) < 1e-6:
                        continue                 # no line, or PLAY is masked -- never nominate it
                    prior = torch.zeros_like(p_g[i])
                    prior[1] = float(min(1.0, max(0.0, pg)))
                    prior[0] = 1.0 - float(prior[1])
                    _fs = (rpool.drill_floor(i) if remote else
                           (pool[i].drill_floor_scale() if hasattr(pool[i], "drill_floor_scale") else 1.0))
                    gf = min(0.97, drill_gate_floor * _fs)
                    p_g[i] = (1.0 - gf) * p_g[i] + gf * prior
            lp_g = p_g.clamp_min(1e-12).log()
            g_samp = torch.multinomial(p_g.clamp_min(1e-12), 1).squeeze(1)
            # Card sampling from a MIXTURE: (1-floor)*policy + floor*uniform(playable). The STORED
            # log-prob below is this mixture's (the true behaviour policy mu), so the PPO ratio the
            # update forms -- pi_new(card)/mu(card), pi_new being the pure softmax it recomputes --
            # stays exact importance sampling; the entropy bonus still shapes the pure policy. This
            # keeps every playable card (tornado/rocket/tesla_evo included) receiving gradient.
            p_c_pure = F.log_softmax(cq_m, dim=1).exp()
            if explore_floor > 0.0:
                p_unif = playable.float() / playable.float().sum(1, keepdim=True).clamp_min(1.0)
                if doctrine_frac > 0.0:
                    # WHICH-CARD prior, the mirror of the cell one below. The cell prior already
                    # knew where a rocket should go and the reward already paid 2.4 for the
                    # tower + support 2-for-1, but neither was reachable: the card head never
                    # selected the rocket at all (0 plays in 14,300 matches and four evals). A
                    # card that is never sampled gets no gradient, so this nominates it in the
                    # situations that are actually rocket situations. Uniform residue kept, so
                    # the scaffold guides rather than dictates, and doctrine_frac -> 0 removes it.
                    p_floor_c = p_unif.clone()
                    for i in range(p_unif.shape[0]):
                        dcard = rpool.doctrine_card(i) if remote else _doctrine_cards(pool[i])
                        if not dcard:
                            continue
                        prior = torch.zeros_like(p_unif[i])
                        for c_j, w_j in dcard.items():
                            if 0 <= int(c_j) < prior.numel():
                                prior[int(c_j)] = float(w_j)
                        prior = prior * playable[i].float()   # never nominate an unplayable card
                        s = prior.sum()
                        if s > 0:
                            p_floor_c[i] = ((1.0 - doctrine_frac) * p_unif[i]
                                            + doctrine_frac * (prior / s))
                    p_unif = p_floor_c
                p_c_mix = (1.0 - explore_floor) * p_c_pure + explore_floor * p_unif
            else:
                p_c_mix = p_c_pure
            lp_c_mix = p_c_mix.clamp_min(1e-12).log()
            c_samp = torch.multinomial(p_c_mix.clamp_min(1e-12), 1).squeeze(1)
            acts, logps = [], []
            for i in range(len(obs_b)):
                g = int(g_samp[i])
                if g == 0:
                    acts.append((0, 0, 0)); logps.append(float(lp_g[i, 0]))
                    continue
                ci = int(c_samp[i])
                cmask = allcells_mask if ci in anywhere_ids else yourhalf_mask
                ceq_i = ceq[i, ci].masked_fill(~cmask, _NEG)   # PER-CARD map
                # CELL sampling from the SAME mixture shape as the card head above. Without this the
                # 432-way cell head had NO anti-collapse protection while the 10-way card head did,
                # and it collapsed to a constant: MEASURED on policy_sim_ppo_best over 150 matches,
                # 3 distinct cells out of 432 with 79% of all plays on ONE tile -- six different
                # cards deploying to the identical spot, in the LEFT lane, regardless of where the
                # push was. A frozen cell head makes every placement-dependent reward unreachable,
                # so no amount of reward tuning can move it. The stored log-prob is the MIXTURE's,
                # so the PPO ratio stays exact importance sampling (same argument as the card floor).
                p_cell_pure = F.log_softmax(ceq_i, dim=0).exp()
                # PER-DRILL SCALE on top of the annealed floor: harder scaffolding for a drill
                # whose successes are not being generated, weaker for one the prior is already
                # winning (whose wins therefore teach nothing at r ~ 0.0125).
                _fs = (rpool.drill_floor(i) if remote else
                       (pool[i].drill_floor_scale() if hasattr(pool[i], "drill_floor_scale") else 1.0))
                floor_i = min(0.95, _drill_floor_now() * _fs) if in_drill[i] else cell_floor
                if floor_i > 0.0:
                    cm = cmask.float()
                    p_floor = cm / cm.sum().clamp_min(1.0)
                    if doctrine_frac > 0.0:
                        # Route part of the floor through the DOCTRINE prior when a rule matches
                        # (see sim/doctrine.py). Masked to deployable, normalised, and blended so
                        # the floor keeps a uniform residue -- the scaffold guides, never dictates.
                        dc = rpool.doctrine(i, ci) if remote else _doctrine_cells(pool[i], ci)
                        if dc:
                            prior = torch.zeros_like(p_floor)
                            for c_j, w_j in dc:
                                prior[c_j] = w_j
                            prior = prior * cm
                            s = prior.sum()
                            if s > 0:
                                p_floor = (1.0 - doctrine_frac) * p_floor + doctrine_frac * (prior / s)
                    p_cell = (1.0 - floor_i) * p_cell_pure + floor_i * p_floor
                else:
                    p_cell = p_cell_pure
                lp_cell = p_cell.clamp_min(1e-12).log()
                cell = int(torch.multinomial(p_cell.clamp_min(1e-12), 1))
                acts.append((1, ci, cell))
                logps.append(float(lp_g[i, 1] + lp_c_mix[i, ci] + lp_cell[cell]))
        return acts, logps, [float(v) for v in val]

    def _drill_gate(env):
        """Local-pool twin of RemotePool.drill_gate."""
        try:
            return env.drill_prior_gate() if hasattr(env, "drill_prior_gate") else None
        except Exception:  # noqa: BLE001 -- a bad reference must not break the rollout
            return None

    def choose_greedy(obs_b, hand_b, nxt_b, elx_b, thr_b, envs=None):
        """Deterministic mode of the policy (benchmark): gate by LOGIT compare, argmax card/cell."""
        net.eval()
        obs_t = torch.stack([to_obs_t(o) for o in obs_b])
        hand_t = torch.stack([to_vec_t(h) for h in hand_b])
        elx_t = torch.stack([to_vec_t(e) for e in elx_b])
        with torch.no_grad():
            cq, ceq, gq, _ = net(obs_t, hand_t, torch.stack([to_vec_t(n) for n in nxt_b]),
                                 elx_t, torch.stack([to_vec_t(t) for t in thr_b]))
        cq_m, _, gq_m, playable = masked_logits(cq, ceq, gq, hand_t, elx_t)
        # THE SAME CARD VETO THE SAMPLER APPLIES -- see the note above. `envs` is the caller's
        # pool, in the same row order.
        if spell_min_value > 0.0 and envs is not None:
            cq_m, playable = cq_m.clone(), playable.clone()
            for i in range(len(obs_b)):
                _apply_veto(cq_m, gq_m, playable, i, _spell_veto(
                    envs[i], playable[i],
                    lambda si: allcells_mask if si in anywhere_ids else yourhalf_mask))
        acts = []
        for i in range(len(obs_b)):
            # Threshold the gate PROBABILITY, not a raw logit compare. `gq[0] >= gq[1]` is tau=0.5,
            # which a calibrated gate almost never clears (a play is rare per tick), so the greedy
            # benchmark under-deployed badly vs the sampling the policy actually trained under.
            if not bool(playable[i].any()) or \
                    float(torch.sigmoid(gq_m[i, 1] - gq_m[i, 0])) <= gate_tau:
                acts.append((0, 0, 0)); continue
            ci = int(cq_m[i].argmax())
            cmask = allcells_mask if ci in anywhere_ids else yourhalf_mask
            acts.append((1, ci, int(ceq[i, ci].masked_fill(~cmask, _NEG).argmax())))
        return acts

    def save(path=None):
        p = path if path is not None else ppo_path
        p.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"model": net.policy.state_dict(), "gate": net.gate.state_dict(),
                    "value": net.value.state_dict(), "algo": "ppo",
                    "grid": [gw, gh], "n_cards": n_cards, "n_cells": n_cells,
                    "threat_dim": threat_dim, "in_ch": in_ch, "deck": e0.deck_keys, "best_wr": best_wr,
                    "matches": done_n,     # matches played when this file was written (checkpoint inventory)
                    "arena_size": list(cfg.get("observation", "arena_size", default=[64, 96]))}, p)

    # -- self-play league (identical machinery to train_sim; snapshots are DQN-CLASS wrappers so
    # SelfPlayOpponent's forward signature matches, tagged _ppo so its greedy gate compares logits) --
    sp_prob = float(cfg.get("sim", "selfplay_prob", default=0.5))
    sp_ramp = int(cfg.get("sim", "selfplay_ramp_matches", default=5000))
    sp_snap_every = int(cfg.get("sim", "selfplay_snapshot_every", default=1000))
    sp_league_size = int(cfg.get("sim", "selfplay_league_size", default=5))
    keep_best = bool(cfg.get("sim", "selfplay_keep_best", default=True))
    pfsp_on = bool(cfg.get("sim", "selfplay_pfsp", default=True))
    pfsp_power = float(cfg.get("sim", "selfplay_pfsp_power", default=2.0))
    league: deque = deque(maxlen=max(1, sp_league_size))
    _best_snap = {"net": None}
    _prog = {"n": 0}
    _adv_stats = {"drill": 0.0, "match": 0.0, "frac_drill_steps": 0.0}
    _clip_split = {"play": 0.0, "play_n": 0.0, "wait": 0.0, "wait_n": 0.0}

    def snapshot(store=True):
        snap = _build_net(cfg, device, n_cards, n_cells, threat_dim, in_ch)
        snap.policy.load_state_dict(net.policy.state_dict())
        snap.gate.load_state_dict(net.gate.state_dict())
        snap.eval()
        for p in snap.parameters():
            p.requires_grad_(False)
        snap._ppo = True                 # SelfPlayOpponent: gate by logit compare, not summed Q
        snap._pfsp = deque(maxlen=40)
        if store:
            league.append(snap)
        return snap

    def sp_prob_now():
        return sp_prob if sp_ramp <= 0 else sp_prob * min(1.0, _prog["n"] / sp_ramp)

    def opponent_provider(env):
        snaps = list(league)
        if keep_best and _best_snap["net"] is not None:
            snaps.append(_best_snap["net"])
        if sp_prob > 0 and snaps and random.random() < sp_prob_now():
            if pfsp_on and len(snaps) > 1:
                pick = random.choices(snaps, weights=pfsp_weights(snaps, pfsp_power), k=1)[0]
            else:
                pick = random.choice(snaps)
            return SelfPlayOpponent(cfg, env, pick, env.rng)
        return make_opponent(cfg, env.db, env.rng, env.meta_pool, adaptive=True)

    _curr = {"d": float(cfg.get("sim", "curriculum_start", default=0.3))}
    full_wr = float(cfg.get("sim", "curriculum_full_wr", default=35.0))
    # FIX 4 (2026-08-24): see scratchpad/fix4.py. At 0.02 the controller moved on 52.5% of updates
    # with the true winrate HELD CONSTANT -- over half of all difficulty changes were noise.
    _curr_deadband = float(cfg.get("sim", "curriculum_deadband", default=0.06))

    def opponent_provider_cur(env):
        # CURRICULUM: below-ladder tier while the winrate is on the floor (0/40 measured --
        # no wins means no win signal at all). Difficulty follows the recent training winrate.
        if env.rng.random() > _curr["d"]:
            return make_opponent(cfg, env.db, env.rng, env.meta_pool, level=11, adaptive=False)
        return opponent_provider(env)

    _bcast = {"nets": []}                # nets index-aligned with the last shipped league

    def _broadcast_league():
        # NET OBJECTS CANNOT CROSS THE PIPE: the DQN class is local to _build_net, so its
        # instances do not pickle (measured: AttributeError "Can't get local object
        # '_build_net.<locals>.DQN'" at the FIRST snapshot broadcast, match 1000, killing the
        # run). Ship plain state_dicts; each worker rebuilds with the same _build_net and
        # caches per league entry. PFSP weights still come from the parent's net objects
        # (their _pfsp histories live here), and _bcast keeps those nets index-aligned with
        # the shipped list so a worker's outcome report can find its snapshot again.
        if not remote:
            return
        nets = list(league)
        if keep_best and _best_snap.get("net") is not None:
            nets.append(_best_snap["net"])
        if not nets:
            return
        try:
            w_l = list(pfsp_weights(nets, pfsp_power)) if (pfsp_on and len(nets) > 1) else []
        except Exception:  # noqa: BLE001
            w_l = []
        sds = [{"model": n.policy.state_dict(), "gate": n.gate.state_dict()} for n in nets]
        _bcast["nets"] = nets
        rpool.set_league(sds, w_l, sp_prob_now())

    if sp_prob > 0 or True:
        for e in pool:
            e.opponent_provider = opponent_provider_cur
        if (resume and ppo_path.exists()) or init:
            sd = snapshot()
            if keep_best:
                _best_snap["net"] = sd
        _broadcast_league()              # remote workers start with the seeded league, not empty
        print(f"[train-sim-ppo] self-play ON: prob {sp_prob:.2f} (ramp {sp_ramp}), snapshot every "
              f"{sp_snap_every}, league {sp_league_size}"
              + (", +best-self" if keep_best else "") + (f", PFSP p={pfsp_power:g}" if pfsp_on else ""))

    # -- benchmark eval (identical protocol to train_sim: frozen scripted pool, canonical render) --
    eval_every = int(cfg.get("sim", "eval_every_matches", default=500))
    eval_matches = int(cfg.get("sim", "eval_matches", default=24))
    eval_envs = min(K, max(1, int(cfg.get("sim", "eval_envs", default=4))))
    eval_pool = [SimMatchEnv(cfg, seed=100000 + i) for i in range(eval_envs)] if eval_every > 0 else []
    for _e in eval_pool:
        _e.domain_rand.enabled = False
        _e.domain_rand.resample()
    eval_hist: deque = deque(maxlen=max(1, int(cfg.get("sim", "eval_smooth_window", default=5))))
    eval_hist_fair: deque = deque(maxlen=eval_hist.maxlen)
    run_fair = bool(cfg.get("sim", "fair_eval", default=True))
    _fair_cfg = cfg.get("sim", "fair_eval_level", default=None)
    _agent_lv = list(e0.deck_card_levels) or [11]
    fair_level = int(_fair_cfg) if _fair_cfg else int(round(sum(_agent_lv) / len(_agent_lv)))
    _el = cfg.get("sim", "enemy_levels", default=[13, 14, 15, 16])
    ladder_lbl = f"L{min(_el)}-{max(_el)}"
    best_path = ppo_path.with_name(ppo_path.stem + "_best" + ppo_path.suffix)
    best_wr = resumed_best_wr

    def evaluate(fair=False):
        if not eval_pool:
            return None
        for j, e in enumerate(eval_pool):
            e.rng.seed(777 + j)
            if fair:
                e.opponent_provider = lambda env: make_opponent(cfg, env.db, env.rng, env.meta_pool,
                                                                level=fair_level)
            else:
                e.opponent_provider = None
        eo = [e.reset() for e in eval_pool]
        eh = [e.hand_vec.copy() for e in eval_pool]; en = [e.next_vec.copy() for e in eval_pool]
        ee = [e.elixir_vec.copy() for e in eval_pool]; et = [e.threat_vec.copy() for e in eval_pool]
        wins = played = 0
        while played < eval_matches:
            acts = choose_greedy(eo, eh, en, ee, et, envs=eval_pool)
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


    def _drill_floor_now() -> float:
        """Drill cell-exploration floor for the CURRENT point in training.

        Linear from `ppo_drill_cell_floor` to `ppo_drill_cell_floor_end` over
        `ppo_drill_cell_floor_anneal` episodes. With anneal 0 this is a constant and the behaviour
        is exactly what it was.
        """
        if drill_cell_floor_anneal <= 0.0:
            return drill_cell_floor
        f = min(1.0, max(0.0, float(_prog.get("n", 0)) / drill_cell_floor_anneal))
        return drill_cell_floor + (drill_cell_floor_end - drill_cell_floor) * f

    def _cell_ent_now() -> float:
        """Cell-entropy coefficient for the CURRENT point in training.

        Linear from `ppo_cell_entropy` to `ppo_cell_entropy_floor` over `ppo_cell_entropy_anneal`
        episodes. With anneal 0 this is a constant and the behaviour is exactly what it was.
        """
        if cell_ent_anneal <= 0.0:
            return cell_ent_coef0
        f = min(1.0, max(0.0, float(_prog.get("n", 0)) / cell_ent_anneal))
        return cell_ent_coef0 + (cell_ent_floor - cell_ent_coef0) * f

    def ppo_update(roll):
        """One PPO update over a finished rollout. roll holds [T] rows of K-sized per-env lists."""
        T = len(roll["rew"])
        adv, ret = compute_gae(roll["rew"], roll["val"], roll["done"], roll["boot"],
                               gamma, gae_lambda, trunc=roll.get("trunc"))
        # flatten [T, K] -> [N]
        def flat(key):
            return [roll[key][t][i] for t in range(T) for i in range(K)]
        N = T * K
        adv_f = torch.tensor(adv.reshape(-1), device=device)
        adv_f = (adv_f - adv_f.mean()) / (adv_f.std() + 1e-8)
        ret_f = torch.tensor(ret.reshape(-1), device=device)
        oldlp_f = torch.tensor(flat("logp"), dtype=torch.float32, device=device)
        g_f = torch.tensor([a[0] for a in flat("act")], device=device)
        c_f = torch.tensor([a[1] for a in flat("act")], device=device)
        cell_f = torch.tensor([a[2] for a in flat("act")], device=device)
        sil_f = (torch.tensor(flat("sil"), dtype=torch.float32, device=device)
                 if roll.get("sil") else torch.zeros(N, device=device))
        obs_f, hand_f = flat("obs"), flat("hand")
        nxt_f, elx_f, thr_f = flat("nxt"), flat("elx"), flat("thr")

        # ADVANTAGE SPLIT: drill steps vs match steps. Advantages are normalised over the WHOLE
        # mixed batch, and a drill episode is ~20 steps against a match's ~300, so the two carry
        # very different return scales. If one population's |advantage| dwarfs the other, the other
        # is squashed toward zero and stops contributing gradient -- which would look exactly like
        # a match winrate that never moves while drill numbers do.
        if roll.get("isdrill"):
            _d = torch.tensor(flat("isdrill"), dtype=torch.float32, device=device)
            _a = adv_f.abs()
            _nd, _nm = float(_d.sum()), float((1.0 - _d).sum())
            if _nd > 0 and _nm > 0:
                _adv_stats["drill"] = float((_a * _d).sum() / _nd)
                _adv_stats["match"] = float((_a * (1.0 - _d)).sum() / _nm)
                _adv_stats["frac_drill_steps"] = _nd / max(1.0, _nd + _nm)

        net.train()
        tot_pl = tot_vl = tot_ent = tot_clip = 0.0
        nb = 0
        idx_all = np.arange(N)
        for _ep in range(n_epochs):
            np.random.shuffle(idx_all)
            for s in range(0, N, minibatch):
                mb = idx_all[s:s + minibatch]
                obs_t = torch.stack([to_obs_t(obs_f[i]) for i in mb])
                hand_t = torch.stack([to_vec_t(hand_f[i]) for i in mb])
                elx_t = torch.stack([to_vec_t(elx_f[i]) for i in mb])
                cq, ceq, gq, val = net(obs_t, hand_t,
                                       torch.stack([to_vec_t(nxt_f[i]) for i in mb]), elx_t,
                                       torch.stack([to_vec_t(thr_f[i]) for i in mb]))
                mb_t = torch.tensor(mb, device=device)
                g_b, c_b, cell_b = g_f[mb_t], c_f[mb_t], cell_f[mb_t]
                cq_m, ceq_m, gq_m, _ = masked_logits(cq, ceq, gq, hand_t, elx_t, card_idx=c_b)
                lp_g = F.log_softmax(gq_m, dim=1)
                lp_c = F.log_softmax(cq_m, dim=1)
                lp_cell = F.log_softmax(ceq_m, dim=1)
                play = (g_b == 1).float()
                new_lp = lp_g.gather(1, g_b.view(-1, 1)).squeeze(1) \
                    + play * (lp_c.gather(1, c_b.view(-1, 1)).squeeze(1)
                              + lp_cell.gather(1, cell_b.view(-1, 1)).squeeze(1))
                ent = -(lp_g.exp() * lp_g).sum(1) \
                    + play * (-(lp_c.exp() * lp_c).sum(1))
                # CELL entropy is weighted SEPARATELY. One shared coefficient cannot hold a 10-way
                # and a 432-way categorical at once: max entropy is ln(10)=2.30 vs ln(432)=6.07, so
                # at ent_coef 0.01 the big head's entropy gradient was far too weak to resist a
                # collapse to a delta -- and it did collapse (3 of 432 cells ever used).
                cell_ent = play * (-(lp_cell.exp() * lp_cell).sum(1))
                a_b, r_b, ol_b = adv_f[mb_t], ret_f[mb_t], oldlp_f[mb_t]
                ratio = (new_lp - ol_b).exp()
                s1 = ratio * a_b
                # PER-ACTION-KIND BOUND: wider for plays, whose ratio carries three log-probs.
                eps_b = clip_eps * (1.0 + (clip_play_mult - 1.0) * play)
                s2 = torch.clamp(ratio, 1.0 - eps_b, 1.0 + eps_b) * a_b
                pl = -torch.min(s1, s2).mean()
                vl = F.mse_loss(val, r_b)
                if _warm["left"] > 0:
                    _warm["left"] -= 1
                    loss = vf_coef * vl                       # critic-only: no policy shove yet
                else:
                    # ANNEALED CELL ENTROPY. A fixed coefficient has to choose between the two
                    # ways this head fails: too low and it collapses to a handful of cells (it did
                    # -- 3 of 432), too high and it is held at maximum entropy and never learns a
                    # placement at all (it was -- 8.36 of 8.37 after 500 matches, identical to an
                    # untrained net). High early, when collapse is the danger and there is nothing
                    # worth sharpening onto; decaying to a floor once the reward is worth following.
                    loss = pl + vf_coef * vl - ent_coef * ent.mean() - _cell_ent_now() * cell_ent.mean()
                    # SELF-IMITATION on VERIFIED-CORRECT actions. The PPO term above reaches the
                    # cell head through r = pi/mu, and with a strong drill prior that ratio is
                    # ~0.01 -- measured -- so a drill success contributes almost nothing however
                    # large its advantage. This term is a plain cross-entropy toward the action
                    # actually taken on steps of a drill the agent PASSED: the drill's predicate
                    # already certified the outcome, so no critic estimate is involved and no
                    # importance weight applies. Mean over marked steps, so it does not grow with
                    # how many drills happened to pass in a rollout.
                    if sil_coef > 0.0:
                        sil_b = sil_f[mb_t]
                        denom = sil_b.sum()
                        if float(denom) > 0.0:
                            sil_lp = play * (lp_c.gather(1, c_b.view(-1, 1)).squeeze(1)
                                             + lp_cell.gather(1, cell_b.view(-1, 1)).squeeze(1))
                            loss = loss - sil_coef * (sil_b * sil_lp).sum() / denom
                opt.zero_grad(); loss.backward()
                torch.nn.utils.clip_grad_norm_(net.parameters(), max_grad)
                opt.step()
                _clamp_heads()                                # sharpness cap: heads can rank, not rail
                with torch.no_grad():
                    tot_pl += float(pl.detach()); tot_vl += float(vl.detach())
                    tot_ent += float(ent.mean().detach())
                    tot_clip += float(((ratio.detach() - 1.0).abs() > clip_eps).float().mean()); nb += 1
                    # CLIP RATE SPLIT BY PLAY vs WAIT. A wait's ratio carries the GATE log-prob
                    # alone; a play's carries gate + card + cell, and the cell head is 432-way. So a
                    # play's ratio is far noisier and clips more often -- and clipping is asymmetric
                    # in effect, capping a positive-advantage update while a negative one keeps
                    # pushing down. That would bias the gate toward WAITING regardless of reward,
                    # which is what every run does (P(play) 0.5 -> 0.15) even though the reward
                    # strongly favours playing (never-play -44.77 vs play-often -7.34 per episode).
                    _cl = ((ratio.detach() - 1.0).abs() > eps_b.detach()).float()
                    _pm = play.detach()
                    _clip_split["play"] += float((_cl * _pm).sum())
                    _clip_split["play_n"] += float(_pm.sum())
                    _clip_split["wait"] += float((_cl * (1.0 - _pm)).sum())
                    _clip_split["wait_n"] += float((1.0 - _pm).sum())
        return tot_pl / nb, tot_vl / nb, tot_ent / nb, tot_clip / nb

    # -- main loop: collect a horizon of experience across K envs, then one PPO update -------------
    if remote:
        cobs = rpool.reset_all()
        chand = [p["hand"] for p in rpool.last]; cnxt = [p["nxt"] for p in rpool.last]
        # WHICH ENVS ARE IN A DRILL -- the exploration floor differs, and the envs live in the
        # workers while the sampling happens here.
        in_drill = [bool(p.get("in_drill")) for p in rpool.last]
        celx = [p["elx"] for p in rpool.last]; cthr = [p["thr"] for p in rpool.last]
    else:
        cobs = [e.reset() for e in pool]
        chand = [e.hand_vec.copy() for e in pool]; cnxt = [e.next_vec.copy() for e in pool]
        in_drill = [bool(getattr(e, "_in_drill", False)) for e in pool]
        celx = [e.elixir_vec.copy() for e in pool]; cthr = [e.threat_vec.copy() for e in pool]
    ep_r = [0.0] * K
    ep_n = [0] * K            # steps per env this episode, for the drill STEP share
    running = {"v": True}
    signal.signal(signal.SIGINT, lambda *_a: running.update(v=False))
    if explore_floor > 0.0:
        print(f"[train-sim-ppo] card exploration floor ON: {explore_floor:.0%} of card-sampling mass "
              f"is uniform over playable cards (anti-collapse; rollouts only, greedy eval is unaffected)")
    if cell_floor > 0.0:
        print(f"[train-sim-ppo] CELL exploration floor ON: {cell_floor:.0%} of cell-sampling mass is "
              f"uniform over deployable cells (the head that collapsed to 3 of {n_cells} cells)")
    if cell_ent_coef != ent_coef:
        print(f"[train-sim-ppo] cell entropy coefficient {cell_ent_coef} (gate/card {ent_coef})")
    print(f"[train-sim-ppo] {device}: {K} env(s), horizon {horizon} (batch {horizon * K}), up to "
          f"{matches} matches (cards={n_cards}, cells={n_cells}). Ctrl+C to stop + save.")
    done_n = wins = losses = draws = 0
    drills_done = drill_pass = 0     # drills are counted apart from the match record
    # ...and their share of STEPS is tracked apart from their share of EPISODES, because those two
    # differ by an order of magnitude (48% of episodes was 8% of steps) and only the second is what
    # the optimiser sees. Printing one without the other is how a barely-training mix looked broken.
    drill_steps = match_steps = 0
    win_hist: deque = deque(maxlen=max(log_every, 50))
    rew_hist: deque = deque(maxlen=max(log_every, 50))
    stats = None
    t0 = time.time()
    try:
        while running["v"] and done_n < matches:
            roll = {"obs": [], "hand": [], "nxt": [], "elx": [], "thr": [],
                    "act": [], "logp": [], "val": [], "rew": [], "done": [], "trunc": [],
                    # SELF-IMITATION MASK: 1.0 on steps that turned out to belong to a drill
                    # episode the agent PASSED. Filled in retroactively when the episode ends,
                    # because that is when the verdict exists.
                    "sil": [], "isdrill": [], "boot": None}
            ep_from = [0] * K                              # first step of each env's current episode
            for _t in range(horizon):
                if not running["v"] or done_n >= matches:
                    break
                acts, logps, vals = choose_sample(cobs, chand, cnxt, celx, cthr)
                roll["obs"].append(list(cobs)); roll["hand"].append([h.copy() for h in chand])
                roll["nxt"].append([n.copy() for n in cnxt]); roll["elx"].append([e.copy() for e in celx])
                roll["thr"].append([t.copy() for t in cthr])
                roll["act"].append(acts); roll["logp"].append(logps); roll["val"].append(vals)
                rew_row, done_row, trunc_row = [], [], []
                if remote:
                    step_out = rpool.step_all(acts)
                else:
                    step_out = None
                for i in range(K):
                    if remote:
                        pay = step_out[i]
                        nobs, reward, done = pay["obs"], pay["rew"], pay["done"]
                        info = {"outcome": pay["outcome"], "pfsp": pay["pfsp"],
                                "drill": pay.get("drill"), "verdict": pay.get("verdict")}
                        env = None
                    else:
                        env = pool[i]
                        nobs, reward, done, info = env.step(acts[i])
                    rew_row.append(float(reward)); done_row.append(1.0 if done else 0.0)
                    # A DRILL ENDING IS A CUT, NOT AN OUTCOME. It has a `drill` name and no match
                    # `outcome`, so the position was still live when the episode stopped -- see
                    # compute_gae for why bootstrapping 0 there poisons the critic.
                    trunc_row.append(1.0 if (done and info.get("drill") is not None
                                             and not info.get("outcome")) else 0.0)
                    ep_r[i] += reward; ep_n[i] += 1
                    if done:
                        oc = info.get("outcome")
                        if remote:
                            pj = info.get("pfsp")          # index into the last broadcast league
                            if pj is not None and 0 <= pj < len(_bcast["nets"]):
                                n_ = _bcast["nets"][pj]
                                if hasattr(n_, "_pfsp"):   # parent-side PFSP ledger
                                    n_._pfsp.append(1.0 if oc == "win" else (0.5 if oc == "draw" else 0.0))
                        else:
                            opp = getattr(env, "opponent", None)   # PFSP attribution (before reset)
                            if isinstance(opp, SelfPlayOpponent) and hasattr(opp.net, "_pfsp"):
                                opp.net._pfsp.append(1.0 if oc == "win" else (0.5 if oc == "draw" else 0.0))
                        # A DRILL IS NOT A LOST MATCH. It ends on its own predicate and has no
                        # `outcome`, so folding it into win_hist records a loss that never
                        # happened -- three in ten at drill_frac 0.3. The winrate EMA drives the
                        # CURRICULUM DIFFICULTY, the PFSP ledger and the checkpoint gate, so that
                        # would have eased the opponent pool and then read as "drills make it
                        # worse" for a reason with nothing to do with drills.
                        is_drill = info.get("drill") is not None
                        if is_drill:
                            drills_done += 1
                            drill_pass += 1 if info.get("verdict") == "pass" else 0
                            drill_steps += ep_n[i]
                            # MARK THE EPISODE FOR SELF-IMITATION, now that its verdict exists. The
                            # steps are already in the rollout; this walks back over the ones that
                            # belong to this env's just-finished episode. An episode that began in
                            # an earlier rollout is marked only over the part present here, which is
                            # the part that can still receive a gradient.
                            if sil_coef > 0.0 and info.get("verdict") == "pass":
                                for _tt in range(ep_from[i], len(roll["sil"])):
                                    roll["sil"][_tt][i] = 1.0
                        else:
                            match_steps += ep_n[i]
                            wins += oc == "win"; losses += oc == "loss"; draws += oc == "draw"
                            win_hist.append(1 if oc == "win" else 0)
                        # NEXT EPISODE'S FIRST ROW, for the self-imitation mask. This must sit
                        # OUTSIDE the drill/match branch -- an earlier version of this line was
                        # written as `if True:` immediately after the drill block, which stole the
                        # `else:` belonging to `if is_drill:` and made the ENTIRE match-accounting
                        # branch dead code: no wins, no losses, no win_hist. The visible symptom was
                        # "0W-0L-0D" on a run with real matches; the invisible one was far worse,
                        # because win_hist drives the winrate EMA, which drives CURRICULUM
                        # DIFFICULTY -- with it permanently empty the difficulty falls to its floor
                        # and the policy trains against the easiest opponents while being evaluated
                        # against full-strength ones.
                        ep_from[i] = len(roll["sil"])
                        rew_hist.append(ep_r[i])
                        done_n += 1; _prog["n"] = done_n; ep_r[i] = 0.0; ep_n[i] = 0
                        cobs[i] = nobs if remote else env.reset()   # workers auto-reset
                        if done_n % log_every == 0 and _clip_split["play_n"] > 0                                 and _clip_split["wait_n"] > 0:
                            print("[train-sim-ppo] clip rate PLAY %.3f vs WAIT %.3f  (a play's "
                                  "ratio carries gate+card+cell, a wait's only the gate)"
                                  % (_clip_split["play"] / _clip_split["play_n"],
                                     _clip_split["wait"] / _clip_split["wait_n"]), flush=True)
                            _clip_split.update({"play": 0.0, "play_n": 0.0,
                                                "wait": 0.0, "wait_n": 0.0})
                        if done_n % log_every == 0 and _adv_stats["match"] > 0:
                            print("[train-sim-ppo] adv |mean|: drill %.3f vs match %.3f "
                                  "(drill = %.0f%% of steps) -- a large gap means one population "
                                  "is squashing the other"
                                  % (_adv_stats["drill"], _adv_stats["match"],
                                     100.0 * _adv_stats["frac_drill_steps"]), flush=True)
                        if done_n % log_every == 0:
                            wr = 100.0 * sum(win_hist) / max(1, len(win_hist))
                            ar = sum(rew_hist) / max(1, len(rew_hist))
                            mps = done_n / max(1e-6, time.time() - t0)
                            xs = (f" pl={stats[0]:+.3f} vl={stats[1]:.3f} ent={stats[2]:.2f} "
                                  f"clip={stats[3]:.2f}") if stats else ""
                            # Drills are reported SEPARATELY, never folded into the winrate: a
                            # mix that is silently not happening looks exactly like a mix that is
                            # not helping, and those two have to be distinguishable at a glance.
                            # BOTH shares. The episode count is what the mix controls; the STEP
                            # share is what the optimiser actually sees, and they differ by an
                            # order of magnitude (48% of episodes was 8% of steps). Printing only
                            # the first is how a drill mix that was barely training got mistaken
                            # for one that was not working.
                            ds = (f" | drills {drills_done} "
                                  f"({100.0 * drill_pass / max(1, drills_done):.0f}% pass, "
                                  f"{100.0 * drills_done / max(1, done_n):.0f}% of eps, "
                                  f"{100.0 * drill_steps / max(1, drill_steps + match_steps):.0f}% of STEPS)"
                                  if drills_done else "")
                            print(f"[train-sim-ppo] {done_n} episodes: winrate={wr:4.0f}% "
                                  f"avg_rew={ar:+.1f} {mps:.1f} ep/s total {wins}W-{losses}L-{draws}D{xs}{ds}",
                                  flush=True)
                        if done_n % save_every == 0:
                            save()
                        if sp_prob > 0 and done_n % sp_snap_every == 0:
                            snapshot()
                            _broadcast_league()
                        if eval_every > 0 and done_n % eval_every == 0:
                            wr = evaluate(fair=False)
                            if wr is not None:
                                eval_hist.append(wr); smooth = sum(eval_hist) / len(eval_hist)
                                line = (f"[train-sim-ppo] EVAL @ {done_n}: ladder({ladder_lbl}) {wr:4.0f}% "
                                        f"(avg-{len(eval_hist)} {smooth:4.0f}%)")
                                if run_fair:
                                    fwr = evaluate(fair=True)
                                    eval_hist_fair.append(fwr)
                                    fsmooth = sum(eval_hist_fair) / len(eval_hist_fair)
                                    line += (f" | fair(L{fair_level}) {fwr:4.0f}% "
                                             f"(avg-{len(eval_hist_fair)} {fsmooth:4.0f}%)")
                                print(line + f" | {eval_matches} matches each", flush=True)
                                # same keep-best guard as train_sim: only bank once the window has
                                # >=3 points (a post-resume avg-1 is a single noisy eval)
                                if smooth > best_wr and len(eval_hist) >= min(3, eval_hist.maxlen):
                                    best_wr = smooth
                                    save(best_path)
                                    if keep_best:
                                        _best_snap["net"] = snapshot(store=False)
                                    print(f"[train-sim-ppo] new BEST ladder avg {smooth:4.0f}% -> "
                                          f"saved {best_path.name}", flush=True)
                    else:
                        cobs[i] = nobs
                    if remote:
                        chand[i], cnxt[i] = pay["hand"], pay["nxt"]
                        in_drill[i] = bool(pay.get("in_drill"))
                        celx[i], cthr[i] = pay["elx"], pay["thr"]
                    else:
                        chand[i], cnxt[i] = env.hand_vec.copy(), env.next_vec.copy()
                        in_drill[i] = bool(getattr(env, "_in_drill", False))
                        celx[i], cthr[i] = env.elixir_vec.copy(), env.threat_vec.copy()
                roll["rew"].append(np.asarray(rew_row, np.float32))
                roll["done"].append(np.asarray(done_row, np.float32))
                roll["trunc"].append(np.asarray(trunc_row, np.float32))
                roll["sil"].append(np.zeros(K, np.float32))
                roll["isdrill"].append(np.asarray([1.0 if in_drill[i] else 0.0
                                                   for i in range(K)], np.float32))
            if not roll["rew"]:
                break
            if len(win_hist) >= 20:
                wr_now = 100.0 * sum(win_hist) / len(win_hist)
                # DAMPED CONTROLLER (2026-08-15). MEASURED on the overnight run: W_easy 37.5%
                # vs W_hard 5.0% -- a 32.5-point spread puts the proportional map's slope at
                # ~-0.93, and the 50-match window refreshes almost fully every rollout (a near-
                # memoryless sensor), so binomial noise (+-7pp at n=50) bounced the difficulty
                # +-0.2 per update -- the all-night thrash the user watched, each swing shifting
                # the training mixture and re-baselining the critic for nothing. Two dampers:
                # an EMA over the window means (the sensor keeps memory across rollouts), and an
                # ASYMMETRIC rate limit -- climb up to +0.10 per update, back off at most -0.05
                # -- so the trend passes and the bounce dies. The equilibrium itself is healthy
                # and unchanged: d* solves WR(d) = full_wr * d (~0.55 -> ~19% mixed WR, exactly
                # the 18.2% gate the run had found).
                ema = _curr.get("wr_ema")
                _curr["wr_ema"] = wr_now if ema is None else 0.7 * ema + 0.3 * wr_now
                d_tgt = min(1.0, max(0.15, _curr["wr_ema"] / full_wr))
                d_new = min(_curr["d"] + 0.10, max(_curr["d"] - 0.05, d_tgt))
                # FIX 4: 0.02 sat below the sampling noise in d_tgt, so the controller moved on
                # 52.5% of updates in response to nothing (measured: constant true winrate, 8%,
                # d sd 0.058 across a 0.296 range). At 0.06 that falls to 0.2% AND a real step
                # change is tracked FASTER -- 199 matches against 236 -- because the rate limit is
                # no longer being spent on noise. Widening the sensor window was measured and
                # REJECTED: +0.1pp immunity for 1.8x the lag.
                if abs(d_new - _curr["d"]) > _curr_deadband:
                    _curr["d"] = d_new
                    if remote:
                        rpool.set_difficulty(d_new)
                    print(f"[train-sim-ppo] curriculum difficulty -> {d_new:.2f} "
                          f"(winrate ema {_curr['wr_ema']:.0f}%, window {wr_now:.0f}%)")
            with torch.no_grad():                              # bootstrap values for the final states
                net.eval()
                _, _, _, bv = net(torch.stack([to_obs_t(o) for o in cobs]),
                                  torch.stack([to_vec_t(h) for h in chand]),
                                  torch.stack([to_vec_t(n) for n in cnxt]),
                                  torch.stack([to_vec_t(e) for e in celx]),
                                  torch.stack([to_vec_t(t) for t in cthr]))
            roll["boot"] = bv.cpu().numpy().astype(np.float32)
            roll["val"] = [np.asarray(v, np.float32) for v in roll["val"]]
            stats = ppo_update(roll)
    except KeyboardInterrupt:
        pass
    finally:
        save()
        print(f"[train-sim-ppo] stopped after {done_n} match(es); saved -> {ppo_path} "
              f"({wins}W-{losses}L-{draws}D)")
