"""Per-phase wall clock of a self-play rollout: wraps the functions run_selfplay_batch spends its time in (inclusive
times; ``report`` also derives the exclusive split). Install once, before the rollout, in the process that runs it."""
from __future__ import annotations

import functools
import time
from collections import defaultdict

T: dict = defaultdict(float)
N: dict = defaultdict(int)


def _wrap(owner, name: str, label: str) -> None:
    f = getattr(owner, name)
    if getattr(f, "_timed", False):
        return

    @functools.wraps(f)
    def g(*a, **k):
        t = time.perf_counter()
        try:
            return f(*a, **k)
        finally:
            T[label] += time.perf_counter() - t
            N[label] += 1
    g._timed = True
    setattr(owner, name, g)


def install(E) -> None:
    from pipeline import adaptive_opponents as AO
    from pipeline import royale_env as RE
    _wrap(E.SelfPlayMatch, "__init__", "reset")              # env.reset + side setup
    _wrap(E.SelfPlayMatch, "due", "due")                     # engine advance + landing + raw()
    _wrap(RE.RoyaleSelfPlayEnv, "_advance_to", "engine_advance")
    _wrap(RE.RoyaleSelfPlayEnv, "raw", "engine_raw")
    _wrap(E.SelfPlaySide, "prepare", "obs_prepare")          # extrapolate + board + tokens
    _wrap(E.SelfPlaySide, "gen_row", "obs_gen_row")          # GenPolicy.row + v3 features + cues + memory
    _wrap(E.GenPolicy, "forward_batch", "forward")
    _wrap(E.GenPolicy, "cell_logits", "cell_logits")
    _wrap(E, "sample_decide_batch", "decide_sample")         # (includes its cell_logits)
    _wrap(AO, "styled_decisions", "decide_styled")           # (includes its per-row sample_decide_batch)
    _wrap(E.SelfPlaySide, "pre", "pre")
    _wrap(E.SelfPlaySide, "apply", "apply")                  # record + queue + land
    _wrap(E.SelfPlayMatch, "result", "result")


def report() -> dict:
    t = dict(T)
    ex = dict(t)
    ex["due_excl"] = t.get("due", 0) - t.get("engine_advance", 0) - t.get("engine_raw", 0)
    ex["decide_sample_excl_cell"] = t.get("decide_sample", 0)   # cell_logits split below (approx: cell inside both)
    return {"inclusive_s": {k: round(v, 3) for k, v in t.items()}, "calls": dict(N),
            "derived_s": {k: round(v, 3) for k, v in ex.items() if k.endswith("_excl") or k.endswith("_cell")}}
