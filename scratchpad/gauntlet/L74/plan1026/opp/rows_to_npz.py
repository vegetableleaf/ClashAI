"""P2-OPP1: slot re-drive shards (slot_redrive.py) -> ONE train_gen npz for the opponent model (+ its memory tables).

    python rows_to_npz.py --src OUT_DIR --vocab vocab_hf.json --hf-replays /workspace/hf_il_replay/data/replays \
        --out hf_slot_v0.npz [--max-shards N] [--keep-wait 8]

Per row (REPORT_opponents 1.4: every play slot, 1/8 of the no-play slots weighted x8, so the timing likelihood stays exact):
  * kept: tier A / B rows (B = the prefix before the first refusal, as built); PLAY rows; WAIT rows on the 10-tick grid
    (tick % 10 == 0). Off-grid wait rows (frames on the other side's play ticks) are dropped: not slots.
  * slot_ok = grid row (wait rows; a play ON a grid tick would be one, HF has none); slot_ev = this side plays within the
    slot (0 <= play_dt < 10), slot_tick = play_dt. Grid rows with a play or an ability press in the slot are always
    kept; the other grid rows with probability 1 / keep_wait (stable hash of tag, side, tick) and row_w = keep_wait
    (Horvitz-Thompson: row_w = 1 / inclusion probability, so the timing AND ability likelihoods stay unbiased).
  * card_ok = not hand_inferred (the hand before a side's 4th play is a fitted deal: no card label there).
  * ab_ok = grid row with an own visible ability controller (own_ability card > 0); ab_ev = 0 <= ab_dt < 10.
  * deck_gid = id of the (card, form) set when >= --deck-min-sides train sides have it, else 0 (unknown).
  * ctx_band: 1 hf_pol, 2 hf_other (3 pro, 4/5/6 live L/M/R are set by the live builder); ctx_mode: battle_type id
    (MODES); ctx_era: 1 = HF.
  * split by crc32(tag) % 100: < 5 held-out (1), 5..9 test (2, untouched), else train (0) -- the 90/5/5 of the design,
    per replay, so no replay straddles splits.
Card ids of every shard are remapped to the GLOBAL vocab (--vocab; the memory tables were built with it).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import zlib
from collections import Counter
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

MODES = {"pathOfLegend": 1, "Ranked": 1, "ladder": 2, "trail": 3, "friendly": 4, "clanMate": 4, "tournament": 5,
         "riverRacePvP": 6, "challenge": 3}
CARD_COLS_INT = ("hand_card", "next_card", "deck_card", "y_card", "y_wait_card")
CARD_COLS_OBJ = ("past", "opp_past", "opp_cycle", "projectiles", "effects", "own_ability")    # [..., 0] = card id
SLOT_TICKS = 10


def col(t, name, shape):
    c = t.column(name).combine_chunks()
    if not shape:
        return np.asarray(c)
    return np.asarray(c.flatten()).reshape((len(t),) + tuple(shape))     # npz_to_parquet: one FixedSizeList level


class Spool:
    """Per-array raw files appended shard by shard, then streamed into an uncompressed .npz (np.load reads it as usual):
    peak memory = one shard, not the whole dataset (the in-memory version was OOM-killed at 100 / 128 shards on 33308)."""

    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=False)
        self.meta = {}

    def append(self, name, a):
        a = np.ascontiguousarray(a)
        dt, tail, n = self.meta.get(name, (a.dtype, a.shape[1:], 0))
        if dt != a.dtype or tail != a.shape[1:]:
            raise ValueError(f"spool {name}: {a.dtype}{a.shape[1:]} after {dt}{tail}")
        with (self.root / f"{name}.bin").open("ab") as f:
            a.tofile(f)
        self.meta[name] = (dt, tail, n + len(a))

    def load(self, name):
        dt, tail, n = self.meta[name]
        return np.fromfile(self.root / f"{name}.bin", dtype=dt).reshape((n,) + tuple(tail))

    def write_npz(self, out: Path, arrays: dict, skip=()):
        """``out`` *.npz -> one uncompressed npz; any other name -> an EXTRACTED dir of NAME.npy files (train_gen --data reads
        both; the dir skips the npz + unzip copies, ~2x the rows on disk at peak)."""
        import contextlib
        import shutil
        import zipfile
        if out.suffix == ".npz":
            z = zipfile.ZipFile(out, "w", zipfile.ZIP_STORED, allowZip64=True)
            opener = lambda name: z.open(name + ".npy", "w", force_zip64=True)   # noqa: E731
        else:
            out.mkdir(parents=True, exist_ok=False)
            z = contextlib.nullcontext()
            opener = lambda name: (out / f"{name}.npy").open("wb")              # noqa: E731
        with z:
            for name, (dt, tail, n) in self.meta.items():
                if name in skip or name in arrays:
                    continue
                with opener(name) as f, (self.root / f"{name}.bin").open("rb") as src:
                    np.lib.format.write_array_header_2_0(f, {"descr": np.lib.format.dtype_to_descr(np.dtype(dt)),
                                                             "fortran_order": False, "shape": (n,) + tuple(tail)})
                    shutil.copyfileobj(src, f, length=1 << 22)
            for name, a in arrays.items():
                with opener(name) as f:
                    np.lib.format.write_array(f, np.asanyarray(a), allow_pickle=False)
        shutil.rmtree(self.root)


def mix(tagcrc, side, tick):
    h = (tagcrc.astype(np.uint64) * np.uint64(0x9E3779B1) + side.astype(np.uint64) * np.uint64(0x85EBCA77)
         + tick.astype(np.uint64) * np.uint64(0xC2B2AE3D)) & np.uint64(0xFFFFFFFF)
    return ((h ^ (h >> np.uint64(15))) * np.uint64(0x2C1B3C6D) & np.uint64(0xFFFFFFFF)) >> np.uint64(7)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--vocab", type=Path, required=True)
    ap.add_argument("--hf-replays", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-shards", type=int, default=0)
    ap.add_argument("--keep-wait", type=int, default=8)
    ap.add_argument("--deck-min-sides", type=int, default=50)
    ap.add_argument("--only-split", type=int, default=None, help="keep only this split (e.g. 2 = test, for level A)")
    ap.add_argument("--deck-map", type=Path, default=None, help="take deck ids from this (training) npz's deck_keys")
    a = ap.parse_args(argv)
    t0 = time.time()
    vocab = json.loads(a.vocab.read_text())
    gid = {k: i for i, k in enumerate(vocab)}
    bt = {}
    for f in sorted(a.hf_replays.glob("*.parquet")):
        r = pq.read_table(f, columns=["replay_tag", "battle_type"])
        bt.update(zip(r.column("replay_tag").to_pylist(), r.column("battle_type").to_pylist()))
    done = {p.stem for p in (a.src / "shards").glob("*.json")}
    files = [f for f in sorted((a.src / "rows").glob("*.parquet")) if f.stem in done]
    files = files[: a.max_shards] if a.max_shards else files
    mems, st = [], Counter()
    sp = Spool(a.out.with_suffix(".spool"))
    tag_list, tag_ix, n_tables = [], {}, 0
    for i, f in enumerate(files):
        t = pq.read_table(f)
        meta = json.loads(t.schema.metadata[b"meta"])
        shapes = json.loads(t.schema.metadata[b"shapes"])
        lut = np.array([gid[k] for k in meta["card_vocab"]], np.int64)     # KeyError = a card outside --vocab
        sc = np.load(f.with_suffix(".slot.npz"))
        n = len(t)
        tier = np.asarray(t.column("tier").combine_chunks()).astype(str)
        gate = col(t, "y_gate", [])
        tick = col(t, "tick", []).astype(np.int64)
        side = col(t, "side", []).astype(np.int64)
        tags = np.asarray(t.column("tag").combine_chunks()).astype(str)
        play_dt, ab_dt = sc["play_dt"].astype(np.int64), sc["ab_dt"].astype(np.int64)
        grid = (gate == 0) & (tick % SLOT_TICKS == 0)
        ev = grid & (play_dt >= 0) & (play_dt < SLOT_TICKS)
        utag, inv = np.unique(tags, return_inverse=True)
        crc = np.array([zlib.crc32(x.encode()) for x in utag], np.uint64)[inv]
        keep_w = mix(crc, side, tick) % np.uint64(a.keep_wait) == 0
        abev = grid & (ab_dt >= 0) & (ab_dt < SLOT_TICKS)
        sure = ev | abev                     # inclusion probability 1; other grid rows 1 / keep_wait -> row_w = 1 / that
        keep = np.isin(tier, ("A", "B")) & ((gate == 1) | sure | (grid & keep_w))
        if a.only_split is not None:
            c100 = np.array([zlib.crc32(x.encode()) % 100 for x in utag])[inv]
            keep &= np.where(c100 < 5, 1, np.where(c100 < 10, 2, 0)) == a.only_split
        st["rows_in"] += n; st["rows_kept"] += int(keep.sum()); st["play_rows"] += int((keep & (gate == 1)).sum())
        st["slot_event_rows"] += int((keep & ev).sum()); st["slot_noevent_rows"] += int((keep & grid & ~ev).sum())
        st["grid_rows_in"] += int((np.isin(tier, ("A", "B")) & grid).sum())
        st["offgrid_wait_dropped"] += int((np.isin(tier, ("A", "B")) & (gate == 0) & ~grid).sum())
        st["unusable_rows"] += int((~np.isin(tier, ("A", "B"))).sum())
        idx = np.where(keep)[0]
        d = {}
        for k, shp in shapes.items():
            if k in ("tok", "unit_form"):
                continue
            if k in ("tag", "tier", "hand_inferred"):
                continue
            d[k] = col(t, k, shp)[idx]
        for k in CARD_COLS_INT:
            d[k] = lut[d[k].astype(np.int64)].astype(np.int16)
        for k in CARD_COLS_OBJ:
            v = d[k]
            v[..., 0] = np.where(v[..., 0] > 0, lut[np.clip(v[..., 0], 0, len(lut) - 1).astype(np.int64)], v[..., 0])
        tk = t.column("tok").combine_chunks()
        off = np.asarray(tk.offsets)
        flat = np.asarray(tk.values.flatten()).reshape(-1, 14)
        uf = np.asarray(t.column("unit_form").combine_chunks().values)
        cnt = (off[1:] - off[:-1])[idx]
        sel = np.concatenate([np.arange(off[j], off[j + 1]) for j in idx]) if len(idx) else np.zeros(0, np.int64)
        sp.append("tok", flat[sel].astype(np.float32)); sp.append("unit_form", uf[sel])
        d["_cnt"] = cnt
        w = np.where(grid & ~sure, float(a.keep_wait), 1.0)[idx].astype(np.float32)
        hi = np.asarray(t.column("hand_inferred").combine_chunks()).astype(bool)[idx]
        oa = d["own_ability"]
        d.update(row_w=w, card_ok=(~hi).astype(np.int8), slot_ok=grid[idx].astype(np.int8),
                 slot_ev=ev[idx].astype(np.int8), slot_tick=np.where(ev, play_dt, 0)[idx].astype(np.int8),
                 ab_ok=(grid[idx] & (oa[..., 0] > 0).any(-1)).astype(np.int8),
                 ab_ev=(grid & (ab_dt >= 0) & (ab_dt < SLOT_TICKS))[idx].astype(np.int8),
                 ab_tick=np.where((ab_dt >= 0) & (ab_dt < SLOT_TICKS), ab_dt, 0)[idx].astype(np.int8))
        d["ab_ev"] &= d["ab_ok"]
        tg = tags[idx]
        for x in np.unique(tg):
            if x not in tag_ix:
                tag_ix[x] = len(tag_list); tag_list.append(x)
        d["rep"] = np.array([tag_ix[x] for x in tg], np.int32)
        c100 = np.array([zlib.crc32(x.encode()) % 100 for x in tg])
        d["split"] = np.where(c100 < 5, 1, np.where(c100 < 10, 2, 0)).astype(np.int8)
        btype = np.array([bt.get(x, "") for x in tg])
        d["ctx_band"] = np.where(btype == "pathOfLegend", 1, 2).astype(np.int8)
        d["ctx_mode"] = np.array([MODES.get(x, 7) for x in btype], np.int8)
        d["ctx_era"] = np.ones(len(idx), np.int8)
        mp = a.src / "mem" / (f.name[: -len(".parquet")] + ".npz")
        if mp.exists():
            z = np.load(mp, allow_pickle=False)
            rt = z["row_tab"][idx]
            d["_mem_row_tab"] = np.where(rt >= 0, rt + n_tables, -1).astype(np.int32)
            mems.append({k[4:]: z[k] for k in z.files if k.startswith("tab_")})
            n_tables += len(z["tab_off"]) - 1
        else:
            st["shards_without_memory"] += 1
            d["_mem_row_tab"] = np.full(len(idx), -1, np.int32)
        for k, v in d.items():
            sp.append(k, v)
        if (i + 1) % 20 == 0:
            print(f"[rows_to_npz] {i + 1}/{len(files)} rows_kept={st['rows_kept']} {time.time() - t0:.0f}s", flush=True)
    arrs = {k: sp.load(k) for k in ("deck_card", "deck_form", "rep", "side", "split")}
    new = {"off": np.concatenate([[0], np.cumsum(sp.load("_cnt"))]).astype(np.int64), "tags": np.asarray(tag_list)}
    new["v3val"] = np.zeros(len(arrs["split"]), np.int8)
    # deck ids: (card, form) sets with >= deck_min_sides TRAIN sides
    order = np.argsort(arrs["deck_card"], 1)
    key = np.concatenate([np.take_along_axis(arrs["deck_card"].astype(np.int64), order, 1),
                          np.take_along_axis(arrs["deck_form"].astype(np.int64), order, 1)], 1)
    ukey, kinv = np.unique(key, axis=0, return_inverse=True)
    kinv = kinv.reshape(-1)
    if a.deck_map is None:
        sides = np.unique(np.stack([arrs["rep"].astype(np.int64), arrs["side"].astype(np.int64), kinv], 1)[arrs["split"] == 0], axis=0)
        nside = np.bincount(sides[:, 2], minlength=len(ukey))
        big = np.where(nside >= a.deck_min_sides)[0]
        remap = np.zeros(len(ukey), np.int32)
        remap[big] = np.arange(1, len(big) + 1)
        new["deck_keys"] = ukey[big].astype(np.int16)             # id i = row i - 1 (rows_to_npz --deck-map reads it)
    else:
        dk = np.load(a.deck_map / "deck_keys.npy") if a.deck_map.is_dir() else np.load(a.deck_map)["deck_keys"]
        known = {tuple(r): i + 1 for i, r in enumerate(np.asarray(dk).tolist())}
        remap = np.array([known.get(tuple(r), 0) for r in ukey.tolist()], np.int32)
        big = np.where(remap > 0)[0]
        new["deck_keys"] = np.asarray(dk)
    new["deck_gid"] = remap[kinv]
    new["deck_id"] = new["deck_gid"].copy()
    st = dict(st)
    st.update(decks=int(len(ukey)), decks_with_id=int(len(big)),
              rows_with_deck_id=int((new["deck_gid"] > 0).sum()), rows=int(len(arrs["split"])),
              split_counts=str(dict(Counter(arrs["split"].tolist()))), tags=len(tag_list), shards=len(files))
    meta = {"kind": "generalist", "feature_version": 5, "grid": "lattice", "card_vocab": vocab, "F": 14, "S": 70,
            "PAST_K": 3, "OPP_PAST_K": 3, "source": "hf_il_replay slot re-drive (P2-OPP1)", "src_dir": str(a.src),
            "row_builder": {"wait_stride": 10, "play_window": 0, "record_every": 10, "keep_wait": a.keep_wait},
            "only_split": a.only_split, "deck_map": str(a.deck_map) if a.deck_map else None,
            "projectile_cols": ["card", "enemy", "x", "y", "target_x", "target_y", "tti_s", "tti_known"],
            "effect_cols": ["card", "enemy", "x", "y", "remaining_s", "remaining_known"],
            "modes": MODES, "bands": {"1": "hf_pol", "2": "hf_other", "3": "pro", "4": "live_L", "5": "live_M", "6": "live_R"},
            "eras": {"1": "hf"}, "vocab_sha256": hashlib.sha256(a.vocab.read_bytes()).hexdigest(),
            "src_manifest_sha256": hashlib.sha256((a.src / "manifest.json").read_bytes()).hexdigest()
            if (a.src / "manifest.json").exists() else None,
            "stats": {k: (int(v) if not isinstance(v, str) else v) for k, v in st.items()}, "built": time.strftime("%Y-%m-%d %H:%M:%S")}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    row_tab = sp.load("_mem_row_tab")
    sp.write_npz(a.out, dict(new, meta=np.asarray(json.dumps(meta))), skip=("_cnt", "_mem_row_tab"))
    if mems:
        from pipeline.match_memory import TABLE_KEYS
        off = [np.asarray(m["off"]) for m in mems]
        base = np.concatenate([[0], np.cumsum([o[-1] for o in off])])
        packed = {k: np.concatenate([m[k] for m in mems]) for k in TABLE_KEYS}
        packed["off"] = np.concatenate([[0]] + [o[1:] + b for o, b in zip(off, base[:-1])]).astype(np.int64)
        mmeta = {"kind": "match_memory_tables", "dataset": str(a.out), "tables": int(len(packed["off"]) - 1),
                 "rows": int(len(row_tab)), "rows_with_table": int((row_tab >= 0).sum()), "card_vocab": vocab}
        np.savez(a.out.with_name(a.out.stem + "_memory.npz"), **{"tab_" + k: v for k, v in packed.items()},
                 row_tab=row_tab, meta=json.dumps(mmeta))
    print(json.dumps({"out": str(a.out), "seconds": round(time.time() - t0), **meta["stats"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
