"""P2-OPP2: the live fine-tune's training rows = ALL rows of a live rows dir (rows_to_npz extracted format, its own split 0 /
1 kept) + whole HF replays drawn from an HF dir's split 0 until they are ``--hf-share`` of the mix (forced split 0, so the
held-out set stays the live time-ordered tail). Both dirs must share the card vocab and deck_keys (rows_to_npz --deck-map).
Ragged arrays (tok, unit_form via off), rep / tags and the memory tables (tab_* + tab_off + row_tab) are re-indexed.

    python mix_rows.py --live /workspace/opp/live/live_train --hf /workspace/opp/v1/hf_slot_v1 --hf-share 0.2 \
        --out /workspace/opp/live/mix_train [--seed 0]
-> OUT/ (extracted dir) + OUT_memory.npz; ends with a self-check of sampled rows against both sources."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

RAGGED = ("tok", "unit_form")


def load(d: Path):
    a = {f.stem: np.load(f, mmap_mode="r") for f in sorted(d.glob("*.npy"))}
    return a, json.loads(str(a.pop("meta"))), dict(np.load(d.with_name(d.name + "_memory.npz")))


def take(a: dict, mem: dict, idx: np.ndarray, n_rows: int) -> tuple[dict, dict]:
    """Rows ``idx`` (sorted) of one source -> its arrays (ragged flattened, rep compacted) + its memory tables (compacted)."""
    out = {k: np.asarray(v[idx]) for k, v in a.items() if k not in RAGGED + ("off", "tags", "deck_keys")
           and v.shape[:1] == (n_rows,)}
    off = np.asarray(a["off"])
    lo, hi = off[idx], off[idx + 1]
    sel = np.concatenate([np.arange(s, e) for s, e in zip(lo, hi)]) if len(idx) else np.zeros(0, np.int64)
    for k in RAGGED:
        out[k] = np.asarray(a[k][sel])
    out["off"] = np.concatenate([[0], np.cumsum(hi - lo)]).astype(np.int64)
    reps, out["rep"] = np.unique(out["rep"], return_inverse=True)
    out["tags"] = np.asarray(a["tags"])[reps]
    rt = mem["row_tab"][idx]
    tabs, inv = np.unique(rt[rt >= 0], return_inverse=True)
    new_rt = np.full(len(idx), -1, np.int32)
    new_rt[rt >= 0] = inv
    toff = mem["tab_off"]
    tsel = np.concatenate([np.arange(toff[t], toff[t + 1]) for t in tabs]) if len(tabs) else np.zeros(0, np.int64)
    m = {k: mem[k][tsel] for k in mem if k.startswith("tab_") and k != "tab_off"}
    m["tab_off"] = np.concatenate([[0], np.cumsum(toff[tabs + 1] - toff[tabs])]).astype(np.int64)
    m["row_tab"] = new_rt
    return out, m


def cat(parts: list, mems: list) -> tuple[dict, dict]:
    out, m = {}, {}
    for k in parts[0]:
        if k == "off":
            base = np.cumsum([0] + [p["off"][-1] for p in parts[:-1]])
            out[k] = np.concatenate([[0]] + [p["off"][1:] + b for p, b in zip(parts, base)])
        elif k == "rep":
            base = np.cumsum([0] + [len(p["tags"]) for p in parts[:-1]])
            out[k] = np.concatenate([p["rep"] + b for p, b in zip(parts, base)]).astype(parts[0]["rep"].dtype)
        else:
            out[k] = np.concatenate([p[k] for p in parts])
    for k in mems[0]:
        if k == "tab_off":
            base = np.cumsum([0] + [q["tab_off"][-1] for q in mems[:-1]])
            m[k] = np.concatenate([[0]] + [q["tab_off"][1:] + b for q, b in zip(mems, base)])
        elif k == "row_tab":
            base = np.cumsum([0] + [len(q["tab_off"]) - 1 for q in mems[:-1]])
            m[k] = np.concatenate([np.where(q[k] >= 0, q[k] + b, -1) for q, b in zip(mems, base)]).astype(np.int32)
        else:
            m[k] = np.concatenate([q[k] for q in mems])
    return out, m


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", type=Path, required=True)
    ap.add_argument("--hf", type=Path, required=True)
    ap.add_argument("--hf-share", type=float, default=0.2)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    L, lmeta, lmem = load(a.live)
    H, hmeta, hmem = load(a.hf)
    if lmeta["card_vocab"] != hmeta["card_vocab"] or not np.array_equal(L["deck_keys"], H["deck_keys"]):
        raise SystemExit("live and HF rows differ in card vocab or deck_keys: rebuild the live rows with --deck-map of the HF dir")
    nl, nh = len(L["split"]), len(H["split"])
    want = int(round(nl * a.hf_share / (1 - a.hf_share)))
    hsplit, hrep = np.asarray(H["split"]), np.asarray(H["rep"])
    reps = np.unique(hrep[hsplit == 0])
    rng = np.random.default_rng(a.seed)
    cnt = np.bincount(hrep[hsplit == 0], minlength=int(hrep.max()) + 1)
    order = rng.permutation(reps)
    pick = order[: int(np.searchsorted(np.cumsum(cnt[order]), want)) + 1]
    hidx = np.where(np.isin(hrep, pick) & (hsplit == 0))[0]
    lo, lm = take(L, lmem, np.arange(nl), nl)
    ho, hm = take(H, hmem, hidx, nh)
    out, mem = cat([lo, ho], [lm, hm])
    out["deck_keys"] = np.asarray(L["deck_keys"])
    meta = dict(lmeta, mix={"live": str(a.live), "hf": str(a.hf), "hf_share": a.hf_share, "seed": a.seed,
                            "live_rows": nl, "hf_rows": int(len(hidx)), "hf_replays": int(len(pick))})
    a.out.mkdir(parents=True, exist_ok=False)
    for k, v in out.items():
        np.save(a.out / f"{k}.npy", v)
    np.save(a.out / "meta.npy", np.asarray(json.dumps(meta)))
    mmeta = json.loads(str(lmem["meta"]))
    mmeta.update(dataset=str(a.out), tables=int(len(mem["tab_off"]) - 1), rows=int(len(mem["row_tab"])))
    np.savez(a.out.with_name(a.out.name + "_memory.npz"), **mem, meta=json.dumps(mmeta))
    # self-check: sampled mixed rows equal their source rows (per-row, ragged, tag, memory table contents)
    chk = np.random.default_rng(1).choice(len(out["split"]), size=min(2000, len(out["split"])), replace=False)
    for r in chk:
        src, sm, s = (L, lmem, r) if r < nl else (H, hmem, int(hidx[r - nl]))
        for k in ("y_cell", "slot_ev", "deck_gid", "tick", "side"):
            assert np.array_equal(out[k][r], src[k][s]), (k, r)
        assert out["split"][r] == (src["split"][s] if r < nl else 0)
        for k in RAGGED:
            assert np.array_equal(out[k][out["off"][r]:out["off"][r + 1]], src[k][src["off"][s]:src["off"][s + 1]]), (k, r)
        assert out["tags"][out["rep"][r]] == src["tags"][src["rep"][s]]
        t0, t1 = mem["row_tab"][r], sm["row_tab"][s]
        assert (t0 < 0) == (t1 < 0)
        if t0 >= 0:
            for k in ("tab_tick", "tab_vals", "tab_card"):
                assert np.array_equal(mem[k][mem["tab_off"][t0]:mem["tab_off"][t0 + 1]], sm[k][sm["tab_off"][t1]:sm["tab_off"][t1 + 1]]), (k, r)
    print(json.dumps({"out": str(a.out), **meta["mix"], "rows": int(len(out["split"])),
                      "split": np.bincount(out["split"]).tolist(), "self_check_rows": int(len(chk))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
