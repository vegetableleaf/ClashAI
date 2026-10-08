"""F2 / F3 model passes (VM CPU, nice; no training). Threat index from threats.py (laptop) -> ~/defense/threat_index.json.gz.

  pro  : icebow-deck (90) PRO play rows of gen_dataset_v32_fv5, NON-train split, in threatened states (one lane >= 3 elixir of
         enemy value on my half, nearest pro frame within 10 ticks). Per row and model: card distribution over the affordable
         hand (live rule: cost <= floor(model elixir)), top card, and the cell argmax for the PRO's card vs the pro placement.
         Models: towerref_w2 (live, 41b52a83) full / its 'cr' variant (TowerRefine off) / the stack2k base checkpoint.
  live : every threatened decision of the towerref_w2 live logs (~/econ2/live_logs), batch rebuilt by L73/lethal_rocket/rebuild.py (dep = ~/defense/repo_dep:
         repo_main + main's pipeline/own_ability.py, i.e. as deployed; hero = ~/econ2/repo_hero, econ2's Hero IW
         own-ability parity fix). Same per-row outputs + what the bot did.
  sum  : tables -> stdout.
  cd ~/defense && CB_REPO=~/econ2/repo_main nice -n 15 ~/venv/bin/python f2f3_vm.py pro
                  CB_REPO=~/defense/repo_dep nice -n 15 ~/venv/bin/python f2f3_vm.py live dep
                  CB_REPO=~/econ2/repo_hero nice -n 15 ~/venv/bin/python f2f3_vm.py live hero
                  ~/venv/bin/python f2f3_vm.py sum
Public information only (the rebuilt batch is the live model input; pro rows are the imitation inputs)."""
import os, sys, json, gzip, pickle, zipfile, collections
import numpy as np

HOME = os.path.expanduser("~")
REPO = os.environ.get("CB_REPO", HOME + "/econ2/repo_main")
sys.path.insert(0, REPO); sys.path.insert(0, HOME + "/econ2/repo_main/scratchpad/gauntlet/L73/lethal_rocket")
HERE = HOME + "/defense/"
NPZ = HOME + "/ClashBot/icebow/data/pipeline/gen_dataset_v32_fv5.npz"
TW2 = HOME + "/probe_rocket/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt"
STACK = HOME + "/ClashBot/icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref.pt"
KEYS = ["sc", "hand_card", "hand_form", "next_card", "next_form", "deck_card", "deck_form", "past", "y_gate", "y_card", "y_hand_pos", "y_xy",
        "y_wait_card", "y_wait_dt", "y_crowns", "tick", "side", "rep", "split", "deck_id", "opp_past", "opp_cycle", "projectiles", "effects",
        "own_ability", "y_cell"]
NICE = {"tornado": "Tornado", "the-log": "Log", "skeletons": "Skeletons", "knight": "Knight", "ice-wizard": "IceWizard", "tesla": "Tesla",
        "x-bow": "Xbow", "rocket": "Rocket"}
GX, GY = 36, 64


def take(zf, name, idx):
    idx = np.asarray(idx)
    with zf.open(name + ".npy") as f:
        ver = np.lib.format.read_magic(f)
        shape, _, dt = (np.lib.format.read_array_header_1_0(f) if ver == (1, 0) else np.lib.format.read_array_header_2_0(f))
        rb = int(np.prod(shape[1:], dtype=np.int64)) * dt.itemsize
        out = np.empty((len(idx),) + tuple(shape[1:]), dt); step = max(1, (96 << 20) // max(rb, 1)); o = 0
        for lo in range(0, shape[0], step):
            n = min(step, shape[0] - lo); buf = bytearray()
            while len(buf) < n * rb:
                c = f.read(n * rb - len(buf))
                if not c: raise EOFError(name)
                buf += c
            a, b = np.searchsorted(idx, [lo, lo + n])
            if b > a:
                out[o:o + b - a] = np.frombuffer(buf, dt).reshape((n,) + tuple(shape[1:]))[idx[a:b] - lo]; o += b - a
    return out


def cell_xy(c):
    """cell index -> own-frame tiles (lattice grid: no half-cell offset; model y = 0 at the enemy edge)."""
    return (c % GX) / GX * 18.0, 32.0 - (c // GX) / GY * 32.0


def index():
    with gzip.open(HERE + "threat_index.json.gz", "rt") as fh: return json.load(fh)


def pro_mode():
    import torch
    from pipeline.eval_gen import GenRows
    from pipeline.model_gen import load_model
    from pipeline.opp_elixir_count import card_cost
    from rebuild import variant
    torch.set_num_threads(16)
    TI = index()["pros"]
    z = np.load(NPZ, allow_pickle=False); meta = json.loads(str(z["meta"])); CV = meta["card_vocab"]
    tags, rep, side, tick, yg, dk, split = (z[k] for k in ("tags", "rep", "side", "tick", "y_gate", "deck_id", "split"))
    print("split values", np.unique(split, return_counts=True), flush=True)
    cand = np.flatnonzero((dk == 90) & (yg == 1) & (split != 0))
    sel, thr = [], []
    fr = {k: (np.array([x[0] for x in v]), v) for k, v in TI.items() if v}
    for i in cand:
        k = f"{str(tags[rep[i]])[:12]}|{int(side[i])}"
        if k not in fr: continue
        T, V = fr[k]; j = int(np.argmin(np.abs(T - int(tick[i]))))
        if abs(int(T[j]) - int(tick[i])) <= 10: sel.append(int(i)); thr.append(V[j])
    sel = np.array(sel); print("non-train deck-90 play rows", len(cand), "threatened", len(sel), flush=True)
    zf = zipfile.ZipFile(NPZ)
    sub = {k: take(zf, k, sel) for k in KEYS}
    off = z["off"]; lens = off[sel + 1] - off[sel]
    gather = np.concatenate([np.arange(off[i], off[i + 1]) for i in sel])
    sub["tok"] = take(zf, "tok", gather); sub["unit_form"] = take(zf, "unit_form", gather)
    sub["off"] = np.concatenate([[0], np.cumsum(lens)]).astype(np.int64)
    n = len(sel)
    COST = np.array([0.0] + [card_cost(c.replace("-", "_")) or 0.0 for c in CV[1:]])
    hand = sub["hand_card"].astype(int); el = sub["sc"][:, 3] * 10
    aff = (hand > 0) & (COST[hand] <= np.floor(el + 1e-3)[:, None] + 1e-6)
    g = GenRows(sub, np.arange(n), torch.device("cpu"))
    res = dict(sel=sel, thr=thr, el=el, hand=[[NICE.get(CV[c], CV[c]) for c in h] for h in hand], aff=aff,
               pro_card=[NICE.get(CV[c], CV[c]) for c in sub["y_card"].astype(int)], pro_xy=sub["y_xy"].astype(float), models={})
    tw2, _ = load_model(TW2, torch.device("cpu")); tw2.eval()
    stk, _ = load_model(STACK, torch.device("cpu")); stk.eval()
    for name, model, var in (("towerref", tw2, "full"), ("towerref_noTR", tw2, "cr"), ("stack2k", stk, "full")):
        P = np.zeros((n, 4), np.float32); cell = np.zeros(n, np.int64); gate = np.zeros(n, np.float32)
        with variant(model, var), torch.no_grad():
            for s in range(0, n, 256):
                ids = np.arange(s, min(n, s + 256)); b = g.batch(ids)
                o = model(b); lg = o["card"].float().clone(); lg[~torch.from_numpy(aff[ids])] = -torch.inf
                P[ids] = torch.softmax(lg, -1).numpy(); gate[ids] = torch.sigmoid(o["gate"].float()).numpy()
                cell[ids] = model(b, card=b["card"], form=b["form"])["cell"].float().argmax(-1).numpy()
        res["models"][name] = dict(P=P, cell=cell, gate=gate)
        print(name, "done", flush=True)
    pickle.dump(res, open(HERE + "pro_res.pkl", "wb"))


def live_one(args):
    f, tag = args
    import torch, rebuild as RB
    from pipeline.model_gen import load_model
    torch.set_num_threads(1)
    TI = index()["live"].get(f) or []
    want = {x[0]: x for x in TI}
    m = RB.Match(os.path.join(HOME, "econ2/live_logs", f), TW2, "cpu")
    stk, _ = load_model(STACK, torch.device("cpu")); stk.eval()
    plays = {e["tick"]: e["name"] for e in m.ev if e.get("event") == "play"}
    out = []
    for i, d in enumerate(m.dec):
        if d["tick"] not in want: continue
        b, info = m.batch(i)
        al = torch.from_numpy(info["allowed"])
        r = dict(file=f, tick=d["tick"], thr=want[d["tick"]], el=float(b["sc"][0, 3]) * 10, names=info["names"], allowed=info["allowed"].tolist(),
                 log_play=bool(d["decision"].get("play")), log_name=d["decision"].get("name"), played=plays.get(d["tick"]),
                 log_p=d["decision"].get("p_play"))
        with torch.no_grad():
            for name, model in (("towerref", m.model), ("stack2k", stk)):
                o = model(b); lg = o["card"][0].float().clone(); lg[~al] = -torch.inf
                r[name] = dict(P=torch.softmax(lg, -1).numpy().tolist(), p=float(torch.sigmoid(o["gate"][0])))
        out.append(r)
    return out


def live_mode(tag):
    from multiprocessing import Pool
    fs = sorted(os.listdir(HOME + "/econ2/live_logs")); L = []
    with Pool(16) as pool:
        for r in pool.imap_unordered(live_one, [(f, tag) for f in fs]): L += r
    pickle.dump(L, open(HERE + f"live_res_{tag}.pkl", "wb"))
    print("live", tag, "threatened decisions", len(L), "logs", len(fs))


CARDS = ("Tornado", "Log", "Skeletons", "Knight", "IceWizard", "Tesla", "Xbow", "Rocket")


def ebk(e): return "<2" if e < 2 else "2-4" if e < 4 else "4-6" if e < 6 else "6+"


def dist_tab(rows, key):
    c = collections.Counter(key(r) for r in rows); n = max(1, len(rows))
    return "  ".join(f"{x} {c[x] / n:.2f}" for x in CARDS) + f"  (n {len(rows)})"


def summary():
    R = pickle.load(open(HERE + "pro_res.pkl", "rb"))
    n = len(R["sel"])
    pro_def = np.array([(1 - R["pro_xy"][i][1]) * 32 <= 18 for i in range(n)])
    v = np.array([t[3] for t in R["thr"]])
    print("## F2 PRO threatened play rows: what pros played vs the model's top card (affordable hand), by model elixir")
    for vmin in (3, 5):
        for b in ("<2", "2-4", "4-6", "6+"):
            ids = [i for i in range(n) if ebk(R["el"][i]) == b and v[i] >= vmin]
            if not ids: continue
            print(f"value>={vmin} el {b:3s} pros      :", dist_tab(ids, lambda i: R["pro_card"][i]))
            for mn in ("towerref", "stack2k"):
                P = R["models"][mn]["P"]
                print(f"value>={vmin} el {b:3s} {mn:10s}:", dist_tab(ids, lambda i: R["hand"][i][int(P[i].argmax())]),
                      f" card top-1 {np.mean([R['hand'][i][int(P[i].argmax())] == R['pro_card'][i] for i in ids]):.3f}")
            for c in ("Tornado", "Log"):
                pm = [float(sum(R["models"]["towerref"]["P"][i][k] for k in range(4) if R["hand"][i][k] == c)) for i in ids if c in [R["hand"][i][k] for k in range(4) if R["aff"][i][k]]]
                pp = [R["pro_card"][i] == c for i in ids if c in [R["hand"][i][k] for k in range(4) if R["aff"][i][k]]]
                if pm: print(f"      {c} affordable: rows {len(pm)} mean P(towerref) {np.mean(pm):.3f}  pro played it {np.mean(pp):.3f}")
    print("\n## F3 PRO defensive rows (threatened, pro placement own y <= 18): card top-1 and cell within 1 tile of the pro (cell for the pro's card)")
    xy = R["pro_xy"]
    def cell_d(mn, i):
        X, Y = cell_xy(int(R["models"][mn]["cell"][i])); return float(np.hypot(X - xy[i][0] * 18, Y - (1 - xy[i][1]) * 32))
    for scope, ids in (("all defensive", [i for i in range(n) if pro_def[i]]), ("defensive el < 4", [i for i in range(n) if pro_def[i] and R["el"][i] < 4]),
                       ("defensive el >= 4", [i for i in range(n) if pro_def[i] and R["el"][i] >= 4])):
        for mn in ("towerref", "towerref_noTR", "stack2k"):
            P = R["models"][mn]["P"]
            top = np.mean([R["hand"][i][int(P[i].argmax())] == R["pro_card"][i] for i in ids])
            d = [cell_d(mn, i) for i in ids]
            print(f"  {scope:18s} {mn:14s} n={len(ids)} card top-1 {top:.3f}  cell <= 1 tile {np.mean([x <= 1 for x in d]):.3f}  median dist {np.median(d):.2f}")
    print("  per card (pro's card), cell <= 1 tile  towerref / noTR / stack2k:")
    for c in CARDS:
        ids = [i for i in range(n) if pro_def[i] and R["pro_card"][i] == c]
        if len(ids) < 30: continue
        print(f"    {c:10s} n={len(ids):5d} " + " / ".join(f"{np.mean([cell_d(mn, i) <= 1 for i in ids]):.3f}" for mn in ("towerref", "towerref_noTR", "stack2k"))
              + "   median dist " + " / ".join(f"{np.median([cell_d(mn, i) for i in ids]):.2f}" for mn in ("towerref", "towerref_noTR", "stack2k")))
    ids = [i for i in range(n) if pro_def[i] and R["pro_card"][i] == "IceWizard"]
    if ids:
        print("  Ice Wizard (pro's defensive IW rows): model cell minus pro placement, own frame (dY > 0 = further from my towers), |dX|")
        for mn in ("towerref", "towerref_noTR", "stack2k"):
            dY = [cell_xy(int(R["models"][mn]["cell"][i]))[1] - (1 - xy[i][1]) * 32 for i in ids]
            dX = [abs(cell_xy(int(R["models"][mn]["cell"][i]))[0] - xy[i][0] * 18) for i in ids]
            print(f"    {mn:14s} dY median {np.median(dY):+.2f} mean {np.mean(dY):+.2f}  |dX| median {np.median(dX):.2f}  share dY > +1 {np.mean([y > 1 for y in dY]):.3f}  dY < -1 {np.mean([y < -1 for y in dY]):.3f}")
    # paired disagreement towerref vs stack2k on defensive rows
    ids = [i for i in range(n) if pro_def[i]]
    ct = [R["hand"][i][int(R["models"]["towerref"]["P"][i].argmax())] for i in ids]; cs = [R["hand"][i][int(R["models"]["stack2k"]["P"][i].argmax())] for i in ids]
    diff = [k for k in range(len(ids)) if ct[k] != cs[k]]
    print(f"  top card differs towerref vs stack2k on {len(diff)}/{len(ids)} defensive rows; on those: towerref right {np.mean([ct[k] == R['pro_card'][ids[k]] for k in diff]):.3f}, stack2k right {np.mean([cs[k] == R['pro_card'][ids[k]] for k in diff]):.3f}")
    print("  changes (stack2k -> towerref):", collections.Counter((cs[k], ct[k]) for k in diff).most_common(8))
    for tag in ("dep", "hero"):   # dep = main pipeline as deployed; hero = econ2 Hero IW own-ability fix (~/econ2/repo_main carries it too since 22:36 UTC)
        p = HERE + f"live_res_{tag}.pkl"
        if not os.path.exists(p): continue
        L = pickle.load(open(p, "rb"))
        print(f"\n## F2 LIVE threatened decisions (towerref_w2 logs, rebuild via repo_{tag}): model top card over the allowed hand, by model elixir")
        for vmin in (3, 5):
            for b in ("<2", "2-4", "4-6", "6+"):
                rs = [r for r in L if ebk(r["el"]) == b and r["thr"][3] >= vmin]
                if not rs: continue
                for mn in ("towerref", "stack2k"):
                    print(f"value>={vmin} el {b:3s} {mn:10s} all states :", dist_tab(rs, lambda r, mn=mn: r["names"][int(np.argmax(r[mn]["P"]))]))
                pl = [r for r in rs if r["played"]]
                if pl:
                    print(f"value>={vmin} el {b:3s} towerref   play states:", dist_tab(pl, lambda r: r["names"][int(np.argmax(r["towerref"]["P"]))]))
                    print(f"value>={vmin} el {b:3s} bot PLAYED            :", dist_tab(pl, lambda r: r["played"]))
                for c in ("Tornado", "Log"):
                    pm = [sum(r["towerref"]["P"][k] for k in range(4) if r["names"][k] == c) for r in rs if any(r["names"][k] == c and r["allowed"][k] for k in range(4))]
                    if pm: print(f"      {c} affordable: states {len(pm)} mean P(towerref) {np.mean(pm):.3f}")
        print("  gate p (towerref) median by elixir:", {b: round(float(np.median([r['towerref']['p'] for r in L if ebk(r['el']) == b])), 3) for b in ('<2', '2-4', '4-6', '6+') if any(ebk(r['el']) == b for r in L)})
        err = [abs(r["towerref"]["p"] - r["log_p"]) for r in L if r["log_p"] is not None]
        print(f"  rebuild check: |rebuilt p - logged p| median {np.median(err):.4f}; logged top card == rebuilt top {np.mean([r['log_name'] == r['names'][int(np.argmax(r['towerref']['P']))] for r in L]):.3f}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "pro": pro_mode()
    elif a[0] == "live": live_mode(a[1])
    else: summary()
