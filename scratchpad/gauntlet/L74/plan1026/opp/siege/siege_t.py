"""OPP-SIEGE2 task 1b: what our reach X-Bow shoots and what happens to the opponent's answer, from SIM board targets
(rows recorded with the pod-only probe SIEGE_TGT=1: hab sample s[8] = [[uid, team, kind, target_uid], ...]).

    python -I siege_t.py NAME=ROWS_DIR [...]     -> out/siege_t_<NAME>.json + a table

Per reach X-Bow (siege_b.sim_xbows + classify: the same X-Bows, classes and lock outcome), from the 1-s samples while the
X-Bow lives (<= 600 ticks): its FIRST target (enemy tower / the on-time answer's bodies / another enemy body / none seen),
ticks from landing to the first tower shot-target, the share of its live samples on a tower; the answer bodies (new enemy
uids named as the answer card, appearing between its landing and 40 ticks after the record tick): did the X-Bow ever target
them, did they ever target the X-Bow, alive when the X-Bow died (or at 600)."""
from __future__ import annotations

import json
import math
import re
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[2] / "opp_model/humanlike"), str(HERE.parents[2] / "succ48")]
import siege_b as SB  # noqa: E402
import xbow_count as XC  # noqa: E402

XB_RANGE = 11.5             # tiles (X-Bow range), centre to play point; ponytail: ignores body radii
TOWER_KINDS = (2, 3)        # facade entity kinds: 0 troop, 1 building, 2 king, 3 princess (checked on tgtR rows)
nrm = lambda s: re.sub(r"[^a-z0-9]", "", str(s).lower())  # noqa: E731


def one(r, h, xs, res):
    smp = [s for s in h["samples"] if len(s) > 8]
    if not smp:
        return []
    L = int(h["L"])
    tower = {u for u, tm, k, tg in smp[0][8] if k in TOWER_KINDS and tm != L}
    out = []
    xb_seen, en_seen = {}, {}
    for s in smp:
        for e in s[7]:
            xb_seen.setdefault(e[0], (s[0], e[2], e[3]))
        for e in s[6]:
            en_seen.setdefault(e[0], (s[0], e[1]))
    own = [q for q in h["own"] if q[3] and "bow" in str(q[2]).lower().replace("-", "")]
    k = 0
    for q in own:
        t0 = int(q[1] if q[1] is not None else q[0])
        if k >= len(xs) or xs[k][0] != t0:
            continue
        rec = dict(res[k])
        k += 1
        cand = [(math.hypot(x - q[8], y - q[9]), u) for u, (ft, x, y) in xb_seen.items()
                if t0 <= ft <= t0 + 60]
        if not cand:
            rec["xb_uid"] = None
            out.append(rec)
            continue
        U = min(cand)[1]
        ans = set()
        if rec["cls"] == "answer_ontime":
            land, last = rec["t"] + rec["dt"] - 20, rec["t"] + rec["dt"] + 40
            ans = {u for u, v in en_seen.items() if land <= v[0] <= last
                   and (nrm(v[1]) in nrm(rec["card"]) or nrm(rec["card"]) in nrm(v[1]))}
        tl, alive_ans, death = [], set(), None
        def_unit = def_tower = False   # did one of OUR (CLXIII) bodies / towers target an answer body while the X-Bow lived
        s0 = next((s for s in smp if s[0] >= t0), None)
        rec["own_bodies_t0"] = sum(1 for e in s0[8] if e[1] == L and e[2] in (0, 1)) - 1 if s0 else None  # minus this X-Bow
        rec["opp_bodies_t0"] = sum(1 for e in s0[8] if e[1] != L and e[2] in (0, 1)) if s0 else None
        for s in smp:
            if not t0 <= s[0] <= t0 + XC.WINDOW:
                continue
            ents = {e[0]: e for e in s[8]}
            if U not in ents:
                if tl:
                    death = s[0]
                    break
                continue
            tl.append((s[0], ents[U][3]))
            alive_ans = {a for a in ans if a in ents}
            for e in s[8]:
                if e[1] == L and e[0] != U and e[3] in ans:
                    def_tower |= e[2] in TOWER_KINDS
                    def_unit |= e[2] not in TOWER_KINDS
            if any(ents[a][3] == U for a in ans if a in ents):
                rec["ans_hits_xb"] = True
        tg = [(t, g) for t, g in tl if g >= 0]
        cls = lambda g: "tower" if g in tower else "answer" if g in ans else "other"  # noqa: E731
        life_end = death or (tl[-1][0] if tl else t0)
        ft0 = rec["t"] + rec["dt"] if rec["cls"] == "answer_ontime" else t0
        rec["n_xb_targets"] = len({g for _, g in tg if g not in tower})      # distinct enemy bodies the X-Bow shot at
        rec["plays_in_range_after"] = sum(1 for p in r["plays"] if ft0 < p[0] <= life_end and   # opponent plays after the
                                          math.hypot(p[3] - rec["xx"], p[4] - rec["xy"]) <= XB_RANGE)  # answer, in X-Bow range
        rec.update(xb_uid=U, xb_life=(death or (tl[-1][0] if tl else t0)) - t0, xb_died=death is not None,
                   first_target=cls(tg[0][1]) if tg else "none", first_target_dt=tg[0][0] - t0 if tg else None,
                   tower_dt=next((t - t0 for t, g in tg if g in tower), None),
                   tower_share=sum(g in tower for _, g in tl) / len(tl) if tl else 0.0,
                   xb_hit_ans=any(g in ans for _, g in tg), n_ans=len(ans),
                   ans_alive_end=bool(alive_ans) if ans else None, ans_hits_xb=rec.get("ans_hits_xb", False),
                   def_unit=def_unit, def_tower=def_tower)
        out.append(rec)
    return out


def table(rs):
    fr = lambda s: round(sum(s) / len(s), 3) if s else None  # noqa: E731
    t = {"xbows": len(rs), "with_uid": sum(r.get("xb_uid") is not None for r in rs), "lock": fr([r["locked"] for r in rs])}
    ok = [r for r in rs if r.get("xb_uid") is not None]
    for grp, sel in (("all", ok), ("ontime_unit", [r for r in ok if r["cls"] == "answer_ontime" and r["kind"] != "spell"])):
        g = {}
        for ft in ("tower", "answer", "other", "none"):
            s = [r for r in sel if r["first_target"] == ft]
            g[f"first_{ft}"] = {"share": fr([1] * len(s) + [0] * (len(sel) - len(s))), "lock": fr([r["locked"] for r in s]), "n": len(s)}
        g["n_xb_targets_mean"] = fr([r["n_xb_targets"] for r in sel])
        g["plays_in_range_after_mean"] = fr([r["plays_in_range_after"] for r in sel])
        g["xb_ever_tower"] = fr([r["tower_dt"] is not None for r in sel])
        g["lock_if_never_tower"] = fr([r["locked"] for r in sel if r["tower_dt"] is None])
        g["tower_dt_q"] = st.quantiles([r["tower_dt"] for r in sel if r["tower_dt"] is not None], n=4) if len(sel) > 4 else None
        g["tower_share_of_life_mean"] = fr([r["tower_share"] for r in sel])
        g["tower_dt_median"] = st.median([r["tower_dt"] for r in sel if r["tower_dt"] is not None]) if sel else None
        g["xb_life_median"] = st.median([r["xb_life"] for r in sel]) if sel else None
        g["xb_died_share"] = fr([r["xb_died"] for r in sel])
        if grp == "ontime_unit":
            a = [r for r in sel if r["n_ans"]]
            g["answer_bodies_found"] = fr([bool(r["n_ans"]) for r in sel])
            g["own_bodies_t0_mean"] = fr([r["own_bodies_t0"] for r in sel if r["own_bodies_t0"] is not None])
            g["opp_bodies_t0_mean"] = fr([r["opp_bodies_t0"] for r in sel if r["opp_bodies_t0"] is not None])
            for key in ("xb_hit_ans", "ans_hits_xb", "ans_alive_end", "def_unit", "def_tower"):
                g[key] = {"share": fr([r[key] for r in a]), "lock_if": fr([r["locked"] for r in a if r[key]]),
                          "lock_ifnot": fr([r["locked"] for r in a if not r[key]])}
        t[grp] = g
    per = defaultdict(list)
    for r in ok:
        if r["cls"] == "answer_ontime":
            per[r["card"]].append(r)
    t["per_card"] = {c: {"n": len(v), "lock": fr([r["locked"] for r in v]), "first_tower": fr([r["first_target"] == "tower" for r in v]),
                         "first_answer": fr([r["first_target"] == "answer" for r in v]), "xb_hit_ans": fr([r.get("xb_hit_ans") for r in v]),
                         "ans_hits_xb": fr([r.get("ans_hits_xb") for r in v]), "ans_alive": fr([r["ans_alive_end"] for r in v if r["ans_alive_end"] is not None]),
                         "tower_share": fr([r["tower_share"] for r in v])}
                     for c, v in sorted(per.items(), key=lambda kv: -len(kv[1]))[:12]}
    return t


def main(argv):
    for a in argv:
        name, root = a.split("=", 1)
        data = SB.sim_xbows(root)
        rs = []
        for (r, xs), (_, h) in zip(data, XC.rows(root)):
            rs += one(r, h, xs, SB.classify(r, xs))
        t = table(rs)
        (SB.OUT / f"siege_t_{name}.json").write_text(json.dumps({"table": t, "xbows": rs}))
        print(name, json.dumps(t, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
