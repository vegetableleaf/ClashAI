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
NOISE_ALIASES = {"scalars": ("my_elixir", "opp_elixir", "king_hp")}   # O5: pre-split spelling, kept for old
                                                                        # CLI invocations and recorded run.json

TAU_LIVE = 0.27
STALL_ELIXIR_LIVE = 9.0
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
OPP_TRACE_EVERY = 20                          # result()["opp_counter"]["trace"]: one (tick, est, truth) per N decisions
# cfg["action_delay_ticks"] D (L68 T9; unset/0 = today, byte-identical): live deploy lag. A play decided on the board
# at tick T enters the engine at T + D (live_play.py: tap -> registered ~24-27 ticks later) at the cell chosen at T.
# While pending there are no decisions, the card stays in hand and no elixir is spent (Match.apply advances straight
# to T + D, acts, then on to the first decide_every grid tick after T + D). Past plays / the anti-stall clock use the
# LANDING tick. A refusal at landing is counted (refuse_reasons, plays_refused_at_landing), never retried; a match
# that ends first counts plays_unlanded ("match_over_before_landing").


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
    and recorded run.json ``"noise_off": ["scalars"]`` still parse the same way; '' -> all ON (unchanged
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
                device: str = "cpu") -> dict:
    """The live student's choice (student_live.py:161-236) on precomputed heads:
    no allowed slot -> WAIT ('no_affordable'); slot = argmax over allowed of the hand-masked card logits;
    p <= tau and not stalled -> WAIT; else cell = argmax of the card-conditioned cell logits."""
    import torch
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
                       device: str = "cpu") -> list[dict]:
    """``live_decide`` over every row of a shared forward at once. The card argmax and the p-vs-tau compare are
    elementwise (bit-identical to a per-row loop); ONE ``cell_logits`` call covers every row that plays, so this
    is O(1) GPU calls per round, not O(matches) (L68e)."""
    import torch
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

    def forward_batch(self, rows: Sequence[dict], device: str = "cpu"):
        """``model_forward_batch``'s contract for gen rows -> (enc, heads, p [B], hand bool [B, 8]); heads["card"] is
        [B, 8] over deck slots, heads["card_hand"] the raw [B, 4] pointer logits."""
        import torch
        keys = ("tok", "mask", "sc", "past", "hand_card", "hand_form", "next_card", "next_form", "deck_card",
                "deck_form", "hand_slot", "slot_card", "slot_form")
        with torch.no_grad():
            b = {k: torch.from_numpy(np.ascontiguousarray(np.stack([r[k] for r in rows]))).to(device) for k in keys}
            enc = self.model.encode_gen(b)
            h = self.model.heads_gen(enc, b)
            B = h["card"].shape[0]
            card = torch.full((B, N_SLOTS + 1), float("-inf"), dtype=h["card"].dtype, device=h["card"].device)
            card = card.scatter(1, b["hand_slot"], h["card"])[:, :N_SLOTS]   # col 8 = unknown positions, dropped
            hand = torch.zeros(B, N_SLOTS + 1, dtype=torch.bool, device=card.device)
            hand = hand.scatter(1, b["hand_slot"], True)[:, :N_SLOTS]        # = model_v3.hand_mask_from_sc(sc)
            enc = {**enc, "slot_card": b["slot_card"], "slot_form": b["slot_form"]}
            heads = {"gate": h["gate"], "card": card, "card_hand": h["card"]}
            p = torch.sigmoid(h["gate"]).cpu().tolist()
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
    from pipeline.eval_gen import load_model
    model, st = load_model(ckpt, torch.device(device))
    model.eval()
    return GenPolicy(model, st["card_vocab"]), {"gen": True, "epoch": st.get("epoch"), "n_params": st.get("n_params"),
                                                 "deck": st.get("deck"), "grid": str(st["args"].get("grid", "lattice"))}


# ------------------------------------------------------------------------------------------------------
# one match
# ------------------------------------------------------------------------------------------------------
def _slot_maps(env, deck, entry) -> tuple[list[str], dict[int, int], list[float]]:
    side = env.side
    engine_deck = [f"{it['name']}@{it['form']}" if it["form"] != "base" else str(it["name"]) for it in env.final_decks[side]]
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
        from pipeline import engine_play as ep
        self.ep, self.env, self.deck, self.entry, self.k, self.cfg = ep, env, deck, entry, int(k), cfg
        self.t0 = time.perf_counter()
        self.delay = int(cfg.get("action_delay_ticks") or 0)
        if self.delay < 0:
            raise ValueError(f"cfg['action_delay_ticks'] {self.delay} < 0")
        self.n_unlanded = 0
        self.opp_mode = cfg.get("opp_elixir")
        if self.opp_mode:
            if self.opp_mode not in OPP_ELIXIR_MODES:
                raise ValueError(f"cfg['opp_elixir'] {self.opp_mode!r} not in {OPP_ELIXIR_MODES}")
            from pipeline.opp_elixir_count import OppElixirCounter
            tap_ghost_deliveries(env)
            self.opp_counter = OppElixirCounter()
            self.opp_i = self.opp_fed = self.opp_dropped = 0
            self.opp_err: list[float] = []
            self.opp_trace: list[list] = []
        self.state = env.reset(entry)
        self.side, self.mirror = env.side, env._mirror
        self.engine_deck, self.deck_index_of_slot, self.costs = _slot_maps(env, deck, entry)
        self.tag = str(entry["tag"])
        obs_s = cfg.get("obs_seed")                          # RL actor override; default = today's per-(tag,k) seed
        self.obs_seed_used = int(obs_s) if obs_s is not None else obs_seed(self.tag, k)   # recorded by result()
        self.rng_obs = np.random.default_rng(self.obs_seed_used)
        self.rng_rand = random.Random(random_seed(self.tag, k))
        self.rng_behave = np.random.default_rng(
            behave_seed(self.tag, int(cfg.get("rollout_index", 0)), int(cfg.get("update", 0))))
        self.unmapped: set = set()
        self.done_plays: list[tuple[int, int, float, float]] = []
        self.last_play_tick: Optional[int] = None
        self.n_dec = self.n_deg = self.n_att = self.n_acc = self.n_stall = self.n_noaff = 0
        self.p_gates: list[float] = []
        self.plays: list[dict] = []
        self.traj: list[dict] = []                           # cfg["record"]: per-decision rows, see result()
        self.refuse: Counter = Counter()
        self.mix_att: Counter = Counter()
        self.mix_acc: Counter = Counter()
        self.done = False

    def prepare(self):
        """-> (tok, mask, sc, past) for the current state."""
        cfg = self.cfg
        tick = int(self.env.tick)
        if self.last_play_tick is None:
            self.last_play_tick = tick                       # match start = first decision (anti-stall clock)
        bs = from_engine(self.ep.compact_raw(self.state), self.side, self.deck, engine_deck=self.engine_deck,
                         unmapped=self.unmapped)
        view = live_view(bs, self.rng_obs, self.deck, cfg["noise"]) if cfg["obs"] == "live" else bs
        if self.opp_mode:
            est = self.opp_estimate(tick)
            if bs.opp_elixir is not None:                    # truth read for the result's error log ONLY
                self.opp_err.append(est - bs.opp_elixir)
                if self.n_dec % OPP_TRACE_EVERY == 0:
                    self.opp_trace.append([tick, round(est, 3), round(bs.opp_elixir, 3)])
            view = dc_replace(view, opp_elixir=est)
        self.n_deg += int(view.source == "degraded")
        tok, mask, sc = to_tokens(view, MAX_U)
        past = _past(self.done_plays, tick)
        self._cur = (tick, bs, view)
        self._obs = (tok, mask, sc, past)                    # kept for cfg["record"] (see apply())
        return tok, mask, sc, past

    def opp_estimate(self, tick: int) -> float:
        """cfg["opp_elixir"]: feed the counter the ghost plays delivered at ticks <= ``tick`` not yet fed (kept per
        ``opp_play_kept``), then its estimate at ``tick``. Reads only ``env.opp_delivered``, never a state."""
        from pipeline.opp_elixir_count import card_cost
        dl = self.env.opp_delivered
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

    def gen_row(self, policy: GenPolicy) -> dict:
        """The current prepared state as a generalist row (``GenPolicy.row``); call after ``prepare``."""
        return policy.row(*self._obs, *policy.slot_ident(self.engine_deck, self.deck_index_of_slot))

    def pre(self, hand) -> tuple[float, np.ndarray, bool]:
        """(a): el_int, allowed, stalled for the current prepared state -- shared by every decide path (live,
        sample; random/none use their own affordability rule, unchanged)."""
        cfg, policy = self.cfg, self.cfg["policy"]
        tick, bs, view = self._cur
        el_int = float(int(view.my_elixir))
        live_like = policy in ("live", "sample")
        allowed = allowed_slots(hand, self.costs, el_int,
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
            return live_decide(model, enc, heads, p, allowed, tau=cfg["tau"], stalled=stalled, device=device)
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
        cfg, env, ep = self.cfg, self.env, self.ep
        tick, bs, view = self._cur
        grid = cfg["grid"]
        self.n_dec += 1
        self.p_gates.append(p)
        if cfg.get("record") and "lp_gate" in d:              # only the sample decide dicts carry these keys
            tok, mask, sc, past = self._obs
            self.traj.append({"tok": tok, "mask": mask, "sc": sc, "past": past, "allowed": d["allowed"],
                              "stalled": d["stalled"], "gate_sampled": d["gate_sampled"], "played": d["play"],
                              "slot": d["slot"], "cell": d["cell"], "lp_gate": d["lp_gate"], "lp_card": d["lp_card"],
                              "lp_cell": d["lp_cell"], "p_gate": d["p_gate"], "T": d["T"]})
        if d["why"] == "no_affordable":
            self.n_noaff += 1
        delay = self.delay
        if d["play"]:
            el_int = float(int(view.my_elixir))
            self.n_att += 1
            self.n_stall += int(d["why"] == "stall")
            x, y = ep.cell_center(d["cell"], grid)
            X, Y = ep.cell_to_engine(d["cell"], self.mirror, grid)
            land = tick + delay                               # cfg["action_delay_ticks"]: the play enters here
            if delay:                                         # pending: board runs on, card in hand, elixir unspent,
                env._advance_to(min(land, env.tail_cap))      # no decisions (the whole wait is inside this call)
            landed = not (delay and (env.terminated or env.tick < land))   # False: match over before it landed
            r = env.eng.act(side=self.side, deck_index=self.deck_index_of_slot[d["slot"]], x=X, y=Y) if landed \
                else {"accepted": False}
            acc = bool(r["accepted"])
            code = int(r.get("result_code", -1))
            card = self.deck.cards[d["slot"]]
            self.mix_att[card] += 1
            rec = {"tick": tick, "slot": d["slot"], "card": card, "cell": d["cell"], "p": round(p, 4), "why": d["why"],
                   "elixir": el_int, "elixir_exact": round(float(bs.my_elixir), 3), "accepted": acc}
            if delay:
                rec["land_tick"] = land
            if acc:
                self.n_acc += 1
                self.mix_acc[card] += 1
                self.done_plays.append((land, d["slot"], x, y))  # past: LANDING tick + position, as training's rows
                self.last_play_tick = land
            elif not landed:
                self.n_unlanded += 1
                self.refuse["match_over_before_landing"] += 1
                rec["reason"] = "match_over_before_landing"
            else:
                # RoyaleSim names its own codes (e.g. 2008 -> out_of_territory); the real engine path keeps
                # engine_play's table, which differs from PoolV1Env's _code_names at 13 and 22 (names unchanged).
                names = env._code_names if type(env).__name__ == "RoyalePoolEnv" else ep.RESULT_CODE_NAMES
                nm = names.get(code, f"native_{code}")
                if r.get("placement_valid") is False:
                    nm = f"{nm}/{r.get('placement_reason')}"
                self.refuse[nm] += 1
                rec["reason"] = nm
            self.plays.append(rec)
        de = cfg["decide_every"]
        # after a delayed play the next decision is the first decide_every grid tick AFTER landing (delay 0: tick + de)
        env._advance_to(min((tick + de * (delay // de + 1)) if (delay and d["play"]) else env.tick + de, env.tail_cap))
        self.state = env.eng.observe()
        self.done = bool(env.terminated) or env.tick >= env.tail_cap

    def result(self) -> dict:
        env, entry, cfg, tag, k = self.env, self.entry, self.cfg, self.tag, self.k
        outcome, crowns = self.ep._outcome(env, self.state)
        minutes = env.tick * TICK_S / 60.0
        end = int(env.tick)
        last_ghost = int(entry.get("last_ghost_tick") or 0)
        after_script = end > last_ghost + SCRIPT_MARGIN_TICKS
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
            "last_ghost_tick": last_ghost, "after_script": bool(after_script),
            "won_after_script": bool(after_script and outcome == "win"),
            "ghost_plays": int(entry.get("ghost_plays") or 0), "ghost_delivered": int(env.ghost_ok),
            "ghost_refused": int(env.ghost_rejected), "ghost_undelivered": int(env.ghost_undelivered()),
            "ghost_distinct_delivered": len(env.ghost_cards_delivered), "ghost_refuse_reasons": dict(env.ghost_reject_reasons),
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
            **({"opp_counter": self._opp_summary()} if self.opp_mode else {}),
            **({"action_delay_ticks": self.delay, "plays_unlanded": self.n_unlanded,
                "plays_refused_at_landing": n_att - n_acc - self.n_unlanded} if self.delay else {}),
        }

    def _opp_summary(self) -> dict:
        """cfg["opp_elixir"]: counter bookkeeping + estimate-minus-TRUE-elixir over this match's decisions (a
        diagnostic; the truth never reaches the estimate) and a (tick, est, truth) sample every OPP_TRACE_EVERY."""
        e = np.asarray(self.opp_err, dtype=np.float64)
        c = self.opp_counter
        return {"mode": self.opp_mode, "fed": self.opp_fed, "dropped": self.opp_dropped,
                "undelivered_to_counter": len(self.env.opp_delivered) - self.opp_i,
                "rebases": c.rebases, "rebase_total": round(c.rebase_total, 3),
                "mae": round(float(np.abs(e).mean()), 4) if len(e) else None,
                "bias": round(float(e.mean()), 4) if len(e) else None, "n": int(len(e)), "trace": self.opp_trace}

    def _traj_arrays(self) -> dict:
        """cfg["record"]: this match's ``traj`` rows stacked into numpy arrays (rl_plan.md 3.3's per-decision
        list). Empty (0 decisions recorded -- e.g. cfg["record"] with a non-sample policy) -> empty arrays that keep
        each key's trailing shape (tok (0, 64, F), mask (0, 64), sc (0, S), past (0, PAST_K, 4), allowed (0, 8))."""
        tj = self.traj
        empty = {"tok": (MAX_U, TOK_F), "mask": (MAX_U,), "sc": (SC_S,), "past": (PAST_K, 4), "allowed": (N_SLOTS,)}
        stack = (lambda k: np.stack([t[k] for t in tj])) if tj else (lambda k: np.zeros((0, *empty[k]), dtype=np.float32))
        scalar = (lambda k, dt: np.array([t[k] for t in tj], dtype=dt))
        return {"tok": stack("tok").astype(np.float32), "mask": stack("mask").astype(bool),
                "sc": stack("sc").astype(np.float32), "past": stack("past").astype(np.float32),
                "allowed": stack("allowed").astype(bool),
                "stalled": scalar("stalled", bool), "gate_sampled": scalar("gate_sampled", bool),
                "played": scalar("played", bool), "slot": scalar("slot", np.int64), "cell": scalar("cell", np.int64),
                "lp_gate": scalar("lp_gate", np.float64), "lp_card": scalar("lp_card", np.float64),
                "lp_cell": scalar("lp_cell", np.float64), "p_gate": scalar("p_gate", np.float64),
                "T": scalar("T", np.float64)}


def run_match(env, model, deck, entry: dict, k: int, cfg: dict) -> dict:
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
    if gen and cfg.get("record"):                        # traj stores S1 rows; the RL learner cannot use them for gen
        raise ValueError("cfg['record'] is S1-only: a GenPolicy trajectory would store the wrong input rows")
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
            decisions = live_decide_batch(model, enc, heads, p, allowed, stalled, tau=cfg["tau"],
                                          device=cfg["device"]) if policy == "live" else \
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
    if a.mode == "eval" and a.ckpt is None:
        raise SystemExit("--mode eval needs --ckpt")
    shard = parse_shard(a.shard)
    seeds = [0] if a.mode in ("parity", "liveness") else parse_seeds(a.seeds)
    noise = parse_noise_off(a.noise_off)                  # validated up front, same as shard/seeds above
    noise_off = noise_off_names(noise)
    stall_elixir = None if str(a.stall_elixir).lower() == "none" else float(a.stall_elixir)
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
    run = {"argv": sys.argv[1:] if argv is None else list(argv), "args": {k: str(v) for k, v in vars(a).items()},
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
           "decide_every": int(a.decide_every), "slot": slot, "port": int(a.port), "T": float(a.sample_T)}
    print(json.dumps({"e1_eval": a.mode, "policy": a.policy, "port": a.port, "tasks": len(tasks),
                      "already_done": len(done_keys), "grid": cfg["grid"], "tau": cfg["tau"],
                      "noise_off": noise_off}), flush=True)

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
