"""L74 fastplays: the four factorial-eval arms of Mark CXXXVIII (fp_chain.sh) + the factorial's ref_cxxxviii.
    python analyze_eval.py [FP_DIR] [REF_DIR]
FP_DIR/<arm>/<arm>_{741200,742000}/D3/matches.jsonl (default C:/Users/benpe/pod_backup_weekend/pod1017_fastplays/fp);
REF_DIR = pod1017_factorial/ref_cxxxviii/eval (layout ref_cxxxviii_<seed>/D3/matches.jsonl).
Prints: identity of off vs the reference (every key but own_plays / wall_s); wins / 960 and paired deltas (heroiw/validate.
paired_drift: 10,000 bootstrap draws within census x side); habits; play cadence from own_plays [decision tick, landing tick, card,
accepted, elixir, cell, why] (sim_patch P1): pairs of consecutive accepted plays <= 24 decision ticks apart (pros' 5.8 % / Tornado
11.9 % of second cards, HANDOFF 10-09), their card pairs, and Rocket -> Tornado pairs within 80 ticks (rule vs model, gap, where)."""
import collections
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "heroiw"))
from validate import paired_drift  # noqa: E402

FP = Path(sys.argv[1] if len(sys.argv) > 1 else "C:/Users/benpe/pod_backup_weekend/pod1017_fastplays/fp")
REF = Path(sys.argv[2] if len(sys.argv) > 2 else "C:/Users/benpe/pod_backup_weekend/pod1017_factorial/ref_cxxxviii/eval")
ARMS = ("off", "on", "offc", "onc")
SEEDS = (741200, 742000)
GX, GY = 36, 64                                   # lattice grid (model_v3 GRID_X / GRID_Y)


def rows(d, name):
    out = []
    for s in SEEDS:
        p = d / f"{name}_{s}" / "D3" / "matches.jsonl"
        out += [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.is_file() else []
    return out


def slug(c):
    return "".join(ch for ch in str(c).split("@")[0].lower() if ch.isalpha()).replace("thelog", "log")


def xy(cell):
    return (cell % GX) * 18.0 / GX, (cell // GX) * 32.0 / GY       # lattice point, board tiles (me at the bottom)


def cadence(rs):
    n_pairs = 0
    second, pairs, rt = collections.Counter(), collections.Counter(), []
    n_plays = el = 0.0
    for r in rs:
        ps = sorted([p for p in r.get("own_plays", []) if p[3]], key=lambda p: p[0])
        n_plays += len(ps)
        el += sum(p[4] for p in ps)
        for a, b in zip(ps, ps[1:]):
            if b[0] - a[0] <= 24:
                n_pairs += 1
                second[slug(b[2])] += 1
                pairs[f"{slug(a[2])}>{slug(b[2])}"] += 1
        for i, a in enumerate(ps):
            if slug(a[2]) != "rocket":
                continue
            b = next((q for q in ps[i + 1:] if slug(q[2]) == "tornado" and q[1] - a[1] <= 80), None)   # landing ticks
            if b is not None:
                rt.append(dict(gap=b[1] - a[1],   # deploy gap (a follow-up records the first decision tick)
                               why=a[6] if len(a) > 6 else "?", ry=xy(a[5])[1] if len(a) > 5 else None,
                               same=len(a) > 5 and math.dist(xy(a[5]), xy(b[5])) <= 2.0))
    n = len(rs)
    return dict(plays=n_plays / n, elixir_at_play=el / max(n_plays, 1), pairs24_per_match=n_pairs / n,
                pair_share=n_pairs / max(n_plays, 1), tornado_second_share=second["tornado"] / max(n_pairs, 1),
                top_pairs=pairs.most_common(8), rt=rt)


def habits(rs):
    h = collections.Counter()
    for r in rs:
        x = r.get("habits") or {}
        h["early_xbow"] += bool(x.get("xbow_open_hand") and x.get("xbow_off_first2"))
        h["xbow_open"] += bool(x.get("xbow_open_hand"))
        for k in ("rocket", "rocket_princess", "rocket_lethal", "tornado", "xbow_off"):
            h[k] += x.get(k, 0)
        h["fu_fired"] += (r.get("follow_ups") or {}).get("fired", 0)
        h["second_plays"] += (r.get("pipeline_decisions") or {}).get("second_plays", 0)
    n = len(rs)
    return {"early_xbow_pct": 100 * h["early_xbow"] / max(h["xbow_open"], 1),
            "rockets": h["rocket"] / n, "unforced_princess_rockets": (h["rocket_princess"] - h["rocket_lethal"]) / n,
            "tornados": h["tornado"] / n, "off_xbows": h["xbow_off"] / n, "combo_fires": h["fu_fired"] / n,
            "pipelined_second_plays": h["second_plays"] / n}


def main():
    data = {a: rows(FP / a, a) for a in ARMS}
    data["ref"] = rows(REF, "ref_cxxxviii")
    for k, v in data.items():
        print(f"{k:5s} rows {len(v)}")
    ref = {(r["census"], r["seed"]): r for r in data["ref"]}
    same = sum({k: v for k, v in r.items() if k not in ("own_plays", "wall_s")} ==
               {k: v for k, v in ref.get((r["census"], r["seed"]), {}).items() if k != "wall_s"} for r in data["off"])
    print(f"identity off vs ref_cxxxviii: {same} / {len(data['off'])} rows identical (all keys but own_plays, wall_s)")
    print("\narm    wins/960  win%   habits")
    for a in ("ref",) + ARMS:
        rs = data[a]
        if not rs:
            continue
        w = sum(r["outcome"] == "win" for r in rs)
        print(f"{a:5s} {w:4d}/{len(rs)} {100 * w / len(rs):5.1f}  " +
              "  ".join(f"{k} {v:.2f}" for k, v in habits(rs).items()))
    print("\npaired deltas (new - old, pp, 95% CI)")
    for new, old in (("on", "off"), ("offc", "off"), ("onc", "offc"), ("onc", "off"), ("off", "ref")):
        if len(data[new]) == 960 and len(data[old]) == 960:
            d = paired_drift(data[old], data[new], expected=960)
            print(f"  {new:4s} - {old:4s}: {d['delta_pp']:+6.2f} [{d['ci95_pp'][0]:+.2f}, {d['ci95_pp'][1]:+.2f}]  "
                  f"({100 * d['old_win_rate']:.1f} -> {100 * d['new_win_rate']:.1f})")
    print("\ncadence (accepted plays; pairs = consecutive plays <= 24 decision ticks apart)")
    for a in ARMS:
        if not data[a]:
            continue
        c = cadence(data[a])
        rt = c.pop("rt")
        print(f"  {a:5s} plays {c['plays']:.1f}  elixir@play {c['elixir_at_play']:.2f}  pairs/match {c['pairs24_per_match']:.2f}  "
              f"pair share {100 * c['pair_share']:.1f}%  Tornado share of 2nd cards {100 * c['tornado_second_share']:.1f}%")
        print(f"        top pairs {c['top_pairs']}")
        by = collections.Counter(x["why"] for x in rt)
        gaps = sorted(x["gap"] for x in rt)
        far = [x for x in rt if x["ry"] is not None and x["ry"] < 12]
        print(f"        Rocket -> Tornado within 80 ticks: {len(rt)} ({len(rt) / len(data[a]):.3f}/match) by Rocket why {dict(by)}; "
              f"same spot (<= 2 t) {sum(x['same'] for x in rt)}; gap median {gaps[len(gaps) // 2] if gaps else None} "
              f"q10-q90 {gaps[len(gaps) // 10] if gaps else None}-{gaps[9 * len(gaps) // 10] if gaps else None}; "
              f"Rocket on the enemy back (y < 12) {len(far)}, gaps {sorted(x['gap'] for x in far)[:20]}")


if __name__ == "__main__":
    main()
