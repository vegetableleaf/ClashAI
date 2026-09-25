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
  3. Rows that sampled nothing (no card allowed) are dropped; each remaining decision carries weight 1/(n_i M) so a
     match's decisions sum to 1/M (``match_weights``: the loss is averaged per match, then over the batch).
  4. Frozen-ref terms once per update (``ref_terms``); ``ppo_epochs`` x minibatches of ``minibatch`` decisions:
     log pi recomputed WITH gradients from the stored tok/mask/sc/past exactly as ``sample_decide_batch`` defined it
     (``policy_terms``), L = L_pg + beta (KL_gate + KL_card + KL_cell) on the tempered distributions
     (``minibatch_loss``). Model in eval() for rollout AND update (E1 3.3 dropout trap).
  5. Update 0, epoch 0, minibatch 0: max |ratio - 1| < 1e-4 and every KL < 1e-6 (plan values), else AssertionError
     (a bug, not noise).
  6. beta x2 / /2 around ``kl_target`` on KL_cell, clamp [beta_min, beta_max] (``adapt_beta``); kl_target never moves.
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
from pipeline.model_v3 import hand_mask_from_sc                                 # noqa: E402

RUN_ROOT = REPO / "scratchpad" / "gauntlet" / "L68" / "rl"
CKPT_ROOT = REPO / "icebow" / "data" / "bench" / "rl_royale"
PA_KEYS = ("cell_half_top1", "card_top1", "gate_bal_acc")
CARD_FILL = -1e9            # finite "not allowed" card logit: exp underflows to exactly 0 (same probs as the sampler's
                            # -inf) but 0 * (lp - ref) stays 0, so the KL has no NaN gradient at masked slots
ASSERT_RATIO, ASSERT_KL = 1e-4, 1e-6          # rl_plan.md "Learner" (measured L68: 7.8e-6 / ~1e-12)
SMOKE = {"E": 4, "G": 2, "n_actors": 1, "in_flight": 8, "max_updates": 2, "screen_entries": 8, "proagree_rows": 1000,
         "proagree_every": 1, "screen_every": 1, "save_every": 1}
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


def rl_obs_seed(tag: str, g: int, update: int) -> int:
    """rl_plan.md 'Behaviour policy': the live_view RNG of rollout g of an entry at an update."""
    return zlib.crc32(f"{tag}:obs:{g}:{update}".encode())


def match_weights(n_rows) -> list[np.ndarray]:
    """Per-row weights: match i's n_i rows each get 1/(n_i M), M = matches with rows -> every match sums to 1/M."""
    n = [int(k) for k in n_rows]
    M = sum(1 for k in n if k > 0)
    return [np.full(k, 1.0 / (k * M)) if k else np.zeros(0) for k in n]


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


def _py(x):
    """numpy scalars / tuples -> plain JSON types (the checkpoint must load with torch.load(weights_only=True))."""
    return json.loads(json.dumps(x, default=lambda o: o.item() if hasattr(o, "item") else str(o)))


# ------------------------------------------------------------------------------------------------------
# trajectories -> one batch
# ------------------------------------------------------------------------------------------------------
def collate(results: list[dict], adv_clip: float = 2.0) -> tuple[dict, dict]:
    """Rollout result records (each with ``traj`` = ``Match._traj_arrays``) -> numpy batch of the CONTRIBUTING rows
    (gate sampled or card/cell played) with per-row A, per-match weight w, match id, and the stored log-probs."""
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
    B = {k: cat(lambda j, k=k: results[j]["traj"][k][keep[j]]) for k in TRAJ_KEYS + (E.GEN_IDENT_KEYS if gen else ())}
    for k in ("lp_gate", "lp_card", "lp_cell"):
        B[k] = cat(lambda j, k=k: results[j]["traj"][k][keep[j]])
    B["lp_old"] = B["lp_gate"] + B["lp_card"] + B["lp_cell"]
    B["A"] = cat(lambda j: np.full(n_rows[j], A[j]))
    B["w"] = cat(lambda j: W[j])
    B["match"] = cat(lambda j: np.full(n_rows[j], j))
    st = {"matches": len(results), "groups": len(groups), "mixed_groups": mixed,
          "mixed_group_share": mixed / max(len(groups), 1), "mean_abs_A": float(np.abs(A).mean()) if len(A) else 0.0,
          "rows": int(len(B["A"])), "rows_played": int(B["played"].sum()), "rows_gate": int(B["gate_sampled"].sum()),
          "decisions": int(sum(len(r["traj"]["played"]) for r in results))}
    return B, st


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


def policy_terms(model, B: dict, idx, tau: float, T: float) -> dict:
    """Recompute the behaviour log-probs of rows ``idx`` exactly as ``e1_eval.sample_decide_batch`` defined them:
    gate ``sigmoid((z - logit(tau)) / T)`` on gate-sampled rows; card softmax over ``allowed`` of the heads'
    hand-masked logits / T and cell softmax over 2,304 for the recorded slot / T on played rows; float64 after the
    float32 forward, as the sampler. Gradients flow unless the caller is in no_grad.
    Generalist rows (``hand_card`` in B, a GenModel ``model``): the forward is ``e1_eval.GenPolicy.heads_t`` -- the
    sampler's own function -- so card = the hand-position logits on their deck slots (softmax over allowed slots ==
    over allowed hand positions) and cell = ``cell_logits_gen`` for the slot's card identity + form."""
    if "hand_card" in B:
        pol = E.GenPolicy(model, ())
        enc, heads = pol.heads_t({k: B[k][idx] for k in E.GEN_ROW_KEYS})
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
    return {"x": x, "card_lp": card_lp, "cell_lp": cell_lp, "lp_gate": lp_gate, "lp_card": lp_card, "lp_cell": lp_cell}


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
                   n_total: int) -> tuple[torch.Tensor, dict]:
    """PPO-clip on the joint log pi = lp_gate + g (lp_card + lp_cell) (E1 3.3) with per-match weights, scaled by
    n_total / |mb| so each minibatch estimates the full-batch loss; + beta (mean KL_gate + mean KL_card + mean KL_cell)."""
    t = policy_terms(model, B, idx, tau, T)
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
    with torch.no_grad():
        dev_ = (ratio - 1).abs()
        st = {"l_pg": float(l_pg), "kl_gate": float(kl_g), "kl_card": float(kl_c), "kl_cell": float(kl_x),
              "ratio_maxdev": float(dev_.max()), "ratio_mean": float(ratio.mean()),
              "clip_frac": float((dev_ > clip).double().mean()), "n": len(idx),
              "lp_maxdiff": {k: float((t[k] - B[k][idx]).abs().max()) for k in ("lp_gate", "lp_card", "lp_cell")},
              "ent_gate": float(bern_ent(t["x"][gs]).mean()) if gs.any() else None,
              "ent_card": float(cat_ent(t["card_lp"][pl]).mean()) if pl.any() else None,
              "ent_cell": float(cat_ent(t["cell_lp"]).mean()) if pl.any() else None}
    return loss, st


def ppo_update(model, opt, B: dict, R: dict, cfg: dict, beta: float, rng: np.random.Generator) -> dict:
    """``ppo_epochs`` passes over the batch in random minibatches. Returns the monitors; ``first`` = epoch 0 minibatch 0
    (the on-policy check), ``nonfinite`` set (and the step skipped) on a non-finite loss or gradient norm."""
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
                "ratio_mean": avg(ratios), "clip_frac": avg(clips), "grad_norm_mean": avg(gnorms)}

    for ep in range(int(cfg["ppo_epochs"])):
        perm = torch.from_numpy(rng.permutation(N)).to(dev)
        for s in range(0, N, mb):
            idx = perm[s:s + mb]
            loss, st = minibatch_loss(model, B, R, idx, tau=cfg["tau"], T=cfg["T"], clip=cfg["clip"], beta=beta,
                                      n_total=N)
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
    """One actor process: a model copy on ``actor_device`` + RoyaleSim envs; runs ``e1_eval.run_batch`` per job list.
    Messages in: (kind, update, state_dict bytes, jobs [(entry_index, entry, g)]) or None to exit.
    Out: ("ready", aid, gen, pid) | ("done", aid, gen, results, skipped, stats) | ("error", aid, gen, traceback)."""
    import multiprocessing as mp
    send = actor_sender(out_q)
    torch.set_num_threads(int(base["actor_threads"]))
    try:
        from pipeline.model_v3 import S1Model
        from pipeline.obs_contract import load_deck
        from pipeline.royale_env import RoyalePoolEnv, UnsupportedDeck
        dev = base["actor_device"]
        deck = load_deck("icebow")
        g = base.get("gen")
        if g:                                                 # generalist: GenModel weights behind GenPolicy
            from pipeline.model_gen import GenModel
            net = GenModel(d=int(base["d"]), layers=int(base["layers"]), d_c=int(g["d_c"]),
                           n_cards=len(g["card_vocab"])).to(dev).eval()
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
                if kind == "rollout":
                    line["rollout_index"], line["update"] = int(line["k"]), int(update)
                results.append(line)

            it = rollout_jobs(jobs, update) if kind == "rollout" else jobs     # screen: eval obs seed of (tag, k)
            E.run_batch(lambda: RoyalePoolEnv(decision_ticks=int(base["decide_every"])), model, deck, it, cfg,
                        max(1, min(int(base["in_flight"]), len(jobs))), on_result=on_result,
                        on_skip=lambda e, exc: skipped.append({"tag": e["tag"], "why": str(exc)}),
                        skip=(UnsupportedDeck,))
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
# config, paths, logging
# ------------------------------------------------------------------------------------------------------
def load_config(path: Path, overrides: list[str], smoke: bool) -> dict:
    import yaml
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if smoke:
        cfg.update(SMOKE)
    for ov in overrides:
        if "=" not in ov:
            raise SystemExit(f"bad override {ov!r} (want key=value)")
        k, v = ov.split("=", 1)
        if k not in cfg:
            raise SystemExit(f"unknown config key {k!r}; keys: {sorted(cfg)}")
        cfg[k] = yaml.safe_load(v)
    return cfg


def config_sha(cfg: dict) -> str:
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
        from pipeline import engine_play as ep
        self.cfg, self.run, self.run_dir, self.ck_dir, self.log = cfg, run, run_dir, ck_dir, log
        self.dev = torch.device(cfg["learner_device"])
        self.init_path = REPO / cfg["init"]
        condition_cfg(cfg)                                    # validate the condition keys before anything runs
        ick = torch.load(self.init_path, map_location="cpu")
        self.gen = {"d_c": int(ick["d_c"]), "card_vocab": list(ick["card_vocab"])} if ick.get("gen") else None
        if self.gen:                                          # generalist init: the learner trains the GenModel itself
            self.model = self._load_net(self.init_path)
            self.minfo = {"gen": True, "grid": str(ick["args"].get("grid", "lattice"))}   # = e1_eval.load_policy's
        else:
            self.model, self.minfo = ep.load_model(self.init_path, str(self.dev))
        self.init_meta = {"args": dict(ick["args"]), "deck": ick["deck"], "epoch": ick["epoch"], "n_params": ick["n_params"]}
        self.grid = self.minfo["grid"]
        self.ref = copy.deepcopy(self.model).eval()
        for p in self.ref.parameters():
            p.requires_grad_(False)
        self.model.eval()                                     # eval() for rollout AND update (E1 3.3 dropout trap)
        self.opt = torch.optim.Adam(self.model.parameters(), lr=float(cfg["lr"]))
        self.beta, self.update = float(cfg["beta0"]), 0
        self.rng = np.random.default_rng(int(cfg["seed"]))
        self.train, self.heldout = self._entries()
        self.visits = [0] * len(self.train)
        self.base: dict = {}                                  # init_proagree, init_screen ("tag:k" -> screen_record)
        self.guards = Guards(cfg)
        self.latest_pa: Optional[dict] = None
        self._rows = None
        self.actors: Optional[ActorPool] = None
        self.resumed = resume
        if resume:
            self._restore(self.ck_dir / f"{run}_latest.pt")

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
                "rng": _py(self.rng.bit_generator.state), "visits": list(map(int, self.visits)),
                "config": _py(self.cfg), "config_sha256": config_sha(self.cfg), "run": self.run,
                "init": str(self.cfg["init"]), "pool_sha256": self.pool_sha,
                "baselines": _py({**self.base, "init_screen": self.base.get("init_screen")}),
                "guards": _py(self.guards.s)}

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
        self.model.load_state_dict(ck["model"])
        self.model.eval()
        self.opt.load_state_dict(rl["optimizer"])
        self.update, self.beta = int(rl["update"]), float(rl["beta"])
        self.rng.bit_generator.state = rl["rng"]
        self.visits = list(rl["visits"])
        self.base = dict(rl["baselines"])
        self.guards = Guards(self.cfg, rl["guards"])
        if rl["config_sha256"] != config_sha(self.cfg):
            diff = {k: (rl["config"].get(k), v) for k, v in self.cfg.items() if rl["config"].get(k) != v}
            self.log(f"[rl] RESUME with a changed config (old, new): {diff}")
        if len(self.visits) != len(self.train):
            raise SystemExit("REFUSING resume: the train entry list changed length")

    # ---- one update ------------------------------------------------------------------------------
    def rollout(self, u: int) -> tuple[list[dict], dict]:
        E_, G = int(self.cfg["E"]), int(self.cfg["G"])
        pick = self.rng.choice(len(self.train), size=min(E_, len(self.train)), replace=False)
        for i in pick:
            self.visits[int(i)] += 1
        jobs = [(int(i), self.train[int(i)], g) for i in pick for g in range(G)]
        res, skipped, st = self.actors.run("rollout", u, state_bytes(self.model), jobs)
        if skipped:
            self.log(f"[rl] WARNING {len(skipped)} rollout(s) skipped as unsupported: {skipped[:3]}")
        return res, {"picked": [int(i) for i in pick], "actors": st, "skipped": len(skipped)}

    def one_update(self, u: int) -> tuple[dict, list[str], bool]:
        cfg, t0 = self.cfg, time.perf_counter()
        if self.dev.type == "cuda":
            torch.cuda.reset_peak_memory_stats(self.dev)
        results, rinfo = self.rollout(u)
        t_roll = time.perf_counter() - t0
        mon = rollout_monitors(results, cfg["tau"], cfg["T"])
        Bn, bst = collate(results, float(cfg["adv_clip"]))
        del results
        t1 = time.perf_counter()
        B = to_device(Bn, self.dev)
        R = ref_terms(self.ref, B, cfg["tau"], cfg["T"])
        beta_used = self.beta
        upd = ppo_update(self.model, self.opt, B, R, cfg, beta_used, self.rng)
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
        if not crash:
            self.beta = adapt_beta(beta_used, upd["kl_cell"] or 0.0, float(cfg["kl_target"]), float(cfg["beta_min"]),
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
               "beta_next": self.beta, "kl_target": cfg["kl_target"], "l_pg": upd["l_pg"],
               "entropy": upd["ent"], "entropy_init": R["ent"], "clip_frac": upd["clip_frac"],
               "ratio_mean": upd["ratio_mean"], "grad_norm_mean": upd["grad_norm_mean"],
               "first_minibatch": {k: first[k] for k in ("ratio_maxdev", "kl_gate", "kl_card", "kl_cell", "lp_maxdiff")},
               "picked": rinfo["picked"], "skipped": rinfo["skipped"], "visits_distinct": sum(v > 0 for v in self.visits),
               "visits_max": max(self.visits), "guards": copy.deepcopy(self.guards.s),
               "wall_rollout_s": t_roll, "wall_update_s": t_upd,
               "actor_s_per_match": {a: s["wall_s"] / max(s["matches"], 1) for a, s in rinfo["actors"].items()},
               "actor_gpu_peak_mb": {a: s["gpu_peak_mb"] for a, s in rinfo["actors"].items()}}
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
            numbered = self.save(self.latest_pa if "proagree" in rec else None,
                                 self.update % int(cfg["save_every"]) == 0)
            rec["ckpt"] = str(numbered) if numbered else None
        rec["wall_save_s"] = time.perf_counter() - t
        rec["wall_total_s"] = time.perf_counter() - t0
        rec["learner_gpu_peak_mb"] = torch.cuda.max_memory_allocated(self.dev) / 2**20 if self.dev.type == "cuda" else None
        rec["stop"] = reasons
        self.log.json(rec)
        f = (lambda v, s="{:.3f}": "-" if v is None else s.format(v))
        self.log(f"[rl] u{u:04d} W/L/D {mon['W']}/{mon['L']}/{mon['D']} ppm {f(mon['plays_per_min'], '{:.2f}')} "
                 f"pgate {f(mon['p_gate_mean'])} KL g/c/x {f(upd['kl_gate'], '{:.4f}')}/{f(upd['kl_card'], '{:.4f}')}/"
                 f"{f(upd['kl_cell'], '{:.4f}')} beta {beta_used:.3g}->{self.beta:.3g} clip {f(upd['clip_frac'])} "
                 f"mixed {bst['mixed_groups']}/{bst['groups']} rows {bst['rows']} "
                 f"wall roll {t_roll:.0f}s upd {t_upd:.0f}s"
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
        return base

    def start_actors(self) -> None:
        base = self.actor_base()
        self.actors = ActorPool(base, int(self.cfg["n_actors"]), self.log, self.cfg["actor_timeout_s"],
                                pid_file=self.run_dir / "actors.pid")
        (self.run_dir / "pid.json").write_text(json.dumps({"learner": os.getpid(), "actors": self.actors.pids}),
                                               encoding="utf-8")

    def startup(self, smoke: bool) -> None:
        """Fresh run: init pro agreement, init held-out screen (both cached in the run dir), u0000 before any update."""
        cfg, log = self.cfg, self.log
        log(f"[rl] run {self.run}: train {len(self.train)} loadable, held-out {len(self.heldout)} loadable "
            f"(screen uses {len(self.screen_entries())}); init {cfg['init']} ({'GENERALIST' if self.gen else 'S1'}) "
            f"grid {self.grid}; conditions (rollouts + screens): "
            + " ".join(f"{k}={cfg.get(k)}" for k in COND_KEYS))
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
              "guards": json.dumps(_py(L2.guards.s), sort_keys=True) == json.dumps(_py(live.guards.s), sort_keys=True)}
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
    cfg = load_config(a.config, a.overrides, a.smoke)
    run_dir, ck_dir = RUN_ROOT / a.run, CKPT_ROOT / a.run
    if a.resume:
        if not (ck_dir / f"{a.run}_latest.pt").exists():
            raise SystemExit(f"--resume needs {ck_dir / (a.run + '_latest.pt')}")
        if (run_dir / "STOP").exists():
            raise SystemExit(f"REFUSING resume: {run_dir / 'STOP'} exists (delete it first)")
    else:
        for d in (run_dir, ck_dir):
            if d.exists() and any(d.iterdir()):
                raise SystemExit(f"REFUSING: {d} exists and is not empty (new --run name, or --resume)")
    run_dir.mkdir(parents=True, exist_ok=True)
    ck_dir.mkdir(parents=True, exist_ok=True)
    import yaml
    (run_dir / (f"config_resume_{int(time.time())}.yaml" if a.resume else "config.yaml")).write_text(
        yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    log = Log(run_dir)
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
        (run_dir / "pid.json").unlink(missing_ok=True)
        (run_dir / "actors.pid").unlink(missing_ok=True)       # left in place only if the learner is killed hard


if __name__ == "__main__":
    raise SystemExit(main())
