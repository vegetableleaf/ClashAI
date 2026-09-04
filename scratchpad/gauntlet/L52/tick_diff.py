"""SIM-PARITY ORACLE step 2 prototype (L52): tick-level diff of the real engine's frame record
(`scratchpad/gauntlet/ext/replay_<tag>_run1.json`, every tick, entities [side,x,y,name,hp,max_hp,state])
against our sim's record of the same timeline (`sim_replay_drive.py --record`, every 0.1 s = 2 ticks).
Reports: (1) level-11 card HP parity per card, (2) tower HP timelines + first-fall ticks, (3) per-play unit
cohort lifetimes (spawn -> death) engine vs sim, (4) elixir timelines.
"""
import json, re, sys, statistics as st
from pathlib import Path
ROOT = Path("C:/Users/benpe/ClashBot")
import os
SIMDIR = os.environ.get("SIMDIR", "simrec")


def norm(name):
    n = re.sub(r"[^a-z]", "", name.lower())
    for suf in ("evo", "hero"):
        if n.endswith(suf) and len(n) > len(suf) + 2:
            n = n[: -len(suf)]
    return n


def cohorts(frames, plays, tick_key, ent_side, ent_name, ent_hp, ent_max, step):
    """Per accepted troop play: cohort size, spawn tick, death tick (count back at baseline), peak hp sum."""
    by_tick = {f["tick"]: f for f in frames}
    ticks = sorted(by_tick)
    out = {}
    for p in plays:
        s, nm, t0 = p["side"], norm(p["card"]), p["tick"]
        def cnt(t):
            f = by_tick.get(t)
            return 0 if f is None else sum(1 for e in f["entities"] if e[ent_side] == s and norm(e[ent_name]) == nm)
        before = [t for t in ticks if t < t0]
        base = cnt(before[-1]) if before else 0
        after = [t for t in ticks if t0 <= t <= t0 + 60]
        if not after:
            continue
        peak = max(cnt(t) for t in after)
        size = peak - base
        if size <= 0:
            out[p["play_index"]] = {"side": s, "card": nm, "spawned": 0}
            continue
        spawn = next(t for t in after if cnt(t) > base)
        death = None
        for t in (t for t in ticks if t > spawn):
            if cnt(t) <= base:
                death = t; break
        last = ticks[-1]
        out[p["play_index"]] = {"side": s, "card": nm, "spawned": size, "spawn": spawn, "death": death,
                                "life_ticks": (death if death is not None else last) - spawn, "died": death is not None}
    return out


def tower_series(frames, is_engine):
    ser = {}
    for f in frames:
        for tw in f["towers"]:
            if is_engine:
                key = (tw[0], tw[1], tw[2] or "")      # side, type, lane
                hp = tw[5]
            else:
                key = tw
            ser.setdefault(None, None)
        break
    return ser


def main(tag):
    E = json.loads((ROOT / f"scratchpad/gauntlet/ext/replay_{tag}_run1.json").read_text())
    S = json.loads((ROOT / f"scratchpad/gauntlet/L52/{SIMDIR}/replay_{tag}.json").read_text())
    ef, sf = E["frames"], S["frames"]
    print(f"=== {tag}: real crowns {E['expected']['crowns_by_side']}, engine {E['final']['crowns']} @tick {E['final']['terminal_tick']}, "
          f"sim {S['final']['crowns']} @tick {sf[-1]['tick']}")
    # (1) card HP parity at level 11
    e_hp = {}
    for f in ef:
        for e in f["entities"]:
            if e[3] != "-1":
                e_hp.setdefault(norm(e[3]), set()).add(e[5])
    s_hp = {}
    for f in sf:
        for e in f["entities"]:
            s_hp.setdefault(norm(e[3]), set()).add(e[5])
    print("--- L11 max HP per card (engine | sim):")
    for k in sorted(set(e_hp) | set(s_hp)):
        ev, sv = sorted(e_hp.get(k, [])), sorted(s_hp.get(k, []))
        flag = "" if (ev and sv and max(ev) == max(sv)) else "  <-- DIFF"
        print(f"   {k:22s} {ev} | {sv}{flag}")
    # (2) towers: engine towers [side,type,lane,x,y,hp,max]; sim [side,type,hp] in order L,R,king per side
    def e_tw(f):
        d = {}
        for tw in f["towers"]:
            d[(tw[0], tw[1], tw[2] or "")] = tw[5]
        return d
    def s_tw(f):
        d = {}
        for s in (0, 1):
            row = [tw for tw in f["towers"] if tw[0] == s]
            # sim order: [left princess, right princess, king]; engine lanes 'left' = low x (3500) -- sim left = x_frac 0.194 = low x. same.
            d[(s, "princess", "left")] = row[0][2]; d[(s, "princess", "right")] = row[1][2]; d[(s, "king", "")] = row[2][2]
        return d
    e_by = {f["tick"]: e_tw(f) for f in ef}; s_by = {f["tick"]: s_tw(f) for f in sf}
    common = sorted(set(e_by) & set(s_by))
    print("--- tower HP at 30 s intervals (engine | sim), and first-fall ticks:")
    keys = [(0, "princess", "left"), (0, "princess", "right"), (0, "king", ""), (1, "princess", "left"), (1, "princess", "right"), (1, "king", "")]
    for t in [x for x in common if x % 600 == 0]:
        print("   t=%3ds " % (t // 20) + "  ".join("%s%s:%4d|%4d" % (k[0], k[1][0] + (k[2][:1] or ""), e_by[t][k], s_by[t][k]) for k in keys))
    for k in keys:
        ef_t = next((t for t in sorted(e_by) if e_by[t][k] <= 0), None); sf_t = next((t for t in sorted(s_by) if s_by[t][k] <= 0), None)
        e1 = next((t for t in sorted(e_by) if e_by[t][k] < e_by[min(e_by)][k]), None); s1 = next((t for t in sorted(s_by) if s_by[t][k] < s_by[min(s_by)][k]), None)
        print(f"   tower {k}: first damage tick engine {e1} sim {s1}; fell engine {ef_t} sim {sf_t}")
    dif = [abs(e_by[t][k] - s_by[t][k]) for t in common for k in keys]
    print("   mean |tower HP diff| over common ticks: %.0f HP (n=%d ticks)" % (st.mean(dif), len(common)))
    # (3) cohorts
    plays = [l for l in E["log"] if l.get("accepted") and l.get("card")]
    sp = [l for l in S["log"] if l.get("accepted") and l.get("card")]
    ec = cohorts(ef, plays, "tick", 0, 3, 4, 5, 1); sc = cohorts(sf, sp, "tick", 0, 3, 4, 5, 2)
    print("--- per-play unit cohorts: idx side card | engine spawned/life_ticks/died | sim spawned/life_ticks/died")
    tot = {"n": 0, "e_life": [], "s_life": [], "e_died": 0, "s_died": 0, "size_diff": 0}
    for i in sorted(ec):
        a, b = ec[i], sc.get(i)
        if b is None:
            continue
        la = a.get("life_ticks"); lb = b.get("life_ticks")
        mark = ""
        if a["spawned"] and b["spawned"]:
            tot["n"] += 1; tot["e_life"].append(la); tot["s_life"].append(lb); tot["e_died"] += a["died"]; tot["s_died"] += b["died"]
            if a["spawned"] != b["spawned"]: tot["size_diff"] += 1
            if la and lb and (lb > 1.5 * la or la > 1.5 * lb): mark = "  <-- x1.5"
        print(f"   {i:3d} s{a['side']} {a['card']:16s} | {a['spawned']:2d} {str(la):>5s} {str(a.get('died')):5s} | {b['spawned']:2d} {str(lb):>5s} {str(b.get('died')):5s}{mark}")
    if tot["n"]:
        print("   SUMMARY n=%d troop plays: median life engine %.0f ticks vs sim %.0f; died engine %d sim %d; cohort-size differs %d"
              % (tot["n"], st.median(tot["e_life"]), st.median(tot["s_life"]), tot["e_died"], tot["s_died"], tot["size_diff"]))
        for s in (0, 1):
            el = [ec[i]["life_ticks"] for i in ec if i in sc and ec[i]["spawned"] and sc[i]["spawned"] and ec[i]["side"] == s]
            sl = [sc[i]["life_ticks"] for i in ec if i in sc and ec[i]["spawned"] and sc[i]["spawned"] and ec[i]["side"] == s]
            if el: print("   side %d: median life engine %.0f vs sim %.0f ticks (n=%d)" % (s, st.median(el), st.median(sl), len(el)))
    # (4) elixir
    ed = [abs(e_by_t["elixir"][s] - s_by_t["elixir"][s]) for t in common for e_by_t in [next(f for f in ef if f["tick"] == t)] for s_by_t in [next(f for f in sf if f["tick"] == t)] for s in (0, 1)] if len(common) < 400 else None
    if ed: print("   mean |elixir diff| %.2f" % st.mean(ed))


if __name__ == "__main__":
    for tag in sys.argv[1:]:
        main(tag)
