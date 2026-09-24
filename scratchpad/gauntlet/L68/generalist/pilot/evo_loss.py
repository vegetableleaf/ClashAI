"""How much of the pilot slice does the sandbox's missing Elite Barbarians evo (26000043) cost, per top-100 deck?"""
import csv
import json
from collections import Counter
from pathlib import Path

G = Path(__file__).resolve().parents[1]
sel = {s["tag"]: s["sides"] for s in json.load(open(G / "pilot_tags.json"))}
rows = list(csv.DictReader(open(G / "pilot/crawl/battles.csv", encoding="utf-8")))
col = {"team": "team_deck", "opponent": "opponent_deck"}
EVO = "elite-barbarians-ev1"
bad, lost, own = set(), Counter(), Counter()
for b in rows:
    if EVO in b["team_deck"].split(",") or EVO in b["opponent_deck"].split(","):
        bad.add(b["replay_tag"])
        for s, k in sel[b["replay_tag"]].items():
            lost[k] += 1
            own[k] += EVO in b[col[s]].split(",")
kept = sum(len(sel[b["replay_tag"]]) for b in rows)
out = {"replays": len(rows), "undrivable_replays": len(bad), "top100_sides": kept, "sides_lost": sum(lost.values()),
       "drivable_sides": kept - sum(lost.values()),
       "decks_losing_ge_half": sum(v >= 100 for v in lost.values()), "decks_losing_ge_95pct": sum(v >= 190 for v in lost.values()),
       "sides_lost_because_own_deck_has_evo": sum(own.values()),
       "top_losers(deck, lost, of_which_own_evo)": [(k, v, own[k]) for k, v in lost.most_common(10)]}
print(json.dumps(out, indent=1))
(G / "pilot/evo_loss.json").write_text(json.dumps(out, indent=1))
