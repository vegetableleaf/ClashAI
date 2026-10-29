"""SIM: lock rate of reach X-Bows by whether a building-damage spell (earthquake / rocket / lightning / fireball / poison) was cast
in (t, t+200]; bodiless spells kept (SIEGE_ALL).  python spell_lock.py ROWS_DIR"""
import os, sys
os.environ["SIEGE_ALL"] = "1"
import siege_b as SB
SP = {"earthquake", "rocket", "lightning", "fireball", "poison"}
for sp in (SP, {"earthquake"}, {"rocket"}):
    a, b = [], []
    for r, xs in SB.sim_xbows(sys.argv[1]):
        for t, x, y, lk, d in xs:
            hit = any(t < p[0] <= t + SB.T_ALL and p[1] in sp for p in r["plays"])
            (a if hit else b).append(lk)
    print(sorted(sp), f"with spell: n {len(a)} lock {sum(a)/len(a):.3f} | without: n {len(b)} lock {sum(b)/len(b):.3f}")
