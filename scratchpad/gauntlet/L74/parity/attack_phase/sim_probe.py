"""SIM side (royalesim 0.1.35, PARITY_SIM_PATH wheel): attack progress per tick around every hit of a slowed / unslowed /
post-freeze Knight, X-Bow and Tesla (ATTACK_PHASE_1016.md section 2).

    python sim_probe.py <unpacked royalesim wheel dir>

Scenarios (level 11, table client160402017_20261006; blue's princess towers down so blue's king is active):
  knight_<s> : a red Knight at blue's king; s = none (no shooter) | hero (blue Hero IW at (9, 9.2) slows it)
  knight_press: as knight_hero, the hero's button pressed every tick from t70 (freeze, then the after-slow)
  xbow_<s>   : a red X-Bow at (9, 13) shooting into blue's half; s = none | hero (blue Hero IW at (9, 9.2))
  tesla_<s>  : a red Tesla at (9, 10.5), a blue Giant walking at it from (9, 4); s = none | hero
Per hit (the tick the progress counter passes a HitSpeed multiple; the SIM's fire test): progress before / after, the
step, the remainder after the hit (progress mod HitSpeed) and whether the load timer was re-armed to LoadTime on it.
A hit that leaves the progress anywhere but before + step (a snap / reset) is printed as SNAP.
"""
import collections
import json
import os
import sys

sys.path.insert(0, sys.argv[1])
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "iw_slow"))
import probe  # noqa: E402

T = probe.T
UNITS = {"Knight": (1200, 700), "Xbow": (400, 0), "Tesla": (1100, 700)}   # HitSpeed, LoadTime (0.1.35 table)


def scenario(name):
    b, ids = probe.new_battle()
    deck = [ids[c] for c in ['IceWizard', 'Knight', 'Giant', 'Musketeer', 'Tesla', 'Log', 'Tornado', 'Rocket']]
    unit, shooter = name.split("_")
    at = {"Knight": T(9, 5.0), "Xbow": T(9, 13.0), "Tesla": T(9, 10.5)}[unit.capitalize() if unit != "xbow" else "Xbow"]
    uname = {"knight": "Knight", "xbow": "Xbow", "tesla": "Tesla"}[unit]
    spawns = [(1, ids[uname], *at, -1)]
    if unit == "tesla":
        spawns.append((0, ids["Giant"], *T(9, 4.0), -1))
    b.reset(1, [deck, deck], 0, 200, [10000, 10000], [[4824, 0, 0], [4824, 3052, 3052]], spawns,
            forms=[[2] + [0] * 7, [0] * 8], levels=[[11] * 8, [11] * 8], tower_levels=[11, 11])
    rows = []
    for t in range(420):
        cmds = []
        if shooter in ("hero", "press") and t == 0:
            cmds = [(0, 0, *T(9, 9.2))]
        if shooter == "press" and t >= 70:
            cmds = [(0, 4, 0, 0)]
        b.step(cmds, 1)
        sv = json.loads(b.save())
        E = sv["ents"]
        n = len(E["alive"])
        slots = len(E["buffs"]) // n
        cat = probe.ent_rows(sv)
        # entity `card` is not the catalogue index (X-Bow 108 vs 101): the probed unit is the only red Troop/Building
        u = next((r for r in cat if r["alive"] and r["team"] == "Red" and r["kind"] in ("Troop", "Building")), None)
        if u is None:
            break
        i = u["i"]
        bs = [s["id"] for s in E["buffs"][i * slots:(i + 1) * slots] if s["id"]]
        rows.append(dict(t=t, buffs=bs, stun=E["stun_ms"][i], phase=E["attack_phase"][i], p=E["attack_ms"][i],
                         load=E["attack_load_ms"][i], target=E["target"][i]))
    return uname, rows


def analyse(uname, rows):
    hs, lt = UNITS[uname]
    out, c, rem = [], collections.Counter(), collections.Counter()
    for r0, r1 in zip(rows, rows[1:]):
        p0, p1 = r0["p"], r1["p"]
        if p1 <= 0 or p0 <= 0 or p1 // hs == p0 // hs:
            continue
        step = p1 - p0
        slowed = bool(r1["buffs"])
        key = "slowed" if slowed else "unbuffed"
        c[key, "hits"] += 1
        c[key, "load_rearmed"] += r1["load"] == lt
        c[key, "step35" if step == 35 else ("step50" if step == 50 else f"step{step}")] += 1
        rem[key, p1 % hs] += 1
        out.append(f"t{r1['t']} {key:<8} buffs {r1['buffs']} progress {p0}->{p1} (step {step}) remainder {p1 % hs} "
                   f"load {r0['load']}->{r1['load']}")
    # progress continuity: every tick with progress > 0 on both sides advances by a constant composed step
    steps = collections.Counter(r1["p"] - r0["p"] for r0, r1 in zip(rows, rows[1:]) if r0["p"] > 0 and r1["p"] > 0)
    held = sum(1 for r0, r1 in zip(rows, rows[1:]) if r0["p"] > 0 and r1["p"] == r0["p"])
    return out, c, rem, steps, held


def main():
    for name in ("knight_none", "knight_hero", "knight_press", "xbow_none", "xbow_hero", "tesla_none", "tesla_hero"):
        uname, rows = scenario(name)
        out, c, rem, steps, held = analyse(uname, rows)
        print(f"== {name} ({uname}, {len(rows)} ticks) per-tick steps {dict(steps)} held ticks {held}")
        for k in sorted({k for k, _ in c}):
            print(f"   {k}: " + " ".join(f"{x}={c[k, x]}" for kk, x in sorted(c) if kk == k)
                  + f" remainders {dict(sorted((r, v) for (kk, r), v in rem.items() if kk == k))}")
        for line in out[:14]:
            print("   " + line)
        if name == "knight_press":
            hold = [(r["t"], r["p"], r["load"], r["buffs"]) for r in rows if 70 <= r["t"] <= 200 and r["t"] % 10 in (0, 5)]
            print("   press timeline (t, progress, load, buffs):", hold[:30])
        if name.startswith("tesla"):
            print("   tesla phases (t, phase, progress, target):",
                  [(r["t"], r["phase"], r["p"], r["target"]) for r in rows[::6]][:40])


if __name__ == "__main__":
    main()
