"""Dead-lane X-Bows in live matches (L74/deadlane step 1). Read-only on the MAIN repo's live logs; public info only.

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/deadlane/live_measure.py [--glob ...]

Reuses L74/loss_review/review.py's parser (own frame: my king (9,3), enemy king (9,29); review.model_to_own).
Per confirmed X-Bow (cell = the intended xy, alive towers at the confirmation tick):
  KONLY   = within REACH of an alive enemy tower but of NO alive enemy princess (reaches only the king) -> the block set
  DL_OFF  = literal ticket definition: lane's enemy princess dead AND offensive (any alive tower in reach)
  DL_DEF  = lane's enemy princess dead, not offensive (public_outcomes' dead_lane_xbow)
  OFF_P   = offensive, reaches an alive enemy princess;   DEF = not offensive, lane alive
Values: X-Bow body life, enemy KING damage during the life, all enemy tower damage during the life, my tower damage in
the next 20 s, opponent public-counter spending in the next 10 s, king awake (kind 13) at placement.
Rockets in the same states (an enemy princess down) for comparison."""
import collections, glob, json, math, os, sys, bisect

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "loss_review"))
import review as R   # noqa: E402  (sets below-normal priority on import)

TPS = 20.0
FAMILY = lambda c: "towerref_w2" if "towerref_w2" in c else "stack2k" if "barrel2k_cellref" in c else "R1e" if "r1e31" in c else "other"  # noqa: E731


def analyse(f):
    r = R.parse(f)
    S = r["S"]
    if len(S) < 20 or r["side"] is None:
        return None
    st = r["start"] or {}
    ckpt = (st.get("ckpt") or "").replace("\\", "/").split("/")[-1]
    do = st.get("decision_options") or {}
    T = [s[0] for s in S]
    hp, kind = collections.defaultdict(list), collections.defaultdict(list)
    for s in S:
        for b in s[4]:
            sl = R.tower_slot(b)
            if sl and b[4] > 0:
                hp[sl].append((s[0], b[4])); kind[sl].append((s[0], b[6]))
    dead = {}
    for sl in ("eL", "eR", "eK", "mL", "mR", "mK"):
        v = hp.get(sl)
        if not v:
            dead[sl] = None; continue
        after = [t for t in T if t > v[-1][0]]
        dead[sl] = after[0] if len(after) >= 3 else None

    def hp_at(sl, t):
        v = hp.get(sl)
        if not v: return None
        if dead[sl] is not None and t >= dead[sl]: return 0
        i = bisect.bisect_right([x[0] for x in v], t)
        return v[0][1] if i == 0 else v[i - 1][1]

    def kind_at(sl, t):
        v = kind.get(sl)
        if not v: return None
        i = bisect.bisect_right([x[0] for x in v], t)
        return v[0][1] if i == 0 else v[i - 1][1]

    end = T[-1]
    lost = lambda keys, t0, t1: sum(max(0, (hp_at(k, t0) or 0) - (hp_at(k, t1) or 0)) for k in keys if hp.get(k))  # noqa: E731
    cm = min(3, sum(dead[k] is not None for k in ("eL", "eR")) + 3 * (dead["eK"] is not None))
    co = min(3, sum(dead[k] is not None for k in ("mL", "mR")) + 3 * (dead["mK"] is not None))
    fin = {k: (0 if dead[k] is not None else v[-1][1]) for k, v in hp.items()}
    a = min([fin[k] for k in ("eK", "eL", "eR") if fin.get(k)] or [0]); b_ = min([fin[k] for k in ("mK", "mL", "mR") if fin.get(k)] or [0])
    derived = "WIN" if cm > co else "LOSS" if cm < co else ("WIN" if a < b_ else "LOSS" if a > b_ else "DRAW")

    plays = r["plays"]; conf = r["conf"]; used = set()
    for p in plays:
        p["conf"] = None
        for i, c in enumerate(conf):
            if i not in used and c["name"] == p["name"] and 0 <= c["tick"] - p["tick"] < 200:
                used.add(i); p["conf"] = c; break
        p["X"], p["Y"] = R.model_to_own(p["xy"]) if p["xy"] else (None, None)

    def opp_spent(t0, t1):              # public counter drops beyond regen (review.opp_spent_counter, windowed)
        k0, k1 = bisect.bisect_left(T, t0), bisect.bisect_right(T, t1)
        out = 0.0
        for a1, b1 in zip(S[k0:k1], S[k0 + 1:k1]):
            if a1[2] is not None and b1[2] is not None:
                out += max(0.0, min(a1[2] + (b1[0] - a1[0]) * R.REGEN[R.ph(a1[0])], 10.0) - b1[2])
        return out

    my_xbow = collections.defaultdict(list)
    for s in S:
        for b in s[4]:
            if b[0] and b[3] != -1 and R.nm(b[3]) == "Xbow" and b[4] > 0:
                my_xbow[b[7]].append((s[0], b[1], b[2], b[4]))
    rows = []
    for p in plays:
        if not p["conf"] or p["X"] is None or p["name"] not in ("Xbow", "Rocket"):
            continue
        t = p["conf"]["tick"]; X, Y = p["X"], p["Y"]
        alive = {k: bool(hp_at(k, t)) for k in R.EN_T}
        down = [k for k in ("eL", "eR") if not alive[k] and hp.get(k)]
        row = dict(file=r["file"], ckpt=FAMILY(ckpt), card=p["name"], t=t, ph=R.ph(t), X=round(X, 2), Y=round(Y, 2),
                   down=down, crowns=[sum(not alive[k] for k in ("eL", "eR")), sum(dead[k] is not None and dead[k] <= t for k in ("mL", "mR"))],
                   el=p["el"], my20=lost(("mL", "mR", "mK"), t, min(end, t + 400)), opp10=round(opp_spent(t, t + 200), 2),
                   result=derived, lethal_opt=do.get("lethal_rocket"), king_kind=kind_at("eK", t))
        if p["name"] == "Xbow":
            reach = {k: math.hypot(X - R.EN_T[k][0], Y - R.EN_T[k][1]) <= R.REACH for k in R.EN_T}
            off = any(reach[k] and alive[k] for k in R.EN_T)
            off_p = any(reach[k] and alive[k] for k in ("eL", "eR"))
            lane = "eL" if X < 9 else "eR"
            lane_dead = not alive[lane] and bool(hp.get(lane))
            body = None
            for addr, v in my_xbow.items():
                if abs(v[0][0] - t) <= 60 and math.hypot(v[0][1] - X, v[0][2] - Y) <= 3.0:
                    body = v; break
            died = body[-1][0] if body else t + 600
            nearest = min((k for k in R.EN_T if alive[k]), key=lambda k: math.hypot(X - R.EN_T[k][0], Y - R.EN_T[k][1]), default=None)
            row.update(cls="KONLY" if off and not off_p else "OFF_P" if off_p else "DL_DEF" if lane_dead else "DEF",
                       dl_off_literal=lane_dead and off, lane_dead=lane_dead, king_nearest_in_reach=off and nearest == "eK",
                       life=(body[-1][0] - body[0][0]) / TPS if body else None,
                       king_dmg=lost(("eK",), t, min(end, died)), tower_dmg=lost(("eK", "eL", "eR"), t, min(end, died)))
        else:
            row.update(cls="ROCKET", tower_dmg=lost(("eK", "eL", "eR"), t, min(end, t + 120)),
                       king_dmg=lost(("eK",), t, min(end, t + 120)),
                       on_tower=any(alive[k] and math.hypot(X - R.EN_T[k][0], Y - R.EN_T[k][1]) <= 3.0 for k in R.EN_T),
                       my_half=Y <= 18)
        rows.append(row)
    return dict(file=r["file"], ckpt=FAMILY(ckpt), result=derived, end=end, plays=rows,
                ot=end >= 3600, eprin_down_s={k: (dead[k] / TPS if dead[k] is not None else None) for k in ("eL", "eR")})


def mean(v):
    v = [x for x in v if x is not None]
    return sum(v) / len(v) if v else float("nan")


def main():
    names, costs, uv = R._catalog(); R.NAME.update(names); R.NCOST.update(costs); R.UV.update(uv)
    pat = sys.argv[sys.argv.index("--glob") + 1] if "--glob" in sys.argv else R.LOGDIR + "live_play_2026100[5-8]_*.jsonl"
    out = []
    for i, f in enumerate(sorted(glob.glob(pat))):
        try:
            m = analyse(f)
        except Exception as e:   # noqa: BLE001 -- one bad log must not stop the census
            print("skip", os.path.basename(f), type(e).__name__, e); continue
        if m: out.append(m)
    with open(os.path.join(HERE, "live_matches.jsonl"), "w") as fh:
        for m in out: fh.write(json.dumps(m) + "\n")
    for fam in ("towerref_w2", "ALL"):
        ms = [m for m in out if fam == "ALL" or m["ckpt"] == fam]
        P = [p for m in ms for p in m["plays"]]
        print(f"\n=== {fam}: {len(ms)} matches, {sum(m['ot'] for m in ms)} reached OT, "
              f"{sum(bool(m['eprin_down_s']['eL'] or m['eprin_down_s']['eR']) for m in ms)} with an enemy princess down")
        print("X-Bows per match by class x phase (1x/2x/OT):")
        for c in ("KONLY", "OFF_P", "DL_DEF", "DEF"):
            n = [sum(p.get("cls") == c and p["ph"] == ph for p in P) for ph in ("1x", "2x", "OT")]
            print(f"  {c:7s} {n} total {sum(n)} = {sum(n) / max(1, len(ms)):.3f}/match")
        lit = [p for p in P if p.get("dl_off_literal")]
        print(f"  literal DL_OFF {len(lit)} (of which KONLY {sum(p['cls'] == 'KONLY' for p in lit)}); "
              f"KONLY-or-king-nearest {sum(p.get('cls') == 'KONLY' or p.get('king_nearest_in_reach', False) for p in P)}")
        print("Value in states with an enemy princess down (cls: n | life s | king dmg | all-tower dmg | my dmg 20 s | opp spent 10 s | king awake):")
        for c in ("KONLY", "OFF_P", "DL_DEF", "DEF", "ROCKET"):
            for ph in ("1x", "2x", "OT", None):
                q = [p for p in P if p["cls"] == c and p["down"] and (ph is None or p["ph"] == ph)]
                if not q: continue
                print(f"  {c:7s} {ph or 'all':3s} n={len(q):4d} life={mean([p.get('life') for p in q]):5.1f} "
                      f"king={mean([p['king_dmg'] for p in q]):6.0f} towers={mean([p['tower_dmg'] for p in q]):6.0f} "
                      f"my20={mean([p['my20'] for p in q]):6.0f} opp10={mean([p['opp10'] for p in q]):4.2f} "
                      f"awake={mean([p['king_kind'] == 13 for p in q]):.2f} win={mean([p['result'] == 'WIN' for p in q]):.2f}")


if __name__ == "__main__":
    main()
