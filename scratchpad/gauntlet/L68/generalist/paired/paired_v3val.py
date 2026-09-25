"""T2: paired per-row comparison, on icebow v3val PLAY rows, generalist vs the 3 icebow S1 v6lat seeds.

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L68/generalist/paired/paired_v3val.py
    (run from repo root; CPU only)

Alignment key = (replay tag, side, tick) -- both datasets carry rep->tags, side, tick per row (dataset.py /
dataset_gen.py docstrings). gen "v3val" rows were built to be exactly S1's split==1 rows (dataset_gen.v3val_tags),
so a 1:1 match of all PLAY rows is expected; this script asserts and reports the actual count instead of assuming it.

evaluate() for S1 is train_s1.evaluate copied line-for-line with a rowlog appended (train_s1.py is not edited).
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as Fn

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO))

from pipeline.dataset import load as load_ds                                    # noqa: E402
from pipeline.eval_gen import GenRows, evaluate as gen_evaluate, load_model as load_gen_model  # noqa: E402
from pipeline.model_v3 import GRID_X, GRID_Y, S1Model, cell_index, cell_label, hand_mask_from_sc, tile_of_cell  # noqa: E402
from pipeline.train_s1 import MAX_U, Rows as S1Rows                              # noqa: E402

GEN_CKPT = REPO / "icebow" / "data" / "pipeline" / "gen_v1_s0" / "gen_s0.pt"
GEN_DATA = REPO / "icebow" / "data" / "pipeline" / "gen_dataset_v1.npz"
S1_DATA = REPO / "icebow" / "data" / "pipeline" / "s1_dataset.npz"
S1_CKPTS = {f"v6lat_s{s}": REPO / "icebow" / "data" / "pipeline" / f"s1_icebow_v6lat_s{s}.pt" for s in (0, 1, 2)}
OUT_DIR = Path(__file__).resolve().parent
N_BOOT = 10_000
SANITY_TOL = 1e-4
SANITY_KNOWN = {"gen": {"cell_half_top1": 0.2071, "card_top1": 0.6457},
                "v6lat_s0": {"cell_half_top1": 0.2097, "card_top1": 0.6546}}


def _wait_for_live_play(poll_s: int = 60, timeout_s: int = 45 * 60) -> None:
    """Blocks while a python.exe process is running live_play.py (owner playing a live match)."""
    cmd = ("(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
           "Where-Object CommandLine -like '*live_play.py*' | Measure-Object).Count")
    t0 = time.time()
    while True:
        n = int(subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                               capture_output=True, text=True, check=True).stdout.strip() or 0)
        if n == 0:
            return
        if time.time() - t0 > timeout_s:
            raise SystemExit(f"live_play.py still running after {timeout_s}s wait")
        print(f"[paired_v3val] live_play.py running ({n}); waiting {poll_s}s", file=sys.stderr)
        time.sleep(poll_s)


@torch.no_grad()
def s1_evaluate_rowlog(model: S1Model, rows: S1Rows, grid: str, bs: int = 512) -> tuple[dict, list]:
    """``train_s1.evaluate`` copied line-for-line (not imported/edited -- it has no rowlog), plus a rowlog of
    (row ids, cell_half_ok, cell_tile_ok, card_ok) per batch for PLAY rows, matching ``eval_gen.evaluate``'s."""
    model.eval()
    n = len(rows.idx)
    agg = {"cell_half": 0, "cell_tile": 0, "card": 0, "joint": 0, "n_play": 0, "gate_tp": 0, "gate_tn": 0,
           "n_pos": 0, "n_neg": 0, "wait": 0, "n_wait": 0, "value": 0, "cell_nll": 0.0,
           "place_hit": 0, "place_1t": 0, "place_dist": 0.0}
    off = 0.5 if grid == "floor" else 0.0
    gs, rowlog = [], []
    for s in range(0, n, bs):
        ids = rows.idx[s:s + bs]
        b = rows.batch(ids)
        hm = hand_mask_from_sc(b["sc"])
        out = model(b["tok"], b["mask"], b["sc"], b["past"], card_slot=b["slot"].clamp(min=0), hand_mask=hm)
        play = b["gate"] > 0.5
        if play.any():
            logits = out["cell"][play]
            xy = b["xy"][play]
            t_half = cell_label(xy, grid)
            pred = logits.argmax(-1)
            half_ok = pred == t_half
            agg["cell_half"] += int(half_ok.sum())
            px = (pred % GRID_X).float() + off; py = (pred // GRID_X).float() + off
            dist = torch.sqrt(((px / GRID_X - xy[:, 0]) * (GRID_X / 2)) ** 2 + ((py / GRID_Y - xy[:, 1]) * (GRID_Y / 2)) ** 2)
            agg["place_hit"] += int((dist <= 0.3).sum()); agg["place_1t"] += int((dist <= 1.0).sum())
            agg["place_dist"] += float(dist.sum())
            agg["cell_nll"] += float(Fn.cross_entropy(logits, t_half, reduction="sum"))
            p = logits.softmax(-1).view(-1, GRID_Y // 2, 2, GRID_X // 2, 2).sum((2, 4)).flatten(1)
            t_tile = cell_index(xy, GRID_X // 2, GRID_Y // 2) if grid == "floor" else tile_of_cell(t_half)
            tile_ok = p.argmax(-1) == t_tile
            agg["cell_tile"] += int(tile_ok.sum())
            card_ok = out["card"][play].argmax(-1) == b["slot"][play]
            agg["card"] += int(card_ok.sum())
            agg["joint"] += int((card_ok & tile_ok).sum())
            agg["n_play"] += int(play.sum())
            rowlog.append((np.asarray(ids)[play.cpu().numpy()], half_ok.cpu().numpy(), tile_ok.cpu().numpy(),
                           card_ok.cpu().numpy()))
        g_pred = out["gate"] > 0
        agg["gate_tp"] += int((g_pred & play).sum()); agg["gate_tn"] += int((~g_pred & ~play).sum())
        agg["n_pos"] += int(play.sum()); agg["n_neg"] += int((~play).sum())
        if (~play).any():
            agg["wait"] += int((out["wait"][~play].argmax(-1) == b["wait"][~play]).sum()); agg["n_wait"] += int((~play).sum())
        agg["value"] += int((out["value"].argmax(-1) == b["value"]).sum())
        if len(gs) < 4:
            gs.append(out["g"])
    g = torch.cat(gs)[:512]
    g = Fn.normalize(g, dim=-1)
    cos = (g @ g.t())
    spread = float((cos.sum() - cos.diag().sum()) / (len(g) * (len(g) - 1)))
    np_ = max(agg["n_play"], 1)
    res = {"cell_half_top1": agg["cell_half"] / np_, "cell_tile_top1": agg["cell_tile"] / np_,
           "card_top1": agg["card"] / np_, "joint_top1": agg["joint"] / np_, "cell_nll": agg["cell_nll"] / np_,
           "gate_acc": (agg["gate_tp"] + agg["gate_tn"]) / max(n, 1),
           "gate_bal_acc": 0.5 * (agg["gate_tp"] / max(agg["n_pos"], 1) + agg["gate_tn"] / max(agg["n_neg"], 1)),
           "wait_top1": agg["wait"] / max(agg["n_wait"], 1), "value_acc": agg["value"] / max(n, 1),
           "place_hit": agg["place_hit"] / np_, "place_1t": agg["place_1t"] / np_, "place_dist": agg["place_dist"] / np_,
           "emb_cosine": spread, "n_play": agg["n_play"], "n": n}
    return res, rowlog


def rowlog_to_keys(arrs: dict, rowlog: list) -> dict:
    """rowlog -> {(tag, side, tick): (half_ok, tile_ok, card_ok)} for the PLAY rows it covers."""
    ids = np.concatenate([r[0] for r in rowlog])
    half = np.concatenate([r[1] for r in rowlog])
    tile = np.concatenate([r[2] for r in rowlog])
    card = np.concatenate([r[3] for r in rowlog])
    tags = arrs["tags"][arrs["rep"][ids]]
    side = arrs["side"][ids]
    tick = arrs["tick"][ids]
    keys = list(zip(tags.tolist(), side.tolist(), tick.tolist()))
    dup = len(keys) != len(set(keys))
    out = {k: (bool(h), bool(t), bool(c)) for k, h, t, c in zip(keys, half, tile, card)}
    return out, dup, len(keys)


def boot_delta(gen_sum: np.ndarray, other_sum: np.ndarray, n: np.ndarray, idx: np.ndarray) -> np.ndarray:
    """Replay-clustered bootstrap of the paired delta (gen - other) in pp, for a GIVEN resample of cluster
    indices ``idx`` (n_boot, K) -- the caller draws ``idx`` once and reuses it across seeds/metrics so the
    3-seed mean CI reflects shared resampling noise, not 3 independently-drawn resamples."""
    tot = n[idx].sum(1)
    g_acc = gen_sum[idx].sum(1) / tot
    o_acc = other_sum[idx].sum(1) / tot
    return (g_acc - o_acc) * 100.0


def main() -> int:
    cmd = f"{sys.executable} scratchpad/gauntlet/L68/generalist/paired/paired_v3val.py"
    t_wall0 = time.time()
    _wait_for_live_play()
    dev = torch.device("cpu")

    # ---- generalist ----
    arrs_g, meta_g = load_ds(GEN_DATA)
    model_g, st_g = load_gen_model(GEN_CKPT, dev)
    grid_g = st_g["args"]["grid"]
    v3_idx = np.where(arrs_g["v3val"] == 1)[0]
    rows_g = GenRows(arrs_g, v3_idx, dev)
    log_g: list = []
    res_g = gen_evaluate(model_g, rows_g, bs=512, grid=grid_g, rowlog=log_g)
    keys_g, dup_g, n_g = rowlog_to_keys(arrs_g, log_g)

    # ---- S1 (3 seeds) ----
    arrs_s, meta_s = load_ds(S1_DATA)
    v3_idx_s = np.where(arrs_s["split"] == 1)[0]
    rows_s = S1Rows(arrs_s, v3_idx_s, dev)
    s1_res, s1_keys = {}, {}
    for name, ckpt in S1_CKPTS.items():
        st = torch.load(ckpt, map_location=dev)
        a = st["args"]
        model_s = S1Model(d=int(a["d"]), layers=int(a["layers"])).to(dev)
        model_s.load_state_dict(st["model"])
        res, rowlog = s1_evaluate_rowlog(model_s, rows_s, grid=a["grid"], bs=512)
        s1_res[name] = res
        s1_keys[name], dup_s, n_s = rowlog_to_keys(arrs_s, rowlog)
        if dup_s:
            raise SystemExit(f"{name}: duplicate (tag,side,tick) keys in S1 v3val play rows -- alignment ambiguous")

    if dup_g:
        raise SystemExit("generalist: duplicate (tag,side,tick) keys in v3val play rows -- alignment ambiguous")

    # ---- sanity gate ----
    sanity = {"gen": {k: res_g[k] for k in ("cell_half_top1", "card_top1")},
              "v6lat_s0": {k: s1_res["v6lat_s0"][k] for k in ("cell_half_top1", "card_top1")}}
    gate_ok = all(abs(sanity[grp][k] - SANITY_KNOWN[grp][k]) <= SANITY_TOL
                  for grp in SANITY_KNOWN for k in SANITY_KNOWN[grp])
    if not gate_ok:
        out = {"command": cmd, "BLOCKED": "sanity gate failed", "sanity": sanity, "known": SANITY_KNOWN}
        (OUT_DIR / "paired_v3val.json").write_text(json.dumps(out, indent=1))
        print(json.dumps(out, indent=1))
        return 1

    # ---- alignment: match by (tag, side, tick) ----
    key_sets = {name: set(s1_keys[name]) for name in S1_CKPTS}
    # play-row key set is identical across the 3 seeds (same dataset, same v3val idx, gate independent of model)
    assert key_sets["v6lat_s0"] == key_sets["v6lat_s1"] == key_sets["v6lat_s2"], \
        "S1 play-row key set differs across seeds -- unexpected"
    s1_all_keys = key_sets["v6lat_s0"]
    gen_all_keys = set(keys_g)
    common = sorted(gen_all_keys & s1_all_keys)
    align = {"gen_play_rows": n_g, "s1_play_rows": len(s1_all_keys), "matched": len(common),
             "gen_only": len(gen_all_keys - s1_all_keys), "s1_only": len(s1_all_keys - gen_all_keys)}

    tags_of = np.array([k[0] for k in common])
    uniq_tags, cluster = np.unique(tags_of, return_inverse=True)
    K = len(uniq_tags)
    n_per_cluster = np.bincount(cluster, minlength=K).astype(np.float64)

    def sums(keys_map: dict, field: int) -> np.ndarray:
        vals = np.array([keys_map[k][field] for k in common], dtype=np.float64)
        return np.bincount(cluster, weights=vals, minlength=K)

    gen_sum = {0: sums(keys_g, 0), 2: sums(keys_g, 2)}   # field 0 = cell_half_ok, 2 = card_ok

    rng = np.random.default_rng(0)
    metrics = {"cell_half_top1": 0, "card_top1": 2}
    results: dict = {name: {} for name in S1_CKPTS}
    mean3: dict = {}
    for mname, field in metrics.items():
        # ONE resample of cluster indices per metric, shared across all 3 seeds (and their per-seed CIs), so the
        # 3-seed mean CI is built from per-resample averages of the three seed deltas, not 3 independent draws.
        idx = rng.integers(0, len(n_per_cluster), size=(N_BOOT, len(n_per_cluster)))
        gsum = gen_sum[field]
        gen_correct = np.array([keys_g[k][field] for k in common])
        seed_boot = []
        for name in S1_CKPTS:
            osum = sums(s1_keys[name], field)
            s1_correct = np.array([s1_keys[name][k][field] for k in common])
            gen_acc, s1_acc = float(gen_correct.mean()), float(s1_correct.mean())
            delta_pp = (gen_acc - s1_acc) * 100.0
            boot = boot_delta(gsum, osum, n_per_cluster, idx)
            seed_boot.append(boot)
            gen_only = int((gen_correct & ~s1_correct).sum())
            s1_only = int((~gen_correct & s1_correct).sum())
            results[name][mname] = {
                "n": len(common), "gen_acc": gen_acc, "s1_acc": s1_acc, "delta_pp": delta_pp,
                "ci95_pp": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
                "mcnemar": {"gen_only_correct": gen_only, "s1_only_correct": s1_only},
            }
        per_seed_delta = [results[name][mname]["delta_pp"] for name in S1_CKPTS]
        combined_boot = np.mean(np.stack(seed_boot), axis=0)   # per-resample average of the 3 seed deltas
        mean3[mname] = {"delta_pp": float(np.mean(per_seed_delta)),
                        "ci95_pp": [float(np.percentile(combined_boot, 2.5)), float(np.percentile(combined_boot, 97.5))]}

    wall_s = round(time.time() - t_wall0, 1)
    out = {"command": cmd, "wall_seconds": wall_s, "n_boot": N_BOOT, "seed": 0,
           "sanity_gate": {"pass": True, "measured": sanity, "known": SANITY_KNOWN, "tol": SANITY_TOL},
           "alignment": align, "results": results, "mean_3seed_delta": mean3}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "paired_v3val.json").write_text(json.dumps(out, indent=1))
    print(f"# {cmd}\n# wall={wall_s}s\n")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
