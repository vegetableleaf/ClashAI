"""Follow-up measurements on defense.py data (-> out/extra.txt):
 (1) the pending lock after a defence: damage while locked, split by whether the NEXT play came at the first decision after the
     confirmation ('chained' = the bot wanted to play again at once, so the lock delayed it);
 (2) consecutive defensive cards inside >= 5 lane episodes: land-to-land gaps, bot vs pros (pros < 26 ticks = impossible under the lock);
 (3) Tornado follow-up: time from a defensive Tornado to the next defensive card landing in that lane, bot vs pros;
 (4) per-card dmg10 split by elixir at the play (< 4 vs >= 6), bot vs pros (separates the economy from card/placement quality).
"""
import sys, os, collections, bisect
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
sys.path.insert(0, HERE)
import defense as D

OUT = []
def pr(*a):
    s = " ".join(str(x) for x in a); OUT.append(s); print(s)


def med(v):
    v = sorted(x for x in v if x is not None); return v[len(v) // 2] if v else None


def run(name, ms, fams=None):
    hz = collections.defaultdict(lambda: [0.0, 0]); lock = collections.Counter(); gaps = []; tor = []; card = collections.defaultdict(list); n_ep = 0; nm = 0
    for m in ms:
        if fams and not any(m["fam"].startswith(f) for f in fams): continue
        if m.get("res") not in ("WIN", "LOSS", "DRAW"): continue
        nm += 1
        T, H = D.hp_series(m["S"]); live = m["src"] == "live"; P = m["P"]; S = m["S"]
        sc = 4424.0 / m["pmax"]
        dts = [s[0] for s in S]
        for e in D.episodes(m):
            D.analyse_episode(m, e, T, H)
            if e["vmax"] < 5 or not e["n_def"]: continue
            n_ep += 1; lane = e["lane"]; k = e["tower"]; tail = e["t_end"] + 60
            defp = [p for p in P if D.is_def(p, lane) and e["t"] - 40 <= (p[0] if live else p[1] - 26) <= e["t_end"]]
            for a, b in zip(defp, defp[1:]): gaps.append(b[1] - a[1])
            for i, p in enumerate(defp):
                if p[2] == "Tornado":
                    nx = defp[i + 1][1] - p[1] if i + 1 < len(defp) else None
                    tor.append((nx, D.dmg(T, H, k, p[1], p[1] + 200) * sc))
                if p[5] is not None:
                    b = "lo<4" if p[5] < 4 else ("hi>=6" if p[5] >= 6 else "mid")
                    card[(p[2], b)].append(D.dmg(T, H, k, p[1], p[1] + 200) * sc)
            # (5) follow-up hazard: after the first defence lands, free states (bot: not pending) while the lane tower is being hit
            # (HP drop within the next 20 ticks), by my elixir: defensive plays per second (bot tap / pro deploy - 26)
            pend = [(p[0], p[1] if p[1] is not None else p[0] + 28) for p in P if p[0] is not None] if live else []
            dplay = sorted((p[0] if live else p[1] - 26) for p in P if D.is_def(p, lane))
            j0 = bisect.bisect_left(dts, e["first_land"] or 10 ** 9)
            for j in range(j0, len(S) - 1):
                a = S[j][0]
                if a >= tail: break
                if live and any(x < a < y for x, y in pend): continue
                if D.dmg(T, H, k, a, max(S[j + 1][0], a + 20)) <= 0 or S[j][1] is None: continue
                el = S[j][1]; b = "<2" if el < 2 else "2-4" if el < 4 else "4-6" if el < 6 else "6+"
                dt = min(S[j + 1][0] - a, 10)
                hz[b][0] += dt / 20; hz[b][1] += sum(1 for x in dplay[bisect.bisect_left(dplay, a):bisect.bisect_left(dplay, a + dt)])
            if live:   # lock windows after the first defence: every play tapped in [first land, tail)
                allp = sorted(p for p in P if p[0] is not None)
                for i, p in enumerate(allp):
                    if p[0] < (e["first_land"] or 10 ** 9) or p[0] >= tail: continue
                    end = p[1] if p[1] is not None else p[0] + 28
                    j = bisect.bisect_left(T, end); end_s = T[j] if j < len(T) else end    # HP is seen only at states
                    dmg = D.dmg(T, H, k, p[0], end_s) * sc
                    nxt = allp[i + 1][0] if i + 1 < len(allp) else None
                    chained = nxt is not None and nxt - end <= 4
                    kind = ("def" if D.is_def(p, lane) else "other")
                    lock[(kind, "chained" if chained else "not")] += dmg
                    lock["sec"] += (end - p[0]) / 20; lock["n"] += 1
    pr(f"\n== {name}: matches {nm}, defended >= 5 episodes {n_ep}")
    if lock["n"]:
        tot = sum(v for kk, v in lock.items() if isinstance(kk, tuple))
        pr(f"(1) lock windows after the first defence: n {lock['n']}, {lock['sec'] / lock['n']:.2f} s each; lane damage per match {tot / nm:.0f}: "
           + "  ".join(f"{kk[0]}/{kk[1]} {v / nm:.0f}" for kk, v in sorted(lock.items(), key=lambda x: str(x[0])) if isinstance(kk, tuple)))
    pr("(5) defensive plays per second in free states after the first defence while the lane tower is being hit, by my elixir: "
       + "  ".join(f"{b}: {hz[b][1] / hz[b][0]:.3f}/s ({hz[b][0]:.0f}s)" for b in ("<2", "2-4", "4-6", "6+") if hz[b][0]))
    g = sorted(gaps)
    if g: pr(f"(2) land-to-land gap between consecutive defensive cards (ticks): n {len(g)} median {med(g)}  < 26: {sum(x < 26 for x in g) / len(g):.3f}"
             f"  < 35: {sum(x < 35 for x in g) / len(g):.3f}  < 60: {sum(x < 60 for x in g) / len(g):.3f}")
    if tor:
        f = [x for x, _ in tor if x is not None]
        pr(f"(3) defensive Tornado: n {len(tor)}; next defensive card lands within 1.5 s {sum(x <= 30 for x in f) / len(tor):.2f}, within 3 s {sum(x <= 60 for x in f) / len(tor):.2f},"
           f" never in the episode {sum(x is None for x, _ in tor) / len(tor):.2f}; dmg10 {sum(d for _, d in tor) / len(tor):.0f}")
    pr("(4) dmg10 by card and elixir at the play (lo < 4 / hi >= 6):  " + "  ".join(
        f"{c} {sum(card[(c, 'lo<4')]) / max(1, len(card[(c, 'lo<4')])):.0f}(n{len(card[(c, 'lo<4')])})/{sum(card[(c, 'hi>=6')]) / max(1, len(card[(c, 'hi>=6')])):.0f}(n{len(card[(c, 'hi>=6')])})"
        for c in ("Knight", "IceWizard", "Tesla", "Skeletons", "Tornado", "Log")))


if __name__ == "__main__":
    L = D.load("live")
    run("TR (towerref_w2 era)", L, ["towerref"])
    run("RL (R-lineage)", L)
    run("PRO", D.load("pros"))
    open(HERE + "out/extra.txt", "w").write("\n".join(OUT) + "\n")
