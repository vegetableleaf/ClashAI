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
# Match and SelfPlaySide both support it; each side owns its pending state.


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
    if "hazard" in heads and "gate" not in heads:              # P2 timing head: p is h_s, never a gate to threshold
        raise ValueError("a timing-head model has no gate: run its seat with policy sample (timing_decide_batch)")
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


ABILITY_FEAT_N = 44   # = royale_env.ABILITY_FEAT_N (royalegym-free copy; pipeline/tests/test_ability_head.py checks it)
ABILITY_FEAT_SETS = {"base": ABILITY_FEAT_N, "freeze": ABILITY_FEAT_N + 11}   # + royale_env.FREEZE_FEAT_N (test checks)


def ability_defaults(n_feat: int = ABILITY_FEAT_N) -> dict:
    """The per-decision ability record of a row with no ability decision (cfg["ability"] on; ``n_feat`` = the head's
    feature count, cfg["ability"]["n_feat"])."""
    return {"ab_sampled": False, "ab_press": False, "ab_lp": 0.0, "ab_feat": np.zeros(n_feat, np.float32),
            "ab_cand": False, "ab_q": 0.0}


def ability_decide(matches: Sequence, enc, cfg: dict) -> Optional[list]:
    """rl_royale ``ability_head`` (B6 stage A; ``cfg["ability"]`` = {mode, head}; absent -> None, nothing touched). A
    match whose ``prepare`` found pressable buttons of its side (``_ability_opts``, ``RoyalePoolEnv.ability_options``)
    makes ONE decision on one of them (``n_dec`` mod their count): mode ``sample`` = Bernoulli(sigmoid(head(g[r], feat)))
    from the match's own ``rng_ability`` (its gate / card / cell draws untouched), ``greedy`` = p > 0.5; a press puts the
    option's command in ``_ability_commands[side]``, which ``apply`` queues through the rule's own press path. ``label``
    (no head: the rule pressed) only records the option's features + the rule's q. -> per row the ``ability_defaults``
    keys (record), filled where a decision / label was made."""
    ab = cfg.get("ability")
    if not ab:
        return None
    import torch
    out = [ability_defaults(int(ab.get("n_feat", ABILITY_FEAT_N))) for _ in matches]
    rows = [r for r, m in enumerate(matches) if getattr(m, "_ability_opts", None)]
    pick = {r: matches[r]._ability_opts[matches[r].n_dec % len(matches[r]._ability_opts)] for r in rows}
    for m in matches:
        m._ability_opts = None
    if ab["mode"] == "label":
        for r in rows:
            out[r].update(ab_cand=True, ab_feat=np.asarray(pick[r]["feat"], np.float32), ab_q=float(pick[r]["q"]))
        return out
    if not rows:
        return out
    g = enc["g"]
    with torch.no_grad():
        feat = torch.as_tensor(np.array([pick[r]["feat"] for r in rows], np.float32), device=g.device)
        z = ab["head"](g[torch.as_tensor(rows, device=g.device)], feat).double().cpu().numpy()
    for j, r in enumerate(rows):
        m, o = matches[r], pick[r]
        lp1, lp0 = -float(np.logaddexp(0.0, -z[j])), -float(np.logaddexp(0.0, z[j]))   # log p, log (1 - p)
        if ab["mode"] == "sample":
            if getattr(m, "rng_ability", None) is None:
                m.rng_ability = np.random.default_rng(behave_seed(f"{m.tag}:ability", int(m.cfg.get("rollout_index", 0)),
                                                                  int(m.cfg.get("update", 0))))
            press = bool(m.rng_ability.random() < math.exp(lp1))
        else:
            press = lp1 > lp0
        if press:
            m._ability_commands[m.side] = [o["cmd"]]
        s = m.__dict__.setdefault("ab_stats", {"decisions": 0, "presses": 0, "p_sum": 0.0})
        s["decisions"] += 1
        s["presses"] += int(press)
        s["p_sum"] += math.exp(lp1)
        out[r].update(ab_sampled=True, ab_press=press, ab_lp=lp1 if press else lp0,
                      ab_feat=np.asarray(o["feat"], np.float32))
    return out


def live_decide_batch(model, enc, heads, p, allowed: np.ndarray, stalled: np.ndarray, *, tau: float,
                       device: str = "cpu", decision_options=None, rngs=None, card_names=None, **context) -> list[dict]:
    """``live_decide`` over every row of a shared forward at once. The card argmax and the p-vs-tau compare are
    elementwise (bit-identical to a per-row loop); ONE ``cell_logits`` call covers every row that plays, so this
    is O(1) GPU calls per round, not O(matches) (L68e)."""
    import torch
    if "hazard" in heads and "gate" not in heads:              # P2 timing head: p is h_s, never a gate to threshold
        raise ValueError("a timing-head model has no gate: run its seat with policy sample (timing_decide_batch)")
    if decision_options is not None and decision_options.active:
        from .decision_options import decide_batch
        return decide_batch(model, enc, heads, p, allowed, stalled, tau=tau, device=device,
                            options=decision_options, rngs=rngs or [None] * len(allowed), card_names=card_names,
                            **context)
    B = allowed.shape[0]
    p = np.asarray(p, dtype=np.float64)
    tau_r = np.broadcast_to(np.asarray(tau, dtype=np.float64), (B,))   # rl_royale C1 posture: per-row tau (posture_live)
    any_allowed = allowed.any(axis=1)
    out: list[Optional[dict]] = [None] * B
    with torch.no_grad():
        logits = heads["card"].clone()
        logits = logits.masked_fill(~torch.from_numpy(allowed).to(logits.device), float("-inf"))
        slot = logits.argmax(dim=-1).cpu().numpy()
        play = any_allowed & ((p > tau_r) | stalled)
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
                      "why": "stall" if p[r] <= tau_r[r] else "gate"}
    return out


def ctx_row(state: dict, side: int, tick: int, seen: set) -> list[int]:
    """``Match._ctx_row``'s body, pure on its inputs (shared with live_gen_v2's posture): ``state`` = an engine
    ``observe()``-shaped dict (entities with side / name; episode.crown_towers or crowns), ``seen`` = the caller's
    cumulative set of opponent body names, updated IN PLACE."""
    from pipeline import archetypes as AR
    from pipeline import reward_shaping as RS
    seen.update(AR.canon(e["name"]) for e in state.get("entities") or ()
                if int(e["side"]) != side and e.get("name"))
    c = RS.crowns(state)
    return [AR.ARCH_IDS.index(AR.classify(seen)) if seen else 0, int(bool(seen & AR.TANK)),
            0 if tick < 2400 else 1 if tick < 3600 else 2, min(3, int(c[side])), min(3, int(c[1 - side]))]


def posture_dtau(matches: Sequence, enc, cfg: dict) -> Optional[np.ndarray]:
    """rl_royale C1 (``cfg["posture"]`` = {head, every, dtau, mode}; absent -> None and nothing is touched): the gate
    threshold offset of each row's posture IN FORCE. A match chooses at its first decision and again once
    ``every`` ticks have passed since its last choice (decision tick ``_cur[0]``), from ``head(enc["g"][r], ctx)`` with
    ctx = ``Match._ctx_row`` (taken at EVERY decision, so the cumulative seen-set is record_ctx's); ``mode`` sample =
    a draw from the match's own ``rng_behave`` (before its gate draw), argmax = the eval rule. Per match:
    ``_posture`` (z, tick), ``_posture_new`` (log pi(z) when it chose at this decision, else None), ``posture_counts``
    (decisions per posture) and ``posture_choices``."""
    pc = cfg.get("posture")
    if not pc:
        return None
    import torch
    ctx = [m._ctx_row(int(m._cur[0])) for m in matches]
    due = [r for r, m in enumerate(matches)
           if getattr(m, "_posture", None) is None or int(m._cur[0]) - m._posture[1] >= int(pc["every"])]
    for m in matches:
        m._posture_new = None
    if due:
        g = enc["g"]
        with torch.no_grad():
            ix = torch.as_tensor(due, device=g.device)
            lp = torch.log_softmax(pc["head"](g[ix], torch.as_tensor([ctx[r] for r in due], device=g.device))
                                   .double(), dim=-1).cpu().numpy()
        for j, r in enumerate(due):
            m = matches[r]
            z = int(m.rng_behave.choice(lp.shape[1], p=np.exp(lp[j]))) if pc["mode"] == "sample" else int(lp[j].argmax())
            m._posture, m._posture_new = (z, int(m._cur[0])), float(lp[j][z])
            m.posture_choices = getattr(m, "posture_choices", 0) + 1
    for m in matches:
        m.__dict__.setdefault("posture_counts", [0] * len(pc["dtau"]))[m._posture[0]] += 1
    return np.array([float(pc["dtau"][m._posture[0]]) for m in matches], dtype=np.float64)


def posture_live(matches: Sequence, enc, cfg: dict, tau, kw: dict) -> tuple:
    """C1 posture on a LIVE (greedy) decide -> (tau, decide kwargs); no cfg["posture"] = (tau, kw) unchanged. With
    decision options active the offset goes in as decide_batch's ``tau_delta`` (added after tau_phase / tau_threatened:
    the threshold in force + dtau); otherwise the plain threshold becomes per row tau + dtau."""
    dt = posture_dtau(matches, enc, cfg)
    if dt is None:
        return tau, kw
    if kw.get("decision_options") is not None:
        return tau, {**kw, "tau_delta": np.asarray(kw.get("tau_delta", 0.0), dtype=np.float64) + dt}
    return float(tau) + dt, kw


def sample_decide_batch(model, enc, heads, p, allowed: np.ndarray, stalled: np.ndarray, matches: Sequence,
                         cfg: dict) -> list[dict]:
    """rl_plan.md 'Behaviour policy', batched: ``decision_options.decide`` with decode 'sample' (plan1026 P1: the ONE
    decide of live, SIM eval and rollouts). The tensor work (masked softmaxes, ONE ``cell_logits`` call for every
    playing row) is shared across the round; each row's Bernoulli/categorical draws come from ITS OWN
    ``matches[r].rng_behave``, so a row's sampled action never depends on which other matches share the round.
    ``matches[r]`` needs only a ``.rng_behave`` (an ``np.random.Generator``); ``run_batch`` passes ``Match``
    instances, the single-row caller (``Match.decide_row``) passes ``[self]``.
    Returns dicts with the live-decide keys (play/slot/cell/why) PLUS the record fields from the spec:
    allowed, stalled, gate_sampled, lp_gate, lp_card, lp_cell (float64), p_gate (untempered sigmoid), T.
    ``cfg['sample_heads']`` (default all three = unchanged): a head left out takes the live greedy choice instead of a
    draw (gate: p > tau; card/cell: argmax) and its log-prob stays 0 -- an EVAL-ONLY decomposition (10-13 GAP), not for
    PPO rows. The finishers (lethal_rocket / lethal_log / lethal_quiet) and barrel_lane in ``cfg`` run as in live
    (decision_options.SAMPLE_RULES); their rows carry ``forced`` True (left out of PPO). No such key in cfg = as before."""
    if "hazard" in heads and "gate" not in heads:              # P2 opponents: a timing-head model has no gate
        return timing_decide_batch(model, enc, heads, allowed, matches, cfg)
    from dataclasses import replace
    from .decision_options import (BARREL_KEY, DecisionOptions, decide, match_kwargs, model_cell_logits,
                                   options_from_config, sample_rules)
    tau, T = float(cfg["tau"]), float(cfg.get("T", 0.5))
    p = np.asarray(p, dtype=np.float64)
    dt = posture_dtau(matches, enc, cfg)                       # rl_royale C1 (None = no posture: all as before)
    tau_r = None
    if cfg.get("tau_phase") is not None:                       # rl_royale tau_phase: live's threshold of the row's phase
        from .decision_options import phase_index              # (decision_options.gate_taus, the board's t_sec) + dtau
        tau_r = np.asarray(cfg["tau_phase"], dtype=np.float64)[phase_index([float(m._cur[1].t_sec) for m in matches])]
        tau_r = tau_r if dt is None else tau_r + dt
    elif dt is not None:
        tau_r = tau + dt                                       # the threshold of each row's posture in force
    rules = sample_rules(options_from_config(cfg))
    context = {}
    if rules != DecisionOptions():                             # the finishers / barrel_lane: live's per-row context
        kw = match_kwargs(matches)
        context = {k: v for k, v in kw.items() if k in ("t_sec", "grid", "lethal", "projectiles", "barrel_goblins")}
        if rules.card_levels is not None:                      # card_levels is LIVE-ONLY (the SIM's own cards)
            rules = sample_rules(replace(rules, card_levels=None))
        if rules.uses_barrels:
            context["barrel_id"] = getattr(model, "gid", {}).get(BARREL_KEY)
    dev = heads["card"].device
    out = decide(heads, p, allowed, stalled, tau=tau, options=rules, rngs=[None] * len(allowed), decode="sample",
                 sampler={"tau_r": tau_r, "T": T, "T_gate": float(cfg.get("T_gate") or T),
                          "heads": frozenset(cfg.get("sample_heads", ("gate", "card", "cell"))),
                          "rngs": [m.rng_behave for m in matches]},
                 cell_logits=model_cell_logits(model, enc, dev),
                 card_names=[list(m.deck.cards) for m in matches] if context else None, **context)
    for r in range(len(out)):
        if dt is not None:                                     # C1: the posture in force; its log-prob if chosen now
            m = matches[r]
            out[r].update(posture=int(m._posture[0]), posture_dtau=float(dt[r]), posture_new=m._posture_new is not None,
                          posture_lp=0.0 if m._posture_new is None else m._posture_new)
        if cfg.get("tau_phase") is not None:                   # tau_phase: the threshold this row's gate was sampled at
            out[r]["gate_tau"] = float(tau_r[r])
    ab = ability_decide(matches, enc, cfg)                     # rl_royale ability_head (None = off: rows unchanged)
    if ab is not None:
        for r in range(len(out)):
            out[r].update(ab[r])
    return out


# ------------------------------------------------------------------------------------------------------
# generalist (GenModel) behind S1's deck-slot interface (L68 T4)
# ------------------------------------------------------------------------------------------------------
GEN_V3_KEYS = ("unit_form", "opp_past")
GEN_V31_KEYS = ('opp_cycle', 'projectiles', 'effects', 'own_ability')
GEN_CUE_KEYS = ("cue",)                # step c (rl_royale cue_inputs): a model with a cue layer takes them (sim_cue_rows)
GEN_TGT_KEYS = ("tgt", "tgt_idx")      # TARGET-OBS (rl_royale target_obs): a model with tgt_in takes them (target_obs)
CUE_MATCH_TILES = 3.0                  # sim_cue_rows: a token takes the nearest same-side SIM body within this (tiles)


def opp_ctx_keys(model) -> tuple:
    """P2 opponents: a deck-encoder / context-token GenModel's extra row keys (deck_gid, ctx_<name>); () for every other
    model (a legacy GenModel's ``opp`` has neither)."""
    o = getattr(model, "opp", None) or {}
    return (("deck_gid",) if o.get("deck_enc") else ()) + tuple(f"ctx_{k}" for k in o.get("ctx_tokens") or {})


def opp_row_keys(row: dict) -> tuple:
    """The opponent-model context keys a row carries (deck_gid, ctx_<name>: GenPolicy.opp_inputs), in its order."""
    return tuple(k for k in row if k == "deck_gid" or k.startswith("ctx_"))


def is_timing(policy) -> bool:
    """A GenPolicy whose GenModel has the P2 slot timing head (no gate): decoded only by gate_decode 'timing_head'."""
    return bool((getattr(getattr(policy, "model", None), "opp", None) or {}).get("timing"))


def timing_cfg(cfg: dict) -> dict:
    """The seat cfg of a timing-head opponent (decision_options 'timing_head'): the 10-tick slot grid, plays issued at
    the drawn tick (no action delay of ours; crforge's own command delay still applies, as in the HF re-drive the rows
    came from), no look-ahead and no anti-stall (the rows have neither). The retired knobs refuse: a decide_every other
    than the slot, or a mechanism this decode does not define."""
    from .decision_options import TIMING_SLOT_TICKS
    bad = [k for k in ("pipeline_decisions", "tap_loss", "tap_slow", "record", "posture", "ability", "_opp_style")
           if cfg.get(k) and not (k == "record" and cfg.get("th_learner"))]   # OPP-LEARN: a learner seat records
    if bad or cfg.get("gate_decode", "timing_head") != "timing_head":
        raise ValueError(f"a timing-head seat cannot run {bad or cfg.get('gate_decode')}")
    if int(cfg.get("decide_every", TIMING_SLOT_TICKS)) != TIMING_SLOT_TICKS:
        raise ValueError(f"a timing-head seat decides every {TIMING_SLOT_TICKS} ticks (opp_decide_every is retired for it)")
    return dict(cfg, gate_decode="timing_head", decide_every=TIMING_SLOT_TICKS, action_delay_ticks=0,
                extrapolate_ticks=0, stall_elixir=None)


def th_has_ability(policy) -> bool:
    """A timing-head seat whose GenModel has the learned ability head (it presses, not the env's rule)."""
    return is_timing(policy) and bool(policy.model.opp.get("ability"))


def th_costs(m) -> list:
    """A timing-head seat's per-slot costs: Mirror costs the card it repeats + 1, capped at 10 (crforge
    LadderMatch.mirrorItem: min(Mirror + repeated card, max elixir); with the catalogue's Mirror cost v0's level B had 70
    of 110 Mirror plays refused not_enough_elixir), the repeated card = this seat's last issued non-Mirror card; no
    card issued yet = Mirror unplayable. Every other card: its catalogue cost."""
    from pipeline.dataset_gen import card_key
    names = [card_key(m.engine_deck[m.deck_index_of_slot[s]]) for s in range(N_SLOTS)]
    if "mirror" not in names:
        return m.costs
    ms, costs = names.index("mirror"), list(m.costs)
    last = next((s for _, s, *_ in reversed(m.done_plays) if s != ms), None)
    costs[ms] = math.inf if last is None else min(m.costs[last] + 1.0, 10.0)
    return costs


def th_decided(m) -> bool:
    """The engine refuses every play now (crforge: the match is decided and in its end period before game over; v0's
    level B had 1,303 of 1,531 opponent refusals in a match's last 80 ticks, none accepted there): its own check."""
    core = getattr(m.env, "core", None)
    if not hasattr(core, "check_deploy"):
        return False
    from royalegym.protocol import DeployCommand, DeployStatus
    return core.check_deploy(DeployCommand(m.side, 0, 0, 0)) == DeployStatus.GAME_OVER


def th_ability(m, heads, r: int) -> Optional[int]:
    """The learned ability head of a timing-head seat (SelfPlaySide.prepare keeps the env's press rule off its side). At a
    slot start with a visible own ability controller (the rows' ab_ok) draw Bernoulli(h) and the tick j inside the slot
    from the seat's own ability stream (its card / cell draws untouched); a press of a READY button is queued j ticks on
    (the env's queue rechecks readiness then); no ready button = no press (the HF rows label accepted presses only).
    -> the tick j a press was queued at (OPP-LEARN: the row's th_ab label), else None."""
    from .decision_options import timing_slot_draw
    oa = (getattr(m, "_gen_row", None) or {}).get("own_ability")
    ready = m.env._scan(m.side, lambda *_: True)             # readiness only (royale_env._any_gate)
    if not (ready if oa is None else (np.asarray(oa)[..., 0] > 0).any()):
        return None
    if getattr(m, "_th_ab_rng", None) is None:
        m._th_ab_rng = np.random.default_rng(zlib.crc32(f"{m.tag}:th_ability".encode()))
    st = m.__dict__.setdefault("th_ab", {"slots": 0, "draws": 0, "queued": 0})
    st["slots"] += 1
    j = timing_slot_draw(float(heads["ab_hazard"][r]), heads["ab_tick"][r].detach().float().cpu().numpy(), m._th_ab_rng)
    if j is None:
        return None
    st["draws"] += 1
    if ready:
        st["queued"] += 1
        m.env.queue_abilities(m.side, [ready[0]], j)
        return j
    return None


def timing_decide_batch(model, enc, heads, allowed: np.ndarray, matches: Sequence, cfg: dict) -> list[dict]:
    """gate_decode 'timing_head' on one shared forward. A side at a slot start (``_th_slot`` None) draws Bernoulli(h_s)
    and the tick j inside the slot from ITS ``rng_behave`` (decision_options.timing_slot_draw); j > 0 -> no play now,
    the side decides again at slot + j (SelfPlaySide.apply, ``th_tick``). j = 0, or a side at its drawn tick, draws the
    card (allowed slots) and the cell at cfg['T'] from these heads -- its observation AT the play tick, as the play
    rows were built (decision_options.timing_play_draw). The card is drawn among the slots the seat can REALLY play:
    crforge runs a play engine_delay_ticks after it is issued and charges / cycles it only then, so the board still shows
    the elixir and the hand from before my plays it holds; those slots are not choosable and their cost is taken off
    the elixir (a human's client charges at the tap: the re-driven human commands never overspend).
    cfg["record"] (OPP-LEARN: the opponent model as the RL learner; refused for a frozen seat): ``th_record``'s fields."""
    from .decision_options import model_cell_logits, timing_play_draw, timing_slot_draw
    if not all(hasattr(m, "_th_slot") for m in matches):
        raise ValueError("timing_head decodes a SelfPlaySide seat only")
    allowed = np.array(allowed, dtype=bool)
    over = []
    for r, m in enumerate(matches):
        eng = int(getattr(m.env, "engine_delay_ticks", 0))
        held = [s for t, s, *_ in m.done_plays if t + eng >= int(m._cur[0])]  # issued, not yet run (the board at
        #                                                                       its run tick is still the one before)
        costs = th_costs(m)
        if held:
            allowed[r, held] = False
        el = math.floor(float(m._cur[2].my_elixir) - sum(costs[s] for s in held) + 1e-9)
        allowed[r] &= np.asarray(costs) <= el
        over.append(th_decided(m))
    T = float(cfg.get("T", 1.0))
    hz = heads["hazard"].detach().float().cpu().numpy()
    tk = heads["tick"].detach().float().cpu().numpy()
    card = heads["card"].detach().float().cpu().numpy()
    cell = model_cell_logits(model, enc, heads["card"].device)
    out, ab_j = [], [None] * len(matches)
    for r, m in enumerate(matches):
        if over[r]:                                           # crforge: the match is decided, every play is refused
            out.append({"play": False, "slot": -1, "cell": -1, "why": "game_over"})
            continue
        if m._th_slot is None and "ab_hazard" in heads:     # the learned ability head (its own slot draw + stream)
            ab_j[r] = th_ability(m, heads, r)
        if m._th_slot is None:
            j = timing_slot_draw(hz[r], tk[r], m.rng_behave)
            if j is None or j > 0:
                out.append({"play": False, "slot": -1, "cell": -1, "why": "timing_wait" if j is None else "timing_slot",
                            **({"th_tick": j} if j else {})})
                continue
        got = timing_play_draw(card[r], allowed[r], lambda s: cell([r], [s])[0].detach().float().cpu().numpy(), m.rng_behave, T)
        out.append({"play": False, "slot": -1, "cell": -1, "why": "no_affordable"} if got is None else
                   {"play": True, "slot": got[0], "cell": got[1], "why": "timing"})
    if cfg.get("record"):
        th_record(out, allowed, matches, hz, card, cell, ab_j, T, tk if cfg.get("th_pg") else None)
    return out


def th_record(out: list, allowed: np.ndarray, matches: Sequence, hz, card, cell, ab_j: list, T: float,
              tk=None) -> None:
    """OPP-LEARN (a timing-head LEARNER seat, cfg["record"]): sample_decide_batch's record fields on every row, in place.
    Only card / cell act through the policy the learner trains (timing / ability heads frozen: ``freeze_heads``), so
    the behaviour log-probs are lp_card / lp_cell of the play rows (the mask = the seat's REAL allowed slots, as drawn;
    float64 of the float32 heads at T, rl_royale.policy_terms' recompute); lp_gate 0 and gate_sampled False on every row
    (there is no gate). Labels of the frozen heads: th_j = the tick-in-slot drawn at a slot start (-1 no play this slot),
    -2 at a drawn tick (the play row of an earlier slot start), -3 game over; th_ab = the tick an ability press was
    queued at this slot start, -1 none. p_gate = sigmoid(hazard) (the monitors' p).
    ``tk`` (OPP-LEARN-D, cfg th_pg = rl_royale timing_pg; None = no key, rows unchanged): + lp_th = the log-prob of the
    slot-start timing decision taken (timing_slot_draw: wait log(1 - h), a play at tick j log h + log softmax(tick)[j];
    float64 of the float32 heads, T 1 as drawn), 0 on rows that decide no timing (th_j -2 / -3)."""
    import torch
    for r, (d, m) in enumerate(zip(out, matches)):
        lc = lx = 0.0
        if d["play"]:
            z = np.where(allowed[r], np.asarray(card[r], np.float64), -1e9) / T
            lc = float(z[d["slot"]] - z.max() - np.log(np.exp(z - z.max()).sum()))
            with torch.no_grad():
                c = cell([r], [d["slot"]])[0].detach().float().cpu().numpy().astype(np.float64) / T
            lx = float(c[d["cell"]] - c.max() - np.log(np.exp(c - c.max()).sum()))
        j = (-3 if d["why"] == "game_over" else -2 if m._th_slot is not None else -1 if d["why"] == "timing_wait"
             else d.get("th_tick", 0))
        d.update(allowed=allowed[r].copy(), stalled=False, gate_sampled=False, lp_gate=0.0, lp_card=lc, lp_cell=lx,
                 p_gate=float(1.0 / (1.0 + math.exp(-float(hz[r])))), T=T, th_j=int(j),
                 th_ab=-1 if ab_j[r] is None else int(ab_j[r]))
        if tk is not None:                                    # OPP-LEARN-D timing_pg: the slot decision's log-prob
            x = float(hz[r])
            lt = 0.0
            if j == -1:
                lt = -float(np.logaddexp(0.0, x))             # log(1 - sigmoid(x))
            elif j >= 0:
                z = np.asarray(tk[r], np.float64)
                lt = -float(np.logaddexp(0.0, -x)) + float(z[j] - z.max() - np.log(np.exp(z - z.max()).sum()))
            d["lp_th"] = lt


def gen_row_keys(model):
    version = getattr(model, 'feature_version', 1)
    keys = (GEN_ROW_KEYS + (GEN_V3_KEYS if version >= 3 else ()) + (GEN_V31_KEYS if version >= 4 else ())
            + (GEN_CUE_KEYS if getattr(model, "cue_in", None) is not None else ())
            + (GEN_TGT_KEYS if getattr(model, "tgt_in", None) is not None else ()) + opp_ctx_keys(model))
    if getattr(model, "mem", None) is not None:              # Plan A memory v1: the match_memory MEM_KEYS
        from pipeline.match_memory import MEM_KEYS
        keys += MEM_KEYS
    return keys


def gen_batch(model, B: dict, idx) -> dict:
    """The model's input rows ``idx`` of a collated batch ``B`` (rl_royale): ``B[k][idx]`` for every gen_row key, except a
    memory model's MEM_KEYS, rebuilt from B's per-match event tables (``mem_tab_*``) and the rows' ``mem_row_tab`` /
    ``mem_row_t`` by match_memory.rows_features (CPU numpy, exactly the rollout's MatchMemory.features)."""
    from pipeline.match_memory import MEM_KEYS, rows_features
    keys = gen_row_keys(model)
    b = {k: B[k][idx] for k in keys if k not in MEM_KEYS}
    if getattr(model, "mem", None) is not None:
        import torch
        if "mem_row_t" not in B:
            raise KeyError("a memory model needs the batch's memory tables (rollouts recorded with a memory model)")
        ids = idx.cpu().numpy() if torch.is_tensor(idx) else np.asarray(idx)
        deck = B["deck_card"].cpu().numpy() if torch.is_tensor(B["deck_card"]) else np.asarray(B["deck_card"])
        packed = {k[8:]: v for k, v in B.items() if k.startswith("mem_tab_")}
        m = rows_features(packed, B["mem_row_tab"], B["mem_row_t"], deck, ids, getattr(model.mem, "version", "v1"),
                          getattr(model.mem, "gid", None),       # v2: the vocabulary model_gen.attach_vocab set
                          e_max=getattr(model.mem, "e_max", None) or 128)   # MEM-FULL (absent = match_memory.E_MAX)
        dev = B["sc"].device if torch.is_tensor(B["sc"]) else "cpu"
        b.update({k: torch.from_numpy(v).to(dev) for k, v in m.items()})
    return b


def require_cue_runtime():
    """Cue inputs read pipeline.sim_unit_state, which needs RoyaleSim >= 0.1.35 (its 160402017 card table)."""
    sim = sys.modules.get("royalesim")
    if sim is None or not hasattr(sim, "EMBEDDED_CARDS_160402017_JSON") or not hasattr(sim.Battle, "unit_types_digest"):
        raise RuntimeError("cue inputs need RoyaleSim >= 0.1.35 (ROYALE_RUNTIME=20261016-linux; laptop: the composite "
                           "venv in scratchpad/gauntlet/L74/cues/STEP_C_SPEC.md); this runtime has "
                           f"{getattr(sim, '__version__', None)!r}")


def sim_cue_rows(match) -> np.ndarray:
    """[MAX_U, CUE_N] float32 cue rows aligned with the prepared ``tok`` (model_gen.cue_vector; STEP_C_SPEC.md). The
    SIM battle's units at the decision tick (sim_unit_state.extract, hit window 100 ms = the live 2-tick sampling,
    per-match buff memo) are matched to the unit tokens (spell tokens and pads stay 0) by side + position: pairs taken
    nearest-first, one body per token, within CUE_MATCH_TILES (the view may be extrapolated). Unmatched -> 0 (cue_known 0).
    ponytail: position matching, not uid -- tokens carry no uid (the live reader will not have one either)."""
    from pipeline.model_gen import CUE_N, cue_vector
    from pipeline.sim_unit_state import extract
    require_cue_runtime()
    tok, mask = match._obs[0], match._obs[1]
    out = np.zeros((len(tok), CUE_N), np.float32)
    c = extract(match.env.core._battle, match.__dict__.setdefault("_cue_memo", {}), hit_window_ms=100)
    towers = {u["uid"] for u in c["units"] if u["kind"] in ("princess_tower", "king_tower")}
    bodies = [u for u in c["units"] if u["uid"] not in towers]
    ti = np.flatnonzero(mask & (tok[:, 13] == 0) & ((tok[:, 1] > 0) | (tok[:, 2] > 0)))
    if not len(ti) or not bodies:
        return out
    bx = np.array([u["x"] / 18.0 for u in bodies])
    by = np.array([1.0 - u["y"] / 32.0 for u in bodies])
    if match.side == 1:                                       # obs_contract._engine_xy: side 1 sees the board mirrored
        bx, by = 1.0 - bx, 1.0 - by
    mine = np.array([u["team"] == match.side for u in bodies])
    d = np.hypot((tok[ti, 4:5] - bx) * 18.0, (tok[ti, 5:6] - by) * 32.0)
    d[(tok[ti, 1:2] > 0) != mine] = np.inf
    while True:
        i, j = np.unravel_index(np.argmin(d), d.shape)
        if not d[i, j] <= CUE_MATCH_TILES:
            return out
        u = bodies[j]
        out[ti[i]] = cue_vector(u, u["attack"]["target"] in towers)
        d[i, :] = np.inf
        d[:, j] = np.inf


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

    def __init__(self, model, card_vocab: Sequence[str], opp_sim: Optional[dict] = None):
        from pipeline.dataset_gen import checkpoint_gid
        self.model = model
        self.gid = checkpoint_gid(card_vocab)              # 0 = <pad>; + stand-ins for cards newer than the vocab
        # P2 opponents (a deck-encoder / context-token model only; None for every other): the checkpoint's "opp_sim"
        # (plan1026/opp/attach_sim.py) = the context token ids to play under + the training deck-id table
        self.opp_sim = None
        if opp_ctx_keys(model):
            if not opp_sim or set(model.opp["ctx_tokens"]) - set(opp_sim.get("ctx") or {}):
                raise ValueError("this opponent model needs its checkpoint's opp_sim (ctx ids + deck_keys): "
                                 "scratchpad/gauntlet/L74/plan1026/opp/attach_sim.py")
            self.opp_sim = {"ctx": {k: int(opp_sim["ctx"][k]) for k in model.opp["ctx_tokens"]},
                            "deck": {tuple(int(v) for v in key): i + 1 for i, key in enumerate(opp_sim.get("deck_keys") or [])}}

    def opp_inputs(self, row: dict) -> dict:
        """The context row keys (opp_ctx_keys) of a GenPolicy.row: deck_gid = the training id of the row's (card, form)
        set in rows_to_npz's key order (deck_card ascending, its forms), 0 = unknown; ctx_<name> = opp_sim's id."""
        out = {f"ctx_{k}": np.int64(v) for k, v in self.opp_sim["ctx"].items()}
        if self.model.opp["deck_enc"]:
            key = tuple(int(v) for v in row["deck_card"]) + tuple(int(v) for v in row["deck_form"])
            out["deck_gid"] = np.int64(self.opp_sim["deck"].get(key, 0))
        return out

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
        if "gate" not in h:                                  # P2 timing head: the slot hazard + tick (no gate)
            return enc, {"card": card, "card_hand": h["card"], "hazard": h["hazard"], "tick": h["tick"],
                         **{k: h[k] for k in ("ab_hazard", "ab_tick") if k in h}}   # + the ability head (th_ability)
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
            p = torch.sigmoid(heads["gate"] if "gate" in heads else heads["hazard"]).cpu().tolist()   # timing: h_s
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
    return GenPolicy(model, st["card_vocab"], st.get("opp_sim")), {"gen": True, "epoch": st.get("epoch"), "n_params": st.get("n_params"),
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
        self.mem = None                                      # Plan A: a MatchMemory once a memory model decides (gen_row)
        self.t0 = time.perf_counter()
        self.delay = int(cfg.get("action_delay_ticks") or 0)
        if self.delay < 0:
            raise ValueError(f"cfg['action_delay_ticks'] {self.delay} < 0")
        # cfg's delay is tap to LAND (live's 26). crforge runs a play its own engine_delay_ticks (20) after the act, so
        # e1 waits only the rest (6); RoyaleSim runs it at once (0 = unchanged)
        self.delay = max(0, self.delay - int(getattr(env, "engine_delay_ticks", 0)))
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
            # LOOP-IW: when the head decides MY side's presses, the rule's answer for my side was discarded, so it is
            # no longer asked (its LiveIWPolicy observe + gates were pure cost). Identity-safe: what that call left
            # behind (my side's IW observer and frame, _ability_check[my side], _v2_dt, _v2_info entries) is read only
            # by my side's own later ability_commands, never made in head mode; _v2_dt is set again by every call that
            # reads it, and ability_options creates the same _v2_info entries at the same tick.
            head = bool(cfg.get("ability")) and cfg["ability"]["mode"] != "label"
            if getattr(self, "timing", False) and th_has_ability(self.model):   # P2: its learned head presses
                head = True                                  # (timing_decide_batch -> th_ability), never the rule
                self.env.learned_sides.add(self.side)
            self._ability_commands = {s: [] if head and s == self.side else self.env.ability_commands(s) for s in sides}
            if cfg.get("ability"):                           # rl_royale ability_head: MY side's options (ability_decide)
                rule = self._ability_commands[self.side]
                if head:                                     # the head decides: the rule never presses for my side
                    self.env.learned_sides.add(self.side)
                self._ability_opts = self.env.ability_options(self.side, None if head else rule)
        self._gen_row = None
        if self.last_play_tick is None:
            self.last_play_tick = tick                       # match start = first decision (anti-stall clock)
        raw, h = self.state, (self.extrap if self._prev_raw is not None else 0)
        if self.feature_version >= 4:
            from pipeline.public_observation import PublicObserver
            if self.public is None:
                self.public = PublicObserver(self.side, schedule=getattr(self.env, 'elixir_regen_schedule', None))
                if getattr(self, "_counter_start", None) is not None:      # W15 lever 2 (SelfPlaySide)
                    self.public.start_at(*self._counter_start)
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
        if cfg.get("record_elixir"):                         # rl_royale F6': my exact elixir in the RAW state of
            self._obs_elixir = float(next(pl for pl in self.state["players"]   # this tick (never the extrapolated /
                                          if int(pl["side"]) == self.side)["elixir_exact"])   # pending-adjusted bs)
        return tok, mask, sc, past

    def _own_effects(self, tick: int) -> list:
        """cfg["own_effects"]: my accepted plays and my side's confirmed ability presses of the last OWN_FX_TICKS."""
        abil = [dict(card=e["card"], tick=int(e["tick"]), x=0, y=0, ability=True)
                for e in getattr(self.env, "own_ability_events", ()) if e["side"] == self.side]
        pend = [dict(card=self.deck.cards[d["slot"]], tick=int(land),
                     **dict(zip("xy", self.ep.cell_to_engine(d["cell"], self.mirror, self.cfg["grid"]))))
                for land, _, d, _ in self.pend]                # cfg["pipeline_decisions"]: pending plays at their landing tick
        out = [p for p in self.own_fx + abil + pend if tick - OWN_FX_TICKS <= p["tick"]]
        if self.cfg.get("tornado_river") in ("on", "full"):   # --tornado-river (owner 10-14): pulls hold ground bodies at the bank
            out = [dict(p, river=True) for p in out]
        return out

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
        if getattr(policy, "opp_sim", None) is not None:          # P2 opponents: deck id + context tokens
            self._gen_row.update(policy.opp_inputs(self._gen_row))
        if getattr(policy.model, "feature_version", 1) >= 3:
            self._gen_row.update(sim_v3_features(self, policy))
        if getattr(policy.model, "cue_in", None) is not None:    # step c: the model has a cue layer -> its cue rows
            self._gen_row["cue"] = sim_cue_rows(self)
        if getattr(policy.model, "tgt_in", None) is not None:    # TARGET-OBS: who targets whom (pipeline/target_obs.py)
            from pipeline.target_obs import sim_target_rows
            self._gen_row["tgt"], self._gen_row["tgt_idx"] = sim_target_rows(self)
        if getattr(policy.model, "mem", None) is not None:       # Plan A memory v1: this decision's memory rows
            self._gen_row.update(self._memory(policy, self._gen_row["deck_card"]))
        return self._gen_row

    def _memory(self, policy, deck) -> dict:
        """Feed this side's MatchMemory the decision's UN-extrapolated state (``self.state`` at the prepare tick: towers,
        own elixir, public bodies) + the public play lists (opponent: PublicObserver.plays; own: its own_events = env
        public_plays + own_ability_events), -> MatchMemory.features at the decision tick. Idempotent per tick."""
        from pipeline import match_memory as MM
        if self.feature_version < 4 or self.public is None:
            raise ValueError("memory v1 needs a feature_version >= 4 policy (the public observation it is built from)")
        tick = int(self._cur[0])
        if getattr(self, "mem", None) is None:
            self.mem, self._mem_gid = MM.MatchMemory(self.side, **MM.opts(policy.model.mem)), policy.gid   # MEM-FULL
        smp = MM.sample_sim(self.state, self.side)
        smp["tick"] = tick
        self.mem.observe(**smp, plays=list(self.public.plays) + list(self.public.own_events))
        return self.mem.features(tick, policy.gid, deck, getattr(policy.model.mem, "version", "v1"))

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
            ability_decide([self], enc, cfg)                  # rl_royale ability_head, greedy (no cfg key = no-op)
            extras = match_kwargs([self])
            if extras or cfg.get("posture"):                  # rl_royale C1 posture: the batch decide takes a per-row tau
                tau, extras = posture_live([self], enc, cfg, cfg['tau'], extras)
                return live_decide_batch(model, enc, heads, [p], allowed[None], np.array([stalled]),
                                         tau=tau, device=device, **extras)[0]
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
        # crforge (royale_env engine_delay_ticks 20; 0 on RoyaleSim = unchanged): the engine runs the play that much after
        # the act, and the seat makes no decision before it runs (live: no decision while a play is pending)
        eng = int(getattr(env, "engine_delay_ticks", 0))
        env._advance_to(min((tick + de * ((delay + eng) // de + 1)) if ((delay or eng) and d["play"]) else env.tick + de,
                            env.tail_cap))
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
        land_a = tick + delay
        st = {"a_acc": None, "a_landed": False, "last": land_a, "seq": 0}
        tally = getattr(self, "follow_n", None)
        if tally is None:
            tally = self.follow_n = Counter()
        # plays decided and not landed yet, by landing tick: the first play, then every fired follow-up. EVERY one reaches the
        # engine at its OWN landing tick: advance() lands whatever is due before it moves the engine on, however long a later
        # follow-up keeps waiting. "Outstanding" = this list (decided, not landed); live's = tapped, not confirmed. Both are
        # judged on the 2-tick frame grid anchored at the decision (below), where a play that landed at or before a frame's
        # tick has been confirmed on that frame, so the two agree except that live counts from the first board tap's
        # return (>= FOLLOW_ARRIVAL_TICKS after the decision; no follow-up is judged earlier either, see ``t`` below).
        queue = [(land_a, 0, d)]

        def advance(t: int) -> None:
            t = min(t, env.tail_cap)
            while queue and queue[0][0] <= t:
                lt, _, dd = queue.pop(0)
                env._advance_to(min(lt, env.tail_cap))
                first = dd is d
                landed = not ((delay or not first) and (env.terminated or env.tick < lt))
                acc = self._land(p, dd, lt, landed)
                st["last"] = max(st["last"], lt)
                if first:
                    st["a_acc"], st["a_landed"] = acc, True
            env._advance_to(t)

        grid = lambda x: tick + -(-(x - tick) // FOLLOW_FRAME_TICKS) * FOLLOW_FRAME_TICKS      # noqa: E731 first frame tick >= x
        for fu in d["follow_ups"]:
            after, within = int(fu["after_ticks"]), int(fu["within_ticks"])
            horizon = fu.get("afford_ticks")
            horizon = FOLLOW_AFFORD_TICKS if horizon is None else int(horizon)
            due, expire = tick + after, tick + after + within
            # judged on reader frames: the first one at or after its due tick AND after the first tap returned
            t, blocked, outcome = grid(max(due, tick + arrival)), None, "late"
            while t <= expire and not (env.terminated or env.tick >= env.tail_cap):
                advance(t)
                out = [dd["slot"] for _, _, dd in queue]
                me = next(pl for pl in env.eng.observe()["players"] if int(pl["side"]) == self.side)
                act, why = follow_up_verdict(
                    tick=env.tick, due=due, expire=expire, blocked=blocked,
                    first_failed=bool(fu.get("require_first", True) and st["a_landed"] and not st["a_acc"]),
                    slot_changed=not self._slot_in_hand(fu["slot"]), slot_busy=fu["slot"] in out, n_out=len(out),
                    have=follow_up_have(me["elixir_exact"], env.tick, horizon, sum(self.costs[s] for s in out)),
                    cost=self.costs[fu["slot"]])
                if act == "fire":
                    st["seq"] += 1
                    queue.append((max(land_a + max(t - tick - arrival, 0), env.tick + 1), st["seq"],
                                  {"play": True, "slot": fu["slot"], "cell": fu["cell"], "why": "follow_up"}))
                    queue.sort(key=lambda e: (e[0], e[1]))
                    outcome = None
                    break
                if act == "cancel":
                    outcome = why
                    break
                blocked = why if why != "early" else blocked      # what held it, for the cancel reason at its expiry
                outcome = blocked or "late"
                t += FOLLOW_FRAME_TICKS
            tally["fired" if outcome is None else f"cancelled_{outcome}"] += 1
        advance(max([land_a] + [lt for lt, _, _ in queue]))   # the rest land, each at its own tick (the first even if all dropped)
        last = st["last"]
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

    def _ctx_row(self, tick: int) -> list[int]:
        """cfg["record_ctx"] (rl_royale critic_ctx), public information from this side's view only: [arch_id, tank_flag,
        phase_id, own crowns, foe crowns]. arch / tank = ``archetypes.classify`` of the cumulative set (this match, this
        side) of the OPPONENT's body names seen on the board at recorded decisions; phase 0 < 2400 <= 1 < 3600 <= 2 by
        the decision tick; crowns = ``reward_shaping.crowns`` (the engine's when attached, else from the towers)."""
        return ctx_row(self.state, self.side, tick, self.__dict__.setdefault("_ctx_seen", set()))

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
                row = {k: self._gen_row[k] for k in self._gen_row
                       if k in GEN_ROW_KEYS + GEN_V3_KEYS + GEN_V31_KEYS + GEN_CUE_KEYS + GEN_TGT_KEYS
                       + opp_row_keys(self._gen_row)}
            if cfg.get("record_phi"):                         # rl_royale shaping: what Phi needs, own view (True =
                from pipeline import reward_shaping as RS     # R2 tower_crown, else the step-3 mode's own row)
                mem = self.__dict__.setdefault("_phi_mem", {})
                if cfg["record_phi"] in ("trade", "trade2"):  # A3 / A3': the PUBLIC counter at this decision, never truth
                    mem["opp_est"] = (None if not self.opp_mode else self.public.estimate_at(tick)
                                      if self.public is not None else self.opp_estimate(tick))
                row = {**row, "phi_state": RS.phi_record(self.state, self.side) if cfg["record_phi"] is True else
                       RS.state_record(cfg["record_phi"], self.state, self.side, self.env, mem)}
            if cfg.get("record_tick"):                        # rl_royale gae_gamma_unit tick: the decision tick
                row = {**row, "tick": int(tick)}
            if getattr(self, "mem", None) is not None:      # Plan A memory: the row's memory tick (the match's event
                row = {**row, "mem_t": int(tick)}             # table rides in result()["memory"]; no per-row arrays)
            if cfg.get("record_ctx"):                         # rl_royale critic_ctx: the decision's public context
                row = {**row, "ctx": self._ctx_row(tick)}
            if cfg.get("record_elixir"):                      # rl_royale F6': my exact elixir at the decision tick,
                row = {**row, "elixir": self._obs_elixir}     # from the raw state (prepare), set with self._obs
            if "posture" in d:                                # rl_royale C1: the posture in force, its choice
                row = {**row, **{k: d[k] for k in ("posture", "posture_dtau", "posture_lp", "posture_new")}}
            if "gate_tau" in d:                               # rl_royale tau_phase: the row's sampled gate threshold
                row = {**row, "gate_tau": d["gate_tau"]}
            if "forced" in d:                                 # plan1026 P1: a finisher / barrel_lane chose (no PPO row)
                row = {**row, "forced": d["forced"]}
            if "ab_sampled" in d:                             # rl_royale ability_head: the press decision / label
                row = {**row, **{k: d[k] for k in ability_defaults()}}
            if "th_j" in d:                                   # OPP-LEARN: a timing-head learner seat's frozen-head labels
                row = {**row, "th_j": d["th_j"], "th_ab": d["th_ab"]}
            if "lp_th" in d:                                  # OPP-LEARN-D timing_pg: the slot decision's log-prob
                row = {**row, "lp_th": d["lp_th"]}
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
        lost = landed and bool(d.get("_tap_lost"))            # SelfPlaySide cfg["tap_loss"]: never reaches the engine
        r = env.eng.act(side=self.side, deck_index=self.deck_index_of_slot[d["slot"]], x=X, y=Y) if landed and not lost \
            else {"accepted": False}
        acc = bool(r["accepted"])
        code = int(r.get("result_code", -1))
        card = self.deck.cards[d["slot"]]
        if (not acc) and landed and not lost and cur is None and getattr(self, "tap_hold", None):
            # cfg["tap_hold"] (RECON-7, opt-in): the game HOLDS a tap that cannot pay yet and runs it once it can, up to N ticks after the
            # tap's arrival (live: 19,361 plays, latency/afford_arrival.txt: refused only when the wait passes ~22); crforge's client gate
            # refuses it at once. A not-enough-elixir refusal is retried each tick for N ticks, the ghost seats' elixir_slack rule: the
            # card stays in hand and nothing is spent until the retry lands. The attempt is tallied once, by the landing that ends the hold.
            names0 = env._code_names if type(env).__name__ in ("RoyalePoolEnv", "RoyaleSelfPlayEnv") else ep.RESULT_CODE_NAMES
            first = d.get("_hold_from", land)
            if names0.get(code, "").startswith("not_enough_elixir") and int(env.tick) - first < self.tap_hold and not env.terminated:
                if "_hold_from" not in d:
                    self.n_tap_held += 1
                self.n_att -= 1
                self.n_stall -= int(d["why"] == "stall")
                self.pending = (int(env.tick) + 1, p, dict(d, _hold_from=first))
                self.next_tick = max(self.next_tick, first + self.tap_hold + 1)   # no decision while the held tap waits (a no-op under crforge's 20-tick delay)
                return False
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
            if d.get("_hold_from") is not None:               # RECON-7: a held tap ran late: the next decision follows ITS run (+ the engine's
                de0, eng0 = self.cfg["decide_every"], int(getattr(env, "engine_delay_ticks", 0))   # own delay), as after any play (no card_pending)
                self.next_tick = max(self.next_tick, int(land) + eng0 + 1 if self.play_resume else tick + de0 * ((int(land) - tick + eng0) // de0 + 1))
        elif not landed:
            self.n_unlanded += 1
            self.refuse["match_over_before_landing"] += 1
            rec["reason"] = "match_over_before_landing"
        elif lost:
            self.n_tap_lost += 1
            self.refuse["tap_lost"] += 1
            rec["reason"] = "tap_lost"
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
        t0 = int((getattr(env, "scenario_start", None) or {}).get("tick", 0))   # W15 lever 2: played time only
        minutes = (env.tick - t0) * TICK_S / 60.0
        end = int(env.tick)
        pg = np.asarray(self.p_gates, dtype=np.float64)
        n_att, n_acc, n_dec, n_deg, plays = self.n_att, self.n_acc, self.n_dec, self.n_deg, self.plays
        return {
            "tag": tag, "k": int(k), "slot": cfg["slot"], "port": cfg["port"], "split": entry.get("split"),
            "entry_index": cfg["entry_index"], "policy": cfg["policy"], "obs": cfg["obs"], "tau": cfg["tau"],
            "afford_mask": cfg["afford_mask"], "stall_elixir": cfg["stall_elixir"], "p_random": cfg["p_random"],
            "obs_seed": self.obs_seed_used, "side": self.side,
            "outcome": outcome, "crowns_for": int(crowns[0]), "crowns_against": int(crowns[1]),
            "end_tick": end, "seconds": round((end - t0) * TICK_S, 1), "terminated": bool(env.terminated),
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
            **({"memory": self.mem.table(self._mem_gid)} if cfg.get("record") and getattr(self, "mem", None) is not None else {}),
            **({'behaviour': env.behaviour_telemetry.result(self.side, env.eng.last_episode)}
               if cfg.get('behaviour_telemetry') else {}),
            **({'public_lookahead_counts': dict(self._public_lookahead_total)}
               if cfg.get('behaviour_telemetry') and hasattr(self, '_public_lookahead_total') else {}),
            **({"opp_counter": self._opp_summary()} if self.opp_mode else {}),
            **({"follow_ups": dict(self.follow_n)} if getattr(self, "follow_n", None) else {}),
            **({"pipeline_decisions": dict(self.pipe_n)} if self.pipe else {}),
            **({"action_delay_ticks": self.delay, "plays_unlanded": self.n_unlanded,
                "plays_refused_at_landing": n_att - n_acc - self.n_unlanded} if self.delay else {}),
            **({"tap_loss": dict(self.tap_loss), "plays_tap_lost": self.n_tap_lost}
               if getattr(self, "tap_loss", None) is not None else {}),   # SelfPlaySide cfg["tap_loss"] (L74 W18)
            **({"tap_slow": list(self.tap_slow), "plays_tap_slow": self.n_tap_slow}
               if getattr(self, "tap_slow", None) is not None else {}),   # SelfPlaySide cfg["tap_slow"] (L74 W18)
            **({"tap_hold": self.tap_hold, "plays_tap_held": self.n_tap_held}
               if getattr(self, "tap_hold", None) is not None else {}),   # SelfPlaySide cfg["tap_hold"] (RECON-7)
            **({"play_resume": self.play_resume} if getattr(self, "play_resume", None) else {}),   # SelfPlaySide cfg["play_resume"] (RECON-7)
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
            **({"ability_head": {"decisions": self.ab_stats["decisions"], "presses": self.ab_stats["presses"],
                                 "p_mean": round(self.ab_stats["p_sum"] / self.ab_stats["decisions"], 4)}}
               if getattr(self, "ab_stats", None) else {}),        # rl_royale ability_head decisions (my side)
            **({"ability_stats": env.ability_stats(self.side)}      # opt-in press outcomes (royale_env ability_outcomes)
               if getattr(env, "ability_outcomes", False) and getattr(env, "hero_abilities", False) else {}),
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
        if tj and "cue" in tj[0]:                            # step c: the cue rows the model saw
            out["cue"] = stack("cue").astype(np.float32)
        if tj and "tgt" in tj[0]:                            # TARGET-OBS: the target rows the model saw
            out["tgt"] = stack("tgt").astype(np.float32)
            out["tgt_idx"] = stack("tgt_idx").astype(np.int64)
        if tj:                                               # OPP-LEARN: an opponent model's context ids + timing labels
            for k in opp_row_keys(tj[0]) + (("th_j", "th_ab") if "th_j" in tj[0] else ()):
                out[k] = scalar(k, np.int64)
            if "lp_th" in tj[0]:                              # OPP-LEARN-D timing_pg
                out["lp_th"] = scalar("lp_th", np.float64)
        if tj and "forced" in tj[0]:                         # plan1026 P1: rule-forced rows (sample decide SAMPLE_RULES)
            out["forced"] = scalar("forced", bool)
        if tj and "phi_state" in tj[0]:                      # cfg["record_phi"]: reward_shaping.phi_record rows
            out["phi_state"] = stack("phi_state").astype(np.float64)
        if tj and "tick" in tj[0]:                           # cfg["record_tick"]: each row's decision tick
            out["tick"] = scalar("tick", np.int64)
        if tj and "mem_t" in tj[0]:                          # Plan A memory model: each row's memory tick
            out["mem_t"] = scalar("mem_t", np.int64)
        if tj and "ctx" in tj[0]:                            # cfg["record_ctx"]: [arch, tank, phase, own, foe crowns]
            out["ctx"] = stack("ctx").astype(np.int64)
        if tj and "elixir" in tj[0]:                         # cfg["record_elixir"]: own exact elixir per row
            out["elixir"] = scalar("elixir", np.float64)
        if tj and "posture" in tj[0]:                        # cfg["posture"] (rl_royale C1): z in force, its dtau,
            out.update(posture=scalar("posture", np.int64), posture_dtau=scalar("posture_dtau", np.float64),
                       posture_lp=scalar("posture_lp", np.float64),           # log pi(z) on the rows that chose it
                       posture_new=scalar("posture_new", bool))
        if tj and "gate_tau" in tj[0]:                       # cfg["tau_phase"] (rl_royale): each row's gate threshold
            out["gate_tau"] = scalar("gate_tau", np.float64)
        if tj and "ab_sampled" in tj[0]:                     # cfg["ability"] (rl_royale ability_head): per row
            out.update(ab_sampled=scalar("ab_sampled", bool), ab_press=scalar("ab_press", bool),
                       ab_lp=scalar("ab_lp", np.float64), ab_feat=stack("ab_feat").astype(np.float32),
                       ab_cand=scalar("ab_cand", bool), ab_q=scalar("ab_q", np.float64))
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
            if policy == "live":                             # (rl_royale C1: posture_live; no posture = unchanged)
                ability_decide(live, enc, cfg)               # rl_royale ability_head, greedy (no cfg key = no-op)
                tau, kw = posture_live(live, enc, cfg, cfg["tau"], match_kwargs(live))
                decisions = live_decide_batch(model, enc, heads, p, allowed, stalled, tau=tau, device=cfg["device"], **kw)
            else:
                decisions = sample_decide_batch(model, enc, heads, p, allowed, stalled, live, cfg)
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
        self.timing = is_timing(model)                      # P2 opponents: gate_decode 'timing_head' (timing_cfg)
        if self.timing:
            cfg = timing_cfg(cfg)
            self._th_slot = None                            # the slot start of a play drawn for a later tick
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
        if self.timing:                                     # the rows' grid: slots start at engine tick % 10 == 0
            self.next_tick = -(-self.next_tick // cfg["decide_every"]) * cfg["decide_every"]
        st = getattr(env, "scenario_start", None)           # W15 lever 2: a mid-match start (None = from tick 0)
        if st is not None and self.opp_mode:                # the counter starts there at the TRUE opponent elixir
            self._counter_start = (int(st["tick"]), float(st["elixir"][1 - self.side]))
            self.opp_counter.tick, self.opp_counter.est = self._counter_start
        # cfg["tap_loss"] (L74 W18, opt-in; absent = no draw, byte-identical): a decided play is LOST with the window's
        # probability -- the board runs through the action delay, the card stays in hand, no elixir is spent (the live
        # pilot's 'unconfirmed' tap with no elixir drop). Its own stream: no other RNG moves.
        self.tap_loss = parse_tap_loss(cfg.get("tap_loss"))
        self.tap_slow = parse_tap_slow(cfg.get("tap_slow"))   # cfg["tap_slow"] (W18, opt-in): a play lands EXTRA ticks late
        self.n_tap_lost = self.n_tap_slow = 0
        if self.tap_loss is not None or self.tap_slow is not None:
            if not self.delay or self.pipe:
                raise ValueError("cfg['tap_loss'] / cfg['tap_slow'] need action_delay_ticks > 0 and no pipeline_decisions")
        self.tap_hold = parse_tap_hold(cfg.get("tap_hold"))   # cfg["tap_hold"] (RECON-7, opt-in): a not-enough-elixir play is retried for N ticks
        self.n_tap_held = 0
        # cfg["play_resume"] (RECON-7, opt-in; "land"): after a delayed play the next decision is the first tick the engine has run it (act + engine
        # delay + 1), not the next tick of the decision grid. Live (20 CLXIII logs, 894 post-play decisions): the next decision comes 26 ticks after the
        # play decision in 50% of plays (24-28 in 77%), then every 10 ticks from there; the SIM's grid made it 30. Absent = byte-identical.
        self.play_resume = cfg.get("play_resume")
        if self.play_resume not in (None, "land"):
            raise ValueError(f"cfg['play_resume'] is 'land' or absent, got {self.play_resume!r}")
        if self.play_resume and (not self.delay or self.pipe or cfg.get("follow_ups")):
            raise ValueError("cfg['play_resume'] needs action_delay_ticks > 0 and neither pipeline_decisions nor follow_ups")
        if self.tap_hold is not None and (not self.delay or self.pipe or cfg.get("follow_ups")):
            raise ValueError("cfg['tap_hold'] needs action_delay_ticks > 0 and neither pipeline_decisions nor follow_ups")
        if self.tap_loss is not None:
            self._tl_rng = random.Random(zlib.crc32(f"{tag}:tap_loss".encode()))
        if self.tap_slow is not None:
            self._ts_rng = random.Random(zlib.crc32(f"{tag}:tap_slow".encode()))

    def _opp_plays(self) -> list:
        return self.other.accepted

    def apply(self, p: float, d: dict) -> None:
        tick = self._record(p, d)
        if getattr(self.env, "hero_abilities", False):
            for side, commands in self._ability_commands.items():
                self.env.queue_abilities(side, commands, self.delay)
        if getattr(self, "timing", False):                    # gate_decode 'timing_head' (timing_decide_batch)
            if d.get("th_tick"):                              # a play drawn for tick j of this slot: decide then
                self._th_slot, self.next_tick = tick, tick + int(d["th_tick"])
                return
            if d["play"]:
                self._land(p, d, tick, True)                  # issued now; crforge runs it its own delay later
            slot, self._th_slot = (tick if self._th_slot is None else self._th_slot), None
            self.next_tick = slot + self.cfg["decide_every"]  # the next slot, whatever the engine still holds
            return
        de, delay = self.cfg["decide_every"], self.delay
        eng = int(getattr(self.env, "engine_delay_ticks", 0))   # crforge's own command delay; 0 on RoyaleSim
        if "_opp_style" in self.cfg:
            delay += int(d.get("_style_delay", 0))
        if d["play"] and d.get("follow_ups"):                 # follow_up_spec second plays: the ghost Match's rules (module comment)
            if not delay:
                raise ValueError("follow_ups need cfg['action_delay_ticks'] > 0 in a SelfPlaySide")
            d, extra = self._tap_draw(d, tick)                # G2: each tap draws its own loss / slowness (first here,
            self._follow_start(p, d, tick, extra)             # each fired follow-up in _follow_check)
            if self.pipe:   # + cfg["pipeline_decisions"] (L74 fastplays P2, as live --follow-up-taps + --pipeline-decisions, live_play
                # ~1306): no decision while a follow-up is scheduled (_follow_start); once resolved, _follow_resolved resumes on the
                # reader-frame grid with fewer than FOLLOW_MAX_OUT plays out; the decision right after a play accrues no hazard step
                self._pipe_ready = tick + int(self.cfg.get("follow_arrival_ticks", FOLLOW_ARRIVAL_TICKS))
                self._hz_step_ticks = 0
            return
        if self.pipe:                                         # cfg["pipeline_decisions"]: plays wait in self.pend (SelfPlayMatch.due
            self._pipe_decided(p, d, tick)                    # lands them); the next decision is on the reader-frame grid
            self.next_tick = self._pipe_next_tick(tick)
            if self.pend and self._hz_step_ticks is None:
                self._hz_step_ticks = self.next_tick - tick
            return
        if d["play"] and delay:
            d, extra = self._tap_draw(d, tick)
            delay += extra
            self.pending = (tick + delay, p, d)
            self.next_tick = (tick + delay + eng + 1) if self.play_resume else tick + de * ((delay + eng) // de + 1)   # crforge: none until the engine runs it (Match.apply)
            return
        if d["play"]:
            self._land(p, d, tick, True)
        self.next_tick = tick + de * (eng // de + 1) if (d["play"] and eng) else tick + de

    def _tap_draw(self, d: dict, tick: int) -> tuple:
        """One tap's cfg["tap_loss"] / cfg["tap_slow"] draws (W18 G2; no key = no draw): -> (decision, extra landing ticks)."""
        extra = 0
        if self.tap_loss is not None and self._tl_rng.random() < tap_loss_p(self.tap_loss, tick):
            d = dict(d, _tap_lost=True)                       # cfg["tap_loss"]: _land refuses it at landing
        if self.tap_slow is not None and self._ts_rng.random() < self.tap_slow[0]:
            extra = self.tap_slow[1]                          # cfg["tap_slow"]: this play lands late
            self.n_tap_slow += 1
        return d, extra

    # ---- follow_ups (the ghost Match._apply_follow_ups' rules, event-driven: SelfPlayMatch.due calls _follow_check) ----------------
    def _fresh_players(self) -> list:
        return self.env.raw()["players"]

    def _follow_start(self, p: float, d: dict, tick: int, extra: int = 0) -> None:
        """The first play lands at tick + delay (SelfPlayMatch.due); each follow-up is evaluated by _follow_check on the reader-frame
        grid from the first frame at or after its due tick AND after the first tap returned; my next decision is only taken once all
        of them are resolved and landed (the first grid tick after the last landing, as Match.apply)."""
        arrival = int(self.cfg.get("follow_arrival_ticks", FOLLOW_ARRIVAL_TICKS))
        grid = lambda x: tick + -(-(x - tick) // FOLLOW_FRAME_TICKS) * FOLLOW_FRAME_TICKS      # noqa: E731
        land_a = tick + self.delay + extra                   # extra: cfg["tap_slow"] drew this first tap late (_tap_draw)
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
                db, extra = self._tap_draw({"play": True, "slot": fu["slot"], "cell": fu["cell"], "why": "follow_up"}, t)
                land_b = max(fu0["land_a"] + max(t - fu0["tick"] - fu0["arrival"], 0), t + 1) + extra
                self.pend.append((land_b, fu0["p"], db, fu0["cur"]))
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
            if self.pipe:   # pipeline_decisions: the reader-frame grid from now, < FOLLOW_MAX_OUT plays out (live_play ~1306)
                self.next_tick = self._pipe_next_tick(int(self.env.tick))

    def _land(self, p: float, d: dict, land: int, landed: bool, cur=None) -> bool:
        from pipeline.dataset_gen import card_key
        acc = super()._land(p, d, land, landed, cur)
        fu0 = getattr(self, "_fu", None)
        if fu0 is not None and d is fu0["d"]:                 # the first play of an open follow-up plan landed (or was refused)
            fu0["a_landed"], fu0["a_acc"] = True, acc
        if acc:
            # the other side's counter sees it when the engine runs it: + crforge's own delay (0 on RoyaleSim)
            self.accepted.append((int(land) + int(getattr(self.env, "engine_delay_ticks", 0)), str(card_key(self.engine_deck[self.deck_index_of_slot[d["slot"]]]))))
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


def opp_tempo(cfg: dict, decide_every=None, reaction_ticks=None) -> dict:
    """L74 human tempo (opt-in; both None = ``cfg`` itself, byte-identical): a SelfPlayMatch OPPONENT side's cfg with its
    own decision interval ``decide_every`` (ticks, int > 0) and ``reaction_ticks`` (int >= 0) added to its action delay,
    so its play lands action_delay_ticks + reaction_ticks after its decision (SelfPlaySide.apply's delayed-play rule; its
    hero-ability presses queue with the same delay). Never apply it to the learner's cfg. No grid constraint: each side
    schedules from its OWN cfg (SelfPlaySide.next_tick) and SelfPlayMatch.due advances the env to the earliest; the env's
    decision_ticks only seeds ability_policy v2's first per-side press dt (royale_env.ability_commands)."""
    if decide_every is None and reaction_ticks is None:
        return cfg
    for name, v, lo in (("opp_decide_every", decide_every, 1), ("opp_reaction_ticks", reaction_ticks, 0)):
        if v is not None and (type(v) is not int or v < lo):
            raise ValueError(f"{name} must be an int >= {lo}, got {v!r}")
    out = dict(cfg)
    if decide_every is not None:
        out["decide_every"] = decide_every
    if reaction_ticks:
        out["action_delay_ticks"] = int(cfg.get("action_delay_ticks") or 0) + reaction_ticks
    return out


class UnsupportedProbeDeck(ValueError):
    """search_s0 --probe-xbow-start: the opponent deck lacks the probe's building / ground troop (redrawn, seeded)."""


def forced_name(deck, card: str) -> str:
    """W18 R4: the engine name (form suffix stripped) of ``deck``'s card matching ``card`` (case / punctuation-free)."""
    key = lambda n: str(n["name"] if isinstance(n, dict) else n).split("@")[0]  # noqa: E731
    norm = lambda n: "".join(ch for ch in n.lower() if ch.isalnum())  # noqa: E731
    hit = [key(n) for n in deck if norm(key(n)) == norm(card)]
    if not hit:
        raise ValueError(f"forced card {card!r} not in deck {list(deck)}")
    return hit[0]


TAP_LOSS_WINDOWS = (("1x", 0, 2400), ("2x", 2400, 3600), ("ot2x", 3600, 4800), ("ot3x", 4800, 10 ** 9))


def parse_tap_loss(spec) -> Optional[dict]:
    """L74 W18 (opt-in; None / '' = off): the LIVE pilot's lost-tap rate, applied to a SelfPlaySide in the SIM.
    ``spec`` = 'NAME:P,...' or {NAME: P} with NAME in TAP_LOSS_WINDOWS (1x / 2x / ot2x / ot3x, by decision tick) and
    0 <= P < 1; an unnamed window is 0. -> {NAME: P} for all four windows."""
    if not spec:
        return None
    if isinstance(spec, str):
        try:
            spec = {k.strip(): float(v) for k, v in (x.split(":") for x in spec.split(",") if x.strip())}
        except ValueError:
            raise ValueError(f"tap_loss: 'NAME:P,...' expected, got {spec!r}") from None
    names = [w for w, _, _ in TAP_LOSS_WINDOWS]
    bad = sorted(set(spec) - set(names))
    if bad:
        raise ValueError(f"tap_loss: unknown window(s) {bad}; use {names}")
    out = {w: float(spec.get(w, 0.0)) for w in names}
    if any(isinstance(spec.get(w), bool) or not 0.0 <= out[w] < 1.0 for w in names):
        raise ValueError(f"tap_loss: every P must be in [0, 1), got {spec!r}")
    return out


def tap_loss_p(rates: dict, tick: int) -> float:
    return next(rates[w] for w, a, b in TAP_LOSS_WINDOWS if a <= tick < b)


def parse_tap_slow(spec) -> Optional[tuple]:
    """L74 W18 (opt-in; None / '' = off): the live pilot's SLOW taps -- with probability P a decided play lands EXTRA ticks
    after the action delay (live: 17% of plays land at 36-59 ticks instead of 24-28). ``spec`` = 'P:EXTRA' or (P, EXTRA),
    0 <= P < 1, EXTRA an int >= 1. -> (P, EXTRA)."""
    if not spec:
        return None
    try:
        p, x = (spec.split(":") if isinstance(spec, str) else spec)
        p, x = float(p), int(x)
    except (ValueError, TypeError):
        raise ValueError(f"tap_slow: 'P:EXTRA' expected, got {spec!r}") from None
    if not 0.0 <= p < 1.0 or x < 1:
        raise ValueError(f"tap_slow: need 0 <= P < 1 and EXTRA >= 1, got {spec!r}")
    return p, x


def parse_tap_hold(spec) -> Optional[int]:
    """RECON-7 (opt-in; None / 0 / '' = off): the game's HOLD of a tap that cannot pay yet -- a not-enough-elixir refusal at landing is
    retried each tick for ``spec`` ticks (an int >= 1; live: ~22, scratchpad/gauntlet/L74/latency/afford_arrival.txt)."""
    if not spec:
        return None
    try:
        n = int(spec)
    except (ValueError, TypeError):
        raise ValueError(f"tap_hold: an int >= 1 expected, got {spec!r}") from None
    if n < 1 or isinstance(spec, bool):
        raise ValueError(f"tap_hold: an int >= 1 expected, got {spec!r}")
    return n


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
        kw = {}
        if "opp_tower" in spec:                 # L74 troops (opt-in): the OPPONENT's crown tower troop; ours = Princess
            kw["tower_troops"] = [None, spec["opp_tower"]] if L == 0 else [spec["opp_tower"], None]
        if "levels" in spec:                    # L74 factor D (opt-in): rl_royale.draw_live_levels, learner / opp -> sides
            lv = {L: spec["levels"]["learner"], 1 - L: spec["levels"]["opp"]}
            kw["levels"] = {"cards": [lv[0]["cards"], lv[1]["cards"]], "towers": [lv[0]["tower"], lv[1]["tower"]]}
        if "start" in spec:                     # W15 lever 2 (opt-in): rl_royale.draw_ot_start, learner / opp -> sides
            st = {L: spec["start"]["learner"], 1 - L: spec["start"]["opp"]}
            kw["start"] = {"tick": spec["start"]["tick"], "princess": [st[0]["princess"], st[1]["princess"]],
                           "elixir": [st[0]["elixir"], st[1]["elixir"]]}
            hf, side_of = {}, {"learner": L, "opp": 1 - L}
            f = spec["start"].get("force")
            if f:                               # W18 R4 (rl_royale.draw_xbow_start): the forced card is in that side's hand
                role = f.get("side", "opp")
                hf[side_of[role]] = forced_name(decks[side_of[role]], f["card"])
            for role, card in (spec["start"].get("hand") or {}).items():   # W18 P-D: a card dealt into a side's hand
                hf[side_of[role]] = forced_name(decks[side_of[role]], card)
            if hf:
                kw["start"]["hand_first"] = hf
        if getattr(env, "spell_tracker", None) is not None:  # rl_royale spell_value (opt-in): a reused env's old tracker
            env.spell_tracker = None
        env.reset(decks[0], decks[1], int(spec["seed"]), **kw)
        if cfg.get("spell_track"):                           # ... and this match's: the learner's Rocket impacts
            from pipeline.spell_value import SpellTracker
            env.spell_tracker = SpellTracker(env, L)
        if cfg.get("crown_track"):                           # rl_royale crown terms / search_s0 --crown-log (opt-in):
            from pipeline.reward_terms import CrownTracker    # read-only stops on the learner's crown towers + Tornados
            ct = str(cfg.get("crown_track"))                  # True / "rocket_dmg" / "king" / "rocket_dmg+king" (Plan A)
            self.crown = CrownTracker(env, L, rocket_dmg="rocket_dmg" in ct.split("+"),   # W10 rocket_tower / rocket_cycle
                                      king="king" in ct.split("+"),                       # Plan A king_redirect
                                      troop="troop" in ct.split("+"))                     # Plan A rocket_cycle
        tag = str(spec["tag"])
        self.learner = SelfPlaySide(env, spec["learner_deck"], L, tag, k, cfg, learner)
        from pipeline.adaptive_opponents import style_config
        if not is_timing(opponent):                          # lead 10-30: P2 timing-head opponents play unstyled
            opp_cfg = style_config(opp_cfg, int(spec["seed"]), int(k))   # (timing_cfg refuses _opp_style)
        self.opp = SelfPlaySide(env, spec["opp_deck"], 1 - L, f"{tag}:opp", k, opp_cfg, opponent)
        self.learner.other, self.opp.other = self.opp, self.learner
        self.sides = sorted((self.learner, self.opp), key=lambda s: s.side)
        if cfg.get("habit_track"):                           # rl_royale habit terms (opt-in): read-only board samples at
            from pipeline.habit_terms import HabitTracker     # the learner's decision stops (search_s0 --record-board rule)
            self.habit = HabitTracker(L)
        self.forced = None
        if "start" in spec and spec["start"].get("force"):
            f = spec["start"]["force"]
            self._force(f, spec["learner_deck"] if f.get("side", "opp") == "learner" else spec["opp_deck"])

    def _force(self, f: dict, opp_deck) -> None:
        """W18 R4: the OPPONENT side's first act at the scenario start = ``f["card"]`` at ``f["board"]`` (its own board frame,
        [x, y] in [0, 1], me at the bottom), straight into the engine at the start tick (the live play had already been
        decided); the learner's opponent-elixir counter sees it as an accepted play. ``self.forced`` = accepted or not."""
        from pipeline import engine_play as ep
        from pipeline.dataset_gen import card_key
        o, env = (self.learner if f.get("side", "opp") == "learner" else self.opp), self.env   # P-D: the learner side
        name = forced_name(opp_deck, f["card"])
        idx = next(i for i, n in enumerate(env.decks[o.side]) if n == name)
        X, Y = ep.board_to_engine(float(f["board"][0]), float(f["board"][1]), o.mirror)
        r = env.eng.act(side=o.side, deck_index=idx, x=int(round(X)), y=int(round(Y)))
        self.forced = bool(r.get("accepted"))
        if self.forced:
            o.accepted.append((int(env.tick), str(card_key(o.engine_deck[idx]))))
            o.last_play_tick = int(env.tick)

    def due(self) -> list[SelfPlaySide]:
        env = self.env
        crown = getattr(self, "crown", None)                 # crown_track only (a search_s0 fork never has one)
        while True:
            if crown is not None:                            # every stop, before its plays land: never steps the engine
                crown.observe(env.core.state())
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
                if getattr(self, "habit", None) is not None and self.learner in ds:   # habit_track: read only
                    self.habit.observe(raw, self.learner)
                return ds
            nxt = min([s.next_tick for s in self.sides] + [s.pending[0] for s in self.sides if s.pending]
                      + [s.pend[0][0] for s in self.sides if s.pend]
                      + [task["next_check"] for s in self.sides for task in s.fu_tasks])
            env._advance_to(min(nxt, env.tail_cap))

    def result(self) -> dict:
        r = self.learner.result()
        if getattr(self, "forced", None) is not None:          # W18 R4: the forced opening act landed or not
            r["forced_start"] = self.forced
        t0 = int((getattr(self.env, "scenario_start", None) or {}).get("tick", 0))   # W15 lever 2: played time only
        o, minutes = self.opp, (self.env.tick - t0) * TICK_S / 60.0
        r["league"] = dict(self.spec)
        if "_opp_style" in o.cfg:
            r["opp_style"] = dict(o.cfg["_opp_style"])
        r["opp_side"] = {"side": o.side, "policy": o.cfg["policy"], "plays_attempted": o.n_att,
                         "plays_accepted": o.n_acc, "plays_per_min": round(o.n_att / minutes, 3) if minutes else None,
                         "stall_fired": o.n_stall, "decisions": o.n_dec}
        if getattr(self.env, "spell_tracker", None) is not None:   # rl_royale spell_value: the learner's Rocket events
            r["spell"] = list(self.env.spell_tracker.events)
        if getattr(self, "crown", None) is not None:          # crown_track: reward_terms.CrownTracker.result
            r["crown"] = self.crown.result()
        if getattr(self, "habit", None) is not None:          # habit_track: habit_terms.HabitTracker.result
            r["habit"] = self.habit.result(self.learner)
        if getattr(self, "cf_state", None) is not None:       # rl_royale cf_credit: the fork samples (cf_credit.Runner)
            from pipeline.cf_credit import match_record
            r["cf"] = match_record(self.cf_state)
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
                                  {**ocfg, **{x: v for x, v in over.items()
                                             if x not in ("obs_seed", "pipeline_decisions", "pipeline_tau_delta")},
                                   "entry_index": i},
                                  learner, opp)
            except skip as exc:
                free.append(env)
                if on_skip:
                    on_skip(spec, exc)
                continue
            live.append(m)

    # rl_royale cf_credit (opt-in; no cfg["cf"] = None = this loop exactly as before): SIM forks at selected learner decisions
    cf = None
    if cfg.get("cf"):
        from pipeline.cf_credit import Runner
        cf = Runner(make_env, cfg["cf"])
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
        todo = selfplay_decide(due)
        if cf is not None:                                  # forks only: the real sides / decisions are never touched
            cf.hook(live, todo)
        for s, pr, d in todo:
            s.apply(pr, d)


def selfplay_decide(due) -> list:
    """``run_selfplay_batch``'s per-round decide on PREPARED sides: ONE forward + one batched decide per policy group
    (the learner, each frozen / styled opponent), each side on its own cfg and RNGs. -> [(side, p_gate, decision)] in
    group order (the apply order). cf_credit's fork rollouts call it on their fork sides."""
    groups: dict = {}
    for s in due:
        # A caller may reuse a policy object for both sides; style decode
        # must still never enter the learner's group.
        key = (id(s.model), "opponent_style") if "_opp_style" in s.cfg else id(s.model)
        groups.setdefault(key, []).append(s)
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
        if "_opp_style" in c:
            from pipeline.adaptive_opponents import styled_decisions
            decisions = styled_decisions(model, enc, heads, p, allowed, stalled, sides)
        elif c["policy"] == "live":                     # (rl_royale C1: posture_live; no posture = unchanged)
            ability_decide(sides, enc, c)               # rl_royale ability_head, greedy (no cfg key = no-op)
            tau, kw = posture_live(sides, enc, c, c["tau"], match_kwargs(sides))
            decisions = live_decide_batch(model, enc, heads, p, allowed, stalled, tau=tau, device=c["device"], **kw)
        else:
            decisions = sample_decide_batch(model, enc, heads, p, allowed, stalled, sides, c)
        todo += [(s, p[r], decisions[r]) for r, s in enumerate(sides)]
    return todo


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
