"""S3's search teacher: at a pro state, try placements in the real engine and keep the one that plays best.

The S1 student predicts a placement from a single forward pass. This asks a different question -- given
the actual game state, which placement actually WORKS -- by putting each candidate into `libg` and
rolling the battle forward. The pre-registered gate (§5cs.53 C, instrument `pipeline/s3_bench.py`) is
whether targets found this way agree with pro placements at least as often as the student does, measured
on the same 500 states.

Three decisions that keep the comparison honest, all of them ways this could otherwise flatter itself:

  * TEACHER-FORCED CARD. Only the placement is searched; the card is the pro's own slot, exactly as
    `s3_bench.predict` reads the student's cell head. A teacher allowed to choose the card too would be
    answering an easier question than the number it is compared against.
  * SAME LATTICE. Candidates are generated ON the model's own half-tile grid (GRID_X x GRID_Y = 36 x 64,
    cell = cy*36 + cx) and converted to engine coordinates from there -- never the reverse. A teacher
    placing continuously would beat a cell-quantised student on sub-cell precision alone, which would be
    a measurement artifact rather than a finding.
  * NO SNAPSHOT, SO NO SHORTCUTS. The engine protocol has no save/restore op (checked: reset, load_replay,
    act, ability, step, step_trace, observe, joint_*, probe_grid), so every candidate is evaluated by
    re-driving the replay from reset to the branch tick. That is the whole cost of this file, and it is
    why --max-candidates exists.

Scoring is deliberately plain: after H ticks, (damage dealt to enemy towers) - (damage taken by our own),
plus a small term for surviving unit hitpoints, from the acting side's view. No learned value function --
a learned value would put the student's own biases inside the teacher and the gate would stop being a
test of search.

What this does NOT do: it does not claim the best-scoring placement is the "correct" one. It produces a
target, and the gate decides whether that target is worth learning from.

usage:
  python -m pipeline.s3_teacher run <bench.json> --out <teacher.jsonl> [--port 37031]
                                 [--max-candidates 24] [--horizon 120] [--limit N] [--tags-from N/M]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "research" / "sandbox_tools"))

GRID_X, GRID_Y = 36, 64                 # must match pipeline/model_v3.py
ENGINE_X, ENGINE_Y = 18000.0, 32000.0   # engine units; 1000 per tile (obs_contract.py:28-29)


def cell_to_engine(cx: int, cy: int, side: int, off: float) -> tuple[int, int]:
    """Model cell -> engine (x, y), inverting obs_contract's nx = x/18000, ny = 1 - y/32000, with side 1
    mirrored first. Done in this direction so candidates land exactly on the lattice the student uses."""
    nx = (cx + off) / GRID_X
    ny = (cy + off) / GRID_Y
    ex = nx * ENGINE_X
    ey = (1.0 - ny) * ENGINE_Y
    if side == 1:
        ex, ey = ENGINE_X - ex, ENGINE_Y - ey
    return int(round(ex)), int(round(ey))


def engine_to_cell(ex: float, ey: float, side: int) -> tuple[float, float]:
    if side == 1:
        ex, ey = ENGINE_X - ex, ENGINE_Y - ey
    return (ex / ENGINE_X) * GRID_X, (1.0 - ey / ENGINE_Y) * GRID_Y


# ----------------------------------------------------------------------------------------------------
# per-tag context: the expensive setup (deal inference + deck-order search) done once, reused per state
# ----------------------------------------------------------------------------------------------------
def prepare(tag: str, rd, env, level: int, seed: int):
    """Replicate replay_drive.drive's steps 1-3 so our states are the SAME states the corpus was built
    from. Any divergence here would silently compare the teacher against a different game."""
    battle, plays = rd.load_battle(tag)
    decks = {s: rd.deck_for_side(battle, s) for s in (0, 1)}
    template = json.loads((rd.SANDBOX / "examples" / "full-card-bootstrap.json").read_text(encoding="utf-8-sig"))
    deals = {}
    for side in (0, 1):
        by_slug = {item["slug"]: item for item in decks[side]}
        seq = [by_slug[r["attr_card"]]["card_id"] for r in plays if r["side"] == side and not r["ability"]]
        found = rd.infer_deals(seq, [item["card_id"] for item in decks[side]])
        if not found:
            return None
        deals[side] = found[0]

    order_a = {s: list(decks[s]) for s in (0, 1)}
    st = env.reset(rd.build_replay(template, rd.deck_spec(order_a[0], level), rd.deck_spec(order_a[1], level),
                                   seed=seed), warmup_steps=0)
    dealt_a = {s: (list(rd.player(st, s)["hand_deck_indices"]), list(rd.player(st, s)["cycle_deck_indices"]))
               for s in (0, 1)}
    order_b = {s: list(reversed(decks[s])) for s in (0, 1)}
    st = env.reset(rd.build_replay(template, rd.deck_spec(order_b[0], level), rd.deck_spec(order_b[1], level),
                                   seed=seed), warmup_steps=0)
    dealt_b = {s: (list(rd.player(st, s)["hand_deck_indices"]), list(rd.player(st, s)["cycle_deck_indices"]))
               for s in (0, 1)}
    position_based = all(sorted(dealt_a[s][0]) == sorted(dealt_b[s][0]) and dealt_a[s][1] == dealt_b[s][1]
                         for s in (0, 1))
    final = ({s: rd.sp_order_for(decks[s], dealt_a[s][0], dealt_a[s][1], deals[s]) for s in (0, 1)}
             if position_based else order_a)
    replay = rd.build_replay(template, rd.deck_spec(final[0], level), rd.deck_spec(final[1], level), seed=seed)
    index_of = {s: {item["slug"]: i for i, item in enumerate(final[s])} for s in (0, 1)}
    return {"tag": tag, "plays": plays, "replay": replay, "index_of": index_of,
            "position_based": bool(position_based)}


def drive_to(env, ctx, upto_play_index: int, rd):
    """reset, then replay every pro play strictly BEFORE the target play, and stand at its tick."""
    st = env.reset(ctx["replay"], warmup_steps=0)
    tick = int(st["tick"])
    for row in ctx["plays"]:
        if row["play_index"] >= upto_play_index:
            break
        if row["tick"] > tick:
            step = env.step(row["tick"] - tick)
            tick = int(step["tick_after"])
            if step["episode"].get("terminated"):
                return None
        if row["ability"]:
            continue
        env.act(side=row["side"], deck_index=ctx["index_of"][row["side"]][row["attr_card"]],
                x=row["x"], y=row["y"])
    target = next(r for r in ctx["plays"] if r["play_index"] == upto_play_index)
    if target["tick"] > tick:
        step = env.step(target["tick"] - tick)
        if step["episode"].get("terminated"):
            return None
        tick = int(step["tick_after"])
    return tick


def tower_hp(state, side: int) -> tuple[int, int]:
    """(our tower hp, their tower hp) from `side`'s point of view."""
    ours = theirs = 0
    for t in state["episode"].get("crown_towers", []):
        if int(t["side"]) == side:
            ours += int(t["hp"])
        else:
            theirs += int(t["hp"])
    return ours, theirs


def unit_hp(state, side: int) -> tuple[int, int]:
    ours = theirs = 0
    for e in state.get("entities", []):
        if int(e["side"]) == side:
            ours += int(e["hp"])
        else:
            theirs += int(e["hp"])
    return ours, theirs


def evaluate(env, side: int, horizon: int) -> float:
    """Roll forward `horizon` ticks and score from `side`'s view. Towers dominate; units are a tiebreak
    at 1/8 weight so that a placement which merely trades evenly does not outrank one that defends a tower."""
    before = env.observe()
    ot0, tt0 = tower_hp(before, side)
    ou0, tu0 = unit_hp(before, side)
    step = env.step(horizon)
    after = env.observe()
    ot1, tt1 = tower_hp(after, side)
    ou1, tu1 = unit_hp(after, side)
    dealt = (tt0 - tt1)
    taken = (ot0 - ot1)
    unit_swing = (ou1 - ou0) - (tu1 - tu0)
    terminated = bool(step["episode"].get("terminated"))
    return float(dealt - taken) + 0.125 * float(unit_swing) + (0.0 if not terminated else 0.0)


def legal_cells(env, side: int, deck_index: int, off: float, max_candidates: int) -> list[tuple[int, int]]:
    """Cells of the model's own grid whose engine point libg accepts for this card, evenly subsampled.

    probe_grid returns libg's own 18x32 tile mask, so legality is asked of the engine rather than assumed
    from an arena-half rule -- spells and buildings have different rules and a hand-written mask would be
    wrong for some card in the deck without ever saying so."""
    try:
        grid = env.probe_grid(side=side, deck_index=deck_index)
    except Exception:                                     # noqa: BLE001
        grid = None
    mask = None
    if isinstance(grid, dict):
        for key in ("cells", "mask", "grid", "allowed"):
            if key in grid:
                mask = grid[key]
                break
    ok: list[tuple[int, int]] = []
    for cy in range(GRID_Y):
        for cx in range(GRID_X):
            if mask is not None:
                tx, ty = cx // 2, cy // 2                 # model half-tiles -> libg tiles
                try:
                    v = mask[ty][tx] if isinstance(mask[0], (list, tuple)) else mask[ty * 18 + tx]
                except Exception:                         # noqa: BLE001
                    v = 1
                if not v:
                    continue
            ok.append((cx, cy))
    if not ok:
        ok = [(cx, cy) for cy in range(GRID_Y) for cx in range(GRID_X)]
    if len(ok) > max_candidates:
        # 2-D STRATIFIED, not a 1-D stride. Striding this row-major list collapses the candidate set
        # onto a single column whenever the stride is near a multiple of GRID_X (=36): the first run at
        # max_candidates=4 proposed px=0.5 for all six states, i.e. cx=0 every time. A teacher that can
        # only offer the left edge cannot agree with a pro, and the gate would then be measuring the
        # sampler rather than the search. Cover the legal region's bounding box instead.
        xs = [c[0] for c in ok]; ys = [c[1] for c in ok]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        aspect = max(1e-6, (x1 - x0 + 1) / max(1, (y1 - y0 + 1)))
        nx = max(1, int(round((max_candidates * aspect) ** 0.5)))
        ny = max(1, int(round(max_candidates / nx)))
        legal = set(ok)
        picked: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()
        for iy in range(ny):
            for ix in range(nx):
                tx = x0 + (x1 - x0) * (ix + 0.5) / nx
                ty = y0 + (y1 - y0) * (iy + 0.5) / ny
                best, bd = None, None
                for c in ok:                              # nearest LEGAL cell to this lattice point
                    d = (c[0] - tx) ** 2 + (c[1] - ty) ** 2
                    if bd is None or d < bd:
                        best, bd = c, d
                if best is not None and best not in seen:
                    seen.add(best); picked.append(best)
        ok = picked or ok[:max_candidates]
    return ok


def run(argv) -> int:
    ap = argparse.ArgumentParser(prog="s3_teacher run")
    ap.add_argument("bench", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--port", type=int, default=37031)
    ap.add_argument("--max-candidates", type=int, default=24)
    ap.add_argument("--horizon", type=int, default=120)
    # Coarse candidates alone CANNOT reach the pre-registered exact-cell criterion (<= 0.3 tiles): a
    # 4x6 lattice is nearly state-independent (the first full run used 23 distinct cells across 497
    # states) so 0% agreement was guaranteed by the design, not measured. Stage B re-searches the full
    # lattice within +/-R cells of the best coarse cell, which makes the criterion reachable.
    ap.add_argument("--refine", type=int, default=2, help="stage-B radius in cells; 0 disables")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--shard", default="0/1", help="i/n -- split BY TAG so per-tag setup is not duplicated")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--level", type=int, default=11)
    ap.add_argument("--off", type=float, default=0.5, help="cell->point offset; 0.5 = cell centre")
    # The 500-state bench is built from the v3 dataset, whose replays were driven from plays_ext.csv.
    # plays_ext_i1.csv holds only the LATER refetch (0 rows for the bench's tags), so pointing at it
    # yields "battles.csv says 55 plays, ... has 0" -- an error whose text names the default file, not
    # the one actually being read, which is why it does not point at its own cause.
    ap.add_argument("--plays-file", default="plays_ext.csv")
    ap.add_argument("--crawl", default="icebow")
    a = ap.parse_args(argv)

    import replay_drive as rd                              # noqa: E402
    from native_core.env import NativeRoyaleEnv            # noqa: E402
    rd.set_crawl(a.crawl)
    rd.set_plays_file(a.plays_file)

    bench = json.loads(a.bench.read_text(encoding="utf-8"))
    rows = bench["rows"]
    by_tag: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_tag[r["tag"]].append(r)
    tags = sorted(by_tag)
    i, n = (int(v) for v in a.shard.split("/"))
    tags = [t for k, t in enumerate(tags) if k % n == i]
    if a.limit:
        tags = tags[:a.limit]

    env = NativeRoyaleEnv(port=a.port, timeout=180.0)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    done = 0
    t0 = time.perf_counter()
    with a.out.open("w", encoding="utf-8") as fh:
        for tag in tags:
            try:
                ctx = prepare(tag, rd, env, a.level, a.seed)
            except Exception as e:                         # noqa: BLE001
                print(json.dumps({"tag": tag, "error": type(e).__name__, "where": "prepare"}), flush=True)
                continue
            if ctx is None:
                print(json.dumps({"tag": tag, "error": "deal_inference_failed"}), flush=True)
                continue
            play_by_tick = {}
            for r in ctx["plays"]:
                play_by_tick.setdefault((r["tick"], r["side"]), r)
            for row in by_tag[tag]:
                target = play_by_tick.get((row["tick"], row["side"]))
                if target is None or target["ability"]:
                    continue
                slug = target["attr_card"]
                di = ctx["index_of"][row["side"]].get(slug)
                if di is None:
                    continue
                base_tick = drive_to(env, ctx, target["play_index"], rd)
                if base_tick is None:
                    continue
                cands = legal_cells(env, row["side"], di, a.off, a.max_candidates)

                def try_cells(cells):
                    got = None
                    for (cx, cy) in cells:
                        if drive_to(env, ctx, target["play_index"], rd) is None:
                            continue
                        ex, ey = cell_to_engine(cx, cy, row["side"], a.off)
                        res = env.act(side=row["side"], deck_index=di, x=ex, y=ey)
                        if not res.get("accepted"):
                            continue
                        sc = evaluate(env, row["side"], a.horizon)
                        if got is None or sc > got[0]:
                            got = (sc, cx, cy)
                    return got

                best = try_cells(cands)
                n_eval = len(cands)
                if best is not None and a.refine > 0:
                    _, bx, by = best
                    near = [(cx, cy)
                            for cy in range(max(0, by - a.refine), min(GRID_Y, by + a.refine + 1))
                            for cx in range(max(0, bx - a.refine), min(GRID_X, bx + a.refine + 1))
                            if (cx, cy) != (bx, by)]
                    n_eval += len(near)
                    fine = try_cells(near)
                    if fine is not None and fine[0] > best[0]:
                        best = fine
                if best is None:
                    continue
                sc, cx, cy = best
                fh.write(json.dumps({"tag": tag, "tick": row["tick"], "slot": row["slot"],
                                     "px": float(cx) + a.off, "py": float(cy) + a.off,
                                     "score": round(sc, 1), "candidates": n_eval}) + chr(10))
                fh.flush()
                done += 1
                if done % 5 == 0:
                    print(json.dumps({"done": done, "tag": tag,
                                      "sec_per_state": round((time.perf_counter() - t0) / done, 1)}), flush=True)
    print(json.dumps({"states": done, "tags": len(tags), "seconds": round(time.perf_counter() - t0, 1),
                      "out": str(a.out)}), flush=True)
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] != "run":
        print(__doc__)
        return 2
    return run(argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
