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
import random
import sys
import time
import zlib
from collections import Counter
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import vocab                                                        # noqa: E402
from pipeline.dataset import _past                                                # noqa: E402
from pipeline.e1_pool import POOL_V1, load_pool_v1, ours, select_split, sha256_file  # noqa: E402
from pipeline.e1_view import live_view                                            # noqa: E402
from pipeline.obs_contract import TICK_S, from_engine, load_deck, to_tokens       # noqa: E402

TAU_LIVE = 0.27
STALL_ELIXIR_LIVE = 9.0
STALL_SECONDS_LIVE = 12.0
DECIDE_EVERY = 10
MAX_U = 64
N_SLOTS = 8
GRID_X, GRID_Y = 36, 64                       # model_v3.GRID_X / GRID_Y (not imported: model_v3 pulls torch)
SCRIPT_MARGIN_TICKS = 200                     # design 4.2.1: "outlived the script" = end > last ghost tick + 200
SLOT_OF_PORT = {38031: 0, 38032: 1, 37031: 0, 37032: 1}


# ------------------------------------------------------------------------------------------------------
# pure helpers (tested offline)
# ------------------------------------------------------------------------------------------------------
def obs_seed(tag: str, k: int) -> int:
    return zlib.crc32(f"{tag}:eval:{k}".encode())


def random_seed(tag: str, k: int) -> int:
    return zlib.crc32(f"{tag}:random:{k}".encode())


def parse_shard(spec: str) -> tuple[int, int]:
    i, n = (int(v) for v in str(spec).split("/"))
    if not (n >= 1 and 0 <= i < n):
        raise SystemExit(f"bad --shard {spec!r}")
    return i, n


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


def run_match(env, model, deck, entry: dict, k: int, cfg: dict) -> dict:
    from pipeline import engine_play as ep
    t0 = time.perf_counter()
    state = env.reset(entry)
    side, mirror = env.side, env._mirror
    engine_deck, deck_index_of_slot, costs = _slot_maps(env, deck, entry)
    tag = str(entry["tag"])
    rng_obs = np.random.default_rng(obs_seed(tag, k))
    rng_rand = random.Random(random_seed(tag, k))
    policy, grid, device = cfg["policy"], cfg["grid"], cfg["device"]
    unmapped: set = set()
    done_plays: list[tuple[int, int, float, float]] = []
    last_play_tick: Optional[int] = None
    n_dec = n_deg = n_att = n_acc = n_stall = n_noaff = 0
    p_gates: list[float] = []
    plays: list[dict] = []
    refuse: Counter = Counter()
    mix_att: Counter = Counter()
    mix_acc: Counter = Counter()
    done = False
    while not done:
        tick = int(env.tick)
        if last_play_tick is None:
            last_play_tick = tick                            # match start = first decision (anti-stall clock)
        bs = from_engine(ep.compact_raw(state), side, deck, engine_deck=engine_deck, unmapped=unmapped)
        view = live_view(bs, rng_obs, deck) if cfg["obs"] == "live" else bs
        n_deg += int(view.source == "degraded")
        tok, mask, sc = to_tokens(view, MAX_U)
        past = _past(done_plays, tick)
        enc, heads, p, hand = model_forward(model, tok, mask, sc, past, device)
        n_dec += 1
        p_gates.append(p)
        el_int = float(int(view.my_elixir))
        allowed = allowed_slots(hand, costs, el_int, afford_mask=cfg["afford_mask"] if policy == "live" else
                                (not cfg["random_hand_only"]))
        if policy == "live":
            st = anti_stall(el_int, tick, last_play_tick, cfg["stall_elixir"], cfg["stall_seconds"])
            d = live_decide(model, enc, heads, p, allowed, tau=cfg["tau"], stalled=st, device=device)
        elif policy == "random":
            d = random_decide(rng_rand, allowed, cfg["p_random"])
        else:
            d = {"play": False, "slot": -1, "cell": -1, "why": "none"}
        if d["why"] == "no_affordable":
            n_noaff += 1
        if d["play"]:
            n_att += 1
            n_stall += int(d["why"] == "stall")
            x, y = ep.cell_center(d["cell"], grid)
            X, Y = ep.cell_to_engine(d["cell"], mirror, grid)
            r = env.eng.act(side=side, deck_index=deck_index_of_slot[d["slot"]], x=X, y=Y)
            acc = bool(r["accepted"])
            code = int(r.get("result_code", -1))
            card = deck.cards[d["slot"]]
            mix_att[card] += 1
            rec = {"tick": tick, "slot": d["slot"], "card": card, "cell": d["cell"], "p": round(p, 4), "why": d["why"],
                   "elixir": el_int, "elixir_exact": round(float(bs.my_elixir), 3), "accepted": acc}
            if acc:
                n_acc += 1
                mix_acc[card] += 1
                done_plays.append((tick, d["slot"], x, y))
                last_play_tick = tick
            else:
                nm = ep.RESULT_CODE_NAMES.get(code, f"native_{code}")
                if r.get("placement_valid") is False:
                    nm = f"{nm}/{r.get('placement_reason')}"
                refuse[nm] += 1
                rec["reason"] = nm
            plays.append(rec)
        env._advance_to(min(env.tick + cfg["decide_every"], env.tail_cap))
        state = env.eng.observe()
        done = bool(env.terminated) or env.tick >= env.tail_cap
    outcome, crowns = ep._outcome(env, state)
    minutes = env.tick * TICK_S / 60.0
    end = int(env.tick)
    last_ghost = int(entry.get("last_ghost_tick") or 0)
    after_script = end > last_ghost + SCRIPT_MARGIN_TICKS
    pg = np.asarray(p_gates, dtype=np.float64)
    return {
        "tag": tag, "k": int(k), "slot": cfg["slot"], "port": cfg["port"], "split": entry.get("split"),
        "entry_index": cfg["entry_index"], "policy": policy, "obs": cfg["obs"], "tau": cfg["tau"],
        "afford_mask": cfg["afford_mask"], "stall_elixir": cfg["stall_elixir"], "p_random": cfg["p_random"],
        "obs_seed": obs_seed(tag, k), "side": side,
        "outcome": outcome, "crowns_for": int(crowns[0]), "crowns_against": int(crowns[1]),
        "end_tick": end, "seconds": round(end * TICK_S, 1), "terminated": bool(env.terminated),
        "termination_reason": (env.eng.last_episode or {}).get("termination_reason"),
        "last_ghost_tick": last_ghost, "after_script": bool(after_script),
        "won_after_script": bool(after_script and outcome == "win"),
        "ghost_plays": int(entry.get("ghost_plays") or 0), "ghost_delivered": int(env.ghost_ok),
        "ghost_refused": int(env.ghost_rejected), "ghost_undelivered": int(env.ghost_undelivered()),
        "ghost_distinct_delivered": len(env.ghost_cards_delivered), "ghost_refuse_reasons": dict(env.ghost_reject_reasons),
        "plays_attempted": n_att, "plays_accepted": n_acc, "plays_refused": n_att - n_acc,
        "refuse_reasons": dict(refuse), "plays_per_min": round(n_att / minutes, 3) if minutes else None,
        "accepted_per_min": round(n_acc / minutes, 3) if minutes else None,
        "card_mix_attempted": dict(mix_att), "card_mix_accepted": dict(mix_acc),
        "play_elixir": [pl["elixir"] for pl in plays], "plays": plays,
        "stall_fired": n_stall, "no_affordable": n_noaff, "decisions": n_dec, "degraded_obs": n_deg,
        "degraded_equals_decisions": bool(n_deg == n_dec) if cfg["obs"] == "live" else None,
        "p_gate_mean": round(float(pg.mean()), 4) if len(pg) else None,
        "p_gate_p90": round(float(np.percentile(pg, 90)), 4) if len(pg) else None,
        "frac_gt_tau": round(float((pg > cfg["tau"]).mean()), 4) if len(pg) else None,
        "real_outcome": entry.get("real_outcome"), "s1_split": entry.get("s1_split"), "group": entry.get("group"),
        "unmapped": sorted(unmapped), "wall_s": round(time.perf_counter() - t0, 1),
    }


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
    ap.add_argument("--port", type=int, required=True, help="engine direct door: 38031 or 38032")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--ckpt", type=Path, default=None, help="required for --mode eval")
    ap.add_argument("--pool", type=Path, default=POOL_V1)
    ap.add_argument("--split-file", type=Path, default=None, help="default: <pool stem>_split.json beside the pool")
    ap.add_argument("--split", choices=("heldout", "train"), default="heldout")
    ap.add_argument("--entries", default="all", help="a:b over the split's entries in pool order, 'all', or a tags file")
    ap.add_argument("--seeds", default="0", help="comma list of eval seeds k")
    ap.add_argument("--shard", default="0/1", help="i/n: round-robin share of the (entry, k) tasks")
    ap.add_argument("--policy", choices=("live", "none", "random"), default="live")
    ap.add_argument("--p-random", type=float, default=0.09)
    ap.add_argument("--random-hand-only", action="store_true", help="random control over hand slots, no affordability")
    ap.add_argument("--mode", choices=("eval", "parity", "liveness"), default="eval",
                    help="liveness = reset the FIRST selected entry + 10 ticks on this port, one line, exit")
    ap.add_argument("--parity-retry", choices=("corpus", "env"), default="corpus",
                    help="corpus = replay_drive's retry set (1050 only); env = EngineMatchEnv's (13, 1050)")
    ap.add_argument("--tau", type=float, default=TAU_LIVE)
    ap.add_argument("--no-afford-mask", action="store_true")
    ap.add_argument("--stall-elixir", default=str(STALL_ELIXIR_LIVE), help="'none' disables anti-stall")
    ap.add_argument("--stall-seconds", type=float, default=STALL_SECONDS_LIVE)
    ap.add_argument("--obs", choices=("live", "clean"), default="live")
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
           "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    deck = load_deck("icebow")
    model, minfo = None, {}
    if a.mode == "eval":
        from pipeline import engine_play as ep
        run["ckpt_sha256"] = sha256_file(a.ckpt)
        model, minfo = ep.load_model(a.ckpt, a.device)
        run["model"] = minfo
    (out / (f"run_resume_{int(time.time())}.json" if a.resume else "run.json")).write_text(
        json.dumps(run, indent=1, default=str), encoding="utf-8")
    cfg = {"policy": a.policy, "tau": float(a.tau), "afford_mask": not a.no_afford_mask, "stall_elixir": stall_elixir,
           "stall_seconds": float(a.stall_seconds), "obs": a.obs, "p_random": float(a.p_random),
           "random_hand_only": bool(a.random_hand_only), "grid": minfo.get("grid", "floor"), "device": a.device,
           "decide_every": int(a.decide_every), "slot": slot, "port": int(a.port)}
    print(json.dumps({"e1_eval": a.mode, "policy": a.policy, "port": a.port, "tasks": len(tasks),
                      "already_done": len(done_keys), "grid": cfg["grid"], "tau": cfg["tau"]}), flush=True)

    from pipeline.e1_pool import PoolV1Env
    new = 0
    results: list[dict] = []
    env = None
    try:
        env = PoolV1Env(port=int(a.port), host=a.host, decision_ticks=int(a.decide_every),
                        drive_our_commands=(a.mode == "parity"),
                        retry_codes=((1050,) if (a.mode == "parity" and a.parity_retry == "corpus") else (13, 1050)))
        for (i, k) in tasks:
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
            except Exception as exc:                          # engine / socket / timeout: record and stop this slot
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
    summ = {"new_matches": new, "finished": time.strftime("%Y-%m-%d %H:%M:%S"),
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
