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

import os
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


def _log_continuations(roll, K, agent_dt, path):
    """P4 step 1 (design doc 1b, owner go 2026-08-31): HINDSIGHT continuation rows from a
    finished horizon buffer. Pure logging -- reads the buffers, writes JSONL, changes nothing.
    For every PLAY decision, the next play by the SAME env within the horizon (dt in seconds),
    with searched flags for both. `trunc` marks pairs cut by the horizon/episode boundary, so
    the hazard loss can treat them as censored rather than "no next play".
    """
    import json as _json
    T = len(roll["act"])
    rows = []
    for i in range(K):
        plays = [(t, roll["act"][t][i], roll["srch"][t][i]) for t in range(T)
                 if roll["act"][t][i][0] == 1]
        ends = {t for t in range(T) if roll["done"][t][i] > 0.5}
        for j, (t, a, sr) in enumerate(plays):
            nxt = next(((t2, a2, s2) for (t2, a2, s2) in plays[j + 1:]
                        if not any(t <= e < t2 for e in ends)), None)
            rows.append({"t": t, "card": int(a[1]), "cell": int(a[2]), "srch": float(sr),
                         "dt": (None if nxt is None else round((nxt[0] - t) * agent_dt, 2)),
                         "next_card": (None if nxt is None else int(nxt[1][1])),
                         "next_cell": (None if nxt is None else int(nxt[1][2])),
                         "next_srch": (None if nxt is None else float(nxt[2])),
                         "trunc": nxt is None})
    if rows:
        with open(path, "a", encoding="utf-8") as f:
            for r in rows:
                f.write(_json.dumps(r) + chr(10))


def worker_config_args(cfg) -> dict:
    """What a rollout worker needs to rebuild THIS process's config (L59 s9.7).

    Workers are spawned processes that load their own Config. They used to call `Config.load()`
    unconditionally -- config.yaml from disk -- so a `--config <run yaml>` reached the learner and
    its local twin env but not one rollout env, with no error. Two things cross the pipe:
      config_path: the file the parent's Config was read from (`Config.source`; the _KeyOverride /
                   _DrillFracOverride proxies forward the attribute). None for a hand-built Config,
                   which keeps the old behaviour.
      overrides:   the parent's in-memory config changes a file load cannot see, as RESOLVED values
                   (never sentinels): --size mutates action.grid; --drill-only proxies sim.drill_only.
                   A None value means "absent here too" and is not shipped.
    drill_frac and spell_min_value keep their own explicit RemotePool arguments, unchanged.
    """
    src = getattr(cfg, "source", None)
    over = [(k, v) for k, v in (
        (("action", "grid"), cfg.get("action", "grid", default=None)),
        (("sim", "drill_only"), cfg.get("sim", "drill_only", default=None)),
    ) if v is not None]
    return {"config_path": (str(src) if src else None), "overrides": over}


def train_sim_ppo(cfg, matches: int = 2000, resume: bool = False, seed: int = 0, envs=None,
                  init: str | None = None, device: str | None = None,
                  reset_gate: bool = False, workers: int = 0,
                  distill_corpus: str | None = None, distill_coef: float = 0.0,
                  distill_batch: int = 256, search_interval: int = 0,
                  search_horizon: float = 12.0, search_cells: int = 3,
                  search_coef: float = 1.0) -> None:
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
    # silently replaced an explicit 0 with sim.rollout_workers (12), took the REMOTE path, and made
    # the documented contract in --workers' own help ("0/1 = classic in-process") a lie. Combined
    # with the drill_frac bug below it meant every `--drill-frac 0.0` arm actually trained at 0.3.
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
        # ⚠ ALWAYS PASS THE RESOLVED FLOAT. This read `float(...) or None`, and `0.0 or None` is
        # None -- which is RemotePool's "no override, re-read config.yaml in the worker" sentinel.
        # So `--drill-frac 0.0` resolved to 0.0 in the parent, became None on the way out, and each
        # worker went back to disk and got sim.drill_frac (0.3). The override printed its banner
        # and changed nothing: the exact "silent no-op at the seam" HANDOFF §3q was written about.
        # A resolved number is never a sentinel, so the parent's value is now authoritative.
        rpool = RemotePool(
            K, workers, seed=seed,
            drill_frac=float(cfg.get("sim", "drill_frac", default=0.0)),
            # the same rule for the spell veto: a resolved float, never a sentinel, so the
            # workers refuse exactly what this process thinks they refuse (ruling 30).
            spell_min_value=float(cfg.get("sim", "ppo_spell_min_value", default=0.0)),
            # L59 s9.7: the parent's config FILE + in-memory overrides (see worker_config_args)
            **worker_config_args(cfg))
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
    # 2026-08-08 measured "faster on CPU" (1.0 vs 0.2 match/s) -- but that GPU read was taken WHILE
    # A DETECTOR RUN SHARED THE GPU, i.e. on a contended device, so it never applied to an idle
    # one. Re-measured 2026-09-01 (HANDOFF 5ar) on an idle box with the real-run config: the PPO
    # update is 70% of every cycle and 87% of the update is the CNN forward+backward on 4 CPU
    # threads (100 s per update); the identical compute on the idle RTX 5050 is 2.4 s. So the net
    # lives on --device; with `cuda` the parent keeps the learner + action selection on the GPU
    # while the 12 CPU workers still get CPU weights (see _cpu_sd: every pipe/disk seam ships CPU
    # copies, or each worker would unpickle cuda tensors and open its own CUDA context).
    device = torch.device(device) if device else _pick_device(cfg)
    if device.type == "cuda":
        # fp32 numerics on the GPU too: Ampere+ defaults TF32 on for convolutions (10-bit
        # mantissa), which would make cuda-vs-cpu arms differ by more than reduction order.
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cuda.matmul.allow_tf32 = False
        print("[train-sim-ppo] LEARNER ON %s (%s, %.1f GB) -- TF32 off, fp32 throughout; workers stay "
              "on CPU and receive CPU weight copies. (workers 0/1 runs the in-process searchers and "
              "per-env self-play opponents on the GPU one tiny forward at a time: functional, "
              "unmeasured, expected slow -- the measured configuration is --workers 12.)"
              % (device, torch.cuda.get_device_name(device),
                 torch.cuda.get_device_properties(device).total_memory / 1e9))

    value_detach = bool(cfg.get("sim", "ppo_value_detach", default=False))
    # SEPARATE CRITIC FOR DRILL vs MATCH STEPS (ppo_value_head_split).
    # One value head must otherwise fit two return distributions -- a drill episode is ~20 steps,
    # a match ~300 -- and measured it fits neither: value loss is 3-4x worse whenever drills share
    # the batch (1.35-1.83 with drills vs 0.38-0.56 without, no overlap). A miscalibrated critic
    # produces the measured -0.43 mean advantage on MATCH steps, which suppresses match plays no
    # matter what the policy loss wants, and match-only training is healthy (P(play) 0.92-0.99).
    # Per-population advantage normalisation did NOT fix this (0.141/0.162/0.149 vs baseline
    # 0.107-0.151), so the coupling is the critic itself, not the advantage scale.
    value_head_split = bool(cfg.get("sim", "ppo_value_head_split", default=False))
    drill_gate_mask = bool(cfg.get("sim", "ppo_drill_gate_mask", default=False))

    class PPONet(nn.Module):
        """Actor-critic over the SAME PolicyNet trunk/heads the DQN uses (logits, not Q) + a value head."""

        def __init__(self):
            super().__init__()
            self.policy = PolicyNet(in_ch, n_cards, n_cells, threat_dim=threat_dim)
            self.gate = nn.Linear(self.policy.embed_dim, 2)    # [wait, play] logits
            self.value = nn.Linear(self.policy.embed_dim, 1)   # V(s) for GAE -- MATCH steps
            # second critic, used only for drill steps when ppo_value_head_split is on
            self.value_d = nn.Linear(self.policy.embed_dim, 1)
            # P4 HAZARD HEAD (owner go 2026-08-31): time-to-next-own-play, 7 log-spaced bins of
            # agent_dt steps (1, 2, 3-4, 5-8, 9-16, 17-32, >32/censored). Inert at
            # train.hazard_coef 0.0 -- the loss is never computed -- but its PRESENCE consumes
            # init RNG, so new-code runs are not bit-comparable to pre-head runs even at 0.
            # A/B arms must both run THIS code.
            self.hazard = nn.Linear(self.policy.embed_dim, 7)

        def forward(self, x, hand, nxt=None, elx=None, thr=None):
            z, cards, cells = self.policy.forward_parts(x, hand, nxt, elx, thr)
            # VALUE HEAD ON A DETACHED TRUNK (ppo_value_detach). The critic carries 10-30x the
            # gate's gradient norm (value 0.30-1.39 vs gate 0.03-0.05) and shares this trunk with
            # it, so every critic step reshapes the features `gate = Linear(z, 2)` reads. Measured,
            # the gate moves AGAINST its own policy gradient: the PPO term pushes +0.014 toward
            # PLAY and entropy +0.0002 toward PLAY, yet log pi(play) falls 0.17-0.41 per update on
            # the states where it played. Neither policy term explains that; representation drift
            # driven by the critic is the only remaining path. Detaching lets the critic fit V
            # without dragging the trunk, at the cost of a weaker critic (it becomes a linear probe
            # on policy features) -- which is why this is a FLAG, not a default.
            v_in = z.detach() if value_detach else z
            v_m = self.value(v_in).squeeze(-1)
            v_d = self.value_d(v_in).squeeze(-1) if value_head_split else v_m
            return cards, cells, self.gate(z), v_m, v_d, self.hazard(z)

    net = PPONet().to(device)

    # ------------------------------------------------ CARD-HEAD DISTILLATION (teacher = rollout search)
    # research/sim_parity/ledger/distillation.md. Measured on a held-out split BY MATCH: the CARD
    # head goes 0.4955 -> 0.8754 agreement with the search teacher (+38pp over the base policy),
    # while the GATE goes 0.5892 -> 0.6012 and sits BELOW the always-WAIT floor of 0.7756.
    # So this term trains the CARD HEAD ONLY. Distilling the gate from this corpus is not supported
    # by the measurement and is deliberately not done.
    _dst = None
    if distill_corpus and distill_coef > 0.0:
        import json as _json
        _dp = Path(distill_corpus)
        if not _dp.exists():
            print(f"[train-sim-ppo] --distill-corpus not found: {_dp}")
            return
        _dz = np.load(str(_dp), allow_pickle=True)
        _dmeta = _json.loads(str(_dz["meta"])) if "meta" in _dz.files else {}
        # HEAD SHAPE IS NOT NEGOTIABLE. icebow has 10 cards and hogeq 11; a corpus from the other
        # deck would index a different card set and silently teach the wrong card everywhere.
        _dn = int(_dmeta.get("n_cards", -1))
        if _dn != int(n_cards):
            print(f"[train-sim-ppo] REFUSING distillation: corpus n_cards={_dn}, this deck has {n_cards}.")
            return
        _dobs = tuple(_dmeta.get("obs_shape") or ())
        if _dobs and tuple(int(x) for x in e0.obs_shape) != _dobs:
            print(f"[train-sim-ppo] REFUSING distillation: corpus obs {_dobs} != env obs "
                  f"{tuple(int(x) for x in e0.obs_shape)}.")
            return
        # TEACHER-PLAY ROWS ONLY: teach_card is -1 wherever the teacher waited, and the measured
        # quantity is card-given-teacher-plays. Rows where it waited carry no card label at all.
        _dsel = np.nonzero(np.asarray(_dz["teach_card"]) >= 0)[0]
        if _dsel.size < 64:
            print(f"[train-sim-ppo] REFUSING distillation: only {_dsel.size} teacher-play rows.")
            return
        _dst = {k: np.ascontiguousarray(_dz[k][_dsel]) for k in ("obs", "hand", "nxt", "elx", "thr")}
        _dst["card"] = np.ascontiguousarray(np.asarray(_dz["teach_card"])[_dsel]).astype(np.int64)
        _dst["n"] = int(_dsel.size)
        print(f"[train-sim-ppo] DISTILL card head: {_dst['n']} teacher-play rows from {_dp.name} "
              f"(coef {distill_coef}, batch {distill_batch})")
        print(f"[train-sim-ppo]   corpus provenance: commit {str(_dmeta.get('git_commit'))[:12]} "
              f"dirty={_dmeta.get('git_dirty')} ckpt {_dmeta.get('checkpoint_sha256_16')} "
              f"N={_dmeta.get('interval')} PYTHONHASHSEED={_dmeta.get('pythonhashseed')}")
        if str(_dmeta.get("interval")) not in ("1", "1.0"):
            # N=1 is not a preference: at N=5 the unsearched decisions between labelled ones
            # contaminate the targets and the restraint signal comes out with the WRONG SIGN.
            print("[train-sim-ppo]   WARNING: corpus interval is NOT 1 -- the restraint signal may be inverted.")
    _dstat = {"loss": 0.0, "n": 0, "kept": 0, "seen": 0}


    # masks shared with train_sim: anywhere cards -> all cells, else YOUR half; affordability by cost
    anywhere_ids = set(e0.anywhere_ids)
    yourhalf_mask = torch.tensor(e0.actions.deployable_mask(False), dtype=torch.bool, device=device)
    # POCKET-AWARE CELL MASKS. Destroying an enemy princess opens deployment across the river on
    # that side, so the legal cell set is a property of the BOARD, not a constant. Rather than store
    # a 432-bool mask per step, precompute the four possibilities and store a 2-bit code
    # (2*left + right) per step -- the update then rebuilds exactly the mask sampling used, which is
    # what keeps the stored log-probs valid.
    pocket_masks = torch.stack([
        torch.tensor(e0.actions.deployable_mask(False, (bool(code & 2), bool(code & 1))),
                     dtype=torch.bool, device=device)
        for code in range(4)
    ])                                                  # [4, n_cells]
    allcells_mask = torch.ones(n_cells, dtype=torch.bool, device=device)
    anywhere_ids_t = torch.tensor(sorted(anywhere_ids), dtype=torch.long, device=device)
    card_costs_t = torch.tensor([float(s.elixir) for s in e0.specs], dtype=torch.float32, device=device)
    # WIN-CONDITION BANK: the deck's win conditions (X-Bow / Rocket) and the elixir needed for the
    # cheapest of them. bank_floor 0 disables the rule entirely (the original always-affordable mask).
    wincon_ids = sorted(set(e0.xbow_ids) | set(e0.rocket_ids))
    wincon_ids_t = torch.tensor(wincon_ids, dtype=torch.long, device=device)
    wincon_cost = min((float(e0.specs[i].elixir) for i in wincon_ids), default=0.0)
    bank_floor = float(cfg.get("sim", "wincon_bank_floor", default=0.0)) if wincon_ids else 0.0
    if bank_floor > 0.0:
        print(f"[train-sim-ppo] win-condition bank ON: holding {wincon_cost:.0f}-elixir "
              f"{'/'.join(e0.deck_keys[i] for i in wincon_ids)} masks cheaper cards from "
              f"{bank_floor:.0f} elixir up, so the bar can actually reach them")

    ppo_path = cfg.path(cfg.get("train", "sim_ppo_checkpoint", default="data/policy_sim_ppo.pt"))
    # WHEN-NOT-TO-PLAY FROM A SOURCE THAT KNOWS (owner ruling 2026-09-02 08:20, HANDOFF 6 / 5bf).
    # The 18k run's elixir>=6 share fell 2% -> 0.02% and three wait-side reward terms are dead at
    # 3 seeds, so this is NOT a reward: it is a cross-entropy pull of the GATE head (only) toward
    # the pro P(play | elixir bucket, phase) table that tools/gate_prior.py fits from the crawled
    # replays. KL(prior || pi) up to a constant. Card and cell heads are untouched; drill rows and
    # rows with nothing affordable (play masked) are excluded. coef 0.0 = off, byte-for-byte.
    gate_prior_coef = float(cfg.get("sim", "ppo_gate_prior_coef", default=0.0))
    # THE THIRD KEY (HANDOFF 5bw/5bx): the ruling's "threat on our half" was dropped from v0, and
    # the blended table pulls "wait" twice as hard as pros on rows where the opponent just played a
    # troop (5-7 elixir: pros play 8.6/6.8/6.6% under pressure vs 2.4/3.0/2.9% quiet). W > 0 reads
    # a schema-2 table split by "opponent troop within W s" and keys the sim rows on "youngest
    # living enemy troop younger than W s" (SimMatchEnv.enemy_troop_min_age). 0.0 = the blended
    # table, byte-for-byte what the gate05 run trained on.
    gate_prior_pressure_s = float(cfg.get("sim", "ppo_gate_prior_pressure_s", default=0.0))
    _gprior = None
    if gate_prior_coef > 0.0:
        import json as _gjson
        _gpp = cfg.path(cfg.get("sim", "ppo_gate_prior_path", default="config/gate_prior.json"))
        _gj = _gjson.loads(Path(_gpp).read_text(encoding="utf-8"))
        assert _gj.get("schema") in (1, 2), "gate prior: unknown schema"
        _greg, _got = float(_gj["regulation_s"]), float(_gj["overtime_s"])
        if gate_prior_pressure_s > 0.0:
            assert _gj.get("schema") == 2, "gate prior: ppo_gate_prior_pressure_s > 0 needs a schema-2 table"
            assert abs(float(_gj["pressure_s"]) - gate_prior_pressure_s) < 1e-6, (
                "gate prior: table fit at W=%s s, config asks %s s" % (_gj["pressure_s"], gate_prior_pressure_s))
            _gtab0 = np.asarray([[_gj["p_play_by_pressure"][p][k] for k in ("quiet", "pressure")]
                                 for p in ("single", "double", "triple")], np.float32)   # [phase, pres, bucket]
        else:
            _gtab0 = np.asarray([_gj["p_play"][p] for p in ("single", "double", "triple")], np.float32)
        _gprior = (_gtab0, _greg - 60.0, _greg + max(0.0, _got - 60.0))
        if gate_prior_pressure_s > 0.0:
            print("[train-sim-ppo] GATE PRIOR ON: coef %.3f, %s (%d replays, dt %.1f s; PRESSURE key W=%.0f s; "
                  "single-elixir P(play) at 4 / 7 / 9 elixir quiet %.3f / %.3f / %.3f, pressure %.3f / %.3f / %.3f)"
                  % (gate_prior_coef, _gpp, int(_gj.get("replays", 0)), float(_gj.get("dt", 0.0)),
                     gate_prior_pressure_s, _gtab0[0][0][4], _gtab0[0][0][7], _gtab0[0][0][9],
                     _gtab0[0][1][4], _gtab0[0][1][7], _gtab0[0][1][9]))
        else:
            print("[train-sim-ppo] GATE PRIOR ON: coef %.3f, %s (%d replays, dt %.1f s; single-elixir "
                  "P(play) at 4 / 7 / 9 elixir = %.2f / %.2f / %.2f)"
                  % (gate_prior_coef, _gpp, int(_gj.get("replays", 0)), float(_gj.get("dt", 0.0)),
                     _gprior[0][0][4], _gprior[0][0][7], _gprior[0][0][9]))
    _gpstat = {"n": 0, "ce": 0.0, "pi": 0.0, "p": 0.0, "rows": 0, "seen": 0, "pres": 0.0}
    hazard_coef = float(cfg.get("train", "hazard_coef", default=0.0))
    if hazard_coef > 0.0:
        print("[train-sim-ppo] HAZARD HEAD ON: coef %.3f, 7 log-spaced dt bins" % hazard_coef)
    # P4 step 1: hindsight continuation logging (JSONL). Empty = OFF (provably zero change).
    cont_log = str(cfg.get("train", "continuation_log", default="") or "")
    if cont_log:
        cont_log = str(cfg.path(cont_log))
        print("[train-sim-ppo] continuation log ON -> %s" % cont_log)
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
        if "value_d" in ck:
            net.value_d.load_state_dict(ck["value_d"])
        elif value_head_split:
            print("[train-sim-ppo]   NOTE: this checkpoint predates the split critic, so the DRILL "
                  "value head starts fresh; expect its value loss to settle over the first "
                  "few updates.")
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
            cell_raws = []
            with torch.no_grad():
                for _ in range(8):
                    # /255: THE INPUT THE NET IS TRAINED ON. Until 2026-09-01 (5ar) this fed the
                    # raw uint8 board as 0..255 floats, 255x what to_obs_t feeds, so the guard read
                    # every head as saturated: the real run's m=2250 checkpoint measured raw absmax
                    # card 1424 / cell 35276 through this path against 8.2 / 143 normalized, and
                    # a --resume would have shrunk the card head x0.0021 (it is healthy). Nothing
                    # resumed a checkpoint through the guard before that day (no log carries its
                    # message), so no run was harmed -- but any --resume, manual or a relauncher's,
                    # would have been.
                    px = (torch.from_numpy(np.asarray(pobs, np.float32)).unsqueeze(0)
                          .permute(0, 3, 1, 2).to(device) / 255.0)
                    pv = [torch.from_numpy(getattr(penv, k).astype(np.float32)).unsqueeze(0).to(device)
                          for k in ("hand_vec", "next_vec", "elixir_vec", "threat_vec")]
                    fmap = net.policy.features(px)
                    z = net.policy._embed(fmap, *pv)
                    worst_card = max(worst_card, float(net.policy.card_head(z).abs().max()))
                    cell_raw = net.policy._cell_logits(fmap, z).abs()
                    worst_cell = max(worst_cell, float(cell_raw.max()))
                    cell_raws.append(cell_raw.flatten())
                    po = penv.step((True, 0, 200))
                    pobs = po[0] if not po[2] else penv.reset()
                fixed = []
                if worst_card > 2.0 * _LOGIT_CAP:
                    a = 3.0 / worst_card
                    net.policy.card_head.weight.mul_(a)
                    net.policy.card_head.bias.mul_(a)
                    fixed.append(f"card head x{a:.4f} (raw absmax {worst_card:.0f})")
                # CELL CRITERION = p99 of |raw|, not the max (2026-09-05, HANDOFF 5cs.38). A healthy
                # head has a few confident cells past the cap -- the BC-initialised heads
                # (bc_bias_native_s*, p99 ~6 by construction) reach absmax 20-28 on real boards, and
                # the max rule would have shrunk their conv residual x0.2 on load while leaving the
                # bias map alone, silently changing the init being tested. The saturated case the
                # guard exists for (c2r_best: 92% of masked cells |raw| > 8, p99 62) still trips.
                cell_p99 = float(torch.quantile(torch.cat(cell_raws), 0.99))
                if cell_p99 > 2.0 * _LOGIT_CAP:
                    a = 4.5 / cell_p99
                    last = net.policy.cell_conv[-1]
                    last.weight.mul_(a)
                    if last.bias is not None:
                        last.bias.mul_(a)
                    fixed.append(f"cell head x{a:.4f} (raw p99 {cell_p99:.0f}, absmax {worst_cell:.0f})")
                else:
                    print(f"[train-sim-ppo] rail guard: cell head raw p99 {cell_p99:.1f} "
                          f"(absmax {worst_cell:.0f}) within 2x cap -- left as loaded")
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
    clip_per_head = bool(cfg.get("sim", "ppo_clip_per_head", default=False))
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

    def to_obs_t(o):                     # per-sample reference chains; the batched forms below
        return torch.from_numpy(o).float().permute(2, 0, 1).to(device) / 255.0     # are checked

    def to_vec_t(v):                     # against these (tools/check_batched_assembly.py)
        return torch.from_numpy(np.asarray(v, np.float32)).to(device)

    # BATCHED ASSEMBLY (5ar). The per-sample chains above cost 512 tiny copies per minibatch --
    # 12% of a CPU update, and on a GPU 2,560 separate host->device copies per minibatch (measured
    # 18 s per update vs 3 s batched). One numpy stack, one device copy, one permute. Bit-identical
    # to torch.stack([to_obs_t(o) ...]): uint8 -> float32 is exact, /255.0 is the same elementwise
    # op, and .contiguous() lands the same NCHW layout torch.stack produced (so cudnn/oneDNN see
    # the same tensor, not a channels-last one that would pick different kernels). Verified with
    # torch.equal on both devices before it replaced the chains.
    def to_obs_batch(obs_list):
        return (torch.from_numpy(np.stack(obs_list)).to(device).permute(0, 3, 1, 2).contiguous()
                .float() / 255.0)

    def to_vec_batch(vec_list):
        return torch.from_numpy(np.stack([np.asarray(v, np.float32) for v in vec_list])).to(device)

    def _cpu_sd(mod):
        """state_dict as CPU tensors -- what every pipe/disk seam ships (workers, league, saves),
        so a cuda learner never hands cuda tensors to the 12 CPU workers or to tools that load
        checkpoints with map_location='cpu'. On a CPU net this is the plain state_dict."""
        return {k: v.detach().cpu() for k, v in mod.state_dict().items()}

    def masked_logits(cq, ceq, gq, hand_t, elx_t, card_idx=None, pocket_code=None,
                      stored_cm=None):
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
        if pocket_code is None:
            half = yourhalf_mask.unsqueeze(0).expand(cq.shape[0], -1)
        else:
            half = pocket_masks[pocket_code.clamp(0, 3)]          # per-row, from the stored code
        cellmask = torch.where(is_any.unsqueeze(1), allcells_mask.unsqueeze(0), half)
        if stored_cm is not None:
            # A spell's legal cells depend on where the ENEMY was standing at that instant, which
            # cannot be recovered from the stored observation. So the mask that sampling actually
            # applied is stored and replayed here verbatim; rows without one keep the mask computed
            # above. Without this the update re-scores a play against a different action set than
            # the one it was drawn from, and the importance ratio stops meaning anything.
            use = stored_cm.any(1)
            cellmask = torch.where(use.unsqueeze(1), stored_cm, cellmask)
        # PER-CARD map: ceq is (B, n_cards, n_cells) now, so pick the row for the card that was
        # actually played. Everything downstream keeps the old (B, n_cells) shape, which is what
        # makes the log-prob gather and the PPO ratio identical to before.
        sel = ceq.gather(1, card_idx.view(-1, 1, 1).expand(-1, 1, ceq.shape[-1])).squeeze(1)
        return cq_m, sel.masked_fill(~cellmask, _NEG), gq_m, playable

    # ------------------------------------------------------------------ SPELL CARD VETO
    # `spell_experiments.md` §7.5: promote the spell mask from a CELL mask to a CARD veto. Measured
    # at eval, n=300 paired GREEDY, the >=3-body clump form is +0.233 tower fractions (3.58σ) over
    # the baseline and +0.207 (2.98σ) over a VOLUME-MATCHED random spell ban, so the criterion and
    # not merely the volume cut is doing the work. The BODY-COUNT form was rejected by the owner
    # (it refuses `nado_king_activation`, `nado_the_sneaky_lock`, `rocket_the_two_for_one` and
    # `rocket_the_pump_on_sight`, all single-body reference lines), so the shipped criterion is on
    # VALUE in tower fractions plus an exemption set -- SimMatchEnv.spell_card_ok, ruling 30.
    #
    # ⚠ APPLIED IN BOTH `choose_sample` AND `choose_greedy`. Until now `choose_greedy` applied NO
    # spell restriction of any kind, so eval and live cast spells unmasked while sampling ran
    # masked. The annealed CELL mask below stays sampling-only on purpose -- its own docstring
    # calls it a training wheel that decays to `ppo_spell_mask_end` -- but a veto is a RULE, so it
    # must hold wherever the policy acts or the benchmark grades behaviour that never ships.
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

    spell_mask_on = bool(cfg.get("sim", "ppo_spell_target_mask", default=False))
    spell_mask_anneal = float(cfg.get("sim", "ppo_spell_mask_anneal", default=0.0))
    spell_mask_end = float(cfg.get("sim", "ppo_spell_mask_end", default=0.0))

    def _spell_mask_now() -> float:
        """How OFTEN the spell mask is applied at this point in training.

        A PERMANENT mask caps the model at the judgement encoded in the criterion. It can never
        discover a cast the criterion forbids -- a "whiff" at empty ground that a Hog is about to
        walk into is a real technique, and _spell_no_target would veto it forever. Owner's point,
        and it is right: hardcoding what the model may do limits it to what a human thought of.

        So the mask is a TRAINING WHEEL, the same shape as the exploration floors and
        train.training_wheels: near-total early, when the policy is close to random and a whiffed
        Rocket is 6 elixir of pure noise, then decaying to `ppo_spell_mask_end` so the model plays
        unmasked once it has something better than noise to offer. Applied PROBABILISTICALLY rather
        than switched off at a threshold, so exposure to unmasked casting arrives gradually and the
        cell head keeps receiving gradient on those cells throughout.
        """
        if not spell_mask_on:
            return 0.0
        if spell_mask_anneal <= 0.0:
            return 1.0
        f = min(1.0, max(0.0, float(_prog.get("n", 0)) / spell_mask_anneal))
        return 1.0 + (spell_mask_end - 1.0) * f
    spell_ids = {i for i in range(n_cards)
                 if getattr(e0.specs[i], "kind", "") == "spell"} if spell_mask_on else set()

    def _spell_cells(env_i, card_id):
        """Target mask for this env's board, or None when unavailable."""
        try:
            if remote:
                return None                       # workers cannot be queried mid-rollout
            return pool[env_i].spell_target_mask(int(card_id))
        except Exception:
            return None

    def pocket_now():
        """2-bit pocket code per env: 2*left_open + right_open, from the LIVE board."""
        out = []
        for e in (pool if not remote else []):
            try:
                l, r = e.pocket_state(0)
            except Exception:
                l, r = False, False
            out.append((2 if l else 0) + (1 if r else 0))
        if remote:
            out = [int(p.get("pocket", 0)) for p in rpool.last]
        return out

    def choose_sample(obs_b, hand_b, nxt_b, elx_b, thr_b):
        """Sample (gate, card, cell) from the factored policy for all K envs; return acts, logps, values."""
        net.eval()
        obs_t = to_obs_batch(obs_b)
        hand_t = to_vec_batch(hand_b)
        elx_t = to_vec_batch(elx_b)
        # POCKET per env, as a 2-bit code. Stored in the rollout so the update rebuilds the exact
        # mask that sampling used -- otherwise the stored log-prob describes a different action set
        # than the one being re-scored, and the importance ratio silently stops meaning anything.
        pk_codes = pocket_now()
        pk_t = torch.tensor(pk_codes, dtype=torch.long, device=device)
        with torch.no_grad():
            cq, ceq, gq, val_m, val_d, _hz = net(obs_t, hand_t, to_vec_batch(nxt_b),
                                            elx_t, to_vec_batch(thr_b))
            val = val_m
            if value_head_split:
                _sel = torch.tensor([1.0 if in_drill[i] else 0.0 for i in range(len(obs_b))],
                                    dtype=val_m.dtype, device=val_m.device)
                val = torch.where(_sel > 0.5, val_d, val_m)
            cq_m, _, gq_m, playable = masked_logits(cq, ceq, gq, hand_t, elx_t, pocket_code=pk_t)
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
                                    lambda si, _i=i: (allcells_mask if si in anywhere_ids
                                                      else pocket_masks[pk_codes[_i]])))
            # GATE SAMPLING, with a DRILL TIMING PRIOR mixed in. Same shape as the card and cell
            # floors below and for the same reason: a head that never samples an action gets no
            # gradient for it. Here the unsampled action is HOLDING -- the gate sits near 50/50
            # early in training, so a drill passed by waiting twelve steps and then playing is
            # reached with probability ~0.5^12, and every timing drill measured zero passes in 60
            # episodes. The prior is the drill's own reference line, which records when each card
            # is played. Stored log-prob is the MIXTURE's, so the PPO ratio stays exact.
            p_g = F.log_softmax(gq_m, dim=1).exp()
            # BEHAVIOUR vs NETWORK. The gate the game sees is not always the gate the network
            # asked for: on DRILL steps it is mixed with the drill's reference line at
            # ppo_drill_gate_floor. 3p already found this class once -- floors overriding the bot
            # 75-85% of the time, pi/mu ~0.0125 -- so measure the override rather than assume it.
            # `_pure` is the network's own P(play); `_mix` is what actually samples.
            _bvg["pure_m"] += float(p_g[[i for i in range(p_g.shape[0]) if not in_drill[i]], 1].sum())                 if any(not in_drill[i] for i in range(p_g.shape[0])) else 0.0
            _bvg["n_m"] += sum(1 for i in range(p_g.shape[0]) if not in_drill[i])
            _bvg["pure_d"] += float(p_g[[i for i in range(p_g.shape[0]) if in_drill[i]], 1].sum())                 if any(in_drill[i] for i in range(p_g.shape[0])) else 0.0
            _bvg["n_d"] += sum(1 for i in range(p_g.shape[0]) if in_drill[i])
            _bvg["greedy"] += int((p_g[:, 1] > gate_tau).sum())
            _bvg["n_all"] += int(p_g.shape[0])
            # IS AFFORDABILITY THE BINDING CONSTRAINT? `playable` is the per-card in-hand AND
            # affordable mask, and masked_logits masks the PLAY gate to -inf when nothing passes it.
            # So p_g[:,1] already carries the mask, while gate_probe's sigmoid(gq1-gq0) does NOT --
            # which is the whole 0.03-vs-0.116 gap. Split it: how often is anything affordable, and
            # what does the gate want WHEN IT HAS THE CHOICE.
            _aff = playable.any(dim=1)
            _raw = torch.sigmoid(gq_m[:, 1] - gq_m[:, 0])
            _bvg["aff"] += int(_aff.sum())
            if int(_aff.sum()) > 0:
                _bvg["pg_aff"] += float(p_g[_aff, 1].sum())
                _bvg["raw_aff"] += float(_raw[_aff].sum())
                _bvg["n_aff"] += int(_aff.sum())
            _bvg["raw_all"] += float(_raw.sum())
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
            _bvg["mix_d"] += float(p_g[[i for i in range(p_g.shape[0]) if in_drill[i]], 1].sum())                 if any(in_drill[i] for i in range(p_g.shape[0])) else 0.0
            _bvg["played"] += int((g_samp == 1).sum())
            _bvg["n"] += 1
            # AFFORDABILITY prints on its own condition. It was nested under the behaviour print,
            # which requires DRILL steps -- so at --drill-frac 0 (the only honest way to read the
            # match economy) it could never fire at all.
            if (_bvg["n"] <= 3 or _bvg["n"] % 100 == 0) and _bvg["n_aff"] > 0:
                print("[train-sim-ppo]   AFFORDABILITY  anything playable on %.1f%% of steps | "
                      "gate P(play) GIVEN a choice %.4f | raw pref %.4f overall"
                      % (100.0 * _bvg["aff"] / _bvg["n_all"],
                         _bvg["pg_aff"] / max(1, _bvg["n_aff"]),
                         _bvg["raw_all"] / _bvg["n_all"]), flush=True)
            if _bvg["n"] % 400 == 0 and _bvg["n_m"] > 0 and _bvg["n_d"] > 0:
                print("[train-sim-ppo]   BEHAVIOUR vs NETWORK  match P(play) %.4f (n=%d) | "
                      "drill pure %.4f -> mixed %.4f (n=%d) | sampled-play %.4f | greedy>tau %.4f"
                      % (_bvg["pure_m"] / _bvg["n_m"], _bvg["n_m"],
                         _bvg["pure_d"] / _bvg["n_d"], _bvg["mix_d"] / _bvg["n_d"], _bvg["n_d"],
                         _bvg["played"] / _bvg["n_all"], _bvg["greedy"] / _bvg["n_all"]), flush=True)

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
            acts, logps, lparts = [], [], []
            # the cell mask ACTUALLY used per env, stored so the update re-scores under the same
            # action set -- a mask that differs between sampling and update silently invalidates
            # every importance ratio (the same discipline the pocket code needed).
            cellmasks = [None] * len(obs_b)
            for i in range(len(obs_b)):
                g = int(g_samp[i])
                if g == 0:
                    acts.append((0, 0, 0)); logps.append(float(lp_g[i, 0]))
                    lparts.append((float(lp_g[i, 0]), 0.0, 0.0))   # wait: gate only
                    continue
                ci = int(c_samp[i])
                cmask = allcells_mask if ci in anywhere_ids else pocket_masks[pk_codes[i]]
                # SPELL TARGET MASK. A whiffed spell is not a judgement error that a -0.3 penalty
                # can argue the policy out of -- during exploration it is a RANDOM choice, and this
                # codebase already learned that once (actions.no_king_mask: "A reward cannot stop a
                # random choice; only a mask can"). The real cost is the ELIXIR: a whiffed Rocket is
                # 6 elixir not available for the next counter, so one bad cast becomes a missed
                # defence too -- reported as the single biggest weakness in live play.
                #
                # Computed only when a SPELL is actually the sampled card (~5% of env-steps), since
                # even vectorised it is 0.23 ms per spell per env.
                if ci in spell_ids and random.random() < _spell_mask_now():
                    tm = _spell_cells(i, ci)
                    if tm is not None:
                        tmt = torch.as_tensor(tm, dtype=torch.bool, device=cmask.device)
                        if bool(tmt.any()):
                            cmask = cmask & tmt          # nothing to hit anywhere -> leave as-is
                cellmasks[i] = cmask
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
                lparts.append((float(lp_g[i, 1]), float(lp_c_mix[i, ci]),
                               float(lp_cell[cell])))
        return acts, logps, [float(v) for v in val], lparts, pk_codes, cellmasks

    def _drill_gate(env):
        """Local-pool twin of RemotePool.drill_gate."""
        try:
            return env.drill_prior_gate() if hasattr(env, "drill_prior_gate") else None
        except Exception:  # noqa: BLE001 -- a bad reference must not break the rollout
            return None

    def choose_greedy(obs_b, hand_b, nxt_b, elx_b, thr_b, envs=None):
        """Deterministic mode of the policy (benchmark): gate by LOGIT compare, argmax card/cell."""
        net.eval()
        obs_t = to_obs_batch(obs_b)
        hand_t = to_vec_batch(hand_b)
        elx_t = to_vec_batch(elx_b)
        with torch.no_grad():
            cq, ceq, gq, _, _, _ = net(obs_t, hand_t, to_vec_batch(nxt_b), elx_t, to_vec_batch(thr_b))
        cq_m, _, gq_m, playable = masked_logits(cq, ceq, gq, hand_t, elx_t)
        # THE SAME CARD VETO THE SAMPLER APPLIES. Without this the benchmark grades a policy that
        # casts spells under no restriction at all while training ran under one -- the asymmetry
        # spell_experiments.md §7.5 flagged. `envs` is the caller's pool, in the same row order.
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
        torch.save({"model": _cpu_sd(net.policy), "gate": _cpu_sd(net.gate),
                    "value": _cpu_sd(net.value),
                    # THE DRILL CRITIC TOO (2026-08-23). Only `value` was saved, so a --resume
                    # rebuilt `value_d` from scratch and the drill population trained against a
                    # RANDOM critic until it refit -- silently undoing ppo_value_head_split, the
                    # one thing that flag exists to provide. Harmless when the flag is off (value_d
                    # is unused), so it is written unconditionally and read back only if present.
                    "value_d": _cpu_sd(net.value_d), "algo": "ppo",
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
    adv_norm_split = bool(cfg.get("sim", "ppo_adv_norm_split", default=False))
    deck_pfsp_power = float(cfg.get("sim", "deck_pfsp_power", default=0.0))
    deck_rec_every = int(cfg.get("sim", "deck_record_ship_every", default=50))
    _dirty = {"n": 0}
    _adv_signed = {"want": True, "drill": 0.0, "match": 0.0, "shift": 0.0}
    _adv_stats = {"drill": 0.0, "match": 0.0, "frac_drill_steps": 0.0}
    _probe = bool(os.environ.get("CLASHRL_GATE_PROBE"))   # heavy diagnostics: 3 extra
    _terms = {"want": _probe, "ppo": 0.0, "entropy": 0.0, "value": 0.0, "n": 0}
    _gnorm = {"want": _probe, "gate": 0.0, "card": 0.0, "cell": 0.0, "val": 0.0,
              "n": 0, "gate_w": 0.0}
    _ep0 = {"want": True}
    _advk = {"p_sum": 0.0, "p_n": 0, "w_sum": 0.0, "w_n": 0, "n": 0}
    _bvg = {"pure_m": 0.0, "n_m": 0, "pure_d": 0.0, "mix_d": 0.0, "n_d": 0,
            "played": 0, "greedy": 0, "n_all": 0, "n": 0,
            "aff": 0, "pg_aff": 0.0, "raw_aff": 0.0, "raw_all": 0.0, "n_aff": 0}
    _lastep = {"want": True}
    _clip_split = {"play": 0.0, "play_n": 0.0, "wait": 0.0, "wait_n": 0.0,
                   "play_block": 0.0, "wait_block": 0.0, "play_push": 0.0, "wait_push": 0.0,
                   "play_raw": 0.0, "wait_raw": 0.0,
                   "gate_z": 0.0, "gate_z_raw": 0.0}

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
        sds = [{"model": _cpu_sd(n.policy), "gate": _cpu_sd(n.gate)} for n in nets]
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
        # 5ar profile sub-buckets (only when CLASHRL_PROFILE=1; `_pc` is the cycle's bucket dict)
        _pu = ({"u_prep": 0.0, "u_mb": 0.0, "u_fwd": 0.0, "u_bwd": 0.0, "u_step": 0.0}
               if _pc is not None else None)
        _pt0 = time.perf_counter()
        T = len(roll["rew"])
        adv, ret = compute_gae(roll["rew"], roll["val"], roll["done"], roll["boot"],
                               gamma, gae_lambda, trunc=roll.get("trunc"))
        # flatten [T, K] -> [N]
        def flat(key):
            return [roll[key][t][i] for t in range(T) for i in range(K)]
        N = T * K
        adv_f = torch.tensor(adv.reshape(-1), device=device)
        # PER-POPULATION ADVANTAGE NORMALISATION (ppo_adv_norm_split).
        #
        # Normalising over the WHOLE mixed batch shares one mean between two populations with
        # different return scales -- a drill episode is ~20 steps, a match ~300. Subtracting a
        # common mean therefore SHIFTS one population relative to the other. Measured, the gate
        # drift splits like this with drills at 30% of steps:
        #     DRILL steps:  PLAY -0.234   WAIT -0.063
        #     match steps:  PLAY -0.101   WAIT +0.006
        # Match steps are pushed away from playing too -- even though match-only training is
        # perfectly healthy (3 seeds at drill_frac 0.0 hold P(play) 0.92-0.99 while drill_frac 0.3
        # collapses to 0.11-0.15). Something SHARED is poisoning the match steps, and the shared
        # thing is this mean.
        #
        # Normalising each population against its own mean and std removes the coupling: a drill's
        # advantage is judged against other drills, a match step against other match steps.
        # NOTE: built whenever the flag exists, not only for adv_norm_split -- the value-head
        # routing needs it too, and an earlier version left it None unless adv_norm_split was on,
        # which would have made ppo_value_head_split silently do nothing.
        _dsplit = (torch.tensor(flat("isdrill"), dtype=torch.float32, device=device)
                   if roll.get("isdrill") else None)
        if adv_norm_split and _dsplit is not None:
            _out = adv_f.clone()
            for _sel in (_dsplit > 0.5, _dsplit <= 0.5):
                if int(_sel.sum()) > 1:
                    _p = adv_f[_sel]
                    _out[_sel] = (_p - _p.mean()) / (_p.std() + 1e-8)
            adv_f = _out
        else:
            adv_f = (adv_f - adv_f.mean()) / (adv_f.std() + 1e-8)
        if roll.get("isdrill") and _adv_signed["want"]:
            # SIGNED means, pre-normalisation -- the |mean| diagnostic below cannot show a SHIFT,
            # only a magnitude gap, and a shift is exactly what would move one population.
            _raw = torch.tensor(adv.reshape(-1), device=device)
            _dm = torch.tensor(flat("isdrill"), dtype=torch.float32, device=device)
            if float(_dm.sum()) > 1 and float((1.0 - _dm).sum()) > 1:
                _adv_signed["drill"] = float(_raw[_dm > 0.5].mean())
                _adv_signed["match"] = float(_raw[_dm <= 0.5].mean())
                _adv_signed["shift"] = _adv_signed["drill"] - _adv_signed["match"]
        ret_f = torch.tensor(ret.reshape(-1), device=device)
        oldlp_f = torch.tensor(flat("logp"), dtype=torch.float32, device=device)
        # PER-HEAD old log-probs [N,3] = (gate, card, cell). Needed to see WHICH head
        # moves a play out of the trust region -- measured, a play swings +-35-46% while
        # a wait swings +-0.5-2.4% (17-84x), which three comparable heads cannot explain.
        def _cm_flat():
            raw = flat("cm") if roll.get("cm") else None
            if not raw:
                return None
            out = np.zeros((len(raw), n_cells), dtype=bool)
            any_set = False
            for i, m in enumerate(raw):
                if m is not None:
                    out[i] = m; any_set = True
            return torch.tensor(out, dtype=torch.bool, device=device) if any_set else None
        cm_f = _cm_flat()
        pk_f = (torch.tensor(flat("pk"), dtype=torch.long, device=device)
                if roll.get("pk") else torch.zeros(N, dtype=torch.long, device=device))
        oldp_f = (torch.tensor(flat("lparts"), dtype=torch.float32, device=device)
                  if roll.get("lparts") else torch.zeros(N, 3, device=device))
        g_f = torch.tensor([a[0] for a in flat("act")], device=device)
        c_f = torch.tensor([a[1] for a in flat("act")], device=device)
        cell_f = torch.tensor([a[2] for a in flat("act")], device=device)
        sil_f = (torch.tensor(flat("sil"), dtype=torch.float32, device=device)
                 if roll.get("sil") else torch.zeros(N, device=device))
        # P4 hazard targets: per flattened step, dt (in agent steps) to the SAME env's next
        # PLAY, binned log-spaced; episode boundaries respected; censored (no next play before
        # horizon/episode end) -> last bin. Built from the same buffers continuation_log reads.
        if hazard_coef > 0.0:
            import bisect as _bisect
            _T = len(roll["act"]); _K = len(roll["act"][0]) if _T else 0
            _edges = [1, 2, 4, 8, 16, 32]          # bin upper bounds in steps; bin 6 = beyond
            _hz_tgt = [[6] * _K for _ in range(_T)]
            for _i in range(_K):
                _nextp = 10 ** 9
                for _t in range(_T - 1, -1, -1):
                    if roll["done"][_t][_i] > 0.5:
                        _nextp = 10 ** 9           # a new episode starts ABOVE this row
                    _dt = _nextp - _t
                    _hz_tgt[_t][_i] = _bisect.bisect_left(_edges, _dt) if _dt <= 32 else 6
                    if roll["act"][_t][_i][0] == 1:
                        _nextp = _t
            hz_f = torch.tensor([b for row in _hz_tgt for b in row], dtype=torch.long,
                                device=device)
        else:
            hz_f = None
        srch_f = (torch.tensor(flat("srch"), dtype=torch.float32, device=device)
                  if roll.get("srch") else torch.zeros(N, device=device))
        obs_f, hand_f = flat("obs"), flat("hand")
        nxt_f, elx_f, thr_f = flat("nxt"), flat("elx"), flat("thr")
        gp_f = gpm_f = gpr_f = None
        if _gprior is not None and roll.get("t"):
            _gtab, _gdbl, _gtri = _gprior
            _gt = np.asarray(flat("t"), np.float32)
            _gph = np.where(_gt >= _gtri, 2, np.where(_gt >= _gdbl, 1, 0))
            _geb = np.clip(np.floor(np.asarray([float(e[0]) for e in elx_f]) * 10.0 + 1e-6),
                           0, 10).astype(np.int64)
            if _gtab.ndim == 3:
                # PRESSURE key: youngest living enemy troop younger than W s (same event as the
                # table's "opponent troop played within W s")
                _gpr = (np.asarray(flat("eage"), np.float32) < gate_prior_pressure_s).astype(np.int64)
                gp_f = torch.tensor(_gtab[_gph, _gpr, _geb], dtype=torch.float32, device=device)
                gpr_f = torch.tensor(_gpr, dtype=torch.float32, device=device)
            else:
                gp_f = torch.tensor(_gtab[_gph, _geb], dtype=torch.float32, device=device)
            _gdr = (torch.tensor(flat("isdrill"), dtype=torch.float32, device=device)
                    if roll.get("isdrill") else torch.zeros(N, device=device))
            gpm_f = (_gdr < 0.5)                    # match rows only; the table is from matches

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
        if _pu is not None:
            _pu["u_prep"] = time.perf_counter() - _pt0
        tot_pl = tot_vl = tot_ent = tot_clip = 0.0
        nb = 0
        idx_all = np.arange(N)
        _ep0["want"] = True     # one epoch-0 reading per UPDATE
        _lastep["want"] = True
        for _ep in range(n_epochs):
            np.random.shuffle(idx_all)
            for s in range(0, N, minibatch):
                mb = idx_all[s:s + minibatch]
                _pt1 = time.perf_counter()
                obs_t = to_obs_batch([obs_f[i] for i in mb])
                hand_t = to_vec_batch([hand_f[i] for i in mb])
                elx_t = to_vec_batch([elx_f[i] for i in mb])
                nxt_t = to_vec_batch([nxt_f[i] for i in mb])
                thr_t = to_vec_batch([thr_f[i] for i in mb])
                if _pu is not None:
                    _psync(); _pt2 = time.perf_counter(); _pu["u_mb"] += _pt2 - _pt1
                cq, ceq, gq, val_m, val_d, hz_q = net(obs_t, hand_t, nxt_t, elx_t, thr_t)
                val = val_m
                if value_head_split and _dsplit is not None:
                    val = torch.where(_dsplit[torch.tensor(mb, device=device)] > 0.5,
                                      val_d, val_m)
                mb_t = torch.tensor(mb, device=device)
                g_b, c_b, cell_b = g_f[mb_t], c_f[mb_t], cell_f[mb_t]
                cq_m, ceq_m, gq_m, _ = masked_logits(cq, ceq, gq, hand_t, elx_t, card_idx=c_b,
                                                     pocket_code=pk_f[mb_t],
                                                     stored_cm=(cm_f[mb_t] if cm_f is not None
                                                                else None))
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
                # ADVANTAGE BY ACTION KIND -- the quantity the policy gradient actually consumes.
                # 5b measured the per-decision REWARD favouring a play over a wait by +5.45 sigma
                # while the policy plays ~10% of the time. PPO does not follow reward, it follows
                # `advantage = reward - V(s)`. If the advantage disagrees with the reward, the
                # critic is the gap and its 329 parameters are the suspect; if it agrees, the
                # critic is exonerated and the gate is being driven by something else.
                # Accumulated across the whole run, NOT read per window -- 4 measured the
                # per-window sd (0.00104) as larger than the effect (0.00073), which is how the
                # clip's sign flip stayed invisible for days.
                if _advk["n"] < 10 ** 9:
                    _pm = play > 0.5
                    _wm = ~_pm
                    if int(_pm.sum()) > 0:
                        _advk["p_sum"] += float(a_b[_pm].sum()); _advk["p_n"] += int(_pm.sum())
                    if int(_wm.sum()) > 0:
                        _advk["w_sum"] += float(a_b[_wm].sum()); _advk["w_n"] += int(_wm.sum())
                    _advk["n"] += 1
                    # EARLY AND OFTEN. A 200-update interval produced NOTHING in the first 14
                    # minutes of a 400-match run; the accumulator is cumulative, so an early print
                    # is simply a noisier estimate of the same number, not a different one.
                    if ((_advk["n"] <= 5 or _advk["n"] % 50 == 0)
                            and _advk["p_n"] > 0 and _advk["w_n"] > 0):
                        _pa = _advk["p_sum"] / _advk["p_n"]
                        _wa = _advk["w_sum"] / _advk["w_n"]
                        print("[train-sim-ppo]   ADV BY ACTION  play %+.5f (n=%d)  wait %+.5f (n=%d)"
                              "   play-wait %+.5f" % (_pa, _advk["p_n"], _wa, _advk["w_n"], _pa - _wa),
                              flush=True)
                ratio = (new_lp - ol_b).exp()
                # EPOCH-0 RATIO. The rollout stores the MIXTURE log-prob mu = (1-f)*pi_old + f*prior,
                # so on the FIRST pass -- pi_new still == pi_old, no gradient step taken yet -- a
                # play's ratio is pi_old/mu, which is ABOVE 1 wherever the policy is more confident
                # than the prior. Ceiling is 1/(1-f) per floored head and they MULTIPLY: with card
                # and cell floors both 0.15 that is 1.176^2 = 1.384, past the 1.2 clip. A wait has
                # no gate floor, so its epoch-0 ratio is exactly 1. If plays sit above 1 here while
                # waits sit at 1, plays are clipped BY CONSTRUCTION and their positive-advantage
                # gradient is deleted before training has done anything at all.
                if _ep0["want"] and _ep == 0:
                    with torch.no_grad():
                        _rd, _pmm = ratio.detach(), play.detach()
                        if float(_pmm.sum()) > 0 and float((1.0 - _pmm).sum()) > 0:
                            _rp = float((_rd * _pmm).sum() / _pmm.sum())
                            _rw = float((_rd * (1.0 - _pmm)).sum() / (1.0 - _pmm).sum())
                            _hi = float(((_rd > 1.0 + clip_eps).float() * _pmm).sum() / _pmm.sum())
                            print("[train-sim-ppo] EPOCH-0 ratio  PLAY mean %.4f  WAIT mean %.4f  "
                                  "| %.1f%% of plays ALREADY outside the %.2f clip before any step"
                                  % (_rp, _rw, 100.0 * _hi, 1.0 + clip_eps), flush=True)
                            _ep0["want"] = False
                # LAST-EPOCH SPREAD. Epoch 0 showed plays only 2.4% off-centre and NOTHING clipped,
                # so the 12-25x clip gap is not present at the start of an update -- it ACCUMULATES
                # over the epochs. A play's log-ratio is the SUM of three heads' log-ratio changes
                # (gate + card + cell), a wait's is the gate alone, so if the heads move roughly
                # independently a play should random-walk out of the trust region about sqrt(3)
                # faster. Compare the SPREAD, not the mean: sd(log r) by kind on the final epoch.
                if _ep == n_epochs - 1 and _lastep["want"]:
                    with torch.no_grad():
                        _lr = (new_lp - ol_b).detach()
                        _pmm = play.detach()
                        _np_, _nw = float(_pmm.sum()), float((1.0 - _pmm).sum())
                        if _np_ > 8 and _nw > 8:
                            _lp_p = _lr[_pmm > 0.5]; _lp_w = _lr[_pmm <= 0.5]
                            _sp, _sw = float(_lp_p.std()), float(_lp_w.std())
                            print("[train-sim-ppo] LAST-EPOCH sd(log ratio)  PLAY %.4f  WAIT %.4f  "
                                  "ratio %.2fx  (sqrt(3)=1.73 if the 3 heads move independently)"
                                  % (_sp, _sw, (_sp / _sw) if _sw > 1e-9 else float('nan')), flush=True)
                            _lastep["want"] = False
                            # WHICH HEAD moves the play out of the band. new_lp - old_lp for a play
                            # is d(gate) + d(card) + d(cell); the stored per-head old log-probs let
                            # us split it. If d(cell) dominates, then a play whose GATE decision was
                            # right is being clipped for a reason that has nothing to do with the
                            # gate -- the 432-way cell head's movement discards the gate's update,
                            # while a wait (gate alone) is never clipped and updates freely. That is
                            # a gate that cannot learn to play, next to a cell head that learns fine
                            # (measured: cell_struct 90.8x untrained, 60 distinct cells).
                            _pm_i = _pmm > 0.5
                            if int(_pm_i.sum()) > 8:
                                _dg = (lp_g.gather(1, g_b.view(-1, 1)).squeeze(1)
                                       - oldp_f[mb_t][:, 0]).detach()[_pm_i]
                                _dc = (lp_c.gather(1, c_b.view(-1, 1)).squeeze(1)
                                       - oldp_f[mb_t][:, 1]).detach()[_pm_i]
                                _dq = (lp_cell.gather(1, cell_b.view(-1, 1)).squeeze(1)
                                       - oldp_f[mb_t][:, 2]).detach()[_pm_i]
                                if _gnorm["n"]:
                                    _k = float(_gnorm["n"])
                                    print("[train-sim-ppo]   GRAD NORM per head: gate %.5f  "
                                          "card %.5f  cell %.5f  value %.5f   | gate weight "
                                          "norm %.3f"
                                          % (_gnorm["gate"] / _k, _gnorm["card"] / _k,
                                             _gnorm["cell"] / _k, _gnorm["val"] / _k,
                                             _gnorm["gate_w"]), flush=True)
                                    for _k2 in ("gate", "card", "cell", "val"):
                                        _gnorm[_k2] = 0.0
                                    _gnorm["n"] = 0
                            # SIGNED mean, not |mean|. The gate moves ~11x its own sd EVERY update -- a small,
                            # near-noiseless drift, which is what compounds 0.5 -> 0.06 over hundreds of updates.
                            # The cell head is the reverse (mean 0.068 vs sd 0.478: almost pure noise). So the
                            # SIGN of the gate drift is the whole question, and the first version of this line
                            # printed .abs() and destroyed exactly that.
                            print("[train-sim-ppo]   PLAY log-ratio BY HEAD  sd: gate %.4f  "
                                  "card %.4f  CELL %.4f   (SIGNED mean %+.4f / %+.4f / %+.4f)"
                                  % (float(_dg.std()), float(_dc.std()), float(_dq.std()),
                                     float(_dg.mean()), float(_dc.mean()), float(_dq.mean())), flush=True)
                            # The gate drift on WAIT steps too -- the play-only mask above never sees them.
                            # If play log-prob falls while wait log-prob rises, the gate is being walked
                            # toward waiting from both sides on every update.
                            _pw_i = ~_pm_i
                            if int(_pw_i.sum()) > 8:
                                _dgw = (lp_g.gather(1, g_b.view(-1, 1)).squeeze(1)
                                        - oldp_f[mb_t][:, 0]).detach()[_pw_i]
                                print("[train-sim-ppo]   GATE drift: PLAY steps %+.5f  WAIT steps %+.5f"
                                      "   (+ = that action becoming MORE likely)"
                                      % (float(_dg.mean()), float(_dgw.mean())), flush=True)
                                # SPLIT THE DRIFT BY DRILL vs MATCH STEP. The collapse is drill-induced (3 seeds at
                                # drill_frac 0.0 hold P(play) 0.92-0.99; four runs at 0.3 collapse to 0.11-0.15), but
                                # that leaves two very different mechanisms:
                                #   * push is negative on DRILL steps only -> drills directly teach the gate to wait
                                #   * push is negative on BOTH -> drills corrupt something SHARED (advantage
                                #     normalisation over the mixed batch, or the critic), poisoning match steps too
                                # The fix differs completely between those, so measure instead of assuming.
                                if roll.get("isdrill"):
                                    _dsel = torch.tensor(flat("isdrill"), dtype=torch.float32,
                                                         device=device)[mb_t]
                                    _dg_all = (lp_g.gather(1, g_b.view(-1, 1)).squeeze(1)
                                               - oldp_f[mb_t][:, 0]).detach()
                                    for _tag, _sel in (("DRILL", _dsel > 0.5), ("match", _dsel <= 0.5)):
                                        _pl_i = _sel & (_pmm > 0.5)
                                        _wt_i = _sel & (_pmm <= 0.5)
                                        if int(_pl_i.sum()) > 4 and int(_wt_i.sum()) > 4:
                                            print("[train-sim-ppo]     %-5s steps: gate drift on PLAY %+.5f  "
                                                  "on WAIT %+.5f   (n_play %d, n_wait %d)"
                                                  % (_tag, float(_dg_all[_pl_i].mean()),
                                                     float(_dg_all[_wt_i].mean()),
                                                     int(_pl_i.sum()), int(_wt_i.sum())), flush=True)
                s1 = ratio * a_b
                # PER-ACTION-KIND BOUND: wider for plays, whose ratio carries three log-probs.
                eps_b = clip_eps * (1.0 + (clip_play_mult - 1.0) * play)
                s2 = torch.clamp(ratio, 1.0 - eps_b, 1.0 + eps_b) * a_b
                pl = -torch.min(s1, s2).mean()
                if drill_gate_mask and _dsplit is not None:
                    # PROTECT THE GATE FROM DRILL STEPS (ppo_drill_gate_mask).
                    #
                    # The measured failure is specific: the play/wait GATE collapses (P(play) 0.5 ->
                    # 0.11-0.15 with drills, 0.92-0.99 without), while the cell head learns fine
                    # (90.8x untrained, 60 distinct cells). Drill steps push log pi(play) down
                    # -0.17 to -0.42 EVERY update; match steps do too (-0.09 to -0.14) but only
                    # while drills share the batch.
                    #
                    # Drills are worth keeping -- they teach WHICH card and WHERE, and drill-free
                    # models play subpar. So keep their gradient for the card and cell heads and
                    # drop it only for the gate: the gate is trained on match steps, where "should
                    # I play at all" is a question the critic can actually value, and drills stop
                    # voting on a decision their artificial boards misprice.
                    #
                    # Implemented by rebuilding the surrogate with the gate log-prob detached on
                    # drill steps, so those steps still shape card/cell but contribute no gradient
                    # to the gate head.
                    _dm = _dsplit[mb_t]
                    _lpg = lp_g.gather(1, g_b.view(-1, 1)).squeeze(1)
                    _lpg_masked = torch.where(_dm > 0.5, _lpg.detach(), _lpg)
                    _new_lp2 = _lpg_masked + play * (
                        lp_c.gather(1, c_b.view(-1, 1)).squeeze(1)
                        + lp_cell.gather(1, cell_b.view(-1, 1)).squeeze(1))
                    _ratio2 = (_new_lp2 - ol_b).exp()
                    _s1 = _ratio2 * a_b
                    _s2 = torch.clamp(_ratio2, 1.0 - eps_b, 1.0 + eps_b) * a_b
                    pl = -torch.min(_s1, _s2).mean()
                if clip_per_head:
                    # PER-HEAD TRUST REGIONS. Clipping the JOINT ratio lets the noisiest head
                    # decide the fate of every head's update. Measured, on play steps:
                    #     sd(log r)  gate 0.0019   card 0.0284   CELL 0.4781
                    # The 432-way cell head moves 250x more than the gate. Its +-61% swing throws
                    # the sample outside the +-20% band, and the min() deletes the gradient for the
                    # WHOLE play -- including the gate's 0.2% move, which was never out of bounds.
                    # A wait carries the gate alone, is essentially never clipped, and updates
                    # freely both ways. So the gate's reinforcement for PLAYING is censored while
                    # its reinforcement for WAITING is not, and it decays regardless of reward.
                    # That is "decay from start": P(play) 0.5 -> 0.06-0.25 in every run, with or
                    # without drills, while the cell head itself learns fine (90.8x untrained).
                    #
                    # Giving each head its own ratio and its own clip removes the coupling: the
                    # cell head can still be clipped for its own excursions, and the gate is judged
                    # only on how far the GATE moved.
                    def _surr(r, eps):
                        # PER-SAMPLE BOUND. `eps` is a tensor, exactly as the joint path's `eps_b`
                        # already is -- torch.clamp takes tensor bounds, so this needs no new
                        # machinery, only the argument that was missing.
                        return torch.min(r * a_b, torch.clamp(r, 1.0 - eps, 1.0 + eps) * a_b)
                    op = oldp_f[mb_t]
                    r_g = (lp_g.gather(1, g_b.view(-1, 1)).squeeze(1) - op[:, 0]).exp()
                    r_c = (lp_c.gather(1, c_b.view(-1, 1)).squeeze(1) - op[:, 1]).exp()
                    r_q = (lp_cell.gather(1, cell_b.view(-1, 1)).squeeze(1) - op[:, 2]).exp()
                    # mean over the heads that ACTED: 1 for a wait, 3 for a play, so a play does
                    # not silently get 3x the gradient magnitude of a wait.
                    # THE GATE GETS THE WIDENED BOUND (`eps_b`, which embeds
                    # ppo_clip_play_mult); card and cell keep the base one. Two DIFFERENT
                    # asymmetries are in play and per-head only fixes the first:
                    #   (1) three-head coupling -- a play's JOINT ratio is gate x card x cell while a
                    #       wait's is the gate alone. Per-head ratios fix that.
                    #   (2) minority-action volatility -- d(log p)/d(logit) is ~1 for the MINORITY
                    #       action and ~p for the majority, so the same logit move swings a play's
                    #       log-ratio ~1/p harder. MEASURED on the SAME head: gate log-ratio sd
                    #       0.518 on plays vs 0.027 on waits, 19x. Per-head does NOTHING about this,
                    #       which is why it measured "no improvement, inside noise" on its own.
                    # Card/cell exist ONLY on play steps, so they carry no play/wait asymmetry and
                    # widening them would just loosen the trust region for nothing.
                    per = _surr(r_g, eps_b) + play * (_surr(r_c, clip_eps) + _surr(r_q, clip_eps))
                    pl = -(per / (1.0 + 2.0 * play)).mean()
                # SEARCHED STEPS LEAVE THE PPO SURROGATE. The stored log-prob belongs to the
                # POLICY's sample, but the action that ran was the SEARCHER's -- so pi_new/mu is not
                # an importance ratio on those steps, it is a ratio between two different
                # distributions. Zero them here and teach them by imitation below instead.
                _sb = srch_f[mb_t]
                if float(_sb.sum()) > 0.0:
                    _keep = (1.0 - _sb)
                    _dn = float(_keep.sum())
                    pl = (-(torch.min(s1, s2) * _keep).sum() / _dn) if _dn > 0 else pl * 0.0
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
                    if _dst is not None:
                        # CARD-HEAD DISTILLATION TERM. A fresh minibatch from the teacher corpus
                        # each update, forwarded through the SAME masked_logits the policy acts
                        # under, scored as plain cross-entropy toward the teacher's card.
                        # NO IMPORTANCE WEIGHT: these are supervised targets, not actions this
                        # policy took, so pi/mu has no meaning and the ~0.01 ratio that silently
                        # kills the SIL/PPO signal on prior-driven steps cannot apply here.
                        _dk = min(int(distill_batch), _dst["n"])
                        _dj = np.random.choice(_dst["n"], size=_dk, replace=False)
                        _dhand = torch.as_tensor(_dst["hand"][_dj], device=device)
                        _delx = torch.as_tensor(_dst["elx"][_dj], device=device)
                        _dcq, _dceq, _dgq, _, _, _ = net(
                            torch.as_tensor(_dst["obs"][_dj], device=device)
                                 .float().permute(0, 3, 1, 2) / 255.0,
                            _dhand,
                            torch.as_tensor(_dst["nxt"][_dj], device=device),
                            _delx,
                            torch.as_tensor(_dst["thr"][_dj], device=device))
                        _dcqm, _, _, _dplayable = masked_logits(_dcq, _dceq, _dgq, _dhand, _delx)
                        _dtgt = torch.as_tensor(_dst["card"][_dj], device=device)
                        # A target this net's mask forbids is -inf under log_softmax, which makes
                        # the loss NaN rather than large -- and one NaN poisons every parameter
                        # through the shared trunk. Drop those rows: the corpus was labelled under
                        # its own elixir/bank state, not the one being masked here.
                        _dkeep = _dplayable.gather(1, _dtgt.view(-1, 1)).squeeze(1)
                        if int(_dkeep.sum()) >= 8:
                            _dloss = F.cross_entropy(_dcqm[_dkeep], _dtgt[_dkeep])
                            loss = loss + distill_coef * _dloss
                            _dstat["loss"] += float(_dloss)
                            _dstat["kept"] += int(_dkeep.sum())
                            _dstat["seen"] += int(_dk)
                            _dstat["n"] += 1
                            # FIRST update too: "did the distillation term actually attach?" is
                            # a question you want answered in the first seconds of a multi-day run,
                            # not 200 updates in.
                            if _dstat["n"] == 1 or _dstat["n"] % 200 == 0:
                                print("[train-sim-ppo]   DISTILL card CE %.4f over %d updates "
                                      "(%.0f%% of sampled rows kept by the live mask)"
                                      % (_dstat["loss"] / _dstat["n"], _dstat["n"],
                                         100.0 * _dstat["kept"] / max(1, _dstat["seen"])),
                                      flush=True)
                # WHICH LOSS TERM DRIVES THE GATE. Measured, the gate drifts -0.169 on play steps and
                # -0.044 on wait steps every update -- consistently, at 11x its own noise. Three terms
                # touch the gate logits: the PPO surrogate, the entropy bonus, and (via the shared trunk
                # z) the value loss. Attributing the drift to any of them by argument has failed all day,
                # so take the gradient of each term separately w.r.t. the GATE LOGITS and report the push
                # on (logit_play - logit_wait). Gradient descent moves logits AGAINST the gradient, so the
                # push is -(d term / d logit_play - d term / d logit_wait). Negative push = that term is
                # driving the gate toward WAITING.
                if _terms["want"] and not _warm["left"]:
                    with torch.enable_grad():
                        _ent_term = -ent_coef * ent.mean() - _cell_ent_now() * cell_ent.mean()
                        for _nm, _t in (("ppo", pl), ("entropy", _ent_term), ("value", vf_coef * vl)):
                            try:
                                _g = torch.autograd.grad(_t, gq_m, retain_graph=True,
                                                         allow_unused=True)[0]
                            except Exception:
                                _g = None
                            if _g is None:
                                _terms[_nm] = float("nan"); continue
                            _push = -(_g[:, 1] - _g[:, 0])
                            _terms[_nm] = float(_push.sum())      # sum: total pull on the gate this minibatch
                        _terms["n"] += 1
                        if _terms["n"] % 40 == 0:
                            print("[train-sim-ppo]   GATE PUSH BY LOSS TERM (+ = toward PLAY):  "
                                  "ppo %+.5f   entropy %+.5f   value %+.5f"
                                  % (_terms["ppo"], _terms["entropy"], _terms["value"]), flush=True)
                # SEARCH IMITATION -- OUTSIDE the value-warmup gate, because it is a SUPERVISED
                # loss and does not depend on the critic. Gating it behind the 60-minibatch warmup
                # meant a short run trained on nothing but the critic (measured: 12 updates, 0
                # imitation steps). Cross-entropy toward the action the SEARCHER chose, on the
                # steps it chose one. No importance weight -- these are supervised targets, not
                # actions this policy took. ALL THREE HEADS, because search's advantage is the
                # whole decision: teaching only the card is what plain distillation did, and it
                # moved card agreement +4.2 sigma while moving winrate by nothing.
                # /!\ BOTH SEARCH PATHS. Gating this on `_searchers` alone would have made the
                # entire supervised term a silent no-op under --workers>1: rows arrive flagged in
                # roll["srch"], the CE is never added, and the run trains as plain PPO while every
                # SEARCH log line still prints. That is this seam's signature failure (drill_frac,
                # spell_veto, deck_record all broke exactly here).
                if ((_searchers is not None or _search_cfg is not None)
                        and float(_sb.sum()) > 0.0 and search_coef > 0.0):
                    _lg = lp_g.gather(1, g_b.view(-1, 1)).squeeze(1)
                    _lc = lp_c.gather(1, c_b.view(-1, 1)).squeeze(1)
                    _lq = lp_cell.gather(1, cell_b.view(-1, 1)).squeeze(1)
                    # A TARGET THE UPDATE'S MASK FORBIDS SCORES -1e9, NOT "a large loss". The
                    # stored cell mask was built for the card the POLICY sampled; when search picks
                    # a DIFFERENT card that mask is the wrong one, so the searcher's cell can land
                    # on a masked entry. MEASURED: one such row in ~346 gave a batch mean of
                    # 2,890,174 (= 1e9/346) -- rare, and catastrophic when it happens, which is
                    # exactly why it needs a guard rather than luck. Drop those rows, as the
                    # card-distillation term does.
                    _ok = (_lg > -50.0) & ((play < 0.5) | ((_lc > -50.0) & (_lq > -50.0)))
                    _sbk = _sb * _ok.float()
                    if float(_sbk.sum()) > 0.0:
                        _im = -_lg - play * _lc - play * _lq
                        _iml = (_im * _sbk).sum() / float(_sbk.sum())
                        loss = loss + search_coef * _iml
                        _sstat["loss"] += float(_iml); _sstat["nl"] += 1
                        _sstat["kept"] += int((_sbk > 0).sum())
                        _sstat["seen"] += int((_sb > 0).sum())
                        if _sstat["nl"] <= 3 or _sstat["nl"] % 200 == 0:
                            print("[train-sim-ppo]   SEARCH  %d/%d decisions searched, %.1f%% changed "
                                  "the action | imitation CE %.4f | %.1f%% of searched rows usable"
                                  % (_sstat["searched"], _sstat["n"],
                                     100.0 * _sstat["changed"] / max(1, _sstat["searched"]),
                                     _sstat["loss"] / _sstat["nl"],
                                     100.0 * _sstat["kept"] / max(1, _sstat["seen"])), flush=True)
                # P4 HAZARD LOSS -- supervised, so OUTSIDE the value warmup for the same reason
                # as the search CE above. Plain CE on binned time-to-next-play; grading by
                # accuracy is forbidden (always-WAIT floor); the A/B is judged on the corpora.
                if hazard_coef > 0.0 and hz_f is not None:
                    loss = loss + hazard_coef * F.cross_entropy(hz_q, hz_f[mb_t])
                if _pu is not None:
                    _psync(); _pt3 = time.perf_counter(); _pu["u_fwd"] += _pt3 - _pt2
                if gp_f is not None and gate_prior_coef > 0.0:
                    # KL(prior || pi) on the gate = Bernoulli cross-entropy toward p_play. Rows
                    # whose PLAY logit is masked (nothing affordable) carry log pi(play) ~ -1e9 and
                    # are excluded, or the term would be dominated by states the gate cannot act in.
                    _gpk = gpm_f[mb_t] & (gq_m[:, 1] > _NEG * 0.5)
                    _gpstat["seen"] += int(_gpk.numel())
                    if bool(_gpk.any()):
                        _gpt = gp_f[mb_t][_gpk]
                        _gce = -(_gpt * lp_g[_gpk, 1] + (1.0 - _gpt) * lp_g[_gpk, 0])
                        loss = loss + gate_prior_coef * _gce.mean()
                        _gpstat["n"] += 1; _gpstat["rows"] += int(_gpk.sum())
                        _gpstat["ce"] += float(_gce.mean()); _gpstat["p"] += float(_gpt.mean())
                        _gpstat["pi"] += float(lp_g[_gpk, 1].exp().mean())
                        if gpr_f is not None:
                            _gpstat["pres"] += float(gpr_f[mb_t][_gpk].mean())
                        if _gpstat["n"] == 1 or _gpstat["n"] % 200 == 0:
                            print("[train-sim-ppo]   GATE PRIOR CE %.4f over %d updates | pi(play) %.3f "
                                  "vs prior %.3f on the same rows | %.0f%% of rows usable%s"
                                  % (_gpstat["ce"] / _gpstat["n"], _gpstat["n"],
                                     _gpstat["pi"] / _gpstat["n"], _gpstat["p"] / _gpstat["n"],
                                     100.0 * _gpstat["rows"] / max(1, _gpstat["seen"]),
                                     (" | PRESSURE on %.0f%% of them" % (100.0 * _gpstat["pres"] / _gpstat["n"]))
                                     if gpr_f is not None else ""), flush=True)
                opt.zero_grad(); loss.backward()
                if _pu is not None:
                    _psync(); _pt4 = time.perf_counter(); _pu["u_bwd"] += _pt4 - _pt3
                # IS THE GATE STARVED OF GRADIENT? Measured, a play's log-prob moves +-61% on the
                # CELL head per update while the GATE moves +-0.2% -- 250x. Clipping does not cause
                # that (it is visible before any clip), and _clamp_heads() never touches the gate.
                # So either the gate receives far less gradient than the other heads, or it receives
                # it and cannot act on it. Adam normalises per-parameter, so a small gradient still
                # yields a ~lr-sized step: if the gate's grad norm is comparable to the others and
                # it STILL barely moves, the cause is downstream (saturation, the shared trunk), not
                # starvation. Record both the raw grad norms and the realised parameter movement.
                if _gnorm["want"]:
                    with torch.no_grad():
                        def _gn(m):
                            g = [q.grad for q in m.parameters() if q.grad is not None]
                            return float(torch.cat([q.reshape(-1) for q in g]).norm()) if g else 0.0
                        _gnorm["gate"] += _gn(net.gate)
                        _gnorm["card"] += _gn(net.policy.card_head)
                        _gnorm["cell"] += _gn(net.policy.cell_conv[-1])
                        _gnorm["val"] += _gn(net.value)
                        _gnorm["n"] += 1
                        _gnorm["gate_w"] = float(net.gate.weight.detach().norm())
                torch.nn.utils.clip_grad_norm_(net.parameters(), max_grad)
                opt.step()
                _clamp_heads()                                # sharpness cap: heads can rank, not rail
                with torch.no_grad():
                    tot_pl += float(pl.detach()); tot_vl += float(vl.detach())
                    tot_ent += float(ent.mean().detach())
                    tot_clip += float(((ratio.detach() - 1.0).abs() > clip_eps).float().mean()); nb += 1
                    # CLIP SPLIT BY PLAY vs WAIT. A wait's ratio carries the GATE log-prob alone;
                    # a play's carries gate + card + cell, and the cell head is 432-way, so a play's
                    # ratio is far noisier and leaves the trust region 12-25x more often (measured).
                    #
                    # But the clip RATE alone proves nothing about direction. PPO's clip is
                    # deliberately TWO-SIDED: it kills the gradient when (A>0 and r>1+eps) OR when
                    # (A<0 and r<1-eps), so a high clip rate on its own is as likely to block a
                    # push down as a push up. What decides whether the gate drifts is the NET
                    # SURVIVING PUSH -- sum of A*r over the steps whose gradient is NOT killed.
                    # If that is negative for plays while waits keep a free two-sided update, the
                    # gate is driven toward waiting no matter what the reward says, which is what
                    # every run does (P(play) 0.535 untrained -> 0.075 after 700 matches).
                    _cl = ((ratio.detach() - 1.0).abs() > eps_b.detach()).float()
                    _pm = play.detach()
                    _clip_split["play"] += float((_cl * _pm).sum())
                    _clip_split["play_n"] += float(_pm.sum())
                    _clip_split["wait"] += float((_cl * (1.0 - _pm)).sum())
                    _clip_split["wait_n"] += float((1.0 - _pm).sum())
                    _r = ratio.detach()
                    _e = eps_b.detach()
                    _blocked = (((a_b > 0) & (_r > 1.0 + _e))
                                | ((a_b < 0) & (_r < 1.0 - _e))).float()
                    _push = a_b * _r * (1.0 - _blocked)      # gradient that actually survives
                    _clip_split["play_block"] += float((_blocked * _pm).sum())
                    _clip_split["wait_block"] += float((_blocked * (1.0 - _pm)).sum())
                    _clip_split["play_push"] += float((_push * _pm).sum())
                    _clip_split["wait_push"] += float((_push * (1.0 - _pm)).sum())
                    # THE CONTROL. Net surviving push being more negative for plays does NOT by
                    # itself implicate clipping: it looks identical whether clipping strips plays
                    # of their positive updates, or the critic simply assigns plays worse
                    # advantage and clipping is irrelevant. So accumulate the SAME quantity with
                    # NO blocking applied. If raw ~= surviving, clipping is not doing the damage
                    # and the bias lives in the advantages themselves.
                    _raw = a_b * _r
                    _clip_split["play_raw"] += float((_raw * _pm).sum())
                    _clip_split["wait_raw"] += float((_raw * (1.0 - _pm)).sum())
                    # PROJECT ONTO THE GATE LOGIT -- the sign convention matters and summing the
                    # two pushes gets it WRONG. The update direction is +A*r*grad log pi(a), so a
                    # wait step with NEGATIVE advantage lowers log pi(wait), which RAISES P(play):
                    # a negative wait push pushes TOWARD playing, not away from it. Writing
                    # play_push + wait_push therefore counts that term with the wrong sign.
                    # With p = P(play): d log pi(play)/dz = (1-p) and d log pi(wait)/dz = -p, so
                    # each step contributes A*r*(1-p) if it played and A*r*(-p) if it waited.
                    # Positive total = the gate is being driven toward PLAYING.
                    _p_play = lp_g[:, 1].detach().exp()
                    _proj = torch.where(_pm > 0.5, 1.0 - _p_play, -_p_play)
                    _clip_split["gate_z"] += float((_push * _proj).sum())
                    _clip_split["gate_z_raw"] += float((_raw * _proj).sum())
                if _pu is not None:
                    _psync(); _pu["u_step"] += time.perf_counter() - _pt4
        if _pu is not None:
            for _k, _v in _pu.items():
                _pc[_k] += _v
        return tot_pl / nb, tot_vl / nb, tot_ent / nb, tot_clip / nb

    # -- main loop: collect a horizon of experience across K envs, then one PPO update -------------
    if remote:
        cobs = rpool.reset_all()
        chand = [p["hand"] for p in rpool.last]; cnxt = [p["nxt"] for p in rpool.last]
        # WHICH ENVS ARE IN A DRILL -- the exploration floor differs, and the envs live in the
        # workers while the sampling happens here.
        in_drill = [bool(p.get("in_drill")) for p in rpool.last]
        celx = [p["elx"] for p in rpool.last]; cthr = [p["thr"] for p in rpool.last]
        ct = [float(p.get("t", 0.0)) for p in rpool.last]      # engine clock, for the gate prior's phase
        ceage = [float(p.get("eage", 1e9)) for p in rpool.last]  # youngest enemy troop, its PRESSURE key
    else:
        cobs = [e.reset() for e in pool]
        chand = [e.hand_vec.copy() for e in pool]; cnxt = [e.next_vec.copy() for e in pool]
        in_drill = [bool(getattr(e, "_in_drill", False)) for e in pool]
        celx = [e.elixir_vec.copy() for e in pool]; cthr = [e.threat_vec.copy() for e in pool]
        ct = [float(getattr(getattr(e, "eng", None), "t", 0.0)) for e in pool]
        ceage = [float(e.enemy_troop_min_age()) if hasattr(e, "enemy_troop_min_age") else 1e9 for e in pool]
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
    # ------------------------------------------------- SEARCH IN THE LOOP (DAgger, not distillation)
    # Rollout search took the FROZEN policy 37.0% -> 85.7% (HANDOFF 4x). Four component-level
    # interventions each hit their mechanism and moved nothing; search is the only thing that has
    # ever moved the outcome, and it differs by replacing the WHOLE decision.
    #
    # WHY THIS IS NOT THE DISTILLATION THAT FAILED: that corpus was labelled from a FROZEN policy,
    # so the teacher described states the learner drifts away from -- textbook covariate shift.
    # Here the searcher runs on the CURRENT policy's own states every rollout, so the target
    # distribution tracks the learner.
    _searchers = None
    _search_cfg = None          # non-None = search runs in the WORKERS, config shipped with the net
    if search_interval > 0:
        try:
            from .sim import rollout_search as _RS   # package module: each deck searches its OWN sim
        except Exception as _e:                                # noqa: BLE001
            print(f"[train-sim-ppo] REFUSING --search-interval: cannot import rollout_search ({_e})")
            return
        if remote:
            # 5u -- THE OLD REFUSAL WAS RIGHT ABOUT THE CAUSE AND WRONG ABOUT THE ONLY FIX. Search
            # must clone a live SimEngine and the parent's `pool` IS empty under workers>1, so
            # searching here was impossible. But the engines are not gone, they are in the WORKERS.
            # Sending the searcher to them is 5m's structural fix: the 98.5% of a decision that is
            # search runs on `workers` cores instead of one. Weights ride down every update.
            _search_cfg = {"horizon": float(search_horizon), "interval": int(search_interval),
                           "gate_tau": float(gate_tau), "cells": int(search_cells)}
            print(f"[train-sim-ppo] SEARCH IN THE WORKERS: every {search_interval} decision(s), "
                  f"H={search_horizon}s cells={search_cells} coef={search_coef} over {K} env(s) "
                  f"across {len(rpool.conns)} worker process(es)")
        else:
            _searchers = [_RS.Searcher(e, net, device, search_horizon, search_interval, 4,
                                       1.0, gate_tau, cells=search_cells) for e in pool]
            print(f"[train-sim-ppo] SEARCH IN THE LOOP: every {search_interval} decision(s), "
                  f"H={search_horizon}s cells={search_cells} coef={search_coef} over {len(pool)} env(s)")
    _sstat = {"n": 0, "searched": 0, "changed": 0, "loss": 0.0, "nl": 0, "kept": 0, "seen": 0}

    done_n = wins = losses = draws = 0
    drills_done = drill_pass = 0     # drills are counted apart from the match record
    # ...and a ROLLING window beside them. The two counters above are never reset, so the
    # printed rate is a run-LIFETIME average: measured on the 18k run of 2026-09-01 it went
    # 29% -> 45% and then sat at EXACTLY 45 for the last 275 prints, because at n=3,500 the
    # next few hundred drills cannot move it (500 recent drills at 60% print as 47%). That
    # is a converging statistic being read as a learning plateau. HANDOFF 5bd.
    drill_recent: deque = deque(maxlen=300)
    # ...and their share of STEPS is tracked apart from their share of EPISODES, because those two
    # differ by an order of magnitude (48% of episodes was 8% of steps) and only the second is what
    # the optimiser sees. Printing one without the other is how a barely-training mix looked broken.
    drill_steps = match_steps = 0
    win_hist: deque = deque(maxlen=max(log_every, 50))
    rew_hist: deque = deque(maxlen=max(log_every, 50))
    stats = None
    # OPT-IN CYCLE PROFILE (5ar): CLASHRL_PROFILE=1 prints where each rollout->update cycle's wall
    # clock goes. OFF by default, and when off nothing below changes: the timers only accumulate
    # into `_pc` when it exists. It was added because the trainer had no timing at all while
    # 12 workers measured 1.83x workers-0 with the cause unknown -- this is the instrument that
    # says whether the parent process (policy forward, PPO update) is the ceiling or the workers.
    _PROF_KEYS = ("bcast", "choose", "search", "step", "eval", "save", "league", "cont", "update",
                  "rollout", "cycle", "u_prep", "u_mb", "u_fwd", "u_bwd", "u_step")
    _prof_on = bool(os.environ.get("CLASHRL_PROFILE"))
    _prof_tot = {k: 0.0 for k in _PROF_KEYS} | {"n": 0, "steps": 0, "matches": 0}
    _pc = None                                          # per-cycle buckets (None = profile off)
    # CUDA kernels are asynchronous: without a sync the update sub-buckets would time the launch
    # queue, not the work. Only called when profiling (a sync per minibatch is not free).
    _psync = torch.cuda.synchronize if device.type == "cuda" else (lambda: None)

    def _prof_report(pc: dict, dm: int, label: str) -> None:
        cyc = max(pc["cycle"], 1e-9)
        book = pc["rollout"] - pc["choose"] - pc["search"] - pc["step"] - pc["eval"] - pc["save"] - pc["league"]
        other = pc["cycle"] - pc["rollout"] - pc["bcast"] - pc["cont"] - pc["update"]
        print("[profile] %s: %.1fs | rollout %.1fs (choose %.1f | search %.1f | step %.1f = %.0f%% | book %.1f)"
              " | update %.1fs = %.0f%% | bcast %.1f | cont %.1f | eval %.1f | save %.1f | league %.1f"
              " | other %.1f | env-steps %d | matches +%d (%d done)"
              % (label, pc["cycle"], pc["rollout"], pc["choose"], pc["search"], pc["step"],
                 100.0 * pc["step"] / cyc, book, pc["update"], 100.0 * pc["update"] / cyc,
                 pc["bcast"], pc["cont"], pc["eval"], pc["save"], pc["league"], other,
                 pc["steps"], dm, done_n), flush=True)
        upd = max(pc["update"], 1e-9)
        print("[profile]   update split: prep %.1f | minibatch tensors %.1f (%.0f%%) | forward+loss %.1f (%.0f%%)"
              " | backward %.1f (%.0f%%) | step+diag %.1f (%.0f%%)"
              % (pc["u_prep"], pc["u_mb"], 100.0 * pc["u_mb"] / upd, pc["u_fwd"], 100.0 * pc["u_fwd"] / upd,
                 pc["u_bwd"], 100.0 * pc["u_bwd"] / upd, pc["u_step"], 100.0 * pc["u_step"] / upd), flush=True)

    t0 = time.time()
    try:
        while running["v"] and done_n < matches:
            if _prof_on:
                _pc = {k: 0.0 for k in _PROF_KEYS} | {"steps": 0}
                _pc0 = time.perf_counter(); _pm0 = done_n
            roll = {"obs": [], "hand": [], "nxt": [], "elx": [], "thr": [],
                    "act": [], "logp": [], "lparts": [], "pk": [], "cm": [], "val": [], "rew": [], "done": [], "trunc": [],
                    # SELF-IMITATION MASK: 1.0 on steps that turned out to belong to a drill
                    # episode the agent PASSED. Filled in retroactively when the episode ends,
                    # because that is when the verdict exists.
                    "sil": [], "isdrill": [], "boot": None, "t": [], "eage": [],
                    # SEARCHED steps: the action came from the SEARCHER, not the policy. They are
                    # EXCLUDED from the PPO surrogate (the stored log-prob is the policy's, not the
                    # behaviour that acted, so the importance ratio would be meaningless) and are
                    # instead the target of a plain imitation cross-entropy.
                    "srch": []}
            ep_from = [0] * K                              # first step of each env's current episode
            # THE WORKERS' SEARCHERS RUN THE CURRENT POLICY, so the weights go down every update.
            # A searcher on last update's weights is a frozen teacher, which is the covariate-shift
            # failure 5m says search exists to avoid. Workers hold the net BY REFERENCE, so this is
            # an in-place refresh that keeps their interval counters and per-env stats alive.
            if _search_cfg is not None:
                _pt = time.perf_counter()
                rpool.set_search_net({"model": _cpu_sd(net.policy),
                                      "gate": _cpu_sd(net.gate)}, _search_cfg)
                if _pc is not None:
                    _pc["bcast"] += time.perf_counter() - _pt
            _pr0 = time.perf_counter()
            for _t in range(horizon):
                if not running["v"] or done_n >= matches:
                    break
                _pt = time.perf_counter()
                acts, logps, vals, lparts, pkc, cms = choose_sample(cobs, chand, cnxt, celx, cthr)
                if _pc is not None:
                    _pc["choose"] += time.perf_counter() - _pt; _pc["steps"] += 1
                roll["obs"].append(list(cobs)); roll["hand"].append([h.copy() for h in chand])
                roll["nxt"].append([n.copy() for n in cnxt]); roll["elx"].append([e.copy() for e in celx])
                roll["thr"].append([t.copy() for t in cthr]); roll["t"].append(list(ct))
                roll["eage"].append(list(ceage))
                # SEARCH OVERRIDES THE ACTION on its own cadence. Acting with the searcher is
                # the point: it puts the trajectory on the distribution the improved policy will
                # see, which is the half plain distillation could not supply.
                srow = [0.0] * len(acts)
                _pt = time.perf_counter()
                if _searchers is not None:
                    for _i in range(len(acts)):
                        if _i >= len(_searchers) or pool[_i].eng.done:
                            continue
                        _sstat["n"] += 1
                        try:
                            _sa, _did = _searchers[_i].act(_t)
                        except Exception:                      # noqa: BLE001
                            continue
                        if _did:
                            _sstat["searched"] += 1
                            if tuple(_sa) != tuple(acts[_i]):
                                _sstat["changed"] += 1
                            acts[_i] = tuple(_sa)
                            srow[_i] = 1.0
                # UNDER WORKER-SIDE SEARCH THE PARENT DOES NOT KNOW THE ACTION UNTIL THE WORKER
                # ANSWERS, so the step has to happen BEFORE the roll is appended -- otherwise
                # roll["act"] records the proposal and the imitation target is the wrong action.
                # `_proposed` is kept so "% changed the action" still compares against the POLICY.
                if _pc is not None:
                    _pc["search"] += time.perf_counter() - _pt
                step_out = None
                if remote:
                    _proposed = list(acts)
                    _pt = time.perf_counter()
                    step_out = rpool.step_all(acts)
                    if _pc is not None:
                        _pc["step"] += time.perf_counter() - _pt
                    if _search_cfg is not None:
                        for _i in range(K):
                            _pay = step_out[_i]
                            _pa = _pay.get("act")
                            if _pa is not None:
                                acts[_i] = tuple(_pa)
                            if float(_pay.get("srch", 0.0)) > 0.0:
                                srow[_i] = 1.0
                                _sstat["searched"] += 1
                                if tuple(acts[_i]) != tuple(_proposed[_i]):
                                    _sstat["changed"] += 1
                            _sstat["n"] += 1
                roll["srch"].append(srow)
                roll["act"].append(acts); roll["logp"].append(logps); roll["val"].append(vals)
                roll["lparts"].append(lparts)
                roll["pk"].append(pkc)
                roll["cm"].append([None if m is None else m.detach().cpu().numpy() for m in cms])
                rew_row, done_row, trunc_row = [], [], []   # step_out was filled above
                for i in range(K):
                    if remote:
                        pay = step_out[i]
                        nobs, reward, done = pay["obs"], pay["rew"], pay["done"]
                        info = {"outcome": pay["outcome"], "pfsp": pay["pfsp"],
                                "drill": pay.get("drill"), "verdict": pay.get("verdict"),
                                # the worker reports which META DECK the episode was against;
                                # dropping it here made deck PFSP inert in the worker path while
                                # looking wired end-to-end (the worker sent it, the parent binned
                                # it, the record stayed empty, nothing was ever shipped back).
                                "deck": pay.get("deck")}
                        env = None
                    else:
                        env = pool[i]
                        _pt = time.perf_counter()
                        nobs, reward, done, info = env.step(acts[i])
                        if _pc is not None:
                            _pc["step"] += time.perf_counter() - _pt
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
                            _dp = 1 if info.get("verdict") == "pass" else 0
                            drill_pass += _dp
                            drill_recent.append(_dp)
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
                            # PER-DECK RECORD, for the deck-exploiter weighting in make_opponent.
                            # Kept on the shared cfg object so every local env's next
                            # make_opponent() call sees it. NOTE: with --workers > 0 the envs live
                            # in separate processes and this record does NOT reach them, so deck
                            # PFSP is a LOCAL-ENV feature until the workers ship results back.
                            _dk = (info or {}).get("deck")
                            if _dk:
                                _rec = getattr(cfg, "_deck_record", None)
                                if _rec is None:
                                    _rec = cfg._deck_record = {}
                                w0, n0 = _rec.get(str(_dk), (0, 0))
                                _rec[str(_dk)] = (w0 + (1 if oc == "win" else 0), n0 + 1)
                                # WORKERS live in other processes and hold their own cfg, so the
                                # record has to be shipped to them or deck PFSP is inert for every
                                # run that uses --workers (i.e. every real run). Batched, because
                                # the send blocks on a round trip to each worker.
                                if remote and deck_pfsp_power > 0.0:
                                    _dirty["n"] += 1
                                    if _dirty["n"] >= deck_rec_every:
                                        _dirty["n"] = 0
                                        try:
                                            rpool.set_deck_record(_rec)
                                            if not _dirty.get("said"):
                                                _dirty["said"] = True
                                                _hard = sorted(((1.0 - w / max(1, n)), k)
                                                               for k, (w, n) in _rec.items()
                                                               if n >= 3)[-3:]
                                                print("[train-sim-ppo] deck PFSP ON: record shipped "
                                                      "to %d workers (%d decks seen; hardest so far: "
                                                      "%s)" % (len(rpool.conns), len(_rec),
                                                               ", ".join("%s %.0f%% loss" % (k, 100 * l)
                                                                         for l, k in reversed(_hard))
                                                               or "none yet"), flush=True)
                                        except Exception as _ex:
                                            print("[train-sim-ppo] deck-record ship failed: %s"
                                                  % type(_ex).__name__, flush=True)
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
                            _pn, _wn = _clip_split["play_n"], _clip_split["wait_n"]
                            print("[train-sim-ppo] clip rate PLAY %.3f vs WAIT %.3f | gradient "
                                  "KILLED PLAY %.3f vs WAIT %.3f | net surviving push/step "
                                  "PLAY %+.4f vs WAIT %+.4f"
                                  % (_clip_split["play"] / _pn,
                                     _clip_split["wait"] / _wn,
                                     _clip_split["play_block"] / _pn,
                                     _clip_split["wait_block"] / _wn,
                                     _clip_split["play_push"] / _pn,
                                     _clip_split["wait_push"] / _wn), flush=True)
                            # THE NUMBER THAT DECIDES THE GATE. The two means above are per-step
                            # WITHIN each kind, and plays are rare -- so a large positive play push
                            # and a small negative wait push can still sum to net-negative pressure
                            # on the gate. Weight each by how often it actually occurs. If this is
                            # negative the gate drifts toward WAITING no matter how good plays look
                            # in isolation, and it is self-reinforcing: fewer plays -> smaller
                            # positive term -> more negative still. That is "decay from start".
                            _tot = _pn + _wn
                            _gate_now = _clip_split["gate_z"] / _tot
                            _gate_raw = _clip_split["gate_z_raw"] / _tot
                            print("[train-sim-ppo]   GATE LOGIT PRESSURE (projected; + = toward PLAY) clipped %+.5f "
                                  "vs unclipped %+.5f   [plays are %.1f%% of steps]"
                                  % (_gate_now, _gate_raw, 100.0 * _pn / _tot), flush=True)
                            print("[train-sim-ppo]   CONTROL raw push (no clipping) PLAY %+.4f vs "
                                  "WAIT %+.4f  -- if this matches the surviving push above, the "
                                  "bias is in the ADVANTAGES, not the clip"
                                  % (_clip_split["play_raw"] / _pn,
                                     _clip_split["wait_raw"] / _wn), flush=True)
                            _clip_split.update({"gate_z": 0.0, "gate_z_raw": 0.0,
                                "play_raw": 0.0, "wait_raw": 0.0,
                                "play_block": 0.0, "wait_block": 0.0,
                                "play_push": 0.0, "wait_push": 0.0,
                                "play": 0.0, "play_n": 0.0,
                                                "wait": 0.0, "wait_n": 0.0})
                        if done_n % log_every == 0 and _adv_stats["match"] > 0:
                            print("[train-sim-ppo] adv SIGNED mean (pre-norm): drill %+.4f vs "
                                  "match %+.4f  -> shift %+.4f  (a nonzero shift means one shared "
                                  "mean is moving one population)"
                                  % (_adv_signed["drill"], _adv_signed["match"],
                                     _adv_signed["shift"]), flush=True)
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
                                  f"({100.0 * drill_pass / max(1, drills_done):.0f}% pass all, "
                                  f"{100.0 * sum(drill_recent) / max(1, len(drill_recent)):.0f}% last {len(drill_recent)}, "
                                  f"{100.0 * drills_done / max(1, done_n):.0f}% of eps, "
                                  f"{100.0 * drill_steps / max(1, drill_steps + match_steps):.0f}% of STEPS)"
                                  if drills_done else "")
                            print(f"[train-sim-ppo] {done_n} episodes: winrate={wr:4.0f}% "
                                  f"avg_rew={ar:+.1f} {mps:.1f} ep/s total {wins}W-{losses}L-{draws}D{xs}{ds}",
                                  flush=True)
                        if done_n % save_every == 0:
                            _pt = time.perf_counter()
                            save()
                            if _pc is not None:
                                _pc["save"] += time.perf_counter() - _pt
                        if sp_prob > 0 and done_n % sp_snap_every == 0:
                            _pt = time.perf_counter()
                            snapshot()
                            _broadcast_league()
                            if _pc is not None:
                                _pc["league"] += time.perf_counter() - _pt
                        _pt = time.perf_counter()
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
                        if _pc is not None:
                            _pc["eval"] += time.perf_counter() - _pt
                    else:
                        cobs[i] = nobs
                    if remote:
                        chand[i], cnxt[i] = pay["hand"], pay["nxt"]
                        in_drill[i] = bool(pay.get("in_drill"))
                        celx[i], cthr[i] = pay["elx"], pay["thr"]
                        ct[i] = float(pay.get("t", 0.0))
                        ceage[i] = float(pay.get("eage", 1e9))
                    else:
                        chand[i], cnxt[i] = env.hand_vec.copy(), env.next_vec.copy()
                        in_drill[i] = bool(getattr(env, "_in_drill", False))
                        celx[i], cthr[i] = env.elixir_vec.copy(), env.threat_vec.copy()
                        ct[i] = float(getattr(getattr(env, "eng", None), "t", 0.0))
                        ceage[i] = float(env.enemy_troop_min_age()) if hasattr(env, "enemy_troop_min_age") else 1e9
                roll["rew"].append(np.asarray(rew_row, np.float32))
                roll["done"].append(np.asarray(done_row, np.float32))
                roll["trunc"].append(np.asarray(trunc_row, np.float32))
                roll["sil"].append(np.zeros(K, np.float32))
                roll["isdrill"].append(np.asarray([1.0 if in_drill[i] else 0.0
                                                   for i in range(K)], np.float32))
            if _pc is not None:
                _pc["rollout"] += time.perf_counter() - _pr0
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
                _, _, _, bv_m, bv_d, _ = net(to_obs_batch(cobs), to_vec_batch(chand), to_vec_batch(cnxt),
                                          to_vec_batch(celx), to_vec_batch(cthr))
                # bootstrap from the SAME critic that scored the episode -- routing the rollout and
                # the update but not the bootstrap would bootstrap a drill's tail off the match
                # critic, which is the miscalibration this flag exists to remove.
                bv = bv_m
                if value_head_split:
                    _bsel = torch.tensor([1.0 if in_drill[i] else 0.0 for i in range(len(cobs))],
                                         dtype=bv_m.dtype, device=bv_m.device)
                    bv = torch.where(_bsel > 0.5, bv_d, bv_m)
            roll["boot"] = bv.cpu().numpy().astype(np.float32)
            roll["val"] = [np.asarray(v, np.float32) for v in roll["val"]]
            if cont_log:
                _pt = time.perf_counter()
                try:
                    _log_continuations(roll, K, float(cfg.get("sim", "agent_dt", default=0.6)),
                                       cont_log)
                except Exception as _e:                        # noqa: BLE001 -- logging must never kill training
                    print("[train-sim-ppo] continuation log failed: %s" % type(_e).__name__)
                if _pc is not None:
                    _pc["cont"] += time.perf_counter() - _pt
            _pt = time.perf_counter()
            stats = ppo_update(roll)
            if _pc is not None:
                _pc["update"] += time.perf_counter() - _pt
                _pc["cycle"] += time.perf_counter() - _pc0
                for _k in _PROF_KEYS:
                    _prof_tot[_k] += _pc[_k]
                _prof_tot["steps"] += _pc["steps"]; _prof_tot["n"] += 1
                _prof_tot["matches"] += done_n - _pm0
                _prof_report(_pc, done_n - _pm0, "cycle %d" % _prof_tot["n"])
    except KeyboardInterrupt:
        pass
    finally:
        if _prof_on and _prof_tot["n"]:
            _prof_report(_prof_tot, _prof_tot["matches"], "TOTAL over %d cycles" % _prof_tot["n"])
        save()
        print(f"[train-sim-ppo] stopped after {done_n} match(es); saved -> {ppo_path} "
              f"({wins}W-{losses}L-{draws}D)")
