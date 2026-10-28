"""Sweep table: python tab.py ROWS_DIR OUT_DIR [NAME ...] -> markdown (stdout) + tab.json.
ROWS_DIR/NAME/NAME_SEED/D3/matches.jsonl (pod run_closed.sh rows), OUT_DIR/NAME/report.json (card.py score --no-c --no-d --out).
Columns: CLXIII win % (Wilson 95), OT share, opp plays/min, refused, B-live RMS d (pass bar 0.10), 'vs 0.05 stretch' (owner 10-28:
report for every setting), fails, siege lock / zero-lock / P(lock|failed)."""
import glob, json, math, sys
from pathlib import Path

rows_dir, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
names = sys.argv[3:] or sorted(p.name for p in rows_dir.iterdir() if p.is_dir())
def wil(k, n, z=1.96):
    if not n: return (float('nan'),) * 2
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - h) / d, (c + h) / d
res, L = {}, ["| setting | games | CLXIII win % [95%] | OT | opp plays/min | refused | B RMS d | vs 0.05 stretch | z-fails | lock (live .47) | zero-lock (.12) | P(lock/failed) (.36) |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
for n in names:
    R = [json.loads(l) for f in sorted(glob.glob(f"{rows_dir}/{n}/*/D3/matches.jsonl")) for l in open(f) if l.strip()]
    if not R: continue
    k = sum(r["outcome"] == "win" for r in R); lo, hi = wil(k, len(R))
    o = [r["hab"]["opp"] for r in R]; npl = sum(map(len, o))
    d = dict(games=len(R), win=k / len(R), lo=lo, hi=hi, ot=sum(r["end_tick"] > 3700 for r in R) / len(R),
             ppm=sum(len(x) / ((r["end_tick"] - 90) / 1200) for x, r in zip(o, R)) / len(R), refused=sum(not p[3] for x in o for p in x) / max(npl, 1))
    f = out_dir / n / "report.json"
    if f.exists():
        rep = json.load(open(f)); b = rep["B_live"]; s = rep["siege"]["sim"]
        d.update(rms=b["rms"], fails=sum(1 for v in b["tost"].values() if not (v if isinstance(v, bool) else v.get("passed", v.get("ok", False)))) if isinstance(b["tost"], dict) else None,
                 lock=s["lock_rate"], zero=s["zero_lock"], plf=s["p_lock_after_fail"], b_games=b["n_sim"])
    res[n] = d; g = lambda k, fmt: (fmt % d[k]) if k in d and d[k] is not None else "-"
    rms = d.get("rms")
    L.append(f"| {n} | {d['games']} | {100*d['win']:.1f} [{100*lo:.1f}, {100*hi:.1f}] | {100*d['ot']:.0f}% | {d['ppm']:.2f} | {100*d['refused']:.1f}% | {g('rms','%.3f')} | "
             f"{'-' if rms is None else f'{rms/0.05:.1f}x (bar 0.05: ' + ('pass' if rms <= 0.05 else 'FAIL') + ')'} | {g('fails','%d')} | {g('lock','%.2f')} | {g('zero','%.3f')} | {g('plf','%.2f')} |")
print("\n".join(L)); (out_dir / "tab.json").write_text(json.dumps(res, indent=1))
