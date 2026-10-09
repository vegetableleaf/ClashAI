"""Grade convert.py on OUR recorded live matches, whose own plays are known (live_play.py `confirmed` events). L74.

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/replay_rec/validate_live.py [--logs N] [--out FILE.json]

Truth per match: every `confirmed` event = MY play: card (engine name), tick (the hand-rotation frame = what the hand
path of convert.py reports), intended cell (the model's target; the real deploy point differs by the tap calibration
error, err_tiles). Input: the log's `frame` events (public bodies only: side, x, y, card_id, hp, max_hp, kind, address;
no hands, no projectiles / effects, no category -> spells are not observable here and are counted apart).
  A. body path   convert.body_plays on my side -> match each truth play to an unmatched detection of the same card
                 within N ticks: recall, precision, tick error, cell error.
  B. hand path   the hand rotation is not logged, but its tick IS the confirmed tick by construction (live_play's
                 receipt), so A's card/tick question is moot there; this grades convert.locate's POSITION at those
                 ticks.
Cell error = max(|dx|, |dy|) in tiles vs the intended cell; "within 1 tile" = <= 1.0.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import convert as cv  # noqa: E402
from pipeline import vocab  # noqa: E402
from pipeline.opp_elixir_count import card_db  # noqa: E402

LOGS = Path("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader")   # main checkout: logs are untracked
TOLS = (5, 10, 20, 40)
SPELL_TOL = 100          # a body-spawning spell (Goblin Barrel) shows only when its bodies land (PlayDetector swarm window)


def load(path: Path):
    frames, truth, side, gen = [], [], None, {}
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        ev = r.get("event")
        if ev == "frame":
            side = r["my_side"]
            if frames and r["tick"] <= frames[-1]["game_tick"]:
                continue
            ents = []
            for e in r["ents"]:
                # live logs drop the reader's `category` (its generation identity; public_frame keys on it). Emulate
                # it: a new generation when an address shows a different card (dead body's address reused)
                c, g = gen.get(e[7], (e[3], 0))
                gen[e[7]] = (e[3], g + (c != e[3]))
                ents.append(dict(side=e[0], x=e[1], y=e[2], card_id=e[3], hp=e[4], max_hp=e[5], kind=e[6],
                                 address=e[7], category=gen[e[7]][1]))
            frames.append(dict(game_tick=r["tick"], players=[], entities=ents))
        elif ev == "confirmed":
            truth.append(r)
    return side, [cv.dedupe_hero_bodies(f) for f in frames], truth


def native(xy, side):
    x, y = xy[0] * 18000, (1 - xy[1]) * 32000
    return (18000 - x, 32000 - y) if side == 1 else (x, y)


def cell_err(x, y, t, side):
    tx, ty = native(t["intended"], side)
    return max(abs(x - tx), abs(y - ty)) / 1000


def grade(path: Path) -> dict | None:
    side, frames, truth = load(path)
    if side is None or len(frames) < 300 or not truth:
        return None
    truth = [t for t in truth if t["tick"] >= frames[0]["game_tick"]]
    spell = [card_db().kind(vocab.engine_key(t["name"])) == "spell" for t in truth]
    rows = []
    det = cv.body_plays(frames, sides=(side,))
    used: set = set()
    born, claimed = cv.births(frames), set()
    ticks = [f["game_tick"] for f in frames]
    for t, sp in zip(truth, spell):
        slug = cv.card_key(t["name"])
        row = dict(log=path.name, card=slug, tick=t["tick"], spell=sp, intended=t["intended"],
                   live_err_tiles=t.get("err_tiles"))
        cands = [(abs(d["tick"] - t["tick"]), j) for j, d in enumerate(det) if j not in used and d["card"] == slug
                 and abs(d["tick"] - t["tick"]) <= (SPELL_TOL if sp else max(TOLS))]
        if cands:
            _, j = min(cands)
            used.add(j)
            d = det[j]
            row.update(body_dt=d["tick"] - t["tick"], body_cell=round(cell_err(d["x"], d["y"], t, side), 3))
        i0 = next((i for i, k in enumerate(ticks) if k >= t["tick"]), None)
        loc = None if i0 is None else cv.locate(frames, born, i0, side, slug, sp, claimed)
        if loc:
            row["hand_cell"] = round(cell_err(loc[0], loc[1], t, side), 3)
        rows.append(row)
    return dict(log=path.name, side=side, frames=len(frames), truth=len(truth), detected=len(det),
                unmatched_detections=[dict(card=d["card"], tick=d["tick"]) for j, d in enumerate(det) if j not in used],
                rows=rows)


def summarize(games) -> dict:
    rows = [r for g in games for r in g["rows"]]
    bodies = [r for r in rows if not r["spell"]]
    n = len(bodies)
    out = dict(matches=len(games), truth_plays=len(rows), truth_spells=len(rows) - n, truth_bodies=n)
    for tol in TOLS:
        hit = [r for r in bodies if "body_dt" in r and abs(r["body_dt"]) <= tol]
        out[f"A_recall_card_tick<={tol}"] = round(len(hit) / max(1, n), 4)
    hit = [r for r in bodies if "body_dt" in r]
    det = sum(g["detected"] for g in games)
    out["A_precision_vs_my_detections"] = round(sum("body_dt" in r for r in rows) / max(1, det), 4)
    out["A_detections"] = det
    dts = sorted(r["body_dt"] for r in hit)
    out["A_tick_err_p50_p90"] = [dts[len(dts) // 2], dts[int(len(dts) * .9)]] if dts else None
    out["A_cell<=1tile_of_matched"] = round(sum(r["body_cell"] <= 1 for r in hit) / max(1, len(hit)), 4)
    loc = [r for r in bodies if "hand_cell" in r]
    out["B_located_bodies"] = round(len(loc) / max(1, n), 4)
    out["B_cell<=1tile_of_located"] = round(sum(r["hand_cell"] <= 1 for r in loc) / max(1, len(loc)), 4)
    # the game itself moves a play off the tapped cell (building overlap: live err_tiles 2.0); the converter then
    # reports where it really landed, so the intended cell is the wrong truth for those rows
    # (diggers stay in: their live err_tiles is the same first-sighting artefact convert.follow fixes)
    kept = [r for r in loc if (r.get("live_err_tiles") or 0) <= 1.0 or r["card"] in cv.DIGGERS]
    out["B_cell<=1tile_excl_game_displaced(live err>1)"] = round(sum(r["hand_cell"] <= 1 for r in kept)
                                                                  / max(1, len(kept)), 4)
    out["B_n_excluded_game_displaced"] = len(loc) - len(kept)
    sp = [r for r in rows if r["spell"]]
    sph = [r for r in sp if "body_dt" in r]
    out["spells_A_detected_from_bodies<=100"] = f"{len(sph)}/{len(sp)}"
    out["spells_A_tick_err_p50"] = sorted(r["body_dt"] for r in sph)[len(sph) // 2] if sph else None
    out["spells_B_located_from_bodies(no_projectiles_in_logs)"] = f"{sum('hand_cell' in r for r in sp)}/{len(sp)}"
    out["spells_B_cell<=1tile_of_located"] = round(sum(r["hand_cell"] <= 1 for r in sp if "hand_cell" in r)
                                                   / max(1, sum("hand_cell" in r for r in sp)), 4)
    out["spells_by_card"] = dict(sorted({r["card"]: sum(q["card"] == r["card"] for q in sp) for r in sp}.items()))
    live = sorted(r["live_err_tiles"] for r in bodies if r.get("live_err_tiles") is not None)
    out["live_tap_err_tiles_p50_p90(context)"] = [live[len(live) // 2], live[int(len(live) * .9)]] if live else None
    per = {}
    for r in bodies:
        p = per.setdefault(r["card"], [0, 0, 0])
        p[0] += 1
        p[1] += "body_dt" in r and abs(r["body_dt"]) <= 10
        p[2] += r.get("hand_cell", 9) <= 1
    out["per_card_[n,A_hit<=10,B_cell<=1]"] = per
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--logs", type=int, default=40, help="the N most recent finished logs with frames")
    ap.add_argument("--out", default=str(HERE / "validation_live.json"))
    ap.add_argument("--detail", default=str(HERE.parents[3] / ".foreman" / "scratch" / "replay_rec" / "validation_rows.json"))
    a = ap.parse_args()
    games = []
    for p in sorted(LOGS.glob("live_play_2026*.jsonl"), reverse=True):
        if time.time() - p.stat().st_mtime < 1800 or p.stat().st_size < 200_000:   # still running / no frames
            continue
        g = grade(p)
        if g:
            games.append(g)
            print(p.name, g["truth"], g["detected"], flush=True)
        if len(games) >= a.logs:
            break
    s = summarize(games)
    s["logs"] = [g["log"] for g in games]
    Path(a.out).write_text(json.dumps(s, indent=1), encoding="utf-8")
    Path(a.detail).parent.mkdir(parents=True, exist_ok=True)
    Path(a.detail).write_text(json.dumps(games), encoding="utf-8")
    print(json.dumps({k: v for k, v in s.items() if k not in ("logs", "per_card_[n,A_hit<=10,B_cell<=1]")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
