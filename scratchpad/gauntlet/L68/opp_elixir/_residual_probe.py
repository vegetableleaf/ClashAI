"""Exploratory: where does perfect-detection accounting miss by > 0.5 in non-pump matches? First jump per side."""
import collections, glob, json, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[4]; sys.path.insert(0, str(REPO))
from pipeline.opp_elixir_count import OppElixirCounter, card_cost
cause = collections.Counter(); ex = []
for deck in ("icebow", "hogeq"):
    for f in sorted(glob.glob(str(REPO / f"scratchpad/gauntlet/ext/corpus_v6/{deck}/replay_*.json"))):
        d = json.load(open(f)); log = [e for e in d["log"] if e.get("accepted")]
        if {e["card"] for e in log} & {"elixir-collector", "elixir-golem"}: continue
        frames = sorted(d["frames"], key=lambda fr: fr["tick"])
        for opp in (0, 1):
            evs = sorted((e["tick"], e["card"].replace("-", "_"), card_cost(e["card"].replace("-", "_"))) for e in log if e["side"] == opp)
            c, i, prev = OppElixirCounter(), 0, None
            for fr in frames:
                t = fr["tick"]
                while i < len(evs) and evs[i][0] < t:
                    c.play(*evs[i]); i += 1
                diff = c.at(t) - fr["elixir"][opp]
                if abs(diff) > 0.5:
                    near = [(e["tick"], e["side"], e["card"], e.get("cost"), e.get("accepted")) for e in d["log"] if prev is not None and prev - 5 <= e["tick"] <= t]
                    cause[tuple(sorted({n[2] + ("/opp" if n[1] == opp else "/me") for n in near}))] += 1
                    if len(ex) < 8: ex.append((f[-22:], opp, prev, t, round(diff, 3), near))
                    break
                prev = t
print(cause.most_common(25))
for e in ex: print(e)
