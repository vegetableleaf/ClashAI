"""P2-RD1 (plan1026 Pillar 2): HF IL_Replay -> crforge re-drive -> opponent-training rows (production builder).

    run.sh LIBDIR OUT [redrive.py run args]      # the one command; LIBDIR from build_lib.sh (+ facade/), see RD1.md

Per replay (one HF `replays` row + its `actions` rows):
1. Source: both sides' decks (card, level, form from the -ev1 / -hero deck key), tower levels, every play_card
   (tick, side, card, native milli-tile x/y) and activate_ability (candidates), the recorded crowns. team = side 0
   (low y, crforge Blue), opponent = side 1. Blocks (unusable before driving): not 1v1, a deck not 8 cards, a tower troop
   other than Princess (the facade wires none), a card the catalogue lacks.
2. Deal: HF has none. ``RoyalePoolEnv.reset`` -> ``royale_env.deal_order`` (the production rule: first deck order whose
   hand-of-4 + queue cycle holds every recorded play). After a side's 4th play the hand is the same under EVERY fitting
   deal (hand = deck minus the last 4 plays); before it the hand is inferred -> rows flagged ``hand_inferred``.
   RNG: HF has no battle seed; crforge seed 0 (an RNG card's draws are the engine's, not the match's).
3. Drive through crforge (ROYALE_ENGINE=crforge, CrforgeCore facade) both seats, each command GIVEN at
   tick + --offset (crforge runs it 20 later). Strict: the first refused play / press (not in hand, elixir, cell,
   ability state) ends the drive: cut = its tick. Frames every 10 ticks + every command tick (pro2's recorder).
4. Grade: A = every play accepted, the match ends, crowns == recorded; B = the prefix before the first refusal (or the
   whole match when only the crowns differ / no end); unusable = blocked, setup refused, or no accepted play.
5. Rows: the shard's recordings (tier B truncated before its cut) -> ``pipeline.dataset_gen.build(feature_version=5)``
   (fv6 models read fv5 data; public observation, opponent elixir = public counter) -> one parquet per shard.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import traceback
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))

CAP = 6600                 # last tick driven (regulation 3600 + overtime 2400 = 6000, plus the tiebreak)
TOWER_OK = "tower-princess"


def base(key: str) -> str:
    for suf in ("-ev1", "-hero"):
        if key.endswith(suf):
            return key[: -len(suf)]
    return key


# ------------------------------------------------------------------------------------------------ 1. HF -> source
def source(r: dict, acts: list, catalog: dict) -> dict:
    b = json.loads(r["payload_json"])["battle"]
    src = dict(tag=r["replay_tag"], battle_type=r["battle_type"], game_mode=r["game_mode"], blocks=[],
               expected={"crowns_by_side": {"0": int(r["team_crowns"]), "1": int(r["opponent_crowns"])}},
               result=r["result"], decks={}, levels={"cards": {}, "towers": [16, 16]}, final_towers={})
    for s, k in ((0, "team"), (1, "opponent")):
        ps = b[k]["players"]
        if len(ps) != 1:
            src["blocks"].append("not_1v1")
            return src
        p = ps[0]
        deck = p["deck"]
        if len(deck) != 8 or len({base(c["card_key"]) for c in deck}) != 8:
            src["blocks"].append("deck_not_8")
            return src
        for c in deck:
            if base(c["card_key"]) not in catalog:
                src["blocks"].append("unsupported_card:" + base(c["card_key"]))
        tower = (p.get("tower_card") or {}).get("card_key") or TOWER_OK
        if tower != TOWER_OK:
            src["blocks"].append("tower_troop:" + tower)
        src["decks"][s] = [c["card_key"] for c in deck]
        src["levels"]["cards"][s] = [int(c.get("level") or 16) for c in deck]
        src["levels"]["towers"][s] = int((p.get("tower_card") or {}).get("level") or 16)
        src["final_towers"][s] = p.get("final_tower_hitpoints")
    plays = []
    for a in sorted(acts, key=lambda a: (a["replay_tick_20hz"], a["event_index"])):
        ab = a["kind"] == "activate_ability"
        if not ab and a["kind"] != "play_card":
            src["blocks"].append("event_kind:" + str(a["kind"]))
            continue
        if not ab and (a["card_key"] is None or a["native_x"] is None):
            src["blocks"].append("play_without_card_or_point")
            continue
        plays.append(dict(play_index=int(a["event_index"]), tick=int(a["replay_tick_20hz"]),
                          side=0 if a["side"] == "team" else 1, card=None if ab else base(a["card_key"]), ability=ab,
                          candidates=[base(c) for c in (a["ability_source_candidates"] or [])],
                          x=None if ab else int(a["native_x"]), y=None if ab else int(a["native_y"])))
    src["plays"] = plays
    if not any(not p["ability"] for p in plays):
        src["blocks"].append("no_plays")
    return src


def hf_sources(rp: Path, ap: Path, lo: int, hi: int, catalog: dict):
    import pyarrow.parquet as pq
    reps = pq.read_table(rp).slice(lo, hi - lo).to_pylist()
    tags = [r["replay_tag"] for r in reps]
    acts = defaultdict(list)
    for a in pq.read_table(ap, filters=[("replay_tag", "in", tags)],
                           columns=["replay_tag", "event_index", "kind", "side", "card_key", "replay_tick_20hz",
                                    "native_x", "native_y", "ability_source_candidates"]).to_pylist():
        acts[a["replay_tag"]].append(a)
    for r in reps:
        yield source(r, acts[r["replay_tag"]], catalog)


# ------------------------------------------------------------------------------------------------ 2-4. drive + grade
def timed_deal(slugs: list, plays: list):
    """``royale_env.deal_order`` with crforge's hand timing: a given card stays in hand (pending, not replayable) until
    it runs, given + 20 < t; only then its slot takes the queue front and it joins the back. ``plays`` = [(given tick,
    slug)] in order. First fit of 70 hands x 24 queues, or None. (Pilot 200, deal_order's untimed fit: 20 of 21
    not_in_hand cuts came within 20 ticks of the side's previous play, before its 4th play ran.)"""
    from itertools import combinations, permutations
    idx = [(t, slugs.index(c)) for t, c in plays]
    for hand in combinations(range(8), 4):
        rest = [i for i in range(8) if i not in hand]
        for queue in permutations(rest):
            h, q, pend = set(hand), list(queue), []
            for t, i in idx:
                while pend and pend[0][0] < t:
                    j = pend.pop(0)[1]
                    h.discard(j)
                    h.add(q.pop(0))
                    q.append(j)
                if i not in h or any(j == i for _, j in pend):
                    break
                pend.append((t + 20, i))
            else:
                return list(hand) + list(queue)
    return None


_ENV = {}


def env_and_catalog():
    if not _ENV:
        import msgspec
        from pipeline import royale_heroiw
        from pipeline.royale_env import RoyalePoolEnv
        from scratchpad.gauntlet.L74.pro2.build_rows import card_catalog
        royale_heroiw.deck_forms = lambda names, forms: list(forms)   # HF decks carry their own forms (no IW override)

        class Env(RoyalePoolEnv):
            levels = None

            def _setup(self, deal, order, wanted):          # + HF levels, permuted with the deal (RoyaleSelfPlayEnv's way)
                s = super()._setup(deal, order, wanted)
                lv = self.levels
                return msgspec.structs.replace(s, levels=[[lv["cards"][k][i] for i in order[k]] for k in (0, 1)],
                                               tower_levels=list(lv["towers"]))

        _ENV["env"] = Env(warmup_ticks=0, forms_mode="deck", feature_version=5, seed=0, iw_press="off")
        _ENV["catalog"] = card_catalog()
    return _ENV["env"], _ENV["catalog"]


def drive(src: dict, offset: int) -> tuple[dict, dict | None]:
    """-> (grade, recording or None)."""
    from pipeline.royale_env import RESULT_CODE_NAMES, UnsupportedDeck
    from scratchpad.gauntlet.L74.pro2.build_rows import CHAMPIONS, snapshot
    env, catalog = env_and_catalog()
    g = dict(tag=src["tag"], plays=sum(not p["ability"] for p in src.get("plays", [])),
             presses=sum(p["ability"] for p in src.get("plays", [])))
    if src["blocks"]:
        return dict(g, tier="unusable", reason=sorted(set(src["blocks"]))[0]), None
    suffix = lambda k: "@evolution" if k.endswith("-ev1") else "@hero" if k.endswith("-hero") else ""
    decks = {s: [dict(slug=base(k), name=catalog[base(k)]["display_name"],
                      form="evolution" if k.endswith("-ev1") else "hero" if k.endswith("-hero") else "base")
                 for k in src["decks"][s]] for s in (0, 1)}
    cmds = {s: [p for p in src["plays"] if p["side"] == s] for s in (0, 1)}
    env.levels = src["levels"]
    try:
        env.reset(dict(tag=src["tag"], our_side=0, ghost_side=1, our_deck=decks[0], ghost_deck=decks[1],
                       our_commands=cmds[0], ghost_commands=cmds[1]))
    except UnsupportedDeck as e:
        return dict(g, tier="unusable", reason="no_fitting_deal" if "no deal fits" in str(e) else "unsupported_deck"), None
    except Exception as e:                                     # crforge refused the setup (a form / card it lacks)
        return dict(g, tier="unusable", reason="setup_refused:" + type(e).__name__, detail=str(e)[:200]), None
    if env.form_fallbacks:
        return dict(g, tier="unusable", reason="form_refused", detail=str(env.form_fallbacks)[:200]), None
    # re-deal with crforge's hand timing (timed_deal); a side no timed deal fits keeps reset's deal_order deal
    from pipeline.royale_env import FORM_OF, deal_order
    orders = {}
    for s in (0, 1):
        slugs = [c["slug"] for c in decks[s]]
        pl = [p for p in sorted(cmds[s], key=lambda p: (p["tick"], p["play_index"])) if not p["ability"]]
        orders[s] = timed_deal(slugs, [(p["tick"] + offset, p["card"]) for p in pl])
        if orders[s] is None:
            g.setdefault("deal_untimed", []).append(s)
            orders[s] = deal_order(slugs, [p["card"] for p in pl])
    env.core.reset(env.seed, env._setup({s: [env.deck_ids[s][i] for i in orders[s]] for s in (0, 1)}, orders,
                                        {s: [FORM_OF[c["form"]] for c in decks[s]] for s in (0, 1)}))
    env._reset_abilities()
    env.tick = int(env.core.state().tick)
    env._ghosts, env._gi, env._pending = [], 0, []
    rec = dict(tag=src["tag"], recording_origin="crforge_redrive_hf", record_native=True, record_full=True,
               record_every=10, drive_abilities=True, forms_unobserved=True, expected=src["expected"],
               final_decks={str(s): [c["name"] + suffix(k) for c, k in zip(decks[s], src["decks"][s])] for s in (0, 1)},
               frames=[], play_frames=[], log=[])
    order = sorted(src["plays"], key=lambda p: (p["tick"] + offset, p["play_index"]))
    ci, cut, why = 0, None, None
    try:
        while not env.terminated and env.tick <= CAP:
            t = env.tick
            due = []
            while ci < len(order) and order[ci]["tick"] + offset <= t:
                due.append(order[ci])
                ci += 1
            if t % 10 == 0 or due:
                rec["frames"].append(snapshot(env.raw(), catalog))
            for k, p in enumerate(due):
                pf = rec["frames"][-1] if k == 0 else snapshot(env.raw(), catalog)
                side = p["side"]
                ev = dict(play_index=p["play_index"], tick=t, hf_tick=p["tick"], side=side, card=p["card"],
                          ability=p["ability"], x=p["x"], y=p["y"], hand_before=pf["players"][side]["hand"])
                if p["ability"]:
                    allowed = set(p["candidates"]) or {c["slug"] for c in decks[side]
                                                       if c["slug"] in CHAMPIONS or c["form"] == "hero"}
                    ids = {env.card_id(c["name"]): c["slug"] for c in decks[side] if c["slug"] in allowed}
                    buttons = [(i, int(b[3])) for i, b in enumerate(env.core.state().players[side].abilities)
                               if int(b[3]) in ids]
                    if len(buttons) > 1:     # HF candidates are not authoritative: keep the ones the engine would take
                        from royalegym.protocol import HAND_SIZE, DeployCommand, DeployStatus
                        legal = [b for b in buttons if env.core.check_deploy(
                            DeployCommand(side, HAND_SIZE + b[0], 0, 0)) == DeployStatus.OK]
                        g["press_disambiguated"] = g.get("press_disambiguated", 0) + (len(legal) == 1)
                        buttons = legal if len(legal) == 1 else buttons
                    if len(buttons) != 1:
                        res = dict(accepted=False, result_code="ability_identity_unavailable")
                        g["detail"] = dict(allowed=sorted(allowed), ids=sorted(ids), rows=[
                            [int(v) for v in b] for b in env.core.state().players[side].abilities])
                    else:
                        ev["card"] = ids[buttons[0][1]]
                        res = env.eng.act(side=side, ability_button=buttons[0][0])
                else:
                    di = next(i for i, c in enumerate(decks[side]) if c["slug"] == p["card"])
                    res = env.eng.act(side=side, deck_index=di, x=p["x"], y=p["y"])
                if not res["accepted"]:
                    rc = res["result_code"]
                    cut, why = t, rc if isinstance(rc, str) else RESULT_CODE_NAMES.get(rc, f"code_{rc}")
                    prev = [e["tick"] for e in rec["log"] if e["side"] == side and not e["ability"]]
                    g.update(cut_card=p["card"], cut_side=side, cut_ability=p["ability"], cut_elixir=pf["elixir"][side],
                             cut_prev_gap=t - prev[-1] if prev else None)
                    break
                ev.update(res)
                rec["log"].append(ev)
                rec["play_frames"].append(dict(pf, play_index=p["play_index"]))
            if cut is not None:
                break
            nxt = order[ci]["tick"] + offset if ci < len(order) else CAP + 1
            env._advance_to(max(t + 1, min(nxt, (t // 10 + 1) * 10, CAP + 1)))
    except Exception as e:                                     # an engine fault mid-match: the prefix before it stands
        cut, why = env.tick, "engine_error:" + type(e).__name__
        if str(e).startswith("unmapped_sim_public_identity:"):   # pro2 snapshot: the native catalogue lacks this form
            why = "record_identity:" + str(e).split(":", 1)[1]
        g["detail"] = str(e)[:200]
    st = env.core.state()
    crowns = {str(p.team): int(p.crowns) for p in st.players}
    acc = [e for e in rec["log"] if not e["ability"]]
    g.update(accepted_plays=len(acc), accepted_presses=len(rec["log"]) - len(acc), end_tick=int(st.tick),
             game_over=bool(env.terminated), crowns=crowns, crowns_match=crowns == src["expected"]["crowns_by_side"],
             hf_end_tick=max(p["tick"] for p in src["plays"]))
    if cut is None and env.terminated and g["crowns_match"]:
        g["tier"] = "A"
    elif not acc:
        return dict(g, tier="unusable", reason="first_play_refused:" + str(why)), None
    else:
        g["tier"] = "B"
        g["reason"] = ("refused:" + why if cut is not None and not why.startswith(("engine_error", "record_identity"))
                       else why if cut is not None else "crowns_mismatch" if env.terminated else "no_game_over")
        g["cut_tick"] = cut
        if cut is not None:
            rec["frames"] = [f for f in rec["frames"] if f["tick"] < cut]
    # rows before a side's 4th accepted play carry a deal-inferred hand (docstring 2)
    g["hand_known_from"] = {str(s): ([e["tick"] for e in acc if e["side"] == s][3:4] or [None])[0] for s in (0, 1)}
    rec["final"] = dict(tick=int(st.tick), crowns=crowns)
    rec["grade"] = g
    return g, rec


# ------------------------------------------------------------------------------------------------ 5. rows
def npz_to_parquet(npz: Path, out: Path, grades: dict) -> int:
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq
    z = np.load(npz, allow_pickle=False)
    meta = json.loads(str(z["meta"]))
    n = len(z["sc"])
    tags = z["tags"][z["rep"]]
    cols, shapes = {}, {}
    for k in z.files:
        if k in ("meta", "tags", "off", "tok"):
            continue
        a = z[k]
        if a.shape[:1] != (n,):
            continue
        shapes[k] = list(a.shape[1:])
        flat = a.reshape(n, -1) if a.ndim > 1 else a
        cols[k] = (pa.FixedSizeListArray.from_arrays(pa.array(flat.ravel()), flat.shape[1]) if a.ndim > 1
                   else pa.array(a))
    tok, off = z["tok"], z["off"]
    shapes["tok"] = [None, int(tok.shape[1])]
    cols["tok"] = pa.LargeListArray.from_arrays(pa.array(off, pa.int64()),
                                                pa.FixedSizeListArray.from_arrays(pa.array(tok.ravel()), tok.shape[1]))
    cols["tag"] = pa.array(tags.astype(str))
    tier = np.array([grades[str(t)]["tier"] for t in tags])
    cols["tier"] = pa.array(tier)
    hk = np.array([grades[str(t)]["hand_known_from"].get(str(int(s))) for t, s in zip(tags, z["side"])], dtype=object)
    cols["hand_inferred"] = pa.array([h is None or int(tk) <= h + 20 for h, tk in zip(hk, z["tick"])])  # to the 4th run
    table = pa.table(cols).replace_schema_metadata({"meta": json.dumps(meta), "shapes": json.dumps(shapes)})
    pq.write_table(table, out, compression="zstd")
    return n


def run_shard(job: dict) -> dict:
    out, sid = Path(job["out"]), job["sid"]
    done = out / "shards" / f"{sid}.json"
    if done.exists():
        return json.loads(done.read_text())
    t0 = time.time()
    tmp = out / "tmp" / sid
    shutil.rmtree(tmp, ignore_errors=True)
    (tmp / "corpus").mkdir(parents=True)
    env, catalog = env_and_catalog()
    grades = {}
    for src in hf_sources(Path(job["rp"]), Path(job["ap"]), job["lo"], job["hi"], catalog):
        g, rec = drive(src, job["offset"])
        grades[g["tag"]] = g
        if rec is not None:
            (tmp / "corpus" / f"replay_{g['tag']}.json").write_text(json.dumps(rec))
    t1 = time.time()
    res = dict(sid=sid, replays=len(grades), tiers=dict(Counter(g["tier"] for g in grades.values())),
               reasons=dict(Counter(f"{g['tier']}:{g.get('reason', '')}" for g in grades.values())),
               drive_s=round(t1 - t0, 1), stamp=env.core.card_table_stamp(), rows=0, build_failed=[])
    from pipeline.dataset_gen import build, replay_rows
    files = sorted((tmp / "corpus").glob("replay_*.json"))
    if files:
        try:
            build([tmp / "corpus"], tmp / "rows.npz", feature_version=5, grid="lattice", workers=1, wait_stride=40,
                  play_window=20, shift_ticks=0, val_pct=10, log=None)
        except ValueError as e:                               # one bad recording sinks a gen_v3.1 build: set it aside
            if "refuses failed recordings" not in str(e):
                raise
            for f in files:
                r = replay_rows(str(f), feature_version=5)
                if "error" in r:
                    res["build_failed"].append([f.stem[7:], r["error"][:200]])
                    grades[f.stem[7:]].update(tier="unusable", reason="row_build_failed")
                    f.unlink()
            build([tmp / "corpus"], tmp / "rows.npz", feature_version=5, grid="lattice", workers=1, wait_stride=40,
                  play_window=20, shift_ticks=0, val_pct=10, log=None)
        pth = out / "rows" / f"{sid}.parquet"
        pth.parent.mkdir(parents=True, exist_ok=True)
        res["rows"] = npz_to_parquet(tmp / "rows.npz", pth, grades)
        res["parquet_sha256"] = hashlib.sha256(pth.read_bytes()).hexdigest()
        res["parquet_bytes"] = pth.stat().st_size
    res["tiers"] = dict(Counter(g["tier"] for g in grades.values()))
    res["reasons"] = dict(Counter(f"{g['tier']}:{g.get('reason', '')}" for g in grades.values()))
    res["rows_s"] = round(time.time() - t1, 1)
    (out / "grades").mkdir(parents=True, exist_ok=True)
    (out / "grades" / f"{sid}.jsonl").write_text("".join(json.dumps(g) + "\n" for g in grades.values()))
    shutil.rmtree(tmp, ignore_errors=True)
    done.parent.mkdir(parents=True, exist_ok=True)
    done.with_suffix(".part").write_text(json.dumps(res))
    done.with_suffix(".part").rename(done)
    return res


def _safe(job):
    try:
        return run_shard(job)
    except Exception:
        return dict(sid=job["sid"], error=traceback.format_exc()[-1500:])


def jobs(data: Path, out: Path, chunk: int, limit: int, offset: int) -> list:
    import pyarrow.parquet as pq
    parts = sorted((data / "replays").glob("part-*.parquet"))
    per = []
    for rp in parts:
        n = pq.ParquetFile(rp).metadata.num_rows
        per.append([dict(sid=f"{rp.stem}_{lo:05d}", rp=str(rp), ap=str(data / "actions" / rp.name), lo=lo,
                         hi=min(lo + chunk, n), out=str(out), offset=offset) for lo in range(0, n, chunk)])
    out_jobs = [j for i in range(max(map(len, per))) for p in per if i < len(p) for j in [p[i]]]   # round-robin parts
    if limit:
        keep, tot = [], 0
        for j in out_jobs:
            if tot >= limit:
                break
            keep.append(j)
            tot += j["hi"] - j["lo"]
        out_jobs = keep
    return out_jobs


def manifest(out: Path, args: dict) -> dict:
    done = [json.loads(p.read_text()) for p in sorted((out / "shards").glob("*.json"))]
    tiers, reasons = Counter(), Counter()
    for d in done:
        tiers.update(d["tiers"])
        reasons.update(d["reasons"])
    lib = Path(os.environ.get("CRFORGE_LIB", "")).parent
    build = json.loads((lib / "BUILD.json").read_text()) if (lib / "BUILD.json").exists() else None
    facade = lib / "CfCore.java"
    m = dict(schema="p2rd1-rows.v1", created=time.strftime("%Y-%m-%d %H:%M:%S"), args=args,
             crforge_build=build, facade_sha256=hashlib.sha256(facade.read_bytes()).hexdigest() if facade.exists() else None,
             tables=os.environ.get("CRFORGE_TABLES"),
             # the facade's card_table_stamp "crforge" field is its hard-coded CRFORGE_PIN, not the loaded lib: dropped
             table_stamp={k: v for k, v in done[0]["stamp"].items() if k != "crforge"} if done else None,
             code_head=os.environ.get("RD_CODE_HEAD"), row_builder="pipeline.dataset_gen.build feature_version=5 "
             "(fv6 models read fv5 data), wait_stride 40, play_window 20, grid lattice, val_pct 10",
             shards=len(done), replays=sum(d["replays"] for d in done), rows=sum(d["rows"] for d in done),
             bytes=sum(d.get("parquet_bytes", 0) for d in done), tiers=dict(tiers), reasons=dict(reasons.most_common()),
             drive_s=round(sum(d["drive_s"] for d in done), 1), rows_s=round(sum(d["rows_s"] for d in done), 1),
             files=[dict(path=f"rows/{d['sid']}.parquet", rows=d["rows"], sha256=d.get("parquet_sha256"),
                         replays=d["replays"], tiers=d["tiers"]) for d in done if d["rows"]])
    (out / "manifest.json").write_text(json.dumps(m, indent=1))
    return m


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--data", type=Path, required=True)
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--chunk", type=int, default=250)
    r.add_argument("--limit", type=int, default=0, help="replays (whole shards, round-robin over parts)")
    r.add_argument("--workers", type=int, default=48)
    r.add_argument("--offset", type=int, default=0, help="given tick = HF replay tick + offset")
    m = sub.add_parser("manifest")
    m.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "manifest":
        print(json.dumps({k: v for k, v in manifest(a.out, {}).items() if k != "files"}, indent=1))
        return 0
    from pipeline.royale_runtime import ENGINE
    if ENGINE != "crforge":
        raise SystemExit("ROYALE_ENGINE=crforge required")
    a.out.mkdir(parents=True, exist_ok=True)
    js = jobs(a.data, a.out, a.chunk, a.limit, a.offset)
    todo = [j for j in js if not (a.out / "shards" / f"{j['sid']}.json").exists()]
    print(f"[rd1] {len(js)} shards, {len(todo)} to do, {a.workers} workers", flush=True)
    t0, errs = time.time(), 0
    import multiprocessing as mp
    with mp.get_context("spawn").Pool(a.workers, maxtasksperchild=40) as pool:
        for i, res in enumerate(pool.imap_unordered(_safe, todo), 1):
            if "error" in res:
                errs += 1
                (a.out / "errors").mkdir(exist_ok=True)
                (a.out / "errors" / f"{res['sid']}.txt").write_text(res["error"])
            print(f"[rd1] {i}/{len(todo)} {res['sid']} {res.get('tiers', 'ERROR')} rows={res.get('rows')} "
                  f"drive={res.get('drive_s')}s rows={res.get('rows_s')}s t={time.time() - t0:.0f}s errs={errs}",
                  flush=True)
    args = {k: str(v) for k, v in vars(a).items()}
    mf = manifest(a.out, args)
    print(json.dumps({k: v for k, v in mf.items() if k != "files"}, indent=1))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
