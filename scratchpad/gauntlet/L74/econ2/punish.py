"""Does the SIM punish meeting a push with low elixir as hard as live does? (L74 econ, 2026-10-14)

Pushes = econ2 push starts (compact 'ps': enemy value on my half >= 7 after >= 80 ticks below); elixir at push start =
the compact 'el' there. Lost = within 300 ticks (15 s) my towers lose >= 1000 HP in total or a tower falls (the loss
review's lost-episode rule, on a fixed window). Towers: SIM = raw lr_frames (every 10 ticks); live = decision events'
public raw_bodies (card_id -1, every 10 ticks). Same rule for both; 95% CI = bootstrap over matches.
    python punish.py SIM_MATCHES_DIR [LIVE_BEFORE=20261014_1343]   (SIM dir holds r1_evo/ r1_lad/ matches.jsonl)
"""
import json, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import econ2 as E  # noqa: E402

WIN, LOST_HP = 300, 1000
# the SIM plays every card and tower at level 11 (princess 3052 HP), live at level 15 (4424): same rule = the same
# FRACTION of tower HP, so the SIM threshold is 1000 x 3052 / 4424 = 690 (both sides' damage scales alike)
SIM_LOST_HP = round(LOST_HP * 3052 / 4424)


def lost(towers, tp, thr=LOST_HP):
    """towers: [(tick, hp_total, n_alive)] ascending -> lost-episode flag for a push starting at tp, None if unseen."""
    base = next((x for x in towers if x[0] >= tp), None)
    if base is None:
        return None
    win = [x for x in towers if tp <= x[0] <= tp + WIN]
    return base[1] - min(x[1] for x in win) >= thr or min(x[2] for x in win) < base[2]


def sim_towers(d, name="r1"):
    out = {}
    for c in ("evo", "lad"):
        for l in open(os.path.join(d, f"{name}_{c}", "matches.jsonl")):
            r = json.loads(l)
            side = r["learner_side"]
            tw = [(f[0], sum(t[4] for t in f[3] if t[0] == side and t[4] > 0), sum(t[0] == side and t[4] > 0 for t in f[3]))
                  for f in r["behaviour"]["lr_frames"]]
            out[f"{c}:{r['tag']}"] = tw
    return out


def live_towers(path):
    tw = []
    for l in open(path, encoding="utf8", errors="replace"):
        if not l.startswith('{"event": "decision"'):
            continue
        j = json.loads(l)
        p = j.get("public") or {}
        side = p.get("observer_side")
        b = [x for x in p.get("raw_bodies", []) if x.get("card_id") == -1 and x.get("kind") in (12, 13) and x["side"] == side]
        if b:
            tw.append((j["tick"], sum(max(0, x["hp"]) for x in b), sum(x["hp"] > 0 for x in b)))
    return tw


def rows(ms, towers, thr=LOST_HP):
    out = []                                           # per match: [(low elixir?, lost?)]
    for m in ms:
        tw = towers(m)
        if not tw:
            continue
        r = []
        for tp in m["ps"]:
            e = m["el"][m["T"].index(tp)]
            f = lost(tw, tp, thr)
            if e is not None and f is not None:
                r.append((e < 4, f))
        if r:
            out.append(r)
    return out


def summary(name, per_match, B=2000, seed=3):
    def rates(ms):
        lo = [f for m in ms for low, f in m if low]; hi = [f for m in ms for low, f in m if not low]
        return (sum(lo) / len(lo) if lo else float("nan")), (sum(hi) / len(hi) if hi else float("nan")), len(lo), len(hi)
    a, b, nl, nh = rates(per_match)
    rng = random.Random(seed); diffs = []
    for _ in range(B):
        s = [per_match[rng.randrange(len(per_match))] for _ in per_match]
        x, y, _, _ = rates(s); diffs.append(x - y)
    diffs.sort()
    print(f"{name}: matches {len(per_match)}; pushes <4 elixir {nl} (lost {100*a:.1f}%), >=4 {nh} (lost {100*b:.1f}%); "
          f"share <4 {100*nl/(nl+nh):.0f}%; penalty {100*(a-b):+.1f} pp [{100*diffs[int(.025*B)]:+.1f}, {100*diffs[int(.975*B)]:+.1f}]")


if __name__ == "__main__":
    sim_dir = sys.argv[1]; before = sys.argv[2] if len(sys.argv) > 2 else "20261014_1343"
    st = sim_towers(sim_dir)
    summary("SIM r1 (D3, 960 games)", rows(E.load("sim_r1"), lambda m: st.get(m["file"]), SIM_LOST_HP))
    live = [m for m in E.load("live") if m["fam"] == "r1" and not m.get("al") and os.path.basename(m["file"])[10:23] < before]
    summary(f"LIVE r1 (before {before})", rows(live, lambda m: live_towers(os.path.join(E.G.LOGDIR, os.path.basename(m["file"])))))
