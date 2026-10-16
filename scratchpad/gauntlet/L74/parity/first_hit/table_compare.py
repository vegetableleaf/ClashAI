"""A) SIM card table vs live (APK + device update) table: first-hit related fields per unit.
Reads only the decoded cards.json files. Usage: table_compare.py [sim.json live.json out.json]"""
import json, sys, os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), *[".."] * 5))
SIM = os.path.join(ROOT, "research/ext/Royale/RoyaleSim/data/derived/cards-15.535.json")
LIVE = os.path.join(ROOT, "scratchpad/gauntlet/L74/apktables/out/device_builds/20261012T221627332682Z-50188/cards.json")
FIELDS = ["load_time_ms", "hit_speed_ms", "deploy_time_ms", "load_first_hit"]
RAW = {"LoadTime": "load_time_ms", "HitSpeed": "hit_speed_ms", "DeployTime": "deploy_time_ms", "LoadFirstHit": "load_first_hit"}


def all_units(d):
    """name -> unit dict, from units + hero-form / evolution embedded tables + towers."""
    out = dict(d["units"])
    for key in ("hero_forms", "evolutions"):
        for c in d.get(key) or []:
            for n, u in ((c.get("tables") or {}).get("units") or {}).items():
                out.setdefault(n, u)
    for t in d.get("towers") or []:
        out.setdefault("TOWER:" + t["name"], t)
    return out


def card_of(d):
    """unit name -> card names that summon it (for the report)"""
    m = {}
    for c in d["cards"] + (d.get("hero_forms") or []) + (d.get("evolutions") or []):
        m.setdefault(c.get("summon_character"), []).append(c["name"])
    return m


def row(u):
    r = {f: u.get(f) for f in FIELDS}
    r["special_load_ms"] = (u.get("special") or {}).get("load_time_ms")
    raw = u.get("raw") or {}
    r["raw"] = {k: raw.get(k) for k in RAW if k in raw}
    return r


def compare(sim, live):
    su, lu = all_units(sim), all_units(live)
    res = []
    for n in sorted(set(su) | set(lu)):
        a, b = su.get(n), lu.get(n)
        if a is None or b is None:
            res.append({"unit": n, "only": "live" if a is None else "sim"})
            continue
        ra, rb = row(a), row(b)
        diff = {f: [ra[f], rb[f]] for f in FIELDS + ["special_load_ms"] if ra[f] != rb[f]}
        rawdiff = {k: [ra["raw"].get(k), rb["raw"].get(k)] for k in set(ra["raw"]) | set(rb["raw"]) if ra["raw"].get(k) != rb["raw"].get(k)}
        res.append({"unit": n, "sim": ra, "live": rb, "diff": diff, "rawdiff": rawdiff,
                    "cards_sim": card_of(sim).get(n, []), "cards_live": card_of(live).get(n, [])})
    return res


if __name__ == "__main__":
    s, l, o = (sys.argv[1:4] + [None] * 3)[:3]
    sim = json.load(open(s or SIM)); live = json.load(open(l or LIVE))
    res = compare(sim, live)
    json.dump(res, open(o or os.path.join(os.path.dirname(__file__), "table_compare.json"), "w"), indent=1)
    both = [r for r in res if "sim" in r]
    bad = [r for r in both if r["diff"] or r["rawdiff"]]
    print("units sim", len(all_units(sim)), "live", len(all_units(live)), "common", len(both), "differing", len(bad),
          "only_sim", sum(1 for r in res if r.get("only") == "sim"), "only_live", sum(1 for r in res if r.get("only") == "live"))
    for r in bad:
        print(r["unit"], r["diff"], r["rawdiff"])


# ---- every timing-looking raw column (not only the four normalised ones): AttackSequenceList entries, delays, offsets
import re
TIMING = re.compile(r"load|first|hitspeed|windup|delay|attack(start|time|delay|cooldown)|sequence|deploy|cooldown|uptime|hidetime", re.I)


def raw_timing_diff(sim, live):
    su, lu = all_units(sim), all_units(live)
    out = {}
    for n in sorted(set(su) & set(lu)):
        a, b = su[n].get("raw") or {}, lu[n].get("raw") or {}
        d = {k: [a.get(k), b.get(k)] for k in set(a) | set(b) if TIMING.search(k) and a.get(k) != b.get(k)}
        if d:
            out[n] = d
    return out
