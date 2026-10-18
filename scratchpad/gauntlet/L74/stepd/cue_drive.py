"""Step d: re-drive pro replays in RoyaleSim and record the 22 cue floats of every body on every recorded frame.

    # laptop / with the native corpus (fid measured against the native frames):
    ROYALE_RUNTIME=<runtime> python scratchpad/gauntlet/L74/stepd/cue_drive.py \
        --corpus scratchpad/gauntlet/ext/corpus_v6/icebow_public_v1 [--crawl DIR ...] --out DIR [--limit N] [--workers W]
    # pod mode (no native corpus shipped; fid measured by cue_sidecar on the dataset's own tokens):
    ROYALE_RUNTIME=<runtime> python scratchpad/gauntlet/L74/stepd/cue_drive.py --from-data gen_dataset_v32_fv5.npz \
        --crawl <pilot crawl> <crawl_hf_icebow> <crawl_hf_hogeq> <icebow crawl2> <hogeq crawl2> --out DIR --workers 24
    # new sources without a dataset yet (rows are then built from the kept SIM recordings): --crawl DIR --crawl-only

Command source per replay: the crawl CSV (battles.csv + plays_ext.csv / plays.csv: card plays AND hero / champion
presses) when a --crawl dir has the tag, else the native recording's own play log (card plays only; ability presses are
absent there, so a deck with a hero / champion is flagged ``abilities_missing``). The SIM drive is PRO2's
``build_rows.drive`` (deal inference, both command streams, refused / delayed plays kept) + a read-only ``on_frame`` hook
and ``record_ticks`` (the native recorder's / the dataset's row ticks, so every row has an exact-tick SIM frame).
Each replay is driven with the Ice Wizard form its own deck string names (ROYALE_HEROIW_FORM set per replay).

Output per replay: <out>/cue_<tag>.npz with
  tick [n] int32, pidx [n] int32 (-1 = periodic frame, else the play_index of a pre-act play frame),
  fid [n] float32  = SIM-vs-NATIVE body agreement on that frame (Dice over non-tower bodies matched by side + card id
                     within FID_TILES; NaN = no native frame there, or --from-data: measured on the tokens later; 1 =
                     --crawl-only, rows built from this very recording), hp_ok [n] = matched pairs with |hp diff| <=
                     15% max hp / matched pairs (NaN if none),
  off [n+1] int64, bodies [sum, 4 + CUE_N] float32 = [team, x tiles, y tiles, hp_frac, *model_gen.cue_vector] per
                     non-tower body (sim_unit_state.extract, hit_window_ms=100, one buff memo per replay = sim_cue_rows),
  meta = json {tag, source, abilities_missing, grade (the SIM drive's), native_grade, fid summary, seconds}.
cue_sidecar.py aligns `bodies` to a dataset's unit tokens with live_unit_state.align (= sim_cue_rows' match, verbatim).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FID_TILES = 1.0                      # a SIM body "is" the native body: same side + card id within 1 tile
HP_TOL = 0.15
SIDE_OF = {"red": 0, "blue": 1}      # research/sandbox_tools/replay_drive.py (the native drive's loader)
DECK_COL_OF_SIDE = {0: "opponent_deck", 1: "team_deck"}
CROWN_COL_OF_SIDE = {0: "opponent_crowns", 1: "team_crowns"}
CHAMPIONS = {"archer-queen", "golden-knight", "skeleton-king", "mighty-miner", "monk", "little-prince", "goblinstein",
             "boss-bandit"}


# ---------------------------------------------------------------------------------------------- command sources
def load_crawl(crawl: Path) -> tuple[dict, dict]:
    """battles.csv rows by tag, plays_ext.csv rows by tag (one pass each)."""
    with (crawl / "battles.csv").open(encoding="utf-8", newline="") as f:
        battles = {r["replay_tag"]: r for r in csv.DictReader(f)}
    plays: dict = {}
    # crawl2's plays_ext.csv lost its positions (L64 column shift); the re-fetched, positioned copy with attr_i is
    # plays_ext_i1.csv (what the native drive read). The L70 hero crawl names it plays.csv.
    pf = next(p for p in (crawl / "plays_ext_i1.csv", crawl / "plays_ext.csv", crawl / "plays.csv") if p.is_file())
    with pf.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            plays.setdefault(r["replay_tag"], []).append(r)
    return battles, plays


def source_from_crawl(tag: str, battle: dict, rows: list) -> dict:
    """PRO2 source dict from crawl rows, with replay_drive.load_battle's rules (red -> 0, blue -> 1; attr_i == 1 rows
    rotated 180 degrees; ability rows carry no position)."""
    plays, blocks = [], []
    for r in rows:
        ab = int(r["attr_ability"])
        p = dict(play_index=int(r["play_index"]), tick=int(r["tick"]), side=SIDE_OF[r["attr_s"]], card=r["attr_card"],
                 ability=ab, x=None, y=None)
        if not ab:
            if r["x_units"] in ("", "None") or r["y_units"] in ("", "None"):
                blocks.append(f"unpositioned_play:{r['play_index']}")
                continue
            x, y = int(r["x_units"]), int(r["y_units"])
            if r.get("attr_i") == "1":
                x, y = 18000 - x, 32000 - y
            p["x"], p["y"] = x / 1000.0, y / 1000.0
        plays.append(p)
    plays.sort(key=lambda p: (p["tick"], p["play_index"]))
    decks = {str(s): [t.strip() for t in battle[DECK_COL_OF_SIDE[s]].split(",")] for s in (0, 1)}
    crowns = {str(s): int(battle[CROWN_COL_OF_SIDE[s]]) for s in (0, 1)}
    return dict(tag=tag, decks=decks, plays=plays, expected=dict(crowns_by_side=crowns), blocks=blocks,
                source="crawl", source_sha256=hashlib.sha256(json.dumps([battle, rows], sort_keys=True).encode()).hexdigest())


def source_from_native(rec: dict) -> dict:
    """PRO2 source dict from a native recording's own log: every driven card play at its ORIGINAL command tick (x, y
    already in the engine frame). The log holds no ability presses."""
    from pipeline.dataset_gen import card_form, card_key
    suffix = {0: "", 1: "-ev1", 2: "-hero"}
    decks = {s: [card_key(n) + suffix[card_form(n)] for n in names] for s, names in rec["final_decks"].items()}
    plays = [dict(play_index=int(e["play_index"]), tick=int(e["tick"]), side=int(e["side"]), card=e["card"], ability=0,
                  x=e["x"] / 1000.0, y=e["y"] / 1000.0)
             for e in rec["log"] if "tick" in e and e.get("x") is not None and not e.get("ability")]
    plays.sort(key=lambda p: (p["tick"], p["play_index"]))
    heroic = any(t.endswith("-hero") or t in CHAMPIONS for d in decks.values() for t in d)
    return dict(tag=str(rec["tag"]), decks=decks, plays=plays, expected=dict(crowns_by_side=rec["expected"]["crowns_by_side"]),
                blocks=[], source="native_log", abilities_missing=heroic,
                source_sha256=hashlib.sha256(json.dumps(rec["log"], sort_keys=True).encode()).hexdigest())


# ---------------------------------------------------------------------------------------------- fidelity
def body_fid(native: list, sim: list) -> tuple[float, float]:
    """(Dice agreement, hp_ok share) of two compact entity lists [side, x, y, name, hp, max_hp, kind, card_id, id]
    (x, y engine units = 1/1000 tile): non-tower live bodies, pairs by side + card id, nearest-first within FID_TILES."""
    def bodies(ents):
        ents = [[e["side"], e["x"], e["y"], None, e["hp"], e["max_hp"], None, e["card_id"]] if isinstance(e, dict) else e
                for e in ents]
        return [(int(e[0]), int(e[7]), float(e[1]), float(e[2]), float(e[4]), float(e[5])) for e in ents
                if int(e[7]) >= 0 and float(e[4]) > 0]
    a, b = bodies(native), bodies(sim)
    if not a and not b:
        return 1.0, float("nan")
    pairs = sorted((math.hypot(p[2] - q[2], p[3] - q[3]) / 1000.0, i, j) for i, p in enumerate(a) for j, q in enumerate(b)
                   if p[0] == q[0] and p[1] == q[1])
    ui, uj, hp = set(), set(), []
    for d, i, j in pairs:
        if d > FID_TILES:
            break
        if i in ui or j in uj:
            continue
        ui.add(i); uj.add(j)
        hp.append(abs(a[i][4] - b[j][4]) <= HP_TOL * max(a[i][5], 1.0))
    return 2 * len(ui) / (len(a) + len(b)), (float(np.mean(hp)) if hp else float("nan"))


# ---------------------------------------------------------------------------------------------- the drive
BODY_HEAD = 4                        # body row = [team, x tiles, y tiles, hp_frac, *cue22]


def cue_bodies(env, memo: dict) -> list:
    """[[team, x, y, hp_frac, *cue22]] for every non-tower SIM body at this moment (e1_eval.sim_cue_rows' settings)."""
    from pipeline.model_gen import cue_vector
    from pipeline.sim_unit_state import extract
    c = extract(env.core._battle, memo, hit_window_ms=100)
    towers = {u["uid"] for u in c["units"] if u["kind"] in ("princess_tower", "king_tower")}
    return [[u["team"], u["x"], u["y"], u["hp"] / max(u["max_hp"], 1), *cue_vector(u, u["attack"]["target"] in towers)]
            for u in c["units"] if u["uid"] not in towers]


def drive_one(source: dict, catalog: dict, native: dict | None, row_ticks=()) -> tuple[dict, dict]:
    """-> (arrays for cue_<tag>.npz, the SIM recording). ``row_ticks`` (--from-data): the dataset's row ticks for this
    replay, recorded exactly; with no native recording the fid stays NaN and cue_sidecar measures it on the tokens."""
    import os
    from scratchpad.gauntlet.L74.pro2.build_rows import drive
    memo: dict = {}
    t0 = time.monotonic()
    # royale_heroiw.deck_forms forces an exact-icebow deck's Ice Wizard to the ROYALE_HEROIW_FORM form: a replay is
    # driven with the form its OWN deck string names (pre-10-05 pro icebow = plain IW; the hero crawl = 'ice-wizard-hero')
    hero = any(t == "ice-wizard-hero" for d in source["decks"].values() for t in d)
    old = os.environ.get("ROYALE_HEROIW_FORM")
    os.environ["ROYALE_HEROIW_FORM"] = "hero" if hero else "normal"
    # the native recorder restarts its 10-tick cadence at every play (195, 205, 215, ...): the dataset's wait rows sit on
    # THOSE ticks, so the SIM records them too (exact-tick cues; a nearest frame would shift attack phases)
    record = frozenset([int(f["tick"]) for f in (native or {}).get("frames") or []] + [int(t) for t in row_ticks])
    try:
        rec = drive(source, catalog, on_frame=lambda env, fr, kind: fr.__setitem__("cue", cue_bodies(env, memo)),
                    record_ticks=record)
    finally:
        if old is None:
            os.environ.pop("ROYALE_HEROIW_FORM", None)
        else:
            os.environ["ROYALE_HEROIW_FORM"] = old
    nat_t = {int(f["tick"]): f["entities"] for f in (native or {}).get("frames") or []}
    nat_p = {int(f["play_index"]): f["entities"] for f in (native or {}).get("play_frames") or []}
    rows = [(int(f["tick"]), -1, f, nat_t.get(int(f["tick"]))) for f in rec["frames"]]
    rows += [(int(f["tick"]), int(f["play_index"]), f, nat_p.get(int(f["play_index"]))) for f in rec["play_frames"]]
    rows.sort(key=lambda r: (r[0], r[1]))
    fid, hp_ok, off, bodies = [], [], [0], []
    for _, _, f, nat in rows:
        if native is None:                    # crawl-only: rows built FROM this recording (fid 1 = self); --from-data:
            d, h = (float("nan") if len(row_ticks) else 1.0), float("nan")   # NaN = measured on the tokens later
        else:
            d, h = body_fid(nat, f["entities"]) if nat is not None else (float("nan"), float("nan"))
        fid.append(d); hp_ok.append(h)
        bodies.extend(f["cue"]); off.append(len(bodies))
    fa = np.asarray(fid, np.float32)
    ref = "native" if native is not None else "tokens" if len(row_ticks) else "self"
    meta = dict(tag=source["tag"], source=source["source"], fid_reference=ref,
                abilities_missing=bool(source.get("abilities_missing")),
                grade=rec["grade"], native_grade=(native or {}).get("grade"), seconds=round(time.monotonic() - t0, 2),
                frames=len(rows), fid_mean=float(np.nanmean(fa)) if np.isfinite(fa).any() else None,
                fid_ge_090=float(np.mean(fa[np.isfinite(fa)] >= 0.9)) if np.isfinite(fa).any() else None)
    arrays = dict(tick=np.asarray([r[0] for r in rows], np.int32), pidx=np.asarray([r[1] for r in rows], np.int32),
                  fid=fa, hp_ok=np.asarray(hp_ok, np.float32), off=np.asarray(off, np.int64),
                  bodies=np.asarray(bodies, np.float32).reshape(-1, BODY_HEAD + 22), meta=np.asarray(json.dumps(meta)))
    return arrays, rec


_W: dict = {}


def _init(crawls: list):
    from pipeline.royale_runtime import activate
    from scratchpad.gauntlet.L74.pro2.build_rows import card_catalog
    _W["stamp"] = activate()
    _W["catalog"] = card_catalog()
    battles, plays = {}, {}
    for c in crawls:                          # several crawl dirs (pilot / crawl_hf_* / crawl2): the first one with a tag wins
        b, p = load_crawl(Path(c))
        for t in b:
            if t not in battles:
                battles[t], plays[t] = b[t], p.get(t, [])
    _W["crawl"] = (battles, plays)


def _job(args) -> dict:
    path, out, keep, row_ticks = args
    if path.startswith("crawl:"):             # crawl-only (no native recording): rows come from the SIM recording
        native, tag, keep = None, path[len("crawl:"):], True
    elif path.startswith("data:"):            # --from-data: the dataset's own rows (native tokens); no native file needed
        native, tag = None, path[len("data:"):]
        if tag not in _W["crawl"][1] or not _W["crawl"][1][tag]:
            return dict(tag=tag, failed="no_crawl_source")
    else:
        native = json.loads(Path(path).read_text(encoding="utf-8"))
        tag = str(native["tag"])
    dest = Path(out) / f"cue_{tag}.npz"
    if dest.exists():
        return dict(tag=tag, skipped="exists")
    battles, plays = _W["crawl"]
    try:
        source = (source_from_crawl(tag, battles[tag], plays[tag]) if plays.get(tag) or native is None
                  else source_from_native(native))           # a crawl tag with no play rows: the native log instead
        if native is not None and source["source"] == "crawl" and (source["blocks"] or not source["plays"]):
            source = source_from_native(native)               # an unpositioned crawl copy: the native log instead
        if not source["plays"]:
            return dict(tag=tag, failed="no_plays")
        if source["blocks"]:
            return dict(tag=tag, failed="blocked:" + ",".join(source["blocks"][:3]))
        arrays, rec = drive_one(source, _W["catalog"], native, row_ticks)
    except (ValueError, KeyError, StopIteration) as e:
        return dict(tag=tag, failed=f"{type(e).__name__}: {e}"[:300])
    np.savez_compressed(dest, **arrays)
    if keep:
        (Path(out) / f"replay_{tag}.json").write_text(json.dumps(rec), encoding="utf-8")
    return json.loads(str(arrays["meta"]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", type=Path, nargs="*", default=[], help="native recording dirs (replay_*.json, any depth)")
    ap.add_argument("--crawl", nargs="*", default=[],
                    help="crawl dirs with battles.csv + plays_ext.csv / plays.csv (the preferred command source)")
    ap.add_argument("--crawl-only", action="store_true",
                    help="drive every --crawl battle with no native recording (e.g. the L70 Hero IW crawl); implies "
                         "--keep-recording (dataset_gen builds the rows from replay_<tag>.json), fid = 1 (self)")
    ap.add_argument("--from-data", type=Path, default=None,
                    help="POD MODE: drive every replay of this dataset_gen npz from --crawl sources, recording exactly its "
                         "row ticks; no native corpus needed (cue_sidecar measures the fid on the dataset's tokens)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--tags", type=Path, default=None, help="optional JSON list of tags to drive")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--keep-recording", action="store_true", help="also write the full SIM recording (all-SIM rows)")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    files, seen = [], set()
    for c in a.corpus:
        for p in sorted(c.rglob("replay_*.json")):
            if p.name not in seen:                   # dataset_gen dedupes replay filenames the same way
                seen.add(p.name); files.append(p)
    if a.tags:
        want = set(json.loads(a.tags.read_text(encoding="utf-8")))
        files = [p for p in files if p.stem[len("replay_"):] in want]
    if a.limit:
        files = files[:a.limit]
    jobs = [(str(p), str(a.out), a.keep_recording, ()) for p in files]
    if a.from_data is not None:
        if files or a.crawl_only or not a.crawl:
            ap.error("--from-data takes --crawl dirs and no --corpus / --crawl-only")
        with np.load(a.from_data, allow_pickle=False) as z:
            dtags, rep, tick = [str(t) for t in z["tags"]], z["rep"], z["tick"]
        order = np.argsort(rep, kind="stable")
        cuts = np.flatnonzero(np.diff(rep[order])) + 1
        by_tag = {dtags[int(rep[ids[0]])]: sorted(set(tick[ids].tolist())) for ids in np.split(order, cuts) if len(ids)}
        if a.tags:
            want = set(json.loads(a.tags.read_text(encoding="utf-8")))
            by_tag = {t: v for t, v in by_tag.items() if t in want}
        jobs = [("data:" + t, str(a.out), a.keep_recording, tuple(v)) for t, v in list(by_tag.items())[:a.limit or None]]
    elif a.crawl_only:
        if len(a.crawl) != 1:
            ap.error("--crawl-only needs exactly one --crawl dir")
        with (Path(a.crawl[0]) / "battles.csv").open(encoding="utf-8", newline="") as f:
            ctags = [r["replay_tag"] for r in csv.DictReader(f)]
        if a.tags:
            ctags = [t for t in ctags if t in want]
        jobs += [("crawl:" + t, str(a.out), True, ()) for t in ctags[:a.limit or None]]
    elif not files:
        ap.error("no replay_*.json under --corpus")
    t0, n, log = time.monotonic(), 0, (a.out / "drive_log.jsonl").open("a", encoding="utf-8")
    if a.workers > 1:
        import multiprocessing as mp
        with mp.get_context("spawn").Pool(a.workers, initializer=_init, initargs=(a.crawl,)) as pool:
            it = pool.imap_unordered(_job, jobs, chunksize=4)
            for r in it:
                n += 1; log.write(json.dumps(r) + "\n"); log.flush()
                if n % 50 == 0:
                    print(f"{n}/{len(jobs)} {time.monotonic() - t0:.0f}s", flush=True)
    else:
        _init(a.crawl)
        for j in jobs:
            r = _job(j); n += 1
            log.write(json.dumps(r) + "\n"); log.flush()
            print(json.dumps({k: r.get(k) for k in ("tag", "source", "seconds", "frames", "fid_mean", "fid_ge_090", "failed")}),
                  flush=True)
    log.close()
    print(f"CUE_DRIVE_DONE {n} replays {time.monotonic() - t0:.0f}s runtime {_W.get('stamp', {}).get('runtime_id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
