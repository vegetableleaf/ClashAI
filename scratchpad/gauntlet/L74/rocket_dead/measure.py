"""Spells aimed at a DESTROYED enemy tower with nothing alive in their reach (owner 2026-10-08 23:xx: "the model cast
rocket on a fallen tower"). Read-only on the MAIN repo's live logs (decision 'public' snapshot = the model board).

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/rocket_dead/measure.py [glob]

Per confirmed Rocket / Log / Tornado play: the decision board's enemy towers and bodies (public.model_towers / model_bodies,
board frame, enemy at the top). Dead-tower hit = the spell's area covers a destroyed enemy tower's footprint (centre
within radius + catalog tower radius). Empty = no enemy body (side != 0) within radius + 0.5 tile and no ALIVE enemy
tower footprint in the area. Rocket radius 2.0 (catalog), Tornado 5.5 (L74 review), Log = its rolling corridor
(decision_options.rolling_corridor geometry: half-width 1.95, ahead up to the roll range). Also: centre-only variant
(dead tower centre within the radius), elixir, phase, why/lethal fields, match family."""
import collections, glob, json, math, os, sys

LOGS = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/"
TOWERS = {("king", None): (9.0, 3.0, 1.4), ("princess", "L"): (3.5, 6.5, 1.0), ("princess", "R"): (14.5, 6.5, 1.0)}
COST = {"Rocket": 6, "Log": 2, "Tornado": 3}
LOG_HALF, LOG_DEPTH, LOG_REACH = 1.95, 0.6, 10.1     # catalog Log projectile (milli/1000): radius, radius_y, range
BODY_SLACK = 0.5


def covers(card, cx, cy, tx, ty, extra):
    if card == "Log":                                 # my Log rolls toward decreasing board y (decision_options)
        ahead = cy - ty
        return abs(tx - cx) <= LOG_HALF + extra and -LOG_DEPTH - extra <= ahead <= LOG_REACH + extra
    r = 2.0 if card == "Rocket" else 5.5
    return math.hypot(tx - cx, ty - cy) <= r + extra


def family(ck):
    ck = ck or ""
    return "towerref_w2" if "towerref_w2" in ck else "stack2k" if "barrel2k" in ck else "R1e" if "r1e31" in ck else "other"


def main():
    pat = sys.argv[1] if len(sys.argv) > 1 else LOGS + "live_play_202610*.jsonl"
    rows, matches = [], collections.Counter()
    for f in sorted(glob.glob(pat)):
        fam, last, conf_names, plays = "other", None, [], []
        for line in open(f, encoding="utf-8", errors="replace"):
            if not line.startswith('{"event": "'):
                continue
            ev = line[11:line.index('"', 11)]
            if ev not in ("start", "decision", "play", "confirmed"):
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if ev == "start":
                fam = family(d.get("ckpt"))
            elif ev == "decision":
                last = d
            elif ev == "play" and d.get("name") in COST and last and "model_towers" in (last.get("public") or {}):
                plays.append((d, last))
            elif ev == "confirmed":
                conf_names.append((d["tick"], d.get("name")))
        if last is None or "model_towers" not in (last.get("public") or {}):
            continue
        matches[fam] += 1
        for d, dec in plays:
            if not any(n == d["name"] and 0 <= t - d["tick"] < 200 for t, n in conf_names):
                continue                                    # unconfirmed: never landed
            xy = d["xy"] if isinstance(d["xy"], list) else json.loads(d["xy"])
            cx, cy = xy[0] * 18, xy[1] * 32
            p = dec["public"]
            enemy_towers = [t for t in p["model_towers"] if t["side"] == 1]
            dead = [t for t in enemy_towers if not t["alive"]]
            card = d["name"]
            dead_hit = [t for t in dead if covers(card, cx, cy, *TOWERS[(t["kind"], t["lane"])][:2], TOWERS[(t["kind"], t["lane"])][2])]
            dead_centre = [t for t in dead if covers(card, cx, cy, *TOWERS[(t["kind"], t["lane"])][:2], 0.0)]
            alive_hit = [t for t in enemy_towers if t["alive"] and covers(card, cx, cy, *TOWERS[(t["kind"], t["lane"])][:2], TOWERS[(t["kind"], t["lane"])][2])]
            bodies = [b for b in p["model_bodies"] if b["side"] != 0 and covers(card, cx, cy, b["x"] * 18, b["y"] * 32, BODY_SLACK)]
            t_ph = "1x" if d["tick"] < 2400 else "2x" if d["tick"] < 3600 else "OT"
            dc = dec.get("decision") or {}
            rows.append(dict(file=os.path.basename(f), fam=fam, card=card, tick=d["tick"], ph=t_ph, xy=[round(cx, 2), round(cy, 2)],
                             dead_hit=bool(dead_hit), dead_centre=bool(dead_centre), empty=not bodies and not alive_hit,
                             n_bodies=len(bodies), why=dc.get("why"), lethal=bool(dc.get("lethal_rocket"))))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "measure_rows.jsonl")
    with open(out, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    for fam in ("towerref_w2", "ALL"):
        n = sum(matches.values()) if fam == "ALL" else matches[fam]
        R = [r for r in rows if fam == "ALL" or r["fam"] == fam]
        print(f"\n=== {fam}: {n} matches with model_towers")
        for card in ("Rocket", "Log", "Tornado"):
            q = [r for r in R if r["card"] == card]
            bad = [r for r in q if r["dead_hit"] and r["empty"]]
            badc = [r for r in q if r["dead_centre"] and r["empty"]]
            ph = collections.Counter(r["ph"] for r in bad)
            print(f"  {card:7s} confirmed {len(q):5d} | over a dead tower {sum(r['dead_hit'] for r in q):4d} | over a dead tower AND "
                  f"empty {len(bad):4d} = {len(bad) / max(n, 1):.3f}/match ({len(bad) / max(len(q), 1):.1%} of {card}s; 1x/2x/OT "
                  f"{[ph[x] for x in ('1x', '2x', 'OT')]}; wasted elixir {len(bad) * COST[card]}, {len(bad) * COST[card] / max(n, 1):.2f}/match)"
                  f" | centre-only variant {len(badc)} | via lethal rule {sum(r['lethal'] for r in bad)}")
    print("\nexamples (towerref_w2 Rockets):")
    for r in [r for r in rows if r["card"] == "Rocket" and r["dead_hit"] and r["empty"] and r["fam"] == "towerref_w2"][:12]:
        print("  ", r)


if __name__ == "__main__":
    main()
