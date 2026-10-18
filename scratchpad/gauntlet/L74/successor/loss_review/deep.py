"""Drill-downs for the successor loss review: trophy bands (opponent levels / deck mix / overtime), a logistic decomposition of
win, the Hog matchup, overtime losses. Reads matches.jsonl rows via analyze.load()."""
import collections, math, random, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import analyze as A
V = A.V
mean = A.mean


def boot(v, f=lambda s: sum(s) / len(s), B=2000, seed=3):
    v = [x for x in v if x is not None]; rng = random.Random(seed)
    d = sorted(f([v[rng.randrange(len(v))] for _ in v]) for _ in range(B))
    return f(v), d[int(.025 * B)], d[int(.975 * B)]


def logit(X, y, names):
    X = np.asarray(X, float); y = np.asarray(y, float); b = np.zeros(X.shape[1])
    for _ in range(50):
        p = 1 / (1 + np.exp(-X @ b)); W = p * (1 - p); H = X.T @ (X * W[:, None]) + 1e-6 * np.eye(len(b))
        step = np.linalg.solve(H, X.T @ (y - p)); b += step
        if np.abs(step).max() < 1e-8: break
    se = np.sqrt(np.diag(np.linalg.inv(H)))
    for n, c, s in zip(names, b, se):
        print(f"    {n:34s} {c:+.3f} +- {1.96 * s:.3f}  (odds x{math.exp(c):.2f}; p~{math.erfc(abs(c / s) / 2 ** .5):.3f})")


def main():
    rows = sorted(A.load(), key=lambda r: r["ts"])
    C124 = [r for r in rows if r["mark"] == "CXXIV" and r["ts"] < A.SWITCH][-200:]
    C138 = [r for r in rows if r["mark"] == "CXXXVIII" and r["ts"] >= A.SWITCH]
    hog = lambda r: r["_cls"] == "Hog (incl. Royal Hogs)"
    win = lambda r: r["result"] == "WIN"
    bands = (("CXXIV < 12,500", [r for r in C124 if r["start"] < 12500]), ("CXXIV >= 12,500", [r for r in C124 if r["start"] >= 12500]),
             ("CXXXVIII < 13,000", [r for r in C138 if r["start"] < 13000]), ("CXXXVIII >= 13,000", [r for r in C138 if r["start"] >= 13000]))
    print("== bands: n | win | opp card level mean [95% CI] | matches with opp mean level >= 16 | opp towers L16 | Hog share | OT share | OT win | hours")
    for name, Q in bands:
        lv = boot([r["opp_card_lv"] for r in Q]); ot = [r for r in Q if r["dur_s"] >= 186]
        print(f"  {name:20s} {len(Q):3d} | {A.wil(sum(map(win, Q)), len(Q)):22s} | {lv[0]:.2f} [{lv[1]:.2f}, {lv[2]:.2f}] | "
              f"{mean([(r['opp_card_lv'] or 0) >= 16 for r in Q]):.0%} | {mean([r['opp_tower_lv'] == 16 for r in Q]):.0%} | {mean([hog(r) for r in Q]):.0%} | "
              f"{len(ot) / len(Q):.0%} | {A.wil(sum(map(win, ot)), len(ot)) if ot else '-'} | {Q[0]['ts'][9:13]}-{Q[-1]['ts'][9:13]}")
    # level effect pooled + by model; and the level gap (opp - ours: our cards 16 except IW 14 / Log 15; our towers 15)
    print("\n== win rate by opponent mean card level (both Marks pooled, then per Mark)")
    for lab, f in (("< 15.25", lambda x: x < 15.25), ("15.25-15.75", lambda x: 15.25 <= x < 15.75), ("15.75-16.0 (excl.)", lambda x: 15.75 <= x < 16.0), (">= 16.0", lambda x: x >= 16.0)):
        for mk, Q in (("both", C124 + C138), ("CXXIV", C124), ("CXXXVIII", C138)):
            S = [r for r in Q if r["opp_card_lv"] is not None and f(r["opp_card_lv"])]
            if S: print(f"  {lab:20s} {mk:9s} n {len(S):3d} win {A.wil(sum(map(win, S)), len(S))}; OT share {mean([r['dur_s'] >= 186 for r in S]):.0%}")
    print("\n== logistic regression of WIN (276 matches): what remains of the >= 13,000 drop after measured opponent strength")
    Q = C124 + C138
    lvc = [((r["opp_card_lv"] if r["opp_card_lv"] is not None else 15.5) - 15.5) for r in Q]
    for cols in (("mark", "ge13k"), ("mark", "ge13k", "lv", "L16", "hog")):
        X = []; names = ["intercept"]
        for r, l in zip(Q, lvc):
            row = [1.0]
            if "mark" in cols: row.append(float(r["mark"] == "CXXXVIII"))
            if "ge13k" in cols: row.append(float(r["start"] >= 13000))
            if "lv" in cols: row.append(l)
            if "L16" in cols: row.append(float(r["opp_tower_lv"] == 16))
            if "hog" in cols: row.append(float(hog(r)))
            X.append(row)
        names += [{"mark": "Mark CXXXVIII (vs CXXIV)", "ge13k": "start >= 13,000", "lv": "opp card level (+1 = one level)", "L16": "opp towers L16", "hog": "Hog deck"}[c] for c in cols]
        print("  model:", " + ".join(cols)); logit(X, [float(win(r)) for r in Q], names)
    # Hog drilldown
    print("\n== Hog matchup drilldown")
    for name, S in (("CXXIV last 200", [r for r in C124 if hog(r)]), ("CXXXVIII < 13k", [r for r in C138 if hog(r) and r["start"] < 13000]),
                    ("CXXXVIII >= 13k", [r for r in C138 if hog(r) and r["start"] >= 13000]), ("CXXIV non-Hog", [r for r in C124 if not hog(r)]), ("CXXXVIII non-Hog", [r for r in C138 if not hog(r)])):
        if not S: continue
        sp = lambda c: mean([sum(1 for s in r["spells"] if s["name"] == c) for r in S])
        cp = lambda c: mean([sum((r["cards_phase"].get(p) or {}).get(c, 0) for p in ("1x", "2x", "OT")) for r in S])
        TH = [e for r in S for e in r["threats"] if "HogRider" in (e.get("cards") or []) or "RoyalHogs" in (e.get("cards") or [])]
        for e in TH: e["bad"] = e["hp_lost"] >= 1000 or e["tower_fell"]
        oc = collections.Counter(c for r in S for c in set(r["opp_cards"]))
        tn_hit = [s for r in S for s in r["spells"] if s["name"] == "Tornado"]
        print(f"  {name:18s} n {len(S):3d} win {A.wil(sum(map(win, S)), len(S))}; OT {mean([r['dur_s'] >= 186 for r in S]):.0%}; opp lv {mean([r['opp_card_lv'] for r in S]):.2f}; "
              f"plays/match Tornado {sp('Tornado'):.2f} (hit something {mean([s['n_hit'] > 0 for s in tn_hit]):.0%}) Tesla {cp('Tesla'):.2f} Knight {cp('Knight'):.2f} "
              f"Skeletons {cp('Skeletons'):.2f} IW {cp('IceWizard'):.2f} Log {cp('Log'):.2f} Rocket {sp('Rocket'):.2f} X-Bow {cp('Xbow'):.2f} (locked {mean([sum(x['lock'] for x in r['xbows']) for r in S]):.2f}, "
              f"defensive {mean([sum(x['defensive'] for x in r['xbows']) for r in S]):.2f})")
        if TH:
            print(f"      Hog pushes {len(TH)} ({len(TH) / len(S):.1f}/match): lost-episode {mean([e['bad'] for e in TH]):.0%}, own elixir median {V.med([e['el'] for e in TH]):.1f}, "
                  f"met < 4 {mean([e['el'] is not None and e['el'] < 4 for e in TH]):.0%}, answered <= 2 s {mean([e['rsp'] is not None and e['rsp'] <= 2 for e in TH]):.0%}, "
                  f"HP lost/push {mean([e['hp_lost'] for e in TH]):.0f}; first answer " + str(collections.Counter(e['first'][0][0] for e in TH if e.get('first')).most_common(5)))
        print(f"      opp cards (share of matches): " + ", ".join(f"{c} {v / len(S):.0%}" for c, v in oc.most_common(10)))
        print(f"      tower HP taken 1x/2x/OT {mean([r['dmg'].get('1x', {}).get('taken') for r in S]):.0f}/{mean([r['dmg'].get('2x', {}).get('taken') for r in S]):.0f}/{mean([r['dmg'].get('OT', {}).get('taken') for r in S]):.0f}; "
              f"dealt {mean([r['dmg'].get('1x', {}).get('dealt') for r in S]):.0f}/{mean([r['dmg'].get('2x', {}).get('dealt') for r in S]):.0f}/{mean([r['dmg'].get('OT', {}).get('dealt') for r in S]):.0f}")
    # Overtime losses at >= 13k
    print("\n== overtime")
    for name, Q in bands:
        ot = [r for r in Q if r["dur_s"] >= 186]; L = [r for r in ot if not win(r)]
        if not ot: continue
        el = mean([r["el_at_play"].get("OT") for r in ot])
        print(f"  {name:20s} OT {len(ot)}, win {A.wil(sum(map(win, ot)), len(ot))}; OT losses by class {dict(collections.Counter(r['_cls'][:10] for r in L).most_common(5))}; "
              f"OT tower HP taken/dealt per OT match {mean([r['dmg'].get('OT', {}).get('taken') for r in ot]):.0f}/{mean([r['dmg'].get('OT', {}).get('dealt') for r in ot]):.0f}; "
              f"elixir at play in OT {el:.2f}; OT locked X-Bows/match {mean([sum(1 for x in r['xbows'] if x['lock'] and x['ph'] == 'OT') for r in ot]):.2f}; "
              f"OT Rockets/match {mean([sum(1 for s in r['spells'] if s['name'] == 'Rocket' and s['ph'] == 'OT') for r in ot]):.2f}")
    # regulation-time state entering OT: tower HP diff at 180 s is not stored; use crowns 0-0 vs 1-1 at OT start proxy = final crowns
    # trophies at stake per candidate cause on the >= 13k cohort (58 trophies per flipped match, unfloored)
    print("\n== >= 13,000 trophies at stake (flip value 58 = +29.7 win, -28.5 mean unfloored loss)")
    C = [r for r in C138 if r["start"] >= 13000]; n = len(C)
    def gap(lab, f, ref_wr):
        S = [r for r in C if f(r)]; w = sum(map(win, S))
        print(f"  {lab:52s} {len(S):2d} matches, win {w}/{len(S)}; at the reference win rate {ref_wr:.1%}: +{max(0, ref_wr * len(S) - w) * 58 / n:.2f} trophies/match")
    rest = [r for r in C if not hog(r)]
    gap("Hog decks (ref: CXXIV live vs Hog 56.4%)", hog, 22 / 39)
    gap("Hog decks (ref: non-Hog >= 13k)", hog, mean([win(r) for r in rest]))
    gap("overtime matches (ref: CXXIV OT win 61.3%)", lambda r: r["dur_s"] >= 186, mean([win(r) for r in C124 if r["dur_s"] >= 186]))
    gap("opp mean card level >= 16 (ref: CXXXVIII < 16 overall)", lambda r: (r["opp_card_lv"] or 0) >= 16, mean([win(r) for r in C138 if (r["opp_card_lv"] or 0) < 16]))


if __name__ == "__main__":
    main()
