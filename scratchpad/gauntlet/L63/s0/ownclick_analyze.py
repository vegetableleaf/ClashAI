"""Recompute the click-vs-detection matching OFFLINE from the saved per-frame detections (ownclick_<proj>_<sess>.json,
written by ownclick_run.py) and aggregate -> ownclick.json + a markdown block on stdout. No GPU.

Modes (all: candidate within FOUND_R tiles of the warped click, in any window frame; error at FIRST sighting):
  strict        same BASE class as the hand card, side mine/unknown          (the task's strict number)
  strict_any    same BASE class, ANY side (isolates the colour-vote team error)
  deck          any deck base class, side mine/unknown                       (the task's fallback number)
  anynew        ANY class, ANY side, not pre-existing (no detection of any class within NEW_R tiles of the candidate in the
                pre-click frame) -- the class-agnostic POSITION measurement
"""
from __future__ import annotations

import bisect
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(r"C:\Users\benpe\ClashBot")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "icebow" / "src"))
from pipeline import obs_contract as oc  # noqa: E402
from pipeline import vocab               # noqa: E402

D = REPO / "scratchpad" / "gauntlet" / "L63" / "s0"
FILES = {
    "icebow/20260804_173304": ("icebow", D / "ownclick_icebow_173304.json"),
    "icebow/20260804_192006": ("icebow", D / "ownclick_icebow_192006.json"),
    "icebow/20260815_222309": ("icebow", D / "ownclick_icebow_222309.json"),
    "hogeq/20260817_194419": ("hogeq", D / "ownclick_hogeq_194419.json"),
}
FOUND_R, NEW_R, T_PRE = 3.0, 1.0, 0.10
MODES = ("strict", "strict_any", "deck", "anynew")


def pct(a, q):
    a = np.asarray([v for v in a if v is not None], dtype=float)
    return None if a.size == 0 else float(np.percentile(a, q))


def mp(a):
    a = [v for v in a if v is not None]
    return {"n": len(a), "median": pct(a, 50), "p90": pct(a, 90), "mean": (float(np.mean(a)) if a else None)}


def rematch(data, project):
    deck = oc.load_deck(project)
    warp = oc.board_warp(deck)
    deck_bases = {vocab.base_key(c) for c in deck.cards}
    meta = json.loads((Path(data["session"]) / "meta.json").read_text(encoding="utf-8"))
    ft = meta["frame_times"]
    by_fi: dict[int, list] = {}
    for d in data["all_dets"]:
        by_fi.setdefault(d["fi"], []).append(d)
    # board coords for every detection ONCE (the contract's own transform: frame_to_board(cx, gy))
    for ds in by_fi.values():
        for d in ds:
            d["bx"], d["by"] = warp.frame_to_board(float(d["cx"]), float(d["gy"]))
            d["base"] = vocab.base_key(d["cls"])
            d["kind"] = vocab.kind_of(vocab.unit_id(d["cls"]))
    rows = []
    for p in data["plays"]:
        if "skip" in p:
            continue
        tc = p["t_click"]
        cbx, cby = p["click_board"]
        card_base = p["card_base"]
        fpre = min(max(bisect.bisect_right(ft, tc - T_PRE) - 1, 0), len(ft) - 1)
        pre = by_fi.get(fpre, [])
        r = {"session": data["session"].split("\\")[-1], "project": project, "k": p["k"], "t_click": tc,
             "card_key": p["card_key"], "card_base": card_base, "card_kind": p.get("card_kind"),
             "click_frame": [p["nx"], p["ny"]], "click_board": [cbx, cby],
             "clamped": (cby >= 0.999 or cby <= 0.001 or cbx >= 0.999 or cbx <= 0.001)}
        # pre-existing same-class unit near the click (any side)
        r["pre_same_within_1.5"] = any(d["base"] == card_base and
                                       np.hypot((d["bx"] - cbx) * oc.TILES_X, (d["by"] - cby) * oc.TILES_Y) <= 1.5 for d in pre)
        # same class tagged ENEMY within R in the window?  (team error diagnostic)
        for mode in MODES:
            first, best, hits = None, None, []
            for fr in p["frames"]:
                cands = []
                for d in by_fi.get(fr["fi"], []):
                    if mode == "strict":
                        ok = card_base is not None and d["base"] == card_base and d["team"] != "enemy"
                    elif mode == "strict_any":
                        ok = card_base is not None and d["base"] == card_base
                    elif mode == "deck":
                        ok = d["base"] in deck_bases and d["team"] != "enemy"
                    else:
                        ok = not any(np.hypot((d["bx"] - q["bx"]) * oc.TILES_X, (d["by"] - q["by"]) * oc.TILES_Y) <= NEW_R for q in pre)
                    if not ok:
                        continue
                    ex, ey = (d["bx"] - cbx) * oc.TILES_X, (d["by"] - cby) * oc.TILES_Y
                    cands.append((float(np.hypot(ex, ey)), ex, ey, d))
                if not cands:
                    continue
                dist, ex, ey, d = min(cands, key=lambda c: c[0])
                rec = {"d": dist, "ex": ex, "ey": ey, "dt": fr["dt"], "cls": d["cls"], "team": d["team"], "conf": d["conf"],
                       "kind": d["kind"], "h_frame": d["h"], "sprite_half_h_tiles": (d["cy"] - (d["cy"] - d["h"] / 2))}
                if best is None or dist < best["d"]:
                    best = rec
                if dist <= FOUND_R:
                    hits.append(rec)
                    if first is None:
                        first = rec
            r[mode] = {"found": first is not None, "first": first, "nearest_any": (best["d"] if best else None),
                       "n_hit_frames": len(hits),
                       "win_med_ex": (float(np.median([h["ex"] for h in hits])) if hits else None),
                       "win_med_ey": (float(np.median([h["ey"] for h in hits])) if hits else None)}
        rows.append(r)
    return rows, by_fi


def block(rows, mode):
    f = [r for r in rows if r[mode]["found"]]
    ex = [r[mode]["first"]["ex"] for r in f]
    ey = [r[mode]["first"]["ey"] for r in f]
    return {"n_plays": len(rows), "n_found": len(f), "recall": (len(f) / len(rows) if rows else None),
            "abs_x_tiles": mp([abs(v) for v in ex]), "abs_y_tiles": mp([abs(v) for v in ey]),
            "signed_x_tiles": mp(ex), "signed_y_tiles": mp(ey),
            "frac_y_negative_above_click": (float(np.mean([v < 0 for v in ey])) if ey else None),
            "window_median_signed_y_tiles": mp([r[mode]["win_med_ey"] for r in f]),
            "first_dt_s": mp([r[mode]["first"]["dt"] for r in f]),
            "team_at_first": {t: sum(1 for r in f if r[mode]["first"]["team"] == t) for t in ("mine", "enemy", "unknown")},
            "conf_at_first": mp([r[mode]["first"]["conf"] for r in f]),
            "nearest_when_not_found": mp([r[mode]["nearest_any"] for r in rows if not r[mode]["found"]]),
            "n_not_found_no_candidate": sum(1 for r in rows if not r[mode]["found"] and r[mode]["nearest_any"] is None)}


def det_stats(dets):
    conf = [d["conf"] for d in dets]
    n = len(dets)
    out = {"n_dets": n, "conf_p10": pct(conf, 10), "conf_p50": pct(conf, 50), "conf_p90": pct(conf, 90),
           "conf_min": (min(conf) if conf else None),
           "frac_conf_lt_0.5": (float(np.mean([c < 0.5 for c in conf])) if conf else None),
           "team_frac": {t: (sum(1 for d in dets if d["team"] == t) / n if n else None) for t in ("mine", "enemy", "unknown")},
           "by_kind": {}}
    for k in ("troop", "building", "spell"):
        sub = [d for d in dets if d["kind"] == k]
        out["by_kind"][k] = {"n": len(sub),
                             "unknown_frac": (float(np.mean([d["team"] == "unknown" for d in sub])) if sub else None),
                             "conf_p10": pct([d["conf"] for d in sub], 10), "conf_p50": pct([d["conf"] for d in sub], 50),
                             "conf_p90": pct([d["conf"] for d in sub], 90)}
    return out


def f2(m):
    return "--" if not m or m["median"] is None else f'{m["median"]:+.2f}/{m["p90"]:+.2f}'


def fmt(b):
    if b["n_plays"] == 0:
        return "n=0"
    t = b["team_at_first"]
    return (f'n={b["n_plays"]} found={b["n_found"]} R={b["recall"]:.2f} | |x| {f2(b["abs_x_tiles"])} |y| {f2(b["abs_y_tiles"])} '
            f'| sy {f2(b["signed_y_tiles"])} (above {b["frac_y_negative_above_click"] if b["frac_y_negative_above_click"] is None else round(b["frac_y_negative_above_click"], 2)}) '
            f'sx {f2(b["signed_x_tiles"])} | winmed sy {f2(b["window_median_signed_y_tiles"])} | dt {f2(b["first_dt_s"])} '
            f'| team m/e/u {t["mine"]}/{t["enemy"]}/{t["unknown"]} | conf {f2(b["conf_at_first"])} '
            f'| miss: nearest {f2(b["nearest_when_not_found"])} none={b["n_not_found_no_candidate"]}')


def subsets(rows):
    good = [r for r in rows if not r["clamped"]]
    s = {"all": rows, "unclamped": good, "clamped": [r for r in rows if r["clamped"]],
         "troop": [r for r in good if r["card_kind"] == "troop"],
         "building": [r for r in good if r["card_kind"] == "building"],
         "spell": [r for r in good if r["card_kind"] == "spell"],
         "depth_back(y>=0.8)": [r for r in good if r["click_board"][1] >= 0.8],
         "depth_mid(0.6-0.8)": [r for r in good if 0.6 <= r["click_board"][1] < 0.8],
         "depth_front(0.5-0.6)": [r for r in good if 0.5 <= r["click_board"][1] < 0.6],
         "enemy_half(y<0.5)": [r for r in good if r["click_board"][1] < 0.5],
         "pre_same_within_1.5": [r for r in good if r["pre_same_within_1.5"]]}
    return s


def main():
    per, all_rows, all_dets = {}, [], []
    for name, (project, f) in FILES.items():
        if not f.exists():
            print("MISSING", f)
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        rows, by_fi = rematch(data, project)
        dets = [d for ds in by_fi.values() for d in ds]
        ident = [r for r in rows if r["card_base"]]
        per[name] = {"n_events": data["n_events"], "n_plays": data["n_plays"], "n_no_click": data["n_plays_no_click_event"],
                     "n_card_identified": len(ident), "n_frames": data["n_frames_detected"], "region": data["region"],
                     "cards": {}, "modes": {}, "detector": det_stats(dets)}
        for r in ident:
            per[name]["cards"][r["card_key"]] = per[name]["cards"].get(r["card_key"], 0) + 1
        for sub_name, sub in subsets(ident).items():
            per[name]["modes"][sub_name] = {m: block(sub, m) for m in MODES}
        per[name]["modes"]["all_plays_incl_unidentified"] = {"anynew": block([r for r in rows if not r["clamped"]], "anynew")}
        all_rows += rows
        all_dets += dets
    ident = [r for r in all_rows if r["card_base"]]
    pooled = {"n_plays": len(all_rows), "n_card_identified": len(ident), "cards": {}, "modes": {},
              "detector": det_stats(all_dets), "per_card": {}}
    for r in ident:
        pooled["cards"][r["card_key"]] = pooled["cards"].get(r["card_key"], 0) + 1
    for sub_name, sub in subsets(ident).items():
        pooled["modes"][sub_name] = {m: block(sub, m) for m in MODES}
    pooled["modes"]["all_plays_incl_unidentified"] = {"anynew": block([r for r in all_rows if not r["clamped"]], "anynew")}
    good = [r for r in ident if not r["clamped"]]
    for c in sorted(pooled["cards"]):
        pooled["per_card"][c] = {m: block([r for r in good if r["card_key"] == c], m) for m in ("strict", "strict_any", "anynew")}
    # what did the detector CALL the placed unit when strict missed but anynew hit?
    confusion = {}
    for r in good:
        if not r["strict"]["found"] and r["anynew"]["found"]:
            key = f'{r["card_base"]} -> {vocab.base_key(r["anynew"]["first"]["cls"])} ({r["anynew"]["first"]["team"]})'
            confusion[key] = confusion.get(key, 0) + 1
    pooled["strict_miss_named_as"] = dict(sorted(confusion.items(), key=lambda kv: -kv[1]))
    # sprite-height proxy: box height (frame frac) -> tiles at the click depth (b: crude; 1 frame-y unit ~ 32/(0.762-0.129) tiles)
    out = {"found_r_tiles": FOUND_R, "new_r_tiles": NEW_R, "window_s": [0.25, 1.5], "det_conf": 0.35,
           "labels": "all (a) measured unless noted", "per_session": per, "pooled": pooled,
           "plays": [{k: v for k, v in r.items()} for r in all_rows]}
    (D / "ownclick.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")

    L = []
    for name, res in per.items():
        L.append(f"### {name}  (region {res['region']})")
        L.append(f"- events {res['n_events']}, plays {res['n_plays']} (no click event {res['n_no_click']}), card identified "
                 f"{res['n_card_identified']}, detector frames {res['n_frames']}, detections {res['detector']['n_dets']}")
        L.append(f"- cards: {res['cards']}")
        for sub in ("unclamped", "clamped"):
            for m in MODES:
                L.append(f"- {sub:9s} {m:10s}: {fmt(res['modes'][sub][m])}")
        for sub in ("troop", "building", "spell"):
            L.append(f"- {sub:9s} strict    : {fmt(res['modes'][sub]['strict'])}")
            L.append(f"- {sub:9s} anynew    : {fmt(res['modes'][sub]['anynew'])}")
        d = res["detector"]
        L.append(f"- detector: n={d['n_dets']} conf p10/p50/p90 {d['conf_p10']:.3f}/{d['conf_p50']:.3f}/{d['conf_p90']:.3f} "
                 f"(min {d['conf_min']:.3f}, frac<0.5 {d['frac_conf_lt_0.5']:.3f}); team m/e/u "
                 f"{d['team_frac']['mine']:.3f}/{d['team_frac']['enemy']:.3f}/{d['team_frac']['unknown']:.3f}; "
                 + "; ".join(f"{k}: n={v['n']} unk={None if v['unknown_frac'] is None else round(v['unknown_frac'], 3)} "
                             f"conf p10/50/90 {v['conf_p10']}/{v['conf_p50']}/{v['conf_p90']}"
                             for k, v in d["by_kind"].items()).replace("None", "--"))
    L.append("### POOLED")
    L.append(f"- plays {pooled['n_plays']}, card identified {pooled['n_card_identified']}; cards {pooled['cards']}")
    for sub, mb in pooled["modes"].items():
        for m, b in mb.items():
            L.append(f"- {sub:24s} {m:10s}: {fmt(b)}")
    L.append("- per card (unclamped):")
    for c, mb in pooled["per_card"].items():
        L.append(f"  - {c}: strict {fmt(mb['strict'])}")
        L.append(f"    {' ' * len(c)}  anynew {fmt(mb['anynew'])}")
    L.append(f"- strict miss but anynew hit, named as: {pooled['strict_miss_named_as']}")
    d = pooled["detector"]
    L.append(f"- detector pooled: n={d['n_dets']} conf p10/p50/p90 {d['conf_p10']:.3f}/{d['conf_p50']:.3f}/{d['conf_p90']:.3f} "
             f"(min {d['conf_min']:.3f}, frac<0.5 {d['frac_conf_lt_0.5']:.3f}); team m/e/u "
             f"{d['team_frac']['mine']:.3f}/{d['team_frac']['enemy']:.3f}/{d['team_frac']['unknown']:.3f}; "
             + "; ".join(f"{k}: n={v['n']} unk={round(v['unknown_frac'], 3)} conf p10/50/90 {v['conf_p10']:.2f}/{v['conf_p50']:.2f}/{v['conf_p90']:.2f}"
                         for k, v in d["by_kind"].items() if v["n"]))
    print("\n".join(L))


if __name__ == "__main__":
    main()
