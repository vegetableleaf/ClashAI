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


def compute_gae(rew, val, done, boot, gamma: float, lam: float):
    """Generalized Advantage Estimation over a [T][K] rollout grid.

    rew/val/done: length-T sequences of K-sized float arrays; boot: [K] bootstrap values for the
    states AFTER the last step. Returns (adv, ret) as [T, K] float32 (ret = adv + val)."""
    T = len(rew)
    K = len(boot)
    adv = np.zeros((T, K), np.float32)
    last = np.zeros(K, np.float32)
    for t in reversed(range(T)):
        nxt_v = boot if t == T - 1 else val[t + 1]
        mask = 1.0 - done[t]
        delta = rew[t] + gamma * nxt_v * mask - val[t]
        last = delta + gamma * lam * mask * last
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
    workers = int(workers if workers else cfg.get("sim", "rollout_workers", default=0))
    remote = workers > 1
    if remote:
        # SUBPROCESS ENGINE SHARDS (2026-08-14): the pure-Python engine is one core per process,
        # so rollouts run in `workers` child processes while this process keeps the batched
        # action selection + PPO updates. The parent pins its own torch threads low -- the old
        # 16-thread pool burned ~7 cores of churn on these tiny tensors (measured).
        import torch as _t
        _t.set_num_threads(max(2, 4))
        from .sim.remote_pool import RemotePool
        rpool = RemotePool(K, workers, seed=seed)
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
    cell_ent_coef = float(cfg.get("sim", "ppo_cell_entropy", default=ent_coef))
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
            lp_g = F.log_softmax(gq_m, dim=1)
            g_samp = torch.multinomial(lp_g.exp(), 1).squeeze(1)
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
                if cell_floor > 0.0:
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
                    p_cell = (1.0 - cell_floor) * p_cell_pure + cell_floor * p_floor
                else:
                    p_cell = p_cell_pure
                lp_cell = p_cell.clamp_min(1e-12).log()
                cell = int(torch.multinomial(p_cell.clamp_min(1e-12), 1))
                acts.append((1, ci, cell))
                logps.append(float(lp_g[i, 1] + lp_c_mix[i, ci] + lp_cell[cell]))
        return acts, logps, [float(v) for v in val]

    def choose_greedy(obs_b, hand_b, nxt_b, elx_b, thr_b):
        """Deterministic mode of the policy (benchmark): gate by LOGIT compare, argmax card/cell."""
        net.eval()
        obs_t = torch.stack([to_obs_t(o) for o in obs_b])
        hand_t = torch.stack([to_vec_t(h) for h in hand_b])
        elx_t = torch.stack([to_vec_t(e) for e in elx_b])
        with torch.no_grad():
            cq, ceq, gq, _ = net(obs_t, hand_t, torch.stack([to_vec_t(n) for n in nxt_b]),
                                 elx_t, torch.stack([to_vec_t(t) for t in thr_b]))
        cq_m, _, gq_m, playable = masked_logits(cq, ceq, gq, hand_t, elx_t)
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

    def ppo_update(roll):
        """One PPO update over a finished rollout. roll holds [T] rows of K-sized per-env lists."""
        T = len(roll["rew"])
        adv, ret = compute_gae(roll["rew"], roll["val"], roll["done"], roll["boot"],
                               gamma, gae_lambda)
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
        obs_f, hand_f = flat("obs"), flat("hand")
        nxt_f, elx_f, thr_f = flat("nxt"), flat("elx"), flat("thr")

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
                s2 = torch.clamp(ratio, 1.0 - clip_eps, 1.0 + clip_eps) * a_b
                pl = -torch.min(s1, s2).mean()
                vl = F.mse_loss(val, r_b)
                if _warm["left"] > 0:
                    _warm["left"] -= 1
                    loss = vf_coef * vl                       # critic-only: no policy shove yet
                else:
                    loss = pl + vf_coef * vl - ent_coef * ent.mean() - cell_ent_coef * cell_ent.mean()
                opt.zero_grad(); loss.backward()
                torch.nn.utils.clip_grad_norm_(net.parameters(), max_grad)
                opt.step()
                _clamp_heads()                                # sharpness cap: heads can rank, not rail
                with torch.no_grad():
                    tot_pl += float(pl.detach()); tot_vl += float(vl.detach())
                    tot_ent += float(ent.mean().detach())
                    tot_clip += float(((ratio.detach() - 1.0).abs() > clip_eps).float().mean()); nb += 1
        return tot_pl / nb, tot_vl / nb, tot_ent / nb, tot_clip / nb

    # -- main loop: collect a horizon of experience across K envs, then one PPO update -------------
    if remote:
        cobs = rpool.reset_all()
        chand = [p["hand"] for p in rpool.last]; cnxt = [p["nxt"] for p in rpool.last]
        celx = [p["elx"] for p in rpool.last]; cthr = [p["thr"] for p in rpool.last]
    else:
        cobs = [e.reset() for e in pool]
        chand = [e.hand_vec.copy() for e in pool]; cnxt = [e.next_vec.copy() for e in pool]
        celx = [e.elixir_vec.copy() for e in pool]; cthr = [e.threat_vec.copy() for e in pool]
    ep_r = [0.0] * K
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
    win_hist: deque = deque(maxlen=max(log_every, 50))
    rew_hist: deque = deque(maxlen=max(log_every, 50))
    stats = None
    t0 = time.time()
    try:
        while running["v"] and done_n < matches:
            roll = {"obs": [], "hand": [], "nxt": [], "elx": [], "thr": [],
                    "act": [], "logp": [], "val": [], "rew": [], "done": [], "boot": None}
            for _t in range(horizon):
                if not running["v"] or done_n >= matches:
                    break
                acts, logps, vals = choose_sample(cobs, chand, cnxt, celx, cthr)
                roll["obs"].append(list(cobs)); roll["hand"].append([h.copy() for h in chand])
                roll["nxt"].append([n.copy() for n in cnxt]); roll["elx"].append([e.copy() for e in celx])
                roll["thr"].append([t.copy() for t in cthr])
                roll["act"].append(acts); roll["logp"].append(logps); roll["val"].append(vals)
                rew_row, done_row = [], []
                if remote:
                    step_out = rpool.step_all(acts)
                else:
                    step_out = None
                for i in range(K):
                    if remote:
                        pay = step_out[i]
                        nobs, reward, done = pay["obs"], pay["rew"], pay["done"]
                        info = {"outcome": pay["outcome"], "pfsp": pay["pfsp"]}
                        env = None
                    else:
                        env = pool[i]
                        nobs, reward, done, info = env.step(acts[i])
                    rew_row.append(float(reward)); done_row.append(1.0 if done else 0.0)
                    ep_r[i] += reward
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
                        wins += oc == "win"; losses += oc == "loss"; draws += oc == "draw"
                        win_hist.append(1 if oc == "win" else 0); rew_hist.append(ep_r[i])
                        done_n += 1; _prog["n"] = done_n; ep_r[i] = 0.0
                        cobs[i] = nobs if remote else env.reset()   # workers auto-reset
                        if done_n % log_every == 0:
                            wr = 100.0 * sum(win_hist) / max(1, len(win_hist))
                            ar = sum(rew_hist) / max(1, len(rew_hist))
                            mps = done_n / max(1e-6, time.time() - t0)
                            xs = (f" pl={stats[0]:+.3f} vl={stats[1]:.3f} ent={stats[2]:.2f} "
                                  f"clip={stats[3]:.2f}") if stats else ""
                            print(f"[train-sim-ppo] {done_n} matches: winrate={wr:4.0f}% "
                                  f"avg_rew={ar:+.1f} {mps:.1f} m/s total {wins}W-{losses}L-{draws}D{xs}",
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
                        celx[i], cthr[i] = pay["elx"], pay["thr"]
                    else:
                        chand[i], cnxt[i] = env.hand_vec.copy(), env.next_vec.copy()
                        celx[i], cthr[i] = env.elixir_vec.copy(), env.threat_vec.copy()
                roll["rew"].append(np.asarray(rew_row, np.float32))
                roll["done"].append(np.asarray(done_row, np.float32))
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
                if abs(d_new - _curr["d"]) > 0.02:
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
