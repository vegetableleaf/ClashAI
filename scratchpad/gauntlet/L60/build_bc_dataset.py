"""L60: PRO behaviour-cloning dataset. Drives every usable RoyaleAPI replay through OUR sim (the L51 parity driver:
both sides L11, princess towers, 40-tick elixir slack, tail cap 360 s) and, IMMEDIATELY BEFORE each accepted deploy
of the FOCUS side, records the exact observation SimMatchEnv would hand the policy (obs image + hand/next/elixir/threat
vectors, team-0 frame), the pro's card identity (policy vocabulary, evo rule = the sim's) and the pro's cell
(nearest env.actions.cell_center over the 18x24 grid).

FRAME. L51 maps corpus side 0 (red) to sim team 0 = the bottom = "me" in SimMatchEnv's obs pipeline (team=0 is hard-coded
there). To make blue "me" the drive is MIRRORED exactly like L51 --mirror (sides swapped, x -> 18000-x, y -> 32000-y).
The icebow deck is the BLUE deck in every usable replay, so the mirrored drive is the main one; the un-mirrored drive is
run only for the replays whose RED deck is icebow too.

HAND. scratchpad/gauntlet/ext/batch/replay_<tag>.json (real-engine record, 211 replays) carries the engine's inferred
opening queue (deal_probe.canonical.<side>.hand_pos + cycle_pos over final_decks) and hand_before per play; the queue is
simulated (played card -> back) and checked against hand_before. Without a record: heuristic queue, first-play order.

Stages (--stage): drive (multiprocess, shards), baseline (checkpoint top-1/top-5 per sample), assemble (dataset.npz +
meta.csv + split.json, streamed so RAM stays flat), report (numbers). Default: all.

    cd icebow && PYTHONHASHSEED=0 ./.venv/Scripts/python.exe ../scratchpad/gauntlet/L60/build_bc_dataset.py --workers 4
"""
import argparse, csv, json, os, sys, time, importlib.util, zipfile, zlib
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
ICEBOW = ROOT / "icebow"
sys.path.insert(0, str(ICEBOW / "src"))
_spec = importlib.util.spec_from_file_location("sim_replay_drive", ROOT / "scratchpad/gauntlet/L51/sim_replay_drive.py")
L51 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(L51)

TICK_S = 0.05
EXT = ROOT / "scratchpad/gauntlet/ext"
OUT_DEFAULT = ICEBOW / "data" / "bc_pro"
CKPT_DEFAULT = ICEBOW / "data" / "bench" / "c2r_best_36k_backup.pt"
ENGINE_NAME = {"Xbow": "x_bow", "Skeletons": "skeletons", "Tesla": "tesla", "Knight": "knight", "Log": "the_log",
               "Tornado": "tornado", "IceWizard": "ice_wizard", "Rocket": "rocket"}
ICEBOW_BASES = frozenset(ENGINE_NAME.values())
META_KEYS = ["tag", "side", "play_index", "tick", "seconds", "sim_t", "delay_ticks", "card_slug", "card_key", "card_id",
             "gx", "gy", "cell", "snap_dist_tiles", "x_units", "y_units", "own_nx", "own_ny", "hand_source",
             "hand_certain", "hand_match_engine", "sim_elixir", "eng_elixir_before", "elixir_diff", "anywhere",
             "pocket_code", "sim_crowns_me", "sim_crowns_them", "my_towers_alive", "their_towers_alive", "n_units_me",
             "n_units_them", "hand_ids"]


def key_base(slug: str) -> str:
    return slug.replace("-ev1", "").replace("-hero", "").replace("-", "_")


def engine_queue(rec: dict, side: int):
    """Initial 8-slot queue (base keys, hand first) from the real-engine record, or None."""
    try:
        deck = [n.split("@")[0] for n in rec["final_decks"][str(side)]]
        probe = rec["deal_probe"]["canonical"][str(side)]
        order = list(probe["hand_pos"]) + list(probe["cycle_pos"])
        names = [deck[i] for i in order]
        if any(n not in ENGINE_NAME for n in names):
            return None
        return [ENGINE_NAME[n] for n in names]
    except Exception:
        return None


def engine_plays(rec: dict, side: int):
    """play_index -> (hand_before base keys or None, elixir_before or None)."""
    out = {}
    for e in rec.get("log", []):
        if e.get("side") != side or "play_index" not in e:
            continue
        hb = e.get("hand_before")
        hb = [ENGINE_NAME.get(n.split("@")[0]) for n in hb] if hb else None
        out[int(e["play_index"])] = (hb, e.get("elixir_before"))
    return out


# ----------------------------------------------------------------------------------------------- worker state
_W = {}


def _init_worker(cfg_path: str):
    os.environ.setdefault("PYTHONHASHSEED", "0")
    from clashrl.config import Config
    from clashrl.cards import shared as shared_db
    from clashrl.sim.env import SimMatchEnv
    cfg = Config.load(cfg_path)
    cfg.data["sim"]["my_tower_troop"] = "princess"      # L51: my_tower_level stays 15 (profile reference level)
    db = shared_db(cfg)
    env = SimMatchEnv(cfg, seed=0)
    env.domain_rand.enabled = False                     # canonical rendering (eval convention)
    env.domain_rand.resample()
    slots = db.deck_slots()
    slot_of_base = {s["base"]: i for i, s in enumerate(slots)}
    acts = env.actions
    centers = np.array([acts.cell_center(c % acts.gw, c // acts.gw) for c in range(acts.n_cells)], np.float64)
    _W.update(cfg=cfg, db=db, env=env, slot_of_base=slot_of_base, centers=centers,
              sub_dt=float(cfg.get("sim", "sub_dt", default=0.1)), agent_dt=float(env.agent_dt))


def nearest_cell(nx: float, ny: float):
    """Nearest policy cell to a board-normalised point, measured in TILES (18x32) through env.actions.cell_center."""
    c = _W["centers"]
    d = np.hypot((c[:, 0] - nx) * 18.0, (c[:, 1] - ny) * 32.0)
    i = int(np.argmin(d))
    return i, float(d[i])


def drive_one(task):
    """One (tag, focus_side) drive. Returns (summary dict); writes the shard npz + meta json."""
    tag, focus_side, battle, plays, rec, shard_dir, level, slack, tail_cap = task
    cfg, db, env = _W["cfg"], _W["db"], _W["env"]
    sub_dt, agent_dt = _W["sub_dt"], _W["agent_dt"]
    slot_of_base = _W["slot_of_base"]
    acts = env.actions
    n_slots = env.n_slots
    mirror = (focus_side == 1)
    t0 = time.time()

    eng = L51.make_engine(cfg, db, level, seed=424242)
    env.eng = eng
    env.rng.seed(zlib.crc32(f"{tag}:{focus_side}".encode()))   # detector-noise stream, deterministic per drive
    env._canvas_stack.reset()
    env._reset_vectors()
    env._tid_unlit_t = None
    env._threat_credits = 0
    env.evo_charge = [0] * n_slots

    # decks per sim team (mirror swaps the sides)
    specs = {}
    for side in (0, 1):
        team = (1 - side) if mirror else side
        specs[team] = {}
        for tok in battle[L51.DECK_COL_OF_SIDE[side]].split(","):
            tok = tok.strip()
            specs[team][tok.replace("-ev1", "").replace("-hero", "")] = L51.build_spec(db, L51.key_of(tok), level)

    # hand model for the focus side (team 0)
    q0 = engine_queue(rec, focus_side) if rec else None
    eplays = engine_plays(rec, focus_side) if rec else {}
    if q0 is not None and all(b in slot_of_base for b in q0) and len(set(q0)) == 8:
        env.cycle = [slot_of_base[b] for b in q0]
        hand_source = "engine"
    else:
        env.cycle = list(range(n_slots))
        hand_source = "heuristic"
    seen = set()
    hand_mismatch = 0
    hand_checked = 0

    obs_l, hand_l, next_l, elx_l, thr_l, act_l, meta_l, oov_l = [], [], [], [], [], [], [], []
    pending, queue = [], []
    for row in plays:
        r = dict(row)
        if r["ability"]:
            continue
        s = r["side"]
        X, Y = (18000 - r["x"], 32000 - r["y"]) if mirror else (r["x"], r["y"])
        r["team"] = (1 - s) if mirror else s
        r["nx"], r["ny"] = X / 18000.0, 1.0 - Y / 32000.0
        queue.append(r)
    accepted = rejected = 0
    n_focus_samples = 0
    last_upd = -1e9

    def update_vectors():
        nonlocal last_upd
        env.agent_dt = max(0.05, eng.t - last_upd) if last_upd > -1e8 else agent_dt
        env._update_vectors()
        last_upd = eng.t

    def advance_cycle(base, card_id):
        env._play_slot(card_id)

    while not eng.done and eng.t < tail_cap:
        while queue and queue[0]["tick"] * TICK_S <= eng.t + 1e-9:
            pending.append([queue.pop(0), 0])
        still = []
        for item in pending:
            row, waited = item
            slug = row["attr_card"].strip()
            team = row["team"]
            spec = specs[team].get(slug) or specs[team].setdefault(slug, L51.build_spec(db, L51.key_of(slug), level))
            if eng.can_afford(team, spec):
                if team == 0:
                    base = key_base(slug)
                    slot = slot_of_base.get(base)
                    in_vocab = slot is not None
                    card_id = -1
                    if in_vocab:
                        if hand_source == "heuristic" and slot not in seen:
                            env.cycle.remove(slot); env.cycle.insert(0, slot)     # first play: it WAS in hand
                        if slot not in env.cycle[:4]:
                            # the model says it is not in hand -- keep going (flagged), force it in
                            env.cycle.remove(slot); env.cycle.insert(0, slot)
                            hand_mismatch += 1
                        card_id = env._slot_card_id(slot)
                        update_vectors()                                          # obs BEFORE the deploy
                        se = float(eng.elixir[0])                                 # sim elixir BEFORE paying
                        hb, eb = eplays.get(row["play_index"], (None, None))
                        hm = -1
                        if hb is not None:
                            hand_checked += 1
                            mine = {env.slots[si]["base"] for si in env.cycle[:4]}
                            hm = int(mine == set(hb))
                            if not hm:
                                hand_mismatch += 1
                    ok = eng.deploy(team, spec, row["nx"], row["ny"])
                    if ok and in_vocab:
                        cell, dist = nearest_cell(row["nx"], row["ny"])
                        gx, gy = cell % acts.gw, cell // acts.gw
                        pk = env.pocket_state(0)
                        obs_l.append(env._last_obs.copy()); hand_l.append(env.hand_vec.copy())
                        next_l.append(env.next_vec.copy()); elx_l.append(env.elixir_vec.copy())
                        thr_l.append(env.threat_vec.copy()); act_l.append([card_id, gx, gy])
                        meta_l.append({
                            "tag": tag, "side": focus_side, "play_index": row["play_index"], "tick": row["tick"],
                            "seconds": round(row["tick"] * TICK_S, 2), "sim_t": round(eng.t, 2), "delay_ticks": waited,
                            "card_slug": slug, "card_key": env.deck_keys[card_id], "card_id": card_id,
                            "gx": gx, "gy": gy, "cell": cell, "snap_dist_tiles": round(dist, 3),
                            "x_units": row["x"], "y_units": row["y"], "own_nx": round(row["nx"], 4), "own_ny": round(row["ny"], 4),
                            "hand_source": hand_source, "hand_certain": int(hand_source == "engine" or len(seen) >= 4),
                            "hand_match_engine": hm, "sim_elixir": round(se, 3),
                            "eng_elixir_before": (round(float(eb), 3) if eb is not None else ""),
                            "elixir_diff": (round(abs(se - float(eb)), 3) if eb is not None else ""),
                            "anywhere": int(card_id in env.anywhere_ids), "pocket_code": (2 if pk[0] else 0) + (1 if pk[1] else 0),
                            "sim_crowns_me": eng.crowns(0), "sim_crowns_them": eng.crowns(1),
                            "my_towers_alive": sum(1 for tw in eng.towers[0] if tw.alive),
                            "their_towers_alive": sum(1 for tw in eng.towers[1] if tw.alive),
                            "n_units_me": sum(1 for u in eng.units if u.team == 0 and u.hp > 0),
                            "n_units_them": sum(1 for u in eng.units if u.team == 1 and u.hp > 0),
                            "hand_ids": " ".join(str(i) for i in env._hand_ids()),
                        })
                        n_focus_samples += 1
                    if in_vocab:
                        seen.add(slot)
                        advance_cycle(base, card_id)          # the card left the pro's hand whether or not the sim took it
                else:
                    ok = eng.deploy(team, spec, row["nx"], row["ny"])
                    if ok:
                        # the OTHER side's play, in ITS OWN frame (team 1 -> flip): cell label only, no obs
                        ox, oy = 1.0 - row["nx"], 1.0 - row["ny"]
                        cell, dist = nearest_cell(ox, oy)
                        oov_l.append({"tag": tag, "side": 1 - focus_side, "play_index": row["play_index"], "tick": row["tick"],
                                      "seconds": round(row["tick"] * TICK_S, 2), "sim_t": round(eng.t, 2), "card_slug": slug,
                                      "cell": cell, "gx": cell % acts.gw, "gy": cell // acts.gw, "delay_ticks": waited})
                if ok:
                    accepted += 1
                else:
                    rejected += 1
            elif waited >= slack:
                rejected += 1
                if team == 0:
                    base = key_base(slug); slot = slot_of_base.get(base)
                    if slot is not None:
                        if slot not in env.cycle[:4]:
                            env.cycle.remove(slot); env.cycle.insert(0, slot)
                        seen.add(slot)
                        advance_cycle(base, env._slot_card_id(slot))
            else:
                item[1] = waited + max(1, int(round(sub_dt / TICK_S)))
                still.append(item)
        pending = still
        eng.advance(sub_dt)
        if eng.t - last_upd >= agent_dt - 1e-9:
            update_vectors()

    last_play_t = max((r["tick"] for r in plays), default=0) * TICK_S
    crowns = [eng.crowns(0), eng.crowns(1)]
    exp = [int(battle[L51.CROWN_COL_OF_SIDE[0]]), int(battle[L51.CROWN_COL_OF_SIDE[1]])]
    if mirror:
        exp = exp[::-1]
    shard = Path(shard_dir) / f"{tag}_{focus_side}.npz"
    if obs_l:
        np.savez_compressed(shard, obs=np.asarray(obs_l, np.uint8), hands=np.asarray(hand_l, np.float32),
                            nexts=np.asarray(next_l, np.float32), elixirs=np.asarray(elx_l, np.float32),
                            threats=np.asarray(thr_l, np.float32), acts=np.asarray(act_l, np.int64))
    summ = {"tag": tag, "focus_side": focus_side, "samples": n_focus_samples, "accepted": accepted, "rejected": rejected,
            "hand_source": hand_source, "hand_checked": hand_checked, "hand_mismatch": hand_mismatch,
            "sim_end_t": round(eng.t, 2), "sim_done": bool(eng.done), "last_play_s": round(last_play_t, 2),
            "ended_before_last_play": bool(eng.t < last_play_t - 1e-6), "sim_crowns_me_them": crowns,
            "exp_crowns_me_them": exp, "crowns_match": crowns == exp, "secs": round(time.time() - t0, 1),
            "n_plays_focus_total": sum(1 for r in plays if not r["ability"] and r["side"] == focus_side)}
    (Path(shard_dir) / f"{tag}_{focus_side}.json").write_text(json.dumps({"summary": summ, "meta": meta_l, "oov": oov_l}))
    return summ


# ----------------------------------------------------------------------------------------------- stages
def stage_drive(args, out: Path):
    import multiprocessing as mp
    tags = json.load(open(EXT / "usable_replays.json"))
    if args.limit:
        tags = tags[: args.limit]
    battles, plays = L51.load_crawl(set(tags))
    shard_dir = out / "shards"; shard_dir.mkdir(parents=True, exist_ok=True)
    tasks = []
    for tag in tags:
        if tag not in battles or not plays.get(tag):
            print("skip (no corpus rows)", tag); continue
        recf = EXT / "batch" / f"replay_{tag}.json"
        rec = json.loads(recf.read_text()) if recf.exists() else None
        if rec is not None and "log" not in rec:
            rec = None
        b = battles[tag]
        sides = []
        if {key_base(t.strip()) for t in b["team_deck"].split(",")} == ICEBOW_BASES:
            sides.append(1)
        if {key_base(t.strip()) for t in b["opponent_deck"].split(",")} == ICEBOW_BASES:
            sides.append(0)
        for fs in sides:
            if (shard_dir / f"{tag}_{fs}.json").exists() and not args.force:
                continue
            tasks.append((tag, fs, b, plays[tag], rec, str(shard_dir), args.level, 40, 360.0))
    print(f"[drive] {len(tasks)} drives to run over {len(tags)} tags, workers={args.workers}", flush=True)
    t0 = time.time()
    done = 0
    if args.workers <= 1:
        _init_worker(str(ICEBOW / "config" / "config.yaml"))
        for t in tasks:
            s = drive_one(t); done += 1
            print(f"[{done}/{len(tasks)}] {s}", flush=True)
    else:
        ctx = mp.get_context("spawn")
        with ctx.Pool(args.workers, initializer=_init_worker, initargs=(str(ICEBOW / "config" / "config.yaml"),)) as pool:
            for s in pool.imap_unordered(drive_one, tasks):
                done += 1
                if done % 10 == 0 or done == len(tasks):
                    print(f"[{done}/{len(tasks)}] {s['tag']} samples={s['samples']} {time.time()-t0:.0f}s", flush=True)
    print(f"[drive] done in {time.time()-t0:.0f}s")


def _shards(out: Path):
    return sorted(f for f in (out / "shards").glob("*.json") if not f.name.endswith(".baseline.json"))


def stage_baseline(args, out: Path):
    """Checkpoint top-1 / top-5 cells for the pro's card on each sample, masked exactly as the policy is (deployable
    mask of the card kind + pocket). Written into a per-shard baseline json; the assemble stage merges it into meta."""
    import torch
    torch.set_num_threads(2)
    from clashrl.config import Config
    from clashrl.model import PolicyNet
    from clashrl.sim.env import SimMatchEnv
    cfg = Config.load(ICEBOW / "config" / "config.yaml")
    env = SimMatchEnv(cfg, seed=0)
    ck = torch.load(args.ckpt, map_location="cpu")
    net = PolicyNet(in_ch=int(ck["in_ch"]), n_cards=int(ck["n_cards"]), n_cells=int(ck["n_cells"]),
                    threat_dim=int(ck["threat_dim"]))
    net.load_state_dict(ck["model"]); net.eval()
    assert [str(c) for c in ck["deck"]] == list(env.deck_keys), (ck["deck"], env.deck_keys)
    masks = {}
    for anywhere in (0, 1):
        for pk in range(4):
            masks[(anywhere, pk)] = torch.tensor(env.actions.deployable_mask(bool(anywhere), (bool(pk & 2), bool(pk & 1))),
                                                 dtype=torch.bool)
    costs = torch.tensor([float(s.elixir) for s in env.specs])
    t0 = time.time()
    for j, jf in enumerate(_shards(out)):
        bf = jf.with_suffix(".baseline.json")
        if bf.exists() and not args.force:
            continue
        d = json.loads(jf.read_text())
        meta = d["meta"]
        npz = jf.with_suffix(".npz")
        if not meta or not npz.exists():
            bf.write_text("[]"); continue
        z = np.load(npz)
        x = torch.from_numpy(z["obs"]).float().permute(0, 3, 1, 2) / 255.0
        hand, nxt = torch.from_numpy(z["hands"]), torch.from_numpy(z["nexts"])
        elx, thr = torch.from_numpy(z["elixirs"]), torch.from_numpy(z["threats"])
        acts = torch.from_numpy(z["acts"])
        rows = []
        with torch.no_grad():
            for i0 in range(0, len(x), 64):
                sl = slice(i0, i0 + 64)
                card_logits, cells = net(x[sl], hand[sl], nxt[sl], elx[sl], thr[sl])
                cid = acts[sl, 0]
                sel = cells[torch.arange(len(cid)), cid]                          # the pro's card's map
                for k in range(len(cid)):
                    m = meta[i0 + k]
                    mask = masks[(int(m["anywhere"]), int(m["pocket_code"]))]
                    lg = sel[k].masked_fill(~mask, float("-inf"))
                    top5 = torch.topk(lg, 5).indices.tolist()
                    # card head: in-hand AND affordable, like masked_logits (bank floor ignored)
                    playable = (hand[i0 + k] > 0.5) & (costs <= elx[i0 + k, 0] * 10.0 + 1e-6)
                    cl = card_logits[k].masked_fill(~playable, float("-inf"))
                    ctop = int(torch.argmax(cl)) if bool(playable.any()) else -1
                    rows.append({"top1": top5[0], "top5": top5, "card_top1": ctop})
        bf.write_text(json.dumps(rows))
        if (j + 1) % 20 == 0:
            print(f"[baseline] {j+1} shards {time.time()-t0:.0f}s", flush=True)
    print(f"[baseline] done {time.time()-t0:.0f}s")


def _write_npz_streamed(path: Path, parts, static: dict):
    """np.savez_compressed equivalent that never holds the big arrays: parts = {name: (dtype, shape, iter_of_chunks)}."""
    from numpy.lib import format as npf
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        for name, (dtype, shape, chunks) in parts.items():
            with zf.open(name + ".npy", "w", force_zip64=True) as fp:
                npf.write_array_header_1_0(fp, {"descr": npf.dtype_to_descr(np.dtype(dtype)), "fortran_order": False,
                                                "shape": tuple(int(s) for s in shape)})
                for ch in chunks():
                    fp.write(np.ascontiguousarray(ch, dtype=dtype).tobytes())
        for name, arr in static.items():
            with zf.open(name + ".npy", "w") as fp:
                npf.write_array(fp, np.asarray(arr))


def stage_assemble(args, out: Path):
    from clashrl.config import Config
    from clashrl.cards import shared as shared_db
    cfg = Config.load(ICEBOW / "config" / "config.yaml")
    db = shared_db(cfg)
    deck = db.deck_identities()
    gw, gh = cfg.get("action", "grid", default=[18, 24])
    files = []
    n = 0
    metas = []
    oov = []
    summaries = []
    for jf in _shards(out):
        d = json.loads(jf.read_text())
        summaries.append(d["summary"])
        oov.extend(d["oov"])
        bf = jf.with_suffix(".baseline.json")
        base = json.loads(bf.read_text()) if bf.exists() else []
        if d["meta"]:
            files.append(jf.with_suffix(".npz"))
            for i, m in enumerate(d["meta"]):
                m = dict(m)
                if i < len(base):
                    m["ck_top1"] = base[i]["top1"]; m["ck_top5"] = " ".join(str(c) for c in base[i]["top5"])
                    m["ck_hit1"] = int(base[i]["top1"] == m["cell"]); m["ck_hit5"] = int(m["cell"] in base[i]["top5"])
                    m["ck_card_top1"] = base[i]["card_top1"]; m["ck_card_hit1"] = int(base[i]["card_top1"] == m["card_id"])
                m["row"] = n; n += 1
                metas.append(m)
    print(f"[assemble] {n} samples from {len(files)} shards")
    shapes = {}
    for f in files[:1]:
        z = np.load(f)
        shapes = {k: z[k].shape[1:] for k in ("obs", "hands", "nexts", "elixirs", "threats", "acts")}

    def chunks(key):
        def it():
            for f in files:
                yield np.load(f)[key]
        return it
    parts = {"obs": (np.uint8, (n,) + shapes["obs"], chunks("obs")),
             "acts": (np.int64, (n,) + shapes["acts"], chunks("acts")),
             "hands": (np.float32, (n,) + shapes["hands"], chunks("hands")),
             "nexts": (np.float32, (n,) + shapes["nexts"], chunks("nexts")),
             "elixirs": (np.float32, (n,) + shapes["elixirs"], chunks("elixirs")),
             "threats": (np.float32, (n,) + shapes["threats"], chunks("threats"))}
    _write_npz_streamed(out / "dataset.npz", parts,
                        {"grid": np.asarray([int(gw), int(gh)], np.int64), "deck": np.asarray(deck)})
    keys = META_KEYS + ["ck_top1", "ck_top5", "ck_hit1", "ck_hit5", "ck_card_top1", "ck_card_hit1", "row"]
    with (out / "meta.csv").open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=keys, extrasaction="ignore"); w.writeheader(); w.writerows(metas)
    if oov:
        with (out / "meta_oov.csv").open("w", newline="", encoding="utf-8") as h:
            w = csv.DictWriter(h, fieldnames=list(oov[0].keys())); w.writeheader(); w.writerows(oov)
    (out / "drive_summary.jsonl").write_text("\n".join(json.dumps(s) for s in summaries) + "\n")
    # by-replay split, 85/15, seed 0 -- a replay's samples (both focus sides) never straddle the split
    tags = sorted({m["tag"] for m in metas})
    rng = np.random.default_rng(0)
    perm = list(rng.permutation(tags))
    n_val = int(round(0.15 * len(perm)))
    val = sorted(perm[:n_val]); train = sorted(perm[n_val:])
    rows_tr = [m["row"] for m in metas if m["tag"] in set(train)]
    rows_va = [m["row"] for m in metas if m["tag"] in set(val)]
    (out / "split.json").write_text(json.dumps({"seed": 0, "val_frac": 0.15, "by": "replay_tag",
                                                "train_tags": train, "val_tags": val,
                                                "train_rows": rows_tr, "val_rows": rows_va,
                                                "n_train": len(rows_tr), "n_val": len(rows_va)}, indent=1))
    print(f"[assemble] split: {len(train)} train tags / {len(val)} val tags; {len(rows_tr)} / {len(rows_va)} rows")


def stage_report(args, out: Path):
    import collections
    metas = list(csv.DictReader((out / "meta.csv").open(encoding="utf-8")))
    summ = [json.loads(l) for l in (out / "drive_summary.jsonl").read_text().splitlines() if l.strip()]
    L = []
    N = len(metas)
    L.append(f"samples_total {N}")
    L.append("per_side " + json.dumps(collections.Counter(m['side'] for m in metas)))
    L.append(f"replays_with_samples {len({m['tag'] for m in metas})}; drives {len(summ)}; "
             f"tags_engine_hand {sum(1 for s in summ if s['hand_source']=='engine')} heuristic {sum(1 for s in summ if s['hand_source']!='engine')}")
    L.append(f"plays_focus_total {sum(s['n_plays_focus_total'] for s in summ)} accepted_all_sides {sum(s['accepted'] for s in summ)} "
             f"rejected_all_sides {sum(s['rejected'] for s in summ)}")
    L.append(f"hand_checked {sum(s['hand_checked'] for s in summ)} hand_mismatch {sum(s['hand_mismatch'] for s in summ)}")
    L.append(f"sim_ended_before_last_play {sum(1 for s in summ if s['ended_before_last_play'])}/{len(summ)}; "
             f"crowns_match {sum(1 for s in summ if s['crowns_match'])}/{len(summ)}; "
             f"median sim_end_t {np.median([s['sim_end_t'] for s in summ]):.1f}s, median last_play_s {np.median([s['last_play_s'] for s in summ]):.1f}s")
    cc = collections.Counter(m["card_key"] for m in metas)
    L.append("per_card " + json.dumps(cc.most_common()))
    L.append("per_cell_top10 " + json.dumps(collections.Counter(int(m["cell"]) for m in metas).most_common(10)))
    secs = np.array([float(m["seconds"]) for m in metas])
    L.append(f"time_coverage: min {secs.min():.1f} p10 {np.percentile(secs,10):.1f} median {np.median(secs):.1f} "
             f"p90 {np.percentile(secs,90):.1f} max {secs.max():.1f}; buckets " +
             json.dumps({"0-60": int((secs < 60).sum()), "60-120": int(((secs >= 60) & (secs < 120)).sum()),
                         "120-180": int(((secs >= 120) & (secs < 180)).sum()), "180+": int((secs >= 180).sum())}))
    ed = [float(m["elixir_diff"]) for m in metas if m["elixir_diff"] not in ("", None)]
    if ed:
        L.append(f"elixir |sim-engine| at deploy: n {len(ed)} mean {np.mean(ed):.2f} median {np.median(ed):.2f} p90 {np.percentile(ed,90):.2f} >2: {np.mean(np.array(ed)>2)*100:.1f}%")
    sd = np.array([float(m["snap_dist_tiles"]) for m in metas])
    L.append(f"snap_dist_tiles mean {sd.mean():.3f} max {sd.max():.3f}")
    L.append(f"delay_ticks>0 {sum(1 for m in metas if int(m['delay_ticks'])>0)}")
    have = [m for m in metas if m.get("ck_hit1") not in ("", None)]
    if have:
        h1 = np.array([int(m["ck_hit1"]) for m in have]); h5 = np.array([int(m["ck_hit5"]) for m in have])
        ch = np.array([int(m["ck_card_hit1"]) for m in have])
        L.append(f"baseline c2r_best cells: n {len(have)} top1 {h1.mean()*100:.2f}% top5 {h5.mean()*100:.2f}% ; card top1 (in-hand+affordable mask) {ch.mean()*100:.2f}%")
        L.append(f"chance: top1 1/{432} = 0.23% of all cells; own-half deployable cells ~ see mask")
        for card, _ in cc.most_common(8):
            sub = [m for m in have if m["card_key"] == card]
            a1 = np.mean([int(m["ck_hit1"]) for m in sub]) * 100; a5 = np.mean([int(m["ck_hit5"]) for m in sub]) * 100
            L.append(f"  card {card:12s} n {len(sub):5d} top1 {a1:6.2f}% top5 {a5:6.2f}%")
        for lo, hi, name in ((0, 60, "0-60"), (60, 120, "60-120"), (120, 180, "120-180"), (180, 1e9, "180+")):
            sub = [m for m in have if lo <= float(m["seconds"]) < hi]
            if sub:
                a1 = np.mean([int(m["ck_hit1"]) for m in sub]) * 100; a5 = np.mean([int(m["ck_hit5"]) for m in sub]) * 100
                L.append(f"  time {name:8s} n {len(sub):5d} top1 {a1:6.2f}% top5 {a5:6.2f}%")
        # checkpoint's own top-1 cell histogram (collapse check)
        L.append("ck_top1_hist_top10 " + json.dumps(collections.Counter(int(m["ck_top1"]) for m in have).most_common(10)))
    sp = json.loads((out / "split.json").read_text())
    L.append(f"split: train tags {len(sp['train_tags'])} rows {sp['n_train']} / val tags {len(sp['val_tags'])} rows {sp['n_val']}")
    txt = "\n".join(L)
    (out / "report.txt").write_text(txt)
    print(txt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all", choices=["all", "drive", "baseline", "assemble", "report"])
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    ap.add_argument("--ckpt", default=str(CKPT_DEFAULT))
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--level", type=int, default=11)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    if args.stage in ("all", "drive"):
        stage_drive(args, out)
    if args.stage in ("all", "baseline"):
        stage_baseline(args, out)
    if args.stage in ("all", "assemble"):
        stage_assemble(args, out)
    if args.stage in ("all", "report"):
        stage_report(args, out)


if __name__ == "__main__":
    main()
