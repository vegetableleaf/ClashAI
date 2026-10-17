"""Troops arms: paired comparisons on the troops eval (live_eval_pod.sh outputs, 960 paired = seeds 741200 + 742000).

    python cmp_tt.py DIR        DIR holds tt_<name>_<seed>/ and ttx_<name>_<seed>/ (names ctl = A, f36 = B, f36tt = C, u250)

Prints, per eval kind (tt = troops at the live rates, ttx = troop slice): each name's wins, B - A, C - B, C - A and
each vs u250 (validate.paired_drift: 10,000 paired bootstrap draws within census and side), after checking that every
pair met the same opponent deck, side AND tower troop; plus each name's win rate in troop vs Princess games (tt)."""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path[:0] = ["C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/heroiw"]
from validate import paired_drift  # noqa: E402

NAMES = {"ctl": "A (0.1.35-trained control)", "f36": "B (fork engine)", "f36tt": "C (fork + troops)", "u250": "u250"}
PAIRS = [("ctl", "f36", "B - A (engine)"), ("f36", "f36tt", "C - B (troops)"), ("ctl", "f36tt", "C - A"),
         ("u250", "ctl", "A - u250"), ("u250", "f36", "B - u250"), ("u250", "f36tt", "C - u250")]


def load(d, kind, name):
    rows = []
    for s in (741200, 742000):
        p = Path(d)/f"{kind}_{name}_{s}"/"D3"/"matches.jsonl"
        if not p.is_file():
            return None
        rows += [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
    return rows


def main(d):
    for kind, label in (("tt", "troops at the live rates (7.0%)"), ("ttx", "troop SLICE (every opponent fields one)")):
        rows = {n: load(d, kind, n) for n in NAMES}
        rows = {n: r for n, r in rows.items() if r}
        print(f"== {kind}: {label}")
        for n, r in rows.items():
            w = sum(x["outcome"] == "win" for x in r)
            tw = Counter(x.get("opp_tower") for x in r)
            print(f"  {NAMES[n]:28s} {w}/{len(r)} ({100*w/len(r):.1f}%)  troops {dict(tw)}")
            if kind == "tt":
                for t in (False, True):
                    sub = [x for x in r if (x.get("opp_tower") is not None) == t]
                    ws = sum(x["outcome"] == "win" for x in sub)
                    print(f"      {'troop' if t else 'Princess':8s} games: {ws}/{len(sub)} ({100*ws/max(1, len(sub)):.1f}%)")
        for a, b, lab in PAIRS:
            if a in rows and b in rows:
                ka = {(x["census"], x["seed"]): x.get("opp_tower") for x in rows[a]}
                kb = {(x["census"], x["seed"]): x.get("opp_tower") for x in rows[b]}
                assert ka == kb, f"{a} / {b}: tower troops differ between the pair"
                r = paired_drift(rows[a], rows[b], expected=len(rows[a]))
                print(f"  {lab:24s} {r['delta_pp']:+.2f} pp [{r['ci95_pp'][0]:+.2f}, {r['ci95_pp'][1]:+.2f}]  "
                      f"({100*r['old_win_rate']:.1f}% -> {100*r['new_win_rate']:.1f}%, {r['pairs']} pairs)")


if __name__ == "__main__":
    main(sys.argv[1])
