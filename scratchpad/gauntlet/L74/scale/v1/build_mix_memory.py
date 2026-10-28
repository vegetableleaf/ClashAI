"""Memory tables (Plan A v1 tables; v2 features are computed from them) for mix_v1.npz:
  * v32 rows (src 0, the first rows, same order): gen_dataset_v32_fv5_memory_v1.npz unchanged (same card vocab);
  * HF rows (src 1): the P2-OPP1 slot re-drive's per-shard tables (slot_dir/mem/<sid>.npz; same replays, same crforge
    build and driver as the P2-RD1 rows), looked up by (tag, side); their card ids (vocab_hf) remapped to the mix vocab.
Identity check first (--check-shards N): the slot re-drive and the RD1 re-drive must have driven the SAME accepted plays
(per shard, the sets of (tag, side, tick, card name) over play rows of tier A/B replays must be equal), else refuse.
    python build_mix_memory.py --mix mix_v1.npz --v32-memory gen_dataset_v32_fv5_memory_v1.npz \
        --rd /workspace/redrive/full_bec5811a --slot /workspace/opp/slot_bec5811a --out mix_v1_memory.npz
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

TABLE_KEYS = ('tick', 'vis', 'vals', 'res', 'card', 'form', 'ans_card', 'flag', 'xb_dmg', 'rk_tl', 'swing', 'vpe')
CARD_KEYS = ('card', 'ans_card')


def plays(path):
    import pyarrow.parquet as pq
    t = pq.read_table(path, columns=["y_gate", "tag", "side", "tick", "y_card", "tier"])
    voc = json.loads(pq.read_schema(path).metadata[b"meta"])["card_vocab"]
    g = np.asarray(t.column("y_gate")) > 0
    ok = g & np.isin(np.asarray(t.column("tier")).astype(str), ("A", "B"))
    tag, side = np.asarray(t.column("tag")).astype(str)[ok], np.asarray(t.column("side"))[ok]
    tick, card = np.asarray(t.column("tick"))[ok], np.asarray(t.column("y_card"))[ok]
    return {(a, int(b), int(c), voc[int(d)]) for a, b, c, d in zip(tag, side, tick, card)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mix", type=Path, required=True)
    ap.add_argument("--v32-memory", type=Path, required=True)
    ap.add_argument("--rd", type=Path, required=True)
    ap.add_argument("--slot", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--check-shards", type=int, default=241, help="identity check on this many shards (0 = none)")
    a = ap.parse_args(argv)
    t0 = time.time()
    z = np.load(a.mix, allow_pickle=False)
    meta = json.loads(str(z["meta"]))
    vocab, mix = meta["card_vocab"], meta["mix"]
    gid = {k: i for i, k in enumerate(vocab)}
    n32, sids = int(mix["v32_rows"]), mix["hf_shards"]
    tags, rep, side, src = z["tags"].astype(str), z["rep"], z["side"].astype(np.int64), z["src"]
    if not ((src[:n32] == 0).all() and (src[n32:] == 1).all()):
        raise SystemExit("mix rows are not v32 first, then HF")
    # 1. identity: the slot drive and the RD1 drive played the same accepted plays
    bad = []
    for sid in sids[: a.check_shards]:
        p_rd, p_sl = plays(a.rd / "rows" / f"{sid}.parquet"), plays(a.slot / "rows" / f"{sid}.parquet")
        if p_rd != p_sl:
            bad.append((sid, len(p_rd), len(p_sl), len(p_rd ^ p_sl)))
    print(json.dumps({"identity_checked_shards": min(a.check_shards, len(sids)), "mismatch": bad[:20],
                      "seconds": round(time.time() - t0)}), flush=True)
    if bad:
        raise SystemExit(f"{len(bad)} shards drove different plays in the two re-drives")
    # 2. v32 tables as they are
    m32 = np.load(a.v32_memory, allow_pickle=False)
    mm32 = json.loads(str(m32["meta"]))
    if mm32["card_vocab"] != vocab or len(m32["row_tab"]) != n32:
        raise SystemExit("v32 memory tables: other vocab or row count")
    tabs = [{k: m32["tab_" + k] for k in TABLE_KEYS + ("off",)}]
    row_tab = [m32["row_tab"].astype(np.int64)]
    n_tab = len(tabs[0]["off"]) - 1
    # 3. HF: per shard, (tag, side) -> table, ids remapped
    hf_rep = rep[n32:]
    hf_tag = tags[hf_rep]
    hf_side = side[n32:]
    rt_hf = np.full(len(hf_rep), -1, np.int64)
    pos = {}
    for i, t in enumerate(hf_tag):                       # rows of one tag are contiguous per shard; index by tag
        pos.setdefault(t, []).append(i)
    missing_tables = 0
    for sid in sids:
        f = np.load(a.slot / "mem" / f"{sid}.npz", allow_pickle=False)
        fm = json.loads(str(f["meta"]))
        lut = np.array([gid[k] for k in fm["card_vocab"]], np.int64)
        tb = {k: f["tab_" + k] for k in TABLE_KEYS + ("off",)}
        for k in CARD_KEYS:
            tb[k] = lut[tb[k].astype(np.int64)].astype(tb[k].dtype)
        index = {(str(t), int(s)): j for j, (t, s) in enumerate(zip(f["table_tag"], f["table_side"]))}
        for t in set(map(str, f["table_tag"])):
            for i in pos.get(t, ()):
                j = index.get((t, int(hf_side[i])))
                if j is None:
                    missing_tables += 1
                else:
                    rt_hf[i] = n_tab + j
        tabs.append(tb)
        n_tab += len(tb["off"]) - 1
    row_tab.append(rt_hf)
    row_tab = np.concatenate(row_tab).astype(np.int32)
    off = [np.asarray(t["off"]) for t in tabs]
    base = np.concatenate([[0], np.cumsum([o[-1] for o in off])])
    packed = {k: np.concatenate([t[k] for t in tabs]) for k in TABLE_KEYS}
    packed["off"] = np.concatenate([[0]] + [o[1:] + b for o, b in zip(off, base[:-1])]).astype(np.int64)
    mmeta = {"kind": "match_memory_tables", "dataset": str(a.mix), "tables": int(len(packed["off"]) - 1),
             "rows": int(len(row_tab)), "rows_with_table": int((row_tab >= 0).sum()),
             "hf_rows_without_table": int((rt_hf < 0).sum()), "v32_rows_without_table": int((row_tab[:n32] < 0).sum()),
             "missing_tables": missing_tables, "card_vocab": vocab, "v32_memory": str(a.v32_memory),
             "slot_dir": str(a.slot), "identity_checked_shards": min(a.check_shards, len(sids)),
             "built": time.strftime("%Y-%m-%d %H:%M:%S")}
    np.savez_compressed(a.out, **{"tab_" + k: v for k, v in packed.items()}, row_tab=row_tab, meta=json.dumps(mmeta))
    print(json.dumps({k: v for k, v in mmeta.items() if k != "card_vocab"} | {"seconds": round(time.time() - t0)}),
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
