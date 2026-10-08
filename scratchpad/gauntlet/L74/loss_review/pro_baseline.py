"""Pro reference numbers for the loss review, on the SAME definitions as review.py (run once; report.py reads pro_baseline.json).

Source: the push-Rocket worker's extraction of 2,244 pro icebow sides (corpus_v6/icebow_public_v1, frames every 10 ticks):
  .claude/worktrees/agent-a8aad346ac44709a7/scratchpad/gauntlet/L73/push_rocket/pros.pkl  (F=(tick, own elixir, hand, enemy bodies own-y<=20, towers),
  me/op=(tick, card, X, Y, elixir_before|cost)). Pro plays are ENGINE deploy ticks; live plays are TAP ticks (~1.3 s earlier).
Pro towers are lower level (princess 3052 vs live 4424), so HP thresholds are scaled by the princess max HP.
Opponent elixir for pros = a public counter rebuilt from the opponent's visible plays (start 6, regen by phase, minus card cost),
the same idea as the live opp_counter. Single process, below-normal priority.
"""
import os, sys, json, math, pickle, collections, bisect
try:
    import ctypes; ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception: pass
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
sys.path.insert(0, HERE)
import review as V
PKL = "C:/Users/benpe/ClashBot/.claude/worktrees/agent-a8aad346ac44709a7/scratchpad/gauntlet/L73/push_rocket/pros.pkl"
PRO_PRINCESS = 3052.0
CARD = {"x-bow": "Xbow", "the-log": "Log", "ice-wizard": "IceWizard", "skeletons": "Skeletons", "knight": "Knight", "tesla": "Tesla",
        "tornado": "Tornado", "rocket": "Rocket"}


def main():
    n_, c_, u_ = V._catalog(); V.NAME.update(n_); V.NCOST.update(c_); V.UV.update(u_)
    low = {k.lower().replace(" ", ""): k for k in list(V.UV) + list(V.NCOST)}
    def canon(n): return low.get(str(n).lower().replace("-", "").replace(" ", "").replace("_", ""), str(n))
    P = pickle.load(open(PKL, "rb"))
    out = collections.defaultdict(list); unknown = collections.Counter()
    EH = {"quiet": collections.defaultdict(lambda: [0.0, 0]), "press": collections.defaultdict(lambda: [0.0, 0])}
    CQ = collections.Counter()
    for m in P:
        F = m["F"]; T = [f[0] for f in F]; end = m["end"]
        if len(F) < 20: continue
        me = sorted(m["me"]); op = sorted(m["op"])
        res = "DRAW" if m["draw"] else ("WIN" if m["win"] else "LOSS")
        out["res"].append(res)
        # towers: princess missing after being seen = destroyed (0); kings only while present
        seen = set(); TW = []
        for f in F:
            tw = dict(f[4]); seen |= set(tw)
            for k in ("mL", "mR", "eL", "eR"):
                if k in seen and k not in tw: tw[k] = 0
            TW.append(tw)
        def hp(k, t):
            i = max(0, bisect.bisect_right(T, t) - 1); return TW[i].get(k)
        def taken(t0, t1): return sum(max(0, (hp(k, t0) or 0) - (hp(k, t1) or 0)) for k in ("mL", "mR") if hp(k, t0) is not None)
        def dealt(t0, t1): return sum(max(0, (hp(k, t0) or 0) - (hp(k, t1) or 0)) for k in ("eL", "eR", "eK") if hp(k, t0) is not None and hp(k, t1) is not None)
        # opponent public counter
        def opp_est(t):
            e, last = 6.0, 0
            for (pt, card, x, y, cost) in op:
                if pt > t: break
                e = min(10.0, e + (pt - last) * V.REGEN[V.ph(last)]); e = max(0.0, e - (cost or 0)); last = pt
            return min(10.0, e + (t - last) * V.REGEN[V.ph(last)])
        # leak + Rocket-in-hand
        leak = {p: [0.0, 0.0] for p, _, _ in V.PH}; rk = [0, 0]
        for a, b in zip(F, F[1:]):
            dt = min(b[0] - a[0], 30); p = V.ph(a[0])
            if a[1] is not None and a[1] >= V.CAP: leak[p][0] += dt * V.REGEN[p]
            leak[p][1] += dt / 20
            if a[2]: rk[0] += "Rocket" in a[2]; rk[1] += 1
        out["waste"].append(sum(v[0] for v in leak.values())); out["rocket_in_hand"].append(rk[0] / rk[1] if rk[1] else None)
        for p in leak: out["waste_" + p].append(leak[p][0] if leak[p][1] else None)
        for (t, card, x, y, eb) in me:
            if eb is not None: out["el_at_play_" + V.ph(t)].append(eb)
            if card == "tornado": out["tornado_y"].append(int(y))
            if card == "the-log": out["log_y"].append(int(y))
        # threat episodes (same definition as review.py)
        vals = []
        for f in F:
            v = 0.0; air = False
            for (n, X, Y) in f[3]:
                c = canon(n)
                if c not in V.UV and c not in V.NCOST: unknown[c] += 1
                if Y <= V.THREAT_Y: v += V.uval(c); air |= c in V.AIR
            vals.append((v, air))
        for i, (a, b) in enumerate(zip(F, F[1:])):      # play rate by own-elixir bucket (same split as review.py el_hist)
            if a[1] is not None: EH["press" if vals[i][0] >= 3 else "quiet"][min(9, int(a[1]))][0] += min(b[0] - a[0], 30) / 20
        for (t, card, x, y, eb) in me:
            if eb is None: continue
            k = max(0, bisect.bisect_right(T, t) - 1)
            EH["press" if vals[k][0] >= 3 else "quiet"][min(9, int(eb))][1] += 1
            CQ[f"{CARD.get(card, card)}|{'press' if vals[k][0] >= 3 else 'quiet'}|{'lo' if eb < 5 else 'hi'}"] += 1
        out["minutes"].append(end / 1200)
        last_hi = -10 ** 9; on = False; ptick = [p[0] for p in me]
        for i, f in enumerate(F):
            t = f[0]; v = vals[i][0]
            if v >= V.THREAT_V:
                if not on and t - last_hi >= 80:
                    j = i; qs = None
                    while j + 1 < len(F) and F[j + 1][0] - t < 600:
                        j += 1
                        if vals[j][0] < 3: qs = F[j][0] if qs is None else qs
                        else: qs = None
                        if qs is not None and F[j][0] - qs >= 60: break
                    t_end = F[j][0]
                    k = bisect.bisect_left(ptick, t); rsp = (ptick[k] - t) / 20 if k < len(ptick) and ptick[k] - t <= 200 else None
                    pre = [p for p in me if t - 200 <= p[0] < t]
                    lost = taken(t, min(end, t_end + 60))
                    fell = any((hp(k2, t) or 0) > 0 and hp(k2, min(end, t_end + 60)) == 0 for k2 in ("mL", "mR"))
                    out["eps"].append(dict(el=f[1], v=max(vals[x][0] for x in range(i, j + 1)), rsp=rsp, pre10=sum(V.COST.get(CARD.get(p[1], ""), 0) for p in pre),
                                           bad=lost >= 1000 / 4424 * PRO_PRINCESS or fell, fell=fell, air=any(vals[x][1] for x in range(i, j + 1)), res=res))
                on = True; last_hi = t
            else: on = False
        # locked X-Bows: enemy tower HP lost in 20 s, opponent public counter at placement
        for (t, card, x, y, eb) in me:
            if card != "x-bow": continue
            alive = [k for k in V.EN_T if (hp(k, t) or 0) > 0]
            lock = any(math.hypot(x - V.EN_T[k][0], y - V.EN_T[k][1]) <= V.REACH for k in alive)
            if not lock: out["xbow_def"].append(1); continue
            d20 = dealt(t, min(end, t + 400)) / PRO_PRINCESS
            out["xbow"].append(dict(d20=d20, ph=V.ph(t), opp_el=opp_est(t), el_after=(eb or 0) - 6, res=res))
        for p, a, b in V.PH:
            n = sum(1 for q in me if a <= q[0] < b); mins = max(0, min(end, b) - a) / 1200
            if mins > 0.2: out["ppm_" + p].append(n / mins)
    def med(v): v = sorted(x for x in v if x is not None); return v[len(v) // 2] if v else None
    def mean(v): v = [x for x in v if x is not None]; return sum(v) / len(v) if v else None
    E = out["eps"]; X = out["xbow"]
    def bad_rate(S): return (sum(e["bad"] for e in S) / len(S), len(S)) if S else (None, 0)
    R = dict(source=PKL, n_sides=len(out["res"]), wr=out["res"].count("WIN") / len(out["res"]),
             threat=dict(n=len(E), el_med=med([e["el"] for e in E]), el_lt4=sum(e["el"] < 4 for e in E) / len(E),
                         bad=bad_rate(E), bad_el_lt4=bad_rate([e for e in E if e["el"] < 4]), bad_el_4_7=bad_rate([e for e in E if 4 <= e["el"] < 7]),
                         bad_el_ge7=bad_rate([e for e in E if e["el"] >= 7]), rsp_le2=sum(e["rsp"] is not None and e["rsp"] <= 2 for e in E) / len(E),
                         pre10_mean=mean([e["pre10"] for e in E]), pre10_ge7=sum(e["pre10"] >= 7 for e in E) / len(E), eps_per_match=len(E) / len(out["res"]),
                         el_med_by_res={r: med([e["el"] for e in E if e["res"] == r]) for r in ("WIN", "LOSS")}),
             waste_per_match=mean(out["waste"]), waste_by_phase={p: mean(out["waste_" + p]) for p, _, _ in V.PH}, waste_ge5=sum(w >= 5 for w in out["waste"]) / len(out["waste"]),
             rocket_in_hand=mean(out["rocket_in_hand"]), el_at_play={p: mean(out["el_at_play_" + p]) for p, _, _ in V.PH},
             plays_per_min={p: mean(out["ppm_" + p]) for p, _, _ in V.PH},
             xbow=dict(n_locked=len(X), n_def=len(out["xbow_def"]), dud=sum(x["d20"] < 300 / 4424 for x in X) / len(X), d20_mean_frac=mean([x["d20"] for x in X]),
                       opp_el_ge7=sum(x["opp_el"] >= 7 for x in X) / len(X), opp_el_med=med([x["opp_el"] for x in X]),
                       dud_opp_ge7=sum(x["d20"] < 300 / 4424 for x in X if x["opp_el"] >= 7) / max(1, sum(x["opp_el"] >= 7 for x in X)),
                       dud_opp_lt7=sum(x["d20"] < 300 / 4424 for x in X if x["opp_el"] < 7) / max(1, sum(x["opp_el"] < 7 for x in X)),
                       el_after_med=med([x["el_after"] for x in X]), by_phase={p: dict(n=sum(x["ph"] == p for x in X), dud=sum(x["d20"] < 300 / 4424 for x in X if x["ph"] == p) / max(1, sum(x["ph"] == p for x in X))) for p, _, _ in V.PH}),
             tornado_y=dict(collections.Counter(out["tornado_y"]).most_common(12)), tornado_enemy_side=sum(y > 16 for y in out["tornado_y"]) / max(1, len(out["tornado_y"])),
             log_y=dict(collections.Counter(out["log_y"]).most_common(8)), unknown_names=dict(unknown.most_common(10)),
             el_hist={k: {b: [round(v[0], 1), v[1]] for b, v in sorted(d.items())} for k, d in EH.items()},
             card_ctx_per_min={k: v / sum(out["minutes"]) for k, v in CQ.items()}, minutes=sum(out["minutes"]))
    json.dump(R, open(HERE + "pro_baseline.json", "w"), indent=1, default=str)
    print(json.dumps(R, indent=1, default=str)[:4000])


if __name__ == "__main__":
    main()
