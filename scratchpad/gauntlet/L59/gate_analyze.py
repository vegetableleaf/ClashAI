"""L59 gate rerun analysis: reads p1/gate_plays.csv + p1/gate_tesla_probe.csv, prints the brief's numbers."""
import csv, statistics as st, sys
from collections import Counter
from pathlib import Path
D = Path(sys.argv[1] if len(sys.argv) > 1 else "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L59/p1")
plays = list(csv.DictReader((D / "gate_plays.csv").open(encoding="utf-8")))
probe = list(csv.DictReader((D / "gate_tesla_probe.csv").open(encoding="utf-8")))
f = float


def frac(xs):
    return f"{sum(xs)/len(xs):.3f}" if xs else "n/a"


print(f"# L59 gate rerun: {len(plays)} scored building plays, {len(probe)} gate-probe boards")
for side, label in ((1, "BLUE (icebow player)"), (0, "RED")):
    for card in ("tesla", "x-bow"):
        rows = [r for r in plays if r["card"] == card and int(r["side"]) == side]
        if not rows:
            continue
        n = len(rows)
        print(f"\n## {label} {card}: n={n}, threat present {sum(1 for r in rows if r['threat'])}/{n}")
        for mode in ("pc", "ra"):
            for k in ("p1_pull_band", "p1_snapshot", "p1_close_penalty", "p1_close_snapshot", "p2_cover", "p5_timing", "p6_siege"):
                pro = [f(r[f"{mode}_pro_{k}"]) for r in rows]
                lock = [f(r[f"{mode}_lock_{k}"]) for r in rows]
                gt = sum(1 for a, b in zip(pro, lock) if a > b + 1e-9); lt = sum(1 for a, b in zip(pro, lock) if a < b - 1e-9)
                nz = [v for v in pro if abs(v) > 1e-9]
                print(f"  {mode} {k:18s} pro>0 {len(nz)/n:.3f} (n={len(nz)}, mean when fires {st.mean(nz) if nz else 0:.3f}) "
                      f"mean_pro {st.mean(pro):.3f} mean_lock {st.mean(lock):.3f} | pro>lock {gt/n:.3f} tie {(n-gt-lt)/n:.3f} pro<lock {lt/n:.3f}")
            pc_p = [f(r[f"{mode}_pro_pcred"]) for r in rows]; pc_l = [f(r[f"{mode}_lock_pcred"]) for r in rows]
            gt = sum(1 for a, b in zip(pc_p, pc_l) if a > b + 1e-9); lt = sum(1 for a, b in zip(pc_p, pc_l) if a < b - 1e-9)
            ranks = [int(r[f"{mode}_rank_pcred"]) for r in rows]
            print(f"  {mode} placement_credit   pro>lock {gt/n:.3f} tie {(n-gt-lt)/n:.3f} pro<lock {lt/n:.3f} | mean pro {st.mean(pc_p):.3f} "
                  f"lock {st.mean(pc_l):.3f} | median rank {st.median(ranks)} of {int(rows[0]['n_cands'])+1} | rank1 {sum(1 for x in ranks if x==1)/n:.3f} "
                  f"| min {min(pc_p):.3f} max {max(pc_p):.3f}")
            tc_p = [f(r[f"{mode}_pro_tcred"]) for r in rows]
            print(f"  {mode} timing_credit      mean pro {st.mean(tc_p):.3f} >0 {sum(1 for v in tc_p if v>0)/n:.3f}")
        # snapshot vs path P1 firing (pc)
        both = sum(1 for r in rows if f(r["pc_pro_p1_pull_band"]) > 0 and f(r["pc_pro_p1_snapshot"]) > 0)
        path_only = sum(1 for r in rows if f(r["pc_pro_p1_pull_band"]) > 0 and f(r["pc_pro_p1_snapshot"]) <= 0)
        snap_only = sum(1 for r in rows if f(r["pc_pro_p1_pull_band"]) <= 0 and f(r["pc_pro_p1_snapshot"]) > 0)
        print(f"  pc P1 fires: both {both} path-only {path_only} snapshot-only {snap_only} neither {n-both-path_only-snap_only} (n={n})")
        cp = sum(1 for r in rows if f(r["pc_pro_p1_close_penalty"]) < 0); cs = sum(1 for r in rows if f(r["pc_pro_p1_close_snapshot"]) < 0)
        print(f"  pc close penalty fires on the PRO tile: d_path form {cp}/{n} = {cp/n:.3f} (mean {st.mean([f(r['pc_pro_p1_close_penalty']) for r in rows if f(r['pc_pro_p1_close_penalty'])<0] or [0]):.3f}); "
              f"snapshot form {cs}/{n} = {cs/n:.3f}")
        # pro tiles
        if card == "tesla" and side == 1:
            tiles = Counter((round(f(r["pro_tx"])), round(f(r["pro_ty"]))) for r in rows)
            print("  pro tiles (rounded):", tiles.most_common(6))
            for tile in ((9, 21), (9, 19), (9, 22), (9, 18)):
                rr = [r for r in rows if (round(f(r["pro_tx"])), round(f(r["pro_ty"]))) == tile]
                if rr:
                    print(f"   tile {tile} n={len(rr)}: path P1 mean {st.mean(f(r['pc_pro_p1_pull_band']) for r in rr):.3f} "
                          f"(>0 {sum(1 for r in rr if f(r['pc_pro_p1_pull_band'])>0)/len(rr):.3f}), snapshot mean {st.mean(f(r['pc_pro_p1_snapshot']) for r in rr):.3f} "
                          f"(>0 {sum(1 for r in rr if f(r['pc_pro_p1_snapshot'])>0)/len(rr):.3f}); pcred pro {st.mean(f(r['pc_pro_pcred']) for r in rr):.3f} "
                          f"vs corner {st.mean(f(r['pc_lock_pcred']) for r in rr):.3f}; close d_path fires {sum(1 for r in rr if f(r['pc_pro_p1_close_penalty'])<0)}")

print(f"\n## doc s3 GATE RULE: modal (9,21) vs corner (1.5,18.5) Tesla on Hog/Giant/PEKKA boards, n={len(probe)}")
thr = Counter(r["threat_m"] for r in probe)
print("  threats:", dict(thr))
for k in ("p1_pull_band", "p1_snapshot", "p1_close_penalty", "p1_close_snapshot", "p2_cover", "p5_timing", "sum", "pcred"):
    d = [f(r[f"modal_{k}"]) - f(r[f"corner_{k}"]) for r in probe]
    gt = sum(1 for v in d if v > 1e-9); lt = sum(1 for v in d if v < -1e-9)
    m = [f(r[f"modal_{k}"]) for r in probe]; c = [f(r[f"corner_{k}"]) for r in probe]
    act = [v for v, a, b in zip(d, m, c) if abs(a) > 1e-9 or abs(b) > 1e-9]
    agt = sum(1 for v in act if v > 1e-9); alt = sum(1 for v in act if v < -1e-9)
    print(f"  {k:18s} median diff {st.median(d):+.3f} mean modal {st.mean(m):.3f} mean corner {st.mean(c):.3f} "
          f"modal>corner {gt/len(d):.3f} modal<corner {lt/len(d):.3f} | ACTIVE n={len(act)} median {st.median(act) if act else 0:+.3f} > {agt/len(act) if act else 0:.3f} < {alt/len(act) if act else 0:.3f}")
    if k == "p1_pull_band":
        for t in ("hog_rider", "giant", "pekka"):
            dd = [f(r["modal_p1_pull_band"]) - f(r["corner_p1_pull_band"]) for r in probe if r["threat_m"] == t]
            if dd:
                print(f"     {t}: n={len(dd)} median {st.median(dd):+.3f} > {sum(1 for v in dd if v>1e-9)/len(dd):.3f} < {sum(1 for v in dd if v<-1e-9)/len(dd):.3f}")
