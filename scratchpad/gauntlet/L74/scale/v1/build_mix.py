"""Curve v1 / P4-10M data: gen_dataset_v32_fv5 (ours) + the HF IL_Replay crforge re-drive (P2-RD1 rows, a shard subset)
-> ONE train_gen npz (same keys / dtypes as v32, + ``src``).

    python build_mix.py --v32 gen_dataset_v32_fv5.npz --rd /workspace/redrive/full_bec5811a --limit-replays 60000 \
        --hf-replays /workspace/hf_il_replay/data/replays --out mix_v1.npz [--workers 16]

* HF shards = the first ``--limit-replays`` replays of the re-drive's own round-robin job order (redrive.jobs), i.e. the
  same shards the P2-OPP1 slot re-drive covers with --limit 60000 (whose per-shard memory tables then exist for them).
* Card ids of every shard are remapped to v32's card_vocab (a card outside it = a hard error).
* HF rows: tier A / B only; a hand-inferred row (the hand before a side's 4th play is a fitted deal) gets
  y_hand_pos = -1 (no card label; train_gen / eval exclude -1); deck_id -1 (no global deck ids); v3val 0; src 1.
* Splits: HF keeps its own (crc of the tag, val 10%: split 1 = HF held-out, the trainer's selection sample comes from
  it); v32's val rows (split 1) become split 3, so they are never trained on or used for selection: their held-out
  minus curve v0's 30k selection sample is exactly curve v0's ``heldout_clean`` (same rows, same ids).
Arrays are written one at a time into a deflate zip (np.load reads it like savez_compressed).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import zipfile
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

import numpy as np

CARD_COLS_INT = ("hand_card", "next_card", "deck_card", "y_card", "y_wait_card")
CARD_COLS_OBJ = ("past", "opp_past", "opp_cycle", "projectiles", "effects", "own_ability")    # [..., 0] = card id
SKIP = ("tok", "unit_form", "tag", "tier", "hand_inferred")


def shard_ids(replays: Path, chunk: int, limit: int) -> list[str]:
    """redrive.jobs' order (round-robin over parts, whole shards until >= limit replays)."""
    import pyarrow.parquet as pq
    per = []
    for rp in sorted(replays.glob("part-*.parquet")):
        n = pq.ParquetFile(rp).metadata.num_rows
        per.append([(f"{rp.stem}_{lo:05d}", min(lo + chunk, n) - lo) for lo in range(0, n, chunk)])
    order = [j for i in range(max(map(len, per))) for p in per if i < len(p) for j in [p[i]]]
    keep, tot = [], 0
    for sid, n in order:
        if limit and tot >= limit:
            break
        keep.append(sid)
        tot += n
    return keep


def col(t, name, shape):
    c = t.column(name).combine_chunks()
    if not shape:
        return np.asarray(c)
    return np.asarray(c.flatten()).reshape((len(t),) + tuple(shape))


def load_shard(job):
    import pyarrow.parquet as pq
    path, vocab = job[:2]
    spool = Path(job[2]) if len(job) > 2 and job[2] else None
    gid = {k: i for i, k in enumerate(vocab)}
    t = pq.read_table(path)
    meta = json.loads(t.schema.metadata[b"meta"])
    shapes = json.loads(t.schema.metadata[b"shapes"])
    miss = sorted(k for k in meta["card_vocab"] if k not in gid)
    if miss:
        return {"path": path, "missing_cards": miss}
    lut = np.array([gid[k] for k in meta["card_vocab"]], np.int64)
    tier = np.asarray(t.column("tier").combine_chunks()).astype(str)
    idx = np.where(np.isin(tier, ("A", "B")))[0]
    d = {k: col(t, k, shp)[idx] for k, shp in shapes.items() if k not in SKIP}
    for k in CARD_COLS_INT:
        d[k] = lut[d[k].astype(np.int64)]
    for k in CARD_COLS_OBJ:
        v = d[k]
        v[..., 0] = np.where(v[..., 0] > 0, lut[np.clip(v[..., 0], 0, len(lut) - 1).astype(np.int64)], v[..., 0])
    hi = np.asarray(t.column("hand_inferred").combine_chunks()).astype(bool)[idx]
    play = d["y_gate"] > 0
    st = Counter(rows_in=len(t), rows=len(idx), unusable_rows=int(len(t) - len(idx)), play=int(play.sum()),
                 wait=int((~play).sum()), hand_inferred=int(hi.sum()), play_hand_inferred=int((hi & play).sum()),
                 card_label_masked=int((hi & play & (d["y_hand_pos"] >= 0)).sum()))
    st.update({f"tier_{x}_rows": int((tier[idx] == x).sum()) for x in ("A", "B")})
    d["y_hand_pos"] = np.where(hi, -1, d["y_hand_pos"]).astype(d["y_hand_pos"].dtype)
    tags = np.asarray(t.column("tag").combine_chunks()).astype(str)[idx]
    utag, d["rep"] = np.unique(tags, return_inverse=True)
    tk = t.column("tok").combine_chunks()
    off = np.asarray(tk.offsets)
    flat = np.asarray(tk.values.flatten()).reshape(-1, 14)
    uf = np.asarray(t.column("unit_form").combine_chunks().values)
    sel = np.concatenate([np.arange(off[j], off[j + 1]) for j in idx]) if len(idx) else np.zeros(0, np.int64)
    d["_cnt"] = (off[1:] - off[:-1])[idx]
    d["_tok"], d["_uf"], d["_tags"] = flat[sel], uf[sel], utag
    d["_stats"], d["_meta_stats"] = dict(st), meta.get("stats", {})
    d["_contract"] = {k: meta.get(k) for k in ("feature_version", "grid", "F", "S", "PAST_K", "OPP_PAST_K",
                                                "projectile_cols", "effect_cols", "public_timing_contract",
                                                "own_ability_cols", "opp_cycle_cols", "body_identity_contract",
                                                "public_observation", "opponent_elixir", "wait_stride", "play_window")}
    if spool is not None:                 # arrays to disk (np.load mmap later): the caller holds no shard in RAM
        spool.mkdir(parents=True, exist_ok=True)
        for k, v in list(d.items()):
            if isinstance(v, np.ndarray):
                np.save(spool / f"{k}.npy", v, allow_pickle=False)
                d[k] = str(spool / f"{k}.npy")
    return d


def write(zf, name, arr):
    with zf.open(name + ".npy", "w", force_zip64=True) as f:
        np.lib.format.write_array(f, np.asarray(arr), allow_pickle=False)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v32", type=Path, required=True)
    ap.add_argument("--rd", type=Path, required=True, help="P2-RD1 output dir (rows/, shards/, manifest.json)")
    ap.add_argument("--hf-replays", type=Path, default=None)
    ap.add_argument("--shards-file", type=Path, default=None, help="shard ids, one per line (instead of --hf-replays)")
    ap.add_argument("--limit-replays", type=int, default=60000)
    ap.add_argument("--chunk", type=int, default=250)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--spool", type=Path, default=None, help="per-shard arrays to this dir (low RAM; delete after)")
    a = ap.parse_args(argv)
    t0 = time.time()
    z = np.load(a.v32, allow_pickle=False)
    m32 = json.loads(str(z["meta"]))
    vocab = m32["card_vocab"]
    sids = (a.shards_file.read_text().split() if a.shards_file else shard_ids(a.hf_replays, a.chunk, a.limit_replays))
    files = [a.rd / "rows" / f"{s}.parquet" for s in sids]
    gone = [str(f) for f in files if not f.exists() or not (a.rd / "shards" / f"{f.stem}.json").exists()]
    if gone:
        raise SystemExit(f"{len(gone)} shards missing in {a.rd}: {gone[:5]}")
    with Pool(a.workers) as pool:
        parts = []
        jobs = [(str(f), vocab, str(a.spool / f"{i:04d}") if a.spool else "") for i, f in enumerate(files)]
        for i, d in enumerate(pool.imap(load_shard, jobs)):
            if "missing_cards" in d:
                raise SystemExit(f"cards outside v32's vocab in {d['path']}: {d['missing_cards']}")
            parts.append({k: np.load(v, mmap_mode="r") if isinstance(v, str) and v.endswith(".npy") else v
                          for k, v in d.items()})
            if (i + 1) % 20 == 0:
                print(f"[build_mix] {i + 1}/{len(files)} shards {time.time() - t0:.0f}s", flush=True)
    c0 = parts[0]["_contract"]
    bad = [(k, c0[k], m32.get(k)) for k in c0 if k not in ("wait_stride", "play_window") and c0[k] != m32.get(k)]
    bad += [(f, k) for p, f in zip(parts, files) for k in c0 if p["_contract"][k] != c0[k]]
    if bad or (c0["wait_stride"], c0["play_window"]) != (m32["wait_stride"], m32["play_window"]):
        raise SystemExit(f"observation contract differs between v32 and the HF rows: {bad[:5]}")
    st, mst = Counter(), Counter()
    for p in parts:
        st.update(p["_stats"])
        mst.update({k: v for k, v in p["_meta_stats"].items() if isinstance(v, (int, float))})
    n32 = len(z["split"])
    nhf = int(st["rows"])
    tags32 = z["tags"]
    rep_off = np.cumsum([0] + [len(p["_tags"]) for p in parts])
    keys = [k for k in z.files if k != "meta"]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(".partial")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as zf:
        for k in keys:
            v = z[k]
            if k == "tags":
                out = np.concatenate([tags32.astype(str)] + [p["_tags"] for p in parts])
            elif k == "off":
                cnt = np.concatenate([p["_cnt"] for p in parts])
                out = np.concatenate([v, v[-1] + np.cumsum(cnt)]).astype(v.dtype)
            elif k == "tok":
                out = np.concatenate([v] + [p["_tok"] for p in parts]).astype(v.dtype)
            elif k == "unit_form":
                out = np.concatenate([v] + [p["_uf"] for p in parts]).astype(v.dtype)
            elif k == "rep":
                out = np.concatenate([v] + [p["rep"] + len(tags32) + rep_off[i] for i, p in enumerate(parts)])
            elif k == "split":
                out = np.concatenate([np.where(v == 1, 3, v)] + [p["split"] for p in parts])
            elif k == "deck_id":
                out = np.concatenate([v] + [np.full(len(p["_cnt"]), -1) for p in parts])
            elif k == "v3val":
                out = np.concatenate([v] + [np.zeros(len(p["_cnt"])) for p in parts])
            else:
                hp = [p[k] for p in parts]
                if hp[0].shape[1:] != v.shape[1:]:
                    raise SystemExit(f"{k}: v32 shape {v.shape} vs HF {hp[0].shape}")
                # streamed: one .npy header for the full shape, then v32's rows and each shard's in order (no full
                # concatenated copy: pods cap a container at 125 GB, and the projectile array alone is ~30 GB)
                for c in hp:
                    if not np.array_equal(c.astype(v.dtype), c):
                        raise SystemExit(f"{k}: values change when cast to v32's dtype {v.dtype}")
                shape = (len(v) + sum(len(c) for c in hp),) + v.shape[1:]
                with zf.open(k + ".npy", "w", force_zip64=True) as f:
                    np.lib.format.write_array_header_2_0(f, {"descr": np.lib.format.dtype_to_descr(v.dtype),
                                                             "fortran_order": False, "shape": shape})
                    for c in [v] + hp:
                        for i in range(0, len(c), 500000):
                            f.write(np.ascontiguousarray(c[i:i + 500000], dtype=v.dtype).tobytes())
                for p in parts:
                    p.pop(k, None)
                print(f"[build_mix] wrote {k} {shape} {v.dtype} (streamed) {time.time() - t0:.0f}s", flush=True)
                del hp, v
                continue
            cast = out if k == "tags" else out.astype(v.dtype)          # tags: keep the widest string dtype
            if not np.array_equal(cast, out):
                raise SystemExit(f"{k}: values change when cast to v32's dtype {v.dtype}")
            write(zf, k, cast)
            for p in parts:
                p.pop(k, None)
            print(f"[build_mix] wrote {k} {cast.shape} {cast.dtype} {time.time() - t0:.0f}s", flush=True)
            del out, cast, v
        write(zf, "src", np.concatenate([np.zeros(n32, np.int8), np.ones(nhf, np.int8)]))
        stats = Counter({k: v for k, v in m32["stats"].items() if isinstance(v, (int, float))})
        stats.update(mst)
        rd_man = a.rd / "manifest.json"
        meta = dict(m32, card_vocab=vocab, stats=dict(stats), built=time.strftime("%Y-%m-%d %H:%M:%S"),
                    source="curve v1 mix: gen_dataset_v32_fv5 (src 0) + HF IL_Replay crforge re-drive P2-RD1 (src 1)",
                    mix={"v32": str(a.v32), "v32_rows": n32, "v32_sha256_meta": hashlib.sha256(str(z["meta"]).encode()).hexdigest(),
                         "hf_dir": str(a.rd), "hf_manifest_sha256": hashlib.sha256(rd_man.read_bytes()).hexdigest(),
                         "hf_limit_replays": a.limit_replays, "hf_shards": sids, "hf_rows": nhf, "hf_stats": dict(st),
                         "splits": {"0": "train (v32 train + HF train)", "1": "HF held-out (selection sample source)",
                                    "3": "v32 held-out (= v32 split 1; never trained or selected)"},
                         "hand_inferred": "y_hand_pos = -1 (no card label)", "deck_id": "-1 on HF rows"})
        write(zf, "meta", np.asarray(json.dumps(meta)))
    tmp.rename(a.out)
    print(json.dumps({"out": str(a.out), "rows": n32 + nhf, "v32_rows": n32, "hf_rows": nhf, "shards": len(sids),
                      "hf_stats": dict(st), "seconds": round(time.time() - t0)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
