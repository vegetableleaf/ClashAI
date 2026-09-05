"""L58 gate, Part 1: pro replays through the sim, scoring the PRO tile vs the policy's candidate tiles with
geometry_reward IMMEDIATELY BEFORE each accepted deploy. The L51 driver is imported (not edited); `drive()` is
re-implemented here with the scoring hook (same engine, conversion, slack, tail cap).

    PYTHONHASHSEED=0 ./.venv/Scripts/python.exe ../scratchpad/gauntlet/L58/gate_replay.py --out ../scratchpad/gauntlet/L58/p1 --limit 20
"""
import argparse, csv, json, sys, time, importlib.util
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
ICEBOW = ROOT / "icebow"
sys.path.insert(0, str(ICEBOW / "src"))
_spec = importlib.util.spec_from_file_location("sim_replay_drive", ROOT / "scratchpad/gauntlet/L51/sim_replay_drive.py")
L51 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(L51)
from clashrl.config import Config                       # noqa: E402
from clashrl.cards import shared as shared_db           # noqa: E402
from clashrl import geometry_reward as GR               # noqa: E402

TICK_S = L51.TICK_S
RELEVANT = {"tesla", "x-bow", "skeletons", "knight", "ice-wizard", "tornado", "the-log", "rocket"}
# policy landing tiles (team-0 frame, tile units; HANDOFF 5cs.27) + the pros' modal tiles + a 3x4 grid over the own half
CANDS = [("corner", 1.5, 18.5), ("lane", 4.5, 20.5), ("centre", 8.5, 23.5), ("tesla_modal", 9.0, 21.0),
         ("bow_modal_L", 2.0, 19.0), ("bow_modal_R", 15.0, 19.0), ("skel_cell", 9.3, 24.1), ("knight_cell", 11.8, 24.1),
         ("corner_R", 16.5, 18.5), ("lane_R", 13.5, 20.5),
         # the env's TRUE landing tiles for the L56 cells (env.actions.cell_center, grid 18x24, measured in gate.md 2):
         # cell 235 -> (1.5,18.0), 423 -> (9.5,31.33), 426 -> (12.5,31.33); the brief's (9.3,24.1)/(11.8,24.1) were mis-converted
         ("tesla_true", 1.5, 18.0), ("skel_true", 9.5, 31.33), ("knight_true", 12.5, 31.33), ("knight_obs", 12.5, 30.0)]
for gx in (3.0, 9.0, 15.0):
    for gy in (18.0, 22.0, 26.0, 30.0):
        CANDS.append((f"g{int(gx)}_{int(gy)}", gx, gy))
LOCKED = {"skeletons": "skel_true", "knight": "knight_true"}     # everything else: corner (1.5,18.5) ~ cell 235 (1.5,18.0)
GRADED = ("p1_pull_band", "p1_close_penalty", "p2_cover", "p3_intercept", "p4_spell_frac", "p4_nado",
          "p4_king_activation", "p5_timing", "p6_siege", "p7_fragility")
GATE_THREATS = {"hog_rider", "giant", "pekka"}


def to_norm(side, tx, ty):
    x, y = tx / 18.0, ty / 32.0
    return (x, y) if side == 0 else (1.0 - x, 1.0 - y)


def to_own_tiles(side, x, y):
    return (x * 18.0, y * 32.0) if side == 0 else ((1.0 - x) * 18.0, (1.0 - y) * 32.0)


def role_board(board, db):
    """Same board with every ENEMY troop/building's radii replaced by its role average (doc 7.1/7.8)."""
    objs = []
    for o in board.objs:
        if o.team != board.team and o.kind in ("troop", "building"):
            try:
                ra, rs = GR.role_average_radii(o.base, db)
            except Exception:
                ra, rs = o.r_atk, o.r_sight
            o = GR.BoardObj(**{**o.__dict__, "r_atk": ra, "r_sight": rs})
        objs.append(o)
    return GR.Board(objs=objs, team=board.team, t=board.t, tiles=board.tiles, river_y=board.river_y,
                    bridges_x=board.bridges_x, tower_range=board.tower_range, king_range=board.king_range,
                    river_half=board.river_half)


def gsum(sc):
    return sum(float(sc[k]) for k in GRADED)


def rank_of(v, others):
    """1 + number of candidates STRICTLY better (ties share the best rank)."""
    return 1 + sum(1 for o in others if o > v + 1e-9)


def score_all(board, spec, side, px, py, eng):
    kw = dict(siege_sight=eng.siege_sight, tower_range=eng.tower_range, king_range=eng.king_range)
    pro = GR.score_placement(board, GR.placement_from_spec(spec, px, py, **kw))
    cands = {}
    for name, tx, ty in CANDS:
        cx, cy = to_norm(side, tx, ty)
        cands[name] = GR.score_placement(board, GR.placement_from_spec(spec, cx, cy, **kw))
    return pro, cands


def drive_scored(tag, battle, plays, cfg, db, level, elixir_slack_ticks, tail_cap_s, sub_dt, tesla_spec, rows, gate_rows):
    eng = L51.make_engine(cfg, db, level, seed=424242)
    specs = {}
    for side in (0, 1):
        specs[side] = {}
        for tok in battle[L51.DECK_COL_OF_SIDE[side]].split(","):
            tok = tok.strip()
            specs[side][tok.replace("-ev1", "").replace("-hero", "")] = L51.build_spec(db, L51.key_of(tok), level)
    pending = []
    queue = list(plays)
    accepted = rejected = scored = 0
    while not eng.done and eng.t < tail_cap_s:
        while queue and queue[0]["tick"] * TICK_S <= eng.t + 1e-9:
            row = queue.pop(0)
            if row["ability"]:
                continue
            pending.append([row, 0])
        still = []
        for item in pending:
            row, waited = item
            slug = row["attr_card"].strip()
            spec = specs[row["side"]].get(slug) or specs[row["side"]].setdefault(slug, L51.build_spec(db, L51.key_of(slug), level))
            x = row["x"] / 18000.0
            y = 1.0 - row["y"] / 32000.0
            if eng.can_afford(row["side"], spec):
                side = row["side"]
                rec = None
                if slug in RELEVANT:
                    board = GR.board_from_engine(eng, side)          # BEFORE the deploy
                    board_ra = role_board(board, db)
                    pro_pc, c_pc = score_all(board, spec, side, x, y, eng)
                    pro_ra, c_ra = score_all(board_ra, spec, side, x, y, eng)
                    otx, oty = to_own_tiles(side, x, y)
                    rec = {"tag": tag, "tick": row["tick"], "sim_t": round(eng.t, 2), "side": side, "card": slug,
                           "base": spec.base, "kind": spec.kind, "pro_tx": round(otx, 2), "pro_ty": round(oty, 2),
                           "threat": pro_pc["threat_base"], "d_threat": round(float(pro_pc["d_threat"]), 2),
                           "threat_ra": pro_ra["threat_base"],
                           "n_enemy_troops": sum(1 for o in board.enemy() if o.kind == "troop"),
                           "bb_detected": pro_pc["bridge_block_detected"], "bb_case": pro_pc["bridge_block_case"],
                           "n_cands": len(CANDS)}
                    locked = LOCKED.get(slug, "corner")
                    for mode, pro, cands in (("pc", pro_pc, c_pc), ("ra", pro_ra, c_ra)):
                        for k in GRADED:
                            rec[f"{mode}_pro_{k}"] = round(float(pro[k]), 4)
                            rec[f"{mode}_lock_{k}"] = round(float(cands[locked][k]), 4)
                            rec[f"{mode}_rank_{k}"] = rank_of(float(pro[k]), [float(c[k]) for c in cands.values()])
                            rec[f"{mode}_ntie_{k}"] = sum(1 for c in cands.values() if abs(float(c[k]) - float(pro[k])) < 1e-9)
                        sp, sl = gsum(pro), gsum(cands[locked])
                        rec[f"{mode}_pro_sum"] = round(sp, 4); rec[f"{mode}_lock_sum"] = round(sl, 4)
                        rec[f"{mode}_rank_sum"] = rank_of(sp, [gsum(c) for c in cands.values()])
                        rec[f"{mode}_ntie_sum"] = sum(1 for c in cands.values() if abs(gsum(c) - sp) < 1e-9)
                        rec[f"{mode}_best_cand"] = max(cands, key=lambda n: gsum(cands[n]))
                    # gate rule probe: a Tesla at the pros' modal tile vs the corner tile on THIS board (per-card radii)
                    kw = dict(siege_sight=eng.siege_sight, tower_range=eng.tower_range, king_range=eng.king_range)
                    mx, my = to_norm(side, 9.0, 21.0); cx, cy = to_norm(side, 1.5, 18.5)
                    tm = GR.score_placement(board, GR.placement_from_spec(tesla_spec, mx, my, **kw))
                    tc = GR.score_placement(board, GR.placement_from_spec(tesla_spec, cx, cy, **kw))
                    if tm["threat_base"] in GATE_THREATS or tc["threat_base"] in GATE_THREATS:
                        g = {"tag": tag, "tick": row["tick"], "side": side, "threat_m": tm["threat_base"], "threat_c": tc["threat_base"],
                             "own_side_threat": 0}
                        thr = GR.pick_threat(board, GR.placement_from_spec(tesla_spec, mx, my, **kw))
                        if thr is not None:
                            g["own_side_threat"] = int(board.own_side(thr.y))
                            ttx, tty = to_own_tiles(side, thr.x, thr.y)
                            g["threat_tx"], g["threat_ty"] = round(ttx, 1), round(tty, 1)
                        for k in GRADED:
                            g[f"modal_{k}"] = round(float(tm[k]), 4); g[f"corner_{k}"] = round(float(tc[k]), 4)
                        g["modal_sum"] = round(gsum(tm), 4); g["corner_sum"] = round(gsum(tc), 4)
                        gate_rows.append(g)
                ok = eng.deploy(side, spec, x, y)
                if ok:
                    accepted += 1
                    if rec is not None:
                        rows.append(rec); scored += 1
                else:
                    rejected += 1
            elif waited >= elixir_slack_ticks:
                rejected += 1
            else:
                item[1] = waited + max(1, int(round(sub_dt / TICK_S)))
                still.append(item)
        pending = still
        eng.advance(sub_dt)
    return {"tag": tag, "accepted": accepted, "rejected": rejected, "scored": scored, "t": round(eng.t, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--level", type=int, default=11)
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    tags = sorted(p.stem.replace("replay_", "") for p in (ROOT / "scratchpad/gauntlet/ext/batch").glob("replay_*.json"))
    if args.limit:
        tags = tags[: args.limit]
    cfg = Config.load(ICEBOW / "config" / "config.yaml")
    cfg.data["sim"]["my_tower_troop"] = "princess"
    sub_dt = float(cfg.get("sim", "sub_dt", default=0.1))
    db = shared_db(cfg)
    battles, plays = L51.load_crawl(set(tags))
    tesla_spec = L51.build_spec(db, "tesla", args.level)
    rows, gate_rows, lines = [], [], []
    t0 = time.time()
    for i, tag in enumerate(tags):
        try:
            res = drive_scored(tag, battles[tag], plays[tag], cfg, db, args.level, 40, 360.0, sub_dt, tesla_spec, rows, gate_rows)
        except Exception as e:
            res = {"tag": tag, "error": repr(e)[:300]}
        lines.append(res)
        if (i + 1) % 10 == 0 or i + 1 == len(tags):
            print(f"[{i+1}/{len(tags)}] plays_scored={len(rows)} gate_rows={len(gate_rows)} {time.time()-t0:.0f}s", flush=True)
    (out / "drive_summary.jsonl").write_text("\n".join(json.dumps(l) for l in lines) + "\n")
    for name, data in (("gate_plays.csv", rows), ("gate_tesla_probe.csv", gate_rows)):
        if data:
            keys = list(data[0].keys())
            for r in data:
                for k in r:
                    if k not in keys:
                        keys.append(k)
            with (out / name).open("w", newline="", encoding="utf-8") as h:
                w = csv.DictWriter(h, fieldnames=keys); w.writeheader(); w.writerows(data)
    print("done", len(rows), "plays;", len(gate_rows), "gate rows;", f"{time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
