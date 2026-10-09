"""E1 option B: the S1 checkpoint vs HELD-OUT ghosts in the engine under the LIVE deploy rule. One process per slot.

    icebow/.venv/Scripts/python.exe -m pipeline.e1_eval --port 38031 --ckpt icebow/data/pipeline/s1_icebow_v6lat_s0.pt ^
        --pool icebow/data/ghost_pool/pool_env_v1.jsonl --split heldout --entries 0:293 --seeds 0 --shard 0/2 ^
        --policy live --mode eval --out scratchpad/gauntlet/L67/e1/baseline_k0/slot0

Design: scratchpad/gauntlet/L67/e1_engine_rl_design.md sections 2.3 (eval protocol), 3.1 (obs), 6.2 (parity).
Runbook: scratchpad/gauntlet/L67/e1/baseline_runbook.md. NO training code here.

THE LIVE RULE (``--policy live``, defaults = the owner's run8/run9 configuration, HANDOFF l.2747):
  every ``--decide-every`` 10 engine ticks (0.5 s): obs = ``e1_view.live_view(from_engine(compact_raw(state)))``
  with ``np.random.default_rng(crc32(f"{tag}:eval:{k}"))`` (ONE generator per match, consumed decision by decision);
  ``past`` = my last 3 ACCEPTED plays (``dataset._past``, engine ticks) as engine_play does; p = sigmoid(gate);
  allowed slots = in hand AND cost <= floored elixir (student_live.py:163-179); none allowed -> WAIT;
  card = argmax of the hand-masked card logits over allowed slots; play iff p > tau (0.27) OR the anti-stall rule
  holds (floored elixir >= 9 and >= 12 s of ENGINE time since my last accepted play or the match start,
  student_live.py:126-133 + L67r F2); cell = argmax of that card's 2,304 cell logits (no legality mask; a refusal is
  counted, never retried); ``engine_play.cell_to_engine`` -> ``env.eng.act``.
  Match start for the anti-stall clock = the first decision tick (tick 90, when the engine first accepts deploys).
Overrides for the section-5cs.66 continuity rule: ``--tau 0.5 --no-afford-mask --stall-elixir none --obs clean``.
``--policy sample`` (design: scratchpad/gauntlet/L68/rl_plan.md "Behaviour policy"): a tempered version of the same
rule for RL rollouts, exact log-probs. gate: ``p_b = sigmoid((z_gate - logit(tau)) / T)``, ``g ~ Bernoulli(p_b)``
(skipped, forced play, when anti-stall fires); card: ``softmax(card_logits_masked_to_allowed / T)``; cell:
``softmax(cell_logits(enc, c) / T)`` over all 2,304 cells. ``T`` -> cfg key ``T`` (``--sample-T``, default 0.5); as
``T -> 0`` this reproduces the live rule (tie-free rows). RNG: one ``np.random.Generator`` per match, seeded
``crc32(f"{tag}:behaviour:{rollout_index}:{update}")`` (cfg keys ``rollout_index``/``update``, default 0). Per-decision
trajectory recorded when ``cfg["record"]`` is truthy, stacked into ``Match.result()["traj"]``.
Controls: ``--policy none`` (never plays; the model still scores p), ``--policy random --p-random P`` (state-blind: with
prob P per decision a uniformly random ALLOWED slot -- ``--random-hand-only`` for engine_play's hand-only rule -- at a
uniformly random own-half cell).
``--mode parity``: no policy; the corpus's own our-side commands are driven through the same scheduler as the ghost
(``PoolV1Env(drive_our_commands=True)``) to the corpus final tick; the final ``state_hash`` is compared with the
corpus record (design 6.2 gate: >= 19/20).

Live condition on the CLI (L68 T12b; the RL trainer's condition keys, so a gate reproduces the training condition):
``--noise-off all --opp-elixir counter --action-delay 26 --extrapolate 26`` (cfg keys noise / opp_elixir /
action_delay_ticks / extrapolate_ticks; defaults = unset = the old behaviour). ``rl_gate --commands --config`` emits them.
Self-play (L68 T12b league, the RL actor only -- not this CLI): ``SelfPlayMatch`` / ``run_selfplay_batch`` run two
policies on one ``royale_env.RoyaleSelfPlayEnv``, each side a ``SelfPlaySide`` (Match's code, its own mirrored view).

Outputs in ``--out`` (refused if it exists non-empty, unless ``--resume``): ``run.json`` (args, shas, model info),
``matches.jsonl`` (one line per match, flushed), ``errors.jsonl`` (engine failures; the process exits 3), ``done.json``.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
import zlib
from collections import Counter
from dataclasses import fields as dc_fields, replace as dc_replace
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import vocab                                                        # noqa: E402
from pipeline.dataset import PAST_K, _past                                        # noqa: E402
from pipeline.e1_pool import POOL_V1, load_pool_v1, ours, select_split, sha256_file  # noqa: E402
from pipeline.e1_view import Noise, live_view                                     # noqa: E402
from pipeline.obs_contract import F as TOK_F, S as SC_S, TICK_S, from_engine, load_deck, to_tokens  # noqa: E402

NOISE_NAMES = tuple(f.name for f in dc_fields(Noise))    # e1_view.Noise's 10 component names
NOISE_ALIASES = {"scalars": ("my_elixir", "opp_elixir", "king_hp"),   # O5: pre-split spelling, kept for old
                 "all": NOISE_NAMES}                                    # CLI invocations and recorded run.json;
                                                                        # all = every component (rl_royale's spelling)

TAU_LIVE = 0.27
STALL_ELIXIR_LIVE = None   # owner 2026-10-07: anti-stall removed permanently (live runs --no-anti-leak since 10-04)
STALL_SECONDS_LIVE = 12.0
DECIDE_EVERY = 10
MAX_U = 64
N_SLOTS = 8
GRID_X, GRID_Y = 36, 64                       # model_v3.GRID_X / GRID_Y (not imported: model_v3 pulls torch)
N_CELLS = GRID_X * GRID_Y                     # 2,304 half-tile cells (model_v3.N_CELLS)
SCRIPT_MARGIN_TICKS = 200                     # design 4.2.1: "outlived the script" = end > last ghost tick + 200
SLOT_OF_PORT = {38031: 0, 38032: 1, 37031: 0, 37032: 1}

# cfg["opp_elixir"] (L68 T8b; unset/None = today's obs, untouched): the model's BoardState.opp_elixir is replaced by
# pipeline.opp_elixir_count.OppElixirCounter fed ONLY the ghost's DELIVERED plays at ticks <= now.
#   counter      the memory-reader equivalent: bodiless spells dropped (the reader decodes no effects)
#   counter_all  every delivered play (perfect-detection upper bound)
OPP_ELIXIR_MODES = ("counter", "counter_all")
# Spells whose bodies carry the spell's card id, so the reader sees them. COPY of
# scratchpad/gauntlet/L68/opp_elixir/eval_accounting.py BODY_SPELLS / keep("reader", .), pinned equal by
# pipeline/tests/test_e1_opp_counter.py.
BODY_SPELLS = frozenset({"graveyard", "goblin_barrel", "barbarian_barrel", "royal_delivery", "clone"})
# GenPolicy.row keys = the GenModel forward's input (heads_t); recorded per decision for a GenPolicy under cfg["record"]
GEN_ROW_KEYS = ("tok", "mask", "sc", "past", "hand_card", "hand_form", "next_card", "next_form", "deck_card",
                "deck_form", "hand_slot", "slot_card", "slot_form")
GEN_IDENT_KEYS = GEN_ROW_KEYS[4:]             # the integer identity / slot arrays (int64 in the trajectory)
OWN_FX_TICKS = 150                            # cfg["own_effects"]: plays older than this (7.5 s) act on nothing
OPP_TRACE_EVERY = 20                          # result()["opp_counter"]["trace"]: one (tick, est, truth) per N decisions
# cfg["action_delay_ticks"] D (L68 T9; unset/0 = today, byte-identical): live deploy lag. A play decided on the board
# at tick T enters the engine at T + D (live_play.py: tap -> registered ~24-27 ticks later) at the cell chosen at T.
# While pending there are no decisions, the card stays in hand and no elixir is spent (Match.apply advances straight
# to T + D, acts, then on to the first decide_every grid tick after T + D). Past plays / the anti-stall clock use the
# LANDING tick. A refusal at landing is counted (refuse_reasons, plays_refused_at_landing), never retried; a match
# that ends first counts plays_unlanded ("match_over_before_landing").
# cfg["extrapolate_ticks"] H (L68 T10; unset/0 = today, byte-identical): each decision sees the RAW state advanced H
# ticks by pipeline.extrapolate.extrapolate (velocity from the previous decision round's raw state of this match;
# the first decision of a match is not extrapolated). The model input, affordability / anti-stall elixir and the
# past-play dt use tick + H; the decision / landing / anti-stall clock ticks stay real. cfg["opp_elixir"]: the
# counter's estimate at tick + H with no further plays (= min(10, est(tick) + regen)), the counter itself never
# moves past the real tick; the truth-error diagnostic stays est(tick) vs truth(tick).
# cfg["afford_ticks"] A (L74; unset = today, byte-identical): the afford mask (live/sample policies) uses MY elixir A
# ticks ahead from the RAW state (afford_elixir) instead of the look-ahead view's; the model input, the anti-stall
# elixir and the landing are unchanged. A == extrapolate_ticks reproduces today's mask (except a match's first,
# unextrapolated decision).


# ------------------------------------------------------------------------------------------------------
# pure helpers (tested offline)
# ------------------------------------------------------------------------------------------------------
def obs_seed(tag: str, k: int) -> int:
    return zlib.crc32(f"{tag}:eval:{k}".encode())


def random_seed(tag: str, k: int) -> int:
    return zlib.crc32(f"{tag}:random:{k}".encode())


def behave_seed(tag: str, rollout_index: int, update: int) -> int:
    """rl_plan.md 'Behaviour policy': one RNG per match for the sample policy's draws."""
    return zlib.crc32(f"{tag}:behaviour:{rollout_index}:{update}".encode())


def parse_shard(spec: str) -> tuple[int, int]:
    i, n = (int(v) for v in str(spec).split("/"))
    if not (n >= 1 and 0 <= i < n):
        raise SystemExit(f"bad --shard {spec!r}")
    return i, n


def parse_noise_off(spec: str) -> Noise:
    """``--noise-off``: comma list of e1_view.Noise component names to switch OFF, plus the O5 alias
    ``scalars`` (the pre-split name) which expands to ``my_elixir,opp_elixir,king_hp`` -- so old invocations
    and recorded run.json ``"noise_off": ["scalars"]`` still parse the same way (``all`` = every component, the RL
    config's spelling of the live condition); '' -> all ON (unchanged
    live_view). Unknown name -> SystemExit (L67aq attribution screen, HANDOFF "AW. L67aq" proposal 1)."""
    raw = [s.strip() for s in str(spec).split(",") if s.strip()]
    names: list[str] = []
    for n in raw:
        names.extend(NOISE_ALIASES.get(n, (n,)))
    bad = [n for n in names if n not in NOISE_NAMES]
    if bad:
        raise SystemExit(f"bad --noise-off name(s) {bad}, choose from {NOISE_NAMES} (or alias 'scalars')")
    return dc_replace(Noise(), **{n: False for n in names})


def noise_off_names(noise: Noise) -> list[str]:
    """The switched-OFF component names, sorted -- what run.json / the header line record for --noise-off."""
    return sorted(n for n in NOISE_NAMES if not getattr(noise, n))


def opp_play_kept(mode: str, key: str) -> bool:
    """Is a delivered opponent play (base key, e.g. 'the_log') charged by the ``mode`` counter?"""
    if mode == "counter_all":
        return True
    from pipeline.opp_elixir_count import card_db
    return card_db().kind(key) != "spell" or key in BODY_SPELLS


def tap_ghost_deliveries(env) -> None:
    """Record every ghost play ``env`` DELIVERS as ``env.opp_delivered`` [(tick it went in, card slug)], in order.
    Wraps the env INSTANCE's ``_fire_ghosts_at`` once (RoyalePoolEnv / PoolV1Mixin both deliver only there, with
    ``tick`` = the engine tick of the act) and diffs ``ghost_cards_delivered`` around each call -- the recorded
    ``ghost_events`` carry the SCHEDULED tick, which is earlier than delivery for a retried refusal. Call before
    every ``env.reset`` (clears the list; deliveries during the warm-up are kept)."""
    if not hasattr(env, "opp_delivered"):
        fire = env._fire_ghosts_at

        def tapped(tick):
            before = Counter(env.ghost_cards_delivered)
            fire(tick)
            for card, n in (Counter(env.ghost_cards_delivered) - before).items():
                env.opp_delivered.extend([(int(tick), str(card))] * n)
        env._fire_ghosts_at = tapped
    env.opp_delivered = []


def parse_seeds(spec: str) -> list[int]:
    out = [int(v) for v in str(spec).split(",") if v.strip() != ""]
    if not out or len(set(out)) != len(out):
        raise SystemExit(f"bad --seeds {spec!r}")
    return out


def parse_entries(spec: Optional[str], entries: list[dict]) -> list[int]:
    """``a:b`` (python slice over the split's entries in pool order), ``all``, or a file of tags (json list / lines)."""
    n = len(entries)
    if spec is None or spec == "all":
        return list(range(n))
    p = Path(spec)
    if ":" in spec and not p.exists():
        a, b = spec.split(":", 1)
        lo, hi = int(a or 0), (int(b) if b else n)
        if not 0 <= lo <= hi <= n:
            raise SystemExit(f"--entries {spec} outside 0:{n}")
        return list(range(lo, hi))
    text = p.read_text(encoding="utf-8")
    tags = json.loads(text) if text.lstrip().startswith("[") else [t.strip() for t in text.splitlines() if t.strip()]
    pos = {e["tag"]: i for i, e in enumerate(entries)}
    missing = [t for t in tags if t not in pos]
    if missing:
        raise SystemExit(f"{len(missing)} tag(s) not in this split, e.g. {missing[:3]}")
    return [pos[t] for t in tags]


def make_tasks(idx: Sequence[int], seeds: Sequence[int], shard: tuple[int, int]) -> list[tuple[int, int]]:
    """(entry index, seed k) in entry-then-seed order, dealt round-robin: task j belongs to shard j % n."""
    tasks = [(int(i), int(k)) for i in idx for k in seeds]
    si, sn = shard
    return [t for j, t in enumerate(tasks) if j % sn == si]


def refuse_existing_out(out: Path, resume: bool = False) -> None:
    out = Path(out)
    if out.exists():
        if not out.is_dir():
            raise SystemExit(f"REFUSING: --out {out} exists and is not a directory")
        if any(out.iterdir()) and not resume:
            raise SystemExit(f"REFUSING: output dir {out} exists and is not empty (use a new dir, or --resume)")
    elif resume:
        raise SystemExit(f"--resume needs the existing run dir {out}")


def allowed_slots(hand: np.ndarray, costs: Sequence[float], elixir_int: float, afford_mask: bool = True) -> np.ndarray:
    """In hand AND (when ``afford_mask``) cost <= the bar's integer elixir (student_live.py:175-178: skip if
    ``cost > elixir_int + 1e-6``)."""
    hand = np.asarray(hand, dtype=bool)
    if not afford_mask:
        return hand.copy()
    return hand & np.array([float(c) <= float(elixir_int) + 1e-6 for c in costs], dtype=bool)


def afford_elixir(players, side: int, tick: int, ticks: int) -> float:
    """cfg["afford_ticks"] A / live_play --afford-ticks (L74; unset = today's rule, the look-ahead elixir): MY elixir
    ``ticks`` after ``tick`` with no spend, read from the RAW state and advanced exactly as pipeline.extrapolate
    advances it, so A == extrapolate_ticks reproduces the look-ahead elixir. Live, a tap that cannot pay yet is held
    by the game and refused unless it can pay within ~22 ticks of the board tap's arrival (n = 19,361 live plays,
    scratchpad/gauntlet/L74/latency/afford_arrival.txt): the afford horizon is arrival + ~21, not the look-ahead."""
    from pipeline.opp_elixir_count import MAX_ELIXIR, regen_between
    me = next(p for p in players if int(p["side"]) == int(side))
    g = regen_between(tick, tick + ticks)
    if "elixir_exact" in me:                                  # SIM state / live_mem.to_observe
        return min(MAX_ELIXIR, float(me["elixir_exact"]) + g)
    return min(MAX_ELIXIR * 1e4, float(me["elixir_raw"]) + g * 1e4) / 1e4    # live reader frame


def pending_hand(deck: Sequence[int], hand: Sequence[int], nxt: int, played: Sequence[int],
                 pending: Sequence[int]) -> tuple[list[int], int, list[int]]:
    """cfg["pipeline_decisions"] / live --pipeline-decisions: my hand and next card as the game will show them once my PENDING
    plays (card ids, decision order) have executed -- what a pro's second-card training row shows (dataset.build_replay: the
    play frame of card B is pre-B, post-A). Each pending card still in ``hand`` hands its position to the current ``nxt``;
    the new next = the queue card that entered the queue first (FIFO cycle): never-played initial queue cards before played
    ones (``played`` = my executed plays, oldest first) by their LAST play; -1 = unknown (two or more never-played queue
    cards: my first plays of a match). A pending card no longer in ``hand`` already executed and is skipped.
    -> (hand, next, positions substituted)."""
    hand, played, pos = list(hand), list(played), []
    for c in pending:
        if c not in hand:
            continue
        i = hand.index(c)
        queue = [k for k in deck if k not in hand and k != nxt]
        hand[i] = nxt
        pos.append(i)
        played.append(c)
        if nxt < 0:                                       # next unknown -> the card after it too
            continue
        fresh = [k for k in queue if k not in played]
        last = {k: j for j, k in enumerate(played)}
        nxt = (fresh[0] if len(fresh) == 1 else -1) if fresh else (min(queue, key=last.get) if queue else -1)
    return hand, nxt, pos


# ---- pipelined decisions (L74 pipeline_decisions; live: live_play --pipeline-decisions) ---------------------------------------
# cfg["pipeline_decisions"] (needs action_delay_ticks > 0; opt-in, unset = byte-identical): the MODEL decides again while one of
# its plays is decided but not landed, on the 2-tick reader-frame grid (FOLLOW_FRAME_TICKS) from the first frame after the first
# tap returned (cfg["follow_arrival_ticks"]), at most FOLLOW_MAX_OUT plays outstanding. Rules (live twin: live_play, same facts):
#   * the pending play is a play already made: the board the model sees holds its bodies / spell at their landing (extrapolate.
#     pending_board), my hand / next as pending_hand shows them, my elixir minus its cost, it is the newest past play and
#     (own_effects) acts in the look-ahead -- so the model does not re-answer a threat its first card already answers
#   * the hand position of a pending card is masked (the game still shows the pending card there): never re-picked / re-tapped
#   * affordability = my elixir (afford_ticks ahead when set) minus the cost of every outstanding play; the final check is the
#     shared follow_up_verdict (cap, slot busy, elixir) -- nothing else is hard-coded about a "second play"
#   * gate, card and cell are the model's own (the decision options apply unchanged; lethal Rocket never fires while a play is
#     pending; cfg["pipeline_tau_delta"] raises the gate threshold only while one is: default 0 = the model's own tau)
#   * a refused first play changes nothing: the second decision stands on its own; no decision on a frame where the last
#     outstanding play landed (live: its confirmation frame), nor while the cap is reached
#   * the hazard decoder's step while pending = the real ticks since the previous decision, 0 right after a play (live's rule)
# SelfPlaySide does not support it (ghost Match only).


# ---- follow-up plays (L74 latency2; live: live_play --follow-up-taps, pilot.plan_follow_up) -------------------------------
# A decision dict that carries ``follow_ups`` = [follow_up_spec(slot, cell, after_ticks), ...] asks for second plays decided
# ``after_ticks`` after the first one WITHOUT waiting for it to land (live: tapped while the first is still unconfirmed).
# Match.apply plays the same rules live_play.follow_verdict does, in engine ticks (opt-in: no key = no change, byte-identical):
#   * the follow-up is decided at tick T + after_ticks (re-checked every 2 ticks = the reader frame grid until
#     T + after_ticks + within_ticks, then dropped) and needs my elixir ``afford_ticks`` ahead (default FOLLOW_AFFORD_TICKS)
#     MINUS the cost of every play decided but not landed yet (the first, earlier follow-ups) to cover its cost
#   * it is dropped when the first play was refused at landing before it was decided (``require_first``)
#   * it lands at A's landing + max(after_ticks - cfg["follow_arrival_ticks"], 0): live both taps are issued as soon as the
#     first board tap returned (~2 ticks deployed, FOLLOW_ARRIVAL_TICKS), so a request below that lands together with it
#     (live, 3 friendly matches 2026-10-09, 11 pairs asked 4 ticks apart: landing gap median 0, mean 1.1, max 3; the first
#     taps took ~4 ticks on a CPU-starved host)
#   * a card that has left the hand / cannot be paid at its landing is refused by the engine and counted like any refusal
# While any of them is pending there are no decisions, as for a single delayed play.
FOLLOW_AFFORD_TICKS = 6          # live_play.FOLLOW_AFFORD_TICKS: default afford horizon of a follow-up
FOLLOW_ARRIVAL_TICKS = 2         # deployed live: decision frame -> board tap returned (stage_chain.txt: median 2.1 ticks)
FOLLOW_FRAME_TICKS = 2           # the reader delivers a frame every 2 ticks: a waiting follow-up is re-checked this often


def follow_up_spec(slot: int, cell: int, after_ticks: int, within_ticks: int = 20, afford_ticks: Optional[int] = None,
                   require_first: bool = True) -> dict:
    """One entry of a SIM decision's ``follow_ups`` (the live twin is GenPilot.plan_follow_up(name, xy, ...))."""
    if int(after_ticks) < 0 or int(within_ticks) < 0:
        raise ValueError(f"follow-up needs after_ticks / within_ticks >= 0: {after_ticks}, {within_ticks}")
    return {"slot": int(slot), "cell": int(cell), "after_ticks": int(after_ticks), "within_ticks": int(within_ticks),
            "afford_ticks": None if afford_ticks is None else int(afford_ticks), "require_first": bool(require_first)}


FOLLOW_MAX_OUT = 2               # plays decided but not landed at once (live: taps outstanding); a follow-up waits at the cap


def follow_up_verdict(*, tick: int, due: int, expire: int, blocked: Optional[str], first_failed: bool, slot_changed: bool,
                      slot_busy: bool, n_out: int, have: float, cost: float) -> tuple:
    """What to do with a follow-up on the frame / engine tick ``tick`` -> ("wait", why) | ("cancel", why) | ("fire", "").
    ONE rule list for live_play.follow_verdict and Match._apply_follow_ups (the caller builds the facts, so only the facts
    differ): the play it follows was refused (``first_failed``) -> cancel first_unconfirmed; its card is no longer in
    the slot (``slot_changed``) -> cancel; past ``expire`` -> cancel, with what held it (``blocked``) else "late"; before
    ``due`` -> wait; another play outstanding on its slot (``slot_busy``) -> cancel slot_busy; ``n_out`` plays outstanding
    at FOLLOW_MAX_OUT -> wait "outstanding"; ``have`` (follow_up_have, reserved already taken off) short of ``cost`` ->
    wait "unaffordable"; else fire. The order is the order of the checks."""
    if first_failed:
        return "cancel", "first_unconfirmed"
    if slot_changed:
        return "cancel", "slot_changed"
    if tick > expire:
        return "cancel", blocked or "late"
    if tick < due:
        return "wait", "early"
    if slot_busy:
        return "cancel", "slot_busy"
    if n_out >= FOLLOW_MAX_OUT:
        return "wait", "outstanding"
    if have + 1e-6 < cost:
        return "wait", "unaffordable"
    return "fire", ""


def follow_up_have(elixir: float, tick: int, horizon: int, reserved: float) -> float:
    """My elixir ``horizon`` ticks after ``tick`` with no further spend, capped, minus ``reserved`` (the cost of every play
    decided but not landed yet). ONE formula for live_play.follow_verdict and Match.apply."""
    from pipeline.opp_elixir_count import MAX_ELIXIR, regen_between
    return min(MAX_ELIXIR, float(elixir) + regen_between(tick, tick + int(horizon))) - float(reserved)


def anti_stall(elixir_int: float, tick: int, last_play_tick: int, stall_elixir: Optional[float],
               stall_seconds: float) -> bool:
    """student_live.StudentPolicy._stalled with ENGINE time: elixir >= stall_elixir and >= stall_seconds since the
    last accepted play (or the match start)."""
    if stall_elixir is None or float(elixir_int) < float(stall_elixir):
        return False
    return (int(tick) - int(last_play_tick)) * TICK_S >= float(stall_seconds) - 1e-9


def model_forward(model, tok, mask, sc, past, device: str = "cpu"):
    """encode once; heads with the hand mask. -> (enc, heads, p_gate, hand bool[8])."""
    import torch
    from pipeline.model_v3 import hand_mask_from_sc
    with torch.no_grad():
        t = (lambda a: torch.from_numpy(np.ascontiguousarray(a)).unsqueeze(0).to(device))
        tsc = t(sc)
        hm = hand_mask_from_sc(tsc)
        enc = model.encode(t(tok), t(mask), tsc, t(past))
        heads = model.heads(enc, hm)
        p = float(torch.sigmoid(heads["gate"])[0])
    return enc, heads, p, hm[0].cpu().numpy().astype(bool)


def live_decide(model, enc, heads, p_gate: float, allowed: np.ndarray, *, tau: float, stalled: bool,
                device: str = "cpu", decision_options=None, rng=None, card_names=None) -> dict:
    """The live student's choice (student_live.py:161-236) on precomputed heads:
    no allowed slot -> WAIT ('no_affordable'); slot = argmax over allowed of the hand-masked card logits;
    p <= tau and not stalled -> WAIT; else cell = argmax of the card-conditioned cell logits."""
    import torch
    if decision_options is not None and decision_options.active:
        from .decision_options import decide_batch
        return decide_batch(model, enc, heads, [p_gate], np.asarray(allowed, bool)[None], np.array([stalled]),
                            tau=tau, device=device, options=decision_options, rngs=[rng],
                            card_names=[card_names] if card_names is not None else None)[0]
    allowed = np.asarray(allowed, dtype=bool)
    if not allowed.any():
        return {"play": False, "slot": -1, "cell": -1, "why": "no_affordable"}
    with torch.no_grad():
        logits = heads["card"][0].clone()
        logits = logits.masked_fill(~torch.from_numpy(allowed).to(logits.device), float("-inf"))
        slot = int(logits.argmax().item())
        if p_gate <= tau and not stalled:
            return {"play": False, "slot": slot, "cell": -1, "why": "wait"}
        cell = int(model.cell_logits(enc, torch.tensor([slot], device=device))[0].argmax().item())
    return {"play": True, "slot": slot, "cell": cell, "why": "stall" if p_gate <= tau else "gate"}


def random_decide(rng: random.Random, allowed: np.ndarray, p_random: float) -> dict:
    """engine_play.decide's random control (draw first, then a uniform allowed slot, uniform own-half cell)."""
    allowed = np.asarray(allowed, dtype=bool)
    play = rng.random() < p_random and bool(allowed.any())
    if not play:
        return {"play": False, "slot": -1, "cell": -1, "why": "random_wait"}
    slot = rng.choice([i for i in range(N_SLOTS) if allowed[i]])
    cell = rng.randrange(GRID_X * (GRID_Y // 2)) + GRID_X * (GRID_Y // 2)
    return {"play": True, "slot": slot, "cell": cell, "why": "random"}


def live_decide_batch(model, enc, heads, p, allowed: np.ndarray, stalled: np.ndarray, *, tau: float,
                       device: str = "cpu", decision_options=None, rngs=None, card_names=None, **context) -> list[dict]:
    """``live_decide`` over every row of a shared forward at once. The card argmax and the p-vs-tau compare are
    elementwise (bit-identical to a per-row loop); ONE ``cell_logits`` call covers every row that plays, so this
    is O(1) GPU calls per round, not O(matches) (L68e)."""
    import torch
    if decision_options is not None and decision_options.active:
        from .decision_options import decide_batch
        return decide_batch(model, enc, heads, p, allowed, stalled, tau=tau, device=device,
                            options=decision_options, rngs=rngs or [None] * len(allowed), card_names=card_names,
                            **context)
    B = allowed.shape[0]
    p = np.asarray(p, dtype=np.float64)
    any_allowed = allowed.any(axis=1)
    out: list[Optional[dict]] = [None] * B
    with torch.no_grad():
        logits = heads["card"].clone()
        logits = logits.masked_fill(~torch.from_numpy(allowed).to(logits.device), float("-inf"))
        slot = logits.argmax(dim=-1).cpu().numpy()
        play = any_allowed & ((p > tau) | stalled)
        play_idx = [r for r in range(B) if play[r]]
        cell = np.full(B, -1, dtype=np.int64)
        if play_idx:
            idx_t = torch.tensor(play_idx, device=logits.device)
            sub_enc = {k: v[idx_t] for k, v in enc.items()}
            slot_t = torch.tensor(slot[play_idx], device=logits.device)
            cell[play_idx] = model.cell_logits(sub_enc, slot_t).argmax(dim=-1).cpu().numpy()
    for r in range(B):
        if not any_allowed[r]:
            out[r] = {"play": False, "slot": -1, "cell": -1, "why": "no_affordable"}
        elif not play[r]:
            out[r] = {"play": False, "slot": int(slot[r]), "cell": -1, "why": "wait"}
        else:
            out[r] = {"play": True, "slot": int(slot[r]), "cell": int(cell[r]),
                      "why": "stall" if p[r] <= tau else "gate"}
    return out


def sample_decide_batch(model, enc, heads, p, allowed: np.ndarray, stalled: np.ndarray, matches: Sequence,
                         cfg: dict) -> list[dict]:
    """rl_plan.md 'Behaviour policy', batched: the tensor work (masked softmaxes, ONE ``cell_logits`` call for
    every playing row) is shared across the round; each row's Bernoulli/categorical draws come from ITS OWN
    ``matches[r].rng_behave``, so a row's sampled action never depends on which other matches share the round.
    ``matches[r]`` needs only a ``.rng_behave`` (an ``np.random.Generator``); ``run_batch`` passes ``Match``
    instances, the single-row caller (``Match.decide_row``) passes ``[self]``.
    Returns dicts with the live-decide keys (play/slot/cell/why) PLUS the record fields from the spec:
    allowed, stalled, gate_sampled, lp_gate, lp_card, lp_cell (float64), p_gate (untempered sigmoid), T."""
    import torch
    tau, T = float(cfg["tau"]), float(cfg.get("T", 0.5))
    B = allowed.shape[0]
    p = np.asarray(p, dtype=np.float64)
    any_allowed = allowed.any(axis=1)
    gate_sampled = any_allowed & ~stalled                      # forced (stalled) or impossible (no card) -> not sampled
    logit_tau = math.log(tau / (1.0 - tau))
    z_gate = heads["gate"].detach().cpu().numpy().astype(np.float64)
    with np.errstate(over="ignore"):
        p_b = 1.0 / (1.0 + np.exp(-(z_gate - logit_tau) / T))
    g = np.zeros(B, dtype=bool)
    lp_gate = np.zeros(B, dtype=np.float64)
    for r in range(B):
        if gate_sampled[r]:
            g[r] = matches[r].rng_behave.random() < p_b[r]
            lp_gate[r] = math.log(p_b[r] if g[r] else 1.0 - p_b[r])
    play = any_allowed & (stalled | g)
    slot = np.full(B, -1, dtype=np.int64)
    cell = np.full(B, -1, dtype=np.int64)
    lp_card = np.zeros(B, dtype=np.float64)
    lp_cell = np.zeros(B, dtype=np.float64)
    with torch.no_grad():
        card_logits = heads["card"].clone()
        card_logits = card_logits.masked_fill(~torch.from_numpy(allowed).to(card_logits.device), float("-inf"))
        card_probs = torch.softmax(card_logits.double() / T, dim=-1).cpu().numpy()          # [B, 8]
        for r in range(B):
            if play[r]:
                probs = card_probs[r]
                c = int(matches[r].rng_behave.choice(N_SLOTS, p=probs))
                slot[r] = c
                lp_card[r] = math.log(probs[c])
        play_idx = [r for r in range(B) if play[r]]
        if play_idx:
            idx_t = torch.tensor(play_idx, device=card_logits.device)
            sub_enc = {k: v[idx_t] for k, v in enc.items()}
            slot_t = torch.tensor(slot[play_idx], device=card_logits.device)
            cell_logits = model.cell_logits(sub_enc, slot_t)
            cell_probs = torch.softmax(cell_logits.double() / T, dim=-1).cpu().numpy()      # [len(play_idx), 2304]
            for j, r in enumerate(play_idx):
                probs = cell_probs[j]
                x = int(matches[r].rng_behave.choice(N_CELLS, p=probs))
                cell[r] = x
                lp_cell[r] = math.log(probs[x])
    out: list[Optional[dict]] = [None] * B
    for r in range(B):
        if not any_allowed[r]:
            why = "no_affordable"
        elif not play[r]:
            why = "wait"
        elif stalled[r]:
            why = "stall"
        else:
            why = "gate"
        out[r] = {"play": bool(play[r]), "slot": int(slot[r]), "cell": int(cell[r]), "why": why,
                  "allowed": allowed[r].copy(), "stalled": bool(stalled[r]), "gate_sampled": bool(gate_sampled[r]),
                  "lp_gate": float(lp_gate[r]), "lp_card": float(lp_card[r]), "lp_cell": float(lp_cell[r]),
                  "p_gate": float(p[r]), "T": T}
    return out


# ------------------------------------------------------------------------------------------------------
# generalist (GenModel) behind S1's deck-slot interface (L68 T4)
# ------------------------------------------------------------------------------------------------------
GEN_V3_KEYS = ("unit_form", "opp_past")
GEN_V31_KEYS = ('opp_cycle', 'projectiles', 'effects', 'own_ability')


def gen_row_keys(model):
    version = getattr(model, 'feature_version', 1)
    return GEN_ROW_KEYS + (GEN_V3_KEYS if version >= 3 else ()) + (GEN_V31_KEYS if version >= 4 else ())


def policy_feature_version(policy):
    return int(getattr(getattr(policy, "model", policy), "feature_version", 1))


def enable_sim_features(env, *policies):
    version = max(policy_feature_version(p) for p in policies)
    if version >= 3 or hasattr(env, "feature_version"):
        env.feature_version = version
    return version


def sim_compact(match, raw):
    """Keep status bits through compacting only for this side's v3 observation."""
    compact = match.ep.compact_raw(raw)
    if match.feature_version >= 3:
        if match.feature_version == 3 and not hasattr(match.env, "public_plays"):
            raise ValueError("gen_v3 requires SIM accepted public_plays")
        for e, original in zip(compact["entities"], raw.get("entities", [])):
            if "status_flags" not in original:
                raise ValueError("gen_v3 requires SIM entity status_flags")
            e["status_flags"] = original["status_flags"]
    return compact


def sim_v3_features(match, policy):
    """V3 public features. Requires the SIM adapter's accepted landing log and status bits.

    Fail closed when an adapter has discarded that information instead of silently
    feeding a v3 network base forms and empty opponent history.
    """
    from pipeline.dataset_gen import opponent_past
    from pipeline.obs_contract import to_unit_forms
    if match.feature_version < 3:
        raise ValueError("enable v3 observations before preparing the match")
    # Use the very same view as tok/mask, after drops, substitutions and extrapolation.
    view = match._cur[2]
    if policy_feature_version(policy) >= 4:
        return dict(unit_form=to_unit_forms(view, MAX_U),
                    **match.public.features(match._view_tick, policy.gid,
                        objects_override=match._public_object_view))
    return {"unit_form": to_unit_forms(view, MAX_U),
            "opp_past": opponent_past(match.env.public_plays, match._view_tick, match.side, policy.gid)}


class GenPolicy:
    """A ``pipeline.model_gen.GenModel`` checkpoint behind the S1 deck-SLOT API that ``live_decide(_batch)``,
    ``sample_decide_batch``, ``Match`` and ``run_batch`` use, so every decide rule (tau, anti-stall, affordability,
    tempering) is S1's code unchanged. Input = ``dataset_gen``'s training row (``row``). The 4 hand-position card
    logits are scattered onto the deck slots those positions hold (-inf elsewhere): a hand holds 4 distinct slots, so
    argmax / softmax over allowed SLOTS == over allowed HAND POSITIONS. ``cell_logits(enc, slot)`` = the GenModel cell
    head for that slot's card IDENTITY + decked form (per-row tables ``slot_card`` / ``slot_form`` carried in ``enc``).
    The chosen slot goes to ``Match.apply`` as S1's does (slot -> engine deck index -> ``env.eng.act``)."""

    def __init__(self, model, card_vocab: Sequence[str]):
        self.model = model
        self.gid = {k: i for i, k in enumerate(card_vocab)}              # 0 = <pad>

    def slot_ident(self, engine_deck: Sequence[str], deck_index_of_slot: dict) -> tuple[np.ndarray, np.ndarray]:
        """[9] card id / form per deck slot; index 8 (the sc one-hots' 'unknown' column) = pad (0, FORM_PAD)."""
        from pipeline.dataset_gen import FORM_PAD, card_form, card_key
        card = np.zeros(N_SLOTS + 1, np.int64)
        form = np.full(N_SLOTS + 1, FORM_PAD, np.int64)
        for s in range(N_SLOTS):
            nm = engine_deck[deck_index_of_slot[s]]
            k = card_key(nm)
            if k not in self.gid:
                raise KeyError(f"card {nm!r} ({k}) not in the generalist's card_vocab")
            card[s], form[s] = self.gid[k], card_form(nm)
        return card, form

    @staticmethod
    def row(tok, mask, sc, past, slot_card: np.ndarray, slot_form: np.ndarray) -> dict:
        """S1's (tok, mask, sc, past) -> dataset_gen's row: sc with SC_SLOT_COLS zeroed; hand / next identities decoded
        from the sc slot one-hots (argmax, 8 -> pad) exactly as ``dataset_gen.replay_rows``; deck in canonical order
        (stable argsort by card id); past = (card, form, x, y, dt) from S1's (slot, x, y, dt), empty -> (0, 3, -1, -1, -1).
        ``hand_slot`` [4] (the deck slot at each hand position) is kept for the slot scatter."""
        from pipeline.dataset_gen import SC_SLOT_COLS
        hs = sc[7:43].reshape(4, 9).argmax(-1)
        ns = int(sc[43:52].argmax())
        sc0 = sc.copy()
        sc0[SC_SLOT_COLS] = 0.0
        ps = np.where(past[:, 0] < 0, N_SLOTS, past[:, 0]).astype(np.int64)
        p5 = np.concatenate([slot_card[ps, None], slot_form[ps, None], past[:, 1:]], -1).astype(np.float32)
        order = np.argsort(slot_card[:N_SLOTS], kind="stable")
        return {"tok": tok, "mask": mask, "sc": sc0, "past": p5,
                "hand_card": slot_card[hs], "hand_form": slot_form[hs], "next_card": slot_card[ns],
                "next_form": slot_form[ns], "deck_card": slot_card[:N_SLOTS][order],
                "deck_form": slot_form[:N_SLOTS][order], "hand_slot": hs, "slot_card": slot_card, "slot_form": slot_form}

    def heads_t(self, b: dict) -> tuple[dict, dict]:
        """The GenModel forward on a tensor batch ``b`` (``GEN_ROW_KEYS``) -> (enc, heads) in S1's deck-slot layout:
        heads["card"] [B, 8] = the 4 hand-position logits scattered onto their deck slots (-inf elsewhere),
        heads["card_hand"] the raw [B, 4]. No no_grad here: the RL learner recomputes the sampler's distribution
        through this same function WITH gradients (rl_royale.policy_terms)."""
        import torch
        enc = self.model.encode_gen(b)
        h = self.model.heads_gen(enc, b)
        B = h["card"].shape[0]
        card = torch.full((B, N_SLOTS + 1), float("-inf"), dtype=h["card"].dtype, device=h["card"].device)
        card = card.scatter(1, b["hand_slot"], h["card"])[:, :N_SLOTS]       # col 8 = unknown positions, dropped
        enc = {**enc, "slot_card": b["slot_card"], "slot_form": b["slot_form"]}
        return enc, {"gate": h["gate"], "card": card, "card_hand": h["card"]}

    def forward_batch(self, rows: Sequence[dict], device: str = "cpu"):
        """``model_forward_batch``'s contract for gen rows -> (enc, heads, p [B], hand bool [B, 8]); heads["card"] is
        [B, 8] over deck slots, heads["card_hand"] the raw [B, 4] pointer logits."""
        import torch
        with torch.no_grad():
            b = {k: torch.from_numpy(np.ascontiguousarray(np.stack([r[k] for r in rows]))).to(device)
                 for k in gen_row_keys(self.model)}
            enc, heads = self.heads_t(b)
            B = heads["card"].shape[0]
            hand = torch.zeros(B, N_SLOTS + 1, dtype=torch.bool, device=heads["card"].device)
            hand = hand.scatter(1, b["hand_slot"], True)[:, :N_SLOTS]        # = model_v3.hand_mask_from_sc(sc)
            p = torch.sigmoid(heads["gate"]).cpu().tolist()
        return enc, heads, p, hand.cpu().numpy()

    def cell_logits(self, enc: dict, slot):
        """S1Model.cell_logits' contract: [B, N_CELLS] for deck slot ``slot`` [B] -> that slot's card identity + form."""
        s = slot.long().unsqueeze(1)
        return self.model.cell_logits_gen(enc, enc["slot_card"].gather(1, s).squeeze(1),
                                          enc["slot_form"].gather(1, s).squeeze(1))


def load_policy(ckpt, device: str = "cpu"):
    """-> (model, minfo). A checkpoint dict with ``"gen": True`` -> ``GenPolicy`` (``eval_gen.load_model``); anything
    else -> ``engine_play.load_model``, unchanged (S1)."""
    import torch
    from pipeline import engine_play as ep
    try:
        gen = bool(torch.load(ckpt, map_location="cpu").get("gen"))
    except Exception:                                   # ep.load_model retries a file the trainer is rewriting
        gen = False
    if not gen:
        return ep.load_model(ckpt, device)
    from pipeline.model_gen import load_model
    model, st = load_model(ckpt, torch.device(device))
    model.eval()
    return GenPolicy(model, st["card_vocab"]), {"gen": True, "epoch": st.get("epoch"), "n_params": st.get("n_params"),
                                                 "deck": st.get("deck"), "grid": str(st["args"].get("grid", "lattice"))}


# ------------------------------------------------------------------------------------------------------
# one match
# ------------------------------------------------------------------------------------------------------
_FORM_SUFFIX = ("", "@evolution", "@hero")          # RoyaleSim MatchSetup.forms value -> the corpus name suffix


def loaded_deck_names(env, side: int, names: Sequence[str]) -> list[str]:
    """``names`` (``side``'s deck, in env deck order) as the policy's form inputs should read them. Default (no
    ``forms_mode`` or "base"): unchanged -- the DECKED form, which RoyaleSim does not play. RoyaleSim forms_mode "deck":
    each card's suffix set to the form the engine LOADED (``env.loaded_forms``; a refused form -> base), i.e. the decked
    form as the corpus and the live reader's ``deck_form_flags`` give it, for every card the engine plays in that form."""
    if getattr(env, "forms_mode", "base") != "deck":
        return names
    return [str(n).split("@")[0] + _FORM_SUFFIX[f] for n, f in zip(names, env.loaded_forms[side])]


def _slot_maps(env, deck, entry) -> tuple[list[str], dict[int, int], list[float]]:
    side = env.side
    engine_deck = [f"{it['name']}@{it['form']}" if it["form"] != "base" else str(it["name"]) for it in env.final_decks[side]]
    engine_deck = loaded_deck_names(env, side, engine_deck)
    deck_index_of_slot: dict[int, int] = {}
    for i, nm in enumerate(engine_deck):
        s = deck.slot_of(vocab.engine_key(nm))
        if s >= 0:
            deck_index_of_slot[s] = i
    if sorted(deck_index_of_slot) != list(range(N_SLOTS)):
        raise RuntimeError(f"{entry['tag']}: engine deck {engine_deck} does not cover the 8 deck slots")
    costs = [float(env.final_decks[side][deck_index_of_slot[s]]["cost"]) for s in range(N_SLOTS)]
    return engine_deck, deck_index_of_slot, costs


class Match:
    """One ``run_match`` as a state machine -- ``prepare`` (the observation), ``step`` (decide on precomputed heads,
    act, advance), ``result`` -- so ``run_batch`` can share one model forward across many matches. Same logic, same
    record, in the same order as the loop it was lifted from (L68)."""

    def __init__(self, env, deck, entry: dict, k: int, cfg: dict):
        self._setup(env, deck, k, cfg)
        self.entry = entry
        if self.opp_mode:
            tap_ghost_deliveries(env)
        self.state = env.reset(entry)
        self.side, self.mirror = env.side, env._mirror
        self.engine_deck, self.deck_index_of_slot, self.costs = _slot_maps(env, deck, entry)
        self._seed(str(entry["tag"]))

    def _setup(self, env, deck, k: int, cfg: dict) -> None:
        """Everything but the episode: cfg checks, the opp-elixir counter, the per-match tallies (shared with
        ``SelfPlaySide``, which plays one side of an env another object resets)."""
        from pipeline import engine_play as ep
        self.ep, self.env, self.deck, self.k, self.cfg = ep, env, deck, int(k), cfg
        if cfg.get('behaviour_telemetry') and getattr(env, 'behaviour_telemetry', None) is None:
            from pipeline.behaviour_telemetry import BehaviourTelemetry
            env.behaviour_telemetry = BehaviourTelemetry()
        self.feature_version = int(cfg.get("feature_version", 1))
        self.public = None
        self.t0 = time.perf_counter()
        self.delay = int(cfg.get("action_delay_ticks") or 0)
        if self.delay < 0:
            raise ValueError(f"cfg['action_delay_ticks'] {self.delay} < 0")
        self.n_unlanded = 0
        self.extrap = int(cfg.get("extrapolate_ticks") or 0)
        if self.extrap < 0:
            raise ValueError(f"cfg['extrapolate_ticks'] {self.extrap} < 0")
        if cfg.get("afford_ticks") is not None and int(cfg["afford_ticks"]) < 0:
            raise ValueError(f"cfg['afford_ticks'] {cfg['afford_ticks']} < 0")
        self._prev_raw = None                                # cfg["extrapolate_ticks"]: last decision's raw state
        self.drops = None                                    # cfg["predict_drops"] (opt-in, needs extrapolate_ticks)
        if cfg.get("predict_drops") and self.extrap:
            from pipeline.extrapolate import DropTracker
            self.drops = DropTracker()
        # cfg["own_effects"] (W1, opt-in, needs extrapolate_ticks): my accepted plays (card, engine tap, landing tick)
        # -> extrapolate(own_effects=...), the enemy bodies my Log / Tornado / Rocket reach move in the look-ahead
        self.own_fx = [] if cfg.get("own_effects") and self.extrap else None
        # cfg["pipeline_decisions"] (opt-in, see the module comment above): outstanding plays and the decision's blocked slots
        self.pipe = bool(cfg.get("pipeline_decisions"))
        if self.pipe and not self.delay:
            raise ValueError("cfg['pipeline_decisions'] needs cfg['action_delay_ticks'] > 0 (a play must be pending to decide on)")
        self.pend: list = []                                 # (landing tick, p, decision, decision _cur), by landing tick
        self._blocked: list = []                             # deck slots not choosable this decision (_pending_view)
        self._hz_step_ticks = None                           # hazard step override of the next decision (match_kwargs)
        self._pipe_last_land, self._pipe_ready = -10 ** 9, 0
        self.pipe_n: Counter = Counter()
        self.opp_mode = cfg.get("opp_elixir")
        if self.opp_mode:
            if self.opp_mode not in OPP_ELIXIR_MODES:
                raise ValueError(f"cfg['opp_elixir'] {self.opp_mode!r} not in {OPP_ELIXIR_MODES}")
            from pipeline.opp_elixir_count import OppElixirCounter
            # the counted engine's regen schedule: RoyaleSim envs declare theirs (royale_env.REGEN_SCHEDULE, no
            # triple phase); anything else (the real engine) -> the counter's default, the real schedule (T12b)
            self.opp_counter = OppElixirCounter(schedule=getattr(env, "elixir_regen_schedule", None))
            self.opp_i = self.opp_fed = self.opp_dropped = 0
            self.opp_err: list[float] = []
            self.opp_trace: list[list] = []
        self._tallies()

    def _seed(self, tag: str) -> None:
        cfg, k = self.cfg, self.k
        self.tag = tag
        obs_s = cfg.get("obs_seed")                          # RL actor override; default = today's per-(tag,k) seed
        self.obs_seed_used = int(obs_s) if obs_s is not None else obs_seed(self.tag, k)   # recorded by result()
        self.rng_obs = np.random.default_rng(self.obs_seed_used)
        self.rng_rand = random.Random(random_seed(self.tag, k))
        self.rng_behave = np.random.default_rng(
            behave_seed(self.tag, int(cfg.get("rollout_index", 0)), int(cfg.get("update", 0))))

    def _tallies(self) -> None:
        self.unmapped: set = set()
        self.done_plays: list[tuple[int, int, float, float]] = []
        self.last_play_tick: Optional[int] = None
        self.n_dec = self.n_deg = self.n_att = self.n_acc = self.n_stall = self.n_noaff = 0
        self.p_gates: list[float] = []
        self.plays: list[dict] = []
        self.traj: list[dict] = []                           # cfg["record"]: per-decision rows, see result()
        self._gen_row: Optional[dict] = None                 # gen_row()'s row for the current prepare() (GenPolicy)
        self.refuse: Counter = Counter()
        self.mix_att: Counter = Counter()
        self.mix_acc: Counter = Counter()
        self.done = False

    def prepare(self):
        """-> (tok, mask, sc, past) for the current state."""
        cfg = self.cfg
        tick = int(self.env.tick)
        if getattr(self.env, "hero_abilities", False):
            sides = [self.side] if isinstance(self, SelfPlaySide) else [0, 1]
            self._ability_commands = {s: self.env.ability_commands(s) for s in sides}
        self._gen_row = None
        if self.last_play_tick is None:
            self.last_play_tick = tick                       # match start = first decision (anti-stall clock)
        raw, h = self.state, (self.extrap if self._prev_raw is not None else 0)
        if self.feature_version >= 4:
            from pipeline.public_observation import PublicObserver
            if self.public is None:
                self.public = PublicObserver(self.side, schedule=getattr(self.env, 'elixir_regen_schedule', None))
            self.public.own_events=[e for e in getattr(self.env,'public_plays',[])+getattr(self.env,'own_ability_events',[]) if e['side']==self.side]
            self.public.update(self.state, source='sim')
        if self.extrap:                                      # cfg["extrapolate_ticks"]; 0 -> this block is skipped
            from pipeline.extrapolate import extrapolate
            if self.drops is not None:                       # observed balloon disappearances (every decision's state)
                self.drops.observe(self.state, self.side)
            if h:
                object_context = self.public.object_context(tick) if self.feature_version >= 4 else {}
                if self.drops is not None:
                    object_context = dict(object_context, drops=self.drops.pending)
                if self.own_fx is not None:
                    object_context = dict(object_context, own_effects=self._own_effects(tick))
                raw = extrapolate(self.state, self._prev_raw, h, self.side, **object_context)
            self._prev_raw = self.state
        if self.pend:                                        # cfg["pipeline_decisions"]: my pending plays on the board
            raw = self._pending_raw(raw, tick + h)
        if self.feature_version >= 4:
            self._public_object_view = raw.get('extrapolated_public_objects')
            self.public_lookahead_counts = raw.get('public_lookahead_counts', {})
            if cfg.get('behaviour_telemetry') and h:
                if not hasattr(self, '_public_lookahead_total'):
                    self._public_lookahead_total = Counter()
                self._public_lookahead_total.update(self.public_lookahead_counts)
        bs = from_engine(sim_compact(self, raw), self.side, self.deck, engine_deck=self.engine_deck,
                         unmapped=self.unmapped, feature_version=self.feature_version)
        view = live_view(bs, self.rng_obs, self.deck, cfg["noise"]) if cfg["obs"] == "live" else bs
        if self.feature_version >= 4:
            # No opponent truth or delivered command log reaches v3.1 inputs.
            from pipeline.public_observation import body_only_board
            view = body_only_board(dc_replace(view, opp_elixir=self.public.estimate_at(tick+h) if self.opp_mode else None))
        elif self.opp_mode:
            est = self.opp_estimate(tick)
            if bs.opp_elixir is not None:                    # truth read for the result's error log ONLY
                self.opp_err.append(est - bs.opp_elixir)     # (extrapolate leaves the opponent's elixir at tick)
                if self.n_dec % OPP_TRACE_EVERY == 0:
                    self.opp_trace.append([tick, round(est, 3), round(bs.opp_elixir, 3)])
            if h:                                            # the counter at tick + h, no plays in between
                from pipeline.opp_elixir_count import MAX_ELIXIR
                est = min(MAX_ELIXIR, est + self.opp_counter.regen(tick, tick + h))
            view = dc_replace(view, opp_elixir=est)
        self._blocked = []
        if self.pend:
            bs, view = self._pending_view(bs, view)
        self.n_deg += int(view.source == "degraded")
        tok, mask, sc = to_tokens(view, MAX_U)
        past = _past(self.done_plays + [(land, d["slot"], *self.ep.cell_center(d["cell"], cfg["grid"]))
                                        for land, _, d, _ in self.pend], tick + h)   # a pending play = executed at landing
        self._cur = (tick, bs, view)
        self._view_tick = tick + h
        self._obs = (tok, mask, sc, past)                    # kept for cfg["record"] (see apply())
        return tok, mask, sc, past

    def _own_effects(self, tick: int) -> list:
        """cfg["own_effects"]: my accepted plays and my side's confirmed ability presses of the last OWN_FX_TICKS."""
        abil = [dict(card=e["card"], tick=int(e["tick"]), x=0, y=0, ability=True)
                for e in getattr(self.env, "own_ability_events", ()) if e["side"] == self.side]
        pend = [dict(card=self.deck.cards[d["slot"]], tick=int(land),
                     **dict(zip("xy", self.ep.cell_to_engine(d["cell"], self.mirror, self.cfg["grid"]))))
                for land, _, d, _ in self.pend]                # cfg["pipeline_decisions"]: pending plays at their landing tick
        return [p for p in self.own_fx + abil + pend if tick - OWN_FX_TICKS <= p["tick"]]

    def _pending_raw(self, raw: dict, view_tick: int) -> dict:
        """``raw`` (the look-ahead state) plus my pending plays as the engine will show them at ``view_tick``
        (extrapolate.pending_board): full-HP deploying bodies, spell projectiles / areas."""
        from pipeline.dataset_gen import card_key
        from pipeline.extrapolate import pending_board
        plays, cid = [], {}
        for land, _, d, _ in self.pend:
            i = self.deck_index_of_slot[d["slot"]]
            name = self.engine_deck[i]
            cid[card_key(name)] = self.env.deck_ids[self.side][i]
            X, Y = self.ep.cell_to_engine(d["cell"], self.mirror, self.cfg["grid"])
            plays.append(dict(card=name, x=X, y=Y, land=land))
        bodies, shots, areas = pending_board(plays, self.side, view_tick)
        cards = {c.card_id: c for c in self.env.core.cards()}
        out = dict(raw, entities=list(raw.get("entities") or []) + [
            dict(side=self.side, x=x, y=y, name=self.env.names.get(cid[k], k), hp=cards[cid[k]].hitpoints,
                 max_hp=cards[cid[k]].hitpoints, card_id=cid[k], entity_id=eid, kind=12, status_flags=0)
            for k, x, y, eid in bodies])
        objs = raw.get("extrapolated_public_objects")
        if objs is not None and (shots or areas):
            out["extrapolated_public_objects"] = dict(projectiles=list(objs["projectiles"]) + shots,
                                                      effects=list(objs["effects"]) + areas)
        return out

    def _pending_view(self, bs, view):
        """The board a decision sees while plays are pending = as if they had executed (a pro's second-card row): hand / next
        per ``pending_hand``, my elixir minus their cost (the SIM spends at landing); the positions they free hold the next
        card, which is NOT choosable (the game still shows the pending card there)."""
        ids = list(self.deck.card_ids)
        hand, nxt, pos = pending_hand(ids, view.my_hand, view.my_next, [ids[s] for _, s, _, _ in self.done_plays],
                                      [ids[d["slot"]] for _, _, d, _ in self.pend])
        cost = sum(self.costs[ids.index(view.my_hand[i])] for i in pos)
        self._blocked = [ids.index(hand[i]) for i in pos if hand[i] in ids]
        sub = dict(my_hand=tuple(hand), my_next=nxt)
        return (dc_replace(bs, my_elixir=max(0.0, bs.my_elixir - cost), **sub),
                dc_replace(view, my_elixir=max(0.0, view.my_elixir - cost), **sub))

    def _pending_cost(self) -> float:
        return float(sum(self.costs[d["slot"]] for _, _, d, _ in self.pend))

    def opp_estimate(self, tick: int) -> float:
        """cfg["opp_elixir"]: feed the counter the ghost plays delivered at ticks <= ``tick`` not yet fed (kept per
        ``opp_play_kept``), then its estimate at ``tick``. Reads only ``env.opp_delivered``, never a state."""
        from pipeline.opp_elixir_count import card_cost
        dl = self._opp_plays()
        while self.opp_i < len(dl) and dl[self.opp_i][0] <= tick:
            t, card = dl[self.opp_i]
            self.opp_i += 1
            key = card.replace("-", "_")
            if opp_play_kept(self.opp_mode, key):
                self.opp_counter.play(t, key, card_cost(key))
                self.opp_fed += 1
            else:
                self.opp_dropped += 1
        return self.opp_counter.at(tick)

    def _opp_plays(self) -> list:
        """[(tick it went in, card slug)] the opponent-elixir counter may read: the ghost's deliveries here."""
        return self.env.opp_delivered

    def gen_row(self, policy: GenPolicy) -> dict:
        """The current prepared state as a generalist row (``GenPolicy.row``); call after ``prepare``. Kept until the
        next ``prepare`` so cfg["record"] stores the row the GenModel actually saw (``apply``)."""
        self._gen_row = policy.row(*self._obs, *policy.slot_ident(self.engine_deck, self.deck_index_of_slot))
        if getattr(policy.model, "feature_version", 1) >= 3:
            self._gen_row.update(sim_v3_features(self, policy))
        return self._gen_row

    def pre(self, hand) -> tuple[float, np.ndarray, bool]:
        """(a): el_int, allowed, stalled for the current prepared state -- shared by every decide path (live,
        sample; random/none use their own affordability rule, unchanged)."""
        cfg, policy = self.cfg, self.cfg["policy"]
        tick, bs, view = self._cur
        el_int = float(int(view.my_elixir))
        live_like = policy in ("live", "sample")
        el_afford = el_int                                    # cfg["afford_ticks"] unset: the look-ahead elixir
        if live_like and cfg.get("afford_ticks") is not None:
            el_afford = float(int(afford_elixir(self.state["players"], self.side, tick, int(cfg["afford_ticks"]))))
            if getattr(self, "pend", None):                   # cfg["pipeline_decisions"]: minus every outstanding play's cost
                el_afford = float(int(max(0.0, afford_elixir(self.state["players"], self.side, tick,
                                                              int(cfg["afford_ticks"])) - self._pending_cost())))
        if getattr(self, "_blocked", None):                   # a pending play's hand position is never choosable
            hand = np.asarray(hand, dtype=bool).copy()
            hand[self._blocked] = False
        allowed = allowed_slots(hand, self.costs, el_afford,
                                afford_mask=cfg["afford_mask"] if live_like else (not cfg["random_hand_only"]))
        stalled = anti_stall(el_int, tick, self.last_play_tick, cfg["stall_elixir"], cfg["stall_seconds"]) \
            if live_like else False
        return el_int, allowed, stalled

    def decide_row(self, model, enc, heads, p: float, hand) -> dict:
        """(a) + the per-policy decide, on ONE row's precomputed heads -- the sequential path, and ``run_batch``'s
        fallback for policies not worth batching (random, none)."""
        cfg, policy, device = self.cfg, self.cfg["policy"], self.cfg["device"]
        el_int, allowed, stalled = self.pre(hand)
        if policy == "live":
            from .decision_options import match_kwargs
            extras = match_kwargs([self])
            if extras:
                return live_decide_batch(model, enc, heads, [p], allowed[None], np.array([stalled]),
                                         tau=cfg['tau'], device=device, **extras)[0]
            return live_decide(model, enc, heads, p, allowed, tau=cfg['tau'], stalled=stalled, device=device)
        if policy == "sample":
            return sample_decide_batch(model, enc, heads, [p], allowed[None, :], np.array([stalled]), [self], cfg)[0]
        if policy == "random":
            return random_decide(self.rng_rand, allowed, cfg["p_random"])
        return {"play": False, "slot": -1, "cell": -1, "why": "none"}

    def step(self, model, enc, heads, p: float, hand) -> None:
        """sequential path: (a) + decide + (b), unchanged behaviour for every policy (run_match)."""
        self.apply(p, self.decide_row(model, enc, heads, p, hand))

    def apply(self, p: float, d: dict) -> None:
        """(b): record p_gate / traj, act on the engine, advance -- the tail of the old ``step`` (L68), unchanged."""
        env = self.env
        tick = self._record(p, d)
        if getattr(self.env, "hero_abilities", False):
            for side, commands in self._ability_commands.items():
                self.env.queue_abilities(side, commands, self.delay)
        delay = self.delay
        if self.pipe:                                         # opt-in model decisions while a play is pending
            if d["play"] and d.get("follow_ups"):
                raise ValueError("follow_ups and pipeline_decisions are separate mechanisms: use one")
            return self._apply_pipelined(p, d, tick)
        if d["play"] and d.get("follow_ups"):                 # opt-in second plays (see follow_up_spec); no key = skipped
            return self._apply_follow_ups(p, d, tick)
        if d["play"]:
            land = tick + delay                               # cfg["action_delay_ticks"]: the play enters here
            if delay:                                         # pending: board runs on, card in hand, elixir unspent,
                env._advance_to(min(land, env.tail_cap))      # no decisions (the whole wait is inside this call)
            landed = not (delay and (env.terminated or env.tick < land))   # False: match over before it landed
            self._land(p, d, land, landed)
        de = self.cfg["decide_every"]
        # after a delayed play the next decision is the first decide_every grid tick AFTER landing (delay 0: tick + de)
        env._advance_to(min((tick + de * (delay // de + 1)) if (delay and d["play"]) else env.tick + de, env.tail_cap))
        self.state = env.eng.observe()
        self.done = bool(env.terminated) or env.tick >= env.tail_cap

    def _pipe_decided(self, p: float, d: dict, tick: int) -> None:
        """The part of a pipelined decision both Match.apply and SelfPlaySide.apply share: the shared verdict has the last word on
        a SECOND play, a play joins the outstanding list, and the hazard step of the NEXT decision is set."""
        arrival = int(self.cfg.get("follow_arrival_ticks", FOLLOW_ARRIVAL_TICKS))
        self._hz_step_ticks = None
        if self.pend:
            self.pipe_n["decisions_pending"] += 1
        if d["play"] and self.pend:
            horizon = self.cfg.get("afford_ticks")
            if horizon is None:                               # the mask used the look-ahead elixir: the verdict never stricter
                horizon = self.extrap or None
            me = next(pl for pl in self.state["players"] if int(pl["side"]) == self.side)
            out = [dd["slot"] for _, _, dd, _ in self.pend]
            act, why = follow_up_verdict(
                tick=tick, due=tick, expire=tick, blocked=None, first_failed=False, slot_changed=False,
                slot_busy=d["slot"] in out, n_out=len(out),
                have=follow_up_have(me["elixir_exact"], tick, FOLLOW_AFFORD_TICKS if horizon is None else int(horizon),
                                    self._pending_cost()), cost=self.costs[d["slot"]])
            if act != "fire":                                 # the mask should make this unreachable; count it if not
                self.pipe_n[f"blocked_{why}"] += 1
                d = dict(d, play=False)
            else:
                self.pipe_n["second_plays"] += 1
        if d["play"]:
            self.pend.append((tick + self.delay, p, d, self._cur))
            self.pend.sort(key=lambda q: q[0])
            self._pipe_ready = tick + arrival
            self._hz_step_ticks = 0                           # live: the decision right after a play accrues nothing

    def _pipe_next_tick(self, tick: int) -> int:
        """The next decision tick with ``self.pend`` as it stands: on the reader-frame grid from ``tick`` (FOLLOW_FRAME_TICKS), the
        first frame after the first tap returned with fewer than FOLLOW_MAX_OUT plays outstanding; the frame on which the last
        outstanding play landed (live: its confirmation frame) never decides; nothing outstanding = the ordinary cadence."""
        fr, lands = FOLLOW_FRAME_TICKS, [q[0] for q in self.pend]
        if not lands:
            return tick + self.cfg["decide_every"]
        t = tick
        while True:
            t += fr
            left = [lt for lt in lands if lt > t]
            if left:
                if len(left) < FOLLOW_MAX_OUT and t >= self._pipe_ready:
                    return t
            elif t - max(lands) >= fr:
                return t

    def _pipe_land_until(self, t: int) -> None:
        """Ghost Match: engine to ``t``, every outstanding play landing at its OWN tick on the way (in landing order)."""
        env = self.env
        t = min(t, env.tail_cap)
        while self.pend and self.pend[0][0] <= t:
            land, p, d, cur = self.pend.pop(0)
            env._advance_to(min(land, env.tail_cap))
            self._land(p, d, land, not (env.terminated or env.tick < land), cur)
        env._advance_to(t)
        self.pending = self.pend[0] if self.pend else None      # decision_options.match_kwargs: no lethal Rocket while pending

    def _apply_pipelined(self, p: float, d: dict, tick: int) -> None:
        """Match.apply under cfg["pipeline_decisions"] (module comment above)."""
        env = self.env
        self._pipe_decided(p, d, tick)
        nt = self._pipe_next_tick(tick)
        if self.pend and self._hz_step_ticks is None:
            self._hz_step_ticks = nt - tick                   # the real ticks since this decision (live's hazard step)
        self.pending = self.pend[0] if self.pend else None
        self._pipe_land_until(nt)
        self.state = env.eng.observe()
        self.done = bool(env.terminated) or env.tick >= env.tail_cap
        if self.done and self.pend:                           # the match ended first: counted as unlanded
            while self.pend:
                land, pp, dd, cur = self.pend.pop(0)
                self._land(pp, dd, land, False, cur)
            self.pending = None

    def _apply_follow_ups(self, p: float, d: dict, tick: int) -> None:
        """Match.apply for a play that carries ``follow_ups`` (module comment above). Engine acts in time order: the first play
        at T + delay, each follow-up at its landing; its decision (affordability on the state at its own tick, the first play
        still unspent if it has not landed) is taken on the way."""
        env, delay, de = self.env, self.delay, self.cfg["decide_every"]
        arrival = int(self.cfg.get("follow_arrival_ticks", FOLLOW_ARRIVAL_TICKS))
        land_a, cost_a = tick + delay, self.costs[d["slot"]]
        st = {"a_landed": False, "a_acc": None}
        tally = getattr(self, "follow_n", None)
        if tally is None:
            tally = self.follow_n = Counter()

        def advance(t: int) -> None:                          # engine to t, the first play landing on the way
            t = min(t, env.tail_cap)
            if not st["a_landed"] and land_a <= t:
                env._advance_to(min(land_a, env.tail_cap))
                landed = not (delay and (env.terminated or env.tick < land_a))
                st["a_acc"], st["a_landed"] = self._land(p, d, land_a, landed), True
            env._advance_to(t)

        fired = []                                            # (landing tick, follow-up decision dict)
        for fu in d["follow_ups"]:
            after, within = int(fu["after_ticks"]), int(fu["within_ticks"])
            horizon = fu.get("afford_ticks")
            horizon = FOLLOW_AFFORD_TICKS if horizon is None else int(horizon)
            due, expire = tick + after, tick + after + within
            t, blocked, outcome = due, None, "late"
            while t <= expire and not (env.terminated or env.tick >= env.tail_cap):
                advance(t)
                out = [d["slot"]] if not st["a_landed"] else []   # plays decided, not landed: the first, earlier follow-ups
                out += [f["slot"] for lt, f in fired if lt > env.tick]
                me = next(pl for pl in env.eng.observe()["players"] if int(pl["side"]) == self.side)
                act, why = follow_up_verdict(
                    tick=env.tick, due=due, expire=expire, blocked=blocked,
                    first_failed=bool(fu.get("require_first", True) and st["a_landed"] and not st["a_acc"]),
                    slot_changed=not self._slot_in_hand(fu["slot"]), slot_busy=fu["slot"] in out, n_out=len(out),
                    have=follow_up_have(me["elixir_exact"], env.tick, horizon, sum(self.costs[s] for s in out)),
                    cost=self.costs[fu["slot"]])
                if act == "fire":
                    fired.append((max(land_a + max(t - tick - arrival, 0), env.tick + 1),
                                  {"play": True, "slot": fu["slot"], "cell": fu["cell"], "why": "follow_up"}))
                    outcome = None
                    break
                if act == "cancel":
                    outcome = why
                    break
                blocked = why if why != "early" else blocked      # what held it, for the cancel reason at its expiry
                outcome = blocked or "late"
                t += FOLLOW_FRAME_TICKS
            tally["fired" if outcome is None else f"cancelled_{outcome}"] += 1
        advance(land_a)                                       # the first play lands even when every follow-up was dropped
        last = land_a
        for land_b, fb in sorted(fired, key=lambda x: x[0]):
            env._advance_to(min(land_b, env.tail_cap))
            self._land(p, fb, land_b, not (env.terminated or env.tick < land_b))
            last = max(last, land_b)
        env._advance_to(min(tick + de * ((last - tick) // de + 1), env.tail_cap))
        self.state = env.eng.observe()
        self.done = bool(env.terminated) or env.tick >= env.tail_cap

    def _slot_in_hand(self, slot: int) -> bool:
        """Is deck slot ``slot``'s card in my hand right now (RoyaleSim: the core's hand; the real engine / fakes:
        ``hand_deck_indices``); True when the env cannot say (never cancels on unknown). Live twin: the reader's hand slot."""
        env, di = self.env, self.deck_index_of_slot[slot]
        core, ids = getattr(env, "core", None), getattr(env, "deck_ids", None)
        if core is not None and ids is not None:
            return ids[self.side][di] in core.state().players[self.side].hand
        me = next((pl for pl in self._fresh_players() if int(pl["side"]) == self.side), {})
        return di in me["hand_deck_indices"] if "hand_deck_indices" in me else True

    def _fresh_players(self) -> list:
        return self.env.eng.observe()["players"]

    def _record(self, p: float, d: dict) -> int:
        """(b), first half: the decision's tallies and its cfg["record"] row. -> the decision tick."""
        cfg = self.cfg
        tick, bs, view = self._cur
        self.n_dec += 1
        self.p_gates.append(p)
        if cfg.get("record") and "lp_gate" in d:              # only the sample decide dicts carry these keys
            tok, mask, sc, past = self._obs
            row = {"tok": tok, "mask": mask, "sc": sc, "past": past}
            if self._gen_row is not None:                     # GenPolicy: the generalist's input row (zeroed sc,
                row = {k: self._gen_row[k] for k in self._gen_row if k in GEN_ROW_KEYS + GEN_V3_KEYS + GEN_V31_KEYS}
            if cfg.get("record_phi"):                         # rl_royale shaping (R2): what Phi needs, own view
                from pipeline.reward_shaping import phi_record
                row = {**row, "phi_state": phi_record(self.state, self.side)}
            if cfg.get("record_tick"):                        # rl_royale gae_gamma_unit tick: the decision tick
                row = {**row, "tick": int(tick)}
            self.traj.append({**row, "allowed": d["allowed"],
                              "stalled": d["stalled"], "gate_sampled": d["gate_sampled"], "played": d["play"],
                              "slot": d["slot"], "cell": d["cell"], "lp_gate": d["lp_gate"], "lp_card": d["lp_card"],
                              "lp_cell": d["lp_cell"], "p_gate": d["p_gate"], "T": d["T"]})
        if d["why"] == "no_affordable":
            self.n_noaff += 1
        return tick

    def _land(self, p: float, d: dict, land: int, landed: bool, cur=None) -> bool:
        """(b), second half: the decided play (``self._cur``'s decision, or ``cur``'s: cfg["pipeline_decisions"] prepares later
        decisions before it lands) enters the engine at ``land`` -- or never, ``landed`` False = the match ended first. Acts,
        tallies, past / anti-stall clock. -> accepted."""
        cfg, env, ep = self.cfg, self.env, self.ep
        tick, bs, view = cur or self._cur
        grid = cfg["grid"]
        el_int = float(int(view.my_elixir))
        self.n_att += 1
        self.n_stall += int(d["why"] == "stall")
        x, y = ep.cell_center(d["cell"], grid)
        X, Y = ep.cell_to_engine(d["cell"], self.mirror, grid)
        r = env.eng.act(side=self.side, deck_index=self.deck_index_of_slot[d["slot"]], x=X, y=Y) if landed \
            else {"accepted": False}
        acc = bool(r["accepted"])
        code = int(r.get("result_code", -1))
        card = self.deck.cards[d["slot"]]
        self.mix_att[card] += 1
        rec = {"tick": tick, "slot": d["slot"], "card": card, "cell": d["cell"], "p": round(p, 4), "why": d["why"],
               "elixir": el_int, "elixir_exact": round(float(bs.my_elixir), 3), "accepted": acc}
        if self.delay:
            rec["land_tick"] = land
        if acc:
            self.n_acc += 1
            self.mix_acc[card] += 1
            self.done_plays.append((land, d["slot"], x, y))  # past: LANDING tick + position, as training's rows
            self.last_play_tick = land
            if self.own_fx is not None:                       # cfg["own_effects"]: the engine tap, landing tick
                self.own_fx.append(dict(card=card, x=X, y=Y, tick=int(land)))
        elif not landed:
            self.n_unlanded += 1
            self.refuse["match_over_before_landing"] += 1
            rec["reason"] = "match_over_before_landing"
        else:
            # RoyaleSim names its own codes (e.g. 2008 -> out_of_territory); the real engine path keeps
            # engine_play's table, which differs from PoolV1Env's _code_names at 13 and 22 (names unchanged).
            names = env._code_names if type(env).__name__ in ("RoyalePoolEnv", "RoyaleSelfPlayEnv") \
                else ep.RESULT_CODE_NAMES
            nm = names.get(code, f"native_{code}")
            if r.get("placement_valid") is False:
                nm = f"{nm}/{r.get('placement_reason')}"
            self.refuse[nm] += 1
            rec["reason"] = nm
        self.plays.append(rec)
        return acc

    def result(self) -> dict:
        env, entry, cfg, tag, k = self.env, self.entry, self.cfg, self.tag, self.k
        outcome, crowns = self._outcome()
        minutes = env.tick * TICK_S / 60.0
        end = int(env.tick)
        pg = np.asarray(self.p_gates, dtype=np.float64)
        n_att, n_acc, n_dec, n_deg, plays = self.n_att, self.n_acc, self.n_dec, self.n_deg, self.plays
        return {
            "tag": tag, "k": int(k), "slot": cfg["slot"], "port": cfg["port"], "split": entry.get("split"),
            "entry_index": cfg["entry_index"], "policy": cfg["policy"], "obs": cfg["obs"], "tau": cfg["tau"],
            "afford_mask": cfg["afford_mask"], "stall_elixir": cfg["stall_elixir"], "p_random": cfg["p_random"],
            "obs_seed": self.obs_seed_used, "side": self.side,
            "outcome": outcome, "crowns_for": int(crowns[0]), "crowns_against": int(crowns[1]),
            "end_tick": end, "seconds": round(end * TICK_S, 1), "terminated": bool(env.terminated),
            "termination_reason": (env.eng.last_episode or {}).get("termination_reason"),
            **self._opponent_fields(outcome, end),
            "plays_attempted": n_att, "plays_accepted": n_acc, "plays_refused": n_att - n_acc,
            "refuse_reasons": dict(self.refuse), "plays_per_min": round(n_att / minutes, 3) if minutes else None,
            "accepted_per_min": round(n_acc / minutes, 3) if minutes else None,
            "card_mix_attempted": dict(self.mix_att), "card_mix_accepted": dict(self.mix_acc),
            "play_elixir": [pl["elixir"] for pl in plays], "plays": plays,
            "stall_fired": self.n_stall, "no_affordable": self.n_noaff, "decisions": n_dec, "degraded_obs": n_deg,
            "degraded_equals_decisions": bool(n_deg == n_dec) if cfg["obs"] == "live" else None,
            "p_gate_mean": round(float(pg.mean()), 4) if len(pg) else None,
            "p_gate_p90": round(float(np.percentile(pg, 90)), 4) if len(pg) else None,
            "frac_gt_tau": round(float((pg > cfg["tau"]).mean()), 4) if len(pg) else None,
            "real_outcome": entry.get("real_outcome"), "s1_split": entry.get("s1_split"), "group": entry.get("group"),
            "unmapped": sorted(self.unmapped), "wall_s": round(time.perf_counter() - self.t0, 1),
            **({"traj": self._traj_arrays()} if cfg.get("record") else {}),
            **({'behaviour': env.behaviour_telemetry.result(self.side, env.eng.last_episode)}
               if cfg.get('behaviour_telemetry') else {}),
            **({'public_lookahead_counts': dict(self._public_lookahead_total)}
               if cfg.get('behaviour_telemetry') and hasattr(self, '_public_lookahead_total') else {}),
            **({"opp_counter": self._opp_summary()} if self.opp_mode else {}),
            **({"follow_ups": dict(self.follow_n)} if getattr(self, "follow_n", None) else {}),
            **({"pipeline_decisions": dict(self.pipe_n)} if self.pipe else {}),
            **({"action_delay_ticks": self.delay, "plays_unlanded": self.n_unlanded,
                "plays_refused_at_landing": n_att - n_acc - self.n_unlanded} if self.delay else {}),
            **({"extrapolate_ticks": self.extrap} if self.extrap else {}),
            **({"afford_ticks": int(cfg["afford_ticks"])} if cfg.get("afford_ticks") is not None else {}),
            **({"predict_drops": True} if self.drops is not None else {}),
            **({"own_effects": True} if self.own_fx is not None else {}),
            **({"hero_abilities": True, "ability_presses": {s: dict(c) for s, c in env.ability_presses.items()}}
               if getattr(env, "hero_abilities", False) else {}),
            **({"ability_policy": "v2", "ability_fallback_generic": dict(env.ability_fallback_generic),
                "ability_deployments": {s: dict(c) for s, c in env.ability_deployments.items()}}
               if getattr(env, "ability_policy", "generic") == "v2" else {}),
            **({"forms_mode": "deck", "form_fallbacks": [list(x) for x in env.form_fallbacks]}
               if getattr(env, "forms_mode", "base") == "deck" else {}),
        }

    def _outcome(self) -> tuple[str, tuple[int, int]]:
        return self.ep._outcome(self.env, self.state)

    def _opponent_fields(self, outcome: str, end: int) -> dict:
        """result()'s opponent block, in its key order: the ghost script and its delivery."""
        env, entry = self.env, self.entry
        last_ghost = int(entry.get("last_ghost_tick") or 0)
        after_script = end > last_ghost + SCRIPT_MARGIN_TICKS
        return {"last_ghost_tick": last_ghost, "after_script": bool(after_script),
                "won_after_script": bool(after_script and outcome == "win"),
                "ghost_plays": int(entry.get("ghost_plays") or 0), "ghost_delivered": int(env.ghost_ok),
                "ghost_refused": int(env.ghost_rejected), "ghost_undelivered": int(env.ghost_undelivered()),
                "ghost_distinct_delivered": len(env.ghost_cards_delivered),
                "ghost_refuse_reasons": dict(env.ghost_reject_reasons)}

    def _opp_summary(self) -> dict:
        """cfg["opp_elixir"]: counter bookkeeping + estimate-minus-TRUE-elixir over this match's decisions (a
        diagnostic; the truth never reaches the estimate) and a (tick, est, truth) sample every OPP_TRACE_EVERY."""
        if self.feature_version >= 4:
            observer = self.public
            counter = observer.counter if observer is not None else self.opp_counter
            return {'mode': 'public_observation_v31', 'requested_mode': self.opp_mode,
                    'fed': len(observer.plays) if observer is not None else 0,
                    'dropped': None, 'undelivered_to_counter': None,
                    'rebases': counter.rebases, 'rebase_total': round(counter.rebase_total, 3),
                    'mae': None, 'bias': None, 'n': 0, 'trace': []}
        e = np.asarray(self.opp_err, dtype=np.float64)
        c = self.opp_counter
        return {"mode": self.opp_mode, "fed": self.opp_fed, "dropped": self.opp_dropped,
                "undelivered_to_counter": len(self._opp_plays()) - self.opp_i,
                "rebases": c.rebases, "rebase_total": round(c.rebase_total, 3),
                "mae": round(float(np.abs(e).mean()), 4) if len(e) else None,
                "bias": round(float(e.mean()), 4) if len(e) else None, "n": int(len(e)), "trace": self.opp_trace}

    def _traj_arrays(self) -> dict:
        """cfg["record"]: this match's ``traj`` rows stacked into numpy arrays (rl_plan.md 3.3's per-decision
        list). Empty (0 decisions recorded -- e.g. cfg["record"] with a non-sample policy) -> empty arrays that keep
        each key's trailing shape (tok (0, 64, F), mask (0, 64), sc (0, S), past (0, PAST_K, 4), allowed (0, 8)).
        GenPolicy rows (``GEN_ROW_KEYS``) add the ``GEN_IDENT_KEYS`` as int64; their ``sc`` has the slot columns zeroed
        and ``past`` is (card, form, x, y, dt) [PAST_K, 5] -- the generalist's own input."""
        tj = self.traj
        empty = {"tok": (MAX_U, TOK_F), "mask": (MAX_U,), "sc": (SC_S,), "past": (PAST_K, 4), "allowed": (N_SLOTS,)}
        stack = (lambda k: np.stack([t[k] for t in tj])) if tj else (lambda k: np.zeros((0, *empty[k]), dtype=np.float32))
        scalar = (lambda k, dt: np.array([t[k] for t in tj], dtype=dt))
        out = {"tok": stack("tok").astype(np.float32), "mask": stack("mask").astype(bool),
                "sc": stack("sc").astype(np.float32), "past": stack("past").astype(np.float32),
                "allowed": stack("allowed").astype(bool),
                "stalled": scalar("stalled", bool), "gate_sampled": scalar("gate_sampled", bool),
                "played": scalar("played", bool), "slot": scalar("slot", np.int64), "cell": scalar("cell", np.int64),
                "lp_gate": scalar("lp_gate", np.float64), "lp_card": scalar("lp_card", np.float64),
                "lp_cell": scalar("lp_cell", np.float64), "p_gate": scalar("p_gate", np.float64),
                "T": scalar("T", np.float64)}
        if tj and "hand_card" in tj[0]:
            out.update({k: stack(k).astype(np.int64) for k in GEN_IDENT_KEYS})
        if tj and "unit_form" in tj[0]:
            out["unit_form"] = stack("unit_form").astype(np.int64)
            out["opp_past"] = stack("opp_past").astype(np.float32)
        if tj and 'opp_cycle' in tj[0]:
            for key in GEN_V31_KEYS:
                out[key] = stack(key).astype(np.float32)
        if tj and "phi_state" in tj[0]:                      # cfg["record_phi"]: reward_shaping.phi_record rows
            out["phi_state"] = stack("phi_state").astype(np.float64)
        if tj and "tick" in tj[0]:                           # cfg["record_tick"]: each row's decision tick
            out["tick"] = scalar("tick", np.int64)
        return out


def run_match(env, model, deck, entry: dict, k: int, cfg: dict) -> dict:
    version = enable_sim_features(env, model)
    if version >= 3:
        cfg = dict(cfg, feature_version=version)
    m = Match(env, deck, entry, k, cfg)
    while not m.done:
        tok, mask, sc, past = m.prepare()
        if isinstance(model, GenPolicy):
            enc, heads, p, hand = model.forward_batch([m.gen_row(model)], cfg["device"])
            p, hand = p[0], hand[0]
        else:
            enc, heads, p, hand = model_forward(model, tok, mask, sc, past, cfg["device"])
        m.step(model, enc, heads, p, hand)
    return m.result()


def model_forward_batch(model, toks, masks, scs, pasts, device: str = "cpu"):
    """``model_forward`` over a batch: one encode + heads. -> (enc, heads, p [B] floats, hand bool [B, 8])."""
    import torch
    from pipeline.model_v3 import hand_mask_from_sc
    with torch.no_grad():
        t = (lambda xs: torch.from_numpy(np.ascontiguousarray(np.stack(xs))).to(device))
        tsc = t(scs)
        hm = hand_mask_from_sc(tsc)
        enc = model.encode(t(toks), t(masks), tsc, t(pasts))
        heads = model.heads(enc, hm)
        p = torch.sigmoid(heads["gate"]).cpu().tolist()
    return enc, heads, p, hm.cpu().numpy().astype(bool)


def run_batch(make_env, model, deck, jobs, cfg: dict, n: int, on_result, on_skip=None, skip=()):
    """Up to ``n`` matches in flight, ONE model forward AND (for ``live``/``sample``) one batched decide per round
    across all of them (L68: the S1 forward is 84% of a sequential RoyaleSim match; L68e: the decide itself is now
    batched too -- ``live_decide_batch`` / ``sample_decide_batch``, one ``cell_logits`` call per round for every
    playing row, not one per match). ``jobs`` yields (entry_index, entry, k) or (entry_index, entry, k, overrides):
    ``overrides`` is a dict of per-match cfg keys (the RL actor's rollout_index / update / obs_seed) merged over
    ``cfg`` for that match only; ``on_result(line)`` gets each finished
    match's ``Match.result()``; an exception type in ``skip`` raised by reset goes to ``on_skip(entry, exc)``.
    Each row's decision depends only on its own tensors and (for ``sample``) its own ``Match.rng_behave``, so a
    match's record does not depend on its batch-mates (float noise in the shared forward/decide aside, L68)."""
    gen = isinstance(model, GenPolicy)
    if gen and cfg.get("record") and cfg["policy"] != "sample":   # only sample decisions carry log-probs, so a gen
        raise ValueError("cfg['record'] with a GenPolicy needs policy 'sample' (no other policy records a row)")
    jobs = iter(jobs)
    free = [make_env() for _ in range(n)]
    live: list[Match] = []

    def fill():
        while free:
            job = next(jobs, None)
            if job is None:
                return
            i, entry, k, *rest = job
            over = dict(rest[0]) if rest and rest[0] else {}
            env = free.pop()
            version = enable_sim_features(env, model)
            if version >= 3:
                over["feature_version"] = version
            try:
                m = Match(env, deck, entry, k, {**cfg, **over, "entry_index": i})
            except skip as exc:
                free.append(env)
                if on_skip:
                    on_skip(entry, exc)
                continue
            live.append(m)

    fill()
    while live:
        obs = [m.prepare() for m in live]
        if gen:
            enc, heads, p, hand = model.forward_batch([m.gen_row(model) for m in live], cfg["device"])
        else:
            enc, heads, p, hand = model_forward_batch(model, *zip(*obs), device=cfg["device"])
        policy = cfg["policy"]
        if policy in ("live", "sample"):
            pre = [m.pre(hand[r]) for r, m in enumerate(live)]
            allowed = np.stack([x[1] for x in pre])
            stalled = np.array([x[2] for x in pre], dtype=bool)
            from .decision_options import match_kwargs
            decisions = live_decide_batch(model, enc, heads, p, allowed, stalled, tau=cfg["tau"],
                                          device=cfg["device"], **match_kwargs(live)) if policy == "live" else \
                sample_decide_batch(model, enc, heads, p, allowed, stalled, live, cfg)
        else:                                                # random / none: cheap, no GPU call -> per-row is fine
            decisions = [m.decide_row(model, {k: v[r:r + 1] for k, v in enc.items()},
                                      {k: v[r:r + 1] for k, v in heads.items()}, p[r], hand[r])
                        for r, m in enumerate(live)]
        for r, m in enumerate(live):
            m.apply(p[r], decisions[r])
        for m in [m for m in live if m.done]:
            live.remove(m)
            free.append(m.env)
            on_result(m.result())
        fill()


# ------------------------------------------------------------------------------------------------------
# self-play (L68 T12b league): two policy-driven sides on ONE RoyaleSelfPlayEnv
# ------------------------------------------------------------------------------------------------------
ICEBOW_ENGINE_DECK = ("Tornado", "Tesla@evolution", "IceWizard", "Xbow", "Rocket", "Knight@evolution", "Log",
                      "Skeletons")                  # the pool's icebow deck (engine names, forms as the corpus has them)
_SP_DECKS: dict = {}


def selfplay_deck(names: Sequence[str]):
    """The obs-contract ``Deck`` a self-play side with engine deck ``names`` is observed under. Icebow -> icebow's own
    yaml deck (S1's slot order = the ghost path's deck). Any other deck -> ``dataset_gen.side_deck`` (placeholder card
    ids that only feed the sc slot one-hots, which ``GenPolicy.row`` decodes and zeroes) with ``config`` set to a
    per-deck path in icebow's config dir: ``live_view``'s ``mine_classes`` caches by that path and reads the card DB
    beside it. ValueError if the 8 names do not make 8 distinct cards."""
    from pipeline.dataset_gen import card_key, side_deck
    key = tuple(sorted(str(card_key(n)) for n in names))
    if key not in _SP_DECKS:
        ice = load_deck("icebow")
        if key == tuple(sorted(card_key(n) for n in ICEBOW_ENGINE_DECK)):
            _SP_DECKS[key] = ice
        else:
            d = side_deck(list(names))
            if d is None:
                raise ValueError(f"not an 8-distinct-card deck: {list(names)}")
            _SP_DECKS[key] = dc_replace(d, name="selfplay", src_dir=ice.src_dir,
                                        config=ice.config.with_name(f"_selfplay_{'+'.join(key)}.yaml"))
    return _SP_DECKS[key]


class SelfPlaySide(Match):
    """One side of a ``SelfPlayMatch``: Match's observation / decide / record / landing code for ``side`` of a shared
    RoyaleSelfPlayEnv (its own mirrored view, RNGs, past plays, anti-stall clock, live-condition state), with the env
    reset and advanced by the SelfPlayMatch. Two differences from the ghost Match. (1) cfg["action_delay_ticks"] D: a
    decided play is QUEUED (``pending``) and landed by the SelfPlayMatch at T + D while the OTHER side keeps deciding;
    this side's next decision is the first grid tick after landing, as Match.apply. (2) cfg["opp_elixir"]: the
    counter reads the OTHER side's ACCEPTED plays at their landing tick (``accepted``), never its elixir."""

    def __init__(self, env, names: Sequence[str], side: int, tag: str, k: int, cfg: dict, model=None):
        if policy_feature_version(model) >= 3:
            cfg = dict(cfg, feature_version=policy_feature_version(model))
        self._setup(env, selfplay_deck(names), k, cfg)
        self.entry, self.model = {"tag": tag}, model
        self.side, self.mirror = int(side), int(side) == 1
        self.engine_deck = list(loaded_deck_names(env, self.side, names))
        ix = {self.deck.slot_of(vocab.engine_key(n)): i for i, n in enumerate(names)}
        if sorted(ix) != list(range(N_SLOTS)):
            raise RuntimeError(f"{tag}: engine deck {list(names)} does not cover the 8 deck slots")
        self.deck_index_of_slot = ix
        cost = env.costs(self.side)
        self.costs = [float(cost[ix[s]]) for s in range(N_SLOTS)]
        self._seed(tag)
        self.accepted: list[tuple[int, str]] = []          # (landing tick, card slug) -> the other side's counter
        self.other: Optional["SelfPlaySide"] = None
        self.pending: Optional[tuple] = None                # (landing tick, p, decision)
        self._fu: Optional[dict] = None                     # the open follow-up plan of my last play (see _follow_start)
        self.fu_tasks: list = []                            # its unresolved follow-ups (SelfPlayMatch.due evaluates them)
        self.next_tick = int(env.tick)

    def _opp_plays(self) -> list:
        return self.other.accepted

    def apply(self, p: float, d: dict) -> None:
        tick = self._record(p, d)
        if getattr(self.env, "hero_abilities", False):
            for side, commands in self._ability_commands.items():
                self.env.queue_abilities(side, commands, self.delay)
        de, delay = self.cfg["decide_every"], self.delay
        if d["play"] and d.get("follow_ups"):                 # follow_up_spec second plays: the ghost Match's rules (module comment)
            if self.pipe:
                raise ValueError("follow_ups and pipeline_decisions are separate mechanisms: use one")
            if not delay:
                raise ValueError("follow_ups need cfg['action_delay_ticks'] > 0 in a SelfPlaySide")
            self._follow_start(p, d, tick)
            return
        if self.pipe:                                         # cfg["pipeline_decisions"]: plays wait in self.pend (SelfPlayMatch.due
            self._pipe_decided(p, d, tick)                    # lands them); the next decision is on the reader-frame grid
            self.next_tick = self._pipe_next_tick(tick)
            if self.pend and self._hz_step_ticks is None:
                self._hz_step_ticks = self.next_tick - tick
            return
        if d["play"] and delay:
            self.pending = (tick + delay, p, d)
            self.next_tick = tick + de * (delay // de + 1)
            return
        if d["play"]:
            self._land(p, d, tick, True)
        self.next_tick = tick + de

    # ---- follow_ups (the ghost Match._apply_follow_ups' rules, event-driven: SelfPlayMatch.due calls _follow_check) ----------------
    def _fresh_players(self) -> list:
        return self.env.raw()["players"]

    def _follow_start(self, p: float, d: dict, tick: int) -> None:
        """The first play lands at tick + delay (SelfPlayMatch.due); each follow-up is evaluated by _follow_check on the reader-frame
        grid from the first frame at or after its due tick AND after the first tap returned; my next decision is only taken once all
        of them are resolved and landed (the first grid tick after the last landing, as Match.apply)."""
        arrival = int(self.cfg.get("follow_arrival_ticks", FOLLOW_ARRIVAL_TICKS))
        grid = lambda x: tick + -(-(x - tick) // FOLLOW_FRAME_TICKS) * FOLLOW_FRAME_TICKS      # noqa: E731
        land_a = tick + self.delay
        self.pend.append((land_a, p, d, self._cur))
        self.pend.sort(key=lambda q: q[0])
        self._fu = dict(tick=tick, land_a=land_a, d=d, arrival=arrival, a_landed=False, a_acc=None, last=land_a, p=p,
                        cur=self._cur)
        self.fu_tasks = [dict(fu=fu, due=tick + int(fu["after_ticks"]),
                              expire=tick + int(fu["after_ticks"]) + int(fu["within_ticks"]), blocked=None,
                              next_check=grid(max(tick + int(fu["after_ticks"]), tick + arrival)))
                         for fu in d["follow_ups"]]
        self.next_tick = 10 ** 9                              # no decision until every follow-up is resolved (_follow_resolved)
        if getattr(self, "follow_n", None) is None:
            self.follow_n = Counter()

    def _follow_check(self, t: int) -> None:
        """Evaluate every follow-up whose check tick is ``t`` (the engine is at t, everything due has landed): the shared verdict on
        the CURRENT state, waiting re-checks 2 ticks later until its window closes."""
        env, fu0 = self.env, self._fu
        for task in list(self.fu_tasks):
            if task["next_check"] > t:
                continue
            fu = task["fu"]
            horizon = fu.get("afford_ticks")
            horizon = FOLLOW_AFFORD_TICKS if horizon is None else int(horizon)
            out = [dd["slot"] for _, _, dd, _ in self.pend]
            me = next(pl for pl in self._fresh_players() if int(pl["side"]) == self.side)
            act, why = follow_up_verdict(
                tick=t, due=task["due"], expire=task["expire"], blocked=task["blocked"],
                first_failed=bool(fu.get("require_first", True) and fu0["a_landed"] and not fu0["a_acc"]),
                slot_changed=not self._slot_in_hand(fu["slot"]), slot_busy=fu["slot"] in out, n_out=len(out),
                have=follow_up_have(me["elixir_exact"], t, horizon, sum(self.costs[x] for x in out)),
                cost=self.costs[fu["slot"]])
            if act == "wait":
                task["blocked"] = why if why != "early" else task["blocked"]
                task["next_check"] = t + FOLLOW_FRAME_TICKS
                if task["next_check"] > task["expire"]:       # the window closed while waiting: never fired late
                    act, why = "cancel", task["blocked"] or "late"
                else:
                    continue
            self.fu_tasks.remove(task)
            if act == "fire":
                land_b = max(fu0["land_a"] + max(t - fu0["tick"] - fu0["arrival"], 0), t + 1)
                self.pend.append((land_b, fu0["p"], {"play": True, "slot": fu["slot"], "cell": fu["cell"], "why": "follow_up"},
                                  fu0["cur"]))
                self.pend.sort(key=lambda q: q[0])
                fu0["last"] = max(fu0["last"], land_b)
                self.follow_n["fired"] += 1
            else:
                self.follow_n[f"cancelled_{why}"] += 1
        self._follow_resolved()

    def _follow_resolved(self) -> None:
        if self._fu is not None and not self.fu_tasks:
            f = self._fu
            self._fu = None
            self.next_tick = f["tick"] + self.cfg["decide_every"] * ((f["last"] - f["tick"]) // self.cfg["decide_every"] + 1)

    def _land(self, p: float, d: dict, land: int, landed: bool, cur=None) -> bool:
        from pipeline.dataset_gen import card_key
        acc = super()._land(p, d, land, landed, cur)
        fu0 = getattr(self, "_fu", None)
        if fu0 is not None and d is fu0["d"]:                 # the first play of an open follow-up plan landed (or was refused)
            fu0["a_landed"], fu0["a_acc"] = True, acc
        if acc:
            self.accepted.append((int(land), str(card_key(self.engine_deck[self.deck_index_of_slot[d["slot"]]]))))
        return acc

    def _outcome(self) -> tuple[str, tuple[int, int]]:
        return self.env.outcome(self.side)

    def _opponent_fields(self, outcome: str, end: int) -> dict:
        """The ghost block's keys filled with the OTHER side's plays (no script to outlive), so rl_royale's monitors
        read a self-play record unchanged: delivered = accepted, refused = refused at landing, undelivered = unlanded."""
        o = self.other
        return {"last_ghost_tick": 0, "after_script": False, "won_after_script": False, "ghost_plays": o.n_att,
                "ghost_delivered": o.n_acc, "ghost_refused": o.n_att - o.n_acc - o.n_unlanded,
                "ghost_undelivered": o.n_unlanded, "ghost_distinct_delivered": len(o.mix_acc),
                "ghost_refuse_reasons": dict(o.refuse)}


class SelfPlayMatch:
    """One self-play match (L68 T12b): ``env.reset`` with spec's decks and deal seed, the learner on
    spec["learner_side"] under ``cfg`` and the frozen opponent on the other side under ``opp_cfg``. ``due()`` advances
    the env to the next tick at which a side decides, landing queued delayed plays on the way (side 0 first when two
    land on one tick), and returns the deciding sides ([] = over; plays still queued then count as unlanded).
    ``result()`` = the learner side's record + ``league`` (the spec) + ``opp_side`` (the opponent's play counts)."""

    def __init__(self, env, spec: dict, k: int, cfg: dict, opp_cfg: dict, learner=None, opponent=None):
        self.env, self.spec = env, spec
        L = int(spec["learner_side"])
        decks = {L: spec["learner_deck"], 1 - L: spec["opp_deck"]}
        enable_sim_features(env, learner, opponent)
        env.reset(decks[0], decks[1], int(spec["seed"]))
        tag = str(spec["tag"])
        self.learner = SelfPlaySide(env, spec["learner_deck"], L, tag, k, cfg, learner)
        self.opp = SelfPlaySide(env, spec["opp_deck"], 1 - L, f"{tag}:opp", k, opp_cfg, opponent)
        self.learner.other, self.opp.other = self.opp, self.learner
        self.sides = sorted((self.learner, self.opp), key=lambda s: s.side)

    def due(self) -> list[SelfPlaySide]:
        env = self.env
        while True:
            t = int(env.tick)
            for s in self.sides:
                if s.pending and s.pending[0] <= t and not env.terminated:
                    (land, p, d), s.pending = s.pending, None
                    s._land(p, d, land, True)
                while s.pend and s.pend[0][0] <= t and not env.terminated:     # pipeline_decisions: each at its OWN tick
                    land, p, d, cur = s.pend.pop(0)
                    s._land(p, d, land, True, cur)
                    s._pipe_last_land = land
            for s in self.sides:
                if s.fu_tasks and not env.terminated:                          # follow_ups: the shared verdict at its check tick
                    s._follow_check(t)
            if env.done:
                for s in self.sides:
                    s.fu_tasks = []
                    if s.pending:
                        (land, p, d), s.pending = s.pending, None
                        s._land(p, d, land, False)
                    while s.pend:
                        land, p, d, cur = s.pend.pop(0)
                        s._land(p, d, land, False, cur)
                return []
            ds = [s for s in self.sides if s.next_tick <= t]
            if ds:
                raw = env.raw()
                for s in ds:
                    s.state = raw
                return ds
            nxt = min([s.next_tick for s in self.sides] + [s.pending[0] for s in self.sides if s.pending]
                      + [s.pend[0][0] for s in self.sides if s.pend]
                      + [task["next_check"] for s in self.sides for task in s.fu_tasks])
            env._advance_to(min(nxt, env.tail_cap))

    def result(self) -> dict:
        r = self.learner.result()
        o, minutes = self.opp, self.env.tick * TICK_S / 60.0
        r["league"] = dict(self.spec)
        r["opp_side"] = {"side": o.side, "policy": o.cfg["policy"], "plays_attempted": o.n_att,
                         "plays_accepted": o.n_acc, "plays_per_min": round(o.n_att / minutes, 3) if minutes else None,
                         "stall_fired": o.n_stall, "decisions": o.n_dec}
        return r


def run_selfplay_batch(make_env, learner, opponents: dict, jobs, cfg: dict, n: int, on_result, on_skip=None, skip=()):
    """``run_batch`` for self-play (L68 T12b). Up to ``n`` ``SelfPlayMatch``es in flight; each round prepares EVERY side
    that decides now across them (all before any acts: a play made this tick is invisible to this tick's decisions,
    board and counter alike), then ONE forward + one batched decide PER POLICY -- the learner, and each distinct frozen
    opponent in flight -- then applies. ``learner`` plays under ``cfg`` (the rollout cfg: policy sample, record);
    ``opponents`` maps spec["opp"]["id"] -> (policy, the cfg its side plays under: live or sample, NEVER record --
    only the learner's side is recorded). Nothing here changes any weights. ``jobs``: (i, spec, g[, overrides]) as
    run_batch's; the overrides (rollout_index / update / obs_seed) go to the learner's side, rollout_index / update also
    to the opponent's (whose tag, hence obs and behaviour seeds, is ``<tag>:opp``)."""
    for c in [cfg] + [oc for _, oc in opponents.values()]:
        if c["policy"] not in ("live", "sample"):
            raise ValueError(f"self-play policies are live or sample, not {c['policy']!r}")
    if any(oc.get("record") for _, oc in opponents.values()):
        raise ValueError("a frozen opponent's side is never recorded")
    if cfg.get("record") and cfg["policy"] != "sample":
        raise ValueError("cfg['record'] needs policy 'sample' (no other policy records a row)")
    jobs = iter(jobs)
    free = [make_env() for _ in range(n)]
    live: list[SelfPlayMatch] = []

    def fill():
        while free:
            job = next(jobs, None)
            if job is None:
                return
            i, spec, k, *rest = job
            over = dict(rest[0]) if rest and rest[0] else {}
            opp, ocfg = opponents[spec["opp"]["id"]]
            env = free.pop()
            try:
                m = SelfPlayMatch(env, spec, k, {**cfg, **over, "entry_index": i},
                                  {**ocfg, **{x: v for x, v in over.items() if x != "obs_seed"}, "entry_index": i},
                                  learner, opp)
            except skip as exc:
                free.append(env)
                if on_skip:
                    on_skip(spec, exc)
                continue
            live.append(m)

    fill()
    while live:
        due: list[SelfPlaySide] = []
        for m in list(live):
            ds = m.due()
            if ds:
                due += ds
            else:
                live.remove(m)
                free.append(m.env)
                on_result(m.result())
        fill()
        for s in due:
            s.prepare()
        groups: dict = {}
        for s in due:
            groups.setdefault(id(s.model), []).append(s)
        todo = []
        for sides in groups.values():
            model, c = sides[0].model, sides[0].cfg
            if isinstance(model, GenPolicy):
                enc, heads, p, hand = model.forward_batch([s.gen_row(model) for s in sides], c["device"])
            else:
                enc, heads, p, hand = model_forward_batch(model, *zip(*[s._obs for s in sides]), device=c["device"])
            pre = [s.pre(hand[r]) for r, s in enumerate(sides)]
            allowed = np.stack([x[1] for x in pre])
            stalled = np.array([x[2] for x in pre], dtype=bool)
            from .decision_options import match_kwargs
            decisions = live_decide_batch(model, enc, heads, p, allowed, stalled, tau=c["tau"], device=c["device"],
                                          **match_kwargs(sides)) \
                if c["policy"] == "live" else sample_decide_batch(model, enc, heads, p, allowed, stalled, sides, c)
            todo += [(s, p[r], decisions[r]) for r, s in enumerate(sides)]
        for s, pr, d in todo:
            s.apply(pr, d)


def run_liveness(env, entry: dict, cfg: dict) -> dict:
    """The caller's own path (design 5.5): ``PoolV1Env(port).reset(entry)`` + 10 ticks + observe()."""
    t0 = time.perf_counter()
    env.reset(entry)
    tick_reset = int(env.tick)
    env._advance_to(tick_reset + 10)
    st = env.eng.observe()
    return {"tag": entry["tag"], "k": 0, "slot": cfg["slot"], "port": cfg["port"], "mode": "liveness",
            "tick_after_reset": tick_reset, "tick": int(st.get("tick", -1)), "towers": len(env._tower_keys),
            "opening_hash_match": env.opening_hash == entry.get("opening_state_hash"), "ok": tick_reset >= 90,
            "wall_s": round(time.perf_counter() - t0, 2)}


def run_parity(env, entry: dict, cfg: dict) -> dict:
    """Drive both sides' recorded commands to the corpus final tick; compare the state hash (design 6.2)."""
    t0 = time.perf_counter()
    env.reset(entry)
    cf = entry["corpus_final"]
    env._advance_to(min(int(cf["tick"]), env.tail_cap))
    st = env.eng.observe()
    last = env.eng.last_episode or env.episode or (st.get("episode") or {})
    pos = [c for c in list(entry["ghost_commands"]) + list(ours(entry, "commands")) if not c.get("ability")]
    return {
        "tag": entry["tag"], "k": 0, "slot": cfg["slot"], "port": cfg["port"], "split": entry.get("split"),
        "entry_index": cfg["entry_index"], "mode": "parity", "retry_codes": list(env.retry_codes),
        "hash_match": st.get("state_hash") == cf.get("state_hash"),
        "engine_hash": st.get("state_hash"), "corpus_hash": cf.get("state_hash"),
        "opening_hash_match": env.opening_hash == entry.get("opening_state_hash"),
        "end_tick": int(env.tick), "corpus_tick": cf.get("tick"), "terminated": bool(env.terminated),
        "corpus_terminated": cf.get("terminated"), "winner": last.get("winner"), "corpus_winner": cf.get("winner"),
        "crowns": last.get("crowns"), "corpus_crowns": cf.get("crowns"),
        "our_cmd_ok": env.our_cmd_ok, "our_cmd_refused": env.our_cmd_refused, "our_cmd_reasons": env.our_cmd_reasons,
        "our_corpus_accepted": sum(1 for c in ours(entry, "commands") if c.get("corpus_accepted")),
        "ghost_ok": env.ghost_ok, "ghost_refused": env.ghost_rejected,
        "ghost_corpus_accepted": sum(1 for c in entry["ghost_commands"] if c.get("corpus_accepted")),
        "min_command_tick": min([int(c["tick"]) for c in pos] or [0]),
        "corpus_rejected_by_reason": (entry.get("corpus_grade") or {}).get("rejected_by_reason"),
        "corpus_elixir_delays_n": (entry.get("corpus_grade") or {}).get("elixir_delays_n"),
        "wall_s": round(time.perf_counter() - t0, 1),
    }


# ------------------------------------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--port", type=int, required=True, help="engine direct door: 38031 or 38032 (any int for royale)")
    ap.add_argument("--engine", choices=("real", "royale"), default="real",
                    help="royale = RoyaleSim via pipeline/royale_env.py (Royale stack venv); entries whose decks it "
                         "cannot load are skipped and counted, not errors")
    ap.add_argument("--subs", default="", help="royale only: card substitutions, e.g. Tornado=Arrows")
    ap.add_argument("--batch", type=int, default=1, help="royale + eval only: matches in flight sharing one model "
                    "forward per round (run_batch; identical records to --batch 1, measured 58/58 in L68)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--ckpt", type=Path, default=None, help="required for --mode eval")
    ap.add_argument("--pool", type=Path, default=POOL_V1)
    ap.add_argument("--split-file", type=Path, default=None, help="default: <pool stem>_split.json beside the pool")
    ap.add_argument("--split", choices=("heldout", "train"), default="heldout")
    ap.add_argument("--entries", default="all", help="a:b over the split's entries in pool order, 'all', or a tags file")
    ap.add_argument("--seeds", default="0", help="comma list of eval seeds k")
    ap.add_argument("--shard", default="0/1", help="i/n: round-robin share of the (entry, k) tasks")
    ap.add_argument("--policy", choices=("live", "none", "random", "sample"), default="live")
    from .decision_options import add_arguments
    add_arguments(ap)
    ap.add_argument("--p-random", type=float, default=0.09)
    ap.add_argument("--random-hand-only", action="store_true", help="random control over hand slots, no affordability")
    ap.add_argument("--sample-T", type=float, default=0.5, help="--policy sample: softmax/Bernoulli temperature "
                    "(cfg['record'] / cfg['rollout_index'] / cfg['update'] are for the RL actor, not this CLI: "
                    "a 'traj' record is numpy, not JSON, so it cannot go through this process's matches.jsonl)")
    ap.add_argument("--mode", choices=("eval", "parity", "liveness"), default="eval",
                    help="liveness = reset the FIRST selected entry + 10 ticks on this port, one line, exit")
    ap.add_argument("--parity-retry", choices=("corpus", "env"), default="corpus",
                    help="corpus = replay_drive's retry set (1050 only); env = EngineMatchEnv's (13, 1050)")
    ap.add_argument("--tau", type=float, default=TAU_LIVE)
    ap.add_argument("--no-afford-mask", action="store_true")
    ap.add_argument("--stall-elixir", default=str(STALL_ELIXIR_LIVE), help="'none' disables anti-stall")
    ap.add_argument("--stall-seconds", type=float, default=STALL_SECONDS_LIVE)
    ap.add_argument("--obs", choices=("live", "clean"), default="live")
    ap.add_argument("--noise-off", default="", help="comma list of live-view noise components to switch OFF "
                    f"(no effect on --obs clean): {','.join(NOISE_NAMES)} (plus alias 'scalars' = "
                    f"{','.join(NOISE_ALIASES['scalars'])})")
    ap.add_argument("--opp-elixir", choices=OPP_ELIXIR_MODES, default=None,
                    help="opponent elixir from the public-events counter fed the ghost's delivered plays (cfg "
                         "'opp_elixir'; counter = the memory-reader equivalent); default: the view's own")
    ap.add_argument("--action-delay", type=int, default=0,
                    help="live tap->land lag in engine ticks: a play decided at T lands at T + D (cfg "
                         "'action_delay_ticks'; the live condition is 26)")
    ap.add_argument("--extrapolate", type=int, default=0,
                    help="each decision sees the raw board advanced H ticks (cfg 'extrapolate_ticks'; 26 with the "
                         "live condition's delay)")
    ap.add_argument("--predict-drops", action="store_true",
                    help="with --extrapolate: add the 7 skeletons of an observed Skeleton Barrel balloon death 12 ticks "
                         "after it (cfg 'predict_drops'); default off = unchanged")
    ap.add_argument("--own-effects", action="store_true",
                    help="W1, with --extrapolate: the look-ahead applies my own recent Log / Tornado / Rocket / hero IW "
                         "freeze to the enemy bodies they reach (cfg 'own_effects'); default off = unchanged")
    ap.add_argument("--decide-every", type=int, default=DECIDE_EVERY)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--resume", action="store_true", help="continue an interrupted run dir (skips done (tag, k))")
    ap.add_argument("--max-matches", type=int, default=0, help="stop after this many new matches (smoke)")
    return ap


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    refuse_existing_out(a.out, a.resume)                 # FIRST: nothing is loaded or connected before this check
    from .decision_options import config_from_args, options_from_config
    decision_cfg = config_from_args(a)
    decision_active = options_from_config(decision_cfg).active
    if decision_active and a.policy != 'live':
        raise ValueError('decision options require --policy live')
    if a.mode == "eval" and a.ckpt is None:
        raise SystemExit("--mode eval needs --ckpt")
    shard = parse_shard(a.shard)
    seeds = [0] if a.mode in ("parity", "liveness") else parse_seeds(a.seeds)
    noise = parse_noise_off(a.noise_off)                  # validated up front, same as shard/seeds above
    noise_off = noise_off_names(noise)
    stall_elixir = None if str(a.stall_elixir).lower() == "none" else float(a.stall_elixir)
    if a.action_delay < 0 or a.extrapolate < 0:
        raise SystemExit(f"--action-delay {a.action_delay} / --extrapolate {a.extrapolate} must be >= 0")
    import torch
    torch.set_num_threads(max(1, int(a.threads)))

    pool_path = Path(a.pool)
    split_path = Path(a.split_file) if a.split_file else pool_path.with_name(pool_path.stem + "_split.json")
    frozen = json.loads(split_path.read_text(encoding="utf-8"))
    pool_sha = sha256_file(pool_path)
    if pool_sha != frozen["pool_sha256"]:
        raise SystemExit(f"REFUSING: pool sha256 {pool_sha} != frozen split's {frozen['pool_sha256']}")
    rows = load_pool_v1(pool_path)
    bad = [r["tag"] for r in rows if frozen["tags"].get(r["tag"], {}).get("split") != r["split"]]
    if bad:
        raise SystemExit(f"REFUSING: {len(bad)} pool rows disagree with the frozen split, e.g. {bad[:3]}")
    entries = select_split(rows, a.split)
    del rows
    idx = parse_entries(a.entries, entries)
    tasks = [(idx[0], 0)] if a.mode == "liveness" else make_tasks(idx, seeds, shard)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    done_keys: set = set()
    mpath = out / "matches.jsonl"
    if a.resume and mpath.exists():
        for line in mpath.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done_keys.add((r["tag"], int(r["k"])))
    slot = SLOT_OF_PORT.get(int(a.port), int(a.port))
    run = {"argv": sys.argv[1:] if argv is None else list(argv),
           "args": {k: str(v) for k, v in vars(a).items() if decision_active or k not in decision_cfg},
           "slot": slot, "pool_sha256": pool_sha, "split_sha256": sha256_file(split_path),
           "n_split_entries": len(entries), "n_tasks": len(tasks), "resumed_done": len(done_keys),
           "noise_off": noise_off, "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    deck = load_deck("icebow")
    model, minfo = None, {}
    if a.mode == "eval":
        run["ckpt_sha256"] = sha256_file(a.ckpt)
        model, minfo = load_policy(a.ckpt, a.device)
        run["model"] = minfo
    (out / (f"run_resume_{int(time.time())}.json" if a.resume else "run.json")).write_text(
        json.dumps(run, indent=1, default=str), encoding="utf-8")
    cfg = {"policy": a.policy, "tau": float(a.tau), "afford_mask": not a.no_afford_mask, "stall_elixir": stall_elixir,
           "stall_seconds": float(a.stall_seconds), "obs": a.obs, "noise": noise, "p_random": float(a.p_random),
           "random_hand_only": bool(a.random_hand_only), "grid": minfo.get("grid", "floor"), "device": a.device,
           "decide_every": int(a.decide_every), "slot": slot, "port": int(a.port), "T": float(a.sample_T),
           "opp_elixir": a.opp_elixir, "action_delay_ticks": int(a.action_delay), "extrapolate_ticks": int(a.extrapolate)}
    if a.predict_drops:
        if not a.extrapolate:
            raise SystemExit("--predict-drops needs --extrapolate > 0 (the skeletons go into the look-ahead board)")
        cfg["predict_drops"] = True
    if a.own_effects:
        if not a.extrapolate:
            raise SystemExit("--own-effects needs --extrapolate > 0 (the effects act on the look-ahead board)")
        cfg["own_effects"] = True
    if decision_active:
        cfg.update(decision_cfg)
    print(json.dumps({"e1_eval": a.mode, "policy": a.policy, "port": a.port, "tasks": len(tasks),
                      "already_done": len(done_keys), "grid": cfg["grid"], "tau": cfg["tau"],
                      "noise_off": noise_off, "opp_elixir": a.opp_elixir, "action_delay_ticks": a.action_delay,
                      "extrapolate_ticks": a.extrapolate}), flush=True)

    new = 0
    results: list[dict] = []
    env = None
    unsupported = UnsupportedDeck = ()
    try:
        if a.engine == "royale":
            from pipeline.royale_env import RoyalePoolEnv, UnsupportedDeck
            subs = dict(s.split("=", 1) for s in a.subs.split(",") if s)
            env = RoyalePoolEnv(decision_ticks=int(a.decide_every), subs=subs)
            unsupported = []
        else:
            from pipeline.e1_pool import PoolV1Env
            env = PoolV1Env(port=int(a.port), host=a.host, decision_ticks=int(a.decide_every),
                            drive_our_commands=(a.mode == "parity"),
                            retry_codes=((1050,) if (a.mode == "parity" and a.parity_retry == "corpus") else (13, 1050)))
        batched = a.engine == "royale" and a.mode == "eval" and a.batch > 1
        if batched:
            def emit(line):
                nonlocal new
                with mpath.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(line) + "\n")
                results.append(line)
                new += 1
                print(f"[e1_eval] {new}/{len(tasks)} {line['tag']} k={line['k']} {line['outcome']} "
                      f"{line['crowns_for']}-{line['crowns_against']} {line['seconds']}s plays {line['plays_accepted']}/"
                      f"{line['plays_attempted']}", flush=True)
            jobs = [(i, entries[i], k) for (i, k) in tasks if (entries[i]["tag"], k) not in done_keys]
            if a.max_matches:
                jobs = jobs[:a.max_matches]
            run_batch(lambda: RoyalePoolEnv(decision_ticks=int(a.decide_every), subs=subs), model, deck, jobs, cfg,
                      a.batch, on_result=emit, skip=(UnsupportedDeck,),
                      on_skip=lambda e, exc: unsupported.append({"tag": e["tag"], "why": str(exc)}))
        for (i, k) in ([] if batched else tasks):
            entry = entries[i]
            if (entry["tag"], k) in done_keys:
                continue
            cfg["entry_index"] = i
            try:
                if a.mode == "liveness":
                    line = run_liveness(env, entry, cfg)
                elif a.mode == "parity":
                    line = run_parity(env, entry, cfg)
                else:
                    line = run_match(env, model, deck, entry, k, cfg)
            except UnsupportedDeck as exc:
                unsupported.append({"tag": entry["tag"], "why": str(exc)})
                continue
            except Exception as exc:                        # engine / socket / timeout: record and stop this slot
                with (out / "errors.jsonl").open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"tag": entry["tag"], "k": k, "entry_index": i, "port": a.port,
                                         "error": repr(exc)[:2000], "time": time.strftime("%Y-%m-%d %H:%M:%S")}) + "\n")
                print(f"[e1_eval] ERROR on {entry['tag']} k={k}: {exc!r}", flush=True)
                return 3
            with mpath.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(line) + "\n")
            results.append(line)
            new += 1
            if a.mode == "liveness":
                print(json.dumps({"LIVENESS": line}), flush=True)
            elif a.mode == "parity":
                print(f"[e1_eval] parity {new}/{len(tasks)} {entry['tag']} hash_match={line['hash_match']} "
                      f"tick {line['end_tick']}/{line['corpus_tick']} {line['wall_s']}s", flush=True)
            else:
                print(f"[e1_eval] {new}/{len(tasks)} {entry['tag']} k={k} {line['outcome']} "
                      f"{line['crowns_for']}-{line['crowns_against']} {line['seconds']}s plays {line['plays_accepted']}/"
                      f"{line['plays_attempted']} wall {line['wall_s']}s", flush=True)
            if a.max_matches and new >= a.max_matches:
                break
    finally:
        if env is not None:
            env.close()
    if a.engine == "royale":
        (out / "unsupported.json").write_text(json.dumps(unsupported, indent=1), encoding="utf-8")
    summ = {"new_matches": new, "finished": time.strftime("%Y-%m-%d %H:%M:%S"),
            "engine": a.engine, "skipped_unsupported": len(unsupported) if a.engine == "royale" else 0,
            "wall_s_mean": round(float(np.mean([r["wall_s"] for r in results])), 1) if results else None}
    if a.mode == "liveness":
        summ["ok"] = bool(results and results[0]["ok"])
    elif a.mode == "parity":
        summ["hash_match"] = sum(1 for r in results if r["hash_match"])
    else:
        summ.update({o: sum(1 for r in results if r["outcome"] == o) for o in ("win", "draw", "loss")})
    (out / f"done_{int(time.time())}.json").write_text(json.dumps(summ, indent=1), encoding="utf-8")
    print(json.dumps({"DONE": summ}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
