"""OPP-SIEGE test 2 (closed loop): what the opponent does after each of OUR reach X-Bows, live humans vs SIM opponents.

    icebow/.venv/Scripts/python.exe -I siege_b.py live                      # CLXIII calibration block (card.live_records)
    icebow/.venv/Scripts/python.exe -I siege_b.py sim NAME=ROWS_DIR ...      # run_closed.sh rows (card.sim_records)
    -> out/siege_b_<name>.json (per-X-Bow records + the table)

Plays + their ticks come from card.py's records (one code path; SIM plays at land + 20 = when the live detector could see
them, bodiless spells dropped in SIM as live cannot see them).  Per reach X-Bow at t (our command tick) with its lock outcome
(card.py's rule: an enemy princess loses >= 5% of max HP in 30 s), the opponent's response is ONE class:
  answer_ontime  first opponent play in (t, t+80] in the X-Bow's lane (x on its side of the centre) within 12 tiles
                 (= match_memory's X-Bow answer rule), split by the answer card's kind (building / spell / troop)
  answer_late    no on-time answer, but such a play in (t+80, t+200]
  elsewhere      plays in (t, t+200], none of them in lane within 12 tiles
  none           no opponent play in (t, t+200]
+ 'spent_5s' = elixir the opponent played in [t-100, t] (elixir-starved proxy, both sources identical).
ponytail: the X-Bow lane / position comes from match_memory events (live) and the board record (SIM)."""
from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
HUM = HERE.parents[2] / "opp_model/humanlike"
sys.path[:0] = [str(HUM)]
import card as CD  # noqa: E402

OUT = HERE / "out"
T_ON, T_ALL, R_ANS = 80, 200, 12.0


def kind(key):
    import opp_behaviour as OB
    k = (OB.catalog()[0].get(key) or ("",))[0]
    return k if k in ("spell", "building") else "troop"


def live_xbows():
    """CLXIII calibration block: per log, reach X-Bows [(tick, x, y, locked)] in card.py's record frame (tiles, us at low y)."""
    import live_dump as LD
    from pipeline import match_memory as M
    cache = OUT / "live_xb_pos2.json"
    pos = json.loads(cache.read_text()) if cache.exists() else {}
    recs = CD.live_records("calibration")
    for r in recs:
        if r["id"] in pos or not r.get("xb"):
            continue
        m = LD.read(CD.LOGS / r["id"])
        ev = M.build(m["side"], m["samples"], m["plays"]).events(m["last"] + 1)
        pos[r["id"]] = [[int(e["tick"]), 18 * e["xy"][0], 32 * (1 - e["xy"][1]), e["xb"]["damage"]] for e in ev
                        if e["type"] == "play" and e["mine"] and e["card"] == "x-bow" and e.get("reach") and e.get("xb")
                        and e["xy"] is not None]
    OUT.mkdir(exist_ok=True)
    cache.write_text(json.dumps(pos))
    out = []
    for r in recs:
        if not r.get("xb"):
            continue
        p = {t: (x, y, d) for t, x, y, d in pos.get(r["id"], [])}
        out.append((r, [(t, *p[t][:2], lk, p[t][2]) for t, lk in r["xb"] if t in p]))
    return out


def sim_xbows(root):
    """run_closed rows: card.sim_records (plays) + the reach X-Bows with their engine position (= card.xb_sim's set)."""
    import xbow_count as XC
    recs = CD.sim_records(root, live_visible=not os.environ.get("SIEGE_ALL"))   # SIEGE_ALL=1: keep bodiless spells
    out = []
    for r, (_, h) in zip(recs, XC.rows(str(root))):
        mir = bool(h["mirror"][0])
        fr = (lambda X, Y: (18 - X / 1000, 32 - Y / 1000)) if mir else (lambda X, Y: (X / 1000, Y / 1000))
        seq = {t: lk for t, lk in r["xb"]}
        series = {}
        for s_ in h["samples"]:
            for t_ in s_[5]:
                if t_[0] != h["L"] and t_[1] != "k":
                    series.setdefault(XC.tiles(t_[2], t_[3]), []).append((s_[0], t_[4]))
        xs = []
        for q in h["own"]:
            if not q[3] or "bow" not in str(q[2]).lower().replace("-", ""):
                continue
            t0 = int(q[1] if q[1] is not None else q[0])
            if t0 in seq:
                X, Y = XC.tiles(q[8], q[9])
                dmg = 0.0                                    # = match_memory._xbow: sum over reach princesses of HP share lost
                for pos, ser in series.items():
                    hp0 = next((hp for t, hp in reversed(ser) if t <= t0), None)
                    if hp0 and hp0 > 0 and math.hypot(X - pos[0], Y - pos[1]) <= XC.REACH:
                        lt = [hp for t, hp in ser if t0 < t <= t0 + XC.WINDOW]
                        if lt:
                            dmg += max(0.0, (hp0 - min(lt)) / max(hp for _, hp in ser))
                xs.append((t0, *fr(q[8], q[9]), seq[t0], dmg))
        out.append((r, xs))
    return out


def classify(r, xs):
    P = sorted(r["plays"], key=lambda p: p[0])
    res = []
    for t, x, y, lk, dmg in xs:
        w = [p for p in P if t < p[0] <= t + T_ALL]
        near = [p for p in w if (p[3] < 9) == (x < 9) and math.hypot(p[3] - x, p[4] - y) <= R_ANS]
        on = [p for p in near if p[0] <= t + T_ON]
        if on:
            c, a = "answer_ontime", on[0]
        elif near:
            c, a = "answer_late", near[0]
        elif w:
            c, a = "elsewhere", w[0]
        else:
            c, a = "none", None
        res.append(dict(id=r["id"], t=t, locked=lk, dmg=round(dmg, 4), cls=c, card=a[1] if a else None, kind=kind(a[1]) if a else None,
                        dt=(a[0] - t) if a else None,
                        dist=round(math.hypot(a[3] - x, a[4] - y), 2) if a else None, ax=a[3] if a else None,
                        ay=a[4] if a else None, xx=round(x, 2), xy=round(y, 2), first_dt=(w[0][0] - t) if w else None, n_plays_10s=len(w),
                        spent_5s=sum(p[2] for p in P if t - 100 <= p[0] <= t),
                        own_plays_10s=sum(t < m <= t + T_ALL for m in r["mine"]),
                        opp_spent_10s=sum(p[2] for p in w)))
    return res


def table(rs):
    n = len(rs)
    tab = {"xbows": n, "lock_rate": sum(r["locked"] for r in rs) / n if n else None}
    cl = Counter()
    lk = defaultdict(list)
    for r in rs:
        k = r["cls"] if r["cls"] != "answer_ontime" else f"answer_ontime_{r['kind']}"
        cl[k] += 1
        lk[k].append(r["locked"])
    tab["classes"] = {k: {"n": v, "share": v / n, "lock_rate": sum(lk[k]) / len(lk[k])} for k, v in sorted(cl.items())}
    dts = sorted(r["dt"] for r in rs if r["cls"] == "answer_ontime")
    tab["ontime_answer_dt_median"] = dts[len(dts) // 2] if dts else None
    for name, f in (("starved_spent_ge4", lambda r: r["spent_5s"] >= 4), ("not_starved", lambda r: r["spent_5s"] < 4)):
        s = [r for r in rs if f(r)]
        tab[name] = {"n": len(s), "share": len(s) / n if n else None,
                     "lock_rate": sum(r["locked"] for r in s) / len(s) if s else None,
                     "none_or_elsewhere": sum(r["cls"] in ("none", "elsewhere") for r in s) / len(s) if s else None}
    tab["ontime_answer_cards_top12"] = Counter(r["card"] for r in rs if r["cls"] == "answer_ontime").most_common(12)
    return tab


def main(argv):
    OUT.mkdir(exist_ok=True)
    jobs = [("live", None)] if argv[0] == "live" else [tuple(a.split("=", 1)) for a in argv[1:]]
    for name, root in jobs:
        data = live_xbows() if root is None else sim_xbows(root)
        rs = [x for r, xs in data for x in classify(r, xs)]
        t = table(rs)
        (OUT / f"siege_b_{name}.json").write_text(json.dumps({"table": t, "xbows": rs}))
        print(name, json.dumps(t, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
