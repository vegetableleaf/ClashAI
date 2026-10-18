"""Critic lens 2: is compare.py's 'overtime (ref game)' slice biased by selecting on the BASE arm's outcome-linked game length?
Paired win delta (new - base) inside the slice defined by (a) the base row, (b) the new row, (c) either row; plus end_tick
distribution and the paired SE of the full 960."""
import json, math, sys, collections
from pathlib import Path
F = Path("C:/Users/benpe/pod_backup_weekend/pod1017_factorial")
def rows(n):
    out = {}
    for s in (741200, 742000):
        for l in (F / n / "eval" / f"{n}_{s}" / "D3" / "matches.jsonl").read_text().splitlines():
            if l.strip():
                r = json.loads(l); out[(r["census"], r["seed"])] = r
    return out
W = lambda r: 1.0 if r["outcome"] == "win" else 0.0
OT = lambda r: (r.get("end_tick") or 0) > 3600
base = rows("ref_cxxxviii")
et = collections.Counter(min((r.get("end_tick") or 0) // 600 * 600, 9000) for r in base.values())
print("ref end_tick buckets (600-tick bins):", sorted(et.items()))
print("ref end_tick exactly 3600:", sum((r.get("end_tick") or 0) == 3600 for r in base.values()), " max", max((r.get("end_tick") or 0) for r in base.values()))
for new_name in sys.argv[1:]:
    new = rows(new_name); ks = sorted(set(base) & set(new))
    d = [W(new[k]) - W(base[k]) for k in ks]
    m = sum(d) / len(d); se = math.sqrt(sum((x - m) ** 2 for x in d) / (len(d) - 1) / len(d))
    print(f"\n{new_name}: n {len(ks)} delta {100*m:+.2f} pp, paired SE {100*se:.2f} pp (95% half-width {196*se:.2f})")
    for lab, f in (("slice by BASE row", lambda k: OT(base[k])), ("slice by NEW row", lambda k: OT(new[k])),
                   ("either row OT", lambda k: OT(base[k]) or OT(new[k])), ("both rows OT", lambda k: OT(base[k]) and OT(new[k]))):
        kk = [k for k in ks if f(k)]
        dd = [W(new[k]) - W(base[k]) for k in kk]
        mm = sum(dd) / len(dd); s2 = math.sqrt(sum((x - mm) ** 2 for x in dd) / (len(dd) - 1) / len(dd))
        print(f"  {lab:18s} n {len(kk):4d}  delta {100*mm:+6.2f} pp  [{100*(mm-1.96*s2):+6.2f}, {100*(mm+1.96*s2):+6.2f}]")
    print(f"  OT incidence base {100*sum(OT(base[k]) for k in ks)/len(ks):.1f}%  new {100*sum(OT(new[k]) for k in ks)/len(ks):.1f}%")
