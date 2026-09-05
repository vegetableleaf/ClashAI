"""L61: BC dataset v2 -- the same pro-placement dataset as L60 (v1) but with the BOARD taken from the REAL CR engine
(cr-native-sandbox recordings, scratchpad/gauntlet/ext/batch_v2/replay_<tag>.json: a full observation immediately
BEFORE every driven play of both sides + a compact frame every 20 ticks).

An engine frame (entities side/x/y/name/hp/max_hp/kind, towers, elixir, hands) is turned into a duck-typed engine
object (FakeEngine: units with sim CardSpecs, sim Tower objects, elixir, t) and handed to a real SimMatchEnv (env.eng
swapped) so that hand/next/elixir/threat vectors and the 12-channel obs are rendered by the SAME pipeline as v1 / the
policy. Mirroring: engine side 1 (RoyaleAPI blue = the icebow deck) is made sim team 0 = "me" = bottom by the L51
mirror (sides swapped, x -> 18000-x, y -> 32000-y); sim x = X/18000, sim y = 1 - Y/32000.

Stages (--stage): assemble (per-tag shards), baseline (c2r_best top-1/top-5 per sample, masked like the policy),
pack (dataset.npz + meta.csv + split.json; split = v1's split.json restricted to converted tags), report.

    cd icebow && PYTHONHASHSEED=0 ./.venv/Scripts/python.exe ../scratchpad/gauntlet/L61/build_bc_v2.py
"""
import argparse, csv, json, os, re, sys, time, zlib, collections
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
ICEBOW = ROOT / "icebow"
sys.path.insert(0, str(ICEBOW / "src"))
sys.path.insert(0, str(ROOT / "scratchpad" / "gauntlet" / "L60"))
import build_bc_dataset as V1                     # noqa: E402  (L60 code, unmodified; reused for stages/keys)

TICK_S = 0.05
EXT = ROOT / "scratchpad/gauntlet/ext"
REC_DIR = EXT / "batch_v2"
OUT_DEFAULT = ICEBOW / "data" / "bc_pro_v2"
V1_DIR = ICEBOW / "data" / "bc_pro"
CKPT_DEFAULT = ICEBOW / "data" / "bench" / "c2r_best_36k_backup.pt"
ENGINE_NAME = V1.ENGINE_NAME                       # engine display name -> policy base key (icebow deck)
ICEBOW_BASES = V1.ICEBOW_BASES
META_KEYS = ["tag", "side", "play_index", "tick", "seconds", "card_slug", "card_key", "card_id", "gx", "gy", "cell",
             "snap_dist_tiles", "x_units", "y_units", "own_nx", "own_ny", "hand_source", "hand_match_engine",
             "eng_elixir_me", "eng_elixir_them", "anywhere", "pocket_code", "my_towers_alive", "their_towers_alive",
             "tw_me_L", "tw_me_R", "tw_me_K", "tw_them_L", "tw_them_R", "tw_them_K",
             "n_units_me", "n_units_them", "n_units_unmapped", "n_deploying", "n_projectiles", "n_effects",
             "engine_accepted", "hand_ids",
             "v1_row", "v1_n_units_me", "v1_n_units_them", "d_units_me", "d_units_them", "v1_my_towers_alive",
             "v1_their_towers_alive", "towers_agree", "v1_sim_elixir", "d_elixir"]

# ----------------------------------------------------------------------------------------------- name mapping
# engine display name (native_core CARD_NAMES = live catalog display_name) -> sim cards.yaml key.
# Built from replay_drive.SLUG_ALIASES (RoyaleAPI slug <-> catalog internal name) inverted, plus CamelCase -> snake.
_ALIAS_INV = {"AngryBarbarians": "elite_barbarians", "Archer": "archers", "Assassin": "bandit", "BarbLog": "barbarian_barrel",
              "MovingCannon": "cannon_cart", "BlowdartGoblin": "dart_goblin", "AxeMan": "executioner", "FireSpirits": "fire_spirit",
              "DartBarrell": "flying_machine", "FirespiritHut": "furnace", "Snowball": "giant_snowball", "SkeletonWarriors": "guards",
              "Heal": "heal_spirit", "IceGolemite": "ice_golem", "IceSpirits": "ice_spirit", "RageBarbarian": "lumberjack",
              "EliteArcher": "magic_archer", "WitchMother": "mother_witch", "DarkWitch": "night_witch", "Ghost": "royal_ghost",
              "GiantBuffer": "rune_giant", "SkeletonBalloon": "skeleton_barrel", "ZapMachine": "sparky", "MergeMaiden": "spirit_empress",
              "MergeMaiden_Normal": "spirit_empress", "MergeMaiden_Mounted": "spirit_empress_air", "Log": "the_log",
              "DarkMagic": "void", "MiniSparkys": "zappies", "Xbow": "x_bow", "Wallbreakers": "wall_breakers",
              "Elixir Collector": "elixir_collector", "Pekka": "pekka", "MiniPekka": "mini_pekka", "GlobalLightning": "lightning",
              "GlobalClone": "clone", "RoyalRecruits_Chess": "royal_recruits", "SkeletonWarriors_SpookyChess": "guards",
              "SuperArcher": "archers", "SuperEliteArcher": "magic_archer", "SuperHogRider": "hog_rider",
              "SuperHogRiderTerry": "hog_rider", "SuperIceGolemite": "ice_golem", "SuperKnight": "knight",
              "SuperLavaHound": "lava_hound", "SuperMiniPekka": "mini_pekka", "SuperWitch": "witch", "TriWizards": "wizard",
              "PrinceBuff": "prince", "GoblinPartyHut": "goblin_hut", "GoblinPartyRocket": "rocket", "GoblinRocketSilo": "goblin_hut",
              "BarbarianLauncher": "barbarian_barrel", "ElixirBarrel": "elixir_collector", "WarmSpell": "fireball"}


def sim_key_for(name, db):
    if name in _ALIAS_INV:
        k = _ALIAS_INV[name]
    else:
        k = re.sub(r"(?<!^)(?=[A-Z])", "_", name.replace(" ", "")).lower()
    return k if db.get(k) else None


# ----------------------------------------------------------------------------------------------- fake engine
class FakeUnit:
    __slots__ = ("spec", "team", "x", "y", "hp", "age", "deploy_left", "target", "locked", "invis_left", "hidden", "ghost")

    def __init__(self, spec, team, x, y, hp, deploying):
        self.spec, self.team, self.x, self.y, self.hp = spec, team, x, y, float(hp)
        self.age = 1.0
        self.deploy_left = 1.0 if deploying else 0.0
        self.target = None
        self.locked = False
        self.invis_left = 0.0
        self.hidden = False
        self.ghost = False


class FakeEngine:
    """What SimMatchEnv's observation pipeline reads: t, units, towers[team], elixir[team]."""

    def __init__(self, t, units, towers, elixir):
        self.t, self.units, self.towers, self.elixir = t, units, towers, elixir
        self.done = False
        self.last_deploy = {}
        self.regulation = 180.0

    def elixir_rate(self):
        return 1.0 / 2.8


def tower_at(x, y, hp, max_hp, king):
    from clashrl.sim.engine import Tower, _KING_HALF, _PRINCESS_HALF
    return Tower(x, y, float(hp), float(max_hp), king=king, active=(not king), alive=hp > 0,
                 radius=(_KING_HALF if king else _PRINCESS_HALF), troop=("king" if king else "princess"))


ANCHORS = {0: [(3.5 / 18, 1 - 6.5 / 32), (14.5 / 18, 1 - 6.5 / 32), (9 / 18, 1 - 3 / 32)],
           1: [(3.5 / 18, 6.5 / 32), (14.5 / 18, 6.5 / 32), (9 / 18, 3 / 32)]}


def frame_to_engine(frame, focus_side, spec_of, stats):
    """Engine frame -> FakeEngine in the focus side's local frame (focus = team 0 = bottom)."""
    mirror = (focus_side == 1)

    def xy(X, Y):
        if mirror:
            X, Y = 18000 - X, 32000 - Y
        return X / 18000.0, 1.0 - Y / 32000.0

    def team_of(side):
        return (1 - side) if mirror else side

    towers = {0: [None, None, None], 1: [None, None, None]}
    for side, typ, lane, X, Y, hp, mhp in frame["towers"]:
        tm = team_of(int(side))
        x, y = xy(int(X), int(Y))
        tw = tower_at(x, y, hp, mhp, typ == "king")
        if typ == "king":
            towers[tm][2] = tw
        else:
            towers[tm][0 if x < 0.5 else 1] = tw
    for tm in (0, 1):                      # towers missing from the engine list = destroyed
        for i in range(3):
            if towers[tm][i] is None:
                ax, ay = ANCHORS[tm][i]
                towers[tm][i] = tower_at(ax, ay, 0.0, 1.0, i == 2)
    units = []
    n_unmapped = 0
    n_deploying = 0
    for e in frame["entities"]:
        side, X, Y, name, hp, mhp = e[:6]
        kind = e[6] if len(e) > 6 else -1
        if name == "-1":
            continue                       # crown towers appear as card_id -1 entities
        if hp <= 0:
            continue
        spec = spec_of(name)
        stats["names"][name] += 1
        if spec is None:
            n_unmapped += 1
            stats["unmapped"][name] += 1
            spec = spec_of("__generic__")
        x, y = xy(int(X), int(Y))
        deploying = kind in (12, 14)
        n_deploying += int(deploying)
        units.append(FakeUnit(spec, team_of(int(side)), x, y, hp, deploying))
    el = frame["elixir"]
    elixir = [float(el[focus_side] or 0.0), float(el[1 - focus_side] or 0.0)]
    return FakeEngine(frame["tick"] * TICK_S, units, towers, elixir), n_unmapped, n_deploying


# ----------------------------------------------------------------------------------------------- per-tag assembly
_W = {}


def init_worker():
    os.environ.setdefault("PYTHONHASHSEED", "0")
    from dataclasses import replace
    from clashrl.config import Config
    from clashrl.cards import shared as shared_db
    from clashrl.sim.env import SimMatchEnv
    from clashrl.sim.engine import build_spec
    cfg = Config.load(str(ICEBOW / "config" / "config.yaml"))
    cfg.data["sim"]["my_tower_troop"] = "princess"
    db = shared_db(cfg)
    env = SimMatchEnv(cfg, seed=0)
    env.domain_rand.enabled = False
    env.domain_rand.resample()
    slots = db.deck_slots()
    acts = env.actions
    centers = np.array([acts.cell_center(c % acts.gw, c // acts.gw) for c in range(acts.n_cells)], np.float64)
    spec_cache = {}
    generic = replace(build_spec(db, "knight", 11), key="__generic__", base="__generic__")

    def spec_of(name):
        if name == "__generic__":
            return generic
        if name not in spec_cache:
            k = sim_key_for(name, db)
            try:
                spec_cache[name] = build_spec(db, k, 11) if k else None
            except Exception:
                spec_cache[name] = None
        return spec_cache[name]
    _W.update(cfg=cfg, db=db, env=env, slot_of_base={s["base"]: i for i, s in enumerate(slots)}, centers=centers,
              spec_of=spec_of, agent_dt=float(env.agent_dt))


def nearest_cell(nx, ny):
    c = _W["centers"]
    d = np.hypot((c[:, 0] - nx) * 18.0, (c[:, 1] - ny) * 32.0)
    i = int(np.argmin(d))
    return i, float(d[i])


def assemble_tag(tag, focus_side, rec, v1_meta, shard_dir):
    env, spec_of = _W["env"], _W["spec_of"]
    slot_of_base = _W["slot_of_base"]
    acts = env.actions
    n_slots = env.n_slots
    stats = {"names": collections.Counter(), "unmapped": collections.Counter()}
    t0 = time.time()
    env.rng.seed(zlib.crc32(f"{tag}:{focus_side}".encode()))
    env._canvas_stack.reset()
    env._reset_vectors()
    env._tid_unlit_t = None
    env._threat_credits = 0
    env.evo_charge = [0] * n_slots
    q0 = V1.engine_queue(rec, focus_side)
    if q0 is not None and all(b in slot_of_base for b in q0) and len(set(q0)) == 8:
        env.cycle = [slot_of_base[b] for b in q0]
        hand_source = "engine"
    else:
        env.cycle = list(range(n_slots))
        hand_source = "heuristic"
    log_by_pi = {int(e["play_index"]): e for e in rec["log"] if "play_index" in e}
    # timeline: drift frames (compact, every 20 ticks) + play frames (full), in tick order; play frames first at a tick
    events = [("drift", f) for f in rec.get("frames", [])] + [("play", f) for f in rec["play_frames"]]
    events.sort(key=lambda ef: (ef[1]["tick"], 0 if ef[0] == "play" else 1, ef[1].get("play_index", -1)))
    state = {"last_upd": None}
    obs_l, hand_l, next_l, elx_l, thr_l, act_l, meta_l = [], [], [], [], [], [], []
    hand_checked = hand_mismatch = 0
    nostats = {"names": collections.Counter(), "unmapped": collections.Counter()}

    def update(eng):
        env.eng = eng
        env.agent_dt = _W["agent_dt"] if state["last_upd"] is None else max(0.05, eng.t - state["last_upd"])
        env._update_vectors()
        state["last_upd"] = eng.t

    for kind, fr in events:
        if kind == "drift":
            eng, _, _ = frame_to_engine(fr, focus_side, spec_of, nostats)
            update(eng)
            continue
        if fr["side"] != focus_side:
            continue
        slug = fr["card"]
        base = V1.key_base(slug)
        slot = slot_of_base.get(base)
        entry = log_by_pi.get(int(fr["play_index"]), {})
        if slot is None:
            continue                       # out of the policy's vocabulary (cannot happen for icebow)
        if slot not in env.cycle[:4]:      # the cycle model says not in hand: force + flag (as v1)
            env.cycle.remove(slot)
            env.cycle.insert(0, slot)
            hand_mismatch += 1
        card_id = env._slot_card_id(slot)
        eng, n_unmapped, n_deploying = frame_to_engine(fr, focus_side, spec_of, stats)
        update(eng)                        # obs BEFORE the deploy, at the play's tick
        pl = next(p for p in fr["players"] if p["side"] == focus_side)
        eh = [ENGINE_NAME.get(n.split("@")[0]) for n in pl["hand"]]
        hm = -1
        if all(eh):
            hand_checked += 1
            mine = {env.slots[si]["base"] for si in env.cycle[:4]}
            hm = int(mine == set(eh))
            hand_mismatch += int(not hm)
        accepted = bool(entry.get("accepted", False))
        if accepted:
            X, Y = (18000 - fr["x"], 32000 - fr["y"]) if focus_side == 1 else (fr["x"], fr["y"])
            nx, ny = X / 18000.0, 1.0 - Y / 32000.0
            cell, dist = nearest_cell(nx, ny)
            gx, gy = cell % acts.gw, cell // acts.gw
            pk = env.pocket_state(0)
            tw = eng.towers
            v1m = v1_meta.get((tag, focus_side, int(fr["play_index"])))
            n_me = sum(1 for u in eng.units if u.team == 0)
            n_them = sum(1 for u in eng.units if u.team == 1)
            my_alive = sum(1 for t in tw[0] if t.alive)
            their_alive = sum(1 for t in tw[1] if t.alive)
            m = {"tag": tag, "side": focus_side, "play_index": int(fr["play_index"]), "tick": fr["tick"],
                 "seconds": round(fr["tick"] * TICK_S, 2), "card_slug": slug, "card_key": env.deck_keys[card_id], "card_id": card_id,
                 "gx": gx, "gy": gy, "cell": cell, "snap_dist_tiles": round(dist, 3), "x_units": fr["x"], "y_units": fr["y"],
                 "own_nx": round(nx, 4), "own_ny": round(ny, 4), "hand_source": hand_source, "hand_match_engine": hm,
                 "eng_elixir_me": round(eng.elixir[0], 3), "eng_elixir_them": round(eng.elixir[1], 3),
                 "anywhere": int(card_id in env.anywhere_ids), "pocket_code": (2 if pk[0] else 0) + (1 if pk[1] else 0),
                 "my_towers_alive": my_alive, "their_towers_alive": their_alive,
                 "tw_me_L": int(tw[0][0].hp), "tw_me_R": int(tw[0][1].hp), "tw_me_K": int(tw[0][2].hp),
                 "tw_them_L": int(tw[1][0].hp), "tw_them_R": int(tw[1][1].hp), "tw_them_K": int(tw[1][2].hp),
                 "n_units_me": n_me, "n_units_them": n_them, "n_units_unmapped": n_unmapped, "n_deploying": n_deploying,
                 "n_projectiles": len(fr.get("projectiles", [])), "n_effects": len(fr.get("effects", [])),
                 "engine_accepted": 1, "hand_ids": " ".join(str(i) for i in env._hand_ids()),
                 "v1_row": "", "v1_n_units_me": "", "v1_n_units_them": "", "d_units_me": "", "d_units_them": "",
                 "v1_my_towers_alive": "", "v1_their_towers_alive": "", "towers_agree": "", "v1_sim_elixir": "", "d_elixir": ""}
            if v1m:
                # v1 counted units AFTER its deploy: add the played card's sim body count to v2's BEFORE count
                spec_played = env.specs[card_id] if hasattr(env, "specs") else None
                played_bodies = int(spec_played.count) if (spec_played is not None and spec_played.kind != "spell") else 0
                m.update({"v1_row": v1m["row"], "v1_n_units_me": v1m["n_units_me"], "v1_n_units_them": v1m["n_units_them"],
                          "d_units_me": n_me + played_bodies - int(v1m["n_units_me"]), "d_units_them": n_them - int(v1m["n_units_them"]),
                          "v1_my_towers_alive": v1m["my_towers_alive"], "v1_their_towers_alive": v1m["their_towers_alive"],
                          "towers_agree": int(my_alive == int(v1m["my_towers_alive"]) and their_alive == int(v1m["their_towers_alive"])),
                          "v1_sim_elixir": v1m["sim_elixir"], "d_elixir": round(eng.elixir[0] - float(v1m["sim_elixir"]), 3)})
            obs_l.append(env._last_obs.copy())
            hand_l.append(env.hand_vec.copy())
            next_l.append(env.next_vec.copy())
            elx_l.append(env.elixir_vec.copy())
            thr_l.append(env.threat_vec.copy())
            act_l.append([card_id, gx, gy])
            meta_l.append(m)
        env._play_slot(card_id)            # the card left the pro's hand whether or not the engine took it
    shard = Path(shard_dir) / f"{tag}_{focus_side}.npz"
    if obs_l:
        np.savez_compressed(shard, obs=np.asarray(obs_l, np.uint8), hands=np.asarray(hand_l, np.float32),
                            nexts=np.asarray(next_l, np.float32), elixirs=np.asarray(elx_l, np.float32),
                            threats=np.asarray(thr_l, np.float32), acts=np.asarray(act_l, np.int64))
    summ = {"tag": tag, "focus_side": focus_side, "samples": len(meta_l), "hand_source": hand_source, "hand_checked": hand_checked,
            "hand_mismatch": hand_mismatch, "final_tick": rec["final"]["tick"], "crowns_match": rec["grade"]["crowns_match"],
            "n_play_frames_focus": sum(1 for f in rec["play_frames"] if f["side"] == focus_side),
            "n_drift_frames": len(rec.get("frames", [])), "secs": round(time.time() - t0, 1),
            "names": dict(stats["names"]), "unmapped": dict(stats["unmapped"])}
    (Path(shard_dir) / f"{tag}_{focus_side}.json").write_text(json.dumps({"summary": summ, "meta": meta_l, "oov": []}))
    return summ


def stage_assemble_shards(args, out):
    init_worker()
    tags = json.load(open(EXT / "usable_replays.json"))
    if args.limit:
        tags = tags[: args.limit]
    battles, _ = V1.L51.load_crawl(set(tags))
    v1_meta = {}
    if (V1_DIR / "meta.csv").exists():
        for r in csv.DictReader(open(V1_DIR / "meta.csv", encoding="utf-8")):
            v1_meta[(r["tag"], int(r["side"]), int(r["play_index"]))] = r
    shard_dir = out / "shards"
    shard_dir.mkdir(parents=True, exist_ok=True)
    done = 0
    t0 = time.time()
    names = collections.Counter()
    unmapped = collections.Counter()
    missing = []
    for tag in tags:
        recf = REC_DIR / f"replay_{tag}.json"
        if not recf.exists() or tag not in battles:
            missing.append(tag)
            continue
        rec = json.loads(recf.read_text(encoding="utf-8"))
        if "play_frames" not in rec:
            missing.append(tag)
            continue
        b = battles[tag]
        sides = []
        if {V1.key_base(t.strip()) for t in b["team_deck"].split(",")} == ICEBOW_BASES:
            sides.append(1)
        if {V1.key_base(t.strip()) for t in b["opponent_deck"].split(",")} == ICEBOW_BASES:
            sides.append(0)
        for fs in sides:
            if (shard_dir / f"{tag}_{fs}.json").exists() and not args.force:
                s = json.loads((shard_dir / f"{tag}_{fs}.json").read_text())["summary"]
            else:
                s = assemble_tag(tag, fs, rec, v1_meta, shard_dir)
            names.update(s["names"])
            unmapped.update(s["unmapped"])
            done += 1
            if done % 20 == 0:
                print(f"[assemble] {done} drives {time.time()-t0:.0f}s last {tag} samples={s['samples']}", flush=True)
    print(f"[assemble] {done} drives in {time.time()-t0:.0f}s; tags without recording: {len(missing)}")
    (out / "name_stats.json").write_text(json.dumps({"entity_name_counts": dict(names.most_common()),
                                                     "unmapped_counts": dict(unmapped.most_common()),
                                                     "mapping": {n: sim_key_for(n, _W["db"]) for n in names},
                                                     "tags_without_recording": missing}, indent=1))


def stage_pack(args, out):
    """dataset.npz + meta.csv + split.json (v1's replay split restricted to the converted tags)."""
    from clashrl.config import Config
    from clashrl.cards import shared as shared_db
    cfg = Config.load(str(ICEBOW / "config" / "config.yaml"))
    db = shared_db(cfg)
    gw, gh = cfg.get("action", "grid", default=[18, 24])
    files, metas, summaries, n = [], [], [], 0
    for jf in V1._shards(out):
        d = json.loads(jf.read_text())
        summaries.append(d["summary"])
        bf = jf.with_suffix(".baseline.json")
        base = json.loads(bf.read_text()) if bf.exists() else []
        if d["meta"]:
            files.append(jf.with_suffix(".npz"))
            for i, m in enumerate(d["meta"]):
                m = dict(m)
                if i < len(base):
                    m["ck_top1"] = base[i]["top1"]
                    m["ck_top5"] = " ".join(str(c) for c in base[i]["top5"])
                    m["ck_hit1"] = int(base[i]["top1"] == m["cell"])
                    m["ck_hit5"] = int(m["cell"] in base[i]["top5"])
                    m["ck_card_top1"] = base[i]["card_top1"]
                    m["ck_card_hit1"] = int(base[i]["card_top1"] == m["card_id"])
                m["row"] = n
                n += 1
                metas.append(m)
    print(f"[pack] {n} samples from {len(files)} shards")
    z = np.load(files[0])
    shapes = {k: z[k].shape[1:] for k in ("obs", "hands", "nexts", "elixirs", "threats", "acts")}

    def chunks(key):
        def it():
            for f in files:
                yield np.load(f)[key]
        return it
    parts = {"obs": (np.uint8, (n,) + shapes["obs"], chunks("obs")), "acts": (np.int64, (n,) + shapes["acts"], chunks("acts")),
             "hands": (np.float32, (n,) + shapes["hands"], chunks("hands")), "nexts": (np.float32, (n,) + shapes["nexts"], chunks("nexts")),
             "elixirs": (np.float32, (n,) + shapes["elixirs"], chunks("elixirs")), "threats": (np.float32, (n,) + shapes["threats"], chunks("threats"))}
    V1._write_npz_streamed(out / "dataset.npz", parts, {"grid": np.asarray([int(gw), int(gh)], np.int64), "deck": np.asarray(db.deck_identities())})
    keys = META_KEYS + ["ck_top1", "ck_top5", "ck_hit1", "ck_hit5", "ck_card_top1", "ck_card_hit1", "row"]
    with (out / "meta.csv").open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(metas)
    (out / "drive_summary.jsonl").write_text("\n".join(json.dumps(s) for s in summaries) + "\n")
    v1sp = json.loads((V1_DIR / "split.json").read_text())
    tags = {m["tag"] for m in metas}
    val = sorted(t for t in v1sp["val_tags"] if t in tags)
    train = sorted(t for t in v1sp["train_tags"] if t in tags)
    extra = sorted(tags - set(val) - set(train))
    trs, vas = set(train), set(val)
    rows_tr = [m["row"] for m in metas if m["tag"] in trs]
    rows_va = [m["row"] for m in metas if m["tag"] in vas]
    (out / "split.json").write_text(json.dumps({"source": "v1 split.json (seed 0, 85/15 by replay) restricted to converted tags",
                                                "train_tags": train, "val_tags": val, "tags_not_in_v1_split": extra,
                                                "v1_val_tags_not_converted": sorted(t for t in v1sp["val_tags"] if t not in tags),
                                                "v1_train_tags_not_converted": sorted(t for t in v1sp["train_tags"] if t not in tags),
                                                "train_rows": rows_tr, "val_rows": rows_va, "n_train": len(rows_tr), "n_val": len(rows_va)}, indent=1))
    print(f"[pack] split: {len(train)} train tags / {len(val)} val tags; {len(rows_tr)} / {len(rows_va)} rows; "
          f"v1 val not converted: {len([t for t in v1sp['val_tags'] if t not in tags])}")


def stage_report(args, out):
    metas = list(csv.DictReader((out / "meta.csv").open(encoding="utf-8")))
    summ = [json.loads(l) for l in (out / "drive_summary.jsonl").read_text().splitlines() if l.strip()]
    L = [f"samples_total {len(metas)}", "per_side " + json.dumps(collections.Counter(m['side'] for m in metas)),
         f"replays_with_samples {len({m['tag'] for m in metas})}; drives {len(summ)}",
         f"focus_play_frames {sum(s['n_play_frames_focus'] for s in summ)} (samples = accepted focus plays)",
         f"hand_checked {sum(s['hand_checked'] for s in summ)} hand_mismatch {sum(s['hand_mismatch'] for s in summ)}; "
         f"crowns_match {sum(1 for s in summ if s['crowns_match'])}/{len(summ)}"]
    cc = collections.Counter(m["card_key"] for m in metas)
    L.append("per_card " + json.dumps(cc.most_common()))
    L.append("per_cell_top10 " + json.dumps(collections.Counter(int(m["cell"]) for m in metas).most_common(10)))
    secs = np.array([float(m["seconds"]) for m in metas])
    L.append(f"time_coverage: min {secs.min():.1f} p10 {np.percentile(secs,10):.1f} median {np.median(secs):.1f} p90 {np.percentile(secs,90):.1f} max {secs.max():.1f}; buckets " +
             json.dumps({"0-60": int((secs < 60).sum()), "60-120": int(((secs >= 60) & (secs < 120)).sum()),
                         "120-180": int(((secs >= 120) & (secs < 180)).sum()), "180+": int((secs >= 180).sum())}))
    sd = np.array([float(m["snap_dist_tiles"]) for m in metas])
    L.append(f"snap_dist_tiles mean {sd.mean():.3f} max {sd.max():.3f}")
    L.append(f"unmapped entity samples: rows with n_units_unmapped>0 {sum(1 for m in metas if int(m['n_units_unmapped'])>0)}; "
             f"rows with n_effects>0 {sum(1 for m in metas if int(m['n_effects'])>0)}; n_projectiles>0 {sum(1 for m in metas if int(m['n_projectiles'])>0)}")
    L.append(f"6 towers alive (engine) {sum(1 for m in metas if int(m['my_towers_alive'])==3 and int(m['their_towers_alive'])==3)}/{len(metas)}")
    nu = np.array([int(m["n_units_me"]) + int(m["n_units_them"]) for m in metas])
    L.append(f"units on board at play (v2): mean {nu.mean():.2f} median {np.median(nu):.0f} p90 {np.percentile(nu,90):.0f} max {nu.max()}")
    paired = [m for m in metas if m["v1_row"] not in ("", None)]
    if paired:
        dm = np.array([int(m["d_units_me"]) for m in paired])
        dt = np.array([int(m["d_units_them"]) for m in paired])
        ta = np.array([int(m["towers_agree"]) for m in paired])
        de = np.array([float(m["d_elixir"]) for m in paired])
        L.append(f"v1-vs-v2 at the same play (n {len(paired)} of {len(metas)}): d_units_me mean {dm.mean():+.2f} |d| mean {np.abs(dm).mean():.2f} "
                 f"(v2 more in {int((dm>0).sum())}, fewer in {int((dm<0).sum())}, equal {int((dm==0).sum())}); d_units_them mean {dt.mean():+.2f} |d| {np.abs(dt).mean():.2f} "
                 f"(v2 more {int((dt>0).sum())}, fewer {int((dt<0).sum())}, equal {int((dt==0).sum())}); towers_agree {ta.mean()*100:.1f}%; "
                 f"elixir v2-v1 mean {de.mean():+.2f} |d| mean {np.abs(de).mean():.2f} p90 {np.percentile(np.abs(de),90):.2f} >2: {np.mean(np.abs(de)>2)*100:.1f}%")
        L.append(f"samples NOT in v1 (after the sim's end or sim-rejected): {len(metas)-len(paired)}")
    have = [m for m in metas if m.get("ck_hit1") not in ("", None)]
    if have:
        h1 = np.array([int(m["ck_hit1"]) for m in have])
        h5 = np.array([int(m["ck_hit5"]) for m in have])
        ch = np.array([int(m["ck_card_hit1"]) for m in have])
        L.append(f"baseline c2r_best cells ALL rows: n {len(have)} top1 {h1.mean()*100:.2f}% top5 {h5.mean()*100:.2f}% ; card top1 {ch.mean()*100:.2f}%")
        sp = json.loads((out / "split.json").read_text())
        va = set(sp["val_rows"])
        hv = [m for m in have if int(m["row"]) in va]
        if hv:
            L.append(f"baseline c2r_best cells VAL rows: n {len(hv)} top1 {np.mean([int(m['ck_hit1']) for m in hv])*100:.2f}% top5 {np.mean([int(m['ck_hit5']) for m in hv])*100:.2f}%")
        for card, _ in cc.most_common(10):
            sub = [m for m in have if m["card_key"] == card]
            L.append(f"  card {card:12s} n {len(sub):5d} top1 {np.mean([int(m['ck_hit1']) for m in sub])*100:6.2f}% top5 {np.mean([int(m['ck_hit5']) for m in sub])*100:6.2f}%")
        for lo, hi, name in ((0, 60, "0-60"), (60, 120, "60-120"), (120, 180, "120-180"), (180, 1e9, "180+")):
            sub = [m for m in have if lo <= float(m["seconds"]) < hi]
            if sub:
                L.append(f"  time {name:8s} n {len(sub):5d} top1 {np.mean([int(m['ck_hit1']) for m in sub])*100:6.2f}% top5 {np.mean([int(m['ck_hit5']) for m in sub])*100:6.2f}%")
        L.append("ck_top1_hist_top10 " + json.dumps(collections.Counter(int(m["ck_top1"]) for m in have).most_common(10)))
    sp = json.loads((out / "split.json").read_text())
    L.append(f"split: train tags {len(sp['train_tags'])} rows {sp['n_train']} / val tags {len(sp['val_tags'])} rows {sp['n_val']}; "
             f"v1 val tags not converted {sp['v1_val_tags_not_converted']}")
    txt = "\n".join(L)
    (out / "report.txt").write_text(txt)
    print(txt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all", choices=["all", "assemble", "baseline", "pack", "report"])
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    ap.add_argument("--ckpt", default=str(CKPT_DEFAULT))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.stage in ("all", "assemble"):
        stage_assemble_shards(args, out)
    if args.stage in ("all", "baseline"):
        V1.stage_baseline(args, out)
    if args.stage in ("all", "pack"):
        stage_pack(args, out)
    if args.stage in ("all", "report"):
        stage_report(args, out)


if __name__ == "__main__":
    main()
