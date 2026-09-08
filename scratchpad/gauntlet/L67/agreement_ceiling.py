"""L67h: what is the CEILING on pro-cell agreement? How often do two PROS in the same position agree?

Every S1 number in this project (18.17 -> 21.04 exact cell) is graded against ONE pro's chosen tile, as if
that tile were the unique right answer. It is not: two strong players in the same position pick different
tiles, so there is a ceiling below 100% and nobody here has measured it. Without it we cannot say whether
21% is a weak model or a strong one against a hard target, and the whole "what do we fix next" ordering
depends on the answer.

METHOD -- model-free throughout (the model's own embedding would make this circular):
  * take every PRO PLAY row (y_gate == 1) in the corpus, from both splits (these are labels, not predictions)
  * describe the board with a coarse, deliberately crude summary: a 6x8 occupancy histogram per side (96
    counts) plus tower HP -- crude on purpose, so "near" means "the same tactical situation", not "the same
    pixels"
  * BLOCK on the decision being the same one: same card played, same integer elixir; pairs must come from
    DIFFERENT replays, so it is never one player agreeing with himself
  * within a block, bin pairs by board distance and report agreement AS A FUNCTION of distance. The ceiling
    is where the curve is heading as distance -> 0; the far bins are the floor (how often two pros agree by
    coincidence).

Reported per distance bin: exact-lattice-cell agreement (the headline metric's own definition), within-1-tile,
and the median separation in tiles. Card agreement is measured separately, blocking on elixir + hand only.

usage: python scratchpad/gauntlet/L67/agreement_ceiling.py --data <npz> --out <json>
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

GX, GY = 6, 8                      # coarse occupancy grid
TILES_X, TILES_Y = 18.0, 32.0


def build_hist(arrs, rows: np.ndarray) -> np.ndarray:
    """[n, GX*GY*2] unit counts: side 0 = mine, side 1 = enemy (unknown never occurs in engine rows)."""
    tok, off = arrs["tok"], arrs["off"]
    out = np.zeros((len(rows), GX * GY * 2), dtype=np.float32)
    for i, r in enumerate(rows):
        a, b = int(off[r]), int(off[r + 1])
        if b <= a:
            continue
        t = tok[a:b]
        mine = t[:, 1] > 0.5
        cx = np.clip((t[:, 4] * GX).astype(int), 0, GX - 1)
        cy = np.clip((t[:, 5] * GY).astype(int), 0, GY - 1)
        idx = cy * GX + cx + np.where(mine, 0, GX * GY)
        np.add.at(out[i], idx, 1.0)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-rows", type=int, default=40000)
    ap.add_argument("--grid", default="lattice")
    ap.add_argument("--players", type=Path, default=None,
                    help="crawl battles.csv (replay_tag,player_tag): exclude pairs from the SAME player. "
                         "Without it a pro can agree with HIMSELF across two of his own replays, which "
                         "inflates the ceiling -- one player is more self-consistent than two.")
    ap.add_argument("--same-replay", action="store_true",
                    help="ANCHOR: keep only pairs from the SAME replay (one player, one match) instead")
    a = ap.parse_args()

    import torch
    from pipeline.dataset import load as load_ds
    from pipeline.model_v3 import cell_label

    arrs, _ = load_ds(a.data)
    play = np.flatnonzero(arrs["y_gate"] == 1)
    if len(play) > a.max_rows:
        play = np.sort(np.random.default_rng(0).choice(play, a.max_rows, replace=False))
    xy = arrs["y_xy"][play]
    cell = cell_label(torch.from_numpy(xy), a.grid).numpy()
    slot = arrs["y_slot"][play]
    rep = arrs["rep"][play]
    elix = np.rint(arrs["sc"][play, 3] * 10.0).astype(int)
    towers = arrs["sc"][play][:, 52:58]
    hist = build_hist(arrs, play)
    who = np.full(len(play), -1, dtype=np.int64)          # player id per row, -1 = unknown
    if a.players is not None and a.players.exists():
        import csv
        tag2p: dict[str, str] = {}
        with a.players.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                if row.get("replay_tag") and row.get("player_tag"):
                    tag2p[row["replay_tag"]] = row["player_tag"]
        pid = {p: i for i, p in enumerate(sorted(set(tag2p.values())))}
        tags = arrs["tags"]
        who = np.array([pid.get(tag2p.get(str(tags[r]), ""), -1) for r in rep], dtype=np.int64)
        known = int((who >= 0).sum())
        print(f"player map: {len(pid)} players, {known}/{len(play)} rows attributed", flush=True)
    hand = (arrs["sc"][play][:, 7:43] > 0.5).astype(np.float32)
    print(f"play rows {len(play)}, replays {len(np.unique(rep))}", flush=True)

    BINS = [(0.0, 0.25), (0.25, 0.5), (0.5, 1.0), (1.0, 2.0), (2.0, 3.0), (3.0, 5.0),
            (5.0, 8.0), (8.0, 1e9)]      # finer near 0: the curve had not plateaued at 0-1
    acc = {b: {"n": 0, "same_cell": 0, "within1": 0, "dist": []} for b in BINS}
    card_acc = {b: {"n": 0, "same_card": 0} for b in BINS}

    def add(pairs_i, pairs_j, d, store, kind):
        for lo, hi in BINS:
            m = (d >= lo) & (d < hi)
            if not m.any():
                continue
            i, j = pairs_i[m], pairs_j[m]
            s = store[(lo, hi)]
            s["n"] += int(m.sum())
            if kind == "cell":
                s["same_cell"] += int((cell[i] == cell[j]).sum())
                dt = np.hypot((xy[i, 0] - xy[j, 0]) * TILES_X, (xy[i, 1] - xy[j, 1]) * TILES_Y)
                s["within1"] += int((dt <= 1.0).sum())
                s["dist"].append(dt)
            else:
                s["same_card"] += int((slot[i] == slot[j]).sum())

    # ---- CELL agreement: block on (card, elixir) ----------------------------------------------------
    hkey0 = ((arrs['sc'][play][:, 7:43] > 0.5).astype(np.float32)
             * (2 ** np.arange(36))).sum(1).astype(np.int64)
    ckey = hkey0 * 1000 + slot.astype(np.int64) * 100 + elix     # same hand, same card, same elixir
    for key in np.unique(ckey):
        idx = np.flatnonzero(ckey == key)
        if len(idx) < 2 or len(idx) > 6000:
            continue
        h, t, r = hist[idx], towers[idx], rep[idx]
        d = np.abs(h[:, None, :] - h[None, :, :]).sum(-1) + np.abs(t[:, None, :] - t[None, :, :]).sum(-1)
        iu, ju = np.triu_indices(len(idx), k=1)
        w = who[idx]
        keep = (r[iu] == r[ju]) if a.same_replay else (
            (r[iu] != r[ju]) & ~((w[iu] >= 0) & (w[iu] == w[ju])))   # different replay AND different player
        add(idx[iu[keep]], idx[ju[keep]], d[iu[keep], ju[keep]], acc, "cell")
    # ---- CARD agreement: block on (elixir, hand) ----------------------------------------------------
    hkey = (hand * (2 ** np.arange(hand.shape[1]))).sum(1).astype(np.int64)
    for key in np.unique(hkey * 100 + elix):
        idx = np.flatnonzero(hkey * 100 + elix == key)
        if len(idx) < 2 or len(idx) > 6000:
            continue
        h, t, r = hist[idx], towers[idx], rep[idx]
        d = np.abs(h[:, None, :] - h[None, :, :]).sum(-1) + np.abs(t[:, None, :] - t[None, :, :]).sum(-1)
        iu, ju = np.triu_indices(len(idx), k=1)
        w = who[idx]
        keep = (r[iu] == r[ju]) if a.same_replay else (
            (r[iu] != r[ju]) & ~((w[iu] >= 0) & (w[iu] == w[ju])))
        add(idx[iu[keep]], idx[ju[keep]], d[iu[keep], ju[keep]], card_acc, "card")

    rows = []
    for (lo, hi) in BINS:
        s = acc[(lo, hi)]
        c = card_acc[(lo, hi)]
        if not s["n"] and not c["n"]:
            continue
        dts = np.concatenate(s["dist"]) if s["dist"] else np.array([np.nan])
        rows.append({"board_distance": f"{lo:g}-{hi:g}" if hi < 1e8 else f">{lo:g}",
                     "cell_pairs": s["n"],
                     "same_cell_pct": round(100.0 * s["same_cell"] / max(s["n"], 1), 2),
                     "within_1_tile_pct": round(100.0 * s["within1"] / max(s["n"], 1), 2),
                     "median_sep_tiles": round(float(np.nanmedian(dts)), 2),
                     "card_pairs": c["n"],
                     "same_card_pct": round(100.0 * c["same_card"] / max(c["n"], 1), 2)})
        print(json.dumps(rows[-1]), flush=True)
    a.out.write_text(json.dumps({"data": str(a.data), "grid": a.grid, "rows": rows}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
