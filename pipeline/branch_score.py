"""Branch scoring for counterfactual PLAY-vs-HOLD branching (opt3, ticket T2; contract scratchpad/gauntlet/L73/opt3/
INTERFACE.md section T2). Scores are always from OUR side (the learner), and NEVER charge spent elixir: S0's scorer did
(spent * 0.061 tower fractions), chose WAIT on 78% of decisions and did not win more.

    score(end_snapshot, outcome, *, kind, phi=None) -> float
        outcome not None (the match ended: +1 win, -1 loss, 0 draw) -> that outcome, whatever the kind.
        outcome None (the horizon was reached first):
          "outcome" -> ValueError (no outcome to score; run that branch to the end of the match)
          "phi"     -> the FROZEN gen model's value head at the horizon state: V = P(win) - P(loss) in [-1, 1]
                       (rl_royale.value_scalar; 7 classes = clip(crowns mine - theirs, -3, 3) + 3, train_s1.Rows),
                       on our side's public-input gen row (SelfPlaySide.prepare + gen_row: the policy's own row path)
          "towers"  -> crown-tower HP fraction, ours - theirs, in [-1, 1] (reference only)
    branch_label(result, kind, *, phi=None) -> (delta, weight)
        delta  = mean over the k CRN pairs of score(PLAY_j) - score(HOLD_j)   (> 0: PLAY better)
        weight = delta^2 / (delta^2 + se^2), se = the paired differences' standard error (ddof 1): the share of the
                 delta's spread that is signal, so a label whose sign is mostly seed noise counts little. k == 1 or
                 se == 0 -> 1.0; delta == 0 -> 0.0.
    snapshot(fork, phi=None) -> dict   the end/horizon snapshot of a forked SelfPlayMatch: tick, towers, phi.

``end_snapshot`` is one of: a snapshot dict ({"towers": float, "phi": float|None, ...}, ``snapshot``'s); a
branching.BranchRunner end snapshot (dict with "state", "side" and a PREPARED "learner" side, env detached: towers from
the state, phi from learner.gen_row(phi) -- fv >= 4 rows do not read the env); or a SelfPlayMatch (via ``snapshot``). The phi model: ``load_phi(ckpt)`` (default DEFAULT_PHI_CKPT, gen_v32_s0, fv5), cached per (path, device).
"""
from __future__ import annotations

import functools
from pathlib import Path

import numpy as np

KINDS = ("outcome", "phi", "towers")
DEFAULT_PHI_CKPT = str(Path(__file__).resolve().parents[1] / "icebow/data/pipeline/gen_v32_s0/gen_s0.pt")


@functools.lru_cache(maxsize=4)
def load_phi(ckpt: str = DEFAULT_PHI_CKPT, device: str = "cpu"):
    """The frozen phi model as an e1_eval.GenPolicy (eval mode). Refuses a value head that is not the 7-class one."""
    from pipeline import e1_eval as E
    pol, info = E.load_policy(ckpt, device)
    if not info.get("gen") or pol.model.value_head.out_features != 7:
        raise ValueError(f"{ckpt}: not a gen model with the 7-class crown-difference value head")
    return pol


def phi_values(phi, rows) -> np.ndarray:
    """V = P(win) - P(loss) for gen rows built for ``phi`` (SelfPlaySide.gen_row(phi)), one batched forward."""
    import torch
    from pipeline import e1_eval as E
    from pipeline.rl_royale import value_scalar
    if not rows:
        return np.zeros(0)
    dev = next(phi.model.parameters()).device
    with torch.no_grad():
        b = {k: torch.from_numpy(np.ascontiguousarray(np.stack([r[k] for r in rows]))).to(dev)
             for k in E.gen_row_keys(phi.model)}
        return value_scalar(phi.model.value_head(phi.model.encode_gen(b)["g"])).cpu().numpy()


def tower_frac_diff(st, us: int) -> float:
    """(our standing crown-tower HP - theirs) / one side's full crown-tower HP (2 princess + king at the engine's
    tower level), in [-1, 1]."""
    from clashrl import levels
    from pipeline.search_s0 import engine_tower_level, tower_hp
    lv = engine_tower_level(st)
    full = 2.0 * levels.PRINCESS_HP[lv] + levels.KING_HP[lv]
    return (tower_hp(st, us) - tower_hp(st, 1 - us)) / full


def snapshot(f, phi=None) -> dict:
    """Snapshot of forked SelfPlayMatch ``f`` for its learner: tick, towers, phi (None without a phi model). With
    ``phi`` our side is re-observed at the current tick (prepare + gen_row): call it only once the fork is finished,
    since prepare advances the side's observation state."""
    s, L = f.learner, f.learner.side
    out = {"tick": int(f.env.tick), "towers": tower_frac_diff(f.env.core.state(), L), "phi": None}
    if phi is not None:
        s.state = f.env.raw()
        s.prepare()
        out["phi"] = float(phi_values(phi, [s.gen_row(phi)])[0])
    return out


def score(end_snapshot, outcome, *, kind: str, phi=None) -> float:
    """See the module docstring. ``phi`` (GenPolicy) is only used to build a missing phi value from a SelfPlayMatch."""
    if kind not in KINDS:
        raise ValueError(f"kind {kind!r} not in {KINDS}")
    if outcome is not None:
        if outcome not in (-1, 0, 1):
            raise ValueError(f"outcome {outcome!r} not in (-1, 0, 1)")
        return float(outcome)
    if kind == "outcome":
        raise ValueError("kind 'outcome' needs a finished match (outcome None = horizon reached)")
    snap = end_snapshot
    if not isinstance(snap, dict):
        if not hasattr(snap, "learner"):
            raise TypeError(f"end_snapshot must be a snapshot dict or a SelfPlayMatch, got {type(snap).__name__}")
        snap = snapshot(snap, (phi or load_phi()) if kind == "phi" else None)
    v = snap.get(kind)
    if v is None and kind == "towers" and "state" in snap:          # branching.BranchRunner's end snapshot
        v = tower_frac_diff(snap["state"], int(snap["side"]))
    if v is None and kind == "phi" and snap.get("learner") is not None:   # its PREPARED learner side (env detached)
        phi = phi or load_phi()
        v = float(phi_values(phi, [snap["learner"].gen_row(phi)])[0])
    if v is None:
        raise ValueError(f"snapshot has no {kind!r} value")
    return float(v)


def label_from_scores(play, hold) -> tuple[float, float]:
    """(delta, weight) from the k paired scores (PLAY_j, HOLD_j)."""
    d = np.asarray(play, np.float64) - np.asarray(hold, np.float64)
    if d.ndim != 1 or len(d) == 0:
        raise ValueError(f"need k >= 1 paired scores, got shape {d.shape}")
    delta = float(d.mean())
    if delta == 0.0:
        return 0.0, 0.0
    if len(d) < 2:
        return delta, 1.0
    se2 = float(d.var(ddof=1)) / len(d)
    return delta, (1.0 if se2 == 0.0 else delta * delta / (delta * delta + se2))


def branch_label(result, kind: str, *, phi=None) -> tuple[float, float]:
    """``result``: a BranchResult (play_end, hold_end, play_outcome, hold_outcome; pair j = continuation j of both
    branches under common random numbers). -> (delta, weight)."""
    pe, he, po, ho = result.play_end, result.hold_end, result.play_outcome, result.hold_outcome
    if not (len(pe) == len(he) == len(po) == len(ho)):
        raise ValueError(f"unpaired branches: {len(pe)}/{len(he)} ends, {len(po)}/{len(ho)} outcomes")
    sc = lambda e, o: score(e, o, kind=kind, phi=phi)                           # noqa: E731
    return label_from_scores([sc(e, o) for e, o in zip(pe, po)], [sc(e, o) for e, o in zip(he, ho)])


def outcome_value(word: str) -> int:
    """royale_env.outcome's word -> +1 / -1 / 0."""
    return {"win": 1, "loss": -1, "draw": 0}[word]

