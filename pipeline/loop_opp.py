"""Fast-loop league opponents (LOOP-OPP, plan1026 pilot; LOOP_SPEC.md interface d): what a producer that holds no
e1_eval Match needs to play an opponent seat exactly as rl_royale's actor path does (actor_main -> run_selfplay_batch ->
SelfPlayMatch / SelfPlaySide -> adaptive_opponents.styled_decisions | e1_eval.sample_decide_batch):

  * ``load_pool``: the frozen pool manifest (pilot/opp/POOL.json), every file sha256-checked before it loads.
  * ``opp_match_cfg``: the opponent side's match cfg (actor_main's ocfg0 + own_opp_cfg + live_opp_cfg, the job's
    rollout_index / update, SelfPlayMatch's per-match style_config, SelfPlaySide's feature_version).
  * ``behave_rng``: that side's behaviour RNG (Match._seed on the tag "<tag>:opp").
  * ``deck_ids``: the per-slot card ids the style's spell delay reads (``deck.card_ids`` of selfplay_deck: a non-icebow
    deck has placeholder ids, so only an icebow-card-set deck ever gets a spell delay -- production as it is).
  * ``after_decision``: SelfPlaySide.apply's schedule (landing tick of a play, next decision tick).
  * ``decide``: the decode itself, by calling production's own functions on stand-in sides; the only device work,
    ``cell_logits``, goes to ``cell_fn(rows, slots)`` (the policy server's cell call).
Nothing here reads hidden opponent state. The test is pilot/opp/oppcheck (production actors, same matches)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Optional

import numpy as np

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "scratchpad/gauntlet/L74/plan1026/pilot/opp/POOL.json"
# the opponent cfg keys a decision, its RNG or its schedule reads (the test compares exactly these with production's)
DECISION_KEYS = ("policy", "T", "T_gate", "tau", "tau_phase", "decide_every", "action_delay_ticks", "extrapolate_ticks",
                 "opp_elixir", "noise", "obs", "afford_mask", "stall_elixir", "stall_seconds", "grid", "record",
                 "rollout_index", "update", "feature_version", "_opp_style", "posture", "ability", "afford_ticks",
                 "pipeline_decisions", "follow_ups", "tap_loss", "tap_slow", "own_effects", "predict_drops",
                 "sample_heads")
UNSUPPORTED = ("posture", "ability", "tau_phase", "afford_ticks", "pipeline_decisions", "follow_ups", "tap_loss",
               "tap_slow", "sample_heads")


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_pool(manifest=MANIFEST, device: str = "cpu", check: bool = True, root=REPO) -> dict:
    """{opponent id: (e1_eval.GenPolicy, grid, manifest entry)}; every manifest file's sha256 is checked first
    (``check``), and a mismatch raises before anything loads."""
    from pipeline import e1_eval as E
    m = json.loads(Path(manifest).read_text(encoding="utf-8"))
    if check:
        bad = [f["path"] for f in m["files"] if sha256(Path(root) / f["path"]) != f["sha256"]]
        if bad:
            raise ValueError(f"pool files differ from the manifest's sha256: {bad}")
    out = {}
    for o in m["opponents"]:
        pol, mi = E.load_policy(Path(root) / o["ckpt"], device)
        out[o["id"]] = (pol, str(mi.get("grid", "floor")), o)
    return out


def opp_match_cfg(cfg: dict, opp: dict, grid: str, seed: int, k: int, update: int, feature_version: int) -> dict:
    """The cfg rl_royale gives the league opponent ``opp`` (a sample_matchups spec["opp"]) of match (seed, k) in
    ``update``, from the run's config ``cfg`` (rl_royale.load_config's dict). ``grid`` = the opponent checkpoint's
    (e1_eval.load_policy's minfo grid, default floor); ``feature_version`` = its model's. Production's cfg also
    carries the learner's record / track keys (inert for an unrecorded side); the test compares DECISION_KEYS.
    Like the actor: league_opp_T never reaches it (actor_base drops it, so opp_T = the run's T)."""
    from pipeline import adaptive_opponents as AO
    from pipeline import rl_royale as R
    from pipeline.decision_options import DecisionOptions, options_from_config, sample_rules
    base = {"T": cfg["T"], **{x: cfg[x] for x in R.OPP_TEMPO_KEYS if cfg.get(x) is not None}}
    if cfg.get("league_opp_live") is not None:
        base["league_opp_live"] = dict(cfg["league_opp_live"])
    oc = {"policy": cfg.get("league_opp_policy", "sample"), "tau": float(cfg["tau"]), "afford_mask": bool(cfg["afford_mask"]),
          "stall_elixir": cfg["stall_elixir"], "stall_seconds": float(cfg["stall_seconds"]), "obs": cfg["obs"],
          "decide_every": int(cfg["decide_every"]), "record": False, "T_gate": None, "T": R.opp_T(base), "grid": grid,
          **R.condition_cfg(cfg)}
    if AO.mode(cfg.get("opp_style", "off")) == "on":
        oc.update({x: cfg.get(x, AO.DEFAULTS[x]) for x in AO.STYLE_KEYS})
    oc = R.live_opp_cfg(R.own_opp_cfg(oc, opp, base), opp, base)
    oc.update(rollout_index=int(k), update=int(update))
    oc = AO.style_config(oc, int(seed), int(k))
    if feature_version >= 3:
        oc["feature_version"] = int(feature_version)
    bad = [x for x in UNSUPPORTED if oc.get(x) is not None]
    if bad or oc["policy"] != "sample" or sample_rules(options_from_config(oc)) != DecisionOptions():
        raise NotImplementedError(f"loop_opp decodes sampled opponents without {UNSUPPORTED} or SAMPLE_RULES (their "
                                  f"per-row context is LOOP-CTX's); got policy {oc['policy']!r}, keys {bad}")
    return oc


def behave_rng(tag: str, k: int, update: int) -> np.random.Generator:
    """The opponent side's behaviour RNG (its tag is ``<tag>:opp``; run_selfplay_batch passes it the job's
    rollout_index and update): one per match, consumed only by its decisions, in decision order."""
    from pipeline.e1_eval import behave_seed
    return np.random.default_rng(behave_seed(f"{tag}:opp", int(k), int(update)))


def deck_ids(opp_deck) -> tuple:
    """The 8 per-slot ids styled_decisions' spell test reads: selfplay_deck(opp_deck).card_ids."""
    from pipeline import e1_eval as E
    return tuple(E.selfplay_deck(opp_deck).card_ids)


def after_decision(tick: int, d: dict, cfg: dict, eng: int) -> tuple[Optional[int], int]:
    """SelfPlaySide.apply's schedule for one decision ``d`` at ``tick`` (``eng`` = env.engine_delay_ticks: crforge's
    command delay, 0 on RoyaleSim) -> (landing tick of the play or None, the side's next decision tick). The match
    delay is action_delay_ticks minus eng (Match._setup), plus the style's spell delay for a styled spell play."""
    de = int(cfg["decide_every"])
    delay = max(0, int(cfg.get("action_delay_ticks") or 0) - int(eng))
    if "_opp_style" in cfg:
        delay += int(d.get("_style_delay", 0))
    if d["play"] and delay:
        return tick + delay, tick + de * ((delay + eng) // de + 1)
    if d["play"]:
        return tick, tick + de * (eng // de + 1) if eng else tick + de
    return None, tick + de


class _Cells:
    """The policy as a decide sees it: cell_logits(enc, slot) -> ``cell_fn`` on the rows ``enc["_row"]`` names."""

    def __init__(self, cell_fn: Callable):
        self.cell_fn = cell_fn

    def cell_logits(self, enc, slot):
        import torch
        out = self.cell_fn(enc["_row"].cpu().numpy(), slot.cpu().numpy())
        return out if torch.is_tensor(out) else torch.from_numpy(np.asarray(out))


def decide(cfgs, rngs, ids, my_elixir, enemy_my_half, heads: dict, p, allowed, stalled, cell_fn) -> list[dict]:
    """One opponent's decisions for n rows of one forward: ``cfgs`` / ``rngs`` / ``ids`` per row (opp_match_cfg,
    behave_rng, deck_ids of that row's match); ``my_elixir`` (float, the view's own elixir) and ``enemy_my_half``
    (bool, an enemy body at view y >= .5) per row = what the style's bank rule reads; ``heads`` = the GenPolicy heads
    (torch, at least gate and card); ``p`` = sigmoid(gate) [n]; ``allowed`` bool [n, 8], ``stalled`` bool [n]
    (e1_eval.Match.pre); ``cell_fn(rows, slots)`` -> [len(rows), N_CELLS] cell logits of those rows of this forward.
    Same dicts as production (play / slot / cell / why / lp_* / _style_delay ...)."""
    import torch
    from pipeline import adaptive_opponents as AO
    from pipeline import e1_eval as E
    n = len(cfgs)
    sides = [SimpleNamespace(cfg=c, rng_behave=g, deck=SimpleNamespace(card_ids=d),
                             _cur=(None, None, SimpleNamespace(my_elixir=float(el),
                                                               units=[SimpleNamespace(side=1, y=1.0)] if eh else [])))
             for c, g, d, el, eh in zip(cfgs, rngs, ids, my_elixir, enemy_my_half)]
    enc = {"_row": torch.arange(n)}
    model = _Cells(cell_fn)
    allowed, stalled, p = np.asarray(allowed, bool), np.asarray(stalled, bool), np.asarray(p, np.float64)
    if "_opp_style" in cfgs[0]:
        return AO.styled_decisions(model, enc, heads, p, allowed, stalled, sides)
    return E.sample_decide_batch(model, enc, heads, p, allowed, stalled, sides, cfgs[0])


def bank_inputs(row: dict) -> tuple[float, bool]:
    """(my_elixir, enemy_my_half) from a GenModel row: sc[3] * 10 and the unit tokens (enemy side column, y col 5) --
    float32 copies of the view's values, so a bank threshold within float32 rounding of them can flip (the test counts
    it); an exact producer takes the view's float64 elixir from the Java builder instead."""
    from pipeline.obs_contract import _SIDE_COL
    tok, mask = row["tok"], row["mask"]
    enemy = mask & (tok[:, _SIDE_COL[1]] > 0) & (tok[:, 13] == 0)
    return float(row["sc"][3]) * 10.0, bool((tok[enemy, 5] >= .5).any())
