"""P2-SCORE: the HF human reference for levels B-HF / C-HF -- every TIER-A replay of an HF re-drive (each play accepted by
crforge at its tick, the match ended, crowns == recorded), one record per SIDE in the scorecard's common match format.

    python -I hf_ref.py --redrive /workspace/redrive/full_bec5811a --data /workspace/hf_il_replay/data --out hf_ref.json.gz

Record (card.py's format; the side is "the opponent", the other side is "us"):
  plays [[tick, key, cost, x, y, n_bodies 1, clean gap 0, el None]] with x, y in tiles in OUR frame (us at low y, so the
  side's own half is y > 19, as opp_behaviour), tick = the HF tick (= the tick the command is given; crforge runs it 20 later);
  mine = the other side's card-play ticks; end = the HF end tick; deck / levels / tower level; split = crc32(tag) % 100 with
  rows_to_npz's rule (< 5 held-out 1, 5..9 test 2, else train 0); band fields copied when the payload has them.
Ability presses are not plays (excluded, as live and SIM). Public data only (both sides' plays are public in a replay)."""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import zlib
from collections import defaultdict
from pathlib import Path


def base(key):
    for suf in ("-ev1", "-hero"):
        if key.endswith(suf):
            return key[: -len(suf)]
    return key


def split_of(tag):
    c = zlib.crc32(tag.encode()) % 100
    return 1 if c < 5 else 2 if c < 10 else 0


def tier_a(redrive: Path) -> dict:
    out = {}
    for f in glob.glob(str(redrive / "grades" / "*.jsonl")):
        for ln in open(f):
            g = json.loads(ln)
            if g.get("tier") == "A":
                out[g["tag"]] = g
    return out


def records(rep: dict, acts: list, grade: dict) -> list:
    from pipeline.opp_elixir_count import card_cost
    b = json.loads(rep["payload_json"])["battle"]
    decks, lv, band = {}, {}, {}
    for s, k in ((0, "team"), (1, "opponent")):
        p = b[k]["players"][0]
        decks[s] = [c["card_key"] for c in p["deck"]]
        lv[s] = dict(cards=[int(c.get("level") or 16) for c in p["deck"]], tower=int((p.get("tower_card") or {}).get("level") or 16))
        band[s] = {kk: v for kk, v in p.items() if "troph" in kk.lower() or kk.lower() in ("league", "league_number", "path_of_legend")}
    plays = {0: [], 1: []}
    for a in sorted(acts, key=lambda a: (a["replay_tick_20hz"], a["event_index"])):
        if a["kind"] != "play_card" or a["card_key"] is None or a["native_x"] is None:
            continue
        s = 0 if a["side"] == "team" else 1
        key = base(a["card_key"]).replace("-", "_")
        x, y = a["native_x"] / 1000.0, a["native_y"] / 1000.0
        plays[s].append((int(a["replay_tick_20hz"]), key, x, y))
    out = []
    for s in (0, 1):
        o = 1 - s
        # our frame = the OTHER side at low y: side 0 (low y) as the opponent is mirrored
        pl = [[t, k, card_cost(k) or 0.0, round(18 - x if s == 0 else x, 2), round(32 - y if s == 0 else y, 2), 1, 0, None]
              for t, k, x, y in plays[s]]
        out.append(dict(src="hf", id=f"{rep['replay_tag']}:{s}", tag=rep["replay_tag"], side=s, t0=0, end=int(grade["hf_end_tick"]),
                        plays=pl, mine=[t for t, *_ in plays[o]], deck=[base(c).replace("-", "_") for c in decks[s]],
                        opp_deck=[base(c).replace("-", "_") for c in decks[o]], levels=lv[s], band=band[s],
                        mode=rep.get("game_mode"), battle_type=rep.get("battle_type"), split=split_of(rep["replay_tag"]),
                        res=int((rep["team_crowns"] > rep["opponent_crowns"]) == (s == 0)) if rep["team_crowns"] != rep["opponent_crowns"] else 0.5))
    return out


def job_row(rep: dict) -> dict:
    """One pairs.py --mvm row: side 0 (team) in the learner seat, side 1 in the opponent seat, both HF decks (card keys with
    forms, converted to engine names in the pairs worker) and levels; the engine seed from the tag."""
    b = json.loads(rep["payload_json"])["battle"]
    d, lv = {}, {}
    for s, k in ((0, "team"), (1, "opponent")):
        p = b[k]["players"][0]
        d[s] = [c["card_key"] for c in p["deck"]]
        lv[s] = dict(cards=[int(c.get("level") or 16) for c in p["deck"]], tower=int((p.get("tower_card") or {}).get("level") or 16))
    return dict(key=rep["replay_tag"], seed=zlib.crc32(rep["replay_tag"].encode()) % 1_000_000_000, learner_side=0,
                learner_slugs=d[0], opp_slugs=d[1], levels=dict(learner=lv[0], opp=lv[1]))


def main():
    import pyarrow.parquet as pq
    ap = argparse.ArgumentParser()
    ap.add_argument("--redrive", type=Path, required=True)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=0, help="split item b: write N model-vs-model job rows (pairs.py --mvm) from the "
                                                       "test-split tier-A deck pairs + levels instead of the reference records")
    a = ap.parse_args()
    A = tier_a(a.redrive)
    print("tier A replays", len(A), flush=True)
    out = []
    for rp in sorted((a.data / "replays").glob("part-*.parquet")):
        reps = [r for r in pq.read_table(rp, columns=["replay_tag", "battle_type", "game_mode", "team_crowns", "opponent_crowns",
                                                      "payload_json"]).to_pylist() if r["replay_tag"] in A]
        if not reps:
            continue
        tags = [r["replay_tag"] for r in reps]
        acts = defaultdict(list)
        for x in pq.read_table(a.data / "actions" / rp.name, filters=[("replay_tag", "in", tags)],
                               columns=["replay_tag", "event_index", "kind", "side", "card_key", "replay_tick_20hz", "native_x",
                                        "native_y"]).to_pylist():
            acts[x["replay_tag"]].append(x)
        for r in reps:
            if a.jobs:
                if split_of(r["replay_tag"]) == 2 and len(out) < a.jobs:
                    out.append(job_row(r))
                continue
            out += records(r, acts[r["replay_tag"]], A[r["replay_tag"]])
        print(rp.name, len(out), flush=True)
        if a.jobs and len(out) >= a.jobs:
            break
    if a.jobs:
        a.out.write_text("".join(json.dumps(x) + chr(10) for x in out))
        print("wrote", a.out, len(out), "job rows")
        return
    meta = dict(redrive=str(a.redrive), manifest=json.loads((a.redrive / "manifest.json").read_text()).get("crforge_build"), n=len(out))
    with gzip.open(a.out, "wt") as fh:
        json.dump(dict(meta=meta, records=out), fh)
    print("wrote", a.out, len(out))


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
    main()
