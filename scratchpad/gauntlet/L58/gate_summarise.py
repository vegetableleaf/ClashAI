"""L58 gate, Part 1 summary: gate_plays.csv + gate_tesla_probe.csv -> gate_summary.txt (stdlib + numpy only)."""
import csv, sys, collections
import numpy as np
from pathlib import Path

D = Path(sys.argv[1])
rows = list(csv.DictReader((D / "gate_plays.csv").open(encoding="utf-8")))
GRADED = ("p1_pull_band", "p1_close_penalty", "p2_cover", "p3_intercept", "p4_spell_frac", "p4_nado",
          "p4_king_activation", "p5_timing", "p6_siege", "p7_fragility")
TERMS = GRADED + ("sum",)
CARDS = ("tesla", "x-bow", "skeletons", "knight", "ice-wizard", "tornado", "the-log", "rocket")
out = []
P = out.append


def f(x):
    return float(x)


P(f"# gate_summary -- Part 1 (pro replays through the sim), {len(rows)} scored plays from {len(set(r['tag'] for r in rows))} replays")
P(f"side 1 (blue = icebow player) plays: {sum(1 for r in rows if r['side']=='1')}; side 0: {sum(1 for r in rows if r['side']=='0')}")
P(f"plays with a recognised threat (per-card radii): {sum(1 for r in rows if r['threat'])} / {len(rows)}")
P("")
P("## A. per card x term: pro tile vs the policy's LOCKED tile (strict >, tie, <), median rank of the pro tile among 1 + N candidates (N = n_cands column)")
P("   (rank 1 = no candidate strictly better; `tie1` = fraction of plays where the pro tile is rank 1 but tied with >= 1 candidate;")
P("    `n_active` = plays where the term is non-zero for the pro tile OR the locked tile OR any candidate is beaten -- i.e. the term applies)")
for side_label, side in (("BLUE side (icebow player)", "1"), ("RED side", "0")):
    P(f"\n### {side_label}")
    for card in CARDS:
        rs = [r for r in rows if r["card"] == card and r["side"] == side]
        if not rs:
            continue
        P(f"\n[{card}] n={len(rs)}  threat present {sum(1 for r in rs if r['threat'])}/{len(rs)}  "
          f"top threats: {collections.Counter(r['threat'] or '-' for r in rs).most_common(4)}")
        P(f"{'term':20s} {'mode':4s} {'n':>5s} {'pro>lock':>9s} {'tie':>6s} {'pro<lock':>9s} {'medrank':>8s} {'rank1':>6s} {'tie1':>6s} {'n_active':>8s} {'mean_pro':>8s} {'mean_lock':>9s}")
        for k in TERMS:
            for mode in ("pc", "ra"):
                pro = np.array([f(r[f"{mode}_pro_{k}"]) for r in rs])
                lock = np.array([f(r[f"{mode}_lock_{k}"]) for r in rs])
                rank = np.array([int(r[f"{mode}_rank_{k}"]) for r in rs])
                ntie = np.array([int(r[f"{mode}_ntie_{k}"]) for r in rs])
                gt = np.mean(pro > lock + 1e-9); lt = np.mean(pro < lock - 1e-9); eq = 1 - gt - lt
                active = np.sum((np.abs(pro) > 1e-9) | (np.abs(lock) > 1e-9) | (rank > 1))
                P(f"{k:20s} {mode:4s} {len(rs):5d} {gt:9.3f} {eq:6.3f} {lt:9.3f} {np.median(rank):8.1f} {np.mean(rank==1):6.3f} "
                  f"{np.mean((rank==1)&(ntie>0)):6.3f} {active:8d} {pro.mean():8.3f} {lock.mean():9.3f}")

P("\n## B. per-card vs role-average radii agreement (fraction of plays where the pro tile's rank is UNCHANGED), blue side")
P(f"{'card':12s} {'n':>5s} " + " ".join(f"{k[:12]:>12s}" for k in TERMS))
for card in CARDS:
    rs = [r for r in rows if r["card"] == card and r["side"] == "1"]
    if not rs:
        continue
    agree = []
    for k in TERMS:
        a = np.mean([int(r[f"pc_rank_{k}"]) == int(r[f"ra_rank_{k}"]) for r in rs])
        agree.append(a)
    P(f"{card:12s} {len(rs):5d} " + " ".join(f"{a:12.3f}" for a in agree))
rs = [r for r in rows if r["side"] == "1"]
P(f"{'ALL blue':12s} {len(rs):5d} " + " ".join(f"{np.mean([int(r[f'pc_rank_{k}'])==int(r[f'ra_rank_{k}']) for r in rs]):12.3f}" for k in TERMS))
P(f"threat identity unchanged under role radii: {np.mean([r['threat']==r['threat_ra'] for r in rs]):.3f} (n={len(rs)})")
P("ONLY-WHEN-ACTIVE agreement (plays where the term is non-zero for the pro tile under either radii), blue side:")
for k in GRADED:
    act = [r for r in rs if abs(f(r[f"pc_pro_{k}"])) > 1e-9 or abs(f(r[f"ra_pro_{k}"])) > 1e-9]
    if act:
        P(f"  {k:20s} n_active={len(act):5d}  rank unchanged {np.mean([int(r[f'pc_rank_{k}'])==int(r[f'ra_rank_{k}']) for r in act]):.3f}  "
          f"mean pro pc {np.mean([f(r[f'pc_pro_{k}']) for r in act]):.3f} ra {np.mean([f(r[f'ra_pro_{k}']) for r in act]):.3f}")

P("\n## C. which candidate wins the summed score most often (blue side, per-card radii)")
for card in CARDS:
    rs = [r for r in rows if r["card"] == card and r["side"] == "1"]
    if rs:
        P(f"  {card:12s} n={len(rs):5d} best: {collections.Counter(r['pc_best_cand'] for r in rs).most_common(5)}")

P("\n## D. GATE RULE (doc s3): Tesla at the pros' modal tile (9,21) vs the corner tile (1.5,18.5) on boards whose picked threat is Hog/Giant/PEKKA")
gp = D / "gate_tesla_probe.csv"
if gp.exists():
    g = list(csv.DictReader(gp.open(encoding="utf-8")))
    for scope, gg in (("all such boards", g), ("threat on OUR half", [r for r in g if r["own_side_threat"] == "1"]),
                      ("threat on THEIR half", [r for r in g if r["own_side_threat"] == "0"])):
        if not gg:
            continue
        P(f"\n  {scope}: n={len(gg)}  threats {collections.Counter(r['threat_m'] for r in gg).most_common(4)}")
        P(f"  {'term':20s} {'med(modal-corner)':>18s} {'med modal':>10s} {'med corner':>11s} {'mean modal':>11s} {'mean corner':>12s} {'modal>corner':>13s} {'modal<corner':>13s} verdict")
        for k in TERMS:
            m = np.array([f(r[f"modal_{k}"]) for r in gg]); c = np.array([f(r[f"corner_{k}"]) for r in gg])
            diff = m - c
            verdict = "DROP (modal below corner on the median board)" if np.median(diff) < -1e-9 else ("flat" if abs(np.median(diff)) <= 1e-9 else "keep")
            if np.all(np.abs(m) < 1e-9) and np.all(np.abs(c) < 1e-9):
                verdict = "inactive (never fires for a Tesla)"
            P(f"  {k:20s} {np.median(diff):18.3f} {np.median(m):10.3f} {np.median(c):11.3f} {m.mean():11.3f} {c.mean():12.3f} "
              f"{np.mean(diff>1e-9):13.3f} {np.mean(diff<-1e-9):13.3f} {verdict}")
(D / "gate_summary.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
print("\n".join(out))
