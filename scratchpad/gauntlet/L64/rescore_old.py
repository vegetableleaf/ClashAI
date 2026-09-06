"""L64: score the OLD BC init (432-cell PolicyNet) on the NEW S1 corpus (corpus_v3 icebow VAL replays, play_frames).
Reuses build_bc_v2.assemble_tag (obs rendering, unchanged) and knn_vs_bc_v2.forward_all/score (unchanged).
    cd icebow && PYTHONHASHSEED=0 ./.venv/Scripts/python.exe ../scratchpad/gauntlet/L64/rescore_old.py
"""
import importlib.util, json, sys, time, zlib, collections
from pathlib import Path
import numpy as np
import torch

ROOT = Path("C:/Users/benpe/ClashBot"); ICEBOW = ROOT / "icebow"
OUT = ROOT / "scratchpad/gauntlet/L64"
SHARDS = OUT / "rescore_old_shards"
CORPUS = ROOT / "scratchpad/gauntlet/ext/corpus_v3/icebow"
CKPT = ICEBOW / "data/bc_pro/models/bc_bias_native_s0.pt"
VAL_PCT = 15


def load(p, name):
    spec = importlib.util.spec_from_file_location(name, str(p)); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


B2 = load(ROOT / "scratchpad/gauntlet/L61/build_bc_v2.py", "bbv2")
K2 = load(ROOT / "scratchpad/gauntlet/L61/knn_vs_bc_v2.py", "kvb2")
K2.CKPT = CKPT
ENGINE_NAME, ICEBOW_BASES = B2.ENGINE_NAME, B2.ICEBOW_BASES


def deck_sides(rec):
    out = []
    for s in (0, 1):
        names = (rec.get("final_decks") or {}).get(str(s)) or []
        bases = [ENGINE_NAME.get(n.split("@")[0]) for n in names]
        if len(names) == 8 and all(bases) and set(bases) == ICEBOW_BASES and len(set(bases)) == 8:
            out.append(s)
    return out


def is_val(tag):
    return (zlib.crc32(tag.encode()) % 100) < VAL_PCT


def stage_assemble(force=False):
    B2.init_worker()
    SHARDS.mkdir(parents=True, exist_ok=True)
    files = sorted(CORPUS.glob("replay_*.json"))
    st = collections.Counter(); t0 = time.time(); done = []
    for f in files:
        tag = f.name[len("replay_"):-len(".json")]
        if not is_val(tag):
            st["train_skipped"] += 1; continue
        rec = json.loads(f.read_text(encoding="utf-8"))
        assert rec["tag"] == tag
        sides = deck_sides(rec)
        if not sides:
            st["val_no_deck_side"] += 1; continue
        if "play_frames" not in rec:
            st["val_no_play_frames"] += 1; continue
        for fs in sides:
            jf = SHARDS / f"{tag}_{fs}.json"
            if jf.exists() and not force:
                s = json.loads(jf.read_text())["summary"]
            else:
                s = B2.assemble_tag(tag, fs, rec, {}, SHARDS)
            st["drives"] += 1; st["samples"] += s["samples"]; st["hand_mismatch"] += s["hand_mismatch"]
            st["hand_checked"] += s["hand_checked"]; st["focus_play_frames"] += s["n_play_frames_focus"]
            st["hand_source_" + s["hand_source"]] += 1
            done.append(s)
        log_by_pi = {int(e["play_index"]): e for e in rec["log"] if "play_index" in e}
        for fr in rec["play_frames"]:
            if fr["side"] in sides and not log_by_pi.get(int(fr["play_index"]), {}).get("accepted"):
                st["focus_play_not_accepted"] += 1
    print(f"[assemble] {dict(st)} {time.time()-t0:.0f}s", flush=True)
    (OUT / "rescore_old_assemble.json").write_text(json.dumps({"stats": dict(st), "drives": done}, indent=1))
    return st


def load_shards(device):
    from clashrl.config import Config
    from clashrl.actions import ActionSpace
    metas, arrs = [], collections.defaultdict(list)
    for jf in sorted(SHARDS.glob("*.json")):
        d = json.loads(jf.read_text())
        if not d["meta"]:
            continue
        z = np.load(jf.with_suffix(".npz"))
        for k in ("obs", "hands", "nexts", "elixirs", "threats", "acts"):
            arrs[k].append(z[k])
        metas.extend(d["meta"])
    A = {k: np.concatenate(v) for k, v in arrs.items()}
    n = len(metas); assert n == len(A["obs"])
    acts = torch.from_numpy(A["acts"]).long()
    cell = acts[:, 2] * K2.GW + acts[:, 1]
    meta = {"seconds": np.array([float(m["seconds"]) for m in metas]), "anywhere": np.array([int(m["anywhere"]) for m in metas]),
            "pocket": np.array([int(m["pocket_code"]) for m in metas]), "card_key": np.array([m["card_key"] for m in metas]),
            "cell": np.array([int(m["cell"]) for m in metas]), "tag": np.array([m["tag"] for m in metas]),
            "side": np.array([int(m["side"]) for m in metas]), "play_index": np.array([int(m["play_index"]) for m in metas]),
            "tick": np.array([int(m["tick"]) for m in metas]), "x_units": np.array([int(m["x_units"]) for m in metas]),
            "y_units": np.array([int(m["y_units"]) for m in metas]), "own_nx": np.array([float(m["own_nx"]) for m in metas]),
            "own_ny": np.array([float(m["own_ny"]) for m in metas]), "card_id": acts[:, 0].numpy(),
            "hand_match_engine": np.array([int(m["hand_match_engine"]) for m in metas]),
            "snap": np.array([float(m["snap_dist_tiles"]) for m in metas])}
    assert (meta["cell"] == cell.numpy()).all()
    cfg = Config.load(ICEBOW / "config" / "config.yaml"); AS = ActionSpace(cfg)
    masks = torch.zeros(2, 4, K2.GW * K2.GH, dtype=torch.bool)
    for a in (0, 1):
        for pk in range(4):
            masks[a, pk] = torch.tensor(AS.deployable_mask(bool(a), (bool(pk & 2), bool(pk & 1))))
    row_mask = masks[torch.from_numpy(meta["anywhere"]), torch.from_numpy(meta["pocket"])]
    T = dict(obs=torch.from_numpy(A["obs"]).to(device), hands=torch.from_numpy(A["hands"]).float().to(device),
             nexts=torch.from_numpy(A["nexts"]).float().to(device), elx=torch.from_numpy(A["elixirs"]).float().to(device),
             thr=torch.from_numpy(A["threats"]).float().to(device), card=acts[:, 0].to(device), cell=cell.to(device),
             mask=row_mask.to(device))
    # cell centres in BOARD space = the sim env's _board_action_space (what build_bc_v2.nearest_cell labelled with);
    # the plain ActionSpace(cfg) above is only used for the deployable mask, exactly as knn_vs_bc_v2.load_all does
    centers = np.asarray(B2._W["centers"], np.float64)
    assert centers.shape == (AS.n_cells, 2)
    return T, meta, centers, AS


def tile(xy):
    cx = np.clip(np.floor(xy[:, 0] * 18).astype(int), 0, 17); cy = np.clip(np.floor(xy[:, 1] * 32).astype(int), 0, 31)
    return cy * 18 + cx


def main():
    force = "--force" in sys.argv
    stage_assemble(force)
    dev = torch.device("cuda")
    T, meta, centers, AS = load_shards(dev)
    net, ck = K2.load_net(dev)
    n = len(meta["cell"]); idx = np.arange(n)
    o = K2.forward_all(net, T, idx, want=("cells",))
    r, hit1, hit5 = K2.score(o["cells"], T["cell"], meta, idx, "old init on S1 val plays (432 grid)")
    lines = [f"[S1 val] matches={ck.get('matches')} {K2.fmt(r)}"]
    for s in (0, 1):
        m = meta["side"] == s
        lines.append(f"  side {s}: n {m.sum()} top1 {hit1[m].mean()*100:.2f} top5 {hit5[m].mean()*100:.2f}")
    hm = meta["hand_match_engine"]
    for v in (1, 0, -1):
        m = hm == v
        if m.any():
            lines.append(f"  hand_match_engine={v}: n {m.sum()} top1 {hit1[m].mean()*100:.2f} top5 {hit5[m].mean()*100:.2f}")
    lines.append(f"  snap_dist_tiles mean {meta['snap'].mean():.3f} max {meta['snap'].max():.3f}; unique (tag,side) {len(set(zip(meta['tag'].tolist(), meta['side'].tolist())))}; unique tags {len(set(meta['tag'].tolist()))}")
    probs = torch.softmax(o["cells"], dim=1)
    am = o["cells"].argmax(1).cpu().numpy()
    probs = probs.cpu().numpy().astype(np.float32)
    am_xy = centers[am]
    pro_xy = np.stack([meta["own_nx"], meta["own_ny"]], 1)
    t_pred, t_pro = tile(am_xy), tile(pro_xy)
    tile1 = (t_pred == t_pro).mean() * 100
    cell_tile = tile(centers)
    tile_mass = np.zeros((n, 18 * 32), np.float32)
    for c in range(len(centers)):
        tile_mass[:, cell_tile[c]] += probs[:, c]
    top5t = np.argsort(-tile_mass, 1)[:, :5]
    tile5 = (top5t == t_pro[:, None]).any(1).mean() * 100
    tile1_mass = (tile_mass.argmax(1) == t_pro).mean() * 100
    dist = np.hypot((am_xy[:, 0] - pro_xy[:, 0]) * 18, (am_xy[:, 1] - pro_xy[:, 1]) * 32)
    lines.append(f"[S1 val, 1-tile 18x32 grid] n {n} top1(argmax cell -> tile) {tile1:.2f}  top1(tile prob mass) {tile1_mass:.2f}  top5(tile mass) {tile5:.2f}")
    lines.append(f"[S1 val] |argmax - pro| tiles: mean {dist.mean():.2f} median {np.median(dist):.2f} p90 {np.percentile(dist,90):.2f}; within 1 tile {np.mean(dist<=1)*100:.1f}% within 2 {np.mean(dist<=2)*100:.1f}%")
    # leakage: replays the OLD model was trained on (bc_pro v1 split train_tags) that fall in the S1 val split
    old_train = set(json.load(open(ICEBOW / "data/bc_pro/split.json"))["train_tags"])
    in_old_train = np.isin(meta["tag"], list(old_train))
    cl = ~in_old_train
    lines.append(f"[leak] S1-val tags in old-model TRAIN split: {len(set(meta['tag'][in_old_train].tolist()))}/{len(set(meta['tag'].tolist()))} tags, {int(in_old_train.sum())}/{n} rows; "
                 f"on those rows top1 {hit1[in_old_train].mean()*100:.2f} top5 {hit5[in_old_train].mean()*100:.2f}")
    lines.append(f"[S1 val CLEAN (never seen by old model)] n {int(cl.sum())} 432-grid top1 {hit1[cl].mean()*100:.2f} top5 {hit5[cl].mean()*100:.2f} | "
                 f"1-tile top1 {(t_pred[cl]==t_pro[cl]).mean()*100:.2f} top5(tile mass) {(top5t[cl]==t_pro[cl,None]).any(1).mean()*100:.2f}; within 1 tile {np.mean(dist[cl]<=1)*100:.1f}%")
    lines.append(f"[grid] board ActionSpace (sim env) gw {AS.gw} gh {AS.gh} n_cells {AS.n_cells}; centre y range {centers[:,1].min():.4f}..{centers[:,1].max():.4f} (row pitch {(centers[:,1].max()-centers[:,1].min())/(AS.gh-1)*32:.3f} tiles); x range {centers[:,0].min():.4f}..{centers[:,0].max():.4f} (col pitch {(centers[:,0].max()-centers[:,0].min())/(AS.gw-1)*18:.3f} tiles)")
    np.savez_compressed(OUT / "rescore_old_preds.npz",
                        tag=meta["tag"], play_index=meta["play_index"], side=meta["side"], tick=meta["tick"],
                        card_id=meta["card_id"], card_key=meta["card_key"], pro_engine_xy=np.stack([meta["x_units"], meta["y_units"]], 1).astype(np.int32),
                        pro_frame_xy=pro_xy.astype(np.float32), pro_cell432=meta["cell"].astype(np.int32),
                        argmax_cell432=am.astype(np.int32), argmax_frame_xy=am_xy.astype(np.float32),
                        probs432=probs, mask432=T["mask"].cpu().numpy(), cell432_centers=centers.astype(np.float32),
                        hit1=hit1.astype(np.int8), hit5=hit5.astype(np.int8), tile18x32_pred=t_pred.astype(np.int32),
                        tile18x32_pro=t_pro.astype(np.int32), hand_match_engine=meta["hand_match_engine"].astype(np.int8),
                        seconds=meta["seconds"].astype(np.float32), in_old_train=in_old_train.astype(np.int8))
    try:
        z = np.load(ICEBOW / "data/pipeline/s1_dataset.npz", allow_pickle=False)
        tags = z["tags"]; sel = (z["split"] == 1) & (z["y_gate"] == 1)
        new_keys = list(zip(tags[z["rep"][sel]].tolist(), z["side"][sel].tolist(), z["tick"][sel].tolist()))
        keys_new = set(new_keys)
        old_keys = list(zip(meta["tag"].tolist(), meta["side"].tolist(), meta["tick"].tolist()))
        keys_old = set(old_keys)
        lines.append(f"[join] s1_dataset val play rows {int(sel.sum())} ({len(set(tags[z['rep'][sel]].tolist()))} tags); old-instrument rows {n} (dup keys old {n-len(keys_old)}, new {len(new_keys)-len(keys_new)}); "
                     f"matched (tag,side,tick) {len(keys_new & keys_old)}; only-new {len(keys_new-keys_old)}; only-old {len(keys_old-keys_new)}")
        k2i = {k: i for i, k in enumerate(old_keys)}
        d = []
        for j in np.where(sel)[0]:
            k = (str(tags[z["rep"][j]]), int(z["side"][j]), int(z["tick"][j]))
            if k in k2i:
                d.append(np.abs(z["y_xy"][j] - pro_xy[k2i[k]]).max())
        d = np.array(d)
        lines.append(f"[join] max |y_xy(new) - own_nxy(old)| over matched rows: {d.max():.5f} (mean {d.mean():.6f})")
        only_new = sorted(keys_new - keys_old)[:5]; only_old = sorted(keys_old - keys_new)[:5]
        lines.append(f"[join] examples only-new {only_new} only-old {only_old}")
    except Exception as ex:
        lines.append(f"[join] failed: {ex!r}")
    txt = "\n".join(lines); print(txt)
    (OUT / "rescore_old_summary.txt").write_text(txt)
    json.dump(r, open(OUT / "rescore_old_score.json", "w"), indent=1)


if __name__ == "__main__":
    main()
