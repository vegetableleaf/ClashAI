"""RL for the icebow S1 policy -- or the GENERALIST (GenModel, a ``"gen": True`` init checkpoint, L68 T11) playing
icebow -- on RoyaleSim: PPO-clip, group leave-one-out baseline, terminal reward, KL leash to the frozen init. One
learner process + ``n_actors`` actor processes (torch.multiprocessing, spawn). L68.

Generalist init (T11): actors play ``e1_eval.GenPolicy`` and record its own input rows (``e1_eval.GEN_ROW_KEYS``); the
learner recomputes the sampler's distribution through ``GenPolicy.heads_t`` (card = the 4 hand-position logits scattered
onto deck slots, i.e. softmax over allowed hand positions; cell = ``cell_logits_gen`` for the chosen card identity +
form); pro agreement = ``eval_gen.evaluate`` on the dataset_gen v3val rows (``proagree_data_gen``); checkpoints carry
``gen``/``d_c``/``card_vocab`` so ``eval_gen.load_model`` / ``e1_eval.load_policy`` load them. Conditions (T11):
``noise_off`` / ``opp_elixir`` / ``action_delay_ticks`` / ``extrapolate_ticks`` go into every actor match cfg, rollouts
AND held-out screens (``condition_cfg``, ``actor_cfg``); defaults = the old behaviour.

LEAGUE (T12b, ``league: true``, generalist init only): every rollout is a SELF-PLAY match (``e1_eval.run_selfplay_batch``
on RoyaleSelfPlayEnv): the learner (sampled + recorded as above) vs a FROZEN opponent -- the init generalist, the S1
icebow specialist (icebow only) or a learner snapshot (``<run>_snap_u{NNNN}.pt`` every ``league_snapshot_every``
updates, newest ``league_snapshot_keep`` in the pool) -- on decks drawn from the census pool (``sample_matchups``); E
matchups = the LOO groups, G rollouts each; both sides under the condition keys. Pool + sampling rng ride in the
checkpoint (--resume continues them). The held-out ghost screen, pro agreement and guards are unchanged.
BRANCH (opt3, ``branch_gate: true``, league only; scratchpad/gauntlet/L73/opt3/INTERFACE.md T3 + the lead's async
redesign): ``branch_actors`` worker processes (``BranchPool``, separate from the PPO actors, which are untouched) run
CONTINUOUSLY: self-play matches with the newest learner weights (picked up between rounds, never waited for) on the
GREEDY live rule against a SAMPLING league opponent; at up to ``branch_points_per_match`` decisions with p_gate in
``branch_band`` they compare PLAY now vs HOLD from the identical state (T1 ``BranchRunner.pair``, T2 ``branch_label``:
full-match outcome, k continuations) and stream each labelled sample, tagged with its weights version, back. Once per
update the learner drains the stream (never blocking), drops samples staler than ``branch_max_staleness`` updates and
|delta| < branch_min_abs_delta, keeps a FIFO buffer (``branch_buffer``) and takes ONE optimizer step on branch_coef x the
weighted BCE of the live gate x = (z - logit(tau)) / T toward 1[delta > 0] (``branch_step``). Off = no worker, no step.
R4 (``branch_kinds``, default ["hold"] = the above exactly): "card" forks Rocket vs the live rule's card where Rocket is
affordable, not the argmax and P(Rocket) >= branch_rocket_band x P(top), and trains a pairwise logistic loss on the two
card logits; "xbow_class" forks the X-Bow's majority vs minority reach class (minority mass >= branch_xbow_floor) and
trains a pairwise logistic loss on the two classes' cell log-mass. Each kind has its own per-match quota
(branch_points_per_match / branch_card_points / branch_xbow_points) and coefficient (branch_coef / branch_card_coef /
branch_xbow_coef); the one branch step sums coef_k x kind k's weighted mean loss.
LEASH (T12b, owner ruling):``leash: max`` steers beta on max(KL_gate, KL_card, KL_cell) (``leash_kl``); ``cell`` = the
old KL_cell rule exactly (and what a run resumed from before the key keeps).

    research/ext/Royale/.venv/Scripts/python.exe -m pipeline.rl_royale --config pipeline/rl_royale.yaml --run NAME
    ... --smoke          E=4, G=2, 1 actor, 2 updates + the checks below; prints SMOKE PASS, exits 0
    ... --resume         continue from <run>_latest.pt exactly (update counter, beta, optimizer, rng, guards)
    ... key=value        override any rl_royale.yaml key (YAML-typed), e.g. max_updates=1 E=8

Design (binding): scratchpad/gauntlet/L68/rl_plan.md "Differences from E1", "Behaviour policy", "Learner", "Launch";
where it is silent, scratchpad/gauntlet/L67/e1_engine_rl_design.md 3.2-3.6 and 4.2 (E1). Runbook:
scratchpad/gauntlet/L68/rl/RUNBOOK.md.

One update (``Learner.one_update``):
  1. E train entries (uniform, no repeat within the update) x G rollouts -> actors run ``e1_eval.run_batch`` with
     ``policy="sample"``, ``record=True``; behaviour seed ``crc32(f"{tag}:behaviour:{g}:{update}")`` (e1_eval),
     obs seed ``crc32(f"{tag}:obs:{g}:{update}")`` (here, ``rl_obs_seed``), both per (entry, g).
  2. R = +1/-1/0; A_i = R_i - mean_{j != i} R_j over the entry's G rollouts, |A| <= 2 (``loo_advantage``).
     ``advantage: gae`` (R1, L69 reward_plan.md; default ``match_loo`` = the line above, unchanged): per-row reward
     ``r_step`` (0, the outcome on a match's last row), critic V = P(win) - P(loss) from the EXISTING crown-diff value
     head (``value_scalar``), GAE(gae_gamma, gae_lambda) advantages normalised per batch (``gae_batch``), + vf_coef x a
     PPO-clipped value loss; the first ``critic_warmup_updates`` updates train ONLY the value head (no L_pg, no KL,
     beta held).
     ``vf_trunk_grad: false`` (default true): the value loss reaches value_head only. ``shaping: tower_crown`` (R2,
     gae only; default none): F_t = gamma_t Phi(s_{t+1}) - Phi(s_t) (``reward_shaping``, Phi = 0 at the match end) on
     every kept row, from the ``phi_state`` rows e1_eval records under ``record_phi``, applied as a RESIDUAL critic
     V_eff = Phi + shaping_critic_scale x v_net with A = GAE(r, V_eff) on the unshaped reward (= the shaped-critic
     method, ``gae_batch``, L69 7b); needs critic_warmup_updates > 0. ``shaping: value_phi`` (lever C, L73): the same
     machinery with Phi(row) = shaping_w_value x the causal trailing mean, over the previous shaping_phi_window_s
     seconds of the match's kept rows (by tick), of P(win) - P(loss) from the value head of a FROZEN net
     (shaping_phi_ckpt, default the init; loaded once by the learner, never trained) on the row's own model inputs
     (``value_phi_rewards``); |Phi| <= shaping_w_value. Actors only add the tick record (``record_tick``).
     ``gae_gamma_unit: tick`` (gae only; default row = gae_gamma per kept row): gamma_t = gae_gamma_tick ** (ticks
     from kept row t to the next kept row, ``row_gammas``), in GAE AND in F_t, from the ``tick`` rows e1_eval records
     under ``record_tick``. ``gae_terminal_gap: true`` (default false, gae + tick only) also discounts the terminal
     outcome by gae_gamma_tick ** (end_tick - last_kept_tick); Phi at the match end stays 0.
  3. Rows that sampled nothing (no card allowed) are dropped; each remaining decision carries weight 1/(n_i M) so a
     match's decisions sum to 1/M (``match_weights``: the loss is averaged per match, then over the batch).
  4. Frozen-ref terms once per update (``ref_terms``); ``ppo_epochs`` x minibatches of ``minibatch`` decisions:
     log pi recomputed WITH gradients from the stored tok/mask/sc/past exactly as ``sample_decide_batch`` defined it
     (``policy_terms``), L = L_pg + beta (KL_gate + KL_card + KL_cell) on the tempered distributions
     (``minibatch_loss``). Model in eval() for rollout AND update (E1 3.3 dropout trap).
  5. Update 0, epoch 0, minibatch 0: max |ratio - 1| < 1e-4 and every KL < 1e-6 (plan values), else AssertionError
     (a bug, not noise).
  6. beta x2 / /2 around ``kl_target`` on the leash KL (``leash_kl``: KL_cell, or the max of the three), clamp
     [beta_min, beta_max] (``adapt_beta``); kl_target never moves.
  7. Held-out screen / pro agreement when due; stop rules (``Guards``, ``tripwire_reason``, ``hard_stop_reason``);
     ``<run>_latest.pt`` every update (tmp + os.replace), ``<run>_u{NNNN}.pt`` every ``save_every`` (never overwritten).
Checkpoint = train_s1 layout (model/args/deck/epoch/val/n_params) + an ``rl`` dict, all ``weights_only``-loadable, so
``engine_play.load_model`` and ``pipeline.eval_s1`` load it unchanged. ``u0000`` = the init, saved before any update.

Outputs: ``scratchpad/gauntlet/L68/rl/<run>/`` (train_log.jsonl, train.log, config.yaml, pid.json, actors.pid, entries.json,
init_proagree.json, init_screen.json; drop a file named STOP here to stop after the current update) and
``icebow/data/bench/rl_royale/<run>/`` (checkpoints). Nothing else under icebow/data/ is written.
royale_env (royalegym) is imported only inside the actor / loadability code, so the unit tests run in the icebow venv.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import math
import os
import queue
import sys
import time
import traceback
import zlib
from collections import Counter
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn.functional as Fn

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import e1_eval as E                                               # noqa: E402
from pipeline import reward_shaping as RS                                       # noqa: E402
from pipeline.model_v3 import hand_mask_from_sc                                 # noqa: E402

RUN_ROOT = REPO / "scratchpad" / "gauntlet" / "L68" / "rl"
CKPT_ROOT = REPO / "icebow" / "data" / "bench" / "rl_royale"
PA_KEYS = ("cell_half_top1", "card_top1", "gate_bal_acc")
CARD_FILL = -1e9            # finite "not allowed" card logit: exp underflows to exactly 0 (same probs as the sampler's
                            # -inf) but 0 * (lp - ref) stays 0, so the KL has no NaN gradient at masked slots
ASSERT_RATIO, ASSERT_KL = 1e-4, 1e-6          # rl_plan.md "Learner" (measured L68: 7.8e-6 / ~1e-12)
SMOKE = {"E": 4, "G": 2, "n_actors": 1, "in_flight": 8, "max_updates": 2, "screen_entries": 8, "proagree_rows": 1000,
         "proagree_every": 1, "screen_every": 1, "save_every": 1, "league_snapshot_every": 1}
TRAJ_KEYS = ("tok", "mask", "sc", "past", "allowed", "gate_sampled", "played", "slot", "cell")
COND_KEYS = ("noise_off", "opp_elixir", "action_delay_ticks", "extrapolate_ticks")   # rl_royale.yaml "conditions"


def condition_cfg(c: dict) -> dict:
    """The rollout / screen CONDITION keys of a config -> e1_eval match-cfg entries (validated; SystemExit on a bad
    value). ``noise_off``: list or comma string of e1_view.Noise names (e1_eval.parse_noise_off), or ``all`` (clean
    obs, run_screen's spelling); ``opp_elixir``: None or one of e1_eval.OPP_ELIXIR_MODES; delays: ints >= 0. Missing /
    empty keys = today's cfg (Noise() all on, no counter, 0, 0), which e1_eval.Match treats exactly like unset."""
    spec = c.get("noise_off") or []
    names = [s.strip() for s in spec.split(",") if s.strip()] if isinstance(spec, str) else [str(s) for s in spec]
    if names == ["all"]:
        names = list(E.NOISE_NAMES)
    opp = c.get("opp_elixir") or None
    if opp is not None and opp not in E.OPP_ELIXIR_MODES:
        raise SystemExit(f"bad opp_elixir {opp!r}: null or one of {E.OPP_ELIXIR_MODES}")
    d, h = int(c.get("action_delay_ticks") or 0), int(c.get("extrapolate_ticks") or 0)
    if d < 0 or h < 0:
        raise SystemExit(f"action_delay_ticks {d} / extrapolate_ticks {h} must be >= 0")
    return {"noise": E.parse_noise_off(",".join(names)), "opp_elixir": opp, "action_delay_ticks": d,
            "extrapolate_ticks": h}


def actor_cfg(base: dict, kind: str, aid: int, dev: str) -> dict:
    """The e1_eval match cfg an actor runs a job under: ``rollout`` = the tempered sampler, recorded; ``screen`` = the
    greedy live rule. BOTH carry the base's condition keys (``condition_cfg``), so train and screen conditions match."""
    from pipeline.e1_view import Noise
    cfg = {"policy": "sample" if kind == "rollout" else "live", "tau": float(base["tau"]),
           "afford_mask": bool(base["afford_mask"]), "stall_elixir": base["stall_elixir"],
           "stall_seconds": float(base["stall_seconds"]), "obs": base["obs"], "noise": Noise(),
           "p_random": 0.0, "random_hand_only": False, "grid": base["grid"], "device": dev,
           "decide_every": int(base["decide_every"]), "slot": aid, "port": 0, "T": float(base["T"]),
           "record": kind == "rollout"}
    cfg.update(condition_cfg(base))
    if kind == "rollout" and base.get("shaping", "none") == "tower_crown":
        cfg["record_phi"] = True                              # R2: each row carries reward_shaping.phi_record
    if kind == "rollout" and (base.get("gae_gamma_unit", "row") == "tick" or base.get("shaping") == "value_phi"):
        cfg["record_tick"] = True                             # each row carries its decision tick
    return cfg


# ------------------------------------------------------------------------------------------------------
# pure helpers (tested offline: pipeline/tests/test_rl_royale.py)
# ------------------------------------------------------------------------------------------------------
def reward(outcome: str) -> float:
    return {"win": 1.0, "loss": -1.0}.get(outcome, 0.0)


def loo_advantage(R, clip: float = 2.0) -> np.ndarray:
    """E1 3.2: A_i = R_i - mean_{j != i} R_j over one entry's rollouts; |A| <= clip; a one-outcome group -> 0."""
    R = np.asarray(R, dtype=np.float64)
    if len(R) < 2:
        return np.zeros(len(R))
    return np.clip(R - (R.sum() - R) / (len(R) - 1), -clip, clip)


# ---- per-decision credit (R1, scratchpad/gauntlet/L69/reward_plan.md): ``advantage: gae`` -------------------------
ADV_MODES = ("match_loo", "gae")
SHAPING_MODES = ("none", "tower_crown", "value_phi")   # R2 (reward_plan.md 2 / 3b) / lever C: potential shaping, gae only
GAE_DEFAULTS = {"advantage": "match_loo", "gae_gamma": 0.999, "gae_lambda": 0.95, "vf_coef": 0.5, "vf_clip": 0.2,
                "critic_warmup_updates": 0,     # a config WITHOUT these keys (a run started before R1) = match_loo
                "shaping": "none", "shaping_w_tower": 0.3, "shaping_w_crown": 0.3,   # ... and no shaping (R2)
                "vf_trunk_grad": True,          # ... and the value loss trains the shared trunk (R1 as committed)
                "gae_gamma_unit": "row", "gae_gamma_tick": 0.99994,   # ... and gamma per kept row (R1 as committed)
                "gae_terminal_gap": False,    # opt-in: discount the outcome from the actual match end
                "shaping_critic_scale": 1.5}    # R2 residual critic: V_eff = Phi + scale x v_net (``gae_batch``)
# lever C (``shaping: value_phi``): Phi = w x the smoothed V of a frozen checkpoint (None = the run's init). Optional
# keys outside GAE_DEFAULTS (no yaml carries them); adv_cfg returns them only when shaping is value_phi.
VALUE_PHI_DEFAULTS = {"shaping_w_value": 0.5, "shaping_phi_window_s": 10.0, "shaping_phi_ckpt": None}
GAMMA_UNITS = ("row", "tick")
VALUE_PHI_KEYS = tuple(VALUE_PHI_DEFAULTS)              # optional config overrides (load_config)


def adv_cfg(cfg: dict) -> dict:
    """The R1 keys of a config (``GAE_DEFAULTS`` for missing ones), validated: SystemExit naming the bad key."""
    c = {k: cfg.get(k, v) for k, v in GAE_DEFAULTS.items()}
    vp = {k: cfg.get(k, v) for k, v in VALUE_PHI_DEFAULTS.items()}
    num = (lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v))
    bad = []
    if c["advantage"] not in ADV_MODES:
        bad.append(f"advantage must be one of {ADV_MODES}, got {c['advantage']!r}")
    if not (num(c["gae_gamma"]) and 0.0 < c["gae_gamma"] <= 1.0):
        bad.append(f"gae_gamma must be in (0, 1], got {c['gae_gamma']!r}")
    if not (num(c["gae_lambda"]) and 0.0 <= c["gae_lambda"] <= 1.0):
        bad.append(f"gae_lambda must be in [0, 1], got {c['gae_lambda']!r}")
    if not (num(c["vf_coef"]) and c["vf_coef"] >= 0.0):
        bad.append(f"vf_coef must be a finite number >= 0, got {c['vf_coef']!r}")
    if not (num(c["vf_clip"]) and c["vf_clip"] > 0.0):
        bad.append(f"vf_clip must be a finite number > 0, got {c['vf_clip']!r}")
    w = c["critic_warmup_updates"]
    if not (isinstance(w, int) and not isinstance(w, bool) and w >= 0):
        bad.append(f"critic_warmup_updates must be an integer >= 0, got {w!r}")
    if c["shaping"] not in SHAPING_MODES:
        bad.append(f"shaping must be one of {SHAPING_MODES}, got {c['shaping']!r}")
    elif c["shaping"] != "none" and c["advantage"] != "gae":
        bad.append(f"shaping {c['shaping']!r} needs advantage gae (summed per match it telescopes to a constant)")
    for k in ("shaping_w_tower", "shaping_w_crown"):
        if not (num(c[k]) and c[k] >= 0.0):
            bad.append(f"{k} must be a finite number >= 0, got {c[k]!r}")
    for k in ("shaping_w_value", "shaping_phi_window_s"):
        if not (num(vp[k]) and vp[k] >= 0.0):
            bad.append(f"{k} must be a finite number >= 0, got {vp[k]!r}")
    if not isinstance(c["vf_trunk_grad"], bool):
        bad.append(f"vf_trunk_grad must be true or false, got {c['vf_trunk_grad']!r}")
    elif not c["vf_trunk_grad"] and c["advantage"] != "gae":
        bad.append("vf_trunk_grad false needs advantage gae (match_loo has no value loss)")
    if c["gae_gamma_unit"] not in GAMMA_UNITS:
        bad.append(f"gae_gamma_unit must be one of {GAMMA_UNITS}, got {c['gae_gamma_unit']!r}")
    elif c["gae_gamma_unit"] != "row" and c["advantage"] != "gae":
        bad.append(f"gae_gamma_unit {c['gae_gamma_unit']!r} needs advantage gae (match_loo has no discount)")
    if not (num(c["gae_gamma_tick"]) and 0.0 < c["gae_gamma_tick"] <= 1.0):
        bad.append(f"gae_gamma_tick must be in (0, 1], got {c['gae_gamma_tick']!r}")
    if not isinstance(c["gae_terminal_gap"], bool):
        bad.append(f"gae_terminal_gap must be true or false, got {c['gae_terminal_gap']!r}")
    elif c["gae_terminal_gap"] and (c["advantage"] != "gae" or c["gae_gamma_unit"] != "tick"):
        bad.append("gae_terminal_gap true needs advantage gae AND gae_gamma_unit tick")
    if not (vp["shaping_phi_ckpt"] is None or (isinstance(vp["shaping_phi_ckpt"], str) and vp["shaping_phi_ckpt"])):
        bad.append(f"shaping_phi_ckpt must be null (= init) or a checkpoint path, got {vp['shaping_phi_ckpt']!r}")
    sc = c["shaping_critic_scale"]
    if not (num(sc) and sc > 0.0):
        bad.append(f"shaping_critic_scale must be a finite number > 0, got {sc!r}")
    elif c["shaping"] != "none" and not bad:
        if c["shaping"] == "value_phi":                        # |Phi| <= w_value (a mean of V in [-1, 1], x w)
            need, why = 1.0 + vp["shaping_w_value"], "1 + w_value"
        else:
            need = 1.0 + c["shaping_w_tower"] + 2.0 / 3.0 * c["shaping_w_crown"]   # max |G - Phi| before the end
            why = "1 + w_tower + (2/3) w_crown"
        if sc < need:
            bad.append(f"shaping_critic_scale {sc} < {need:.4f} = {why}: the residual target "
                       f"(G - Phi) / scale could leave the value head's [-1, 1]")
        if c["critic_warmup_updates"] == 0:
            bad.append(f"shaping {c['shaping']!r} needs critic_warmup_updates > 0 (the pretrained value head "
                       f"predicts G, not the residual (G - Phi) / scale)")
    if bad:
        raise SystemExit("bad advantage config: " + "; ".join(bad))
    if c["shaping"] == "value_phi":
        c.update(vp)
    return c


# ---- counterfactual gate branching (opt3, scratchpad/gauntlet/L73/opt3/INTERFACE.md T3): opt-in ``branch_gate`` ------
# Off (the default, and any config without the keys) = the trainer exactly as before: no branch actor, no extra loss.
BRANCH_DEFAULTS = {"branch_gate": False, "branch_actors": 24, "branch_threads": 1, "branch_points_per_match": 6,
                   "branch_band": [0.2, 0.55], "branch_hold_s": [2, 4, 8], "branch_hold_tau": 0.55,
                   "branch_horizon_s": None, "branch_k": 16, "branch_score": "outcome", "branch_phi_ckpt": None,
                   "branch_coef": 0.1, "branch_lr": None, "branch_min_abs_delta": 0.25, "branch_buffer": 512,
                   "branch_max_staleness": 3, "branch_buffer_max_age": 20,
                   # R4: more fork kinds (pipeline.branching.ALT_KINDS). Default hold-only = opt3 exactly.
                   "branch_kinds": ["hold"], "branch_card_points": 6, "branch_xbow_points": 6,
                   "branch_card_coef": 0.1, "branch_xbow_coef": 0.1, "branch_rocket_band": 0.5,
                   "branch_xbow_floor": 0.2}
BRANCH_SPECS_PER_SEND = 2      # fresh matchups per worker per update (a branch match spans many updates)
BRANCH_SCORES = ("phi", "outcome")
# per kind: (points-per-match quota key, loss coefficient key)
BRANCH_KIND_KEYS = {"hold": ("branch_points_per_match", "branch_coef"),
                    "card": ("branch_card_points", "branch_card_coef"),
                    "xbow_class": ("branch_xbow_points", "branch_xbow_coef")}
R4_KEYS = ("branch_kinds", "branch_card_points", "branch_xbow_points", "branch_card_coef", "branch_xbow_coef",
           "branch_rocket_band", "branch_xbow_floor")


def branch_cfg(cfg: dict) -> dict:
    """The branch keys of a config (``BRANCH_DEFAULTS`` for missing ones), validated: SystemExit naming the bad key.
    ``branch_gate`` on also needs ``league`` (branch workers play self-play matches, T1's ``SelfPlayMatch`` fork), a
    SAMPLING league opponent (``league_opp_policy: sample``, T > 0: with a greedy opponent all k continuations of a
    branch are identical), branch_hold_tau > tau (HOLD = a STRICTER gate), branch_band's upper edge <= branch_hold_tau
    (so the HOLD branch never also plays at the root) and, for ``branch_score: phi``, a ``branch_phi_ckpt``
    (``outcome``: branch_horizon_s null). ``branch_lr`` null = the PPO ``lr`` (the branch step's OWN Adam)."""
    c = {k: cfg.get(k, v) for k, v in BRANCH_DEFAULTS.items()}
    num = (lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v))
    intk = (lambda v, lo: isinstance(v, int) and not isinstance(v, bool) and v >= lo)
    on, bad = c["branch_gate"], []
    if not isinstance(on, bool):
        bad.append(f"branch_gate must be true or false, got {on!r}")
        on = False
    for k in ("branch_actors", "branch_threads"):
        if not intk(c[k], 1):
            bad.append(f"{k} must be an integer >= 1, got {c[k]!r}")
    for k in ("branch_max_staleness", "branch_buffer_max_age"):
        if not intk(c[k], 0):
            bad.append(f"{k} must be an integer >= 0, got {c[k]!r}")
    if not (c["branch_lr"] is None or (num(c["branch_lr"]) and c["branch_lr"] >= 0.0)):
        bad.append(f"branch_lr must be null (= lr) or a finite number >= 0, got {c['branch_lr']!r}")
    if on and cfg.get("league_opp_policy", "sample") != "sample":
        bad.append(f"branch_gate true needs league_opp_policy sample, got {cfg.get('league_opp_policy')!r}: a greedy "
                   f"branch-match opponent makes all branch_k continuations identical")
    elif on and not (num(cfg.get("T")) and cfg["T"] > 0):
        bad.append(f"branch_gate true needs T > 0 (the sampling opponent's temperature), got {cfg.get('T')!r}")
    if not intk(c["branch_buffer"], 1):
        bad.append(f"branch_buffer must be an integer >= 1, got {c['branch_buffer']!r}")
    if not intk(c["branch_points_per_match"], 1):
        bad.append(f"branch_points_per_match must be an integer >= 1, got {c['branch_points_per_match']!r}")
    b = c["branch_band"]
    if not (isinstance(b, (list, tuple)) and len(b) == 2 and all(num(x) for x in b) and 0.0 <= b[0] < b[1] <= 1.0):
        bad.append(f"branch_band must be [lo, hi] with 0 <= lo < hi <= 1, got {b!r}")
    h = c["branch_hold_s"]
    if not (isinstance(h, (list, tuple)) and h and all(num(x) and x > 0 for x in h)):
        bad.append(f"branch_hold_s must be a non-empty list of numbers > 0, got {h!r}")
    ht = c["branch_hold_tau"]
    if not (num(ht) and 0.0 < ht < 1.0):
        bad.append(f"branch_hold_tau must be in (0, 1), got {ht!r}")
    elif on and num(cfg.get("tau")) and ht <= cfg["tau"]:
        bad.append(f"branch_hold_tau {ht} must be > tau {cfg['tau']} (HOLD is the stricter gate)")
    elif on and isinstance(b, (list, tuple)) and len(b) == 2 and num(b[1]) and b[1] > ht:
        bad.append(f"branch_band upper edge {b[1]} must be <= branch_hold_tau {ht} (else the HOLD branch also plays "
                   f"at the root: a pair with no difference)")
    hz = c["branch_horizon_s"]
    if not (hz is None or (num(hz) and hz > 0)):
        bad.append(f"branch_horizon_s must be null (play to the end) or a number > 0, got {hz!r}")
    if not intk(c["branch_k"], 1):
        bad.append(f"branch_k must be an integer >= 1, got {c['branch_k']!r}")
    if c["branch_score"] not in BRANCH_SCORES:
        bad.append(f"branch_score must be one of {BRANCH_SCORES}, got {c['branch_score']!r}")
    elif on and c["branch_score"] == "phi" and not (isinstance(c["branch_phi_ckpt"], str) and c["branch_phi_ckpt"]):
        bad.append(f"branch_score phi needs branch_phi_ckpt (a frozen gen checkpoint), got {c['branch_phi_ckpt']!r}")
    elif on and c["branch_score"] == "outcome" and c["branch_horizon_s"] is not None:
        bad.append("branch_score outcome needs branch_horizon_s null (an outcome exists only at the match end)")
    for k in ("branch_coef", "branch_min_abs_delta", "branch_card_coef", "branch_xbow_coef"):
        if not (num(c[k]) and c[k] >= 0.0):
            bad.append(f"{k} must be a finite number >= 0, got {c[k]!r}")
    kd = c["branch_kinds"]
    if not (isinstance(kd, (list, tuple)) and kd and len(set(map(str, kd))) == len(kd)
            and all(x in BRANCH_KIND_KEYS for x in kd)):
        bad.append(f"branch_kinds must be a non-empty list of distinct kinds from {list(BRANCH_KIND_KEYS)}, got {kd!r}")
    else:
        c["branch_kinds"] = list(kd)
    for k in ("branch_card_points", "branch_xbow_points"):
        if not intk(c[k], 1):
            bad.append(f"{k} must be an integer >= 1, got {c[k]!r}")
    if not (num(c["branch_rocket_band"]) and 0.0 < c["branch_rocket_band"] <= 1.0):
        bad.append(f"branch_rocket_band must be in (0, 1], got {c['branch_rocket_band']!r}")
    if not (num(c["branch_xbow_floor"]) and 0.0 < c["branch_xbow_floor"] <= 0.5):
        bad.append(f"branch_xbow_floor must be in (0, 0.5], got {c['branch_xbow_floor']!r}")
    if on and not cfg.get("league"):
        bad.append("branch_gate true needs league true (branch actors play self-play matches)")
    if bad:
        raise SystemExit("bad branch config: " + "; ".join(bad))
    return c


# RoyaleSim phases (royale_env.REGEN_SCHEDULE): 1x to 120 s, 2x to 180 s (regulation end), overtime to tick 6000
PHASES = ((0, "single"), (2400, "double"), (3600, "overtime"))   # = branching.BranchResult.phase
BRANCH_TARGET_END = 4800       # targets drawn on [0, 4800): 1x / 2x / first 60 s of OT, 1/3 of the points each


def phase_of(tick: int) -> str:
    return [name for t0, name in PHASES if int(tick) >= t0][-1]


def branch_targets(rng: np.random.Generator, n: int) -> list[int]:
    """``n`` sorted target ticks for one match's branch points, stratified toward 2x / OT: density 1 per single-elixir
    tick, 2 per double / overtime tick on [0, BRANCH_TARGET_END) (equal mass per phase). A target fires at the first ELIGIBLE learner
    decision at or after it (``play_branch_match``); OT targets of a match that ends in regulation never fire.
    ponytail: fixed density, no per-match length model -- a regulation-only match gets ~2/3 of its points."""
    segs = [(0, 2400, 1.0), (2400, 3600, 2.0), (3600, BRANCH_TARGET_END, 2.0)]
    mass = np.array([(b - a) * d for a, b, d in segs])
    out = []
    for _ in range(int(n)):
        a, b, _d = segs[int(rng.choice(len(segs), p=mass / mass.sum()))]
        out.append(int(rng.integers(a, b)))
    return sorted(out)


def branch_impl():
    """(BranchSpec, BranchRunner, branch_label): T1's ``pipeline.branching`` + T2's ``pipeline.branch_score`` (tests
    monkeypatch this function; the smoke patches it inside the spawn workers via a wrapped ``branch_worker_main``)."""
    from pipeline.branching import BranchRunner, BranchSpec
    from pipeline.branch_score import branch_label
    return BranchSpec, BranchRunner, branch_label


def side_decide(s, fwd: bool = False) -> tuple:
    """One PREPARED self-play side's forward + decision under its own model and cfg -- ``run_selfplay_batch``'s
    per-policy rule (live: greedy ``live_decide_batch``; sample: ``sample_decide_batch`` on the side's own RNG) on one
    row. -> (p_gate, decision, allowed, stalled = anti-stall forces a play now), + (enc, heads) with ``fwd``."""
    from pipeline.decision_options import match_kwargs
    from pipeline.search_s0 import forward
    p, enc, heads, hand = forward(s)
    _, allowed, stalled = s.pre(hand)
    if s.cfg["policy"] == "live":
        d = E.live_decide_batch(s.model, enc, heads, [p], allowed[None], np.array([stalled]), tau=s.cfg["tau"],
                                device=s.cfg["device"], **match_kwargs([s]))[0]
    else:
        d = E.sample_decide_batch(s.model, enc, heads, [p], allowed[None], np.array([stalled]), [s], s.cfg)[0]
    out = (float(p), d, allowed, bool(stalled))
    return out + (enc, heads) if fwd else out


def fork_alt(kind: str, s, enc, heads, d: dict, allowed: np.ndarray, bc: dict) -> Optional[dict]:
    """R4: is our PREPARED side's decision ``d`` a fork point of ``kind`` ("card" / "xbow_class"), and with which root
    actions? -> {"a": (slot, cell), "b": (slot, cell), "row": the extra learner-row fields, "info"} or None.
      card        ``branching.card_alt`` (live rule plays, Rocket affordable, not argmax, P(Rocket) >= branch_rocket_band
                  x P(top)): A = the live rule's (slot, cell), B = Rocket at its own argmax cell. Row: slot_a, slot_b.
      xbow_class  the live rule plays X-Bow, ``branching.xbow_alt`` on its cell logits with the reach rule
                  ``decision_options.xbow_offensive_cells`` (alive enemy towers of the prepared board, the side's grid)
                  and branch_xbow_floor: A / B = the majority / minority class argmax cell. Row: played, slot, cell
                  (= A), cls_a (the A class's cells)."""
    from pipeline.branching import card_alt, xbow_alt
    from pipeline.decision_options import is_xbow, xbow_offensive_cells
    if not d.get("play"):
        return None
    names = list(s.deck.cards)
    with torch.no_grad():
        if kind == "card":
            got = card_alt(heads["card"][0].detach().double().cpu().numpy(), allowed, names, d,
                           float(bc["branch_rocket_band"]))
            if got is None:
                return None
            top, rk = got
            z = heads["card"][0].detach().double().cpu().numpy()
            cell_b = int(s.model.cell_logits(enc, torch.tensor([rk], device=heads["card"].device))[0].argmax())
            return {"a": (int(d["slot"]), int(d["cell"])), "b": (rk, cell_b), "row": {"slot_a": top, "slot_b": rk},
                    "info": {"ratio": float(math.exp(z[rk] - z[top]))}}
        if kind == "xbow_class":
            slot = int(d["slot"])
            if not is_xbow(names[slot]):
                return None
            alive = tuple(bool(t.alive) for t in s._cur[1].towers[3:6])
            cl = s.model.cell_logits(enc, torch.tensor([slot], device=heads["card"].device))[0]
            got = xbow_alt(cl.detach().double().cpu().numpy(), xbow_offensive_cells(alive, s.cfg["grid"]),
                           float(bc["branch_xbow_floor"]))
            if got is None:
                return None
            ca, cb, a_cls, dmass = got
            return {"a": (slot, ca), "b": (slot, cb),
                    "row": {"played": True, "slot": slot, "cell": ca, "cls_a": a_cls.copy()},
                    "info": {"def_mass": dmass, "a_defensive": bool(dmass > 0.5)}}
    raise ValueError(f"unknown fork kind {kind!r}")


def branch_row(s, allowed: np.ndarray, p: float, T: float, stalled: bool = False) -> dict:
    """The deciding side's input row in ``Match._record``'s format (the generalist's ``gen_row`` keys, else
    tok/mask/sc/past), with the trajectory fields ``Match._traj_arrays`` stacks: a gate-only row (gate_sampled, not
    played), so ``policy_terms`` recomputes exactly the gate logit x the PPO loss uses."""
    if s._gen_row is not None:
        row = {k: s._gen_row[k] for k in s._gen_row if k in E.GEN_ROW_KEYS + E.GEN_V3_KEYS + E.GEN_V31_KEYS}
    else:
        tok, mask, sc, past = s._obs
        row = {"tok": tok, "mask": mask, "sc": sc, "past": past}
    return {**row, "allowed": np.asarray(allowed, bool).copy(), "stalled": bool(stalled), "gate_sampled": True,
            "played": False,
            "slot": -1, "cell": -1, "lp_gate": 0.0, "lp_card": 0.0, "lp_cell": 0.0, "p_gate": float(p), "T": float(T)}


def play_branch_match(m, runner, impl: tuple, bc: dict, phi=None, sync=(lambda: True), emit=None) -> list[dict]:
    """Play SelfPlayMatch ``m`` to the end as ``run_selfplay_batch`` would (every side prepared, then decided on its
    own model / cfg, then applied in side order) with the learner on the GREEDY live rule. At an eligible learner
    decision -- an affordable card, anti-stall NOT firing (a forced play has no HOLD alternative), p_gate in
    ``branch_band`` (which straddles tau: above it PLAY is the live rule's own play, below it T1 forces the play) and
    a ``branch_targets`` tick reached -- call ``runner.pair(m, ds, spec)`` (T1) BEFORE any side's decision draws an RNG
    (the learner's live rule draws none) and ``branch_label(result, branch_score[, phi=])`` (T2) -> one sample: the row
    (``branch_row``), delta, weight, phase, tick. The main trajectory is unchanged by the branching (pair leaves ``m``
    untouched, T1 contract). ``sync()`` runs at the top of every round (a branch worker loads the newest weights
    there, so a round -- decision and pair -- uses ONE set of weights); False = stop now. ``emit(sample)`` (optional)
    gets each sample as soon as it is labelled."""
    Spec, _, label = impl
    tag = str(m.spec["tag"])
    rng = np.random.default_rng(zlib.crc32(f"{tag}:branch".encode()))
    kinds = bc.get("branch_kinds", ["hold"])
    targets = branch_targets(rng, bc["branch_points_per_match"]) if "hold" in kinds else []
    # R4 kinds: their own target streams (the hold stream above is untouched); a target fires at the first decision at
    # or after it that ``fork_alt`` accepts
    extra = {k: branch_targets(np.random.default_rng(zlib.crc32(f"{tag}:branch:{k}".encode())),
                               bc[BRANCH_KIND_KEYS[k][0]]) for k in kinds if k != "hold"}
    lo, hi = bc["branch_band"]
    L, out = m.learner, []
    while True:
        if not sync():
            return out
        ds = m.due()
        if not ds:
            return out
        for s in ds:
            s.prepare()
        dec = {}
        if L in ds:
            if extra:
                p, d, allowed, stalled, enc, heads = side_decide(L, fwd=True)
                dec[id(L)] = (p, d, allowed, stalled)
            else:
                p, d, allowed, stalled = dec[id(L)] = side_decide(L)
            tick = int(m.env.tick)
            for kind, tg in extra.items():
                if not (tg and tick >= tg[0]):
                    continue
                alt = fork_alt(kind, L, enc, heads, d, allowed, bc)
                if alt is None:
                    continue
                tg.pop(0)
                j = len(out)
                spec = Spec(hold_s=0.0, hold_tau=float(bc["branch_hold_tau"]), horizon_s=bc["branch_horizon_s"],
                            k=int(bc["branch_k"]), seed=zlib.crc32(f"{tag}:branch:{kind}:{j}".encode()), alt=kind,
                            a=alt["a"], b=alt["b"])
                t0 = time.perf_counter()
                res = runner.pair(m, ds, spec)
                delta, w = label(res, bc["branch_score"], **({"phi": phi} if phi is not None else {}))
                out.append({"branch": True, "kind": kind, "tag": tag, "k": j, "entry_index": -1, "side": L.side,
                            "tick": tick, "phase": getattr(res, "phase", None) or phase_of(tick), "p_gate": p,
                            "p_play": getattr(res, "p_play", None), "hold_s": None, "delta": float(delta),
                            "weight": float(w), "wall_s": time.perf_counter() - t0,
                            "alt": {"a": list(alt["a"]), "b": list(alt["b"]), **alt["info"]},
                            "row": {**branch_row(L, allowed, p, L.cfg["T"], stalled), **alt["row"]}})
                if emit is not None:
                    emit(out[-1])
            if targets and tick >= targets[0] and not stalled and d["why"] in ("gate", "wait") and lo <= p <= hi:
                targets.pop(0)
                j = len(out)
                spec = Spec(hold_s=float(rng.choice(bc["branch_hold_s"])), hold_tau=float(bc["branch_hold_tau"]),
                            horizon_s=bc["branch_horizon_s"], k=int(bc["branch_k"]),
                            seed=zlib.crc32(f"{tag}:branch:{j}".encode()))
                t0 = time.perf_counter()
                res = runner.pair(m, ds, spec)
                delta, w = label(res, bc["branch_score"], **({"phi": phi} if phi is not None else {}))
                out.append({"branch": True, "kind": "hold", "tag": tag, "k": j, "entry_index": -1, "side": L.side,
                            "tick": tick,
                            "phase": getattr(res, "phase", None) or phase_of(tick), "p_gate": p,
                            "p_play": getattr(res, "p_play", None), "hold_s": spec.hold_s, "delta": float(delta),
                            "weight": float(w), "wall_s": time.perf_counter() - t0,
                            "row": branch_row(L, allowed, p, L.cfg["T"], stalled)})
                if emit is not None:
                    emit(out[-1])
        for s in ds:
            if id(s) not in dec:
                dec[id(s)] = side_decide(s)
        for s in ds:
            p, d = dec[id(s)][:2]
            s.apply(p, d)


def branch_jobs(make_env, learner, opps: dict, jobs, lcfg: dict, bc: dict, update: int,
                on_skip=None, skip=(), sync=(lambda: True), emit=None, phi=None) -> tuple[list[dict], dict]:
    """Branch matches IN ORDER until ``sync()`` returns False or the list ends: one ``play_branch_match`` per (i, league
    spec, k), the learner under ``lcfg`` (live rule, unrecorded) with the PPO rollout's per-match seeds
    (``rollout_jobs``' overrides), the spec's real opponent ``opps[id] = (policy, cfg)`` (``run_selfplay_batch``'s
    format; also what BranchRunner gets). ``branch_score: phi``: T2's frozen phi model from ``branch_phi_ckpt``
    (REPO-relative or absolute), loaded here unless passed. -> (all samples, {matches started, pairs, stopped})."""
    impl = branch_impl()
    if phi is None and bc["branch_score"] == "phi":
        from pipeline.branch_score import load_phi
        phi = load_phi(str(REPO / bc["branch_phi_ckpt"]), lcfg["device"])
    runner = impl[1](make_env, learner, opps, lcfg, device=lcfg["device"])
    env, out, n = make_env(), [], 0
    stopped = False
    for i, spec, k, over in rollout_jobs(jobs, update):
        if not sync():
            stopped = True
            break
        opp, ocfg = opps[spec["opp"]["id"]]
        try:
            m = E.SelfPlayMatch(env, spec, k, {**lcfg, **over, "entry_index": i},
                                {**ocfg, **{x: v for x, v in over.items() if x != "obs_seed"}, "entry_index": i},
                                learner, opp)
        except skip as exc:
            if on_skip:
                on_skip(spec, exc)
            continue
        n += 1
        live = [True]

        def sync_once():
            live[0] = sync()
            return live[0]
        out += play_branch_match(m, runner, impl, bc, phi, sync_once, emit)
        if not live[0]:
            stopped = True
            break
    return out, {"matches": n, "pairs": len(out), "stopped": stopped}


def branch_stats(samples: list[dict], min_abs: float, kinds=None) -> dict:
    """Per-update branch monitors: samples emitted, dropped (|delta| < min_abs), and over the KEPT samples n, share
    HOLD-better (delta < 0; for the R4 kinds: B-better) and mean delta -- overall and by phase; with ``kinds`` other
    than hold-only also ``by_kind`` (emitted, n, b_better_share, mean_delta)."""
    kept = [s for s in samples if abs(s["delta"]) >= min_abs]

    def agg(ss):
        d = np.array([s["delta"] for s in ss], dtype=np.float64)
        return {"n": len(ss), "hold_better_share": float((d < 0).mean()) if len(d) else None,
                "mean_delta": float(d.mean()) if len(d) else None}
    out = {"emitted": len(samples), "dropped": len(samples) - len(kept), **agg(kept),
           "by_phase": {ph: agg([s for s in kept if s["phase"] == ph]) for ph in sorted({s["phase"] for s in samples})},
           "pair_wall_s_mean": float(np.mean([s["wall_s"] for s in samples])) if samples else None}
    if kinds is not None and list(kinds) != ["hold"]:
        kd = (lambda s: s.get("kind", "hold"))
        out["by_kind"] = {}
        for k in kinds:
            a = agg([s for s in kept if kd(s) == k])
            out["by_kind"][k] = {"emitted": sum(kd(s) == k for s in samples), "n": a["n"],
                                 "b_better_share": a["hold_better_share"], "mean_delta": a["mean_delta"]}
    return out


def branch_batch(samples: list[dict], min_abs: float) -> Optional[dict]:
    """Kept samples (|delta| >= min_abs, all of ONE kind) -> numpy batch: the rows stacked by ``Match._traj_arrays``
    (the PPO batch's own layout) + ``target`` (1.0 = A better, delta > 0 -- hold kind: PLAY; 0.0 = B, ties included)
    and ``weight``; card rows add slot_a / slot_b, xbow_class rows cls_a [N, 2304] bool. None if empty."""
    from types import SimpleNamespace
    kept = [s for s in samples if abs(s["delta"]) >= min_abs]
    if not kept:
        return None
    rows = [s["row"] for s in kept]
    B = E.Match._traj_arrays(SimpleNamespace(traj=rows))
    B["target"] = np.array([float(s["delta"] > 0) for s in kept], dtype=np.float64)
    B["weight"] = np.array([s["weight"] for s in kept], dtype=np.float64)
    if "slot_a" in rows[0]:
        B["slot_a"] = np.array([r["slot_a"] for r in rows], dtype=np.int64)
        B["slot_b"] = np.array([r["slot_b"] for r in rows], dtype=np.int64)
    if "cls_a" in rows[0]:
        B["cls_a"] = np.stack([r["cls_a"] for r in rows]).astype(bool)
    return B


def branch_terms(model, Bb: dict, idx, tau: float, T: float, kind: str = "hold") -> tuple[torch.Tensor, torch.Tensor]:
    """Rows ``idx``: (x, weight x BCE(sigmoid(x), target)), x > 0 = prefer A:
      hold        x = (z - logit(tau)) / T -- the live gate's parameterisation (play iff x > 0), recomputed by
                  ``policy_terms`` exactly as the PPO gate term
      card        x = z_card[slot_a] - z_card[slot_b] (the card head's logits at the training T, ``policy_terms``' hand-masked
                  card log-softmax: the normaliser cancels)
      xbow_class  x = logsumexp(cell logits over the A class) - logsumexp(over the B class), for the row's X-Bow slot."""
    if kind == "hold":
        x = policy_terms(model, Bb, idx, tau, T)["x"]
    elif kind == "card":
        cl = policy_terms(model, Bb, idx, tau, T)["card_lp"]          # lead ruling: the training T, like hold
        x = cl.gather(1, Bb["slot_a"][idx].unsqueeze(1)).squeeze(1) - cl.gather(1, Bb["slot_b"][idx].unsqueeze(1)).squeeze(1)
    elif kind == "xbow_class":
        if not bool(Bb["played"][idx].all()):
            raise ValueError("xbow_class rows must be played rows (the X-Bow slot's cell logits)")
        lp, m = policy_terms(model, Bb, idx, tau, T)["cell_lp"], Bb["cls_a"][idx]   # lead ruling: training T
        x = torch.logsumexp(lp.masked_fill(~m, float("-inf")), -1) - torch.logsumexp(lp.masked_fill(m, float("-inf")), -1)
    else:
        raise ValueError(f"unknown branch kind {kind!r}")
    return x, Bb["weight"][idx] * Fn.binary_cross_entropy_with_logits(x, Bb["target"][idx], reduction="none")


def branch_step(model, opt, Bb: dict, cfg: dict, coef) -> dict:
    """ONE optimizer step on sum over kinds of coef_k x mean_i weight_i loss_i over the whole replay buffer (gradients
    accumulated over chunks of ``minibatch`` rows; clipped at ``grad_clip`` like PPO's), after the PPO epochs. ``Bb`` =
    one hold batch + a scalar ``coef`` (opt3), or {kind: batch} + {kind: coef} (R4; each kind's loss is ITS mean).
    ``opt`` is the branch's OWN Adam (``Learner.branch_opt``) -- all kinds share it and its one step. Adam divides by the
    gradient's running RMS, so the coefs barely scale the step: they are loss weights (they set the kinds' RELATIVE
    gradient share and where ``grad_clip`` bites; all 0 = no gradient = no step); the step size is ``branch_lr``. ->
    monitors: buffer rows, BCE (the unscaled weighted mean over all rows) before / after, mean and max |dP| on the
    buffer rows with P = sigmoid(x) (hold: P(play); card / xbow_class: P(prefer A)), grad norm; ``skipped`` (no step
    taken) on a non-finite loss or gradient norm; a non-hold kind adds ``by_kind`` {rows, bce_before, bce_after}."""
    groups = [("hold", Bb, float(coef))] if "target" in Bb else [(k, b, float(coef[k])) for k, b in Bb.items()]
    mb = int(cfg["minibatch"])
    groups = [(k, b, c, [torch.arange(s, min(s + mb, len(b["target"])), device=b["target"].device)
                         for s in range(0, len(b["target"]), mb)]) for k, b, c in groups]
    N = sum(len(b["target"]) for _, b, _, _ in groups)

    def probe():
        with torch.no_grad():
            per = {}
            for k, b, _, chunks in groups:
                xs, ls = zip(*(branch_terms(model, b, i, cfg["tau"], cfg["T"], k) for i in chunks))
                per[k] = (torch.cat(xs), torch.cat(ls))
            return (torch.sigmoid(torch.cat([v[0] for v in per.values()])),
                    float(torch.cat([v[1] for v in per.values()]).mean()), {k: float(v[1].mean()) for k, v in per.items()})
    p0, bce0, k0 = probe()
    opt.zero_grad(set_to_none=True)
    for k, b, c, chunks in groups:
        n = len(b["target"])
        for i in chunks:
            (c * branch_terms(model, b, i, cfg["tau"], cfg["T"], k)[1].sum() / n).backward()
    gn = torch.nn.utils.clip_grad_norm_(model.parameters(), float(cfg["grad_clip"]))
    out = {"rows": N, "bce_before": bce0, "grad_norm": float(gn), "skipped": None, "p_play_mean": float(p0.mean())}
    multi = [k for k, *_ in groups] != ["hold"]
    if not (math.isfinite(bce0) and torch.isfinite(gn)):
        opt.zero_grad(set_to_none=True)
        out.update({"skipped": f"non-finite bce {bce0} / grad norm {float(gn)}", "bce_after": bce0,
                    "dp_abs_mean": 0.0, "dp_abs_max": 0.0})
        if multi:
            out["by_kind"] = {k: {"rows": len(b["target"]), "bce_before": k0[k], "bce_after": k0[k]}
                              for k, b, *_ in groups}
        return out
    opt.step()
    p1, bce1, k1 = probe()
    dp = (p1 - p0).abs()
    out.update({"bce_after": bce1, "dp_abs_mean": float(dp.mean()), "dp_abs_max": float(dp.max())})
    if multi:
        out["by_kind"] = {k: {"rows": len(b["target"]), "bce_before": k0[k], "bce_after": k1[k]} for k, b, *_ in groups}
    return out


def branch_batches(buf: list[dict], dev) -> dict:
    """The replay buffer -> {kind: device batch} in BRANCH_KIND_KEYS order (one hold batch = opt3's exactly)."""
    out = {}
    for k in BRANCH_KIND_KEYS:
        b = branch_batch([x for x in buf if x.get("kind", "hold") == k], 0.0)
        if b is not None:
            out[k] = to_device(b, dev)
    return out


def value_scalar(logits: torch.Tensor) -> torch.Tensor:
    """The critic V(s) in [-1, 1] from the EXISTING value head: its 7 classes are the crown difference (mine - theirs)
    -3..3 at class diff + 3 (train_s1.Rows), from the side the observation belongs to. V = P(diff > 0) - P(diff < 0)
    = P(win) - P(loss), the expectation of the +1 / -1 / 0 terminal reward; float64 like the policy terms."""
    p = torch.softmax(logits.double(), dim=-1)
    return p[..., 4:].sum(-1) - p[..., :3].sum(-1)


def terminal_rewards(n_rows, outcomes) -> list[np.ndarray]:
    """Per-row step reward of each match: 0 on every row, ``reward(outcome)`` on its LAST contributing row (the
    outcome is the learner side's own, e1_eval ``_outcome``, whichever side it played). R2's shaping term adds onto
    this array (``F_t`` per row) without changing anything else."""
    out = []
    for n, o in zip(n_rows, outcomes):
        r = np.zeros(int(n))
        if n:
            r[-1] = reward(o)
        out.append(r)
    return out


def gae(r, v, match, gamma, lam: float) -> tuple[np.ndarray, np.ndarray]:
    """GAE(gamma, lambda) over rows grouped in contiguous time-ordered matches (``match`` id per row): delta_t = r_t +
    gamma_t V_{t+1} - V_t with V after a match's last row = 0 (terminal); A_t = delta_t + gamma_t lambda A_{t+1} within
    the match. -> (A, returns = A + V); lambda = 1 makes the returns the discounted returns-to-go. One step = one
    contributing decision row (rows collate drops are skipped, not discounted). ``gamma``: one float (per kept row,
    the default) or a per-row array, gamma_t = the discount from row t to the next row of its match (``row_gammas``;
    ignored on a match's last row)."""
    r, v, m = (np.asarray(x, dtype=np.float64) for x in (r, v, match))
    g = np.broadcast_to(np.asarray(gamma, dtype=np.float64), r.shape)
    A = np.zeros(len(r))
    nxt_v, nxt_a = 0.0, 0.0
    for t in range(len(r) - 1, -1, -1):
        if t == len(r) - 1 or m[t + 1] != m[t]:
            nxt_v, nxt_a = 0.0, 0.0
        d = r[t] + g[t] * nxt_v - v[t]
        A[t] = nxt_a = d + g[t] * lam * nxt_a
        nxt_v = v[t]
    return A, A + v


def row_gammas(ticks, gamma_tick: float) -> np.ndarray:
    """``gae_gamma_unit: tick``: one match's per-kept-row discount gamma_t = gamma_tick ** (tick_{t+1} - tick_t), the
    decision ticks of consecutive KEPT rows (time order); the last row's entry (1.0) is never used (V = Phi = 0
    after it). Default 0.99994: league1c (144 updates) kept 279 rows over ~4330 ticks a match, 15.5 ticks a row, and
    0.99994^15.5 = 0.99907 ~ the row unit's 0.999 (horizon 1/(1-gamma) ~ 16.7k ticks ~ 1075 rows vs 1000 rows; a whole
    match 0.99994^4330 = 0.77 vs 0.999^279 = 0.76)."""
    dt = np.diff(np.asarray(ticks, dtype=np.int64))
    if (dt <= 0).any():
        raise ValueError(f"kept-row ticks must strictly increase, got gaps {dt[dt <= 0][:5].tolist()}")
    return np.append(float(gamma_tick) ** dt.astype(np.float64), 1.0)


def explained_variance(v, ret) -> Optional[float]:
    """1 - Var(ret - v) / Var(ret); None when Var(ret) == 0."""
    v, ret = np.asarray(v, dtype=np.float64), np.asarray(ret, dtype=np.float64)
    var = float(ret.var())
    return None if var == 0 else 1.0 - float((ret - v).var()) / var


def rl_obs_seed(tag: str, g: int, update: int) -> int:
    """rl_plan.md 'Behaviour policy': the live_view RNG of rollout g of an entry at an update."""
    return zlib.crc32(f"{tag}:obs:{g}:{update}".encode())


def match_weights(n_rows) -> list[np.ndarray]:
    """Per-row weights: match i's n_i rows each get 1/(n_i M), M = matches with rows -> every match sums to 1/M."""
    n = [int(k) for k in n_rows]
    M = sum(1 for k in n if k > 0)
    return [np.full(k, 1.0 / (k * M)) if k else np.zeros(0) for k in n]


LEASH_MODES = ("cell", "max")


def leash_kl(upd: dict, mode: str) -> tuple[float, str]:
    """The KL ``adapt_beta`` steers on (owner ruling 2026-09-25, T12b), from ``ppo_update``'s monitors (None = 0.0):
    ``cell`` = KL_cell (the S1 rule, unchanged); ``max`` = max(KL_gate, KL_card, KL_cell). -> (value, the head that
    drove it; a tie goes to the first of gate, card, cell). A config without the key is ``cell`` (Learner)."""
    kls = {h: float(upd.get(f"kl_{h}") or 0.0) for h in ("gate", "card", "cell")}
    if mode == "cell":
        return kls["cell"], "cell"
    if mode != "max":
        raise ValueError(f"leash {mode!r} not in {LEASH_MODES}")
    h = max(kls, key=kls.get)
    return kls[h], h


def adapt_beta(beta: float, kl_cell: float, target: float, lo: float = 0.03, hi: float = 3.0) -> float:
    """E1 3.4: x2 if KL_cell > 1.5 target, /2 if < target / 1.5, clamp [lo, hi]."""
    if kl_cell > 1.5 * target:
        beta *= 2.0
    elif kl_cell < target / 1.5:
        beta /= 2.0
    return float(min(max(beta, lo), hi))


def hard_stop_reason(pa: dict, init: dict, cfg: dict) -> Optional[str]:
    """plan diff 3 HARD stop (single): cell or card < init - 3 pp, or gate_bal_acc < init - 0.05."""
    if pa["cell_half_top1"] < init["cell_half_top1"] - cfg["hard_cell_pp"] / 100:
        return f"HARD pro agreement: cell {pa['cell_half_top1']:.4f} < init {init['cell_half_top1']:.4f} - {cfg['hard_cell_pp']} pp"
    if pa["card_top1"] < init["card_top1"] - cfg["hard_card_pp"] / 100:
        return f"HARD pro agreement: card {pa['card_top1']:.4f} < init {init['card_top1']:.4f} - {cfg['hard_card_pp']} pp"
    if pa["gate_bal_acc"] < init["gate_bal_acc"] - cfg["hard_gate_bal"]:
        return f"HARD pro agreement: gate_bal_acc {pa['gate_bal_acc']:.4f} < init {init['gate_bal_acc']:.4f} - {cfg['hard_gate_bal']}"
    return None


def tripwire_reason(pa: dict, init: dict, latest_delta_pp: Optional[float], cfg: dict) -> Optional[str]:
    """plan diff 3 tripwire: BOTH cell < init - 1 pp AND the latest held-out screen paired delta <= 0 pp.
    ``latest_delta_pp`` None (no screen yet) never trips -- the caller runs a screen first when the cell leg holds."""
    cell_low = pa["cell_half_top1"] < init["cell_half_top1"] - cfg["tripwire_cell_pp"] / 100
    if cell_low and latest_delta_pp is not None and latest_delta_pp <= 0:
        return (f"pro-agreement tripwire: cell {pa['cell_half_top1']:.4f} < init {init['cell_half_top1']:.4f} - "
                f"{cfg['tripwire_cell_pp']} pp AND latest screen paired delta {latest_delta_pp:+.1f} pp <= 0")
    return None


def ghost_refused_limit(base: Optional[float], x: float = 2.0) -> Optional[float]:
    """E1 4.2.3 stop limit on ghost REFUSED plays per match: max(x * init, init + 1.0) -- rl_gate's floor, so a
    near-zero init value is not 'doubled' by a single refusal."""
    return None if base is None else max(x * base, base + 1.0)


def screen_record(r: dict) -> dict:
    """What a held-out screen keeps per (tag, k) match: the outcome value (rl_gate.WIN_VAL) plus the E1 4.2 exploit
    fields, so the init and every candidate screen are compared on the SAME matches."""
    from pipeline.rl_gate import val
    return {"v": val(r), "win": r["outcome"] == "win", "won_after_script": bool(r["won_after_script"]),
            "ghost_delivered": int(r["ghost_delivered"]), "ghost_refused": int(r["ghost_refused"])}


def exploit_values(recs: list[dict]) -> dict:
    """E1 4.2.1-3 over a list of ``screen_record``s: outlived-the-script share of wins, <= 10-ghost-delivered share of
    wins (None without wins), ghost refused plays per match."""
    wins = [r for r in recs if r["win"]]
    share = (lambda k: sum(1 for r in wins if k(r)) / len(wins) if wins else None)
    return {"outlived_win_share": share(lambda r: r["won_after_script"]),
            "low_delivered_win_share": share(lambda r: r["ghost_delivered"] <= 10),
            "ghost_refused_per_match": sum(r["ghost_refused"] for r in recs) / len(recs) if recs else None}


def exploit_reasons(init: dict, cand: dict, cfg: dict) -> list[str]:
    """Screen-level exploit guards (single occurrence, lead ruling L68 after the rl30 false alarm): the candidate's
    values vs the INIT's on the same held-out matches. outlived share > init + outlived_pp; <= 10-delivered share >
    init + low_delivered_pp; refused/match > max(ghost_refusal_x * init, init + 1.0)."""
    out = []
    for key, margin, what in (("outlived_win_share", cfg["outlived_pp"] / 100, "outlived-the-script win share"),
                              ("low_delivered_win_share", cfg["low_delivered_pp"] / 100, "<=10-delivered win share")):
        c, i = cand.get(key), init.get(key)
        if c is not None and i is not None and c > i + margin:
            out.append(f"held-out {what} {c:.3f} > init {i:.3f} + {margin:.2f} on the same matches")
    c, lim = cand.get("ghost_refused_per_match"), ghost_refused_limit(init.get("ghost_refused_per_match"),
                                                                      float(cfg["ghost_refusal_x"]))
    if c is not None and lim is not None and c > lim:
        out.append(f"held-out ghost refused/match {c:.2f} > limit {lim:.2f} = max({cfg['ghost_refusal_x']}x, +1.0) of "
                   f"init {init['ghost_refused_per_match']:.2f} on the same matches")
    return out


GUARD_BASE_KEYS = ("plays_per_min",)
GUARD_CONSEC_KEYS = ("plays", "kl", "entropy_gate", "entropy_card", "entropy_cell")


class Guards:
    """The per-update stop rules with state (consecutive counters, the update-0 plays/min baseline, the latest screen
    delta); ``s`` is plain JSON so it rides in the checkpoint's ``rl`` dict and --resume continues the counters. The
    exploit guards are NOT here (they compare held-out screens, ``exploit_reasons``): a train batch samples different
    ghosts every update, so a train-batch value vs update 0 measures opponent sampling, not the policy (rl30 false
    alarm, L68). State written by the older code (EMAs, exploit baselines, ghost_refused_limit) loads; those keys are
    dropped."""

    def __init__(self, cfg: dict, state: Optional[dict] = None):
        self.cfg = cfg
        st = state or {}
        base = st.get("base")
        self.s = {"base": {k: base.get(k) for k in GUARD_BASE_KEYS} if base else None,
                  "consec": {k: v for k, v in (st.get("consec") or {}).items() if k in GUARD_CONSEC_KEYS},
                  "latest_screen_delta_pp": st.get("latest_screen_delta_pp")}

    def _consec(self, name: str, cond: bool) -> bool:
        c = self.s["consec"]
        c[name] = c.get(name, 0) + 1 if cond else 0
        return c[name] >= int(self.cfg["stop_consecutive"])

    def set_baselines(self, mon: dict) -> None:
        """E1 3.6 rule 1: the update-0 behaviour plays/min (a property of the policy's gate, not of the sampled ghosts)."""
        self.s["base"] = {k: mon.get(k) for k in GUARD_BASE_KEYS}

    def after_update(self, mon: dict, beta_used: float, kl_cell: float, kl_gate: float,
                     ent: Optional[dict] = None, ent_init: Optional[dict] = None) -> list[str]:
        cfg, base, out = self.cfg, self.s["base"] or {}, []
        # E1 3.4 l.280-281: a head's entropy (policy, epoch 0) below entropy_floor_frac x the INIT's on the same rows
        for h in ("gate", "card", "cell"):
            e, e0 = (ent or {}).get(h), (ent_init or {}).get(h)
            low = e is not None and e0 is not None and e < float(cfg["entropy_floor_frac"]) * e0
            if self._consec(f"entropy_{h}", low):
                out.append(f"{h} entropy {e:.4f} < {cfg['entropy_floor_frac']} x init's {e0:.4f} on the same rows for "
                           f"{cfg['stop_consecutive']} updates")
        ppm, b = mon.get("plays_per_min"), base.get("plays_per_min")
        if ppm is not None and b:
            r = ppm / b
            if self._consec("plays", not (cfg["plays_lo"] <= r <= cfg["plays_hi"])):
                out.append(f"plays/min {ppm:.2f} = {r:.2f}x the update-0 {b:.2f} outside "
                           f"[{cfg['plays_lo']}, {cfg['plays_hi']}] for {cfg['stop_consecutive']} updates")
        at_clamp = beta_used >= float(cfg["beta_max"]) - 1e-12
        if self._consec("kl", at_clamp and (kl_cell > cfg["kl_cell_stop"] or kl_gate > cfg["kl_gate_stop"])):
            out.append(f"KL_cell {kl_cell:.3f} / KL_gate {kl_gate:.3f} over {cfg['kl_cell_stop']} / {cfg['kl_gate_stop']} "
                       f"with beta at its {cfg['beta_max']} clamp for {cfg['stop_consecutive']} updates")
        return out

    def screen(self, delta_pp: Optional[float], ci_hi_pp: Optional[float]) -> Optional[str]:
        """E1 3.6 rule 4 with the lead's noise ruling (single occurrence): the entry-clustered paired delta <= -10 pp
        AND its bootstrap 95% CI upper bound < 0. The point estimate also feeds the tripwire. ``delta_pp`` None (no
        paired match) = no screen: the latest delta becomes None (a stale earlier delta must not feed the tripwire),
        never a stop."""
        if delta_pp is None:
            self.s["latest_screen_delta_pp"] = None
            return None
        self.s["latest_screen_delta_pp"] = float(delta_pp)
        if delta_pp <= self.cfg["screen_stop_pp"] and ci_hi_pp < 0:
            return (f"held-out screen paired delta {delta_pp:+.1f} pp <= {self.cfg['screen_stop_pp']} pp with 95% CI "
                    f"upper bound {ci_hi_pp:+.1f} pp < 0")
        return None


def rollout_jobs(jobs, update: int) -> list[tuple]:
    """(entry_index, entry, g) -> ``run_batch`` jobs carrying their per-match cfg overrides (4th element): the
    behaviour seed index and the obs seed are per (entry, g), not per batch (test_rl_royale.TestRolloutJobsSeeds)."""
    return [(i, entry, g, {"rollout_index": int(g), "update": int(update),
                           "obs_seed": rl_obs_seed(str(entry["tag"]), int(g), int(update))}) for i, entry, g in jobs]


# ------------------------------------------------------------------------------------------------------
# league (L68 T12b): opponents, decks, matchups, monitors -- pure, tested offline (pipeline/tests/test_league.py)
# ------------------------------------------------------------------------------------------------------
OPP_CATS = ("latest", "older", "init", "s1")
DECK_BUCKETS = ("icebow", "head", "tail")
HEAD_DECKS = 20                     # "head" bucket = the 20 most-played loadable census decks (~30% of census draws)


def league_decks(path: Path) -> list[dict]:
    """loadable_decks.json's census decks (census order) -> [{name, engine, sides, bucket}], icebow REMOVED: icebow
    enters only through ``league_icebow_share`` (``sample_deck``), so its share is exactly that number."""
    ice = sorted(n.split("@")[0] for n in E.ICEBOW_ENGINE_DECK)
    out = []
    for x in json.loads(Path(path).read_text(encoding="utf-8"))["decks"]:
        if sorted(x["engine"]) == ice:
            continue
        out.append({"name": f"r{x['rank']}", "engine": list(x["engine"]), "sides": int(x["sides"]),
                    "bucket": "head" if len(out) < HEAD_DECKS else "tail"})
    return out


ICEBOW_DECK = {"name": "icebow", "engine": list(E.ICEBOW_ENGINE_DECK), "sides": None, "bucket": "icebow"}


def deck_weights(sides, alpha: float, floor: float) -> np.ndarray:
    """Census-frequency tempering with a floor: w_i = max(sides_i ** alpha, floor * mean_j(sides_j ** alpha)),
    normalised to sum 1."""
    w = np.asarray(sides, dtype=np.float64) ** float(alpha)
    w = np.maximum(w, float(floor) * w.mean())
    return w / w.sum()


def sample_deck(rng: np.random.Generator, census: list[dict], p: np.ndarray, icebow_share: float) -> dict:
    """icebow with probability ``icebow_share``, else a census deck drawn with ``p`` (``deck_weights``)."""
    if rng.random() < float(icebow_share):
        return ICEBOW_DECK
    return census[int(rng.choice(len(census), p=p))]


def validate_league(cfg: dict) -> None:
    """The league keys, checked before anything runs (SystemExit with the offending key and value)."""
    bad = []
    for k in ("league_snapshot_every", "league_snapshot_keep"):
        v = cfg.get(k)
        if not (isinstance(v, int) and not isinstance(v, bool) and v >= 1):
            bad.append(f"{k} must be an integer >= 1, got {v!r}")
    mix = cfg.get("league_mix")
    if not isinstance(mix, dict) or set(mix) - set(OPP_CATS):
        bad.append(f"league_mix must be a mapping over {OPP_CATS}, got {mix!r}")
    else:
        vals = {c: mix.get(c, 0.0) for c in OPP_CATS}
        if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or v < 0
               for v in vals.values()):
            bad.append(f"league_mix weights must be finite numbers >= 0, got {mix!r}")
        elif sum(vals.values()) <= 0:
            bad.append(f"league_mix weights must have a positive sum, got {mix!r}")
    sh = cfg.get("league_icebow_share")
    if not (isinstance(sh, (int, float)) and not isinstance(sh, bool) and 0.0 <= sh <= 1.0):
        bad.append(f"league_icebow_share must be a number in [0, 1], got {sh!r}")
    lsh = cfg.get("league_learner_icebow_share")
    if lsh is not None and not (isinstance(lsh, (int, float)) and not isinstance(lsh, bool) and 0.0 <= lsh <= 1.0):
        bad.append(f"league_learner_icebow_share must be null or a number in [0, 1], got {lsh!r}")
    for k in ("league_deck_alpha", "league_deck_floor"):
        v = cfg.get(k)
        if not (isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0):
            bad.append(f"{k} must be a finite number >= 0, got {v!r}")
    if cfg.get("league_opp_policy") not in ("live", "sample"):
        bad.append(f"league_opp_policy must be live or sample, got {cfg.get('league_opp_policy')!r}")
    if bad:
        raise SystemExit("bad league config: " + "; ".join(bad))


def opponent_mix(n_snaps: int, mix: dict) -> dict:
    """The opponent categories available with ``n_snaps`` snapshots and their probabilities (``mix`` renormalised):
    ``latest`` always (the newest snapshot, or the init before the first), ``older`` from 2 snapshots on, ``init``,
    ``s1``; a category with weight 0 is left out."""
    ok = [c for c in OPP_CATS if float(mix.get(c, 0.0)) > 0 and (c != "older" or n_snaps >= 2)]
    tot = sum(float(mix[c]) for c in ok)
    return {c: float(mix[c]) / tot for c in ok}


def sample_opponent(rng: np.random.Generator, snaps: list[dict], mix: dict, init_path: str, s1_path: str) -> dict:
    """-> {id, cat, type, path}: ``type`` (init / snapshot / s1) is what the monitors group by."""
    m = opponent_mix(len(snaps), mix)
    cats = list(m)
    cat = cats[int(rng.choice(len(cats), p=[m[c] for c in cats]))]
    if cat == "s1":
        return {"id": "s1", "cat": cat, "type": "s1", "path": str(s1_path)}
    if cat == "init" or (cat == "latest" and not snaps):
        return {"id": "init", "cat": cat, "type": "init", "path": str(init_path)}
    sn = snaps[-1] if cat == "latest" else snaps[int(rng.integers(len(snaps) - 1))]
    return {"id": sn["id"], "cat": cat, "type": "snapshot", "path": sn["path"]}


def sample_matchups(rng: np.random.Generator, n: int, update: int, snaps: list[dict], cfg: dict, census: list[dict],
                    p: np.ndarray) -> list[dict]:
    """``n`` league matchups (one LOO group each): opponent (``sample_opponent``), learner deck (``sample_deck``),
    opponent deck (the same rule; ALWAYS icebow for the S1 specialist, the only deck it can play), learner side
    (uniform) and the env's deal seed -- drawn in that order per matchup from ``rng`` (the learner's own, so resume
    continues the stream). ``league_learner_icebow_share`` (optional) replaces ``league_icebow_share`` for the
    learner's deck only; the draw order is the same either way (an icebow hit skips the census ``choice``)."""
    out = []
    lshare = cfg.get("league_learner_icebow_share")
    lshare = cfg["league_icebow_share"] if lshare is None else lshare      # null = the shared rule (league1/1b)
    for i in range(int(n)):
        opp = sample_opponent(rng, snaps, cfg["league_mix"], cfg["init"], cfg["league_specialist"])
        ld = sample_deck(rng, census, p, lshare)
        od = ICEBOW_DECK if opp["type"] == "s1" else sample_deck(rng, census, p, cfg["league_icebow_share"])
        out.append({"tag": f"sp{int(update):04d}_{i:02d}", "opp": opp,
                    "learner_deck": ld["engine"], "learner_deck_name": ld["name"], "learner_bucket": ld["bucket"],
                    "opp_deck": od["engine"], "opp_deck_name": od["name"],
                    "learner_side": int(rng.integers(2)), "seed": int(rng.integers(2 ** 31 - 1))})
    return out


def league_monitors(results: list[dict]) -> dict:
    """Per-update self-play monitors: learner W/L/D and win rate by opponent type and by learner-deck bucket, draws,
    learner and opponent plays/min."""
    def wdl(rs):
        n = len(rs)
        w, l_ = sum(r["outcome"] == "win" for r in rs), sum(r["outcome"] == "loss" for r in rs)
        return {"n": n, "W": w, "L": l_, "D": n - w - l_, "winrate": w / n if n else None}
    minutes = sum(r["seconds"] for r in results) / 60.0
    return {"by_opp": {t: wdl([r for r in results if r["league"]["opp"]["type"] == t]) for t in ("init", "snapshot", "s1")},
            "by_deck": {b: wdl([r for r in results if r["league"]["learner_bucket"] == b]) for b in DECK_BUCKETS},
            "draws": sum(r["outcome"] == "draw" for r in results),
            "plays_per_min": sum(r["plays_attempted"] for r in results) / minutes if minutes else None,
            "opp_plays_per_min": sum(r["opp_side"]["plays_attempted"] for r in results) / minutes if minutes else None}


def _py(x):
    """numpy scalars / tuples -> plain JSON types (the checkpoint must load with torch.load(weights_only=True))."""
    return json.loads(json.dumps(x, default=lambda o: o.item() if hasattr(o, "item") else str(o)))


# ------------------------------------------------------------------------------------------------------
# trajectories -> one batch
# ------------------------------------------------------------------------------------------------------
def collate(results: list[dict], adv_clip: float = 2.0, advantage: str = "match_loo",
            shaping: Optional[dict] = None, gamma_tick: Optional[float] = None,
            gae_terminal_gap: bool = False) -> tuple[dict, dict]:
    """Rollout result records (each with ``traj`` = ``Match._traj_arrays``) -> numpy batch of the CONTRIBUTING rows
    (gate sampled or card/cell played) with per-row A, per-match weight w, match id, and the stored log-probs.
    ``advantage="gae"`` adds ``r_step`` (``terminal_rewards``, the UNSHAPED win/loss reward); A stays the LOO value
    until ``gae_batch`` replaces it. ``gamma_tick`` (gae only; ``gae_gamma_unit: tick``): + ``gamma_row`` per kept
    row (``row_gammas`` of the traj ``tick``), the discount GAE and the shaping use. ``shaping`` (gae only; {gamma,
    w_tower, w_crown}; gamma replaced by ``gamma_row`` under gamma_tick): + ``phi`` (Phi(s_t)) per kept row (the
    residual critic's base, ``gae_batch``), and the F / Phi stats under ``st["shaping"]``. ``gae_terminal_gap``
    discounts only the last reward by gamma_tick ** (end_tick - last_kept_tick); requires every result's end_tick."""
    if gae_terminal_gap:
        if advantage != "gae" or gamma_tick is None:
            raise ValueError("gae_terminal_gap true needs advantage gae AND gamma_tick (gae_gamma_unit tick)")
        for j, r in enumerate(results):
            if r.get("end_tick") is None:
                raise ValueError(f"gae_terminal_gap true needs end_tick for result {j}")
    groups: dict = {}
    for j, r in enumerate(results):
        groups.setdefault(r["entry_index"], []).append(j)
    A = np.zeros(len(results))
    mixed = 0
    for js in groups.values():
        R = [reward(results[j]["outcome"]) for j in js]
        A[js] = loo_advantage(R, adv_clip)
        mixed += int(len(set(R)) > 1)
    keep = []
    for r in results:
        t = r["traj"]
        keep.append((t["gate_sampled"] | t["played"]) if len(t["played"]) else np.zeros(0, dtype=bool))
    n_rows = [int(k.sum()) for k in keep]
    W = match_weights(n_rows)
    use = [j for j, n in enumerate(n_rows) if n]
    cat = (lambda f: np.concatenate([f(j) for j in use]))
    gen = bool(use) and "hand_card" in results[use[0]]["traj"]           # GenPolicy rows: + the identity arrays
    extra = E.GEN_IDENT_KEYS if gen else ()
    if gen and "unit_form" in results[use[0]]["traj"]:
        extra += E.GEN_V3_KEYS
    if gen and 'opp_cycle' in results[use[0]]['traj']:
        extra += E.GEN_V31_KEYS
    B = {k: cat(lambda j, k=k: results[j]["traj"][k][keep[j]]) for k in TRAJ_KEYS + extra}
    for k in ("lp_gate", "lp_card", "lp_cell"):
        B[k] = cat(lambda j, k=k: results[j]["traj"][k][keep[j]])
    B["lp_old"] = B["lp_gate"] + B["lp_card"] + B["lp_cell"]
    B["A"] = cat(lambda j: np.full(n_rows[j], A[j]))
    B["w"] = cat(lambda j: W[j])
    B["match"] = cat(lambda j: np.full(n_rows[j], j))
    sh = None
    if advantage == "gae":
        rs = terminal_rewards(n_rows, [r["outcome"] for r in results])
        if gae_terminal_gap:
            for j in use:
                gap = results[j]["end_tick"] - results[j]["traj"]["tick"][keep[j]][-1]
                if not np.isfinite(gap) or gap < 0:
                    raise ValueError(f"gae_terminal_gap: end_tick must be finite and >= last kept tick for result {j}")
                rs[j][-1] *= gamma_tick ** gap
        B["r_step"] = cat(lambda j: rs[j])
        gr = None
        if gamma_tick is not None:
            gr = {j: row_gammas(results[j]["traj"]["tick"][keep[j]], gamma_tick) for j in use}
            B["gamma_row"] = cat(lambda j: gr[j])
        if shaping is not None and shaping.get("mode") == "value_phi":     # lever C: the frozen net on B's inputs
            raw = np.asarray(shaping["phi_fn"](B), dtype=np.float64)
            off = dict(zip(use, np.cumsum([0] + [n_rows[j] for j in use])))
            sh = {}
            for j in use:
                if "tick" not in results[j]["traj"]:
                    raise ValueError("shaping value_phi needs the per-row tick (actor_cfg record_tick)")
                sh[j] = value_phi_rewards(raw[off[j]:off[j] + n_rows[j]], results[j]["traj"]["tick"][keep[j]],
                                          shaping if gr is None else {**shaping, "gamma": gr[j]})
            B["phi"] = cat(lambda j: sh[j]["phi"])
        elif shaping is not None:
            sh = {j: shaping_rewards(results[j]["traj"]["phi_state"][keep[j]],
                                     shaping if gr is None else {**shaping, "gamma": gr[j]}) for j in use}
            B["phi"] = cat(lambda j: sh[j]["phi"])
    elif shaping is not None or gamma_tick is not None:
        raise ValueError("shaping / gamma_tick need advantage gae")
    st = {"matches": len(results), "groups": len(groups), "mixed_groups": mixed,
          "mixed_group_share": mixed / max(len(groups), 1), "mean_abs_A": float(np.abs(A).mean()) if len(A) else 0.0,
          "rows": int(len(B["A"])), "rows_played": int(B["played"].sum()), "rows_gate": int(B["gate_sampled"].sum()),
          "decisions": int(sum(len(r["traj"]["played"]) for r in results))}
    if sh is not None and shaping.get("mode") == "value_phi":
        st["shaping"] = value_phi_stats([sh[j] for j in use], [reward(results[j]["outcome"]) for j in use])
    elif sh is not None:
        st["shaping"] = shaping_stats([sh[j] for j in use])
    return B, st


def value_phi_rewards(raw, ticks, shaping: dict) -> dict:
    """One match's lever-C shaping on its KEPT rows (time order): ``raw`` = the frozen net's P(win) - P(loss) per row,
    Phi_t = w_value x ``reward_shaping.trailing_mean`` of raw over [tick_t - window_ticks, tick_t] (causal), then the
    R2 machinery unchanged: F_t = gamma_t Phi_{t+1} - Phi_t with Phi = 0 after the last kept row (``gamma`` one float
    or the per-row ``gamma_row``). -> numpy F, Phi(s_t) per row (``phi``, the terminal 0 dropped) and ``raw``."""
    raw = np.atleast_1d(np.asarray(raw, dtype=np.float64))
    sm = RS.trailing_mean(raw, ticks, int(shaping["window_ticks"]))
    g = shaping["gamma"]
    out = RS.shaping_from_parts(sm.tolist(), [0.0] * len(sm), float(g) if np.ndim(g) == 0 else g,
                                (float(shaping["w_value"]), 0.0))
    return {"F": np.asarray(out["F"]), "phi": np.asarray(out["phi"][:-1]), "raw": raw}


def value_phi_stats(per_match: list[dict], outcomes: list[float]) -> dict:
    """Per-update lever-C monitors over every kept row: mean |F|, mean / max |Phi|, ``shaping_dominates`` (as R2),
    ``phi_step_std`` = std of Phi_{t+1} - Phi_t within matches (smoothed, weighted) and ``raw_step_std`` the same of the
    raw frozen V (L73 phi_eval: 0.121 raw, 0.036 at a 10 s trailing mean), and ``phi_end_corr`` = Pearson correlation
    over matches of Phi at the last kept row (the Phi_end proxy; Phi itself is 0 at the end) with the outcome reward
    (None below 2 matches or with a constant side)."""
    c = (lambda k: np.concatenate([m[k] for m in per_match]) if per_match else np.zeros(0))
    phi, F = c("phi"), c("F")
    steps = (lambda k: np.concatenate([np.diff(m[k]) for m in per_match]) if per_match else np.zeros(0))
    ps, rs_ = steps("phi"), steps("raw")
    end = np.array([m["phi"][-1] for m in per_match], dtype=np.float64)
    o = np.asarray(outcomes, dtype=np.float64)
    corr = float(np.corrcoef(end, o)[0, 1]) if len(end) >= 2 and end.std() > 0 and o.std() > 0 else None
    return {"mode": "value_phi", "mean_abs_F": float(np.abs(F).mean()) if len(F) else None,
            "mean_abs_phi": float(np.abs(phi).mean()) if len(phi) else None,
            "max_abs_phi": float(np.abs(phi).max()) if len(phi) else None,
            "shaping_dominates": float(np.abs(phi).mean()) if len(phi) else None,
            "phi_step_std": float(ps.std()) if len(ps) else None, "raw_step_std": float(rs_.std()) if len(rs_) else None,
            "phi_end_corr": corr, "matches": len(per_match), "rows": int(len(F))}


def shaping_rewards(phi_rows, shaping: dict) -> dict:
    """One match's R2 shaping on its KEPT rows (``reward_shaping.phi_record`` rows, time order): F_t = gamma Phi(s_{t+1})
    - Phi(s_t) with gamma = ``gae_gamma`` per kept row (the GAE step unit; or the per-row ``gamma_row`` array under
    ``gae_gamma_unit: tick``) and Phi = 0 after the last kept row (the match end). -> numpy F, its weighted terms
    tower / crown (F = tower + crown), and Phi(s_t) per row (``phi``, the terminal 0 dropped) with its weighted
    terms ``phi_tower`` / ``phi_crown``."""
    pt, pc = (np.atleast_1d(x).astype(np.float64) for x in RS.phi_parts(phi_rows))
    wt, wc = float(shaping["w_tower"]), float(shaping["w_crown"])
    g = shaping["gamma"]
    out = RS.shaping_from_parts(pt.tolist(), pc.tolist(), float(g) if np.ndim(g) == 0 else g, (wt, wc))
    return {"F": np.asarray(out["F"]), "tower": np.asarray(out["tower"]), "crown": np.asarray(out["crown"]),
            "phi": np.asarray(out["phi"][:-1]), "phi_tower": wt * pt, "phi_crown": wc * pc}


def shaping_stats(per_match: list[dict]) -> dict:
    """Per-update R2 monitors over every kept row: mean |F| and |Phi(s_t)|, each per term, and ``shaping_dominates``
    = mean |Phi| / 1.0 (the terminal reward's magnitude; plan 3b: -Phi(s_t) is the shaping part of every
    return-to-go, so a value above 0.5 means shaping is louder than half of winning)."""
    c = (lambda k: np.concatenate([m[k] for m in per_match]) if per_match else np.zeros(0))
    m = (lambda k: float(np.abs(c(k)).mean()) if len(c(k)) else None)
    st = {f"mean_abs_{k}": m(k) for k in ("F", "tower", "crown", "phi", "phi_tower", "phi_crown")}
    st["max_abs_phi"] = float(np.abs(c("phi")).max()) if len(c("phi")) else None
    st["shaping_dominates"] = None if st["mean_abs_phi"] is None else st["mean_abs_phi"] / 1.0
    st["rows"] = int(len(c("F")))
    return st


GEN_PA_KEYS = ("sc", "past", "y_xy", "y_hand_pos", "y_gate", "y_wait_card", "y_crowns", "y_card") + (
    "hand_card", "hand_form", "next_card", "next_form", "deck_card", "deck_form")      # what eval_gen.GenRows reads


def gen_v3val_arrays(path: Path, n: int = 0) -> tuple[dict, dict]:
    """The v3val rows (``v3val == 1``: S1's v3 VAL rows inside a dataset_gen npz) -> (arrays, meta), first ``n`` of them
    (0 = all), with ``tok``/``off`` re-packed for just those rows. Keys are loaded one at a time (the v1 set is 3.7M
    rows: tok ~0.9 GB, sc ~1 GB), so the full arrays never sit in memory together."""
    z = np.load(path, allow_pickle=False)
    idx = np.where(z["v3val"] == 1)[0]
    idx = idx[:n] if n else idx
    off = z["off"]
    lo, hi = off[idx], off[idx + 1]
    out = {"off": np.concatenate([[0], np.cumsum(hi - lo)]).astype(off.dtype)}
    out["tok"] = z["tok"][np.concatenate([np.arange(a, b) for a, b in zip(lo, hi)]).astype(np.int64)]
    for k in GEN_PA_KEYS:
        out[k] = z[k][idx]
    if "unit_form" in z:
        out["unit_form"] = z["unit_form"][np.concatenate([np.arange(a, b) for a, b in zip(lo, hi)]).astype(np.int64)]
        out["opp_past"] = z["opp_past"][idx]
    if 'opp_cycle' in z:
        for key in E.GEN_V31_KEYS:
            out[key] = z[key][idx]
    return out, json.loads(str(z["meta"]))


def to_device(B: dict, dev) -> dict:
    out = {}
    for k, v in B.items():
        t = torch.from_numpy(np.ascontiguousarray(v))
        out[k] = t.to(dev)
    return out


# ------------------------------------------------------------------------------------------------------
# log-probs, KL, loss
# ------------------------------------------------------------------------------------------------------
def _logit(p: float) -> float:
    return math.log(p / (1.0 - p))


def policy_terms(model, B: dict, idx, tau: float, T: float, value: bool = False, value_trunk: bool = True) -> dict:
    """Recompute the behaviour log-probs of rows ``idx`` exactly as ``e1_eval.sample_decide_batch`` defined them:
    gate ``sigmoid((z - logit(tau)) / T)`` on gate-sampled rows; card softmax over ``allowed`` of the heads'
    hand-masked logits / T and cell softmax over 2,304 for the recorded slot / T on played rows; float64 after the
    float32 forward, as the sampler. Gradients flow unless the caller is in no_grad.
    Generalist rows (``hand_card`` in B, a GenModel ``model``): the forward is ``e1_eval.GenPolicy.heads_t`` -- the
    sampler's own function -- so card = the hand-position logits on their deck slots (softmax over allowed slots ==
    over allowed hand positions) and cell = ``cell_logits_gen`` for the slot's card identity + form.
    ``value``: also ``v`` = ``value_scalar`` of the value head on the same forward (gae mode only); ``value_trunk``
    False (``vf_trunk_grad: false``) detaches the trunk features under ``v``, so a loss on ``v`` reaches value_head only."""
    if "hand_card" in B:
        pol = E.GenPolicy(model, ())
        enc, heads = pol.heads_t({k: B[k][idx] for k in E.gen_row_keys(model)})
        cell_of = pol.cell_logits
    else:
        tok, mask, sc, past = B["tok"][idx], B["mask"][idx], B["sc"][idx], B["past"][idx]
        enc = model.encode(tok, mask, sc, past)
        heads = model.heads(enc, hand_mask_from_sc(sc))
        cell_of = model.cell_logits
    allowed, gs, played = B["allowed"][idx], B["gate_sampled"][idx], B["played"][idx]
    slot, cell = B["slot"][idx], B["cell"][idx]
    x = (heads["gate"].double() - _logit(tau)) / T
    card_lp = torch.log_softmax(heads["card"].double().masked_fill(~allowed, CARD_FILL) / T, dim=-1)
    lp_gate = torch.where(gs, torch.where(played, Fn.logsigmoid(x), Fn.logsigmoid(-x)), torch.zeros_like(x))
    lp_card = torch.zeros_like(x)
    lp_cell = torch.zeros_like(x)
    pi = played.nonzero().squeeze(-1)
    cell_lp = None
    if len(pi):
        lp_card = lp_card.index_put((pi,), card_lp[pi].gather(1, slot[pi].unsqueeze(1)).squeeze(1))
        cl = cell_of({k: v[pi] for k, v in enc.items()}, slot[pi])
        cell_lp = torch.log_softmax(cl.double() / T, dim=-1)
        lp_cell = lp_cell.index_put((pi,), cell_lp.gather(1, cell[pi].unsqueeze(1)).squeeze(1))
    out = {"x": x, "card_lp": card_lp, "cell_lp": cell_lp, "lp_gate": lp_gate, "lp_card": lp_card, "lp_cell": lp_cell}
    if value:
        out["v"] = value_scalar(model.value_head(enc["g"] if value_trunk else enc["g"].detach()))
    return out


@torch.no_grad()
def value_rows(model, B: dict, chunk: int = 512) -> torch.Tensor:
    """V(s) (``value_scalar``) of every row under ``model``, no grad: the encoder + value head only."""
    N = len(B["A"])
    out = []
    for s in range(0, N, chunk):
        idx = torch.arange(s, min(s + chunk, N), device=B["A"].device)
        if "hand_card" in B:
            enc = model.encode_gen({k: B[k][idx] for k in E.gen_row_keys(model)})
        else:
            enc = model.encode(B["tok"][idx], B["mask"][idx], B["sc"][idx], B["past"][idx])
        out.append(value_scalar(model.value_head(enc["g"])))
    return torch.cat(out) if out else torch.zeros(0, dtype=torch.float64, device=B["A"].device)


def gae_batch(model, B: dict, cfg: dict) -> dict:
    """gae mode, once per update BEFORE any step (``model`` = the behaviour policy): ``v_old`` = V(s) per row, GAE over
    ``r_step`` -> ``ret`` (value target) and ``A`` normalised over the batch (mean 0, std 1). -> monitors (advantage
    mean / std BEFORE normalisation, return mean, V mean, explained variance of v_old for ret). The discount is
    ``B["gamma_row"]`` when collate made it (``gae_gamma_unit: tick``), else ``gae_gamma`` per row.

    Shaping (``B["phi"]``, L69 7b): a RESIDUAL critic. v_net = ``value_scalar`` (P(win) - P(loss), a difference of
    softmax probabilities: bounded in [-1, 1], no tanh), s = ``shaping_critic_scale``, and per row
        V_eff_t = Phi_t + s v_net_t,        A = GAE(r, V_eff) on the UNSHAPED r, per-row gamma_t,
        ret_t = A_t + V_eff_t (the unshaped lambda-return),   value target for v_net = (ret_t - Phi_t) / s.
    This IS the shaped-critic method (Ng 1999 / Wiewiora 2003): with F_t = gamma_t Phi_{t+1} - Phi_t and the same
    gamma_t (Phi = V = 0 after a match's last row),
        r_t + gamma_t V_eff_{t+1} - V_eff_t = (r_t + F_t) + gamma_t (s v_net_{t+1}) - s v_net_t,
    i.e. the TD error of a critic s v_net on the shaped reward r + F, whose true value is G - Phi. So the net learns
    the shaped value (scaled into [-1, 1]); Phi is the hand-made prior the plan wants (3b). If s v_net = V_true - Phi
    exactly, A = GAE(r, V_true), the true-value advantage. s: |G - Phi| <= 1 + |Phi| < 1 + w_tower + (2/3) w_crown =
    1.5 at w 0.3 (adv_cfg rejects a smaller s); measured max |Phi| 0.388 in the 7b smoke (|G - Phi| <= 1.39).
    A pretrained v_net predicts G, not (G - Phi) / s: its first targets move by -Phi / s and its scale by 1/s, so a
    critic warm-up is mandatory with shaping (adv_cfg rejects critic_warmup_updates 0). Monitors: ``adv_r1_diff`` =
    mean |A - GAE(r, v_net)| (what R1 would compute with the same net; 0 = shaping changed nothing), ``phi_share`` =
    mean |Phi| / mean |V_eff|, ``veff_mean``; ``explained_var`` is of V_eff for ret. Critic diagnostics (logging only):
    ``value_target_outside_share`` = share of v_net targets outside [-1, 1], ``value_saturation_share`` = share with
    |v_net| > 0.95, ``value_mae`` = mean |v_net - target| (residual target with shaping, ret otherwise)."""
    c = adv_cfg(cfg)
    v = value_rows(model, B)
    gam = B["gamma_row"].cpu().numpy() if "gamma_row" in B else c["gae_gamma"]
    vn, m, r = v.cpu().numpy(), B["match"].cpu().numpy(), B["r_step"].cpu().numpy()
    if "phi" not in B:
        A, ret = gae(r, vn, m, gam, c["gae_lambda"])
        st = {"adv_mean": float(A.mean()) if len(A) else None, "adv_std": float(A.std()) if len(A) else None,
              "ret_mean": float(ret.mean()) if len(ret) else None, "v_mean": float(v.mean()) if len(v) else None,
              "explained_var": explained_variance(v.cpu().numpy(), ret) if len(A) else None}
        target = ret
    else:
        phi, sc = B["phi"].cpu().numpy(), float(c["shaping_critic_scale"])
        veff = phi + sc * vn
        A, ret = gae(r, veff, m, gam, c["gae_lambda"])
        a_r1, _ = gae(r, vn, m, gam, c["gae_lambda"])
        n = len(A)
        mean = (lambda x: float(x.mean()) if n else None)
        st = {"adv_mean": mean(A), "adv_std": float(A.std()) if n else None, "ret_mean": mean(ret),
              "v_mean": mean(vn), "explained_var": explained_variance(veff, ret) if n else None,
              "veff_mean": mean(veff), "adv_r1_diff": mean(np.abs(A - a_r1)),
              "phi_share": float(np.abs(phi).mean() / max(float(np.abs(veff).mean()), 1e-12)) if n else None,
              "critic_scale": sc}
        target = (ret - phi) / sc
    st.update({"value_target_outside_share": float((np.abs(target) > 1.0).mean()) if len(target) else None,
               "value_saturation_share": float((np.abs(vn) > 0.95).mean()) if len(vn) else None,
               "value_mae": float(np.abs(vn - target).mean()) if len(target) else None})
    dev = B["A"].device
    B["A"] = torch.from_numpy((A - A.mean()) / (A.std() + 1e-8) if len(A) else A).to(dev)
    B["ret"] = torch.from_numpy(target).to(dev)
    B["v_old"] = v
    return st


def bern_kl(xp, xq):
    """KL(Bern(sigmoid(xp)) || Bern(sigmoid(xq))), stable in log space."""
    lp, lnp, lq, lnq = Fn.logsigmoid(xp), Fn.logsigmoid(-xp), Fn.logsigmoid(xq), Fn.logsigmoid(-xq)
    return lp.exp() * (lp - lq) + lnp.exp() * (lnp - lnq)


def bern_ent(x):
    lp, lnp = Fn.logsigmoid(x), Fn.logsigmoid(-x)
    return -(lp.exp() * lp + lnp.exp() * lnp)


def cat_kl(lp, lq):
    return (lp.exp() * (lp - lq)).sum(-1)


def cat_ent(lp):
    return -(lp.exp() * lp).sum(-1)


@torch.no_grad()
def ref_terms(ref, B: dict, tau: float, T: float, chunk: int = 512) -> dict:
    """Frozen-ref tempered distributions for every row, once per update (E1 3.4): gate x [N], card log-probs [N, 8],
    cell log-probs [P, 2304] for the P played rows (``play_pos`` maps a row to its position, -1 if not played)."""
    N = len(B["A"])
    dev = B["A"].device
    xs, cards, cells = [], [], []
    for s in range(0, N, chunk):
        idx = torch.arange(s, min(s + chunk, N), device=dev)
        t = policy_terms(ref, B, idx, tau, T)
        xs.append(t["x"]); cards.append(t["card_lp"])
        if t["cell_lp"] is not None:
            cells.append(t["cell_lp"])
    played = B["played"]
    play_pos = torch.full((N,), -1, dtype=torch.long, device=dev)
    play_pos[played] = torch.arange(int(played.sum()), device=dev)
    R = {"x": torch.cat(xs), "card_lp": torch.cat(cards),
         "cell_lp": torch.cat(cells) if cells else torch.zeros(0, E.N_CELLS, dtype=torch.float64, device=dev),
         "play_pos": play_pos}
    gs = B["gate_sampled"]
    R["ent"] = {"gate": float(bern_ent(R["x"][gs]).mean()) if gs.any() else None,
                "card": float(cat_ent(R["card_lp"][played]).mean()) if played.any() else None,
                "cell": float(cat_ent(R["cell_lp"]).mean()) if len(R["cell_lp"]) else None}
    return R


def minibatch_loss(model, B: dict, R: dict, idx, *, tau: float, T: float, clip: float, beta: float,
                   n_total: int, vf: Optional[dict] = None) -> tuple[torch.Tensor, dict]:
    """PPO-clip on the joint log pi = lp_gate + g (lp_card + lp_cell) (E1 3.3) with per-match weights, scaled by
    n_total / |mb| so each minibatch estimates the full-batch loss; + beta (mean KL_gate + mean KL_card + mean KL_cell).
    ``vf`` (gae mode: {coef, clip, policy}): + coef x the PPO-clipped value loss 0.5 max((V - ret)^2, (V_old +
    clip(V - V_old, +-clip) - ret)^2), per-match weighted like L_pg; ``policy`` False (critic warm-up) = the value
    loss ALONE (no L_pg, no KL term); ``trunk_grad`` False (default True) = the value loss trains value_head only.
    None = the match_loo loss, unchanged."""
    t = policy_terms(model, B, idx, tau, T, value=vf is not None,
                     value_trunk=True if vf is None else bool(vf.get("trunk_grad", True)))
    lp_new = t["lp_gate"] + t["lp_card"] + t["lp_cell"]
    ratio = torch.exp(lp_new - B["lp_old"][idx])
    A, w = B["A"][idx], B["w"][idx]
    pg = -torch.min(ratio * A, ratio.clamp(1 - clip, 1 + clip) * A)
    l_pg = (w * pg).sum() * (n_total / len(idx))
    gs, pl = B["gate_sampled"][idx], B["played"][idx]
    zero = lp_new.new_zeros(())
    kl_g = bern_kl(t["x"][gs], R["x"][idx][gs]).mean() if gs.any() else zero
    kl_c = cat_kl(t["card_lp"][pl], R["card_lp"][idx][pl]).mean() if pl.any() else zero
    kl_x = cat_kl(t["cell_lp"], R["cell_lp"][R["play_pos"][idx[pl]]]).mean() if pl.any() else zero
    loss = l_pg + beta * (kl_g + kl_c + kl_x)
    if vf is not None:
        v, v_old, ret = t["v"], B["v_old"][idx], B["ret"][idx]
        v_clip = v_old + (v - v_old).clamp(-float(vf["clip"]), float(vf["clip"]))
        l_v = (w * 0.5 * torch.max((v - ret) ** 2, (v_clip - ret) ** 2)).sum() * (n_total / len(idx))
        loss = (loss if vf["policy"] else 0.0) + float(vf["coef"]) * l_v
    with torch.no_grad():
        dev_ = (ratio - 1).abs()
        st = {"l_pg": float(l_pg), "kl_gate": float(kl_g), "kl_card": float(kl_c), "kl_cell": float(kl_x),
              "ratio_maxdev": float(dev_.max()), "ratio_mean": float(ratio.mean()),
              "clip_frac": float((dev_ > clip).double().mean()), "n": len(idx),
              "lp_maxdiff": {k: float((t[k] - B[k][idx]).abs().max()) for k in ("lp_gate", "lp_card", "lp_cell")},
              "ent_gate": float(bern_ent(t["x"][gs]).mean()) if gs.any() else None,
              "ent_card": float(cat_ent(t["card_lp"][pl]).mean()) if pl.any() else None,
              "ent_cell": float(cat_ent(t["cell_lp"]).mean()) if pl.any() else None}
        if vf is not None:
            st["l_v"] = float(l_v)
    return loss, st


def vf_grad_share(model, B: dict, R: dict, cfg: dict, beta: float, vf: dict) -> dict:
    """gae-mode monitor (R1 verifier finding F2: the value loss also trains the shared trunk, moving the policy where
    the KL monitors do not look). On ONE minibatch (``minibatch`` rows strided over the batch; no step, no .grad
    written, no RNG drawn): the gradient norms, on the TRUNK, of the value part of the loss as trained (vf_coef x L_v;
    exactly 0 with ``vf["trunk_grad"]`` False) and of the policy part (L_pg + beta KL). Trunk = every parameter but
    value_head that the value loss reaches through the trunk features. -> {share = |g_v| / (|g_v| + |g_pg|), norms}."""
    N = len(B["A"])
    idx = torch.arange(0, N, max(1, N // int(cfg["minibatch"])), device=B["A"].device)[:int(cfg["minibatch"])]
    kw = dict(tau=cfg["tau"], T=cfg["T"], clip=cfg["clip"], beta=beta, n_total=N)
    params = [p for n, p in model.named_parameters() if p.requires_grad and not n.startswith("value_head.")]
    l_v, _ = minibatch_loss(model, B, R, idx, vf={**vf, "policy": False, "trunk_grad": True}, **kw)
    g_reach = torch.autograd.grad(l_v, params, allow_unused=True)
    trunk = [i for i, g in enumerate(g_reach) if g is not None]
    l_pg, _ = minibatch_loss(model, B, R, idx, **kw)
    g_pg = torch.autograd.grad(l_pg, [params[i] for i in trunk], allow_unused=True)
    norm = (lambda gs: math.sqrt(sum(float((g.double() ** 2).sum()) for g in gs if g is not None)))
    nv = norm([g_reach[i] for i in trunk]) if vf.get("trunk_grad", True) else 0.0
    npg = norm(g_pg)
    return {"share": nv / (nv + npg) if nv + npg > 0 else None, "grad_v": nv, "grad_pg": npg,
            "trunk_tensors": len(trunk), "rows": int(len(idx))}


def ppo_update(model, opt, B: dict, R: dict, cfg: dict, beta: float, rng: np.random.Generator,
               vf: Optional[dict] = None) -> dict:
    """``ppo_epochs`` passes over the batch in random minibatches. Returns the monitors; ``first`` = epoch 0 minibatch 0
    (the on-policy check), ``nonfinite`` set (and the step skipped) on a non-finite loss or gradient norm.
    ``vf`` (gae mode, ``minibatch_loss``): + ``l_v``; ``vf["policy"]`` False = critic warm-up: ONLY ``value_head``
    parameters get gradients (the trunk is shared with the policy heads, so training it would move the policy)."""
    frozen = [p for n, p in model.named_parameters()
              if vf is not None and not vf["policy"] and not n.startswith("value_head.") and p.requires_grad]
    for p in frozen:
        p.requires_grad_(False)
    try:
        return _ppo_steps(model, opt, B, R, cfg, beta, rng, vf)
    finally:
        for p in frozen:
            p.requires_grad_(True)


def _ppo_steps(model, opt, B: dict, R: dict, cfg: dict, beta: float, rng: np.random.Generator,
               vf: Optional[dict]) -> dict:
    N = len(B["A"])
    dev = B["A"].device
    mb = int(cfg["minibatch"])
    first, last_ep, ep0 = None, [], []
    ratios, clips, gnorms = [], [], []
    mean = (lambda xs, k: float(np.mean([x[k] for x in xs if x[k] is not None])) if any(x[k] is not None for x in xs) else None)
    avg = (lambda xs: float(np.mean(xs)) if xs else None)

    def summary(nonfinite: Optional[str]) -> dict:
        """Every key present even on the non-finite early exit (one_update logs them; None = not measured)."""
        return {"first": first, "nonfinite": nonfinite, "steps": len(ratios),
                "kl_gate": mean(last_ep, "kl_gate"), "kl_card": mean(last_ep, "kl_card"),
                "kl_cell": mean(last_ep, "kl_cell"), "l_pg": mean(last_ep, "l_pg"),
                "ent": {h: mean(ep0, f"ent_{h}") for h in ("gate", "card", "cell")},
                "ratio_mean": avg(ratios), "clip_frac": avg(clips), "grad_norm_mean": avg(gnorms),
                **({"l_v": mean(last_ep, "l_v"), "l_v_first": first["l_v"] if first else None} if vf is not None else {})}

    for ep in range(int(cfg["ppo_epochs"])):
        perm = torch.from_numpy(rng.permutation(N)).to(dev)
        for s in range(0, N, mb):
            idx = perm[s:s + mb]
            loss, st = minibatch_loss(model, B, R, idx, tau=cfg["tau"], T=cfg["T"], clip=cfg["clip"], beta=beta,
                                      n_total=N, vf=vf)
            if first is None:
                first = st
            if not torch.isfinite(loss):
                return summary(f"loss {float(loss.detach())} at epoch {ep} minibatch {s // mb}")
            opt.zero_grad(set_to_none=True)
            loss.backward()
            gn = torch.nn.utils.clip_grad_norm_(model.parameters(), float(cfg["grad_clip"]))
            if not torch.isfinite(gn):
                return summary(f"grad norm {float(gn)} at epoch {ep} minibatch {s // mb}")
            opt.step()
            (ep0 if ep == 0 else []).append(st)
            if ep == int(cfg["ppo_epochs"]) - 1:
                last_ep.append(st)
            ratios.append(st["ratio_mean"]); clips.append(st["clip_frac"]); gnorms.append(float(gn))
    return summary(None)


# ------------------------------------------------------------------------------------------------------
# monitors (E1 3.6 / 4.2) from the rollout records
# ------------------------------------------------------------------------------------------------------
def rollout_monitors(results: list[dict], tau: float, T: float) -> dict:
    n = len(results)
    wins = [r for r in results if r["outcome"] == "win"]
    minutes = sum(r["seconds"] for r in results) / 60.0
    att = sum(r["plays_attempted"] for r in results)
    mix = Counter()
    refuse = Counter()
    for r in results:
        mix.update(r["card_mix_attempted"])
        refuse.update(r["refuse_reasons"])
    el = [e for r in results for e in r["play_elixir"]]
    pg = np.concatenate([r["traj"]["p_gate"] for r in results if "traj" in r]) if results and "traj" in results[0] \
        else np.concatenate([[r["p_gate_mean"] or 0.0] for r in results])
    with np.errstate(divide="ignore", over="ignore"):
        z = np.log(pg) - np.log1p(-pg)
        p_b = 1.0 / (1.0 + np.exp(-(z - _logit(tau)) / T))
    share = (lambda xs: len(xs) / len(wins) if wins else None)
    return {
        "matches": n, "W": len(wins), "L": sum(r["outcome"] == "loss" for r in results),
        "D": sum(r["outcome"] == "draw" for r in results), "winrate": len(wins) / n if n else None,
        "plays_per_min": att / minutes if minutes else None, "plays_per_match": att / n if n else None,
        "accepted_frac": sum(r["plays_accepted"] for r in results) / att if att else None,
        "refuse_top": dict(refuse.most_common(5)), "stall_per_match": sum(r["stall_fired"] for r in results) / max(n, 1),
        "card_mix": {k: round(v / max(att, 1), 4) for k, v in mix.most_common()},
        "elixir_at_play_mean": float(np.mean(el)) if el else None,
        "elixir_at_play_share10": float(np.mean([e >= 10 for e in el])) if el else None,
        "p_gate_mean": float(pg.mean()), "p_gate_p90": float(np.percentile(pg, 90)),
        "p_gate_frac_gt_tau": float((pg > tau).mean()), "stochastic_share": float(((p_b > 0.05) & (p_b < 0.95)).mean()),
        "ghost_delivered_per_match": sum(r["ghost_delivered"] for r in results) / max(n, 1),
        "ghost_refused_per_match": sum(r["ghost_refused"] for r in results) / max(n, 1),
        "ghost_undelivered_per_match": sum(r["ghost_undelivered"] for r in results) / max(n, 1),
        "outlived_win_share": share([r for r in wins if r["won_after_script"]]),
        "low_delivered_win_share": share([r for r in wins if r["ghost_delivered"] <= 10]),
        "seconds_mean": float(np.mean([r["seconds"] for r in results])) if n else None,
        "won_seconds_mean": float(np.mean([r["seconds"] for r in wins])) if wins else None,
    }


# ------------------------------------------------------------------------------------------------------
# actors
# ------------------------------------------------------------------------------------------------------
def actor_sender(out_q):
    """The actor's side of the result queue. ``cancel_join_thread`` so process EXIT never blocks on the queue's feeder
    thread (a multi-MB put with no reader left would otherwise hang the exit forever -- verifier F1, L68), and every
    send first checks the learner is alive: a dead learner -> nothing is put (returns False) and the caller exits."""
    import multiprocessing as mp
    out_q.cancel_join_thread()
    parent = mp.parent_process()

    def send(msg) -> bool:
        if parent is not None and not parent.is_alive():
            return False
        out_q.put(msg)
        return True
    return send


def actor_main(aid: int, gen: int, in_q, out_q, base: dict) -> None:
    """One actor process: a model copy on ``actor_device`` + RoyaleSim envs; runs ``e1_eval.run_batch`` per job list
    (``selfplay``: ``e1_eval.run_selfplay_batch`` with the frozen opponents the jobs name, loaded read-only from their
    checkpoint files by ``e1_eval.load_policy`` and cached by path; the learner's weights come in the message as always).
    Messages in: (kind, update, state_dict bytes, jobs [(entry_index, entry | league spec, g)]) or None to exit.
    Out: ("ready", aid, gen, pid) | ("done", aid, gen, results, skipped, stats) | ("error", aid, gen, traceback)."""
    import multiprocessing as mp
    send = actor_sender(out_q)
    torch.set_num_threads(int(base["actor_threads"]))
    try:
        from pipeline.royale_runtime import require_same
        require_same(base.get("runtime"))
        from pipeline.model_v3 import S1Model
        from pipeline.obs_contract import load_deck
        from pipeline.royale_env import RoyalePoolEnv, RoyaleSelfPlayEnv, UnsupportedDeck
        dev = base["actor_device"]
        opp_cache: dict = {}                                  # league: checkpoint path -> (frozen policy, its grid)
        deck = load_deck("icebow")
        g = base.get("gen")
        if g:                                                 # generalist: GenModel weights behind GenPolicy
            from pipeline.model_gen import GenModel
            net = GenModel(d=int(base["d"]), layers=int(base["layers"]), d_c=int(g["d_c"]),
                           n_cards=len(g["card_vocab"]), feature_version=int(g.get("feature_version", 1))).to(dev).eval()
            model = E.GenPolicy(net, g["card_vocab"])
        else:
            net = model = S1Model(d=int(base["d"]), layers=int(base["layers"])).to(dev).eval()
        send(("ready", aid, gen, os.getpid()))
    except Exception:
        send(("error", aid, gen, traceback.format_exc()))
        return
    parent = mp.parent_process()
    while True:
        try:
            msg = in_q.get(timeout=30)
        except queue.Empty:
            if parent is not None and not parent.is_alive():
                return                                        # learner gone: do not linger
            continue
        if msg is None:
            return
        kind, update, sd, jobs = msg
        try:
            t0 = time.perf_counter()
            if dev.startswith("cuda"):
                torch.cuda.reset_peak_memory_stats()
            net.load_state_dict(torch.load(io.BytesIO(sd), map_location=dev))
            net.eval()
            cfg = actor_cfg(base, kind, aid, dev)
            results, skipped = [], []

            def on_result(line):
                if kind in ("rollout", "selfplay"):
                    line["rollout_index"], line["update"] = int(line["k"]), int(update)
                results.append(line)

            n_fl = max(1, min(int(base["in_flight"]), len(jobs)))
            fm = base.get("forms_mode", "base")                # RoyaleSim forms (royale_env.FORMS_MODES)
            on_skip = (lambda e, exc: skipped.append({"tag": e["tag"], "why": str(exc)}))
            if kind == "selfplay":
                cfg = actor_cfg(base, "rollout", aid, dev)
                need = {j[1]["opp"]["path"] for j in jobs}
                for pth in [x for x in opp_cache if x not in need]:
                    del opp_cache[pth]
                for pth in need - set(opp_cache):
                    pol, mi = E.load_policy(REPO / pth, dev)
                    opp_cache[pth] = (pol, str(mi.get("grid", "floor")))
                opps = {j[1]["opp"]["id"]: (opp_cache[j[1]["opp"]["path"]][0],
                                            {**cfg, "policy": base["league_opp_policy"], "record": False,
                                             "grid": opp_cache[j[1]["opp"]["path"]][1]}) for j in jobs}
                E.run_selfplay_batch(lambda: RoyaleSelfPlayEnv(decision_ticks=int(base["decide_every"]), forms_mode=fm,
                                                               hero_abilities=base.get("hero_abilities", False),
                                                               ability_policy=base.get("ability_policy", "generic")), model, opps,
                                     rollout_jobs(jobs, update), cfg, n_fl, on_result=on_result, on_skip=on_skip,
                                     skip=(UnsupportedDeck,))
            else:
                it = rollout_jobs(jobs, update) if kind == "rollout" else jobs     # screen: eval obs seed of (tag, k)
                E.run_batch(lambda: RoyalePoolEnv(decision_ticks=int(base["decide_every"]), forms_mode=fm,
                                                               hero_abilities=base.get("hero_abilities", False),
                                                               ability_policy=base.get("ability_policy", "generic")), model, deck, it, cfg,
                            n_fl, on_result=on_result, on_skip=on_skip, skip=(UnsupportedDeck,))
            stats = {"wall_s": time.perf_counter() - t0, "matches": len(results),
                     "gpu_peak_mb": (torch.cuda.max_memory_allocated() / 2**20) if dev.startswith("cuda") else None}
            if not send(("done", aid, gen, results, skipped, stats)):
                return                                        # learner died mid-job: drop the results, exit
        except Exception:
            if not send(("error", aid, gen, traceback.format_exc())):
                return


class ActorCrash(RuntimeError):
    pass


class ActorPool:
    """``n`` actor processes; ``run`` deals a job list round-robin and gathers the records. A crash (error message, dead
    process or timeout) restarts that actor ONCE and re-runs its share; a second crash raises ActorCrash."""

    def __init__(self, base: dict, n: int, log, timeout_s: float, pid_file: Optional[Path] = None):
        import torch.multiprocessing as tmp
        self.ctx = tmp.get_context("spawn")
        self.base, self.n, self.log, self.timeout_s = base, int(n), log, float(timeout_s)
        self.pid_file = pid_file                                 # <run_dir>/actors.pid: one PID per line (RUNBOOK 4)
        self.out_q = self.ctx.Queue()
        self.procs, self.in_qs, self.gen, self.pids = {}, {}, {}, {}
        self.restarts = Counter()
        for a in range(self.n):
            self._start(a)
        t0, ready = time.time(), set()
        while len(ready) < self.n:                               # surface startup errors (imports, CUDA) now
            try:
                msg = self.out_q.get(timeout=5)
            except queue.Empty:
                msg = None
            if msg and msg[0] == "ready":
                ready.add(msg[1])
            elif msg and msg[0] == "error":
                raise ActorCrash(f"actor {msg[1]} failed to start:\n{msg[3]}")
            for a, p in self.procs.items():
                if not p.is_alive() and a not in ready:
                    raise ActorCrash(f"actor {a} died during startup (exit {p.exitcode})")
            if time.time() - t0 > 600:
                raise ActorCrash("actors not ready after 600 s")

    def _start(self, a: int) -> None:
        self.gen[a] = self.gen.get(a, -1) + 1
        self.in_qs[a] = self.ctx.Queue()
        p = self.ctx.Process(target=actor_main, args=(a, self.gen[a], self.in_qs[a], self.out_q, self.base), daemon=True)
        p.start()
        self.procs[a] = p
        self.pids[a] = p.pid
        if self.pid_file is not None:                            # refreshed on every (re)start
            self.pid_file.write_text("".join(f"{pid}\n" for pid in self.pids.values()), encoding="utf-8")

    def _crash(self, a: int, why: str) -> None:
        self.log(f"[rl] ACTOR {a} CRASH ({why.strip().splitlines()[-1] if why.strip() else why}); restarts so far "
                 f"{self.restarts[a]}")
        self.log(why)
        p = self.procs[a]
        if p.is_alive():
            p.terminate()
            p.join(10)
        if self.restarts[a] >= 1:
            raise ActorCrash(f"actor {a} crashed twice: {why.strip().splitlines()[-1] if why.strip() else why}")
        self.restarts[a] += 1
        self._start(a)

    def run(self, kind: str, update: int, sd: bytes, jobs: list) -> tuple[list[dict], list[dict], dict]:
        shares = {a: jobs[a::self.n] for a in range(self.n) if jobs[a::self.n]}
        for a, js in shares.items():
            self.in_qs[a].put((kind, update, sd, js))
        pending = {a: time.time() for a in shares}
        results, skipped, stats = [], [], {}
        while pending:
            try:
                msg = self.out_q.get(timeout=5)
            except queue.Empty:
                msg = None
            if msg is not None:
                tag, a, gen = msg[0], msg[1], msg[2]
                if gen != self.gen.get(a):
                    pass                                          # a message from a replaced actor
                elif tag == "ready":
                    self.pids[a] = msg[3]
                elif tag == "done" and a in pending:
                    results += msg[3]; skipped += msg[4]; stats[a] = msg[5]
                    del pending[a]
                    if not pending:   # lead 2026-10-04: arrival order (actor count, timing) must not reorder the batch
                        results.sort(key=lambda r: (str(r.get("tag")), int(r.get("k", 0)),
                                                    int(r.get("entry_index", -1)), str(r.get("side"))))
                elif tag == "error" and a in pending:
                    self._crash(a, msg[3])
                    self.in_qs[a].put((kind, update, sd, shares[a]))
                    pending[a] = time.time()
            for a in list(pending):
                dead = not self.procs[a].is_alive()
                if dead or time.time() - pending[a] > self.timeout_s:
                    self._crash(a, f"process {'exited ' + str(self.procs[a].exitcode) if dead else 'timed out'}")
                    self.in_qs[a].put((kind, update, sd, shares[a]))
                    pending[a] = time.time()
        return results, skipped, stats

    def close(self) -> None:
        for a, q in self.in_qs.items():
            try:
                q.put(None)
            except Exception:
                pass
        for p in self.procs.values():
            p.join(20)
            if p.is_alive():
                p.terminate()
                p.join(5)


# ------------------------------------------------------------------------------------------------------
# opt3: asynchronous branch workers (never on the PPO path)
# ------------------------------------------------------------------------------------------------------
BRANCH_MAX_ERRORS = 5          # consecutive failed matches before a worker gives up (reported, restarted by the pool)


def branch_worker_main(wid: int, in_q, out_q, base: dict) -> None:
    """One branch worker, for the whole run. In: (version, state_dict bytes, [league specs]) per update, None = exit;
    only the NEWEST message counts (older ones are skipped), read between rounds without waiting -- it waits only for
    its first weights, or for specs when it has none. Each spec is one branch match (``branch_jobs``) with the weights
    of the round; every labelled sample goes out at once as ("sample", wid, sample + version, worker). Out also:
    ("ready", wid, pid), ("error", wid, traceback) -- one failed match is reported and skipped; BRANCH_MAX_ERRORS in a
    row end the worker."""
    import multiprocessing as mp
    send = actor_sender(out_q)
    bc = base["branch"]
    torch.set_num_threads(int(bc["branch_threads"]))
    try:
        from pipeline.royale_runtime import require_same
        require_same(base.get("runtime"))
        from pipeline.model_v3 import S1Model
        from pipeline.royale_env import RoyaleSelfPlayEnv, UnsupportedDeck
        dev = base["actor_device"]
        g = base.get("gen")
        if g:
            from pipeline.model_gen import GenModel
            net = GenModel(d=int(base["d"]), layers=int(base["layers"]), d_c=int(g["d_c"]),
                           n_cards=len(g["card_vocab"]), feature_version=int(g.get("feature_version", 1))).to(dev).eval()
            model = E.GenPolicy(net, g["card_vocab"])
        else:
            net = model = S1Model(d=int(base["d"]), layers=int(base["layers"])).to(dev).eval()
        phi = None
        if bc["branch_score"] == "phi":
            from pipeline.branch_score import load_phi
            phi = load_phi(str(REPO / bc["branch_phi_ckpt"]), dev)
        send(("ready", wid, os.getpid()))
    except Exception:
        send(("error", wid, traceback.format_exc()))
        return
    parent = mp.parent_process()
    st = {"version": None, "specs": [], "exit": False}

    def sync(block: bool = False) -> bool:
        """Drain ``in_q`` to its newest message and load it; ``block``: wait until one exists. False = exit."""
        got = None
        while True:
            try:
                msg = in_q.get(timeout=30) if (block and got is None) else in_q.get_nowait()
            except queue.Empty:
                if block and got is None:
                    if parent is not None and not parent.is_alive():
                        st["exit"] = True
                        return False
                    continue
                break
            if msg is None:
                st["exit"] = True
                return False
            got = msg
        if got is not None:
            version, sd, specs = got
            net.load_state_dict(torch.load(io.BytesIO(sd), map_location=dev))
            net.eval()
            st.update(version=int(version), specs=list(specs))
        return True

    lcfg = actor_cfg(base, "screen", wid, dev)                # the greedy live rule, unrecorded
    ocfg = {**actor_cfg(base, "rollout", wid, dev), "policy": base["league_opp_policy"], "record": False}
    sp_env = (lambda: RoyaleSelfPlayEnv(decision_ticks=int(base["decide_every"]), forms_mode=base.get("forms_mode", "base"),
                                        hero_abilities=base.get("hero_abilities", False),
                                        ability_policy=base.get("ability_policy", "generic")))
    emit = (lambda smp: send(("sample", wid, {**smp, "version": st["version"], "worker": wid})))
    opp_cache: dict = {}
    n_match = errors = 0
    if not sync(block=True):
        return
    while not st["exit"]:
        if not st["specs"]:
            if not sync(block=True):
                return
            continue
        spec = st["specs"].pop(0)
        try:
            pth = spec["opp"]["path"]
            if pth not in opp_cache:
                if len(opp_cache) >= 8:                         # bounded: snapshots churn over a run
                    opp_cache.pop(next(iter(opp_cache)))
                pol, mi = E.load_policy(REPO / pth, dev)
                opp_cache[pth] = (pol, str(mi.get("grid", "floor")))
            pol, grid = opp_cache[pth]
            tag = f"bw{wid:02d}_{n_match:05d}"
            n_match += 1
            branch_jobs(sp_env, model, {spec["opp"]["id"]: (pol, {**ocfg, "grid": grid})}, [(n_match, {**spec, "tag": tag}, 0)],
                        lcfg, bc, st["version"], skip=(UnsupportedDeck,), sync=sync, emit=emit, phi=phi)
            errors = 0
        except Exception:
            errors += 1
            if not send(("error", wid, traceback.format_exc())) or errors >= BRANCH_MAX_ERRORS:
                return


class BranchPool:
    """``n`` branch worker processes for the whole run (spawn, like ``ActorPool``, but never waited on after startup):
    ``send`` puts (version, weights, specs) on every worker's queue (non-blocking); ``drain`` takes everything that has
    arrived (non-blocking), logs worker errors, restarts a dead worker (``max_restarts`` each, then it stays down)."""

    def __init__(self, base: dict, n: int, log, pid_file: Optional[Path] = None, max_restarts: int = 3,
                 target=None, ctx=None):
        if ctx is None:
            import torch.multiprocessing as tmp
            ctx = tmp.get_context("spawn")
        self.ctx, self.base, self.n, self.log, self.pid_file = ctx, base, int(n), log, pid_file
        self.target = target or branch_worker_main
        self.max_restarts, self.restarts, self.errors = int(max_restarts), Counter(), Counter()
        self.out_q = ctx.Queue()
        self.in_qs, self.procs, self.pids, self.last = {}, {}, {}, None
        self._queues = [self.out_q]                            # EVERY queue this pool made (close cancels them all)
        # a reader thread keeps the workers' pipe flowing: a sample carries its observation row, so between drains the
        # pipe fills and a get_nowait drain alone saw samples 1-2 updates late (measured, laptop smoke 2026-10-07)
        import threading
        self._got, self._lock, self._closed = [], threading.Lock(), False
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()
        for w in range(self.n):
            self._start(w)

    def _read(self) -> None:
        while not self._closed:
            try:
                msg = self.out_q.get(timeout=1.0)
            except queue.Empty:
                continue
            except (EOFError, OSError, ValueError):
                return
            with self._lock:
                self._got.append(msg)

    def _start(self, w: int) -> None:
        old = self.in_qs.get(w)
        if old is not None:                                    # a dead worker's queue: nobody will read it again
            _cancel_join(old)
        self.in_qs[w] = self.ctx.Queue()
        self._queues.append(self.in_qs[w])
        p = self.ctx.Process(target=self.target, args=(w, self.in_qs[w], self.out_q, self.base), daemon=True)
        p.start()
        self.procs[w], self.pids[w] = p, p.pid
        if self.pid_file is not None:
            self.pid_file.write_text("".join(f"{pid}\n" for pid in self.pids.values()), encoding="utf-8")
        if self.last is not None:                              # a restarted worker gets the newest weights at once
            self.in_qs[w].put(self.last[w])

    def send(self, version: int, sd: bytes, specs: list) -> None:
        """Worker w gets (version, sd, specs[w]); nothing here waits on a worker."""
        self.last = {w: (int(version), sd, list(specs[w])) for w in range(self.n)}
        for w in range(self.n):
            self.in_qs[w].put(self.last[w])

    def drain(self) -> tuple[list[dict], dict]:
        """Every sample that has arrived since the last drain (non-blocking) + {errors, restarts, alive}."""
        out, errs = [], 0
        with self._lock:
            msgs, self._got = self._got, []
        for msg in msgs:
            if msg[0] == "sample":
                out.append(msg[2])
            elif msg[0] == "ready":
                self.pids[msg[1]] = msg[2]
            elif msg[0] == "error":
                errs += 1
                self.errors[msg[1]] += 1
                tb = str(msg[2]).strip().splitlines()
                self.log(f"[rl] BRANCH WORKER {msg[1]} error: {tb[-1] if tb else '?'}")
        restarted = []
        for w, p in list(self.procs.items()):
            if not p.is_alive() and self.restarts[w] < self.max_restarts:
                self.restarts[w] += 1
                self.log(f"[rl] BRANCH WORKER {w} exited ({p.exitcode}); restart {self.restarts[w]}/{self.max_restarts}")
                self._start(w)
                restarted.append(w)
        return out, {"errors": errs, "restarted": restarted, "alive": sum(p.is_alive() for p in self.procs.values())}

    def close(self) -> None:
        """Idempotent. Every queue's feeder thread is cancelled FIRST: a worker mid-pair never reads its ~6 MB weights
        messages, and an uncancelled feeder makes the learner wait for them forever at interpreter exit (verifier,
        Windows). Then None to each worker, join, terminate the ones mid-label."""
        if getattr(self, "_closed_all", False):
            return
        self._closed_all = True
        for q in self._queues:
            _cancel_join(q)
        for q in self.in_qs.values():
            try:
                q.put(None)
            except Exception:
                pass
        deadline = time.time() + 5.0                           # one shared budget (24 workers x 5 s would be 2 min)
        for p in self.procs.values():
            p.join(max(0.0, deadline - time.time()))
        for p in self.procs.values():
            if p.is_alive():
                p.terminate()                                  # mid-pair: a label is minutes long
                p.join(5)
        self._closed = True


def _cancel_join(q) -> None:
    """``q.cancel_join_thread()`` where the queue has one (mp queues; test doubles may not)."""
    f = getattr(q, "cancel_join_thread", None)
    if f is not None:
        f()


# ------------------------------------------------------------------------------------------------------
# config, paths, logging
# ------------------------------------------------------------------------------------------------------
def load_config(path: Path, overrides: list[str], smoke: bool) -> dict:
    import yaml
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    cfg.setdefault("hero_abilities", False)
    if smoke:
        cfg.update(SMOKE)
    for ov in overrides:
        if "=" not in ov:
            raise SystemExit(f"bad override {ov!r} (want key=value)")
        k, v = ov.split("=", 1)
        if (k not in cfg and k != "ability_policy" and k not in BRANCH_DEFAULTS   # optional: absent = generic / off
                and k not in VALUE_PHI_KEYS):
            raise SystemExit(f"unknown config key {k!r}; keys: {sorted(cfg)}")
        cfg[k] = yaml.safe_load(v)
    if type(cfg["hero_abilities"]) is not bool:
        raise SystemExit("hero_abilities must be a bool")
    if cfg.get("ability_policy", "generic") not in ("generic", "v2"):
        raise SystemExit(f"ability_policy must be generic or v2, got {cfg['ability_policy']!r}")
    if cfg.get("ability_policy") == "v2" and not cfg["hero_abilities"]:
        raise SystemExit("ability_policy v2 needs hero_abilities=true")
    return cfg


def config_sha(cfg: dict) -> str:
    # Off is the historical configuration, including checkpoint resume hashes.
    if cfg.get("hero_abilities") is False:
        cfg = {k: v for k, v in cfg.items() if k != "hero_abilities"}
    if cfg.get("ability_policy", "generic") == "generic":
        cfg = {k: v for k, v in cfg.items() if k != "ability_policy"}
    return hashlib.sha256(json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()


class Log:
    def __init__(self, run_dir: Path):
        self.human, self.jl = run_dir / "train.log", run_dir / "train_log.jsonl"

    def __call__(self, msg: str) -> None:
        print(msg, flush=True)
        with self.human.open("a", encoding="utf-8") as fh:
            fh.write(msg + "\n")

    def json(self, rec: dict) -> None:
        with self.jl.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(_py(rec)) + "\n")


def state_bytes(model) -> bytes:
    buf = io.BytesIO()
    torch.save({k: v.detach().cpu() for k, v in model.state_dict().items()}, buf)
    return buf.getvalue()


def screen_score(results: list[dict], init: Optional[dict]) -> dict:
    """Held-out screen (plan diff 2 + lead ruling L68 repair): winrate over (tag, k), and PAIRED vs the init's same
    (tag, k): the ENTRY-CLUSTERED delta (per-tag mean over its seeds, then mean over tags) with its entry-clustered
    bootstrap 95% CI -- rl_gate's headline statistic and helper (e1_score.cluster_bootstrap, 10,000 draws, seed 0) --
    plus better/worse counts over (tag, k), and the E1 4.2 exploit values of init and candidate on the PAIRED matches
    (``exploit_init`` / ``exploit_cand``). ``per_key`` ("tag:k") holds ``screen_record``s; an ``init`` value may also be
    a bare outcome float (init screens cached by older code: delta only, no exploit values). No pair -> None."""
    from pipeline.e1_score import cluster_bootstrap
    from pipeline.rl_gate import DRAWS, GATE_SEED
    recs = {f"{r['tag']}:{int(r['k'])}": screen_record(r) for r in results}
    out = {"n": len(recs), "winrate": float(np.mean([x["v"] for x in recs.values()])) if recs else None,
           "per_key": recs, "exploit": exploit_values(list(recs.values())),
           "plays_per_min": (sum(r["plays_attempted"] for r in results) / (sum(r["seconds"] for r in results) / 60.0))
           if results else None}
    if init is not None:
        iv = (lambda x: x["v"] if isinstance(x, dict) else float(x))
        both = sorted(set(recs) & set(init))
        by_entry: dict = {}
        for key in both:
            by_entry.setdefault(key.rsplit(":", 1)[0], []).append(recs[key]["v"] - iv(init[key]))
        ci = cluster_bootstrap(by_entry, DRAWS, GATE_SEED)
        pp = (lambda x: 100.0 * x if x is not None else None)          # no paired match -> None, never 0.0
        d = [recs[key]["v"] - iv(init[key]) for key in both]
        have = both and all(isinstance(init[key], dict) for key in both)
        out.update({"paired": len(both), "paired_entries": len(by_entry), "delta_pp": pp(ci["point"]),
                    "ci_lo_pp": pp(ci["lo"]), "ci_hi_pp": pp(ci["hi"]),
                    "better": sum(x > 0 for x in d), "worse": sum(x < 0 for x in d),
                    "exploit_init": exploit_values([init[key] for key in both]) if have else None,
                    "exploit_cand": exploit_values([recs[key] for key in both]) if have else None})
    return out


# ------------------------------------------------------------------------------------------------------
# the learner
# ------------------------------------------------------------------------------------------------------
class Learner:
    def __init__(self, cfg: dict, run: str, run_dir: Path, ck_dir: Path, log: Log, resume: bool):
        from pipeline.royale_runtime import activate
        self.runtime = activate()
        from pipeline import engine_play as ep
        self.cfg, self.run, self.run_dir, self.ck_dir, self.log = cfg, run, run_dir, ck_dir, log
        self.dev = torch.device(cfg["learner_device"])
        self.init_path = REPO / cfg["init"]
        condition_cfg(cfg)                                    # validate the condition keys before anything runs
        adv_cfg(cfg)                                          # ... and the advantage (R1) keys
        bc = branch_cfg(cfg)                                  # ... and the branch (opt3) keys
        if bc["branch_gate"]:
            try:
                branch_impl()
            except ImportError as exc:
                raise SystemExit(f"branch_gate true but the branch modules do not import: {exc!r}")
            if bc["branch_score"] == "phi" and not (REPO / bc["branch_phi_ckpt"]).exists():
                raise SystemExit(f"branch_phi_ckpt {bc['branch_phi_ckpt']} not found")
        ick = torch.load(self.init_path, map_location="cpu")
        self.gen = {"d_c": int(ick["d_c"]), "card_vocab": list(ick["card_vocab"])} if ick.get("gen") else None
        if self.gen and int(ick["args"].get("feature_version", 1)) >= 3:
            self.gen["feature_version"] = int(ick["args"]["feature_version"])
        if self.gen:                                          # generalist init: the learner trains the GenModel itself
            self.model = self._load_net(self.init_path)
            self.minfo = {"gen": True, "grid": str(ick["args"].get("grid", "lattice"))}   # = e1_eval.load_policy's
        else:
            self.model, self.minfo = ep.load_model(self.init_path, str(self.dev))
        self.init_meta = {"args": dict(ick["args"]), "deck": ick["deck"], "epoch": ick["epoch"], "n_params": ick["n_params"]}
        self.grid = self.minfo["grid"]
        self.league = None                                    # league on: {"snapshots": [{id, update, path}]}
        if cfg.get("league"):
            self._league_setup()
        self.ref = copy.deepcopy(self.model).eval()
        for p in self.ref.parameters():
            p.requires_grad_(False)
        if adv_cfg(cfg)["shaping"] == "value_phi":            # lever C: the frozen Phi net, loaded once from FILE
            self.phi_net = self._load_phi_net(ick)            # (never self.model / a resumed one), never trained
        self.model.eval()                                     # eval() for rollout AND update (E1 3.3 dropout trap)
        self.opt = torch.optim.Adam(self.model.parameters(), lr=float(cfg["lr"]))
        if branch_cfg(cfg)["branch_gate"]:                    # opt3: the branch step's OWN Adam (never PPO's state)
            self.branch_opt = self._branch_optimizer(branch_cfg(cfg))
        self.beta, self.update = float(cfg["beta0"]), 0
        self.rng = np.random.default_rng(int(cfg["seed"]))
        self.train, self.heldout = self._entries()
        self.visits = [0] * len(self.train)
        self.base: dict = {}                                  # init_proagree, init_screen ("tag:k" -> screen_record)
        self.guards = Guards(cfg)
        self.latest_pa: Optional[dict] = None
        self._rows = None
        self.actors: Optional[ActorPool] = None
        self.branch_pool: Optional[BranchPool] = None
        self.resumed = resume
        if resume:
            self._restore(self.ck_dir / f"{run}_latest.pt")

    def _league_setup(self) -> None:
        """League on (T12b): the learner must be the generalist; the deck pool + its sampling weights; opponents =
        init + the S1 specialist + snapshots (none yet; ``_restore`` brings a resumed run's back)."""
        cfg = self.cfg
        if not self.gen:
            raise SystemExit("league: the learner must be the generalist (a 'gen' init); S1 plays only icebow")
        validate_league(cfg)
        if not (REPO / cfg["league_specialist"]).exists():
            raise SystemExit(f"league_specialist {cfg['league_specialist']} not found")
        self.census = league_decks(REPO / cfg["league_decks"])
        self.census_p = deck_weights([d["sides"] for d in self.census], cfg["league_deck_alpha"],
                                     cfg["league_deck_floor"])
        self.league = {"snapshots": []}

    def _snapshot_payload(self) -> dict:
        """What a FROZEN opponent needs and nothing else: the weights + the keys ``e1_eval.load_policy`` /
        ``eval_gen.load_model`` read (gen, args, d_c, card_vocab, epoch, n_params, deck). No optimizer, no rl state."""
        return {"model": {k: v.detach().cpu() for k, v in self.model.state_dict().items()},
                "args": _py(dict(self.init_meta["args"]) | {"rl_run": self.run, "rl_init": str(self.cfg["init"])}),
                "deck": self.init_meta["deck"], "epoch": self.init_meta["epoch"],
                "n_params": int(self.init_meta["n_params"]), "gen": True, "d_c": int(self.gen["d_c"]),
                "card_vocab": list(self.gen["card_vocab"]), "snapshot": {"run": self.run, "update": int(self.update)}}

    def _snapshot(self) -> tuple[str, list[Path]]:
        """Freeze the learner now as a league opponent: ``<run>_snap_u{NNNN}.pt`` beside the checkpoints (weights +
        load metadata only, ``_snapshot_payload``); the pool keeps the newest ``league_snapshot_keep``. -> (its id, the
        EVICTED snapshot files): the caller deletes those only AFTER ``_latest.pt`` (which holds the new pool) is
        saved, so a crash in between never leaves a saved pool naming a deleted file. An existing file for this update
        (a crash after it, then --resume re-ran the update) is kept if its weights are identical, else this raises:
        the pool must never silently change what a snapshot id plays."""
        path = self.ck_dir / f"{self.run}_snap_u{self.update:04d}.pt"
        obj = self._snapshot_payload()
        if path.exists():
            old = torch.load(path, map_location="cpu")["model"]
            if set(old) != set(obj["model"]) or not all(torch.equal(old[k], obj["model"][k]) for k in old):
                raise RuntimeError(f"snapshot {path} already exists with DIFFERENT weights (a crash after it was written, "
                                   f"then --resume re-ran update {self.update}); move it aside and resume again")
            self.log(f"[rl] {path.name} already exists with identical weights -- kept")
        else:
            self._atomic_save(obj, path)
        try:
            rel = path.resolve().relative_to(REPO).as_posix()
        except ValueError:
            rel = str(path)
        snaps = self.league["snapshots"]
        snaps.append({"id": f"snap_u{self.update:04d}", "update": int(self.update), "path": rel})
        keep = int(self.cfg["league_snapshot_keep"])
        evicted = snaps[:-keep]
        del snaps[:-keep]
        return snaps[-1]["id"], [REPO / e["path"] for e in evicted]

    def _delete_evicted(self, files: list[Path]) -> list[str]:
        """Delete evicted snapshot files: only this run's own ``_snap_`` files inside its checkpoint dir (a numbered
        checkpoint ``_uNNNN.pt`` is a separate file and is never touched here)."""
        gone = []
        for f in files:
            f = Path(f)
            if f.resolve().parent == self.ck_dir.resolve() and f.name.startswith(f"{self.run}_snap_u"):
                f.unlink(missing_ok=True)
                gone.append(f.name)
        return gone

    # ---- entries ---------------------------------------------------------------------------------
    def _entries(self) -> tuple[list[dict], list[dict]]:
        """The RoyaleSim-loadable train and held-out entries (pool file order), cached to entries.json in the run dir
        (loadable = ``RoyalePoolEnv().reset(entry)`` does not raise UnsupportedDeck; measured 299 / 58)."""
        from pipeline.e1_pool import load_pool_v1, select_split, sha256_file
        pool = REPO / self.cfg["pool"]
        frozen = json.loads(pool.with_name(pool.stem + "_split.json").read_text(encoding="utf-8"))
        sha = sha256_file(pool)
        if sha != frozen["pool_sha256"]:
            raise SystemExit(f"REFUSING: pool sha256 {sha} != frozen split's {frozen['pool_sha256']}")
        rows = load_pool_v1(pool)
        tr, ho = select_split(rows, "train"), select_split(rows, "heldout")
        cache = self.run_dir / "entries.json"
        if cache.exists():
            c = json.loads(cache.read_text(encoding="utf-8"))
            if c["pool_sha256"] != sha:
                raise SystemExit("REFUSING: entries.json was built from a different pool")
            keep_tr, keep_ho = set(c["train"]), set(c["heldout"])
        else:
            from pipeline.royale_env import RoyalePoolEnv, UnsupportedDeck
            env = RoyalePoolEnv(decision_ticks=int(self.cfg["decide_every"]))

            def ok(e):
                try:
                    env.reset(e)
                    return True
                except UnsupportedDeck:
                    return False
            keep_tr = {e["tag"] for e in tr if ok(e)}
            keep_ho = {e["tag"] for e in ho if ok(e)}
            cache.write_text(json.dumps({"pool_sha256": sha, "train": [e["tag"] for e in tr if e["tag"] in keep_tr],
                                         "heldout": [e["tag"] for e in ho if e["tag"] in keep_ho],
                                         "train_total": len(tr), "heldout_total": len(ho)}, indent=1), encoding="utf-8")
        tr = [e for e in tr if e["tag"] in keep_tr]
        ho = [e for e in ho if e["tag"] in keep_ho]
        self.pool_sha = sha
        return tr, ho

    def screen_entries(self) -> list[dict]:
        n = int(self.cfg["screen_entries"])
        return self.heldout[:n] if n else self.heldout

    # ---- evals -----------------------------------------------------------------------------------
    def _load_net(self, path: Path):
        """A checkpoint's network on the learner device, eval(): GenModel via eval_gen.load_model for a generalist
        run, else engine_play.load_model's S1Model (unchanged)."""
        if getattr(self, "gen", None):
            from pipeline.eval_gen import load_model
            return load_model(path, self.dev)[0].eval()
        from pipeline import engine_play as ep
        return ep.load_model(path, str(self.dev))[0]

    def _load_phi_net(self, ick: dict):
        """``shaping: value_phi``: the frozen net (``shaping_phi_ckpt``, null = the init) on the learner device, eval,
        no grad. Refuses a checkpoint whose row inputs differ from the learner's (gen / feature_version / d_c /
        card_vocab), since Phi runs on the learner's recorded rows."""
        ck = adv_cfg(self.cfg)["shaping_phi_ckpt"] or self.cfg["init"]
        path = REPO / ck
        if not path.exists():
            raise SystemExit(f"shaping_phi_ckpt {ck} not found")
        pck = torch.load(path, map_location="cpu")
        sig = (lambda c: (bool(c.get("gen")), c.get("d_c"), list(c.get("card_vocab") or []),
                          int(c["args"].get("feature_version", 1))))
        if sig(pck) != sig(ick):
            raise SystemExit(f"shaping_phi_ckpt {ck}: row inputs differ from the init (gen, d_c, card_vocab, "
                             f"feature_version)")
        net = self._load_net(path)
        if net.value_head.out_features != 7:
            raise SystemExit(f"shaping_phi_ckpt {ck}: not the 7-class crown-difference value head")
        for p in net.parameters():
            p.requires_grad_(False)
        return net.eval()

    def _phi_values(self, Bn: dict) -> np.ndarray:
        """``value_rows`` of the frozen Phi net on the numpy batch ``collate`` built (its model-input keys only)."""
        keys = E.gen_row_keys(self.phi_net) if "hand_card" in Bn else ("tok", "mask", "sc", "past")
        return value_rows(self.phi_net, to_device({k: Bn[k] for k in (*keys, "A")}, self.dev)).cpu().numpy()

    def proagree(self, model) -> dict:
        """plan diff 3: train_s1.evaluate on v3 VAL clean (the eval_s1 instrument), first ``proagree_rows`` rows.
        Generalist: eval_gen.evaluate (train_s1.evaluate line for line, hand-position card) on the SAME v3 VAL rows as
        dataset_gen marks them (``v3val == 1`` in ``proagree_data_gen``), first ``proagree_rows``."""
        if getattr(self, "gen", None):
            from pipeline.eval_gen import GenRows, evaluate as evaluate_gen
            if self._rows is None:
                arrs, meta = gen_v3val_arrays(REPO / self.cfg["proagree_data_gen"], int(self.cfg["proagree_rows"]))
                if meta["card_vocab"] != self.gen["card_vocab"]:
                    raise SystemExit("proagree_data_gen card_vocab differs from the init checkpoint's")
                if getattr(model, "feature_version", 1) >= 3 and not all(k in arrs for k in E.GEN_V3_KEYS):
                    raise SystemExit("v3 pro-agreement requires a v3 proagree_data_gen with unit_form and opp_past")
                fv = int(getattr(model, 'feature_version', 1))
                want = 5 if fv == 6 else fv          # fv6 reads fv5 data (train_gen.py expected_data_version)
                if fv >= 4 and int(meta.get('feature_version', 1)) != want:
                    raise SystemExit(f'v3.1+ pro-agreement for an fv{fv} model requires public-only fv{want} data')
                self._rows = GenRows(arrs, np.arange(len(arrs["y_gate"])), self.dev)
            ev = evaluate_gen(model, self._rows, grid=self.grid)
            model.eval()
            return {k: (float(v) if isinstance(v, (float, np.floating)) else v) for k, v in ev.items()}
        from pipeline.dataset import load as load_ds
        from pipeline.train_s1 import Rows, evaluate
        if self._rows is None:
            arrs, _ = load_ds(REPO / self.cfg["proagree_data"])
            idx = np.where(arrs["split"] == 1)[0]
            n = int(self.cfg["proagree_rows"])
            self._rows = Rows(arrs, idx[:n] if n else idx, self.dev)
        ev = evaluate(model, self._rows, grid=self.grid)
        model.eval()
        return {k: (float(v) if isinstance(v, (float, np.floating)) else v) for k, v in ev.items()}

    def screen(self, model=None) -> dict:
        jobs = [(i, e, int(k)) for i, e in enumerate(self.screen_entries()) for k in self.cfg["screen_seeds"]]
        res, skipped, st = self.actors.run("screen", self.update, state_bytes(model or self.model), jobs)
        out = screen_score(res, self.base.get("init_screen"))
        out["skipped"] = len(skipped)
        return out

    # ---- checkpoints -----------------------------------------------------------------------------
    def _rl_state(self) -> dict:
        return {"update": int(self.update), "beta": float(self.beta), "optimizer": self.opt.state_dict(),
                **({"branch_optimizer": self.branch_opt.state_dict()}
                   if getattr(self, "branch_opt", None) is not None else {}),
                "rng": _py(self.rng.bit_generator.state), "visits": list(map(int, self.visits)),
                "config": _py(self.cfg), "config_sha256": config_sha(self.cfg), "run": self.run,
                "init": str(self.cfg["init"]), "pool_sha256": self.pool_sha,
                "runtime": getattr(self, "runtime", None),
                "baselines": _py({**self.base, "init_screen": self.base.get("init_screen")}),
                "guards": _py(self.guards.s), **({"league": _py(self.league)} if getattr(self, "league", None) else {})}

    def _payload(self, val: Optional[dict]) -> dict:
        args = dict(self.init_meta["args"]) | {"rl_run": self.run, "rl_init": str(self.cfg["init"])}
        out = {"model": self.model.state_dict(), "args": _py(args), "deck": self.init_meta["deck"],
               "epoch": self.init_meta["epoch"], "val": _py(val or {}), "n_params": int(self.init_meta["n_params"]),
               "rl": self._rl_state()}
        if getattr(self, "gen", None):                       # train_gen's keys: eval_gen / e1_eval.load_policy load it
            out.update({"gen": True, "d_c": int(self.gen["d_c"]), "card_vocab": list(self.gen["card_vocab"])})
        return out

    def _atomic_save(self, obj: dict, path: Path) -> None:
        assert CKPT_ROOT.resolve() in path.resolve().parents, f"refusing to write {path} outside {CKPT_ROOT}"
        tmp = path.with_name(path.name + ".tmp")
        torch.save(obj, tmp)
        os.replace(tmp, path)

    def save(self, val: Optional[dict], numbered: bool) -> Optional[Path]:
        """``<run>_latest.pt`` always; ``<run>_u{NNNN}.pt`` (NNNN = updates done) when ``numbered``, never overwritten:
        if it already exists (crash after it, before _latest; resume re-ran the update) it is logged and kept."""
        obj = self._payload(val)
        path = None
        if numbered:
            path = self.ck_dir / f"{self.run}_u{self.update:04d}.pt"
            if path.exists():                                   # a crash between this save and _latest, then --resume
                self.log(f"[rl] {path.name} already exists (an earlier attempt at this update) -- kept, not overwritten")
            else:
                self._atomic_save(obj, path)
        self._atomic_save(obj, self.ck_dir / f"{self.run}_latest.pt")
        return path

    def crash_save(self, why: str) -> Path:
        path = self.ck_dir / f"{self.run}_crash_u{self.update:04d}_{int(time.time())}.pt"
        obj = self._payload(None)
        obj["rl"]["crash"] = why[-4000:]
        self._atomic_save(obj, path)
        return path

    def _restore(self, path: Path) -> None:
        ck = torch.load(path, map_location=self.dev)          # weights_only (the default): proves the layout loads
        rl = ck["rl"]
        if getattr(self, "runtime", None) is not None:
            from pipeline.royale_runtime import require_same
            require_same(rl.get("runtime"))
        self.model.load_state_dict(ck["model"])
        self.model.eval()
        self.opt.load_state_dict(rl["optimizer"])
        if getattr(self, "branch_opt", None) is not None and "branch_optimizer" in rl:
            self.branch_opt.load_state_dict(rl["branch_optimizer"])
        self.update, self.beta = int(rl["update"]), float(rl["beta"])
        self.rng.bit_generator.state = rl["rng"]
        self.visits = list(rl["visits"])
        self.base = dict(rl["baselines"])
        self.guards = Guards(self.cfg, rl["guards"])
        if getattr(self, "league", None) is not None:
            self.league = dict(rl.get("league") or {"snapshots": []})
        if "leash" not in rl["config"] and self.cfg.get("leash", "cell") != "cell":
            self.log(f"[rl] RESUME of a run from before the leash key: leash stays 'cell' (was {self.cfg['leash']!r} "
                     f"in this config) -- the old run's beta rule")
            self.cfg["leash"] = "cell"
        if rl["config_sha256"] != config_sha(self.cfg):
            diff = {k: (rl["config"].get(k), v) for k, v in self.cfg.items() if rl["config"].get(k) != v}
            self.log(f"[rl] RESUME with a changed config (old, new): {diff}")
        if len(self.visits) != len(self.train):
            raise SystemExit("REFUSING resume: the train entry list changed length")

    # ---- one update ------------------------------------------------------------------------------
    def rollout(self, u: int) -> tuple[list[dict], dict]:
        E_, G = int(self.cfg["E"]), int(self.cfg["G"])
        if getattr(self, "league", None) is not None:           # league: E self-play matchups x G rollouts
            specs = sample_matchups(self.rng, E_, u, self.league["snapshots"], self.cfg, self.census, self.census_p)
            jobs = [(i, sp, g) for i, sp in enumerate(specs) for g in range(G)]
            res, skipped, st = self.actors.run("selfplay", u, state_bytes(self.model), jobs)
            if skipped:
                self.log(f"[rl] WARNING {len(skipped)} self-play rollout(s) skipped: {skipped[:3]}")
            return res, {"picked": [], "actors": st, "skipped": len(skipped),
                         "league": [{"opp": sp["opp"]["id"], "learner_deck": sp["learner_deck_name"],
                                     "opp_deck": sp["opp_deck_name"], "side": sp["learner_side"]} for sp in specs]}
        pick = self.rng.choice(len(self.train), size=min(E_, len(self.train)), replace=False)
        for i in pick:
            self.visits[int(i)] += 1
        jobs = [(int(i), self.train[int(i)], g) for i in pick for g in range(G)]
        res, skipped, st = self.actors.run("rollout", u, state_bytes(self.model), jobs)
        if skipped:
            self.log(f"[rl] WARNING {len(skipped)} rollout(s) skipped as unsupported: {skipped[:3]}")
        return res, {"picked": [int(i) for i in pick], "actors": st, "skipped": len(skipped)}

    def _branch_send(self, u: int, bc: dict) -> None:
        """Start of update u: the weights the PPO actors get (version u) + BRANCH_SPECS_PER_SEND fresh matchups per
        worker, drawn like the PPO matchups (``sample_matchups``) from an rng of their own (seed, update): the learner's
        rng -- PPO's matchups, minibatch order -- is not touched. Non-blocking."""
        rng = np.random.default_rng(zlib.crc32(f"branch:{int(self.cfg['seed'])}:{int(u)}".encode()))
        n = int(bc["branch_actors"])
        specs = sample_matchups(rng, BRANCH_SPECS_PER_SEND * n, u, self.league["snapshots"], self.cfg, self.census,
                                self.census_p)
        self.branch_pool.send(u, state_bytes(self.model), [specs[w::n] for w in range(n)])

    def _branch_optimizer(self, bc: dict):
        """The branch step's OWN Adam over the same parameters, lr ``branch_lr`` (null = the PPO lr): PPO's Adam
        moments never move the policy outside PPO's steps (with the shared Adam, coef 0 still moved the params by the
        leftover PPO momentum -- verifier), and they stay untouched by the branch step."""
        lr = bc["branch_lr"] if bc["branch_lr"] is not None else self.cfg["lr"]
        return torch.optim.Adam(self.model.parameters(), lr=float(lr))

    def _branch_update(self, samples: list[dict], bc: dict, apply: bool, u: int) -> dict:
        """The samples drained this update: those labelled under weights older than ``branch_max_staleness`` updates
        (u - version) are dropped; the rest -> monitors (``branch_stats``), and the kept ones (|delta| >= min) join the
        FIFO replay buffer (last ``branch_buffer``); buffer rows whose version is older than u - branch_buffer_max_age
        are evicted; ``apply`` (not warm-up, no crash) -> ONE ``branch_step`` on the whole buffer with the branch's own
        Adam (``branch_opt``). ponytail: the buffer is not checkpointed -- a --resume starts it empty."""
        lag = [int(u) - int(x["version"]) for x in samples]
        fresh = [x for x, g in zip(samples, lag) if g <= int(bc["branch_max_staleness"])]
        st = branch_stats(fresh, bc["branch_min_abs_delta"], bc["branch_kinds"])
        st.update({"drained": len(samples), "stale_dropped": len(samples) - len(fresh),
                   "staleness_mean": float(np.mean(lag)) if lag else None,
                   "by_worker": dict(Counter(int(x.get("worker", -1)) for x in samples))})
        samples = fresh
        buf = self.__dict__.setdefault("branch_buf", [])
        buf += [x for x in samples if abs(x["delta"]) >= bc["branch_min_abs_delta"]]
        n0 = len(buf)
        buf[:] = [x for x in buf if int(u) - int(x["version"]) <= int(bc["branch_buffer_max_age"])]
        aged = n0 - len(buf)
        del buf[:-int(bc["branch_buffer"])]
        st.update({"buffer": len(buf), "buffer_aged_out": aged, "step": None})
        if apply and buf:
            if getattr(self, "branch_opt", None) is None:
                self.branch_opt = self._branch_optimizer(bc)
            t = time.perf_counter()
            st["step"] = branch_step(self.model, self.branch_opt, branch_batches(buf, self.dev), self.cfg,
                                     {k: bc[BRANCH_KIND_KEYS[k][1]] for k in BRANCH_KIND_KEYS})
            st["step"]["wall_s"] = time.perf_counter() - t
        return st

    def one_update(self, u: int) -> tuple[dict, list[str], bool]:
        cfg, t0 = self.cfg, time.perf_counter()
        if self.dev.type == "cuda":
            torch.cuda.reset_peak_memory_stats(self.dev)
        if branch_cfg(cfg)["branch_gate"]:                    # opt3: this update's weights to the branch workers
            self._branch_send(u, branch_cfg(cfg))
        results, rinfo = self.rollout(u)
        t_roll = time.perf_counter() - t0
        mon = rollout_monitors(results, cfg["tau"], cfg["T"])
        league = getattr(self, "league", None) is not None
        if league:
            mon["league"] = league_monitors(results)
        ac = adv_cfg(cfg)
        gae_on = ac["advantage"] == "gae"
        shp = ({"gamma": ac["gae_gamma"], "w_tower": ac["shaping_w_tower"], "w_crown": ac["shaping_w_crown"]}
               if ac["shaping"] == "tower_crown" else None)
        if ac["shaping"] == "value_phi":
            shp = {"mode": "value_phi", "gamma": ac["gae_gamma"], "w_value": ac["shaping_w_value"],
                   "window_ticks": int(round(ac["shaping_phi_window_s"] / E.TICK_S)), "phi_fn": self._phi_values}
        tick_unit = gae_on and ac["gae_gamma_unit"] == "tick"
        Bn, bst = collate(results, float(cfg["adv_clip"]), advantage=ac["advantage"], shaping=shp,
                          **({"gamma_tick": ac["gae_gamma_tick"]} if tick_unit else {}),
                          **({"gae_terminal_gap": True} if ac["gae_terminal_gap"] else {}))
        gamma_row_mean = float(Bn["gamma_row"].mean()) if tick_unit and len(Bn["gamma_row"]) else None
        del results
        t1 = time.perf_counter()
        B = to_device(Bn, self.dev)
        R = ref_terms(self.ref, B, cfg["tau"], cfg["T"])
        beta_used = self.beta
        vf = gst = None
        warm = gae_on and self.update < ac["critic_warmup_updates"]        # critic warm-up: policy frozen
        if gae_on:
            gst = gae_batch(self.model, B, cfg)
            vf = {"coef": ac["vf_coef"], "clip": ac["vf_clip"], "policy": not warm, "trunk_grad": ac["vf_trunk_grad"]}
            gst["vf_trunk_share"] = None if warm else vf_grad_share(self.model, B, R, cfg, beta_used, vf)
        upd = ppo_update(self.model, self.opt, B, R, cfg, beta_used, self.rng, vf=vf)
        t_upd = time.perf_counter() - t1
        first = upd["first"]
        if u == 0 and not upd["nonfinite"]:
            bad = first["ratio_maxdev"] >= ASSERT_RATIO or max(first["kl_gate"], first["kl_card"], first["kl_cell"]) >= ASSERT_KL
            assert not bad, (f"ON-POLICY CHECK FAILED at update 0 epoch 0 minibatch 0: max|ratio-1| "
                             f"{first['ratio_maxdev']:.3g} (< {ASSERT_RATIO}), KL gate/card/cell {first['kl_gate']:.3g}/"
                             f"{first['kl_card']:.3g}/{first['kl_cell']:.3g} (< {ASSERT_KL}), lp max diffs "
                             f"{first['lp_maxdiff']} -- a bug between the stored forward and the recompute")
        reasons, crash = [], False
        if upd["nonfinite"]:
            reasons.append(f"non-finite {upd['nonfinite']}")
            crash = True
        elif not all(bool(torch.isfinite(p).all()) for p in self.model.parameters()):
            reasons.append("non-finite parameters after the update")
            crash = True
        bc, brst = branch_cfg(cfg), None
        if bc["branch_gate"]:                                   # opt3: drain (never waits), ONE gate-BCE step, after PPO
            drained, pinfo = self.branch_pool.drain()
            brst = self._branch_update(drained, bc, apply=not crash and not warm, u=u)
            brst["pool"] = pinfo
            if brst["step"] and not all(bool(torch.isfinite(p).all()) for p in self.model.parameters()):
                reasons.append("non-finite parameters after the branch step")
                crash = True
        leash = cfg.get("leash", "cell")
        kl_leash, kl_driver = leash_kl(upd, leash)
        if not crash:
            if not warm:                                        # warm-up: no KL step (the policy did not move)
                self.beta = adapt_beta(beta_used, kl_leash, float(cfg["kl_target"]), float(cfg["beta_min"]),
                                       float(cfg["beta_max"]))
            if u == 0 and self.guards.s["base"] is None:
                self.guards.set_baselines(mon)
                self.log(f"[rl] update-0 plays/min baseline {self.guards.s['base']['plays_per_min']:.3f} (stop outside "
                         f"[{cfg['plays_lo']}, {cfg['plays_hi']}]x for {cfg['stop_consecutive']} updates)")
            reasons += self.guards.after_update(mon, beta_used, upd["kl_cell"] or 0.0, upd["kl_gate"] or 0.0,
                                                ent=upd["ent"], ent_init=R["ent"])
            self.update = u + 1                                 # a crashed update is not counted (crash save = u)
        else:
            self.log(f"[rl] NON-FINITE at update {u}: {reasons[0]}; crash save, {self.run}_latest.pt left at the last "
                     f"good update ({self.update} done)")
        rec = {"type": "update", "update": u, "time": time.strftime("%Y-%m-%d %H:%M:%S"), **mon, **bst,
               "kl_gate": upd["kl_gate"], "kl_card": upd["kl_card"], "kl_cell": upd["kl_cell"], "beta_used": beta_used,
               "beta_next": self.beta, "kl_target": cfg["kl_target"], "leash": leash, "kl_leash": kl_leash,
               "kl_driver": kl_driver, "l_pg": upd["l_pg"],
               "entropy": upd["ent"], "entropy_init": R["ent"], "clip_frac": upd["clip_frac"],
               "ratio_mean": upd["ratio_mean"], "grad_norm_mean": upd["grad_norm_mean"],
               "first_minibatch": {k: first[k] for k in ("ratio_maxdev", "kl_gate", "kl_card", "kl_cell", "lp_maxdiff")},
               "picked": rinfo["picked"], "skipped": rinfo["skipped"],
               **({"matchups": rinfo["league"]} if league else {}), "visits_distinct": sum(v > 0 for v in self.visits),
               "visits_max": max(self.visits), "guards": copy.deepcopy(self.guards.s),
               "wall_rollout_s": t_roll, "wall_update_s": t_upd,
               "actor_s_per_match": {a: s["wall_s"] / max(s["matches"], 1) for a, s in rinfo["actors"].items()},
               "actor_gpu_peak_mb": {a: s["gpu_peak_mb"] for a, s in rinfo["actors"].items()}}
        if gae_on:
            rec["gae"] = {**gst, "l_v": upd["l_v"], "l_v_first": upd["l_v_first"], "critic_warmup": warm,
                          "gamma": ac["gae_gamma"], "lambda": ac["gae_lambda"], "vf_coef": ac["vf_coef"],
                          "vf_trunk_grad": ac["vf_trunk_grad"], "shaping": ac["shaping"]}
            if tick_unit:
                rec["gae"].update({"gamma_unit": "tick", "gamma_tick": ac["gae_gamma_tick"],
                                   "gamma_row_mean": gamma_row_mean})
        if brst is not None:
            rec["branch"] = {**brst, "coef": bc["branch_coef"], "min_abs_delta": bc["branch_min_abs_delta"],
                             "buffer_cap": bc["branch_buffer"], "max_staleness": bc["branch_max_staleness"],
                             **({"kinds": bc["branch_kinds"], "card_coef": bc["branch_card_coef"],
                                 "xbow_coef": bc["branch_xbow_coef"]} if bc["branch_kinds"] != ["hold"] else {})}
        del B, R
        if not crash:
            u1 = self.update
            if u1 % int(cfg["screen_every"]) == 0:
                t = time.perf_counter()
                rec["screen"] = self.screen()
                rec["wall_screen_s"] = time.perf_counter() - t
                r = self.guards.screen(rec["screen"]["delta_pp"], rec["screen"]["ci_hi_pp"])
                reasons += ([r] if r else []) + self._screen_exploit(rec["screen"])
                if rec["screen"]["delta_pp"] is None:
                    self.log(f"[rl] held-out screen after update {u} had NO paired matches -- counted as no screen")
            if u1 % int(cfg["proagree_every"]) == 0:
                t = time.perf_counter()
                pa = self.proagree(self.model)
                rec["proagree"] = {k: pa[k] for k in PA_KEYS + ("cell_tile_top1",)}
                rec["proagree_delta_pp"] = {k: 100 * (pa[k] - self.base["init_proagree"][k]) for k in PA_KEYS}
                self.latest_pa = pa
                init = self.base["init_proagree"]
                r = hard_stop_reason(pa, init, cfg)
                cell_low = pa["cell_half_top1"] < init["cell_half_top1"] - cfg["tripwire_cell_pp"] / 100
                if not r and cell_low and self.guards.s["latest_screen_delta_pp"] is None:
                    rec["screen"] = self.screen()                 # the tripwire needs a screen; none has run yet
                    r2 = self.guards.screen(rec["screen"]["delta_pp"], rec["screen"]["ci_hi_pp"])
                    reasons += ([r2] if r2 else []) + self._screen_exploit(rec["screen"])
                    if rec["screen"]["delta_pp"] is None:
                        self.log("[rl] forced tripwire screen had NO paired matches -- tripwire cannot fire this update")
                r = r or tripwire_reason(pa, init, self.guards.s["latest_screen_delta_pp"], cfg)
                reasons += [r] if r else []
                rec["wall_proagree_s"] = time.perf_counter() - t
            if (self.run_dir / "STOP").exists():
                reasons.append("STOP file present")
        if "screen" in rec:
            rec["screen"] = {k: v for k, v in rec["screen"].items() if k != "per_key"}
            rec["screen_guards"] = {"init": rec["screen"].get("exploit_init"), "cand": rec["screen"].get("exploit_cand")}
        t = time.perf_counter()
        if crash:
            rec["crash_ckpt"] = str(self.crash_save("; ".join(reasons)))
        else:
            evicted: list = []
            if league and self.update % int(cfg["league_snapshot_every"]) == 0:
                rec["snapshot"], evicted = self._snapshot()
            if league:
                rec["league_pool"] = [x["id"] for x in self.league["snapshots"]]
            numbered = self.save(self.latest_pa if "proagree" in rec else None,
                                 self.update % int(cfg["save_every"]) == 0)
            rec["ckpt"] = str(numbered) if numbered else None
            if evicted:                                       # only now: _latest.pt no longer names them
                rec["snapshot_deleted"] = self._delete_evicted(evicted)
        rec["wall_save_s"] = time.perf_counter() - t
        rec["wall_total_s"] = time.perf_counter() - t0
        rec["learner_gpu_peak_mb"] = torch.cuda.max_memory_allocated(self.dev) / 2**20 if self.dev.type == "cuda" else None
        rec["stop"] = reasons
        self.log.json(rec)
        f = (lambda v, s="{:.3f}": "-" if v is None else s.format(v))
        shs = bst.get("shaping")                                # R2 monitors (shaping on only)
        self.log(f"[rl] u{u:04d} W/L/D {mon['W']}/{mon['L']}/{mon['D']} ppm {f(mon['plays_per_min'], '{:.2f}')} "
                 f"pgate {f(mon['p_gate_mean'])} KL g/c/x {f(upd['kl_gate'], '{:.4f}')}/{f(upd['kl_card'], '{:.4f}')}/"
                 f"{f(upd['kl_cell'], '{:.4f}')} beta {beta_used:.3g}->{self.beta:.3g}"
                 + (f" (leash max: {kl_driver})" if leash == "max" else "") + f" clip {f(upd['clip_frac'])} "
                 f"mixed {bst['mixed_groups']}/{bst['groups']} rows {bst['rows']} "
                 f"wall roll {t_roll:.0f}s upd {t_upd:.0f}s"
                 + (f" | gae{' WARMUP (critic only)' if warm else ''} vloss {f(upd['l_v'], '{:.4f}')} ev "
                    f"{f(gst['explained_var'])} A {f(gst['adv_mean'], '{:+.4f}')}/{f(gst['adv_std'], '{:.4f}')} "
                    f"ret {f(gst['ret_mean'], '{:+.3f}')} V {f(gst['v_mean'], '{:+.3f}')} vshare "
                    f"{f((gst['vf_trunk_share'] or {}).get('share'))}" if gae_on else "")
                 + (f" | shape |F| {f(shs['mean_abs_F'], '{:.4f}')} (t {f(shs['mean_abs_tower'], '{:.4f}')} c "
                    f"{f(shs['mean_abs_crown'], '{:.4f}')}) |Phi| {f(shs['mean_abs_phi'], '{:.4f}')} dom "
                    f"{f(shs['shaping_dominates'])}" if shs and shs.get("mode") != "value_phi" else "")
                 + (f" | vphi |F| {f(shs['mean_abs_F'], '{:.4f}')} |Phi| {f(shs['mean_abs_phi'], '{:.4f}')} share "
                    f"{f(gst['phi_share'])} dPhi std {f(shs['phi_step_std'], '{:.4f}')} (raw "
                    f"{f(shs['raw_step_std'], '{:.4f}')}) end-corr {f(shs['phi_end_corr'], '{:+.3f}')}"
                    if shs and shs.get("mode") == "value_phi" else "")
                 + (f" | branch n {brst['n']}/{brst['emitted']} hold+ {f(brst['hold_better_share'])} d "
                    f"{f(brst['mean_delta'], '{:+.3f}')}"
                    + "".join(f" [{ph} {v['n']} {f(v['hold_better_share'])} {f(v['mean_delta'], '{:+.3f}')}]"
                              for ph, v in brst["by_phase"].items())
                    + "".join(f" <{k} {v['n']}/{v['emitted']} b+ {f(v['b_better_share'])} d "
                              f"{f(v['mean_delta'], '{:+.3f}')}"
                              + (f" bce {f(brst['step']['by_kind'][k]['bce_before'], '{:.4f}')}->"
                                 f"{f(brst['step']['by_kind'][k]['bce_after'], '{:.4f}')}"
                                 if brst["step"] and k in brst["step"].get("by_kind", {}) else "") + ">"
                              for k, v in brst.get("by_kind", {}).items())
                    + f" buf {brst['buffer']} aged-{brst['buffer_aged_out']}"
                    + (f" bce {f(brst['step']['bce_before'], '{:.4f}')}->{f(brst['step']['bce_after'], '{:.4f}')} "
                       f"|dP| {f(brst['step']['dp_abs_mean'], '{:.5f}')}"
                       + (f" SKIPPED {brst['step']['skipped']}" if brst["step"]["skipped"] else "")
                       if brst["step"] else " (no step)")
                    + f" | drained {brst['drained']} stale-{brst['stale_dropped']} lag {f(brst['staleness_mean'], '{:.1f}')}"
                    f" workers {brst['pool']['alive']}/{bc['branch_actors']} err {brst['pool']['errors']}"
                    + (f" restarted {brst['pool']['restarted']}" if brst["pool"]["restarted"] else "")
                    if brst is not None else "")
                 + (" | league wr " + " ".join(f"{t} {f(v['winrate'], '{:.2f}')}/{v['n']}"
                                               for t, v in mon["league"]["by_opp"].items())
                    + f" D {mon['league']['draws']}" + (f" +{rec['snapshot']}" if "snapshot" in rec else "")
                    if league else "")
                 + (f" | screen {f(rec['screen']['winrate'])} d {f(rec['screen']['delta_pp'], '{:+.1f}')}pp "
                    f"CI [{f(rec['screen']['ci_lo_pp'], '{:+.1f}')}, {f(rec['screen']['ci_hi_pp'], '{:+.1f}')}] "
                    f"(+{rec['screen']['better']}/-{rec['screen']['worse']}) {exploit_str(rec['screen'])}"
                    if "screen" in rec else "")
                 + (f" | proagree cell {rec['proagree']['cell_half_top1']:.4f} card {rec['proagree']['card_top1']:.4f} "
                    f"gate {rec['proagree']['gate_bal_acc']:.4f}" if "proagree" in rec else ""))
        return rec, reasons, crash

    def _screen_exploit(self, sc: dict) -> list[str]:
        if sc.get("exploit_init") is None:
            self.log("[rl] screen exploit guards SKIPPED: the cached init screen has no per-match exploit fields")
            return []
        return exploit_reasons(sc["exploit_init"], sc["exploit_cand"], self.cfg)

    def rebuild_init_screen(self) -> None:
        """--resume of a run whose cached init screen is outcome-only (older code): re-run it with the frozen INIT
        weights (greedy live rule, eval seeds: the same matches) so the screen exploit guards have their init side."""
        t = time.perf_counter()
        sc = self.screen(self.ref)
        old = self.base.get("init_screen") or {}
        same = sum(1 for k, v in sc["per_key"].items() if k in old and not isinstance(old[k], dict) and float(old[k]) == v["v"])
        self.base["init_screen"] = sc["per_key"]
        self.log(f"[rl] init screen rebuilt with the init weights for the exploit guards: {sc['n']} matches, "
                 f"{same}/{len(old)} outcomes identical to the cached ones, {exploit_str({'exploit': sc['exploit']})} "
                 f"({time.perf_counter() - t:.0f}s)")

    # ---- startup + loop --------------------------------------------------------------------------
    def actor_base(self) -> dict:
        """What every actor process gets: the decide-rule keys, the model shape (``gen`` = GenModel extras or None)
        and the condition keys (``COND_KEYS``) that ``actor_cfg`` puts into rollout AND screen matches."""
        a = self.init_meta["args"]
        base = {k: self.cfg[k] for k in ("actor_threads", "actor_device", "tau", "T", "afford_mask", "stall_elixir",
                                         "stall_seconds", "obs", "decide_every", "in_flight")}
        base.update({"d": int(a.get("d", 128)), "layers": int(a.get("layers", 4)), "grid": self.grid})
        base.update({k: self.cfg.get(k) for k in COND_KEYS})
        base["gen"] = getattr(self, "gen", None)
        base["runtime"] = getattr(self, "runtime", None)
        base["league_opp_policy"] = self.cfg.get("league_opp_policy", "sample")
        base["hero_abilities"] = self.cfg.get("hero_abilities", False)
        if type(base["hero_abilities"]) is not bool:
            raise SystemExit("hero_abilities must be a bool")
        base["ability_policy"] = self.cfg.get("ability_policy", "generic")
        if base["ability_policy"] not in ("generic", "v2"):
            raise SystemExit(f"ability_policy must be generic or v2, got {base['ability_policy']!r}")
        base["forms_mode"] = self.cfg.get("forms_mode", "base")
        if base["forms_mode"] not in ("base", "deck"):
            raise SystemExit(f"forms_mode must be base or deck, got {base['forms_mode']!r}")
        if self.cfg.get("shaping", "none") != "none":         # R2: actor_cfg -> record_phi (absent by default)
            base["shaping"] = self.cfg["shaping"]
        if self.cfg.get("gae_gamma_unit", "row") != "row":    # actor_cfg -> record_tick (absent by default)
            base["gae_gamma_unit"] = self.cfg["gae_gamma_unit"]
        return base

    def start_actors(self) -> None:
        base = self.actor_base()
        self.actors = ActorPool(base, int(self.cfg["n_actors"]), self.log, self.cfg["actor_timeout_s"],
                                pid_file=self.run_dir / "actors.pid")
        (self.run_dir / "pid.json").write_text(json.dumps({"learner": os.getpid(), "actors": self.actors.pids}),
                                               encoding="utf-8")
        bc = branch_cfg(self.cfg)
        if bc["branch_gate"]:                                   # opt3: the branch workers (their own pids file)
            self.branch_pool = BranchPool({**base, "branch": bc}, bc["branch_actors"], self.log,
                                          pid_file=self.run_dir / "branch_workers.pid")

    def startup(self, smoke: bool) -> None:
        """Fresh run: init pro agreement, init held-out screen (both cached in the run dir), u0000 before any update."""
        cfg, log = self.cfg, self.log
        log(f"[rl] run {self.run}: train {len(self.train)} loadable, held-out {len(self.heldout)} loadable "
            f"(screen uses {len(self.screen_entries())}); init {cfg['init']} ({'GENERALIST' if self.gen else 'S1'}) "
            f"grid {self.grid}; conditions (rollouts + screens): "
            + " ".join(f"{k}={cfg.get(k)}" for k in COND_KEYS) + f"; leash {cfg.get('leash', 'cell')}"
            + ("; advantage gae " + " ".join(f"{k}={v}" for k, v in adv_cfg(cfg).items() if k != "advantage")
               if adv_cfg(cfg)["advantage"] == "gae" else "")
            + ("; BRANCH " + " ".join(f"{k}={v}" for k, v in branch_cfg(cfg).items() if k != "branch_gate"
                                      and (k not in R4_KEYS or branch_cfg(cfg)["branch_kinds"] != ["hold"]))
               if branch_cfg(cfg)["branch_gate"] else ""))
        if self.league is not None:
            log(f"[rl] LEAGUE: {len(self.census)} census decks + icebow (share {cfg['league_icebow_share']}), weights "
                f"sides^{cfg['league_deck_alpha']} floor {cfg['league_deck_floor']}x mean (max p {self.census_p.max():.4f}, "
                f"min {self.census_p.min():.4f}); opponents mix {cfg['league_mix']} (opp policy "
                f"{cfg['league_opp_policy']}), S1 specialist {cfg['league_specialist']} (icebow only); snapshot every "
                f"{cfg['league_snapshot_every']} updates, keep {cfg['league_snapshot_keep']}")
        t = time.perf_counter()
        pa = self.proagree(self.model)
        self.base["init_proagree"] = {k: pa[k] for k in PA_KEYS + ("cell_tile_top1", "n", "n_play")}
        (self.run_dir / "init_proagree.json").write_text(json.dumps(_py(pa), indent=1), encoding="utf-8")
        log(f"[rl] init pro agreement ({pa['n']} VAL rows, {time.perf_counter() - t:.0f}s): cell "
            f"{pa['cell_half_top1']:.4f} card {pa['card_top1']:.4f} gate_bal {pa['gate_bal_acc']:.4f}")
        self.start_actors()
        t = time.perf_counter()
        sc = self.screen()
        self.base["init_screen"] = sc["per_key"]
        (self.run_dir / "init_screen.json").write_text(json.dumps(_py(sc), indent=1), encoding="utf-8")
        log(f"[rl] init held-out screen: {sc['n']} matches, winrate {sc['winrate']:.3f}, plays/min "
            f"{sc['plays_per_min']:.2f}, {exploit_str(sc)} ({time.perf_counter() - t:.0f}s)")
        path = self.save(self.base["init_proagree"], numbered=True)
        log(f"[rl] saved {path}")
        self.log.json({"type": "startup", "init_proagree": pa, "init_screen": {k: v for k, v in sc.items()},
                       "train_loadable": len(self.train), "heldout_loadable": len(self.heldout), "config": cfg})
        if smoke:
            m2 = self._load_net(path)
            pa2 = self.proagree(m2)
            same = all(pa2[k] == pa[k] for k in pa)
            log(f"[rl] SMOKE u0000 round trip via {'eval_gen' if self.gen else 'engine_play'}.load_model: pro "
                f"agreement identical = {same}")
            if not same:
                raise SmokeFail(f"u0000 reload pro agreement {pa2} != in-memory init {pa}")

    def loop(self) -> tuple[int, Optional[str]]:
        for u in range(self.update, int(self.cfg["max_updates"])):
            rec, reasons, crash = self.one_update(u)
            if reasons:
                self.log(f"STOP after update {u}: {' | '.join(reasons)}" + (f" (crash save {rec['crash_ckpt']})" if crash else ""))
                return 0, "; ".join(reasons)
        self.log(f"[rl] DONE: max_updates {self.cfg['max_updates']} reached")
        return 0, None


def exploit_str(sc: dict) -> str:
    """Screen-line text: the three E1 4.2 values, init -> candidate on the paired matches (or the init screen's own)."""
    f = (lambda v: "-" if v is None else f"{v:.3f}")
    keys = (("outlived_win_share", "outlived"), ("low_delivered_win_share", "<=10dlv"), ("ghost_refused_per_match", "refused/m"))
    if sc.get("exploit_cand") is not None:
        return "guards " + " ".join(f"{n} {f(sc['exploit_init'][k])}->{f(sc['exploit_cand'][k])}" for k, n in keys)
    ex = sc.get("exploit") or {}
    return "guards " + " ".join(f"{n} {f(ex.get(k))}" for k, n in keys)


class SmokeFail(AssertionError):
    pass


def smoke_resume_check(cfg, run, run_dir, ck_dir, log, live: Learner) -> None:
    """--smoke: a FRESH learner through the resume path must restore update counter, beta, optimizer and rng."""
    L2 = Learner(cfg, run, run_dir, ck_dir, log, resume=True)
    s1, s2 = live.opt.state_dict(), L2.opt.state_dict()
    checks = {"update": L2.update == live.update == int(cfg["max_updates"]), "beta": L2.beta == live.beta,
              "rng": L2.rng.bit_generator.state == live.rng.bit_generator.state, "visits": L2.visits == live.visits,
              "opt_step": all(float(s1["state"][k]["step"]) == float(s2["state"][k]["step"]) for k in s1["state"]),
              "opt_moments": all(torch.equal(s1["state"][k][m], s2["state"][k][m].to(s1["state"][k][m].device))
                                 for k in s1["state"] for m in ("exp_avg", "exp_avg_sq")),
              "params": all(torch.equal(a, b) for a, b in zip(live.model.state_dict().values(), L2.model.state_dict().values())),
              "guards": json.dumps(_py(L2.guards.s), sort_keys=True) == json.dumps(_py(live.guards.s), sort_keys=True),
              "league": L2.league == live.league}
    if live.league is not None and not live.league["snapshots"]:
        raise SmokeFail("league smoke added no snapshot (set league_snapshot_every small)")
    step = float(next(iter(s2["state"].values()))["step"]) if s2["state"] else None
    log(f"[rl] SMOKE resume check: update {L2.update}, beta {L2.beta}, optimizer step {step}: {checks}")
    bad = [k for k, v in checks.items() if not v]
    if bad:
        raise SmokeFail(f"resume did not restore {bad}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--config", type=Path, default=REPO / "pipeline" / "rl_royale.yaml")
    ap.add_argument("--run", required=True)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("overrides", nargs="*", help="key=value config overrides")
    a = ap.parse_args(argv)
    from pipeline.royale_runtime import activate
    runtime = activate()
    cfg = load_config(a.config, a.overrides, a.smoke)
    run_dir, ck_dir = RUN_ROOT / a.run, CKPT_ROOT / a.run
    if a.resume:
        if not (ck_dir / f"{a.run}_latest.pt").exists():
            raise SystemExit(f"--resume needs {ck_dir / (a.run + '_latest.pt')}")
        if (run_dir / "STOP").exists():
            raise SystemExit(f"REFUSING resume: {run_dir / 'STOP'} exists (delete it first)")
    else:
        for d in (run_dir, ck_dir):   # a pre-seeded entries.json alone is allowed: it pins another run's entry set
            if d.exists() and any(p.name != "entries.json" for p in d.iterdir()):
                raise SystemExit(f"REFUSING: {d} exists and is not empty (new --run name, or --resume)")
    run_dir.mkdir(parents=True, exist_ok=True)
    ck_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / (f"runtime_resume_{int(time.time())}.json" if a.resume else "runtime.json")).write_text(
        json.dumps(runtime, indent=2), encoding="utf-8")
    import yaml
    (run_dir / (f"config_resume_{int(time.time())}.yaml" if a.resume else "config.yaml")).write_text(
        yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    log = Log(run_dir)
    log(f"[rl] runtime {json.dumps(runtime, sort_keys=True)}")
    log(f"[rl] {'RESUME' if a.resume else 'START'} {a.run} pid {os.getpid()} "
        f"{'SMOKE ' if a.smoke else ''}config sha {config_sha(cfg)[:12]} argv {sys.argv[1:] if argv is None else argv}")
    L = None
    try:
        L = Learner(cfg, a.run, run_dir, ck_dir, log, a.resume)
        if a.resume:
            log(f"[rl] resumed at update {L.update}, beta {L.beta}")
            L.start_actors()
            if any(not isinstance(v, dict) for v in (L.base.get("init_screen") or {}).values()):
                L.rebuild_init_screen()
        else:
            L.startup(a.smoke)
        code, why = L.loop()
        if a.smoke:
            if why:
                raise SmokeFail(f"a stop rule fired during the smoke: {why}")
            smoke_resume_check(cfg, a.run, run_dir, ck_dir, log, L)
            log("SMOKE PASS")
        return code
    except SmokeFail as exc:
        log(f"SMOKE FAIL: {exc}")
        return 1
    except BaseException as exc:
        tb = traceback.format_exc()
        log(f"[rl] CRASH: {exc!r}\n{tb}")
        if L is not None:
            try:
                log(f"[rl] crash save {L.crash_save(tb)}")
            except Exception as e2:
                log(f"[rl] crash save failed: {e2!r}")
        if a.smoke:
            log(f"SMOKE FAIL: {exc!r}")
        return 1 if a.smoke else 3
    finally:
        if L is not None and L.actors is not None:
            L.actors.close()
        if L is not None and getattr(L, "branch_pool", None) is not None:
            L.branch_pool.close()
            (run_dir / "branch_workers.pid").unlink(missing_ok=True)
        (run_dir / "pid.json").unlink(missing_ok=True)
        (run_dir / "actors.pid").unlink(missing_ok=True)       # left in place only if the learner is killed hard


if __name__ == "__main__":
    raise SystemExit(main())
