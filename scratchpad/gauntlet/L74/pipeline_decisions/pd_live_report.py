"""Read the live_play logs of a --pipeline-decisions run and report what the live test is for.

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/pipeline_decisions/pd_live_report.py live_play_<ts>.jsonl [...]

Per log: plays, pipelined (second) plays, consecutive-play gaps (<= 24 ticks share vs the pros' 0.058), pairs and the second card,
the gate p at pipelined decisions, outcomes of both taps of a pair (matched by name + order, NOT play->next-confirm adjacency),
verdict blocks (a MASK failure if slot_busy / outstanding), refusals of pipelined plays vs ordinary ones, elixir drops vs card costs.
"""
import json
import statistics as st
import sys
from collections import Counter

COST = {"Skeletons": 1, "Log": 2, "Knight": 3, "Tornado": 3, "IceWizard": 3, "Tesla": 4, "Xbow": 6, "Rocket": 6}
PROS_SHARE24 = 0.0583


def load(path):
    out = []
    for ln in open(path, encoding="utf-8"):
        try:
            out.append(json.loads(ln))
        except ValueError:
            pass
    return out


def main():
    tot = Counter()
    gaps, pairs, second, gate_p, drops = [], Counter(), Counter(), [], []
    for path in sys.argv[1:]:
        ev = load(path)
        plays = [e for e in ev if e["event"] == "play"]
        conf = [e for e in ev if e["event"] == "confirmed"]
        unc = [e for e in ev if e["event"] == "unconfirmed"]
        blocked = [e for e in ev if e["event"] == "pipeline_blocked"]
        end = next((e for e in ev if e["event"] == "end"), {})
        piped = [e for e in plays if e.get("pipelined")]
        tot["logs"] += 1
        tot["plays"] += len(plays)
        tot["pipelined"] += len(piped)
        tot["confirmed"] += len(conf)
        tot["unconfirmed"] += len(unc)
        tot["unconf_pipelined"] += sum(bool(u.get("pipelined")) for u in unc)
        for b in blocked:
            tot[f"blocked_{b['why']}"] += 1
        for a, b in zip(plays, plays[1:]):
            g = b["tick"] - a["tick"]
            gaps.append(g)
            if g <= 24:
                pairs[f"{a['name']}->{b['name']}"] += 1
                second[b["name"]] += 1
        # the pipelined decisions' gate p: the decision events carry `pending` when one was outstanding
        gate_p += [e["decision"]["p_play"] for e in ev if e["event"] == "decision" and e.get("pending") and "decision" in e]
        for c in conf:
            n = c["name"]
            if n in COST and c.get("elixir_drop") is not None:
                drops.append((n, round(c["elixir_drop"], 2)))
        print(f"{path.split(chr(92))[-1].split('/')[-1]}: plays {len(plays)} pipelined {len(piped)} blocked {len(blocked)} "
              f"confirmed {len(conf)} unconfirmed {len(unc)} | end pipelined_plays {end.get('pipelined_plays')} fails {end.get('fails')}")
    n = max(len(gaps), 1)
    s24 = sum(g <= 24 for g in gaps) / n
    print(f"\nlogs {tot['logs']} plays {tot['plays']} pipelined {tot['pipelined']} ({tot['pipelined'] / max(tot['plays'], 1):.3f} of plays)")
    print(f"consecutive plays <= 24 ticks apart: {s24:.4f} (pros {PROS_SHARE24}); min gap {min(gaps) if gaps else None}")
    print("pairs <=24: " + ", ".join(f"{k} {v}" for k, v in pairs.most_common(10)))
    tot_s = max(sum(second.values()), 1)
    print("second-card mix: " + ", ".join(f"{k} {v / tot_s:.2f}" for k, v in second.most_common()) + "   (pros: skeletons .28, log .17, knight .14, icewizard .13, tornado .12, tesla .11)")
    if gate_p:
        print(f"gate p at decisions with a play pending: median {st.median(gate_p):.3f} (n {len(gate_p)})")
    print(f"unconfirmed {tot['unconfirmed']} of {tot['plays']} plays ({tot['unconfirmed'] / max(tot['plays'], 1):.3f}; ordinary baseline 0.033); "
          f"pipelined plays unconfirmed: {tot['unconf_pipelined']} of {tot['pipelined']}")
    print("verdict blocks: " + (", ".join(f"{k} {v}" for k, v in tot.items() if k.startswith("blocked_")) or "none")
          + "   (slot_busy / outstanding = the MASK failed: a bug; unaffordable = the mask and the shared verdict disagreed)")
    by = {}
    for n_, d in drops:
        by.setdefault(n_, []).append(d)
    print("median elixir drop at confirmation (cost; regen over the ~24 ticks makes it smaller): "
          + ", ".join(f"{k} {st.median(v):.2f} ({COST[k]})" for k, v in sorted(by.items())))


if __name__ == "__main__":
    main()
