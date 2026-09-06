"""Tag list for the corpus drive of the re-fetched (i=1) half: tags in <deck>_done.json whose
plays_ext_i1.csv rows are all positioned (ability rows aside) and match battles.csv's play count.
usage: i1_tags.py <deck> -> writes <here>/<deck>_i1_tags.json, prints counts"""
import sys, csv, json, collections
from pathlib import Path
deck = sys.argv[1]; here = Path(__file__).resolve().parent
d = Path(f"C:/Users/benpe/ClashBot/{deck}/data/royaleapi/crawl2")
done = set(json.loads((here / f"{deck}_done.json").read_text()))
plays = {r["replay_tag"]: int(r["plays"]) for r in csv.DictReader(open(d / "battles.csv", encoding="utf-8"))}
n = collections.Counter(); pos = collections.Counter(); ivals = collections.Counter()
for r in csv.DictReader(open(d / "plays_ext_i1.csv", encoding="utf-8")):
    n[r["replay_tag"]] += 1
    if r.get("attr_ability") == "1" or r["x_units"] not in ("", "None"):
        pos[r["replay_tag"]] += 1
    if r["x_units"] not in ("", "None"): ivals[r["attr_i"]] += 1
ok = sorted(t for t in done if n[t] == plays.get(t, -1) and pos[t] == n[t])
bad = sorted(t for t in done if t not in ok)
(here / f"{deck}_i1_tags.json").write_text(json.dumps(ok))
print(json.dumps({"deck": deck, "done": len(done), "usable": len(ok), "rejected": len(bad), "rejected_tags": bad[:10],
                  "i_values": dict(ivals)}))
