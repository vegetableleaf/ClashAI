"""Which SIM opponent setting matches LIVE pressure for r1? (owner 10-14). One row per source, same definitions everywhere:
econ2.pressure (push rate / value / board pressure), punish.py (lost-episode rate by elixir at push start), win rate.
distance = mean |relative error| vs live r1 over TARGETS (lower = closer to live).
    python calib_report.py RAWDIR NAME [NAME ...]    (RAWDIR/NAME_{evo,lad}/matches.jsonl; data/sim_NAME.json.gz)
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import econ2 as E  # noqa: E402
import punish as P  # noqa: E402

TARGETS = ("push_pm", "push_v", "t_vm3", "lost_lo", "lost_hi", "share_lo", "win")


def row(ms, towers):
    r = E.pressure(ms)
    per = P.rows(ms, towers)
    lo = [f for m in per for low, f in m if low]; hi = [f for m in per for low, f in m if not low]
    r.update(lost_lo=sum(lo) / max(1, len(lo)), lost_hi=sum(hi) / max(1, len(hi)), share_lo=len(lo) / max(1, len(lo) + len(hi)),
             win=r["win"] / max(1, r["n"] - r["draw"]))
    return r


def main(rawdir, names, before="20261014_1343"):
    live = [m for m in E.load("live") if m["fam"] == "r1" and not m.get("al") and os.path.basename(m["file"])[10:23] < before]
    rows = {"live_r1": row(live, lambda m: P.live_towers(os.path.join(E.G.LOGDIR, os.path.basename(m["file"]))))}
    # live compact rows carry no outcome: take crowns from the loss review ledger (equal crowns -> excluded)
    import json
    cr = {r["file"]: (r.get("crowns_me"), r.get("crowns_opp")) for r in map(json.loads, open(os.path.join(HERE, "..", "loss_review", "matches.jsonl"), encoding="utf8"))}
    res = [cr.get(os.path.basename(m["file"])) for m in live]
    w = sum(1 for c in res if c and c[0] is not None and c[0] > c[1]); l = sum(1 for c in res if c and c[0] is not None and c[0] < c[1])
    rows["live_r1"]["win"] = w / max(1, w + l)
    for n in names:
        st = P.sim_towers(rawdir, n)
        rows["sim_" + n] = row(E.load("sim_" + n), lambda m, st=st: st.get(m["file"]))
    ref = rows["live_r1"]
    print("| source | matches | win | pushes/min | push value | time vm>=3 | pushes met < 4 elixir | lost < 4 | lost >= 4 | distance |")
    for k, r in rows.items():
        d = E.mean([abs(r[t] / ref[t] - 1) for t in TARGETS]) if k != "live_r1" else None
        print(f"| {k} | {r['n']} | {100*r['win']:.1f}% | {r['push_pm']:.2f} | {r['push_v']:.1f} | {100*r['t_vm3']:.1f}% | "
              f"{100*r['share_lo']:.0f}% | {100*r['lost_lo']:.1f}% | {100*r['lost_hi']:.1f}% | {'' if d is None else f'{d:.3f}'} |")
    # live win rate here = all live r1 matches in the window with a known result; the A/B1 figure was 50.7% (150 games)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
