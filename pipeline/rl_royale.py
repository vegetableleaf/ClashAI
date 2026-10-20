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
F6 (``kl_ref_gate: <checkpoint>``, opt-in; absent / null = unchanged, same config hash): KL_gate (and the gate entropy
baseline) is taken to that frozen net -- e.g. the imitation generalist -- instead of the run's own init; card and cell
keep the init ref (``ref_terms(gate_ref=)``, ``Learner._load_gate_ref``). The update-0 KL check then skips KL_gate.
K1 (step d, opt-in; absent / null = unchanged, same config hash): ``kl_heads: [card]`` (a subset of gate / card / cell;
needs ``leash: max``) puts only those heads' KL in the loss and the leash steers on their max; ``kl_ref_card: <ckpt>``
anchors KL_card to that frozen net instead of the init (``ref_terms(card_ref=)``; the update-0 check then skips KL_card).
F6' (``kl_ref_gate_max_elixir: X`` + optional ``kl_ref_gate_target_frac`` (default 0.5), needs kl_ref_gate; absent /
null = F6 / F1 exactly, same hash; ``gate_lo_cfg``): only gate rows with own elixir < X (``row["elixir"]``, the
actor's exact elixir at the decision, ``record_elixir``) are anchored to the kl_ref_gate net, with their OWN
coefficient beta_g: L += beta_g KL_gate_imit(low rows); KL_gate (the ``kl_gate`` monitor, the shared leash, the update-0
check) is the init-ref KL over the >= X rows only. beta_g adapts as ``adapt_beta`` around frac x KL_gate_imit_low
measured on update 0's batch (the init vs the anchor); both ride in the checkpoint (rl["beta_g"], rl["gate_lo_target"]).
C2 / F2 (``critic_ctx: arch | full``, gae only, opt-in; absent / null = unchanged, same config hash; L74
reward/REWARD_ARCHITECTURE.md 5 / 2): rollout rows carry a public context (e1_eval ``Match._ctx_row``: opponent
archetype + tank flag, match phase, crowns) and V = value_scalar(value_head(g) + ``CtxHead``(ctx, g)), the head owned
by the Learner (not the model's state_dict; zero last layer = the plain critic at update 0; checkpoint rl["ctx_head"]).
Step c (``cue_inputs: on``, generalist init, RoyaleSim >= 0.1.35; absent / null / false = unchanged, same config hash;
L74/cues/STEP_C_SPEC.md): the init gets a ZERO ``GenModel.cue_in`` layer (in the state_dict, so actors / checkpoints /
evals carry it); a model with it records per-unit-token cue rows (e1_eval ``sim_cue_rows``) and the learner feeds them.
C1 stage A (``posture_head: true``, gae only, opt-in; absent / null / false = unchanged, same config hash; L74
reward/REWARD_ARCHITECTURE.md 5 C1): a LEARNED posture z in {defend, balanced, pressure} = a gate-threshold offset
``posture_dtau`` (default +0.10 / 0 / -0.10) added to tau for every gate decision of the learner side, re-chosen every
``posture_every`` ticks (default 200) from ``PostureHead``(g detached, the actor's public ctx row) -- SAMPLED in rollouts,
argmax in screens and in search_s0 (e1_eval ``posture_dtau``). The choice is an extra policy action with its own PPO-clip
term on the row's GAE advantage + ``posture_ent_coef`` x its entropy (``minibatch_loss``); the gate's log-prob uses
tau + dtau of the posture in force. The head is the Learner's (own Adam; checkpoint rl["posture_head"] + rl["posture"]
metadata), sent to actors inside the weights message under ``POSTURE_SD`` keys (``actor_bytes`` / ``split_actor_sd``).
B6 stage A (``ability_head: on``, gae only, opt-in; absent / null / false = unchanged, same config hash; owner 10-15/16:
the bait deck's Hero Valkyrie ability): the LEARNER's hero / champion presses are decided by ``AbilityHead``(g detached,
the button's public board features, royale_env ``_ability_head_features``) -- one Bernoulli press / no-press at each
learner decision with a pressable button (e1_eval ``ability_decide``: sampled in rollouts, p > 0.5 in screens and
search_s0); a press goes through the rule's own queue / recheck / ``eng.act`` path and the rule never presses for that
side (``learned_sides``); opponents keep ``ability_policy``. Credit: its own PPO-clip term on the decision row's GAE
advantage + ``ability_ent_coef`` x its entropy (``minibatch_loss``); own Adam (``ability_lr``); checkpoint
rl["ability_head"] / ["ability_optimizer"] / ["ability"]; weights message keys ``ABILITY_SD``. Warm start
(``_ability_warm_start``): ``ability_bc_matches`` rollouts with the RULE pressing record the rule's q at every pressable
decision, the head is fitted to it (``ability_bc_fit``) before the init screen and u0000.
L74 combo (``spell_value_reward: on``, gae + league only, opt-in; absent / null / false = unchanged, same config hash; owner
10-17, scratchpad/gauntlet/L74/combo/RL_COMBO_REWARD.md): the learner's Rocket impacts are measured in the engine
(``spell_value.SpellTracker``) and each adds spell_value_w x (troop elixir removed, x a princess-in-blast bonus for a real
clump, - the Rocket's cost; a princess hit floors at 0) to the r_step of the rows that decided the Rocket and its setup Tornado
(``collate``).
L74 W6 crown terms (``lead_protect: on`` / ``princess_redirect: penalty | potential`` / ``tornado_king_penalty: on``, gae +
league only, opt-in, one per arm; absent / null / false = unchanged, same config hash; plan1019 TUESDAY D / I / I2): a
read-only ``reward_terms.CrownTracker`` on the learner's crown towers, crowns and Tornados (e1_eval ``crown_track``) and
``reward_terms.row_terms`` on each match's kept rows: rewards into r_step, the redirect potential into ``phi`` (``collate``).

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
     ``shaping: live_phi`` uses the same causal smoothing and residual critic with 2 P(win)-1 from the frozen
     public-board MLP (pipeline.live_phi). Null shaping_phi_ckpt resolves to L74/livephi/phi_live.pt. Default off.
     ``shaping: solvency | tower_score`` (L74 REWARD_ARCHITECTURE.md step 3: A2 / A1 + A1b): R2's machinery with Phi
     from the mode's own public-state row (``reward_shaping.state_record`` at the actor, ``state_phi`` here with the
     optional ``shaping_solv_*`` / ``shaping_ts_*`` keys, defaults ``reward_shaping.STATE_PHI_DEFAULTS``; absent = the
     historical config and hash); shaping_critic_scale must be >= 1 + ``reward_shaping.phi_bound``.
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
from pipeline import reward_terms as RT                                         # noqa: E402
from pipeline import spell_value as SV                                          # noqa: E402
from pipeline import adaptive_opponents as AO                                  # noqa: E402
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
# L74 human tempo (optional keys, league only; absent / null = off, same hash): the league OPPONENT's decision interval
# and extra reaction delay in ticks (e1_eval.opp_tempo); the learner's cfg never carries them.
OPP_TEMPO_KEYS = ("opp_decide_every", "opp_reaction_ticks")


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


def opp_T(base: dict) -> float:
    """League opponents' sampling temperature: `league_opp_T` (10-14 opponent calibration: decisive opponents punish like
    live) or, unset, the learner's T as before."""
    t = base.get("league_opp_T")
    return float(base["T"] if t is None else t)


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
    if base.get("T_gate") is not None:                       # 10-13: learner gate temperature; absent = unchanged cfg
        cfg["T_gate"] = float(base["T_gate"])
    if kind == "rollout" and base.get("shaping", "none") == "tower_crown":
        cfg["record_phi"] = True                              # R2: each row carries reward_shaping.phi_record
    elif kind == "rollout" and base.get("shaping") in RS.STATE_PHI_MODES:
        cfg["record_phi"] = base["shaping"]                   # step 3: the mode's reward_shaping.state_record row
    if kind == "rollout" and (base.get("gae_gamma_unit", "row") == "tick" or base.get("shaping") in ("value_phi", "live_phi")):
        cfg["record_tick"] = True                             # each row carries its decision tick
    if kind == "rollout" and (base.get("critic_ctx") is not None or base.get("posture") is not None):
        cfg["record_ctx"] = True                              # C2 / F2 / C1: each row carries e1_eval Match._ctx_row
    if base.get("posture") is not None:                       # C1: sampled in rollouts, argmax in screens; actor_main
        pb = base["posture"]                                  # attaches the head (it arrives with the weights)
        cfg["posture"] = {"every": int(pb["every"]), "dtau": [float(x) for x in pb["dtau"]],
                          "mode": "sample" if kind == "rollout" else "argmax"}
    if kind == "rollout" and base.get("kl_ref_gate_max_elixir") is not None:
        cfg["record_elixir"] = True                           # F6': each row carries its exact own elixir
    if base.get("ability") is not None:                       # B6: sampled in rollouts, greedy in screens; actor_main
        cfg["ability"] = {"mode": "sample" if kind == "rollout" else "greedy",   # attaches the head (or: label mode)
                          "n_feat": int(base["ability"].get("n_feat", E.ABILITY_FEAT_N))}
    if kind == "rollout" and base.get("spell_value"):         # L74 combo: the learner's Rocket events + each row's tick
        cfg["spell_track"] = cfg["record_tick"] = True        # (spell_value.row_rewards maps events to rows by tick)
    if kind == "rollout" and base.get("crown_track"):         # L74 W6: the crown record + each row's tick
        cfg["crown_track"] = cfg["record_tick"] = True        # (reward_terms.row_terms maps events to rows by tick)
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
SHAPING_MODES = ("none", "tower_crown", "value_phi", "live_phi") + RS.STATE_PHI_MODES   # R2 / lever C / step 3, gae only
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
# step 3 (``shaping: solvency | tower_score``): optional keys outside GAE_DEFAULTS, returned only for those modes.
STATE_PHI_KEYS = tuple(RS.STATE_PHI_DEFAULTS)
# C2 / F2 (L74 REWARD_ARCHITECTURE.md 5 / 2; ``critic_ctx``, gae only, optional key: absent / null = off, same hash):
# the critic also reads the row's public context (``CtxHead``); arch = opponent archetype + tank flag, full = + match
# phase + own / foe crowns. adv_cfg returns the key only when set.
CRITIC_CTX_MODES = (None, "arch", "full")
# C1 stage A (``posture_head``, gae only, optional keys: absent / null / false = off, same hash). POSTURES index z.
POSTURES = ("defend", "balanced", "pressure")
POSTURE_DEFAULTS = {"posture_every": 200, "posture_dtau": [0.10, 0.0, -0.10], "posture_ent_coef": 0.01,
                    "posture_lr": 3e-4}   # lead 10-15: a fresh head at the trunk lr (1e-5) moves < ~0.4 logit in 65 updates
POSTURE_KEYS = ("posture_head",) + tuple(POSTURE_DEFAULTS)
POSTURE_HIDDEN, POSTURE_P_BALANCED = 64, 0.8        # PostureHead width; P(balanced) at init
POSTURE_SD = "__posture__."                          # actor weights message: the head's tensors under this prefix
# B6 stage A (``ability_head``, gae only, optional keys: absent / null / false = off, same hash): the LEARNER's hero /
# champion ability presses decided by a learned Bernoulli head instead of the press rule (opponents keep the rule).
ABILITY_DEFAULTS = {"ability_ent_coef": 0.01, "ability_lr": 3e-4,   # the posture head's lr (a fresh head moves at it)
                    "ability_bc_matches": 128,     # imitation warm start: rollouts with the RULE pressing (labels)
                    "ability_bc_steps": 300, "ability_bc_lr": 1e-3}  # ... full-batch soft-BCE steps on the rule's q
ABILITY_KEYS = ("ability_head",) + tuple(ABILITY_DEFAULTS)
ABILITY_HIDDEN, ABILITY_P0 = 64, 0.1                  # AbilityHead width; P(press) at init before the warm start
ABILITY_SD = "__ability__."                          # actor weights message: the ability head's tensors
SMOKE_AB_BC = 8                                      # --smoke with ability_head: warm-start rollouts (not 128)


def ability_cfg(cfg: dict) -> Optional[dict]:
    """The B6 keys of a config, validated (SystemExit naming the bad key): None when ``ability_head`` is absent / null /
    false (the other ability keys must then be unset), else {ent_coef, lr, bc_matches, bc_steps, bc_lr}. Needs advantage
    gae (the press is credited with its row's GAE advantage) and no branch_gate. hero_abilities false is ALLOWED (the
    head then never sees a pressable button: a no-op the Learner logs), so the plain smoke runs with the key."""
    on = cfg.get("ability_head")
    if on is None or on is False:
        stray = [k for k in (*ABILITY_DEFAULTS, "ability_features") if cfg.get(k) is not None]
        if stray:
            raise SystemExit(f"bad ability config: {stray} set without ability_head on")
        return None
    num = (lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v))
    intk = (lambda v, lo: isinstance(v, int) and not isinstance(v, bool) and v >= lo)
    c = {k: (v if cfg.get(k) is None else cfg[k]) for k, v in ABILITY_DEFAULTS.items()}
    bad = []
    if on is not True and on != "on":
        bad.append(f"ability_head must be on / true (or absent / null / false), got {on!r}")
    if not (num(c["ability_ent_coef"]) and c["ability_ent_coef"] >= 0.0):
        bad.append(f"ability_ent_coef must be a finite number >= 0, got {c['ability_ent_coef']!r}")
    for k in ("ability_lr", "ability_bc_lr"):
        if not (num(c[k]) and c[k] > 0.0):
            bad.append(f"{k} must be a finite number > 0, got {c[k]!r}")
    for k in ("ability_bc_matches", "ability_bc_steps"):
        if not intk(c[k], 0):
            bad.append(f"{k} must be an integer >= 0, got {c[k]!r}")
    if cfg.get("advantage", "match_loo") != "gae":
        bad.append(f"ability_head needs advantage gae (refusing {cfg.get('advantage', 'match_loo')!r})")
    if cfg.get("branch_gate"):
        bad.append("ability_head with branch_gate is not supported (branch workers press with the rule)")
    feats = cfg.get("ability_features") or "base"            # L74 press audit (10-18): opt-in head inputs
    if feats not in E.ABILITY_FEAT_SETS:
        bad.append(f"ability_features must be one of {sorted(E.ABILITY_FEAT_SETS)} (or absent / null), got {feats!r}")
    if bad:
        raise SystemExit("bad ability config: " + "; ".join(bad))
    return {"ent_coef": float(c["ability_ent_coef"]), "lr": float(c["ability_lr"]),
            "bc_matches": int(c["ability_bc_matches"]), "bc_steps": int(c["ability_bc_steps"]),
            "bc_lr": float(c["ability_bc_lr"]), "features": feats}


def store_ability_cfg(cfg: dict) -> Optional[dict]:
    """Learner.__init__'s B6 step: validate (``ability_cfg``) and, with the head on, write every ABILITY_DEFAULTS key
    back into ``cfg`` as its validated value (the posture_lr lesson: every later reader finds every key)."""
    ac = ability_cfg(cfg)
    if ac is not None:
        cfg.update(ability_head=True, **{f"ability_{k}": v for k, v in ac.items() if k != "features"})
        if ac["features"] != "base":                          # base = absent (the historical config and hash)
            cfg["ability_features"] = ac["features"]
    return ac


HEROIW_PRESS_MODES = ("off", "live", "never")         # = royale_heroiw.press_mode's values


def heroiw_press_cfg(cfg: dict) -> str:
    """L74 overpress (10-18). ``heroiw_press`` (optional; absent / null = unchanged, same config hash) sets
    ROYALE_HEROIW_PRESS for this process and so for every actor it starts later (off | live | never); an environment
    that already holds a DIFFERENT value refuses. Then a hard refusal: with ``ability_head`` on, hero_abilities, the
    Hero IW runtime and the hero form, the press mode must be 'live' -- else the Hero Ice Wizard's rule is v2's generic
    range fallback (~5.4 presses / match vs the live rule's ~1.9) and the warm start would clone it (cue_ab, 10-18).
    -> the press mode in force."""
    from pipeline import royale_heroiw as heroiw
    want = cfg.get("heroiw_press")
    if want is not None:
        if want not in HEROIW_PRESS_MODES:
            raise SystemExit(f"heroiw_press must be one of {HEROIW_PRESS_MODES} (or absent / null), got {want!r}")
        have = os.environ.get("ROYALE_HEROIW_PRESS")
        if have not in (None, want):
            raise SystemExit(f"heroiw_press {want} but the environment has ROYALE_HEROIW_PRESS={have}: unset one")
        os.environ["ROYALE_HEROIW_PRESS"] = want
    try:
        mode = heroiw.press_mode()
    except ValueError as exc:
        raise SystemExit(str(exc))
    if (cfg.get("ability_head") not in (None, False) and cfg.get("hero_abilities") and heroiw.ENABLED
            and os.environ.get("ROYALE_HEROIW_FORM", "hero") == "hero" and mode != "live"):
        raise SystemExit(f"REFUSING: ability_head with the Hero Ice Wizard needs the live press rule (press mode is "
                         f"{mode!r}: the IW would press by the generic range rule and the warm start would clone it); "
                         f"set heroiw_press: live")
    return mode


def posture_cfg(cfg: dict) -> Optional[dict]:
    """The C1 keys of a config, validated (SystemExit naming the bad key): None when ``posture_head`` is absent / null /
    false (then the other posture keys must be unset), else {every, dtau, ent_coef, lr} with POSTURE_DEFAULTS filled.
    Needs advantage gae (the choice is credited with the row's GAE advantage), every tau + dtau inside (0, 1), and no
    branch_gate (branch workers decide with the plain gate)."""
    on = cfg.get("posture_head")
    if on is None or on is False:
        stray = [k for k in POSTURE_DEFAULTS if cfg.get(k) is not None]
        if stray:
            raise SystemExit(f"bad posture config: {stray} set without posture_head true")
        return None
    num = (lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v))
    c = {k: (v if cfg.get(k) is None else cfg[k]) for k, v in POSTURE_DEFAULTS.items()}
    bad = []
    if on is not True and on != "on":
        bad.append(f"posture_head must be true / on (or absent / null / false), got {on!r}")
    ev = c["posture_every"]
    if not (isinstance(ev, int) and not isinstance(ev, bool) and ev >= 1):
        bad.append(f"posture_every must be an integer >= 1 (ticks), got {ev!r}")
    dt = c["posture_dtau"]
    if not (isinstance(dt, (list, tuple)) and len(dt) == len(POSTURES) and all(num(x) for x in dt)):
        bad.append(f"posture_dtau must be {len(POSTURES)} finite numbers {list(POSTURES)}, got {dt!r}")
    elif num(cfg.get("tau")) and not all(0.0 < cfg["tau"] + x < 1.0 for x in dt):
        bad.append(f"posture_dtau {list(dt)}: every tau {cfg['tau']} + dtau must lie in (0, 1)")
    if not (num(c["posture_ent_coef"]) and c["posture_ent_coef"] >= 0.0):
        bad.append(f"posture_ent_coef must be a finite number >= 0, got {c['posture_ent_coef']!r}")
    if not (num(c["posture_lr"]) and c["posture_lr"] > 0.0):
        bad.append(f"posture_lr must be a finite number > 0, got {c['posture_lr']!r}")
    if cfg.get("advantage", "match_loo") != "gae":
        bad.append(f"posture_head needs advantage gae (refusing {cfg.get('advantage', 'match_loo')!r})")
    if cfg.get("branch_gate"):
        bad.append("posture_head with branch_gate is not supported (branch workers decide with the plain gate)")
    if bad:
        raise SystemExit("bad posture config: " + "; ".join(bad))
    return {"every": int(ev), "dtau": [float(x) for x in dt], "ent_coef": float(c["posture_ent_coef"]),
            "lr": float(c["posture_lr"])}


def store_posture_cfg(cfg: dict) -> Optional[dict]:
    """Learner.__init__'s C1 step: validate (``posture_cfg``) and, with the head on, write EVERY POSTURE_DEFAULTS key
    back into ``cfg`` as its validated value (10-15: posture_lr was left out here and every pod smoke died with a
    KeyError before update 0). -> posture_cfg's dict, or None."""
    pc = posture_cfg(cfg)
    if pc is not None:
        cfg.update(posture_head=True, **{f"posture_{k}": v for k, v in pc.items()})
    return pc


# L74 combo (``spell_value_reward: on``, gae + league only, opt-in; absent / null / false = off, same hash; owner 10-17,
# L74/combo/RL_COMBO_REWARD.md): per-row reward on the rows that decided OUR Rocket (+ its setup Tornado) = spell_value_w x
# (the elixir of enemy bodies the blast removed, x (1 + tower_bonus) with a princess in it and >= tower_min caught, - the
# Rocket's cost; floored at 0 when a princess was hit), added to r_step (``collate``); the critic becomes the residual one (phi = 0) at shaping_critic_scale,
# which must cover 1 + spell_value_match_cap. spell_value_w 0 = the measuring control (tracker, rows, critic scale, no reward).
# ``spell_value_lone: on`` (owner 10-18; needs spell_value_reward on; absent / null / false = the 6 : 3 cost split, same hash):
# a combo's Tornado row earns its marginal over a LONE Rocket instead (spell_value.tornado_credit; spell_value_lone_min).
SPELL_KEYS = ("spell_value_reward", "spell_value_lone") + tuple(SV.DEFAULTS) + tuple(SV.LONE_DEFAULTS)


def spell_cfg(cfg: dict) -> Optional[dict]:
    """The combo-reward keys of a config, validated (SystemExit naming the bad key): None when ``spell_value_reward`` is
    absent / null / false (the other spell_value keys must then be unset), else {spell_value_*: value} with the defaults."""
    on, lone = cfg.get("spell_value_reward"), cfg.get("spell_value_lone")
    if lone is None or lone is False:                # spell_value_lone off: its keys must be unset (the cost split)
        stray = [k for k in SV.LONE_DEFAULTS if cfg.get(k) is not None]
        if stray:
            raise SystemExit(f"bad spell_value config: {stray} set without spell_value_lone on")
    elif lone is not True:
        raise SystemExit(f"bad spell_value config: spell_value_lone must be on / off (a bool), got {lone!r}")
    if on is None or on is False:
        stray = [k for k in SV.DEFAULTS if cfg.get(k) is not None] + (["spell_value_lone"] if lone else [])
        if stray:
            raise SystemExit(f"bad spell_value config: {stray} set without spell_value_reward on")
        return None
    num = (lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v))
    p = {k: (v if cfg.get(k) is None else cfg[k]) for k, v in SV.DEFAULTS.items()}
    bad = [] if on is True else [f"spell_value_reward must be on / off (a bool), got {on!r}"]
    bad += [f"{k} must be a finite number >= 0, got {v!r}" for k, v in p.items() if not (num(v) and v >= 0)]
    bad += [f"{k} must be > 0" for k in ("spell_value_event_cap", "spell_value_match_cap") if num(p[k]) and p[k] <= 0]
    if cfg.get("advantage", "match_loo") != "gae":
        bad.append(f"spell_value_reward needs advantage gae (refusing {cfg.get('advantage', 'match_loo')!r})")
    if not cfg.get("league"):
        bad.append("spell_value_reward needs league true (the tracker rides on self-play matches)")
    lp = {k: (v if cfg.get(k) is None else cfg[k]) for k, v in SV.LONE_DEFAULTS.items()} if lone else {}
    bad += [f"{k} must be a finite number >= 0, got {v!r}" for k, v in lp.items() if not (num(v) and v >= 0)]
    if bad:
        raise SystemExit("bad spell_value config: " + "; ".join(bad))
    return {**{k: float(v) for k, v in {**p, **lp}.items()}, **({"spell_value_lone": True} if lone else {})}


# L74 W6 crown terms (reward_terms; gae + league only, opt-in, one key per arm; absent / null / false = off, same hash): the
# rewards go into r_step (the residual critic at shaping_critic_scale, phi = 0, which must cover 1 + reward_terms.bound),
# princess_redirect potential into phi instead (``collate``).
CROWN_KEYS = tuple(RT.TERMS) + tuple(RT.DEFAULTS)


def crown_cfg(cfg: dict) -> Optional[dict]:
    """The crown-term keys of a config, validated (SystemExit naming the bad key): None when every switch is absent / null /
    false (their weight keys must then be unset), else {switch: True (princess_redirect: its mode), weight: float} for the
    terms that are on."""
    off = (lambda v: v is None or v is False)
    num = (lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v))
    bad = [f"{w} set without {k} on" for k, w in RT.TERMS.items() if off(cfg.get(k)) and cfg.get(w) is not None]
    if all(off(cfg.get(k)) for k in RT.TERMS):
        if bad:
            raise SystemExit("bad crown-term config: " + "; ".join(bad))
        return None
    p = {}
    for k, wk in RT.TERMS.items():
        v = cfg.get(k)
        if off(v):
            continue
        if k == "princess_redirect" and v not in RT.REDIRECT_MODES:
            bad.append(f"princess_redirect must be one of {RT.REDIRECT_MODES} (or absent / null / false), got {v!r}")
        elif k != "princess_redirect" and v is not True:
            bad.append(f"{k} must be on / off (a bool), got {v!r}")
        w = RT.DEFAULTS[wk] if cfg.get(wk) is None else cfg[wk]
        if not (num(w) and w >= 0):
            bad.append(f"{wk} must be a finite number >= 0, got {w!r}")
        p[k], p[wk] = v, w
    if cfg.get("advantage", "match_loo") != "gae":
        bad.append(f"crown terms need advantage gae (refusing {cfg.get('advantage', 'match_loo')!r})")
    if not cfg.get("league"):
        bad.append("crown terms need league true (the tracker rides on self-play matches)")
    if bad:
        raise SystemExit("bad crown-term config: " + "; ".join(bad))
    return {k: (float(v) if k in RT.DEFAULTS else v) for k, v in p.items()}


def adv_cfg(cfg: dict) -> dict:
    """The R1 keys of a config (``GAE_DEFAULTS`` for missing ones), validated: SystemExit naming the bad key."""
    c = {k: cfg.get(k, v) for k, v in GAE_DEFAULTS.items()}
    vp = {k: cfg.get(k, v) for k, v in VALUE_PHI_DEFAULTS.items()}
    sp = {k: cfg.get(k, v) for k, v in RS.STATE_PHI_DEFAULTS.items()}
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
    for k in ("shaping_solv_w", "shaping_solv_k", "shaping_ts_w_tb", "shaping_tr_w"):
        if not (num(sp[k]) and sp[k] >= 0.0):
            bad.append(f"{k} must be a finite number >= 0, got {sp[k]!r}")
    if not (num(sp["shaping_solv_cap"]) and sp["shaping_solv_cap"] > 0.0):
        bad.append(f"shaping_solv_cap must be a finite number > 0, got {sp['shaping_solv_cap']!r}")
    if not (num(sp["shaping_tr_cap"]) and sp["shaping_tr_cap"] > 0.0):
        bad.append(f"shaping_tr_cap must be a finite number > 0, got {sp['shaping_tr_cap']!r}")
    if c["shaping"] in ("trade", "trade2") and cfg.get("opp_elixir") not in ("counter", "counter_all"):
        bad.append(f"shaping {c['shaping']} needs opp_elixir counter (its Phi reads the PUBLIC opponent-elixir counter)")
    if c["shaping"] == "trade2":                                          # A3' (reward_shaping phi_trade2)
        if not (num(sp["shaping_t2_w"]) and sp["shaping_t2_w"] >= 0.0):
            bad.append(f"shaping_t2_w must be a finite number >= 0, got {sp['shaping_t2_w']!r}")
        if not (num(sp["shaping_t2_cap"]) and sp["shaping_t2_cap"] > 0.0):
            bad.append(f"shaping_t2_cap must be a finite number > 0, got {sp['shaping_t2_cap']!r}")
    if not (num(sp["shaping_ts_h_power"]) and sp["shaping_ts_h_power"] >= 1.0):
        bad.append(f"shaping_ts_h_power must be a finite number >= 1 (h concave), got {sp['shaping_ts_h_power']!r}")
    for k in ("shaping_ts_w_own", "shaping_ts_w_foe"):                   # [behind, even, ahead]
        if not (isinstance(sp[k], (list, tuple)) and len(sp[k]) == 3 and all(num(x) and x >= 0.0 for x in sp[k])):
            bad.append(f"{k} must be 3 finite numbers >= 0 [behind, even, ahead], got {sp[k]!r}")
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
    need = 1.0                                                               # |return| bound without shaping
    if not (num(sc) and sc > 0.0):
        bad.append(f"shaping_critic_scale must be a finite number > 0, got {sc!r}")
    elif c["shaping"] != "none" and not bad:
        if c["shaping"] in ("value_phi", "live_phi"):                        # |Phi| <= w_value (a mean of V in [-1, 1], x w)
            need, why = 1.0 + vp["shaping_w_value"], "1 + w_value"
        elif c["shaping"] in RS.STATE_PHI_MODES:                             # |Phi| <= phi_bound on every reachable state
            need, why = 1.0 + RS.phi_bound(c["shaping"], sp), "1 + reward_shaping.phi_bound"
        else:
            need = 1.0 + c["shaping_w_tower"] + 2.0 / 3.0 * c["shaping_w_crown"]   # max |G - Phi| before the end
            why = "1 + w_tower + (2/3) w_crown"
        if sc < need:
            bad.append(f"shaping_critic_scale {sc} < {need:.4f} = {why}: the residual target "
                       f"(G - Phi) / scale could leave the value head's [-1, 1]")
        if c["critic_warmup_updates"] == 0:
            bad.append(f"shaping {c['shaping']!r} needs critic_warmup_updates > 0 (the pretrained value head "
                       f"predicts G, not the residual (G - Phi) / scale)")
    sv = spell_cfg(cfg)                                                      # L74 combo: the return widens by its cap
    if sv is not None and not bad:
        need += sv["spell_value_match_cap"]
        if sc < need:
            bad.append(f"shaping_critic_scale {sc} < {need:.4f} = the return bound + spell_value_match_cap: the residual "
                       f"target ret / scale could leave the value head's [-1, 1]")
        if c["critic_warmup_updates"] == 0:
            bad.append("spell_value_reward needs critic_warmup_updates > 0 (the pretrained value head predicts G, "
                       "not G / scale)")
    ct = crown_cfg(cfg)                                                      # L74 W6: the return (or |Phi|) widens too
    if ct is not None and not bad:
        need += RT.bound(ct)
        if sc < need:
            bad.append(f"shaping_critic_scale {sc} < {need:.4f} = the return bound + reward_terms.bound: the residual "
                       f"target ret / scale could leave the value head's [-1, 1]")
        if c["critic_warmup_updates"] == 0:
            bad.append("crown terms need critic_warmup_updates > 0 (the pretrained value head predicts G, not G / scale)")
    cc = cfg.get("critic_ctx")
    if cc not in CRITIC_CTX_MODES:
        bad.append(f"critic_ctx must be one of {CRITIC_CTX_MODES}, got {cc!r}")
    elif cc is not None and c["advantage"] != "gae":
        bad.append(f"critic_ctx {cc!r} needs advantage gae (match_loo has no critic)")
    if bad:
        raise SystemExit("bad advantage config: " + "; ".join(bad))
    if cc is not None:                                        # optional key: absent = the R1 dict exactly
        c["critic_ctx"] = cc
    if c["shaping"] in ("value_phi", "live_phi"):
        c.update(vp)
    if c["shaping"] in RS.STATE_PHI_MODES:
        c.update(sp)
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
        row = {k: s._gen_row[k] for k in s._gen_row
               if k in E.GEN_ROW_KEYS + E.GEN_V3_KEYS + E.GEN_V31_KEYS + E.GEN_CUE_KEYS}
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


class CtxHead(torch.nn.Module):
    """C2 / F2 (``critic_ctx``): a residual on the value head's 7 logits from the row's public context ``B["ctx"]``
    ([arch_id, tank_flag, phase_id, own crowns, foe crowns], e1_eval ``Match._ctx_row``) and the trunk feature g the
    value head reads: V = value_scalar(value_head(g) + CtxHead(ctx, g)). Owned by the Learner, never part of the
    model's state_dict (grafting / live inference untouched). The last layer starts at exactly 0, so at update 0 V is
    the plain critic's V bit for bit. Features: arch one-hot (``archetypes.ARCH_IDS``, 9) + tank (1); ``full`` also
    phase one-hot (3) + own / foe crowns one-hot (4 + 4)."""

    def __init__(self, mode: str, d_g: int, hidden: int = 64):
        from pipeline.archetypes import ARCH_IDS
        super().__init__()
        self.mode, self.n_arch = mode, len(ARCH_IDS)
        d_ctx = self.n_arch + 1 + (11 if mode == "full" else 0)
        self.net = torch.nn.Sequential(torch.nn.Linear(d_ctx + int(d_g), hidden), torch.nn.ReLU(),
                                       torch.nn.Linear(hidden, 7))
        torch.nn.init.zeros_(self.net[2].weight)
        torch.nn.init.zeros_(self.net[2].bias)

    def features(self, ctx: torch.Tensor) -> torch.Tensor:
        c = ctx.long()
        f = [Fn.one_hot(c[:, 0], self.n_arch), c[:, 1:2].clamp(0, 1)]
        if self.mode == "full":
            f += [Fn.one_hot(c[:, 2], 3), Fn.one_hot(c[:, 3], 4), Fn.one_hot(c[:, 4], 4)]
        return torch.cat(f, dim=1).float()

    def forward(self, ctx: torch.Tensor, g: torch.Tensor) -> torch.Tensor:
        return self.net(torch.cat([self.features(ctx).to(g.dtype), g], dim=1))


class PostureHead(torch.nn.Module):
    """C1 (``posture_head``): Linear(d_g + 21, 64) -> ReLU -> Linear(64, 3) logits over ``POSTURES`` from the trunk
    feature g (DETACHED here: no posture gradient ever reaches the trunk) + CtxHead's ``full`` one-hots of the row's
    public ctx (arch 9 + tank 1 + phase 3 + own / foe crowns 4 + 4). Last layer weights 0, bias [0, b, 0] with
    b = log(2 P / (1 - P)) so P(balanced) = POSTURE_P_BALANCED exactly at init (argmax = balanced = dtau 0). Owned by
    the Learner, never part of the model's state_dict."""
    mode = "full"
    features = CtxHead.features

    def __init__(self, d_g: int, hidden: int = POSTURE_HIDDEN):
        from pipeline.archetypes import ARCH_IDS
        super().__init__()
        self.n_arch = len(ARCH_IDS)
        self.net = torch.nn.Sequential(torch.nn.Linear(self.n_arch + 12 + int(d_g), int(hidden)), torch.nn.ReLU(),
                                       torch.nn.Linear(int(hidden), len(POSTURES)))
        torch.nn.init.zeros_(self.net[2].weight)
        b = math.log(2.0 * POSTURE_P_BALANCED / (1.0 - POSTURE_P_BALANCED))
        with torch.no_grad():
            self.net[2].bias.copy_(torch.tensor([0.0, b, 0.0]))

    def forward(self, g: torch.Tensor, ctx: torch.Tensor) -> torch.Tensor:
        g = g.detach()
        return self.net(torch.cat([self.features(ctx).to(g.dtype), g], dim=1))


def load_posture_head(path, device: str = "cpu") -> Optional[dict]:
    """search_s0: the trained posture of an RL checkpoint (rl["posture_head"] + rl["posture"]) as an e1_eval
    cfg["posture"] in ARGMAX mode; None when the checkpoint has none (a pre-C1 / posture-off run, a non-RL model)."""
    rl = torch.load(path, map_location="cpu").get("rl") or {}
    if "posture_head" not in rl:
        return None
    meta = rl["posture"]
    head = PostureHead(int(meta["d_g"]), int(meta.get("hidden", POSTURE_HIDDEN)))
    head.load_state_dict(rl["posture_head"])
    return {"head": head.to(device).eval(), "every": int(meta["every"]), "dtau": [float(x) for x in meta["dtau"]],
            "mode": "argmax"}


class AbilityHead(torch.nn.Module):
    """B6 (``ability_head``): Linear(d_g + E.ABILITY_FEAT_N, 64) -> ReLU -> Linear(64, 1) = the press logit of one
    pressable hero / champion button, from the trunk feature g (DETACHED: no ability gradient ever reaches the trunk,
    whose KL leash only watches gate / card / cell) + the button's public board features
    (``royale_env._ability_head_features``). Last layer weight 0, bias logit(ABILITY_P0) at init (the imitation warm
    start, ``ability_bc_fit``, then refits it). Owned by the Learner, never part of the model's state_dict."""

    def __init__(self, d_g: int, hidden: int = ABILITY_HIDDEN, n_feat: int = E.ABILITY_FEAT_N):
        super().__init__()
        self.net = torch.nn.Sequential(torch.nn.Linear(int(n_feat) + int(d_g), int(hidden)), torch.nn.ReLU(),
                                       torch.nn.Linear(int(hidden), 1))
        torch.nn.init.zeros_(self.net[2].weight)
        with torch.no_grad():
            self.net[2].bias.fill_(_logit(ABILITY_P0))

    def forward(self, g: torch.Tensor, feat: torch.Tensor) -> torch.Tensor:
        g = g.detach()
        return self.net(torch.cat([feat.to(g.dtype), g], dim=1)).squeeze(-1)


def load_ability_head(path, device: str = "cpu") -> Optional[dict]:
    """search_s0: the trained ability head of an RL checkpoint (rl["ability_head"] + rl["ability"]) as an e1_eval
    cfg["ability"] in GREEDY mode (press iff p > 0.5); None when the checkpoint has none."""
    rl = torch.load(path, map_location="cpu").get("rl") or {}
    if "ability_head" not in rl:
        return None
    meta = rl["ability"]
    head = AbilityHead(int(meta["d_g"]), int(meta.get("hidden", ABILITY_HIDDEN)), int(meta.get("n_feat", E.ABILITY_FEAT_N)))
    head.load_state_dict(rl["ability_head"])
    return {"head": head.to(device).eval(), "mode": "greedy", "n_feat": int(meta.get("n_feat", E.ABILITY_FEAT_N)),
            "features": meta.get("features", "base")}


def trunk_g(model, B: dict, idx) -> torch.Tensor:
    """The trunk feature g of rows ``idx`` (S1 encode or GenModel encode_gen, as policy_terms)."""
    if "hand_card" in B:
        return model.encode_gen({k: B[k][idx] for k in E.gen_row_keys(model)})["g"]
    return model.encode(B["tok"][idx], B["mask"][idx], B["sc"][idx], B["past"][idx])["g"]


def ability_bc_fit(head, g: torch.Tensor, feat: torch.Tensor, q: torch.Tensor, steps: int, lr: float) -> dict:
    """The imitation warm start: the head's bias set to logit(mean q) (the rule's press rate per decision), then
    ``steps`` full-batch Adam steps of soft BCE(sigmoid(head(g, feat)), q) -- q = the rule's own press probability at
    that decision (v2: 1 - (1 - p)^dt; a range-rule card: whether it pressed). -> monitors (BCE before / after and its
    floor = the mean entropy of q, mean q, mean p before / after). Deterministic (no RNG)."""
    q = q.to(torch.float32)
    qm = float(q.mean())
    with torch.no_grad():
        head.net[2].bias.fill_(_logit(min(max(qm, 1e-3), 1 - 1e-3)))
    bce = (lambda: Fn.binary_cross_entropy_with_logits(head(g, feat), q))
    with torch.no_grad():
        b0, p0 = float(bce()), float(torch.sigmoid(head(g, feat)).mean())
    opt = torch.optim.Adam(head.parameters(), lr=float(lr))
    for _ in range(int(steps)):
        opt.zero_grad(set_to_none=True)
        loss = bce()
        loss.backward()
        opt.step()
    with torch.no_grad():
        qc = q.clamp(1e-6, 1 - 1e-6)
        floor = float((-(qc * qc.log() + (1 - qc) * (1 - qc).log())).mean())
        return {"n": int(len(q)), "q_mean": qm, "bce_before": b0, "bce_after": float(bce()), "bce_floor": floor,
                "p_mean_before": p0, "p_mean_after": float(torch.sigmoid(head(g, feat)).mean()), "steps": int(steps)}


def critic_logits(model, g: torch.Tensor, ctx_head=None, ctx=None) -> torch.Tensor:
    """The critic's 7 logits on trunk feature g: ``model.value_head(g)`` (+ ``ctx_head(ctx, g)`` under critic_ctx)."""
    out = model.value_head(g)
    return out if ctx_head is None else out + ctx_head(ctx, g)


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


def leash_kl(upd: dict, mode: str, heads=None) -> tuple[float, str]:
    """The KL ``adapt_beta`` steers on (owner ruling 2026-09-25, T12b), from ``ppo_update``'s monitors (None = 0.0):
    ``cell`` = KL_cell (the S1 rule, unchanged); ``max`` = max(KL_gate, KL_card, KL_cell). -> (value, the head that
    drove it; a tie goes to the first of gate, card, cell). A config without the key is ``cell`` (Learner).
    ``heads`` (K1 ``kl_heads``; None = all three): ``max`` over the leashed heads only."""
    kls = {h: float(upd.get(f"kl_{h}") or 0.0) for h in (heads or ("gate", "card", "cell"))}
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


GATE_LO_FRAC, GATE_LO_MIN_KL = 0.5, 1e-4   # F6': default target fraction; the smallest usable update-0 low-row KL


def gate_lo_cfg(cfg: dict) -> Optional[dict]:
    """F6' keys, validated (SystemExit naming the key): None = off (``kl_ref_gate_max_elixir`` absent / null), else
    {max_elixir, frac} (frac default 0.5). Needs kl_ref_gate; max_elixir a finite number > 0; frac in (0, 1]."""
    mx, fr = cfg.get("kl_ref_gate_max_elixir"), cfg.get("kl_ref_gate_target_frac")
    num = (lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v))
    if mx is None:
        if fr is not None:
            raise SystemExit("kl_ref_gate_target_frac needs kl_ref_gate_max_elixir")
        return None
    if cfg.get("kl_ref_gate") is None:
        raise SystemExit("kl_ref_gate_max_elixir needs kl_ref_gate (the net the low-elixir gate rows are anchored to)")
    if not (num(mx) and mx > 0):
        raise SystemExit(f"kl_ref_gate_max_elixir must be a finite number > 0, got {mx!r}")
    fr = GATE_LO_FRAC if fr is None else fr
    if not (num(fr) and 0.0 < fr <= 1.0):
        raise SystemExit(f"kl_ref_gate_target_frac must be a number in (0, 1], got {fr!r}")
    return {"max_elixir": float(mx), "frac": float(fr)}


ELIXIR_BANDS = ((0, 2), (2, 4), (4, 7), (7, 11))


def elixir_band_play(el, gs, played) -> dict:
    """F6' monitor: per own-elixir band [lo, hi), the gate-sampled rows and the share of them that played."""
    el, gs, played = np.asarray(el, dtype=np.float64), np.asarray(gs, bool), np.asarray(played, bool)
    out = {}
    for lo, hi in ELIXIR_BANDS:
        sel = gs & (el >= lo) & (el < hi)
        out[f"[{lo},{hi})"] = {"rows": int(sel.sum()), "play_rate": float(played[sel].mean()) if sel.any() else None}
    return out


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


def rollout_jobs(jobs, update: int, learner_pipeline_frac: float = 0.0, seed: int = 0) -> list[tuple]:
    """(entry_index, entry, g) -> ``run_batch`` jobs carrying their per-match cfg overrides (4th element): the
    behaviour seed index and the obs seed are per (entry, g), not per batch (test_rl_royale.TestRolloutJobsSeeds)."""
    result = [(i, entry, g, {"rollout_index": int(g), "update": int(update),
                           "obs_seed": rl_obs_seed(str(entry["tag"]), int(g), int(update))}) for i, entry, g in jobs]
    if learner_pipeline_frac:
        # Independent per-match RNG: worker count/order and league sampling are unchanged.
        # Bernoulli probability, not a quota over an actor's variable-size batch.
        for _, entry, g, over in result:
            key = f"{seed}:{entry['tag']}:{g}:{update}:learner_pipeline".encode()
            draw = int.from_bytes(hashlib.sha256(key).digest()[:8], "big") / 2**64
            over.update(pipeline_decisions=draw < learner_pipeline_frac, pipeline_tau_delta=0.0)
    return result


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
    AO.validate(cfg)
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
    if cfg.get("league_opp_T") is not None and not float(cfg["league_opp_T"]) > 0:
        bad.append(f"league_opp_T must be > 0 (or null = T), got {cfg['league_opp_T']!r}")
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


def exploiter_league(cfg: dict) -> Optional[dict]:
    """``league_exploiters`` (O2, owner 10-16; optional, absent / null = None = sample_matchups unchanged):
    {ckpt, decks, share} -> {share, opp, decks, p}: a ``share`` of matchups is against the frozen ``ckpt`` playing
    ``decks`` (a league_decks file, drawn with ``deck_weights`` under the run's alpha / floor). SystemExit on a bad value.
    L74 O6 (lead 10-20; OPTIONAL keys, each absent = the run's own setting, all absent = the dict and opp spec above
    unchanged): ``T`` (> 0, that opponent's sampling temperature instead of ``league_opp_T``), ``decide_every`` (int >= 1)
    and ``reaction_ticks`` (int >= 0) (that opponent's tempo instead of ``opp_decide_every`` / ``opp_reaction_ticks``) ->
    opp["cfg"]; ``own_opp_cfg`` applies them to THAT opponent only."""
    x = cfg.get("league_exploiters")
    if x is None:
        return None
    if not isinstance(x, dict) or not {"ckpt", "decks", "share"} <= set(x) <= {"ckpt", "decks", "share", *EXPLOITER_OWN}:
        raise SystemExit(f"league_exploiters must be {{ckpt, decks, share}} (+ optional {', '.join(EXPLOITER_OWN)}), got {x!r}")
    own = {k: x[k] for k in EXPLOITER_OWN if k in x}
    for k, v in own.items():
        ok = ((not isinstance(v, bool) and isinstance(v, (int, float)) and v > 0) if k == "T" else
              (type(v) is int and v >= (1 if k == "decide_every" else 0)))
        if not ok:
            raise SystemExit(f"league_exploiters.{k} must be {'a number > 0' if k == 'T' else 'an int >= ' + ('1' if k == 'decide_every' else '0')}, got {v!r}")
    sh = x["share"]
    if isinstance(sh, bool) or not isinstance(sh, (int, float)) or not 0 < sh <= 1:
        raise SystemExit(f"league_exploiters.share must be a number in (0, 1], got {sh!r}")
    for k in ("ckpt", "decks"):
        if not isinstance(x[k], str) or not (REPO / x[k]).is_file():
            raise SystemExit(f"league_exploiters.{k} {x[k]!r} not found")
    if not cfg.get("league") or cfg.get("league_frozen_opponent"):
        raise SystemExit("league_exploiters needs league true and no league_frozen_opponent (that is the exploiter run)")
    decks = league_decks(REPO / x["decks"])
    return {"share": float(sh), "decks": decks,
            "p": deck_weights([d["sides"] for d in decks], cfg["league_deck_alpha"], cfg["league_deck_floor"]),
            "opp": {"id": "exploiter_league:" + x["ckpt"], "cat": "exploiter_league", "type": "exploiter_league",
                    "path": x["ckpt"], **({"cfg": own} if own else {})}}


EXPLOITER_OWN = ("T", "decide_every", "reaction_ticks")      # league_exploiters' optional per-opponent keys (L74 O6)


def own_opp_cfg(oc: dict, opp: dict, base: dict) -> dict:
    """A league opponent's match cfg: the run's human tempo (``opp_decide_every`` / ``opp_reaction_ticks``) on ``oc``
    as before, unless ``opp`` carries a league_exploiters ``cfg`` (L74 O6): then ITS T / decide_every / reaction_ticks
    (each absent = the run's). No ``cfg`` = exactly ``E.opp_tempo(oc, run tempo)``."""
    c = opp.get("cfg")
    if not c:
        return E.opp_tempo(oc, base.get("opp_decide_every"), base.get("opp_reaction_ticks"))
    if c.get("T") is not None:
        oc = {**oc, "T": float(c["T"])}
    return E.opp_tempo(oc, c.get("decide_every", base.get("opp_decide_every")),
                       c.get("reaction_ticks", base.get("opp_reaction_ticks")))


TOWER_TROOPS = ("DaggerDuchess", "Cannoneer", "ChefTower")    # the RoyaleSim fork's crown tower troops (card.rs)


def opp_tower_troops(cfg: dict) -> Optional[dict]:
    """``opp_tower_troops`` (L74 troops 10-17; optional, absent / null = None = matchups unchanged): {name: P(the
    opponent fields it)} over TOWER_TROOPS, sum <= 1 (the rest = the Princess), the live-measured rates. Needs the
    RoyaleSim fork runtime (Battle.set_tower_troops) and league true. SystemExit on a bad value."""
    x = cfg.get("opp_tower_troops")
    if x is None:
        return None
    ok = isinstance(x, dict) and x and set(x) <= set(TOWER_TROOPS) and all(
        isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1 for v in x.values())
    if not ok or sum(x.values()) > 1:
        raise SystemExit(f"opp_tower_troops must be {{name: rate}} over {TOWER_TROOPS}, rates in [0, 1] summing "
                         f"<= 1, got {x!r}")
    if not cfg.get("league"):
        raise SystemExit("opp_tower_troops needs league true (it sets the self-play opponent's crown towers)")
    return {k: float(v) for k, v in x.items()}


def draw_tower_troop(rates: dict, key: str) -> Optional[str]:
    """One crown tower troop for a match (None = the Princess) from ``rates``, drawn from a stream of its own seeded
    by ``key`` -- no other RNG stream (the learner's, a match's) moves, so the matchups are those of the option off."""
    u, acc = float(np.random.default_rng(zlib.crc32(f"tower_troop:{key}".encode())).random()), 0.0
    for name in sorted(rates):
        acc += rates[name]
        if u < acc:
            return name
    return None


LIVE_LEVELS = REPO / "scratchpad/gauntlet/L74/levels/live_levels.json"   # live_levels.py output (measured, 10-17)


def live_levels(cfg: dict) -> Optional[dict]:
    """``live_levels`` (L74 factor D 10-17; optional, absent / null / false = None = matchups unchanged: every card and
    tower at the engine default, level 11): true -> the measured live table LIVE_LEVELS -- our side at our live levels,
    the opponent's drawn per match from the live opponents (``draw_live_levels``). Its file's sha256 enters config_sha.
    "all16" -> every card and both towers at level 16 (cards clamped to their engine ranges); the string enters
    config_sha. Needs league true. SystemExit on a bad value."""
    x = cfg.get("live_levels")
    if x is None or x is False:
        return None
    if x is not True and x != "all16":
        raise SystemExit(f"live_levels must be true, false, null or 'all16', got {x!r}")
    if not cfg.get("league"):
        raise SystemExit("live_levels needs league true (it sets the self-play match levels)")
    return _live_level_table(x)


_LIVE_TABLE: dict = {}


def _live_level_table(mode=True) -> dict:
    if mode == "all16":
        return {"own": {"cards": {}, "default": 16, "tower": 16}, "opp_profiles": [[None, 16, [16]]]}
    if not _LIVE_TABLE:
        _LIVE_TABLE.update(json.loads(LIVE_LEVELS.read_text(encoding="utf-8")))
    return _LIVE_TABLE


def card_level(name: str, level: int) -> int:
    """``level`` clamped into engine card ``name``'s level range (RoyaleSim catalog level_scaling, parse_card_levels'
    rule: Champion 11-16, Legendary 9-16, Epic 6-16, Rare 3-16, Common 1-16); a card the catalog lacks: unchanged."""
    import re
    from pipeline.decision_options import _catalog_cards
    ls = (_catalog_cards().get(re.sub(r"[^a-z]", "", name.lower())) or {}).get("level_scaling")
    if not ls:
        return int(level)
    lo = max(ls["relative_level"] + 1, ls["base_level"])
    hi = min(ls["relative_level"] + ls["level_count"], ls["base_level"] + len(ls["multiplier_percent_by_level"]) - 1)
    return min(max(int(level), lo), hi)


def draw_live_levels(table: dict, learner_deck, opp_deck, key: str) -> dict:
    """One match's levels -> {"learner": {cards, tower}, "opp": {cards, tower, profile}} (cards in deck order), from a
    stream of its own seeded by ``key`` (no other stream moves). Learner: our live level per card (table own.cards,
    else own.default) and our tower level. Opponent: one live opponent drawn uniformly from opp_profiles (its tower
    level and the levels read off its cards); each of the 8 cards takes a level drawn from that opponent's card levels
    (its tower level when none was read). Every level is clamped into the card's range (``card_level``)."""
    rng = np.random.default_rng(zlib.crc32(f"live_levels:{key}".encode()))
    i = int(rng.integers(len(table["opp_profiles"])))
    _, tower, seen = table["opp_profiles"][i]
    own = table["own"]
    base = [str(n["name"] if isinstance(n, dict) else n).split("@")[0] for n in learner_deck]
    opp = [str(n["name"] if isinstance(n, dict) else n).split("@")[0] for n in opp_deck]
    return {"learner": {"cards": [card_level(n, own["cards"].get(n, own["default"])) for n in base],
                        "tower": int(own["tower"])},
            "opp": {"cards": [card_level(n, int(seen[int(rng.integers(len(seen)))]) if seen else int(tower)) for n in opp],
                    "tower": int(tower), "profile": i}}


def sample_matchups(rng: np.random.Generator, n: int, update: int, snaps: list[dict], cfg: dict, census: list[dict],
                    p: np.ndarray, league_state=None, exploiters: Optional[dict] = None) -> list[dict]:
    """``n`` league matchups (one LOO group each): opponent (``sample_opponent``), learner deck (``sample_deck``),
    opponent deck (the same rule; ALWAYS icebow for the S1 specialist, the only deck it can play), learner side
    (uniform) and the env's deal seed -- drawn in that order per matchup from ``rng`` (the learner's own, so resume
    continues the stream). ``league_learner_icebow_share`` (optional) replaces ``league_icebow_share`` for the
    learner's deck only; the draw order is the same either way (an icebow hit skips the census ``choice``).
    ``exploiters`` (``exploiter_league``; None = no extra draw, the stream above unchanged): first one uniform per
    matchup; below ``share`` the opponent is the exploiter and its deck is drawn from the exploiter pool."""
    out = []
    lshare = cfg.get("league_learner_icebow_share")
    lshare = cfg["league_icebow_share"] if lshare is None else lshare      # null = the shared rule (league1/1b)
    for i in range(int(n)):
        ex = exploiters is not None and rng.random() < exploiters["share"]
        adaptive = cfg.get("league_pfsp") == "hard" or cfg.get("league_frozen_opponent")
        opp = (exploiters["opp"] if ex else AO.sample_opponent(rng, snaps, cfg, league_state or {}) if adaptive else
               sample_opponent(rng, snaps, cfg["league_mix"], cfg["init"], cfg["league_specialist"]))
        ld = sample_deck(rng, census, p, lshare)
        od = (exploiters["decks"][int(rng.choice(len(exploiters["decks"]), p=exploiters["p"]))] if ex else
              ICEBOW_DECK if opp["type"] in ("s1", "frozen") else sample_deck(rng, census, p, cfg["league_icebow_share"]))
        out.append({"tag": f"sp{int(update):04d}_{i:02d}", "opp": opp,
                    "learner_deck": ld["engine"], "learner_deck_name": ld["name"], "learner_bucket": ld["bucket"],
                    "opp_deck": od["engine"], "opp_deck_name": od["name"],
                    "learner_side": int(rng.integers(2)), "seed": int(rng.integers(2 ** 31 - 1))})
        if cfg.get("opp_tower_troops") is not None:          # L74 troops: absent / null = no key (unchanged)
            out[-1]["opp_tower"] = draw_tower_troop(cfg["opp_tower_troops"], f"{out[-1]['seed']}:{out[-1]['tag']}")
        if cfg.get("live_levels"):                            # L74 factor D: absent / null / false = no key (unchanged)
            out[-1]["levels"] = draw_live_levels(_live_level_table(cfg["live_levels"]), ld["engine"], od["engine"],
                                                 f"{out[-1]['seed']}:{out[-1]['tag']}")
    return out


def league_monitors(results: list[dict]) -> dict:
    """Per-update self-play monitors: learner W/L/D and win rate by opponent type and by learner-deck bucket, draws,
    learner and opponent plays/min."""
    def wdl(rs):
        n = len(rs)
        w, l_ = sum(r["outcome"] == "win" for r in rs), sum(r["outcome"] == "loss" for r in rs)
        return {"n": n, "W": w, "L": l_, "D": n - w - l_, "winrate": w / n if n else None}
    minutes = sum(r["seconds"] for r in results) / 60.0
    types = ["init", "snapshot", "s1"]
    types += sorted({r["league"]["opp"]["type"] for r in results} - set(types))
    return {"by_opp": {t: wdl([r for r in results if r["league"]["opp"]["type"] == t]) for t in types},
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
            gae_terminal_gap: bool = False, spell: Optional[dict] = None,
            crown: Optional[dict] = None) -> tuple[dict, dict]:
    """Rollout result records (each with ``traj`` = ``Match._traj_arrays``) -> numpy batch of the CONTRIBUTING rows
    (gate sampled or card/cell played) with per-row A, per-match weight w, match id, and the stored log-probs.
    ``advantage="gae"`` adds ``r_step`` (``terminal_rewards``, the UNSHAPED win/loss reward); A stays the LOO value
    until ``gae_batch`` replaces it. ``gamma_tick`` (gae only; ``gae_gamma_unit: tick``): + ``gamma_row`` per kept
    row (``row_gammas`` of the traj ``tick``), the discount GAE and the shaping use. ``shaping`` (gae only; {gamma,
    w_tower, w_crown}; gamma replaced by ``gamma_row`` under gamma_tick): + ``phi`` (Phi(s_t)) per kept row (the
    residual critic's base, ``gae_batch``), and the F / Phi stats under ``st["shaping"]``. ``gae_terminal_gap``
    discounts only the last reward by gamma_tick ** (end_tick - last_kept_tick); requires every result's end_tick.
    ``spell`` (gae only; ``spell_cfg``'s dict, L74 combo): + ``spell_value.row_rewards`` of each result's "spell" events on
    its rows (by the traj ``tick``) into r_step, ``phi`` = 0 when no shaping made one (the residual critic at the config's
    scale), and the per-update monitors under ``st["spell"]``. ``crown`` (gae only; ``crown_cfg``'s dict, L74 W6): + each
    result's ``reward_terms.row_terms`` on its kept rows (by the traj ``tick``) into r_step, the princess_redirect potential
    into ``phi`` (added to a shaping phi), ``phi`` = 0 otherwise, and the monitors under ``st["crown"]``."""
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
        k = (t["gate_sampled"] | t["played"]) if len(t["played"]) else np.zeros(0, dtype=bool)
        if "posture_new" in t and len(t["played"]):          # C1: a row that chose the posture is kept (its log-prob)
            k = k | t["posture_new"]
        if "ab_sampled" in t and len(t["played"]):           # B6: a row with a press decision is kept (its log-prob)
            k = k | t["ab_sampled"]
        keep.append(k)
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
    if gen and "cue" in results[use[0]]["traj"]:                      # step c: the cue rows (a model with cue_in)
        extra += E.GEN_CUE_KEYS
    B = {k: cat(lambda j, k=k: results[j]["traj"][k][keep[j]]) for k in TRAJ_KEYS + extra}
    for k in ("lp_gate", "lp_card", "lp_cell"):
        B[k] = cat(lambda j, k=k: results[j]["traj"][k][keep[j]])
    B["lp_old"] = B["lp_gate"] + B["lp_card"] + B["lp_cell"]
    B["A"] = cat(lambda j: np.full(n_rows[j], A[j]))
    B["w"] = cat(lambda j: W[j])
    B["match"] = cat(lambda j: np.full(n_rows[j], j))
    if use and "ctx" in results[use[0]]["traj"]:                     # critic_ctx: actor_cfg record_ctx rows
        B["ctx"] = cat(lambda j: results[j]["traj"]["ctx"][keep[j]])
    if use and "elixir" in results[use[0]]["traj"]:                  # F6': actor_cfg record_elixir rows
        B["elixir"] = cat(lambda j: results[j]["traj"]["elixir"][keep[j]])
    if use and "posture" in results[use[0]]["traj"]:                 # C1: actor_cfg posture rows
        for k in ("posture", "posture_dtau", "posture_lp", "posture_new"):
            B[k] = cat(lambda j, k=k: results[j]["traj"][k][keep[j]])
        nc = {j: int(results[j]["traj"]["posture_new"][keep[j]].sum()) for j in use}
        Mp = max(1, sum(1 for n in nc.values() if n))           # w_post: each match's choices sum to 1/Mp
        B["w_post"] = cat(lambda j: np.where(results[j]["traj"]["posture_new"][keep[j]], 1.0 / (max(nc[j], 1) * Mp), 0.0))
    if use and "ab_sampled" in results[use[0]]["traj"]:              # B6: the press decisions (actor cfg ability)
        for k in ("ab_sampled", "ab_press", "ab_lp", "ab_feat"):
            B[k] = cat(lambda j, k=k: results[j]["traj"][k][keep[j]])
        na = {j: int(results[j]["traj"]["ab_sampled"][keep[j]].sum()) for j in use}
        Ma = max(1, sum(1 for n in na.values() if n))           # w_ab: each match's decisions sum to 1/Ma
        B["w_ab"] = cat(lambda j: np.where(results[j]["traj"]["ab_sampled"][keep[j]], 1.0 / (max(na[j], 1) * Ma), 0.0))
    sh = None
    if advantage == "gae":
        rs = terminal_rewards(n_rows, [r["outcome"] for r in results])
        if gae_terminal_gap:
            for j in use:
                gap = results[j]["end_tick"] - results[j]["traj"]["tick"][keep[j]][-1]
                if not np.isfinite(gap) or gap < 0:
                    raise ValueError(f"gae_terminal_gap: end_tick must be finite and >= last kept tick for result {j}")
                rs[j][-1] *= gamma_tick ** gap
        if spell is not None:                                 # L74 combo: the Rocket / setup-Tornado rows' reward
            sp, lost = {}, 0
            for j in use:
                if "tick" not in results[j]["traj"]:
                    raise ValueError("spell_value_reward needs the per-row tick (actor_cfg record_tick)")
                sp[j] = SV.row_rewards(results[j].get("spell"), results[j]["plays"], results[j]["traj"]["tick"], spell)
                lost += int(np.count_nonzero(sp[j]["r"][~keep[j]]))     # a played row is always kept: 0
                rs[j] = rs[j] + sp[j]["r"][keep[j]]
        if crown is not None:                                 # L74 W6: the crown terms on each match's kept rows
            cr = {}
            for j in use:
                if "tick" not in results[j]["traj"] or "crown" not in results[j]:
                    raise ValueError("crown terms need the per-row tick and the crown record (actor_cfg crown_track)")
                cr[j] = RT.row_terms(results[j]["crown"], results[j]["plays"], results[j]["traj"]["tick"][keep[j]], crown)
                rs[j] = rs[j] + cr[j]["r"]
        B["r_step"] = cat(lambda j: rs[j])
        gr = None
        if gamma_tick is not None:
            gr = {j: row_gammas(results[j]["traj"]["tick"][keep[j]], gamma_tick) for j in use}
            B["gamma_row"] = cat(lambda j: gr[j])
        if shaping is not None and shaping.get("mode") in ("value_phi", "live_phi"):     # lever C: the frozen net on B's inputs
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
        if crown is not None and crown.get("princess_redirect") == "potential":   # L74 W6: Phi into the residual critic
            ph = cat(lambda j: cr[j]["phi"])
            B["phi"] = B["phi"] + ph if "phi" in B else ph
        if (spell is not None or crown is not None) and "phi" not in B:   # combo / W6: residual critic, Phi = 0
            B["phi"] = np.zeros(len(B["r_step"]))
    elif shaping is not None or gamma_tick is not None or spell is not None or crown is not None:
        raise ValueError("shaping / gamma_tick / spell / crown need advantage gae")
    st = {"matches": len(results), "groups": len(groups), "mixed_groups": mixed,
          "mixed_group_share": mixed / max(len(groups), 1), "mean_abs_A": float(np.abs(A).mean()) if len(A) else 0.0,
          "rows": int(len(B["A"])), "rows_played": int(B["played"].sum()), "rows_gate": int(B["gate_sampled"].sum()),
          "decisions": int(sum(len(r["traj"]["played"]) for r in results))}
    if sh is not None and shaping.get("mode") in ("value_phi", "live_phi"):
        st["shaping"] = value_phi_stats([sh[j] for j in use], [reward(results[j]["outcome"]) for j in use])
        st["shaping"]["mode"] = shaping["mode"]
    elif sh is not None:
        st["shaping"] = shaping_stats([sh[j] for j in use])
        if shaping.get("mode") in RS.STATE_PHI_MODES:
            st["shaping"]["mode"] = shaping["mode"]
    if spell is not None:                                     # L74 combo monitors (wins: rollout_monitors' winrate)
        st["spell"] = {**SV.batch_stats([SV.match_summary(results[j].get("spell"), spell) for j in use],
                                        [float(sp[j]["r"].sum()) for j in use]),
                       "w": spell["spell_value_w"], "rows_rewarded": int(sum(np.count_nonzero(sp[j]["r"]) for j in use)),
                       "rows_lost": lost, "unmapped_rockets": sum(e["row"] is None for j in use for e in sp[j]["events"]),
                       # learner_pipeline_frac: matches that ran pipelined decisions, and their accepted second plays
                       "pipelined_matches": sum("pipeline_decisions" in r for r in results),
                       "second_plays": sum(r.get("pipeline_decisions", {}).get("second_plays", 0) for r in results)}
    if crown is not None:                                     # L74 W6 monitors
        st["crown"] = RT.batch_stats([RT.match_summary(results[j]["crown"]) for j in use], [cr[j] for j in use])
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
    terms ``phi_tower`` / ``phi_crown``. Step 3 (``shaping["mode"]`` solvency / tower_score): the rows are that mode's
    ``reward_shaping.state_record`` rows, Phi = ``reward_shaping.state_phi`` with ``shaping["params"]`` -> F, phi."""
    g = shaping["gamma"]
    if shaping.get("mode") in RS.STATE_PHI_MODES:
        ph = RS.state_phi(shaping["mode"], phi_rows, shaping["params"]) if len(phi_rows) else np.zeros(0)
        out = RS.shaping_from_parts(ph.tolist(), [0.0] * len(ph), float(g) if np.ndim(g) == 0 else g, (1.0, 0.0))
        return {"F": np.asarray(out["F"]), "phi": np.asarray(out["phi"][:-1])}
    pt, pc = (np.atleast_1d(x).astype(np.float64) for x in RS.phi_parts(phi_rows))
    wt, wc = float(shaping["w_tower"]), float(shaping["w_crown"])
    out = RS.shaping_from_parts(pt.tolist(), pc.tolist(), float(g) if np.ndim(g) == 0 else g, (wt, wc))
    return {"F": np.asarray(out["F"]), "tower": np.asarray(out["tower"]), "crown": np.asarray(out["crown"]),
            "phi": np.asarray(out["phi"][:-1]), "phi_tower": wt * pt, "phi_crown": wc * pc}


def shaping_stats(per_match: list[dict]) -> dict:
    """Per-update R2 monitors over every kept row: mean |F| and |Phi(s_t)|, each per term, and ``shaping_dominates``
    = mean |Phi| / 1.0 (the terminal reward's magnitude; plan 3b: -Phi(s_t) is the shaping part of every
    return-to-go, so a value above 0.5 means shaping is louder than half of winning)."""
    c = (lambda k: np.concatenate([m[k] for m in per_match]) if per_match else np.zeros(0))
    m = (lambda k: float(np.abs(c(k)).mean()) if len(c(k)) else None)
    keys = [k for k in ("F", "tower", "crown", "phi", "phi_tower", "phi_crown") if not per_match or k in per_match[0]]
    st = {f"mean_abs_{k}": m(k) for k in keys}                          # step 3 modes: F and phi only
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


def policy_terms(model, B: dict, idx, tau: float, T: float, value: bool = False, value_trunk: bool = True,
                 T_gate: Optional[float] = None, ctx_head=None) -> dict:
    """Recompute the behaviour log-probs of rows ``idx`` exactly as ``e1_eval.sample_decide_batch`` defined them:
    gate ``sigmoid((z - logit(tau)) / T)`` on gate-sampled rows; card softmax over ``allowed`` of the heads'
    hand-masked logits / T and cell softmax over 2,304 for the recorded slot / T on played rows; float64 after the
    float32 forward, as the sampler. Gradients flow unless the caller is in no_grad.
    Generalist rows (``hand_card`` in B, a GenModel ``model``): the forward is ``e1_eval.GenPolicy.heads_t`` -- the
    sampler's own function -- so card = the hand-position logits on their deck slots (softmax over allowed slots ==
    over allowed hand positions) and cell = ``cell_logits_gen`` for the slot's card identity + form.
    ``value``: also ``v`` = ``value_scalar`` of the value head on the same forward (gae mode only); ``value_trunk``
    False (``vf_trunk_grad: false``) detaches the trunk features under ``v``, so a loss on ``v`` reaches value_head only.
    ``ctx_head`` (critic_ctx): ``v`` also adds the ``CtxHead`` residual on ``B["ctx"]`` (same g, same detach rule)."""
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
    lt = _logit(tau)
    if "posture_dtau" in B:                                   # C1: the threshold of the posture in force (e1_eval)
        tt = tau + B["posture_dtau"][idx]
        lt = torch.log(tt / (1.0 - tt))
    x = (heads["gate"].double() - lt) / (T_gate or T)                   # T_gate: the sampler's own gate temperature
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
    out = {"x": x, "card_lp": card_lp, "cell_lp": cell_lp, "lp_gate": lp_gate, "lp_card": lp_card, "lp_cell": lp_cell,
           "g": enc["g"]}                                    # C1: the posture head's input (detached by the head)
    if value:
        g = enc["g"] if value_trunk else enc["g"].detach()
        out["v"] = value_scalar(critic_logits(model, g, ctx_head, B["ctx"][idx] if ctx_head is not None else None))
    return out


@torch.no_grad()
def value_rows(model, B: dict, chunk: int = 512, ctx_head=None) -> torch.Tensor:
    """V(s) (``value_scalar``) of every row under ``model``, no grad: the encoder + value head only (+ ``ctx_head``
    on ``B["ctx"]`` under critic_ctx)."""
    N = len(B["A"])
    out = []
    for s in range(0, N, chunk):
        idx = torch.arange(s, min(s + chunk, N), device=B["A"].device)
        if "hand_card" in B:
            enc = model.encode_gen({k: B[k][idx] for k in E.gen_row_keys(model)})
        else:
            enc = model.encode(B["tok"][idx], B["mask"][idx], B["sc"][idx], B["past"][idx])
        out.append(value_scalar(critic_logits(model, enc["g"], ctx_head,
                                              B["ctx"][idx] if ctx_head is not None else None)))
    return torch.cat(out) if out else torch.zeros(0, dtype=torch.float64, device=B["A"].device)


@torch.no_grad()
def posture_snapshot(model, head, B: dict, chunk: int = 512) -> Optional[dict]:
    """C1, once per update BEFORE the steps: the trunk g (``model``'s encoder, as policy_terms; ``chunk`` rows per
    forward, as value_rows) and the head's log-probs at every row that chose a posture. None without such rows."""
    ch = B["posture_new"].nonzero().squeeze(-1)
    if not len(ch):
        return None
    gs = []
    for s in range(0, len(ch), chunk):
        c = ch[s:s + chunk]
        if "hand_card" in B:
            gs.append(model.encode_gen({k: B[k][c] for k in E.gen_row_keys(model)})["g"])
        else:
            gs.append(model.encode(B["tok"][c], B["mask"][c], B["sc"][c], B["past"][c])["g"])
    g = torch.cat(gs)
    ctx = B["ctx"][ch]
    return {"g": g, "ctx": ctx, "lp": torch.log_softmax(head(g, ctx).double(), dim=-1)}


@torch.no_grad()
def posture_monitors(Bn: dict, snap: Optional[dict], head) -> dict:
    """C1 logging (no training quantity): posture shares over the kept rows (the posture IN FORCE; overall, by the
    row's ctx tank flag and phase) and over the choices, mean dtau, and at the choice rows the pre-update head's
    entropy and KL(pre || post) of the head on the same g (``snap``; call after the update)."""
    z, ctx, new = Bn["posture"], Bn["ctx"], Bn["posture_new"].astype(bool)

    def share(sel):
        n = int(sel.sum())
        return {"n": n, **{p: float((z[sel] == i).mean()) for i, p in enumerate(POSTURES)}} if n else {"n": 0}
    out = {"share": share(np.ones(len(z), dtype=bool)), "share_choices": share(new),
           "share_by_tank": {"tank": share(ctx[:, 1] == 1), "no_tank": share(ctx[:, 1] == 0)},
           "share_by_phase": {ph: share(ctx[:, 2] == i) for i, (_, ph) in enumerate(PHASES)},
           "mean_dtau": float(Bn["posture_dtau"].mean()) if len(z) else None, "entropy": None, "kl_prev": None}
    if snap is not None:
        lp1 = torch.log_softmax(head(snap["g"], snap["ctx"]).double(), dim=-1)
        out["entropy"] = float(cat_ent(snap["lp"]).mean())
        out["kl_prev"] = float(cat_kl(snap["lp"], lp1).mean())
    return out


def ctx_tank_stats(v_ev, ret, v_net, target, ctx, match) -> dict:
    """critic_ctx diagnostics (logging only): rows split by the tank flag of their match's LAST kept row's context
    (the opponent showed a tank by the end, or not) -> per group {rows, value_loss = mean 0.5 (v_net - target)^2,
    explained_var of v_ev for ret} -- the same pairs as gae_batch's value_mae / explained_var, at the behaviour critic
    (before this update's steps)."""
    m = np.asarray(match)
    last = np.r_[m[1:] != m[:-1], True] if len(m) else np.zeros(0, dtype=bool)
    end = dict(zip(m[last].tolist(), np.asarray(ctx)[last, 1].tolist()))
    tank = np.array([end[x] for x in m.tolist()], dtype=bool)
    out = {}
    for name, sel in (("tank", tank), ("no_tank", ~tank)):
        n = int(sel.sum())
        out[name] = {"rows": n, "value_loss": float((0.5 * (v_net[sel] - target[sel]) ** 2).mean()) if n else None,
                     "explained_var": explained_variance(v_ev[sel], ret[sel]) if n else None}
    return out


def gae_batch(model, B: dict, cfg: dict, ctx_head=None) -> dict:
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
    |v_net| > 0.95, ``value_mae`` = mean |v_net - target| (residual target with shaping, ret otherwise).
    ``ctx_head`` (critic_ctx; needs ``B["ctx"]``): v_net includes the ``CtxHead`` residual, and ``ctx_tank`` splits
    the value loss / explained variance by the match's final tank flag (``ctx_tank_stats``)."""
    c = adv_cfg(cfg)
    v = value_rows(model, B, ctx_head=ctx_head)
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
    if ctx_head is not None:
        st["ctx_tank"] = ctx_tank_stats(vn if "phi" not in B else veff, ret, vn, target, B["ctx"].cpu().numpy(), m)
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
def ref_terms(ref, B: dict, tau: float, T: float, chunk: int = 512, T_gate: Optional[float] = None,
              gate_ref=None, gate_lo_max: Optional[float] = None, card_ref=None) -> dict:
    """Frozen-ref tempered distributions for every row, once per update (E1 3.4): gate x [N], card log-probs [N, 8],
    cell log-probs [P, 2304] for the P played rows (``play_pos`` maps a row to its position, -1 if not played).
    ``gate_ref`` (F6 ``kl_ref_gate``): the gate x -- and so KL_gate and the gate entropy baseline -- comes from this
    second frozen net instead; card and cell stay ``ref``'s. None = unchanged.
    ``gate_lo_max`` (F6', needs gate_ref and ``B["elixir"]``): only rows with elixir < gate_lo_max (``R["low"]``) take
    gate_ref's x; the others keep ``ref``'s (so the entropy baseline follows the split). ``R["kl_lo_init"]`` = mean
    KL(ref gate || gate_ref gate) over the low gate-sampled rows (None without such rows): update 0's KL_gate_imit_low.
    ``card_ref`` (K1 ``kl_ref_card``): the card log-probs come from this frozen net instead; None = unchanged."""
    N = len(B["A"])
    dev = B["A"].device
    if gate_lo_max is not None and (gate_ref is None or "elixir" not in B):
        raise ValueError("gate_lo_max needs gate_ref and the per-row elixir (actor_cfg record_elixir)")
    xs, xis, cards, cells = [], [], [], []
    for s in range(0, N, chunk):
        idx = torch.arange(s, min(s + chunk, N), device=dev)
        t = policy_terms(ref, B, idx, tau, T, T_gate=T_gate)
        if gate_ref is not None:
            xg = policy_terms(gate_ref, B, idx, tau, T, T_gate=T_gate)["x"]
            if gate_lo_max is None:
                t["x"] = xg
            else:
                xis.append(xg)
        if card_ref is not None:
            t["card_lp"] = policy_terms(card_ref, B, idx, tau, T, T_gate=T_gate)["card_lp"]
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
    if gate_lo_max is not None:
        low, xi = B["elixir"] < gate_lo_max, torch.cat(xis)
        sel = gs & low
        R["kl_lo_init"] = float(bern_kl(R["x"][sel], xi[sel]).mean()) if sel.any() else None
        R["x"], R["low"] = torch.where(low, xi, R["x"]), low
    R["ent"] = {"gate": float(bern_ent(R["x"][gs]).mean()) if gs.any() else None,
                "card": float(cat_ent(R["card_lp"][played]).mean()) if played.any() else None,
                "cell": float(cat_ent(R["cell_lp"]).mean()) if len(R["cell_lp"]) else None}
    return R


def minibatch_loss(model, B: dict, R: dict, idx, *, tau: float, T: float, clip: float, beta: float,
                   n_total: int, vf: Optional[dict] = None, T_gate: Optional[float] = None,
                   posture: Optional[dict] = None, ability: Optional[dict] = None) -> tuple[torch.Tensor, dict]:
    """PPO-clip on the joint log pi = lp_gate + g (lp_card + lp_cell) (E1 3.3) with per-match weights, scaled by
    n_total / |mb| so each minibatch estimates the full-batch loss; + beta (mean KL_gate + mean KL_card + mean KL_cell).
    ``vf`` (gae mode: {coef, clip, policy}): + coef x the PPO-clipped value loss 0.5 max((V - ret)^2, (V_old +
    clip(V - V_old, +-clip) - ret)^2), per-match weighted like L_pg; ``policy`` False (critic warm-up) = the value
    loss ALONE (no L_pg, no KL term); ``trunk_grad`` False (default True) = the value loss trains value_head only.
    ``vf["ctx_head"]`` (critic_ctx): V includes that ``CtxHead`` (its params get the value loss's gradient).
    None = the match_loo loss, unchanged.
    ``R["low"]`` (F6' ``ref_terms(gate_lo_max=)``): KL_gate = the mean over the HIGH gate-sampled rows only, and
    + ``R["beta_g"]`` x ``kl_gate_imit_low`` (the same per-row KL, mean over the LOW gate-sampled rows, to R's x there,
    i.e. the anchor net's; None without such rows).
    ``posture`` (C1 {head, ent_coef}): + its own PPO-clip term on the rows that CHOSE a posture, r = pi_new(z) /
    pi_old(z) (``B["posture_lp"]``) with the row's A, weighted by ``B["w_post"]`` (each match's choices sum to 1/M) and
    scaled like L_pg, minus ent_coef x the same-weighted entropy of the head; the head reads g detached, so this term
    reaches the head only. Dropped with L_pg in the critic warm-up.
    ``ability`` (B6 {head, ent_coef}): the same construction for the press decisions (``B["ab_sampled"]`` rows):
    r = pi_new(a) / pi_old(a) of the Bernoulli press (``B["ab_lp"]``), the row's A, weights ``B["w_ab"]``, minus
    ent_coef x the head's weighted Bernoulli entropy; reaches the AbilityHead only (g detached)."""
    t = policy_terms(model, B, idx, tau, T, value=vf is not None,
                     value_trunk=True if vf is None else bool(vf.get("trunk_grad", True)), T_gate=T_gate,
                     ctx_head=None if vf is None else vf.get("ctx_head"))
    lp_new = t["lp_gate"] + t["lp_card"] + t["lp_cell"]
    ratio = torch.exp(lp_new - B["lp_old"][idx])
    A, w = B["A"][idx], B["w"][idx]
    pg = -torch.min(ratio * A, ratio.clamp(1 - clip, 1 + clip) * A)
    l_pg = (w * pg).sum() * (n_total / len(idx))
    gs, pl = B["gate_sampled"][idx], B["played"][idx]
    zero = lp_new.new_zeros(())
    kl_gi = None
    if "low" in R:                                            # F6': low rows -> their own term, high rows -> KL_gate
        lo = R["low"][idx]
        lo_gs = gs & lo
        gs = gs & ~lo
        if lo_gs.any():
            kl_gi = bern_kl(t["x"][lo_gs], R["x"][idx][lo_gs]).mean()
    kl_g = bern_kl(t["x"][gs], R["x"][idx][gs]).mean() if gs.any() else zero
    gs = B["gate_sampled"][idx]                               # the entropy monitor below: every gate-sampled row
    kl_c = cat_kl(t["card_lp"][pl], R["card_lp"][idx][pl]).mean() if pl.any() else zero
    kl_x = cat_kl(t["cell_lp"], R["cell_lp"][R["play_pos"][idx[pl]]]).mean() if pl.any() else zero
    if "kl_heads" in R:                                       # K1: only the leashed heads' KL enters the loss
        loss = l_pg + beta * sum({"gate": kl_g, "card": kl_c, "cell": kl_x}[h] for h in R["kl_heads"])
    else:
        loss = l_pg + beta * (kl_g + kl_c + kl_x)
    if kl_gi is not None:
        loss = loss + float(R["beta_g"]) * kl_gi
    pst = None
    if posture is not None:
        ch = B["posture_new"][idx]
        pst = {"l_post": None, "post_ratio_maxdev": None, "ent_posture": None, "post_n": int(ch.sum())}
        if ch.any():
            ii = idx[ch]
            lp_all = torch.log_softmax(posture["head"](t["g"][ch], B["ctx"][ii]).double(), dim=-1)
            pr = torch.exp(lp_all.gather(1, B["posture"][ii].unsqueeze(1)).squeeze(1) - B["posture_lp"][ii])
            Ap, wp = B["A"][ii], B["w_post"][ii]
            l_post = (wp * -torch.min(pr * Ap, pr.clamp(1 - clip, 1 + clip) * Ap)).sum() * (n_total / len(idx))
            ent_p = (wp * cat_ent(lp_all)).sum() * (n_total / len(idx))
            loss = loss + l_post - float(posture["ent_coef"]) * ent_p
            with torch.no_grad():
                pst.update(l_post=float(l_post), post_ratio_maxdev=float((pr - 1).abs().max()),
                           ent_posture=float(cat_ent(lp_all).mean()))
    ast = None
    if ability is not None:
        ch = B["ab_sampled"][idx]
        ast = {"l_ab": None, "ab_ratio_maxdev": None, "ent_ability": None, "ab_n": int(ch.sum())}
        if ch.any():
            ii = idx[ch]
            za = ability["head"](t["g"][ch], B["ab_feat"][ii]).double()
            lpa = torch.where(B["ab_press"][ii], Fn.logsigmoid(za), Fn.logsigmoid(-za))
            ar = torch.exp(lpa - B["ab_lp"][ii])
            Aa, wa = B["A"][ii], B["w_ab"][ii]
            l_ab = (wa * -torch.min(ar * Aa, ar.clamp(1 - clip, 1 + clip) * Aa)).sum() * (n_total / len(idx))
            ent_a = (wa * bern_ent(za)).sum() * (n_total / len(idx))
            loss = loss + l_ab - float(ability["ent_coef"]) * ent_a
            with torch.no_grad():
                ast.update(l_ab=float(l_ab), ab_ratio_maxdev=float((ar - 1).abs().max()),
                           ent_ability=float(bern_ent(za).mean()))
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
        if "low" in R:
            st["kl_gate_imit_low"] = None if kl_gi is None else float(kl_gi)
        if vf is not None:
            st["l_v"] = float(l_v)
        if pst is not None:
            st.update(pst)
        if ast is not None:
            st.update(ast)
    return loss, st


def vf_grad_share(model, B: dict, R: dict, cfg: dict, beta: float, vf: dict) -> dict:
    """gae-mode monitor (R1 verifier finding F2: the value loss also trains the shared trunk, moving the policy where
    the KL monitors do not look). On ONE minibatch (``minibatch`` rows strided over the batch; no step, no .grad
    written, no RNG drawn): the gradient norms, on the TRUNK, of the value part of the loss as trained (vf_coef x L_v;
    exactly 0 with ``vf["trunk_grad"]`` False) and of the policy part (L_pg + beta KL). Trunk = every parameter but
    value_head that the value loss reaches through the trunk features (critic_ctx's Learner-owned ``CtxHead`` is not
    a model parameter, so it is excluded too). -> {share = |g_v| / (|g_v| + |g_pg|), norms}."""
    N = len(B["A"])
    idx = torch.arange(0, N, max(1, N // int(cfg["minibatch"])), device=B["A"].device)[:int(cfg["minibatch"])]
    kw = dict(tau=cfg["tau"], T=cfg["T"], clip=cfg["clip"], beta=beta, n_total=N, T_gate=cfg.get("T_gate"))
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
               vf: Optional[dict] = None, posture: Optional[dict] = None, ability: Optional[dict] = None) -> dict:
    """``ppo_epochs`` passes over the batch in random minibatches. Returns the monitors; ``first`` = epoch 0 minibatch 0
    (the on-policy check), ``nonfinite`` set (and the step skipped) on a non-finite loss or gradient norm.
    ``vf`` (gae mode, ``minibatch_loss``): + ``l_v``; ``vf["policy"]`` False = critic warm-up: ONLY ``value_head``
    parameters get gradients (the trunk is shared with the policy heads, so training it would move the policy).
    ``vf["ctx_head"]`` / ``vf["ctx_opt"]`` (critic_ctx): the Learner-owned ``CtxHead`` (not in ``model``, so never
    frozen: it trains with the value head) and its own Adam, stepped with ``opt``; its grad norm is clipped
    separately at grad_clip, so the model's clipping is exactly the plain critic's.
    ``posture`` (C1 {head, opt, ent_coef}): the posture term (``minibatch_loss``) and the head's own Adam, stepped with
    ``opt``, grad norm clipped separately at grad_clip; no step in the critic warm-up (the term is dropped there).
    ``ability`` (B6 {head, opt, ent_coef}): the press term and the AbilityHead's own Adam, exactly as ``posture``."""
    frozen = [p for n, p in model.named_parameters()
              if vf is not None and not vf["policy"] and not n.startswith("value_head.") and p.requires_grad]
    for p in frozen:
        p.requires_grad_(False)
    try:
        return _ppo_steps(model, opt, B, R, cfg, beta, rng, vf, posture, ability)
    finally:
        for p in frozen:
            p.requires_grad_(True)


def _ppo_steps(model, opt, B: dict, R: dict, cfg: dict, beta: float, rng: np.random.Generator,
               vf: Optional[dict], posture: Optional[dict] = None, ability: Optional[dict] = None) -> dict:
    N = len(B["A"])
    dev = B["A"].device
    mb = int(cfg["minibatch"])
    first, last_ep, ep0 = None, [], []
    ratios, clips, gnorms = [], [], []
    mean = (lambda xs, k: float(np.mean([x[k] for x in xs if x[k] is not None])) if any(x[k] is not None for x in xs) else None)
    avg = (lambda xs: float(np.mean(xs)) if xs else None)
    ctx_opt = None if vf is None else vf.get("ctx_opt")
    post_opt = None if posture is None else posture["opt"]
    ab_opt = None if ability is None else ability["opt"]

    def summary(nonfinite: Optional[str]) -> dict:
        """Every key present even on the non-finite early exit (one_update logs them; None = not measured)."""
        return {"first": first, "nonfinite": nonfinite, "steps": len(ratios),
                **({"l_post": mean(last_ep, "l_post"), "ent_posture": mean(ep0, "ent_posture")}
                   if posture is not None else {}),
                **({"l_ab": mean(last_ep, "l_ab"), "ent_ability": mean(ep0, "ent_ability")}
                   if ability is not None else {}),
                "kl_gate": mean(last_ep, "kl_gate"), "kl_card": mean(last_ep, "kl_card"),
                "kl_cell": mean(last_ep, "kl_cell"), "l_pg": mean(last_ep, "l_pg"),
                **({"kl_gate_imit_low": mean(last_ep, "kl_gate_imit_low")} if "low" in R else {}),
                "ent": {h: mean(ep0, f"ent_{h}") for h in ("gate", "card", "cell")},
                "ratio_mean": avg(ratios), "clip_frac": avg(clips), "grad_norm_mean": avg(gnorms),
                **({"l_v": mean(last_ep, "l_v"), "l_v_first": first["l_v"] if first else None} if vf is not None else {})}

    for ep in range(int(cfg["ppo_epochs"])):
        perm = torch.from_numpy(rng.permutation(N)).to(dev)
        for s in range(0, N, mb):
            idx = perm[s:s + mb]
            loss, st = minibatch_loss(model, B, R, idx, tau=cfg["tau"], T=cfg["T"], clip=cfg["clip"], beta=beta,
                                      n_total=N, vf=vf, T_gate=cfg.get("T_gate"),
                                      **({"posture": posture} if posture is not None else {}),
                                      **({"ability": ability} if ability is not None else {}))
            if first is None:
                first = st
            if not torch.isfinite(loss):
                return summary(f"loss {float(loss.detach())} at epoch {ep} minibatch {s // mb}")
            opt.zero_grad(set_to_none=True)
            if ctx_opt is not None:
                ctx_opt.zero_grad(set_to_none=True)
            if post_opt is not None:
                post_opt.zero_grad(set_to_none=True)
            if ab_opt is not None:
                ab_opt.zero_grad(set_to_none=True)
            loss.backward()
            gn = torch.nn.utils.clip_grad_norm_(model.parameters(), float(cfg["grad_clip"]))
            if not torch.isfinite(gn):
                return summary(f"grad norm {float(gn)} at epoch {ep} minibatch {s // mb}")
            if ctx_opt is not None:
                gc = torch.nn.utils.clip_grad_norm_(vf["ctx_head"].parameters(), float(cfg["grad_clip"]))
                if not torch.isfinite(gc):
                    return summary(f"ctx_head grad norm {float(gc)} at epoch {ep} minibatch {s // mb}")
                ctx_opt.step()
            if post_opt is not None:
                gp = torch.nn.utils.clip_grad_norm_(posture["head"].parameters(), float(cfg["grad_clip"]))
                if not torch.isfinite(gp):
                    return summary(f"posture_head grad norm {float(gp)} at epoch {ep} minibatch {s // mb}")
                post_opt.step()
            if ab_opt is not None:
                ga = torch.nn.utils.clip_grad_norm_(ability["head"].parameters(), float(cfg["grad_clip"]))
                if not torch.isfinite(ga):
                    return summary(f"ability_head grad norm {float(ga)} at epoch {ep} minibatch {s // mb}")
                ab_opt.step()
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
        pb = base.get("posture")                              # C1: the head's weights arrive with each message
        phead = PostureHead(int(pb["d_g"]), int(pb.get("hidden", POSTURE_HIDDEN))).to(dev).eval() if pb else None
        ab = base.get("ability")                              # B6: likewise
        ahead = AbilityHead(int(ab["d_g"]), int(ab.get("hidden", ABILITY_HIDDEN)),
                            int(ab.get("n_feat", E.ABILITY_FEAT_N))).to(dev).eval() if ab else None
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
            msd, psd = split_actor_sd(sd, dev)
            asd = pop_prefix(msd, ABILITY_SD)
            net.load_state_dict(msd)
            net.eval()
            if psd:                                           # C1: this update's posture head
                phead.load_state_dict(psd)
            if asd:                                           # B6: this update's ability head
                ahead.load_state_dict(asd)

            def mk_cfg(k):
                """actor_cfg + the posture head when the message carried one (none: the ref's screen = no posture)."""
                c = actor_cfg(base, k, aid, dev)
                if "posture" in c:
                    if psd:
                        c["posture"] = {**c["posture"], "head": phead}
                    else:
                        del c["posture"]
                if "ability" in c:                            # B6: no head in the message -> the rule presses; a
                    if asd:                                   # rollout then records the rule's labels (warm start)
                        c["ability"] = {**c["ability"], "head": ahead}
                    elif k == "rollout":
                        c["ability"] = {"mode": "label", "n_feat": c["ability"]["n_feat"]}
                    else:
                        del c["ability"]
                return c
            cfg = mk_cfg(kind)
            results, skipped = [], []

            def on_result(line):
                if kind in ("rollout", "selfplay"):
                    line["rollout_index"], line["update"] = int(line["k"]), int(update)
                results.append(line)

            n_fl = max(1, min(int(base["in_flight"]), len(jobs)))
            fm = base.get("forms_mode", "base")                # RoyaleSim forms (royale_env.FORMS_MODES)
            on_skip = (lambda e, exc: skipped.append({"tag": e["tag"], "why": str(exc)}))
            if kind == "selfplay":
                cfg = mk_cfg("rollout")
                need = {j[1]["opp"]["path"] for j in jobs}
                for pth in [x for x in opp_cache if x not in need]:
                    del opp_cache[pth]
                for pth in need - set(opp_cache):
                    pol, mi = E.load_policy(REPO / pth, dev)
                    opp_cache[pth] = (pol, str(mi.get("grid", "floor")))
                ocfg0 = {k: v for k, v in cfg.items() if k not in ("posture", "ability")}   # C1 / B6: the learner's only
                opps = {j[1]["opp"]["id"]: (opp_cache[j[1]["opp"]["path"]][0],
                                            {**ocfg0, "policy": base["league_opp_policy"], "record": False, "T_gate": None,
                                             "T": opp_T(base),
                                             **{k: base[k] for k in AO.STYLE_KEYS if k in base},
                                             "grid": opp_cache[j[1]["opp"]["path"]][1]}) for j in jobs}
                specs = {j[1]["opp"]["id"]: j[1]["opp"] for j in jobs}
                opps = {i: (pol, own_opp_cfg(oc, specs[i], base))
                        for i, (pol, oc) in opps.items()}            # L74 human tempo (+ O6 per-exploiter): the OPPONENT's cfg only
                E.run_selfplay_batch(lambda: RoyaleSelfPlayEnv(decision_ticks=int(base["decide_every"]), forms_mode=fm,
                                                               hero_abilities=base.get("hero_abilities", False),
                                                               ability_policy=base.get("ability_policy", "generic"),
                                                               ability_features=base.get("ability_features") or "base"), model, opps,
                                     rollout_jobs(jobs, update, base.get("learner_pipeline_frac", 0), base["seed"]),
                                     cfg, n_fl, on_result=on_result, on_skip=on_skip,
                                     skip=(UnsupportedDeck,))
            else:
                it = (rollout_jobs(jobs, update, base.get("learner_pipeline_frac", 0), base["seed"])
                      if kind == "rollout" else jobs)     # screen: eval obs seed of (tag, k)
                E.run_batch(lambda: RoyalePoolEnv(decision_ticks=int(base["decide_every"]), forms_mode=fm,
                                                               hero_abilities=base.get("hero_abilities", False),
                                                               ability_policy=base.get("ability_policy", "generic"),
                                                               ability_features=base.get("ability_features") or "base"), model, deck, it, cfg,
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
    ocfg0 = {**actor_cfg(base, "rollout", wid, dev), "policy": base["league_opp_policy"], "record": False,
             "T_gate": None, "T": opp_T(base)}
    ocfg = E.opp_tempo(ocfg0, base.get("opp_decide_every"), base.get("opp_reaction_ticks"))
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
            oc = ocfg if not spec["opp"].get("cfg") else own_opp_cfg(ocfg0, spec["opp"], base)   # L74 O6: own T / tempo
            branch_jobs(sp_env, model, {spec["opp"]["id"]: (pol, {**oc, "grid": grid})}, [(n_match, {**spec, "tag": tag}, 0)],
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
                and k not in VALUE_PHI_KEYS and k not in STATE_PHI_KEYS and k not in AO.DEFAULTS
                and k not in ("league_learner_icebow_share", "learner_pipeline_frac", "league_opp_T", "kl_ref_gate",
                              "critic_ctx", "kl_ref_gate_max_elixir", "kl_ref_gate_target_frac",
                              "league_exploiters", "cue_inputs", "opp_tower_troops", "live_levels",
                              "heroiw_press", "ability_features", "kl_heads", "kl_ref_card") + OPP_TEMPO_KEYS
                and k not in POSTURE_KEYS and k not in ABILITY_KEYS and k not in SPELL_KEYS and k not in CROWN_KEYS):
            raise SystemExit(f"unknown config key {k!r}; keys: {sorted(cfg)}")
        cfg[k] = yaml.safe_load(v)
    if type(cfg["hero_abilities"]) is not bool:
        raise SystemExit("hero_abilities must be a bool")
    if cfg.get("kl_heads") is not None:                      # K1 (step d): absent / null = all three heads leashed
        hs = cfg["kl_heads"]
        if not isinstance(hs, list) or not hs or len(set(hs)) != len(hs) or not set(hs) <= {"gate", "card", "cell"}:
            raise SystemExit(f"kl_heads must be null or a non-empty list of distinct gate / card / cell, got {hs!r}")
        if cfg.get("leash", "cell") != "max":
            raise SystemExit("kl_heads needs leash: max (the leash steers on the max over the leashed heads)")
        cfg["kl_heads"] = [h for h in ("gate", "card", "cell") if h in hs]    # canonical order: one hash
    if cfg.get("kl_ref_card") is not None and not (isinstance(cfg["kl_ref_card"], str) and cfg["kl_ref_card"]):
        raise SystemExit(f"kl_ref_card must be null or a checkpoint path, got {cfg['kl_ref_card']!r}")
    if cfg.get("cue_inputs") not in (None, False, True):     # step c (yaml "on" = true): absent / null / false = off
        raise SystemExit(f"cue_inputs must be on / off (a bool) or null, got {cfg['cue_inputs']!r}")
    if smoke and cfg.get("ability_head") not in (None, False) and cfg.get("ability_bc_matches") is None:
        cfg["ability_bc_matches"] = SMOKE_AB_BC                # B6: a smoke-sized warm start (unless set explicitly)
    if cfg.get("stall_elixir") is not None:   # owner 2026-10-07: no anti-stall in training, ever (live has none)
        raise SystemExit("stall_elixir must be null: the anti-stall was removed permanently (owner 2026-10-07)")
    if cfg.get("ability_policy", "generic") not in ("generic", "v2"):
        raise SystemExit(f"ability_policy must be generic or v2, got {cfg['ability_policy']!r}")
    if cfg.get("ability_policy") == "v2" and not cfg["hero_abilities"]:
        raise SystemExit("ability_policy v2 needs hero_abilities=true")
    AO.validate(cfg)
    exploiter_league(cfg)                                     # O2: checked at start (files exist, league on); absent = no-op
    opp_tower_troops(cfg)                                     # L74 troops: checked at start; absent = no-op
    live_levels(cfg)                                          # L74 factor D: checked (and the table read) at start
    frac = cfg.get("learner_pipeline_frac", 0.0)
    if isinstance(frac, bool) or not isinstance(frac, (int, float)) or not 0 <= frac <= 1:
        raise SystemExit("learner_pipeline_frac must be a finite number in [0, 1]")
    if frac and int(cfg.get("action_delay_ticks", 0)) <= 0:
        raise SystemExit("learner_pipeline_frac needs action_delay_ticks > 0")
    if any(cfg.get(k) is not None for k in OPP_TEMPO_KEYS):
        if not cfg.get("league"):
            raise SystemExit(f"{'/'.join(OPP_TEMPO_KEYS)} need league true (they set the self-play opponent's tempo)")
        try:
            E.opp_tempo({}, cfg.get("opp_decide_every"), cfg.get("opp_reaction_ticks"))
        except ValueError as exc:
            raise SystemExit(str(exc))
    return cfg


def config_sha(cfg: dict) -> str:
    # Off is the historical configuration, including checkpoint resume hashes.
    cfg = AO.canonical_config(cfg)
    if cfg.get("learner_pipeline_frac", 0) == 0:
        cfg = {k: v for k, v in cfg.items() if k != "learner_pipeline_frac"}
    if cfg.get("hero_abilities") is False:
        cfg = {k: v for k, v in cfg.items() if k != "hero_abilities"}
    if cfg.get("ability_policy", "generic") == "generic":
        cfg = {k: v for k, v in cfg.items() if k != "ability_policy"}
    if cfg.get("kl_ref_gate") is None:                       # F6 off (absent or null) = the historical hash
        cfg = {k: v for k, v in cfg.items() if k != "kl_ref_gate"}
    for k in ("kl_heads", "kl_ref_card"):                    # K1 off (absent or null) = the historical hash
        if cfg.get(k) is None:
            cfg = {kk: v for kk, v in cfg.items() if kk != k}
    if cfg.get("league_exploiters") is None:                 # O2 off (absent or null) = the historical hash
        cfg = {k: v for k, v in cfg.items() if k != "league_exploiters"}
    if cfg.get("opp_tower_troops") is None:                  # L74 troops off (absent or null) = the historical hash
        cfg = {k: v for k, v in cfg.items() if k != "opp_tower_troops"}
    if not cfg.get("live_levels"):                           # L74 factor D off (absent / null / false) = the historical hash
        cfg = {k: v for k, v in cfg.items() if k != "live_levels"}
    elif cfg["live_levels"] != "all16":                       # true: measured bytes enter the hash; all16 keeps its string
        cfg = {**cfg, "live_levels": hashlib.sha256(LIVE_LEVELS.read_bytes()).hexdigest()}
    if cfg.get("heroiw_press") is None:                      # L74 overpress key absent / null = the historical hash
        cfg = {k: v for k, v in cfg.items() if k != "heroiw_press"}
    if cfg.get("critic_ctx") is None:                        # C2 / F2 off (absent or null) = the historical hash
        cfg = {k: v for k, v in cfg.items() if k != "critic_ctx"}
    if not cfg.get("cue_inputs"):                            # step c off (absent / null / false) = the historical hash
        cfg = {k: v for k, v in cfg.items() if k != "cue_inputs"}
    if cfg.get("kl_ref_gate_max_elixir") is None:            # F6' off (absent or null) = the historical hash
        cfg = {k: v for k, v in cfg.items() if k not in ("kl_ref_gate_max_elixir", "kl_ref_gate_target_frac")}
    elif cfg.get("kl_ref_gate_target_frac") is None:         # F6' frac absent / null = the 0.5 default, one hash
        cfg = {**cfg, "kl_ref_gate_target_frac": GATE_LO_FRAC}
    cfg = {k: v for k, v in cfg.items() if k not in OPP_TEMPO_KEYS or v is not None}   # human tempo off = historical hash
    if cfg.get("posture_head") is None or cfg.get("posture_head") is False:   # C1 off (absent / null / false) = historical
        cfg = {k: v for k, v in cfg.items() if k not in POSTURE_KEYS}
    else:                                                    # C1 on: defaults filled, one hash for implicit / explicit
        cfg = {**cfg, "posture_head": True, **{k: (v if cfg.get(k) is None else cfg[k]) for k, v in POSTURE_DEFAULTS.items()}}
        if isinstance(cfg["posture_dtau"], (list, tuple)):
            cfg["posture_dtau"] = [float(x) for x in cfg["posture_dtau"]]
    if cfg.get("ability_features") in (None, "base"):       # L74 head inputs absent / null / base = the historical hash
        cfg = {k: v for k, v in cfg.items() if k != "ability_features"}
    if cfg.get("ability_head") is None or cfg.get("ability_head") is False:   # B6 off (absent / null / false) = historical
        cfg = {k: v for k, v in cfg.items() if k not in ABILITY_KEYS}
    else:                                                    # B6 on: defaults filled, one hash for implicit / explicit
        cfg = {**cfg, "ability_head": True,
               **{k: (v if cfg.get(k) is None else cfg[k]) for k, v in ABILITY_DEFAULTS.items()}}
    if cfg.get("spell_value_reward") is None or cfg.get("spell_value_reward") is False:   # L74 combo off = historical
        cfg = {k: v for k, v in cfg.items() if k not in SPELL_KEYS}
    else:                                                    # on: defaults filled (floats), one hash for implicit / explicit
        cfg = {**cfg, "spell_value_reward": True,
               **{k: float(v if cfg.get(k) is None else cfg[k]) for k, v in SV.DEFAULTS.items()}}
        if cfg.get("spell_value_lone") is None or cfg.get("spell_value_lone") is False:   # lone off = the 10-18 hash
            cfg = {k: v for k, v in cfg.items() if k != "spell_value_lone" and k not in SV.LONE_DEFAULTS}
        else:                                                # lone on: defaults filled (floats)
            cfg = {**cfg, "spell_value_lone": True,
                   **{k: float(v if cfg.get(k) is None else cfg[k]) for k, v in SV.LONE_DEFAULTS.items()}}
    for k, wk in RT.TERMS.items():                           # L74 W6: off (absent / null / false) = the historical hash;
        if cfg.get(k) is None or cfg.get(k) is False:        # on: its weight filled, one hash for implicit / explicit
            cfg = {kk: v for kk, v in cfg.items() if kk not in (k, wk)}
        else:
            cfg = {**cfg, wk: float(RT.DEFAULTS[wk] if cfg.get(wk) is None else cfg[wk])}
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


def actor_bytes(model, posture_head=None, ability_head=None) -> bytes:
    """The actors' weights message: ``state_bytes(model)`` exactly without a head; C1 adds the posture head's tensors
    under ``POSTURE_SD`` keys, B6 the ability head's under ``ABILITY_SD`` (``split_actor_sd`` / ``pop_prefix``)."""
    if posture_head is None and ability_head is None:
        return state_bytes(model)
    buf = io.BytesIO()
    torch.save({**{k: v.detach().cpu() for k, v in model.state_dict().items()},
                **({POSTURE_SD + k: v.detach().cpu() for k, v in posture_head.state_dict().items()}
                   if posture_head is not None else {}),
                **({ABILITY_SD + k: v.detach().cpu() for k, v in ability_head.state_dict().items()}
                   if ability_head is not None else {})}, buf)
    return buf.getvalue()


def pop_prefix(sd: dict, prefix: str) -> dict:
    """Remove the ``prefix`` keys from ``sd`` (in place) -> them, prefix stripped ({} when none)."""
    return {k[len(prefix):]: sd.pop(k) for k in [k for k in sd if k.startswith(prefix)]}


def split_actor_sd(sd: bytes, dev) -> tuple[dict, dict]:
    """-> (the model's state_dict, the posture head's ({} when the message has none))."""
    msd = torch.load(io.BytesIO(sd), map_location=dev)
    return msd, pop_prefix(msd, POSTURE_SD)


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
        if gate_lo_cfg(cfg) is not None:                      # ... and the F6' keys; the frac default stored
            cfg["kl_ref_gate_target_frac"] = gate_lo_cfg(cfg)["frac"]
        pc = store_posture_cfg(cfg)                           # ... and the C1 keys; the defaults stored
        abc = store_ability_cfg(cfg)                          # ... and the B6 keys; the defaults stored
        heroiw_press_cfg(cfg)                                 # ... heroiw_press -> env (before any actor starts); refusal
        bc = branch_cfg(cfg)                                 # ... and the branch (opt3) keys
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
        if cfg.get("cue_inputs"):                             # step c (L74/cues/STEP_C_SPEC.md): a ZERO cue layer on the
            if not self.gen:                                  # init (kept if the init already has one); the rows follow
                raise SystemExit("cue_inputs needs a generalist (GenModel) init")   # the model (e1_eval.gen_row_keys)
            E.require_cue_runtime()
            if getattr(self.model, "cue_in", None) is None:
                self.model.add_cue_in()
        self.init_meta = {"args": dict(ick["args"]), "deck": ick["deck"], "epoch": ick["epoch"], "n_params": ick["n_params"]}
        self.grid = self.minfo["grid"]
        self.league = None                                    # league on: {"snapshots": [{id, update, path}]}
        if cfg.get("league"):
            self._league_setup()
        self.ref = copy.deepcopy(self.model).eval()
        for p in self.ref.parameters():
            p.requires_grad_(False)
        self.gate_ref = self._load_gate_ref(ick) if cfg.get("kl_ref_gate") is not None else None   # F6
        self.card_ref = self._load_gate_ref(ick, "kl_ref_card") if cfg.get("kl_ref_card") is not None else None   # K1
        if adv_cfg(cfg)["shaping"] in ("value_phi", "live_phi"):            # lever C: the frozen Phi net, loaded once from FILE
            self.phi_net = self._load_phi_net(ick)            # (never self.model / a resumed one), never trained
        self.model.eval()                                     # eval() for rollout AND update (E1 3.3 dropout trap)
        self.opt = torch.optim.Adam(self.model.parameters(), lr=float(cfg["lr"]))
        if adv_cfg(cfg).get("critic_ctx") is not None:       # C2 / F2: the critic's context head + its own Adam
            self._ctx_setup()
        if pc is not None:                                    # C1: the posture head + its own Adam
            self._posture_setup()
        if abc is not None:                                   # B6: the ability head + its own Adam
            self._ability_setup()
        if branch_cfg(cfg)["branch_gate"]:                   # opt3: the branch step's OWN Adam (never PPO's state)
            self.branch_opt = self._branch_optimizer(branch_cfg(cfg))
        self.beta, self.update = float(cfg["beta0"]), 0
        if gate_lo_cfg(cfg) is not None:                      # F6': the low-row anchor's coefficient + update-0 target
            self.beta_g, self.gate_lo_target = float(cfg["beta0"]), None
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

    def _ctx_setup(self) -> None:
        """critic_ctx: ``self.ctx_head`` (``CtxHead`` on the value head's input width; first layer drawn from a torch RNG
        seeded with the run seed inside fork_rng over the CPU AND every CUDA device -- torch.manual_seed seeds CUDA too --
        so the global torch RNG states are untouched) and ``self.ctx_opt`` (Adam, lr).
        Neither is in the model's state_dict; the checkpoint carries them under rl["ctx_head"] / rl["ctx_optimizer"]."""
        with torch.random.fork_rng(devices=list(range(torch.cuda.device_count()))):
            torch.manual_seed(int(self.cfg["seed"]))
            self.ctx_head = CtxHead(self.cfg["critic_ctx"], self.model.value_head.in_features).to(self.dev)
        self.ctx_opt = torch.optim.Adam(self.ctx_head.parameters(), lr=float(self.cfg["lr"]))

    def _posture_setup(self) -> None:
        """C1: ``self.posture_head`` (``PostureHead`` on the value head's input width = g; first layer drawn inside
        fork_rng from a seed of its own, global torch RNG untouched) and ``self.posture_opt`` (Adam, posture_lr). Neither is in
        the model's state_dict; the checkpoint carries rl["posture_head"] / ["posture_optimizer"] / ["posture"]."""
        with torch.random.fork_rng(devices=list(range(torch.cuda.device_count()))):
            torch.manual_seed(zlib.crc32(f"posture:{int(self.cfg['seed'])}".encode()))
            self.posture_head = PostureHead(self.model.value_head.in_features).to(self.dev)
        self.posture_opt = torch.optim.Adam(self.posture_head.parameters(), lr=float(self.cfg["posture_lr"]))

    def _posture_meta(self) -> dict:
        return {"every": int(self.cfg["posture_every"]), "dtau": [float(x) for x in self.cfg["posture_dtau"]],
                "d_g": int(self.model.value_head.in_features), "hidden": POSTURE_HIDDEN}

    def _ability_setup(self) -> None:
        """B6: ``self.ability_head`` (``AbilityHead`` on g's width; first layer drawn inside fork_rng from its own seed,
        global torch RNG untouched) and ``self.ability_opt`` (Adam, ability_lr). Neither is in the model's state_dict;
        the checkpoint carries rl["ability_head"] / ["ability_optimizer"] / ["ability"]."""
        with torch.random.fork_rng(devices=list(range(torch.cuda.device_count()))):
            torch.manual_seed(zlib.crc32(f"ability:{int(self.cfg['seed'])}".encode()))
            self.ability_head = AbilityHead(self.model.value_head.in_features, n_feat=self._ability_n_feat()).to(self.dev)
        self.ability_opt = torch.optim.Adam(self.ability_head.parameters(), lr=float(self.cfg["ability_lr"]))
        self.ability_bc = None                                # the warm start's monitors (``_ability_warm_start``)

    def _ability_n_feat(self) -> int:
        return E.ABILITY_FEAT_SETS[self.cfg.get("ability_features") or "base"]

    def _ability_meta(self) -> dict:
        feats = self.cfg.get("ability_features") or "base"
        return {"d_g": int(self.model.value_head.in_features), "hidden": ABILITY_HIDDEN, "n_feat": self._ability_n_feat(),
                **({"features": feats} if feats != "base" else {}),
                "bc": _py(getattr(self, "ability_bc", None))}

    def _ability_warm_start(self) -> None:
        """B6 imitation warm start (fresh run, before the init screen and u0000): ``ability_bc_matches`` rollouts of the
        INIT policy with the press RULE acting for the learner (the weights message carries no ability head -> the
        actors' label mode), matchups / entries drawn from an rng of its own (the learner's rng untouched); every
        learner decision with a pressable button gives (g of the row under the init, its features, the rule's q) ->
        ``ability_bc_fit``. Without labels (no hero in any learner deck, hero_abilities off) the head keeps its init."""
        cfg, n = self.cfg, int(self.cfg["ability_bc_matches"])
        t = time.perf_counter()
        if not cfg.get("hero_abilities"):
            self.log("[rl] ability_head: hero_abilities is false -- no button is ever pressable, the head never decides "
                     "(no warm start)")
            return
        if n == 0:
            self.log("[rl] ability_head: ability_bc_matches 0 -- no imitation warm start (P(press) = ABILITY_P0)")
            return
        rng = np.random.default_rng(zlib.crc32(f"ability_bc:{int(cfg['seed'])}".encode()))
        if getattr(self, "league", None) is not None:
            specs = sample_matchups(rng, n, 0, self.league["snapshots"], cfg, self.census, self.census_p,
                                    **({"league_state": self.league} if cfg.get("league_pfsp") == "hard" else {}),
                                    exploiters=getattr(self, "exploiters", None))
            kind, jobs = "selfplay", [(i, sp, 0) for i, sp in enumerate(specs)]
        else:
            pick = rng.choice(len(self.train), size=min(n, len(self.train)), replace=False)
            kind, jobs = "rollout", [(int(i), self.train[int(i)], 0) for i in pick]
        res, skipped, _ = self.actors.run(kind, 0, actor_bytes(self.model, getattr(self, "posture_head", None)), jobs)
        from pipeline.royale_env import ABILITY_CARDS
        names = list(ABILITY_CARDS) + ["other"]
        rows = {k: [] for k in ("feat", "q")}
        inp: dict = {}
        cards: Counter = Counter()
        for r in res:
            tj = r["traj"]
            if "ab_cand" not in tj or not len(tj["ab_cand"]):
                continue
            c = tj["ab_cand"]
            rows["feat"].append(tj["ab_feat"][c])
            rows["q"].append(tj["ab_q"][c])
            for k in (E.gen_row_keys(self.model) if "hand_card" in tj else ("tok", "mask", "sc", "past")):
                inp.setdefault(k, []).append(tj[k][c])
            cards.update(names[i] for i in tj["ab_feat"][c][:, 18:18 + len(names)].argmax(1))
        nl = int(sum(len(x) for x in rows["q"]))
        if not nl:
            self.ability_bc = {"n": 0, "matches": len(res), "skipped": len(skipped)}
            self.log(f"[rl] ability_head warm start: {len(res)} rule rollouts, NO pressable decision -- head kept at "
                     f"its init (P(press) {ABILITY_P0})")
            return
        B = to_device({k: np.concatenate(v) for k, v in inp.items()}, self.dev)
        with torch.no_grad():
            g = torch.cat([trunk_g(self.model, B, torch.arange(s, min(s + 512, nl), device=self.dev))
                           for s in range(0, nl, 512)])
        feat = torch.as_tensor(np.concatenate(rows["feat"]), device=self.dev)
        q = torch.as_tensor(np.concatenate(rows["q"]), device=self.dev)
        st = ability_bc_fit(self.ability_head, g, feat, q, int(cfg["ability_bc_steps"]), float(cfg["ability_bc_lr"]))
        self.ability_bc = {**st, "matches": len(res), "skipped": len(skipped), "by_card": dict(cards),
                           "wall_s": time.perf_counter() - t}
        self.log(f"[rl] ability_head warm start: {nl} labels from {len(res)} rule rollouts {dict(cards)}; rule q mean "
                 f"{st['q_mean']:.4f}; BCE {st['bce_before']:.4f} -> {st['bce_after']:.4f} (floor {st['bce_floor']:.4f}); "
                 f"head p mean {st['p_mean_before']:.4f} -> {st['p_mean_after']:.4f} ({self.ability_bc['wall_s']:.0f}s)")

    def _actor_bytes(self, model=None) -> bytes:
        """The weights message: the posture / ability heads ride along only with the learner's own model (the frozen
        ref's screen plays without a posture = the init's argmax, balanced, dtau 0, and presses by the rule)."""
        own = model is None or model is self.model
        ph, ah = getattr(self, "posture_head", None), getattr(self, "ability_head", None)
        return actor_bytes(model or self.model, ph if own else None, ah if own else None)

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
        AO.sync_pool(self.league, cfg)
        self.exploiters = exploiter_league(cfg)               # O2: absent / null = None (matchups unchanged)

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
        AO.sync_pool(self.league, self.cfg)
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
            # iw_press off: this env only resets (no hero_abilities, never presses); the live IW rule's guard must not
            # trip here (L74 overpress 10-18) -- loadability is independent of the press mode
            env = RoyalePoolEnv(decision_ticks=int(self.cfg["decide_every"]), iw_press="off")

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
        if adv_cfg(self.cfg)["shaping"] == "live_phi":
            from pipeline.live_phi import DEFAULT_CHECKPOINT, load
            ck = adv_cfg(self.cfg)["shaping_phi_ckpt"] or DEFAULT_CHECKPOINT
            try:
                return load(REPO / ck, self.dev, int(ick["args"].get("feature_version", 1)))
            except (OSError, ValueError, RuntimeError) as exc:
                raise SystemExit(f"live_phi checkpoint {ck}: {exc}") from exc
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

    def _load_gate_ref(self, ick: dict, key: str = "kl_ref_gate"):
        """F6 ``kl_ref_gate``: the frozen net the GATE's KL term is anchored to (card / cell keep the init ref). Refuses
        a non-generalist init, a missing file, or a checkpoint whose card_vocab / d_c / grid / row inputs differ from
        the init's. feature_version may differ while the row inputs are the same (fv5 vs fv6: fv6 only adds the
        projectile-target branch, which feeds the cell patches, never the gate), so the fv5 imitation model loads as is.
        ``key`` "kl_ref_card" (K1): the same checks for the CARD head's anchor."""
        ck = self.cfg[key]
        if not (isinstance(ck, str) and ck):
            raise SystemExit(f"{key} must be null or a checkpoint path, got {ck!r}")
        if not self.gen:
            raise SystemExit(f"{key} needs a generalist init")
        path = REPO / ck
        if not path.exists():
            raise SystemExit(f"{key} {ck} not found")
        gck = torch.load(path, map_location="cpu")
        sig = (lambda c: (bool(c.get("gen")), c.get("d_c"), list(c.get("card_vocab") or []),
                          str(c["args"].get("grid", "lattice"))))
        if sig(gck) != sig(ick):
            raise SystemExit(f"{key} {ck}: gen / d_c / card_vocab / grid differ from the init's")
        net = self._load_net(path)
        if E.gen_row_keys(net) != E.gen_row_keys(self.model):
            raise SystemExit(f"{key} {ck}: row inputs differ from the init's (feature_version "
                             f"{net.feature_version} vs {self.model.feature_version})")
        for p in net.parameters():
            p.requires_grad_(False)
        head = "gate" if key == "kl_ref_gate" else "card"
        self.log(f"[rl] {key}: KL_{head} anchored to {ck} (fv {net.feature_version}, sha256 "
                 f"{hashlib.sha256(path.read_bytes()).hexdigest()[:16]}); the other heads stay on the init")
        return net.eval()

    def _phi_values(self, Bn: dict) -> np.ndarray:
        """``value_rows`` of the frozen Phi net on the numpy batch ``collate`` built (its model-input keys only)."""
        if adv_cfg(self.cfg)["shaping"] == "live_phi":
            with torch.no_grad():
                values = []
                for start in range(0, len(Bn["sc"]), 2048):
                    b = {k: torch.as_tensor(Bn[k][start:start + 2048], device=self.dev)
                         for k in ("tok", "mask", "sc")}
                    values.append(self.phi_net(b).cpu())
                return torch.cat(values).numpy() if values else np.zeros(0, np.float32)
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
        res, skipped, st = self.actors.run("screen", self.update, self._actor_bytes(model), jobs)
        out = screen_score(res, self.base.get("init_screen"))
        out["skipped"] = len(skipped)
        return out

    # ---- checkpoints -----------------------------------------------------------------------------
    def _rl_state(self) -> dict:
        return {"update": int(self.update), "beta": float(self.beta), "optimizer": self.opt.state_dict(),
                **({"branch_optimizer": self.branch_opt.state_dict()}
                   if getattr(self, "branch_opt", None) is not None else {}),
                **({"ctx_head": self.ctx_head.state_dict(), "ctx_optimizer": self.ctx_opt.state_dict()}
                   if getattr(self, "ctx_head", None) is not None else {}),
                **({"posture_head": self.posture_head.state_dict(), "posture_optimizer": self.posture_opt.state_dict(),
                    "posture": self._posture_meta()} if getattr(self, "posture_head", None) is not None else {}),
                **({"ability_head": self.ability_head.state_dict(), "ability_optimizer": self.ability_opt.state_dict(),
                    "ability": self._ability_meta()} if getattr(self, "ability_head", None) is not None else {}),
                **({"beta_g": float(self.beta_g), "gate_lo_target": self.gate_lo_target}
                   if getattr(self, "beta_g", None) is not None else {}),
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
        from pipeline.model_v3 import grow_optimizer_state    # a run saved before vocab classes were appended: its
        self.opt.load_state_dict(rl["optimizer"])              # cls_emb Adam rows grow like the weights (no-op otherwise)
        grow_optimizer_state(self.opt, self.model)
        if getattr(self, "branch_opt", None) is not None and "branch_optimizer" in rl:
            self.branch_opt.load_state_dict(rl["branch_optimizer"])
            grow_optimizer_state(self.branch_opt, self.model)
        if getattr(self, "ctx_head", None) is not None:      # critic_ctx
            if "ctx_head" in rl:
                self.ctx_head.load_state_dict(rl["ctx_head"])
                self.ctx_opt.load_state_dict(rl["ctx_optimizer"])
            else:
                self.log("[rl] RESUME: the checkpoint has no ctx_head (run started without critic_ctx) -- it starts "
                         "at zero (V = the plain critic's)")
        if getattr(self, "posture_head", None) is not None:  # C1
            if "posture_head" in rl:
                self.posture_head.load_state_dict(rl["posture_head"])
                self.posture_opt.load_state_dict(rl["posture_optimizer"])
            else:
                self.log("[rl] RESUME: the checkpoint has no posture_head (run started without it) -- it starts at its "
                         "init (P(balanced) 0.8)")
        if getattr(self, "ability_head", None) is not None:  # B6
            if "ability_head" in rl:
                self.ability_head.load_state_dict(rl["ability_head"])
                self.ability_opt.load_state_dict(rl["ability_optimizer"])
                self.ability_bc = (rl.get("ability") or {}).get("bc")
            else:
                self.log(f"[rl] RESUME: the checkpoint has no ability_head (run started without it) -- it starts at its "
                         f"init (P(press) {ABILITY_P0}), no warm start")
        self.update, self.beta = int(rl["update"]), float(rl["beta"])
        if gate_lo_cfg(self.cfg) is not None:                 # F6': beta_g + the update-0 target (None = not measured)
            self.beta_g, self.gate_lo_target = float(rl.get("beta_g", self.cfg["beta0"])), rl.get("gate_lo_target")
            if "beta_g" not in rl:
                self.log("[rl] RESUME: the checkpoint has no beta_g (run started without kl_ref_gate_max_elixir)")
        self.rng.bit_generator.state = rl["rng"]
        self.visits = list(rl["visits"])
        self.base = dict(rl["baselines"])
        self.guards = Guards(self.cfg, rl["guards"])
        if getattr(self, "league", None) is not None:
            self.league = dict(rl.get("league") or {"snapshots": []})
            AO.sync_pool(self.league, self.cfg)
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
            specs = sample_matchups(self.rng, E_, u, self.league["snapshots"], self.cfg, self.census, self.census_p,
                                    **({"league_state": self.league} if self.cfg.get("league_pfsp") == "hard" else {}),
                                    exploiters=getattr(self, "exploiters", None))
            jobs = [(i, sp, g) for i, sp in enumerate(specs) for g in range(G)]
            res, skipped, st = self.actors.run("selfplay", u, self._actor_bytes(), jobs)
            if skipped:
                self.log(f"[rl] WARNING {len(skipped)} self-play rollout(s) skipped: {skipped[:3]}")
            if self.cfg.get("league_pfsp") == "hard":
                AO.update_ratings(self.league, res)
            if AO.mode(self.cfg.get("opp_style", "off")) == "on":
                for r in sorted(res, key=lambda r: (r["league"]["tag"], r["k"])):
                    self.log.json({"event": "opponent_style", "update": u, "tag": r["league"]["tag"],
                                   "k": r["k"], "opp": r["league"]["opp"]["id"], "style": r["opp_style"]})
            return res, {"picked": [], "actors": st, "skipped": len(skipped),
                         "league": [{"opp": sp["opp"]["id"], "learner_deck": sp["learner_deck_name"],
                                     "opp_deck": sp["opp_deck_name"], "side": sp["learner_side"],
                                     **({"opp_tower": sp["opp_tower"]} if "opp_tower" in sp else {}),
                                     **({"opp_level": sp["levels"]["opp"]["tower"]} if "levels" in sp else {})}
                                    for sp in specs]}
        pick = self.rng.choice(len(self.train), size=min(E_, len(self.train)), replace=False)
        for i in pick:
            self.visits[int(i)] += 1
        jobs = [(int(i), self.train[int(i)], g) for i in pick for g in range(G)]
        res, skipped, st = self.actors.run("rollout", u, self._actor_bytes(), jobs)
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
                                self.census_p,
                                **({"league_state": self.league} if self.cfg.get("league_pfsp") == "hard" else {}),
                                exploiters=getattr(self, "exploiters", None))
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
        mon = rollout_monitors(results, cfg["tau"], cfg.get("T_gate") or cfg["T"])   # p_b monitor = the gate actually sampled
        league = getattr(self, "league", None) is not None
        if league:
            mon["league"] = league_monitors(results)
        ac = adv_cfg(cfg)
        gae_on = ac["advantage"] == "gae"
        shp = ({"gamma": ac["gae_gamma"], "w_tower": ac["shaping_w_tower"], "w_crown": ac["shaping_w_crown"]}
               if ac["shaping"] == "tower_crown" else None)
        if ac["shaping"] in ("value_phi", "live_phi"):
            shp = {"mode": ac["shaping"], "gamma": ac["gae_gamma"], "w_value": ac["shaping_w_value"],
                   "window_ticks": int(round(ac["shaping_phi_window_s"] / E.TICK_S)), "phi_fn": self._phi_values}
        if ac["shaping"] in RS.STATE_PHI_MODES:                # step 3: Phi from the actors' state_record rows
            shp = {"mode": ac["shaping"], "gamma": ac["gae_gamma"], "params": {k: ac[k] for k in STATE_PHI_KEYS}}
        tick_unit = gae_on and ac["gae_gamma_unit"] == "tick"
        sv = spell_cfg(cfg)                                   # L74 combo (None = off: the call unchanged)
        ct = crown_cfg(cfg)                                   # L74 W6 (None = off: the call unchanged)
        Bn, bst = collate(results, float(cfg["adv_clip"]), advantage=ac["advantage"], shaping=shp,
                          **({"gamma_tick": ac["gae_gamma_tick"]} if tick_unit else {}),
                          **({"gae_terminal_gap": True} if ac["gae_terminal_gap"] else {}),
                          **({"spell": sv} if sv is not None else {}),
                          **({"crown": ct} if ct is not None else {}))
        gamma_row_mean = float(Bn["gamma_row"].mean()) if tick_unit and len(Bn["gamma_row"]) else None
        ab_acc = ([sum(dict(r.get("ability_presses", {}).get(r["side"], {})).values()) for r in results]
                  if getattr(self, "ability_head", None) is not None else None)   # B6: engine-accepted learner presses
        del results
        t1 = time.perf_counter()
        B = to_device(Bn, self.dev)
        gate_ref = getattr(self, "gate_ref", None)            # F6 kl_ref_gate (None = the init ref for all heads)
        glo = gate_lo_cfg(cfg)                                # F6' (None = off)
        card_ref = getattr(self, "card_ref", None)            # K1 kl_ref_card (None = the init ref)
        R = ref_terms(self.ref, B, cfg["tau"], cfg["T"], T_gate=cfg.get("T_gate"), gate_ref=gate_ref,
                      **({"gate_lo_max": glo["max_elixir"]} if glo else {}),
                      **({"card_ref": card_ref} if card_ref is not None else {}))
        if cfg.get("kl_heads") is not None:                   # K1: only these heads' KL enters the loss
            R["kl_heads"] = tuple(cfg["kl_heads"])
        if glo is not None:
            if getattr(self, "beta_g", None) is None:
                self.beta_g = float(cfg["beta0"])
            if getattr(self, "gate_lo_target", None) is None:
                if u != 0 or R["kl_lo_init"] is None:         # the target needs the init's own update-0 batch
                    raise SystemExit(f"kl_ref_gate_max_elixir: no update-0 target (update {u}, low-row KL "
                                     f"{R['kl_lo_init']}) -- a run started without the key, or no low gate rows")
                if R["kl_lo_init"] < GATE_LO_MIN_KL:          # the init already IS the anchor on these rows: a ~0
                    raise SystemExit(f"kl_ref_gate_max_elixir: update-0 KL_gate_imit_low {R['kl_lo_init']:.3g} < "
                                     f"{GATE_LO_MIN_KL} -- the init's low-elixir gate already matches "
                                     f"{cfg['kl_ref_gate']}; the anchor is meaningless (beta_g would run to beta_max)")
                self.gate_lo_target = glo["frac"] * R["kl_lo_init"]
            R["beta_g"] = beta_g_used = self.beta_g
            sel = B["gate_sampled"] & R["low"]
            imit_p_low = float(torch.sigmoid(R["x"][sel]).mean()) if sel.any() else None
        beta_used = self.beta
        vf = gst = None
        warm = gae_on and self.update < ac["critic_warmup_updates"]        # critic warm-up: policy frozen
        ctx_head = getattr(self, "ctx_head", None)            # critic_ctx (None = the plain critic)
        if gae_on:
            gst = gae_batch(self.model, B, cfg, ctx_head=ctx_head)
            vf = {"coef": ac["vf_coef"], "clip": ac["vf_clip"], "policy": not warm, "trunk_grad": ac["vf_trunk_grad"]}
            if ctx_head is not None:
                vf.update(ctx_head=ctx_head, ctx_opt=self.ctx_opt)
            gst["vf_trunk_share"] = None if warm else vf_grad_share(self.model, B, R, cfg, beta_used, vf)
        ph = getattr(self, "posture_head", None)              # C1 (None = no posture)
        post = psnap = None
        if ph is not None:
            if "posture_new" not in B or "ctx" not in B:
                raise SystemExit("posture_head: the rollout rows carry no posture / ctx (actor_cfg posture rows)")
            psnap = posture_snapshot(self.model, ph, B)
            post = {"head": ph, "opt": self.posture_opt, "ent_coef": float(cfg["posture_ent_coef"])}
        ah, abl = getattr(self, "ability_head", None), None    # B6 (None = the press rule)
        if ah is not None:
            if "ab_sampled" not in B:
                raise SystemExit("ability_head: the rollout rows carry no press decisions (actor_cfg ability rows)")
            abl = {"head": ah, "opt": self.ability_opt, "ent_coef": float(cfg["ability_ent_coef"])}
        upd = ppo_update(self.model, self.opt, B, R, cfg, beta_used, self.rng, vf=vf,
                         **({"posture": post} if post is not None else {}),
                         **({"ability": abl} if abl is not None else {}))
        t_upd = time.perf_counter() - t1
        first = upd["first"]
        if u == 0 and not upd["nonfinite"]:
            # kl_ref_gate: KL_gate is to another net, so > 0 by design; the ratio check still covers the gate's recompute
            # F6': KL_gate is the init ref's over the high rows only, so ~0 again; the low rows' imitation KL is not
            # K1 kl_ref_card: KL_card is to another net, so > 0 by design, the same way
            kl0 = (((first["kl_card"],) if card_ref is None else ()) + (first["kl_cell"],)
                   + ((first["kl_gate"],) if gate_ref is None or glo else ()))
            if card_ref is not None:
                self.log(f"[rl] kl_ref_card: update-0 KL_card to {cfg['kl_ref_card']} = {first['kl_card']:.4f} (first "
                         f"minibatch), {upd['kl_card']:.4f} (last-epoch mean); kl_target {cfg['kl_target']}, kl_heads "
                         f"{cfg.get('kl_heads')}")
            bad = first["ratio_maxdev"] >= ASSERT_RATIO or max(kl0) >= ASSERT_KL or (
                (first.get("post_ratio_maxdev") or 0.0) >= ASSERT_RATIO) or (     # C1: the posture's own ratio
                (first.get("ab_ratio_maxdev") or 0.0) >= ASSERT_RATIO)            # B6: the press's own ratio
            if glo is not None:
                self.log(f"[rl] kl_ref_gate_max_elixir {glo['max_elixir']}: update-0 KL_gate_imit_low to "
                         f"{cfg['kl_ref_gate']} = {R['kl_lo_init']:.4f} (full batch) -> beta_g target "
                         f"{self.gate_lo_target:.4f} (x {glo['frac']}); KL_gate_init_high {first['kl_gate']:.3g} "
                         f"(first minibatch); beta_g {beta_g_used:.3g}; ref gate entropy {R['ent']['gate']}")
            elif gate_ref is not None:
                self.log(f"[rl] kl_ref_gate: update-0 KL_gate to {cfg['kl_ref_gate']} = {first['kl_gate']:.4f} (first "
                         f"minibatch), {upd['kl_gate']:.4f} (last-epoch mean); kl_target {cfg['kl_target']}, leash "
                         f"{cfg.get('leash', 'cell')}; ref gate entropy {R['ent']['gate']}")
            assert not bad, (f"ON-POLICY CHECK FAILED at update 0 epoch 0 minibatch 0: max|ratio-1| "
                             f"{first['ratio_maxdev']:.3g} (< {ASSERT_RATIO}), KL gate/card/cell {first['kl_gate']:.3g}/"
                             f"{first['kl_card']:.3g}/{first['kl_cell']:.3g} (< {ASSERT_KL}), lp max diffs "
                             f"{first['lp_maxdiff']}, posture max|ratio-1| {first.get('post_ratio_maxdev')}, ability "
                             f"max|ratio-1| {first.get('ab_ratio_maxdev')} -- a bug "
                             f"between the stored forward and the recompute")
        reasons, crash = [], False
        if upd["nonfinite"]:
            reasons.append(f"non-finite {upd['nonfinite']}")
            crash = True
        elif not all(bool(torch.isfinite(p).all()) for p in self.model.parameters()) or (
                ctx_head is not None and not all(bool(torch.isfinite(p).all()) for p in ctx_head.parameters())) or (
                ph is not None and not all(bool(torch.isfinite(p).all()) for p in ph.parameters())) or (
                ah is not None and not all(bool(torch.isfinite(p).all()) for p in ah.parameters())):
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
        kl_leash, kl_driver = leash_kl(upd, leash, cfg.get("kl_heads"))
        if not crash:
            if not warm:                                        # warm-up: no KL step (the policy did not move)
                self.beta = adapt_beta(beta_used, kl_leash, float(cfg["kl_target"]), float(cfg["beta_min"]),
                                       float(cfg["beta_max"]))
                if glo is not None and upd["kl_gate_imit_low"] is not None:   # F6': its own leash, same rule
                    self.beta_g = adapt_beta(beta_g_used, upd["kl_gate_imit_low"], self.gate_lo_target,
                                             float(cfg["beta_min"]), float(cfg["beta_max"]))
            if glo is not None:                               # F6' runaway monitor (owner-visible; no stop rule)
                run = (not warm and beta_g_used >= float(cfg["beta_max"]) and upd["kl_gate_imit_low"] is not None
                       and upd["kl_gate_imit_low"] > 1.5 * self.gate_lo_target)
                self.beta_g_cap_streak = getattr(self, "beta_g_cap_streak", 0) + 1 if run else 0
                if self.beta_g_cap_streak >= 3:
                    self.log(f"[rl] WARNING u{u:04d}: beta_g at beta_max {cfg['beta_max']} for "
                             f"{self.beta_g_cap_streak} consecutive updates and KL_gate_imit_low "
                             f"{upd['kl_gate_imit_low']:.4f} still > 1.5 x target {self.gate_lo_target:.4f}")
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
                          "vf_trunk_grad": ac["vf_trunk_grad"], "shaping": ac["shaping"],
                          **({"critic_ctx": ac["critic_ctx"]} if ctx_head is not None else {})}
            if tick_unit:
                rec["gae"].update({"gamma_unit": "tick", "gamma_tick": ac["gae_gamma_tick"],
                                   "gamma_row_mean": gamma_row_mean})
        if ph is not None:                                     # C1 monitors (after the steps: kl_prev)
            rec["posture"] = {**posture_monitors(Bn, psnap, ph), "l_post": upd["l_post"],
                              "ent_posture_ep0": upd["ent_posture"], "trained": not warm,
                              "first_ratio_maxdev": first.get("post_ratio_maxdev") if first else None,
                              "every": cfg["posture_every"], "dtau": cfg["posture_dtau"],
                              "ent_coef": cfg["posture_ent_coef"]}
        if ah is not None:                                     # B6 monitors (the sampled decisions of this batch)
            sel = Bn["ab_sampled"].astype(bool)
            lp, pr = Bn["ab_lp"][sel], Bn["ab_press"][sel].astype(bool)
            p_press = np.where(pr, np.exp(lp), 1.0 - np.exp(lp))
            rec["ability"] = {"decisions": int(sel.sum()), "press_rate": float(pr.mean()) if sel.any() else None,
                              "p_mean": float(p_press.mean()) if sel.any() else None, "l_ab": upd["l_ab"],
                              "ent_ability_ep0": upd["ent_ability"], "trained": not warm,
                              "first_ratio_maxdev": first.get("ab_ratio_maxdev") if first else None,
                              "accepted_per_match": float(np.mean(ab_acc)) if ab_acc else None,
                              "ent_coef": cfg["ability_ent_coef"]}
        if glo is not None:                                    # F6' monitors (kl_gate above = KL_gate_init_high)
            bands = elixir_band_play(Bn["elixir"], Bn["gate_sampled"], Bn["played"])
            lo_sel = Bn["gate_sampled"] & (Bn["elixir"] < glo["max_elixir"])
            rec["gate_lo"] = {"max_elixir": glo["max_elixir"], "kl_gate_imit_low": upd["kl_gate_imit_low"],
                              "target": self.gate_lo_target, "beta_g_used": beta_g_used, "beta_g_next": self.beta_g,
                              "kl_gate_init_high": upd["kl_gate"], "kl_lo_init": R["kl_lo_init"],
                              "rows_low": int(lo_sel.sum()), "imit_p_play_low": imit_p_low,
                              "learner_play_rate_low": float(Bn["played"][lo_sel].mean()) if lo_sel.any() else None,
                              "play_rate_by_elixir": bands,
                              "beta_g_cap_streak": getattr(self, "beta_g_cap_streak", 0)}
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
                 + (" | posture " + "/".join(f(rec["posture"]["share"].get(p), "{:.2f}") for p in POSTURES)
                    + f" (d/b/p) choices {rec['posture']['share_choices']['n']} dtau {f(rec['posture']['mean_dtau'], '{:+.3f}')}"
                    f" H {f(rec['posture']['entropy'])} KL {f(rec['posture']['kl_prev'], '{:.5f}')}"
                    f" lpost {f(rec['posture']['l_post'], '{:+.4f}')}" if "posture" in rec else "")
                 + (f" | ability dec {rec['ability']['decisions']} press {f(rec['ability']['press_rate'])} p "
                    f"{f(rec['ability']['p_mean'])} acc/m {f(rec['ability']['accepted_per_match'], '{:.2f}')} H "
                    f"{f(rec['ability']['ent_ability_ep0'])} lab {f(rec['ability']['l_ab'], '{:+.4f}')}"
                    if "ability" in rec else "")
                 + (f" | crown r/m lead {f(bst['crown']['lead_reward_per_match'], '{:+.4f}')} redirect "
                    f"{f(bst['crown']['redirect_reward_per_match'], '{:+.4f}')} tornado "
                    f"{f(bst['crown']['tornado_reward_per_match'], '{:+.4f}')} lost {f(bst['crown'].get('lost_princess_per_match'), '{:.2f}')}"
                    f" gave {f(bst['crown'].get('gave_back_per_match'), '{:.2f}')} king_end "
                    f"{f(bst['crown'].get('king_end_per_match'), '{:.2f}')} tor>king {f(bst['crown'].get('tornado_to_king_per_match'), '{:.2f}')}"
                    if "crown" in bst else "")
                 + (f" | shape |F| {f(shs['mean_abs_F'], '{:.4f}')} (t {f(shs['mean_abs_tower'], '{:.4f}')} c "
                    f"{f(shs['mean_abs_crown'], '{:.4f}')}) |Phi| {f(shs['mean_abs_phi'], '{:.4f}')} dom "
                    f"{f(shs['shaping_dominates'])}" if shs and shs.get("mode") is None else "")
                 + (f" | {shs['mode']} |F| {f(shs['mean_abs_F'], '{:.4f}')} |Phi| {f(shs['mean_abs_phi'], '{:.4f}')} "
                    f"max {f(shs['max_abs_phi'], '{:.4f}')} dom {f(shs['shaping_dominates'])}"
                    if shs and shs.get("mode") in RS.STATE_PHI_MODES else "")
                 + (f" | vphi |F| {f(shs['mean_abs_F'], '{:.4f}')} |Phi| {f(shs['mean_abs_phi'], '{:.4f}')} share "
                    f"{f(gst['phi_share'])} dPhi std {f(shs['phi_step_std'], '{:.4f}')} (raw "
                    f"{f(shs['raw_step_std'], '{:.4f}')}) end-corr {f(shs['phi_end_corr'], '{:+.3f}')}"
                    if shs and shs.get("mode") in ("value_phi", "live_phi") else "")
                 + (f" | KL_gate_imit_low {f(upd['kl_gate_imit_low'], '{:.4f}')} (target {f(self.gate_lo_target, '{:.4f}')}) beta_g "
                    f"{beta_g_used:.3g}->{self.beta_g:.3g} play<{glo['max_elixir']:g} "
                    f"{f(rec['gate_lo']['learner_play_rate_low'])} (imit p {f(imit_p_low)}) bands "
                    + "/".join(f(v["play_rate"]) for v in rec["gate_lo"]["play_rate_by_elixir"].values())
                    if glo is not None else "")
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
        base["seed"] = self.cfg["seed"]                                       # rollout_jobs: per-(update, job) pipelining draw
        tg = self.cfg.get("T_gate")
        if tg is not None and not (isinstance(tg, (int, float)) and not isinstance(tg, bool) and 0 < tg <= 10):
            raise SystemExit(f"T_gate must be null or a number in (0, 10], got {tg!r}")
        if tg is not None and self.cfg.get("branch_gate"):
            raise SystemExit("T_gate with branch_gate is not supported (branch_terms parameterise the gate with T)")
        base["T_gate"] = tg
        base["learner_pipeline_frac"] = self.cfg.get("learner_pipeline_frac", 0)   # 0 = no learner pipelining (default)
        base["league_opp_policy"] = self.cfg.get("league_opp_policy", "sample")
        if AO.mode(self.cfg.get("opp_style", "off")) == "on":
            base.update({k: self.cfg.get(k, AO.DEFAULTS[k]) for k in AO.STYLE_KEYS})
        base["hero_abilities"] = self.cfg.get("hero_abilities", False)
        if type(base["hero_abilities"]) is not bool:
            raise SystemExit("hero_abilities must be a bool")
        base["ability_policy"] = self.cfg.get("ability_policy", "generic")
        base["ability_features"] = self.cfg.get("ability_features") or "base"   # L74: the env's head-input set
        if base["ability_policy"] not in ("generic", "v2"):
            raise SystemExit(f"ability_policy must be generic or v2, got {base['ability_policy']!r}")
        base["forms_mode"] = self.cfg.get("forms_mode", "base")
        if base["forms_mode"] not in ("base", "deck"):
            raise SystemExit(f"forms_mode must be base or deck, got {base['forms_mode']!r}")
        if self.cfg.get("shaping", "none") != "none":         # R2: actor_cfg -> record_phi (absent by default)
            base["shaping"] = self.cfg["shaping"]
        if self.cfg.get("gae_gamma_unit", "row") != "row":    # actor_cfg -> record_tick (absent by default)
            base["gae_gamma_unit"] = self.cfg["gae_gamma_unit"]
        if self.cfg.get("critic_ctx") is not None:            # actor_cfg -> record_ctx (absent by default)
            base["critic_ctx"] = self.cfg["critic_ctx"]
        if getattr(self, "posture_head", None) is not None:   # actor_cfg -> posture + record_ctx (absent by default)
            base["posture"] = self._posture_meta()
        if getattr(self, "ability_head", None) is not None:   # actor_cfg -> ability (absent by default)
            base["ability"] = {k: v for k, v in self._ability_meta().items() if k != "bc"}
        if self.cfg.get("kl_ref_gate_max_elixir") is not None:   # actor_cfg -> record_elixir (absent by default)
            base["kl_ref_gate_max_elixir"] = self.cfg["kl_ref_gate_max_elixir"]
        for k in OPP_TEMPO_KEYS:                              # L74 human tempo -> the opponent's cfg (absent by default)
            if self.cfg.get(k) is not None:
                base[k] = self.cfg[k]
        if spell_cfg(self.cfg) is not None:                   # L74 combo -> actor_cfg spell_track (absent by default)
            base["spell_value"] = True
        if crown_cfg(self.cfg) is not None:                   # L74 W6 -> actor_cfg crown_track (absent by default)
            base["crown_track"] = True
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
            + (f"; POSTURE every {cfg['posture_every']} dtau {cfg['posture_dtau']} ent {cfg['posture_ent_coef']}"
               if getattr(self, "posture_head", None) is not None else "")
            + (f"; ABILITY head (learner presses) ent {cfg['ability_ent_coef']} lr {cfg['ability_lr']} warm start "
               f"{cfg['ability_bc_matches']} rule rollouts x {cfg['ability_bc_steps']} steps"
               if getattr(self, "ability_head", None) is not None else "")
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
        if getattr(self, "ability_head", None) is not None:   # B6: imitate the press rule before the init screen / u0000
            self._ability_warm_start()
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
            # floats to 1e-6 relative: a save / load bug moves metrics far more; GPU reduction order alone moved cell_nll
            # 3e-8 (step d 10-18, CLIII fv6 init + ability head: 3.1361532936 vs 3.1361533864, every other metric equal)
            same = all(pa2[k] == pa[k] or (isinstance(pa[k], float) and math.isclose(pa2[k], pa[k], rel_tol=1e-6))
                       for k in pa)
            log(f"[rl] SMOKE u0000 round trip via {'eval_gen' if self.gen else 'engine_play'}.load_model: pro "
                f"agreement identical (floats to 1e-6) = {same}")
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
    if getattr(live, "posture_head", None) is not None:      # C1: the head + its Adam came back
        checks["posture_head"] = all(torch.equal(a, b) for a, b in zip(live.posture_head.state_dict().values(),
                                                                       L2.posture_head.state_dict().values()))
    if getattr(live, "ability_head", None) is not None:      # B6: the head + its Adam came back
        checks["ability_head"] = all(torch.equal(a, b) for a, b in zip(live.ability_head.state_dict().values(),
                                                                       L2.ability_head.state_dict().values()))
        a1, a2 = live.ability_opt.state_dict()["state"], L2.ability_opt.state_dict()["state"]
        checks["ability_opt"] = set(a1) == set(a2) and all(torch.equal(a1[k][m], a2[k][m].to(a1[k][m].device))
                                                           for k in a1 for m in ("exp_avg", "exp_avg_sq"))
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
