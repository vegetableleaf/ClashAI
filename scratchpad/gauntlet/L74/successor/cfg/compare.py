"""Successor readout: every trained successor run vs Mark CXXXVIII on the PROMOTION eval (the owner's bar: paired 95% CI
lower bound > 0, 960 games, seeds 741200 + 742000) and vs its control succ_ctl (the one-change attribution), the same on
the FRESH seeds 743000 + 744000 and pooled (1,920), the 13k-relevant slices (opponent deck holds a 13k-core card / a Hog
Rider; the reference game went to overtime; opponent tower level 16), the habit metrics, and the 13k-gap probe
(gap13k_*: the exploiter as the opponent -- does the SIM then order CXXXVIII vs u250 the way live does?).
    python compare.py [SUCC_ROOT] [--ctl NAME=ROOT ...]     python compare.py --selftest
SUCC_ROOT default C:/Users/benpe/pod_backup_weekend/pod1017_successor (pull.sh); refs from pod1017_factorial (same command).
--ctl cue_ctl=DIR adds another control whose rows sit at DIR/<NAME>_{741200,742000}/D3/matches.jsonl (e.g. rlarm_gae_cue_ctl).
Slice CIs are paired bootstraps inside the slice (heroiw/validate.paired_drift); slices were chosen from LIVE data (loss
review + drift report), not from these eval rows."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[1] / "heroiw"), str(HERE.parents[1] / "weekend"), str(HERE.parents[1] / "factorial")]
from validate import paired_drift  # noqa: E402
import archetypes as A  # noqa: E402
from analyze import metrics, HABITS  # noqa: E402

SUCC = Path("C:/Users/benpe/pod_backup_weekend/pod1017_successor")
FACT = Path("C:/Users/benpe/pod_backup_weekend/pod1017_factorial")
STD, FRESH = (741200, 742000), (743000, 744000)
CORE = {"megaknight", "witch", "firecracker", "hogrider", "electrogiant", "elixirgolem", "goldenknight"}
REG_END = 3600                                   # 180 s x 20 ticks: a game that ends later went to overtime
RUNS = ("succ_ctl", "succ_levels", "succ_hist", "succ_tower", "succ_troops", "succ_exploit")


def rows_at(d, name, seeds):
    out = []
    for s in seeds:
        p = Path(d) / f"{name}_{s}" / "D3" / "matches.jsonl"
        if not p.is_file():
            return None
        out += [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    return out if len(out) == 480 * len(seeds) else None


def job(root, name, seeds):
    return rows_at(Path(root) / name / "eval", name, seeds)


SLICES = {
    "core deck": lambda r: bool({A.canon(n) for n in r["opp_deck"]} & CORE),
    "Hog deck": lambda r: "hogrider" in {A.canon(n) for n in r["opp_deck"]},
    "overtime (ref game)": lambda r: (r.get("end_tick") or 0) > REG_END,
    "opp tower L16": lambda r: ((r.get("levels") or {}).get("opp") or {}).get("tower") == 16,
}


def pd(base, new, keep=None):
    """paired delta 'x.xx [lo, hi] (n)' of new vs base, restricted to the keys whose BASE row passes keep."""
    if base is None or new is None:
        return "-"
    if keep is not None:
        ks = {(r["census"], r["seed"]) for r in base if keep(r)}
        base = [r for r in base if (r["census"], r["seed"]) in ks]
        new = [r for r in new if (r["census"], r["seed"]) in ks]
    try:
        d = paired_drift(base, new, expected=len(base))
    except ValueError as exc:
        return f"unpaired ({exc})"
    lo, hi = d["ci95_pp"]
    return f"{d['delta_pp']:+6.2f} [{lo:+6.2f}, {hi:+6.2f}] n {d['pairs']}" + ("  BAR PASS" if keep is None and lo > 0 else "")


def report(root, ctls):
    ref = {s: rows_at(FACT / "ref_cxxxviii" / "eval", "ref_cxxxviii", STD) for s in ("std",)}["std"]
    ref_f = job(root, "fresh_ref_cxxxviii", FRESH)
    print(f"Mark CXXXVIII std {'ok' if ref else 'MISSING'}: "
          f"{sum(r['outcome'] == 'win' for r in ref) if ref else '-'}/960; fresh {'ok' if ref_f else 'missing'}")
    ctl_rows = {n: rows_at(d, n, STD) for n, d in ctls.items()}
    ctl_rows["succ_ctl"] = job(root, "succ_ctl", STD)
    for r in RUNS + tuple(sorted({p.name for p in Path(root).glob("succ_*_s7?")})):
        std = job(root, r, STD)
        if std is None:
            print(f"\n{r}: not complete")
            continue
        fr = job(root, f"fresh_{r}", FRESH)
        m, mr = metrics(std), metrics(ref)
        print(f"\n{r}: {sum(x['outcome'] == 'win' for x in std)}/960")
        print(f"  vs Mark CXXXVIII (owner bar)  {pd(ref, std)}")
        for n, c in ctl_rows.items():
            if n != r and c is not None and not r.startswith(n):
                print(f"  vs {n:27} {pd(c, std).replace('  BAR PASS', '')}")
        if fr is not None and ref_f is not None:
            print(f"  fresh seeds vs CXXXVIII       {pd(ref_f, fr).replace('  BAR PASS', '')}")
            print(f"  pooled 1,920 vs CXXXVIII      {pd(ref + ref_f, std + fr).replace('  BAR PASS', '')}")
        for s, f in SLICES.items():
            print(f"  slice {s:23} {pd(ref, std, f)}")
        print("  habits (run / CXXXVIII): " + ", ".join(f"{h} {m[h][0]:.2f} / {mr[h][0]:.2f}" for h in HABITS if h in m and h in mr))
    g = {k: job(root, f"gap13k_{k}", STD) for k in ("ref_cxxxviii", "ref_u250")}
    if all(v is not None for v in g.values()):
        print("\n13k-gap probe (opponent = exploiter): CXXXVIII minus u250 -- live says core 42.0 vs 46.2, Hog 28.6 vs 56.4 "
              "(CXXIV); the E4 eval says Hog 70.4 vs 66.3")
        print(f"  all       {pd(g['ref_u250'], g['ref_cxxxviii'])}".replace("  BAR PASS", ""))
        for s, f in SLICES.items():
            print(f"  {s:9} {pd(g['ref_u250'], g['ref_cxxxviii'], f)}")
        for k, v in g.items():
            core = [x for x in v if SLICES["core deck"](x)]
            print(f"  {k}: win {100 * sum(x['outcome'] == 'win' for x in v) / 960:.1f}%, core decks "
                  f"{100 * sum(x['outcome'] == 'win' for x in core) / max(1, len(core)):.1f}% (n {len(core)})")


def selftest():
    base = [{"census": "c", "seed": i, "outcome": "loss", "opp_deck": ["HogRider" if i % 2 else "Knight"],
             "learner_side": 0, "opp_gen_sha256": "x", "searched": 0, "end_tick": 4000 if i % 3 == 0 else 3000} for i in range(400)]
    new = [dict(r, outcome="win" if r["opp_deck"] == ["HogRider"] else r["outcome"]) for r in base]
    first = lambda txt: float(txt.split()[0])
    assert first(pd(base, new)) == 50.0 and "BAR PASS" in pd(base, new), pd(base, new)
    assert first(pd(base, new, SLICES["Hog deck"])) == 100.0
    assert first(pd(base, new, lambda r: not SLICES["Hog deck"](r))) == 0.0
    assert SLICES["overtime (ref game)"](base[0]) and not SLICES["overtime (ref game)"](base[1])
    print("SELFTEST PASS")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        args = [a for a in sys.argv[1:] if not a.startswith("--ctl")]
        ctls = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a and not a.startswith("--"))
        report(Path(args[0]) if args and "=" not in args[0] else SUCC, ctls)
