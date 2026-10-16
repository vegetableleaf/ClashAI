"""B) First-hit delays measured from the live frame logs (10-16 logs carry ents_state + proj), per card.

    research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L74/parity/first_hit/measure.py [out.json]

Reads ALREADY-DECODED JSON only (frame events: ents / ents_state / proj; see READER_VALIDATION_1016.md). No layout, no
addresses printed (an address is only the in-frame join key between proj.source and ents). Bodies are keyed by the
generation id ents_state[3]. Opponent hand/next/elixir are never read. Frames are ~2 ticks apart (96.8%), so every
delay carries about +-1 tick of sampling error; compare medians with that in mind.

Definitions (tick = 50 ms):
  entry   = first frame of a body in behavior_state_raw 2 (engaged) after a frame in another state.
  ranged  = first projectile row whose source is that body (first sight of its shot key), minus entry.
            Tower runs are the same, one per idle-to-engaged edge after >= 40 idle ticks (fresh load timer).
            Only a body's FIRST run counts for troops (it leaves its deploy with the load timer at 0).
  melee   = first hp drop of any enemy body inside reach at entry, minus entry, reach = Range + both radii + 0.4 tile.
            Kept only when the drop equals the card's modal first-drop (self-calibrated damage), so another unit's
            damage on the same victim is mostly rejected.
  SIM first-hit prediction = (HitSpeed - LoadTime) / 50 - 1 ticks after entry (engine docs, combat.rs
  attack_step_progress: measured on the 15.535.29 corpus, 911 of 1004 projectile units exact); cadence = HitSpeed / 50.
"""
from __future__ import annotations

import collections
import glob
import json
import math
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))
LOGS = REPO / "scratchpad/gauntlet/L68/live_reader"
SIM_NEW = REPO / "research/ext/Royale/RoyaleSim/data/derived/cards-160402017-20261006.json"   # table the runtime really runs
SIM_OLD = REPO / "research/ext/Royale/RoyaleSim/data/derived/cards-15.535.json"              # embedded default of the wheel
LIVE = REPO / "scratchpad/gauntlet/L74/apktables/out/device_builds/20261012T221627332682Z-50188/cards.json"
MAIN_PRINCESS_HP = {4424, 3052}     # own princess tower hp at the first frame: main account (ladder 4424; owner classic battles 3052). 4392 / 4656 = bait account
TOWER_X_KING = 9000
IDLE_TOWER = 40                     # idle ticks before a tower run counts as a fresh edge


def norm(s: str) -> str:
    return "".join(c for c in s.lower() if c.isalnum())


class Table:
    """card display name -> (unit row) for one cards.json; plus unit rows by name."""

    def __init__(self, path):
        d = json.load(open(path, encoding="utf-8"))
        self.units = dict(d["units"])
        for key in ("hero_forms", "evolutions"):
            for c in d.get(key) or []:
                for n, u in ((c.get("tables") or {}).get("units") or {}).items():
                    self.units.setdefault(n, u)
        self.by_card, self.card = {}, {}
        for c in d["cards"]:
            u = self.units.get(c.get("summon_character"))
            if u is not None:
                for k in (norm(c["display_name"]), norm(c["name"])):
                    self.by_card[k] = u
                    self.card[k] = c
        self.towers = {t["name"]: t for t in d.get("towers") or []}

    def rows_for(self, name: str, ranged: bool):
        """unit rows of a card (summon, second summon, spawner, death spawn) that shoot (ranged) or do not"""
        if name in self.towers:
            return [(name, self.towers[name])]
        c = self.card.get(norm(name))
        names = [c.get("summon_character")] if c else [name]
        if c:
            for k in ("second_summon", "spawner", "death_spawn"):
                if isinstance(c.get(k), dict) and c[k].get("character"):
                    names.append(c[k]["character"])
        out = []
        for n in names:
            u = self.units.get(n)
            if u and u.get("hit_speed_ms") and bool(u.get("projectile")) == ranged:
                out.append((n, u))
        return out

    def row(self, name: str):
        if name in self.towers:
            return self.towers[name]
        return self.by_card.get(norm(name)) or self.units.get(name)


def sim_first(row):
    """predicted first-shot delay (ticks after entry) and cadence (ticks)"""
    if not row or not row.get("hit_speed_ms"):
        return None, None
    hs, lt = row["hit_speed_ms"], max(row.get("load_time_ms") or 0, 0)
    return (hs - lt) / 50 - 1, hs / 50


def main_logs():
    """10-16 frame logs (those with ents_state) of the main icebow account."""
    from pipeline.obs_contract import _catalog_names
    cat = _catalog_names()
    out = []
    for f in sorted(glob.glob(str(LOGS / "live_play_2026101[56]_*.jsonl"))):
        fr = []
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                if '"event": "frame"' in line:
                    e = json.loads(line)
                    if "ents_state" in e:
                        fr.append(e)
        if len(fr) < 400:
            continue
        ms = fr[0]["my_side"]
        pr = [e[4] for e in fr[0]["ents"] if e[3] == -1 and e[0] == ms and e[1] in (3500, 14500)]
        own = {cat.get(e[3]) for x in fr[::50] for e in x["ents"] if e[0] == ms}
        ok = bool(pr) and pr[0] in MAIN_PRINCESS_HP and bool(own & {"X-Bow", "Xbow", "Tesla"})
        out.append((f, fr, ok, pr[0] if pr else None))
    return cat, out


def tracks(fr, cat):
    """gen -> dict(name, side, rows=[(tick, x, y, hp, state)]) ; also proj shots by gen"""
    byt = {}
    for x in fr:
        byt[x["tick"]] = x                                   # frames with a repeated tick: keep the last
    body, shots = {}, collections.defaultdict(dict)          # gen -> {gk: first tick}
    for t in sorted(byt):
        x = byt[t]
        a2 = {}
        for e, s in zip(x["ents"], x["ents_state"]):
            g = s[3]
            a2[e[7]] = g
            b = body.get(g)
            if b is None:
                if e[3] == -1:
                    nm = "KingTower" if abs(e[1] - TOWER_X_KING) < 1500 else "PrincessTower"
                else:
                    nm = cat.get(e[3], str(e[3])) + ("_evo" if s[1] else "")
                b = body[g] = {"name": nm, "side": e[0], "rows": [], "cid": e[3]}
            b["rows"].append((t, e[1], e[2], e[4], s[0]))
        for p in x["proj"]:
            g = a2.get(p[8])
            if g is not None:
                shots[g].setdefault(p[7], t)
    return body, shots


def runs_of_two(rows):
    """[(i_first, i_last)] runs of state 2 whose previous frame exists and is another state"""
    out, i, n = [], 0, len(rows)
    while i < n:
        if rows[i][4] == 2 and i > 0 and rows[i - 1][4] != 2:
            j = i
            while j + 1 < n and rows[j + 1][4] == 2:
                j += 1
            out.append((i, j))
            i = j + 1
        else:
            i += 1
    return out


def collect(logs, cat, tab):
    ev = []          # dicts: kind, name, delay, [drop]
    cad = collections.defaultdict(list)
    for path, fr, ok, _ in logs:
        if not ok:
            continue
        body, shots = tracks(fr, cat)
        enemy_rows = {g: b for g, b in body.items()}
        for g, b in body.items():
            nm = b["name"]
            ranged = g in shots
            cands = tab.rows_for(nm, ranged)
            if not cands:
                continue
            row = cands[0][1]
            hs = row["hit_speed_ms"] / 50
            rows = b["rows"]
            runs = runs_of_two(rows)
            is_tower = b["cid"] == -1
            if not is_tower:
                runs = runs[:1]
            for (i, j) in runs:
                t0 = rows[i][0]
                if is_tower:
                    # idle edge: previous frames all state != 2 for >= IDLE_TOWER ticks
                    k, idle0 = i - 1, None
                    while k >= 0 and rows[k][4] != 2:
                        idle0 = rows[k][0]
                        k -= 1
                    if k < 0:
                        idle0 = rows[0][0] - IDLE_TOWER      # idle since the log began (game start, load timer 0)
                    if idle0 is None or t0 - idle0 < IDLE_TOWER:
                        continue
                t1 = rows[j][0] + 2
                if ranged and g in shots:
                    firsts = sorted(t for t in shots[g].values())
                    inrun = [t for t in firsts if t0 <= t <= t1]
                    if inrun:
                        d = inrun[0] - t0
                        if d <= hs + 4:
                            ev.append({"kind": "ranged", "name": nm, "delay": d, "tick": t0, "log": Path(path).stem[-6:]})
                        for a, c in zip(inrun, inrun[1:]):
                            if c - a <= hs + 3:
                                cad[nm].append(c - a)
                elif not ranged:
                    # melee: enemy bodies in reach at entry
                    ra = row.get("collision_radius_milli") or 500
                    reach0 = (row.get("range_milli") or 1000) + ra
                    cand = []
                    for g2, b2 in enemy_rows.items():
                        if b2["side"] == b["side"]:
                            continue
                        r2 = b2["rows"]
                        # position of the candidate at the entry tick
                        pr = next((r for r in r2 if r[0] == t0), None)
                        if pr is None:
                            continue
                        v = tab.row(b2["name"])
                        rv = (v.get("collision_radius_milli") if v else None) or (1400 if b2["cid"] == -1 else 500)
                        if math.hypot(pr[1] - rows[i][1], pr[2] - rows[i][2]) <= reach0 + rv + 400:
                            cand.append(g2)
                    best = None
                    for g2 in cand:
                        r2 = body[g2]["rows"]
                        # crowded: another own-side non-tower body within 3 tiles of the victim at entry (hits would mix)
                        vp = next((r for r in r2 if r[0] == t0), None)
                        if vp is None:
                            continue
                        crowd = 0
                        for g3, b3 in body.items():
                            if g3 != g and b3["side"] == b["side"] and b3["cid"] != -1:
                                q = next((r for r in b3["rows"] if r[0] == t0), None)
                                if q and math.hypot(q[1] - vp[1], q[2] - vp[2]) <= 3000:
                                    crowd += 1
                        drops = []
                        for k in range(1, len(r2)):
                            if r2[k][3] < r2[k - 1][3] and t0 <= r2[k][0] <= t0 + 2 * hs + 8:
                                iso = (k < 2 or r2[k - 1][3] == r2[k - 2][3]) and (k + 1 >= len(r2) or r2[k + 1][3] == r2[k][3])
                                if iso:                              # a DOT (poison, burn) drops every frame: not a hit
                                    drops.append((r2[k][0], r2[k - 1][3] - r2[k][3]))
                        for (ta, da) in drops:
                            # a hit chain: the same drop again one HitSpeed later (+-2 ticks: 2-tick frames)
                            if ta - t0 <= hs + 6 and any(db == da and abs((tb - ta) - hs) <= 2 for tb, db in drops):
                                if best is None or ta < best[0]:
                                    best = (ta, da, body[g2]["name"], crowd)
                                break
                    if best:
                        ev.append({"kind": "melee" if best[3] == 0 else "melee_crowded", "name": nm, "delay": best[0] - t0,
                                   "drop": best[1], "victim": best[2], "tick": t0, "log": Path(path).stem[-6:]})
                    else:
                        ev.append({"kind": "melee_nohit", "name": nm, "tick": t0, "log": Path(path).stem[-6:]})
    return ev, cad


def deploy_lengths(logs, cat, tab):
    """card -> [state-4 run length in ticks] for bodies whose first frame is in state 4 (start known to ~2 ticks)"""
    out = collections.defaultdict(list)
    for path, fr, ok, _ in logs:
        if not ok:
            continue
        body, _ = tracks(fr, cat)
        for g, b in body.items():
            rows = b["rows"]
            if b["cid"] == -1 or rows[0][4] != 4 or rows[0][0] < 160:
                continue
            k = 0
            while k < len(rows) and rows[k][4] in (4, 11):
                k += 1
            if 0 < k < len(rows):
                out[b["name"]].append(rows[k][0] - rows[0][0])
    return out


def summarize(ev, cad, tabs):
    by = collections.defaultdict(list)
    for e in ev:
        by[(e["name"], "melee" if e["kind"] == "melee_nohit" else e["kind"])].append(e)
    rows = []
    for (nm, kind), es in sorted(by.items()):
        hit = [e for e in es if e["kind"] in ("ranged", "melee", "melee_crowded")]
        if not hit:
            continue
        if kind.startswith("melee"):
            c = collections.Counter(e["drop"] for e in hit)
            thr = max(3, 0.25 * len(hit))
            keep_drops = {d for d, k in c.items() if k >= thr}
            kept = [e for e in hit if e["drop"] in keep_drops]
        else:
            kept = hit
        if not kept:
            continue
        d = sorted(e["delay"] for e in kept)
        mode, mn = collections.Counter(d).most_common(1)[0]
        near = sum(1 for x in d if abs(x - mode) <= 1)
        r = {"name": nm, "kind": kind, "n": len(d), "n_all_runs": len(es), "median": st.median(d),
             "q1": d[len(d) // 4], "q3": d[(3 * len(d)) // 4], "mode": mode, "mode_share_pm1": round(near / len(d), 2),
             "cadence_median": st.median(cad[nm]) if cad.get(nm) else None, "cadence_n": len(cad.get(nm, []))}
        for lab, t in tabs.items():
            ex = [sim_first(u) for _, u in t.rows_for(nm, kind == "ranged")]
            r[lab] = ex[0][0] if ex else None
            r[lab + "_cadence"] = ex[0][1] if ex else None
            r[lab + "_all"] = sorted({e[0] for e in ex})
            r[lab + "_units"] = [n for n, _ in t.rows_for(nm, kind == "ranged")]
        rows.append(r)
    return rows


def main(out=None):
    cat, logs = main_logs()
    tabs = {"sim_eff": Table(SIM_NEW), "sim_old": Table(SIM_OLD), "live": Table(LIVE)}
    ev, cad = collect(logs, cat, tabs["sim_eff"])
    rows = summarize(ev, cad, tabs)
    dep = {}
    for nm, v in deploy_lengths(logs, cat, tabs["sim_eff"]).items():
        u = tabs["sim_eff"].by_card.get(norm(nm))
        if len(v) >= 3:
            dep[nm] = {"n": len(v), "median": st.median(v), "q1": sorted(v)[len(v) // 4], "q3": sorted(v)[(3 * len(v)) // 4],
                       "sim_eff": u["deploy_time_ms"] / 50 if u else None,
                       "live": (tabs["live"].by_card.get(norm(nm)) or {}).get("deploy_time_ms", 0) / 50 or None}
    used = [(Path(p).stem[10:], len(fr), pr) for p, fr, ok, pr in logs if ok]
    skipped = [(Path(p).stem[10:], len(fr), pr) for p, fr, ok, pr in logs if not ok]
    json.dump({"logs_used": used, "logs_skipped": skipped, "rows": rows, "deploy": dep, "events": len(ev)},
              open(out or HERE / "measure.json", "w"), indent=1)
    print("logs used", len(used), "skipped", skipped)
    print(f"{'card':16s}{'kind':7s}{'n':>5s}{'/runs':>6s}{'med':>6s}{'IQR':>9s}{'mode':>5s}{'sh':>5s}{'SIMeff':>7s}{'SIMold':>7s}{'live':>6s}{'cad':>6s}{'cadSIM':>7s}")
    for r in sorted(rows, key=lambda r: -r["n"]):
        print(f"{r['name'][:15]:16s}{r['kind']:7s}{r['n']:5d}{r['n_all_runs']:6d}{r['median']:6.1f}{r['q1']:5d}-{r['q3']:<3d}{r['mode']:5d}"
              f"{r['mode_share_pm1']:5.2f}{(r['sim_eff'] if r['sim_eff'] is not None else float('nan')):7.1f}"
              f"{(r['sim_old'] if r['sim_old'] is not None else float('nan')):7.1f}{(r['live'] if r['live'] is not None else float('nan')):6.1f}"
              f"{(r['cadence_median'] if r['cadence_median'] is not None else float('nan')):6.1f}{(r['sim_eff_cadence'] or float('nan')):7.1f}")
    print("\ndeploy (state-4 run, ticks):", {k: (v["n"], v["median"], v["sim_eff"]) for k, v in sorted(dep.items(), key=lambda kv: -kv[1]["n"])})


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
