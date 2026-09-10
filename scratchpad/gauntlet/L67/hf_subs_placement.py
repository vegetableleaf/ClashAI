"""L67m: is a card SUBSTITUTION safe to alias? Compare where pros actually place the two cards.

Owner's condition for mining 7-of-8 decks: placements must not be confounded -- a substituted card's plays
have to correspond to OUR slot's plays. That is an empirical claim, not a matter of opinion, so this measures
it: for each candidate pair (our card, their card), collect every placement of OUR card from EXACT-deck
replays and every placement of THEIR card from the substituted replays, and compare the distributions.

If a pro places a Cannon where a pro places a Tesla, aliasing them adds data. If the distributions differ,
aliasing teaches our slot the wrong tile and the pair must be dropped however common it is.

Positions are RoyaleAPI raw tile coords; both sides are normalised to "the placing player attacks upward" so
team and opponent plays are comparable, and only the placing side's own card is counted.

usage: python scratchpad/gauntlet/L67/hf_subs_placement.py [--out <json>]
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

import numpy as np
import polars as pl

HF = Path("scratchpad/gauntlet/L67/hf/replays")
HOGEQ = frozenset({"hog-rider", "firecracker", "mighty-miner", "tesla", "the-log", "earthquake",
                   "skeletons", "ice-spirit"})
# candidates worth testing: everything with enough plays to compare
PAIRS = [("ice-spirit", "electro-spirit"), ("tesla", "cannon"), ("the-log", "barbarian-barrel"),
         ("mighty-miner", "valkyrie"), ("skeletons", "goblins")]


def base(k: str) -> str:
    return re.sub(r"-ev\d+$", "", k)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--max-files", type=int, default=52)
    a = ap.parse_args()

    want_cards = {c for pair in PAIRS for c in pair} | HOGEQ
    pos: dict[tuple[str, str], list] = collections.defaultdict(list)   # (card, context) -> [(x, y)]

    files = sorted(HF.glob("*.parquet"))[:a.max_files]
    for i, f in enumerate(files):
        try:
            df = pl.read_parquet(f, columns=["payload_json"])
        except Exception:                                              # noqa: BLE001
            continue
        for raw in df["payload_json"].to_list():
            try:
                p = json.loads(raw)
                b = p["battle"]
            except Exception:                                          # noqa: BLE001
                continue
            sides = {}
            for side in ("team", "opponent"):
                pls = (b.get(side) or {}).get("players") or []
                if len(pls) == 1:
                    sides[side] = {base(c["card_key"]) for c in pls[0].get("deck", [])}
            if len(sides) != 2:
                continue
            # which side is on our deck, exactly or one card off?
            for side, ks in sides.items():
                if len(ks) != 8:
                    continue
                exact = ks == HOGEQ
                off = len(ks & HOGEQ) == 7
                if not (exact or off):
                    continue
                ctx = "exact" if exact else "sub"
                s_tag = "t" if side == "team" else "o"
                for e in p.get("events", []):
                    if e.get("kind") != "play_card":
                        continue
                    sf = e.get("source_fields") or {}
                    if sf.get("data_s") != s_tag or sf.get("data_x") is None:
                        continue
                    card = base(str(sf.get("data_c") or e.get("card_key") or ""))
                    if card not in want_cards:
                        continue
                    # RoyaleAPI coords are MILLI-TILES (replay_drive.py:162-164 mirrors with 18000-x /
                    # 32000-y), not tiles. Reading them as tiles put every play outside the histogram and
                    # produced a self-overlap of 0.0 -- which is exactly what the self-overlap control is for.
                    x, y = float(sf["data_x"]) / 1000.0, float(sf["data_y"]) / 1000.0
                    if s_tag == "o":                     # normalise: everyone attacks the same way
                        x, y = 18.0 - x, 32.0 - y
                    pos[(card, ctx)].append((x, y))
        if i % 10 == 9:
            print(f"  {i+1}/{len(files)} files", flush=True)

    # save the raw positions so the analysis can be redone without a 10-minute rescan
    if a.out:
        np.savez_compressed(str(a.out).replace(".json", "_pos.npz"),
                            **{f"{c}|{ctx}": np.array(v, dtype=np.float32) for (c, ctx), v in pos.items()})
    out = []
    for ours, theirs in PAIRS:
        A = np.array(pos.get((ours, "exact"), []) or pos.get((ours, "sub"), []))
        B = np.array(pos.get((theirs, "sub"), []))
        if len(A) < 30 or len(B) < 30:
            out.append({"pair": f"{ours} <- {theirs}", "n_ours": len(A), "n_theirs": len(B),
                        "verdict": "too few plays to judge"})
            print(json.dumps(out[-1]), flush=True)
            continue
        # coarse 6x8 histogram overlap: 1.0 = identical placement distributions, 0 = disjoint
        H1, _, _ = np.histogram2d(A[:, 0], A[:, 1], bins=[6, 8], range=[[0, 18], [0, 32]])
        H2, _, _ = np.histogram2d(B[:, 0], B[:, 1], bins=[6, 8], range=[[0, 18], [0, 32]])
        H1 = H1 / max(H1.sum(), 1); H2 = H2 / max(H2.sum(), 1)
        overlap = float(np.minimum(H1, H2).sum())
        rec = {"pair": f"{ours} <- {theirs}", "n_ours": int(len(A)), "n_theirs": int(len(B)),
               "ours_median_xy": [round(float(np.median(A[:, 0])), 2), round(float(np.median(A[:, 1])), 2)],
               "theirs_median_xy": [round(float(np.median(B[:, 0])), 2), round(float(np.median(B[:, 1])), 2)],
               "median_shift_tiles": round(float(np.hypot(np.median(A[:, 0]) - np.median(B[:, 0]),
                                                          np.median(A[:, 1]) - np.median(B[:, 1]))), 2),
               "histogram_overlap": round(overlap, 3)}
        out.append(rec)
        print(json.dumps(rec), flush=True)

    # reference: how much do two halves of OUR OWN card's plays overlap? that is the ceiling for this metric
    for ours in ("tesla", "ice-spirit"):
        A = np.array(pos.get((ours, "exact"), []))
        if len(A) >= 60:
            h = len(A) // 2
            H1, _, _ = np.histogram2d(A[:h, 0], A[:h, 1], bins=[6, 8], range=[[0, 18], [0, 32]])
            H2, _, _ = np.histogram2d(A[h:, 0], A[h:, 1], bins=[6, 8], range=[[0, 18], [0, 32]])
            H1 = H1 / max(H1.sum(), 1); H2 = H2 / max(H2.sum(), 1)
            print(json.dumps({"self_overlap_ceiling": ours, "n": len(A),
                              "overlap": round(float(np.minimum(H1, H2).sum()), 3)}), flush=True)
            out.append({"self_overlap_ceiling": ours, "overlap": round(float(np.minimum(H1, H2).sum()), 3)})
    if a.out:
        a.out.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
