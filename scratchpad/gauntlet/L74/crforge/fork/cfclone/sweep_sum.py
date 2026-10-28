# usage: cp_sum.py cp_X.tsv -- CloneProbe summary: scenes, outcomes by message (forms numbered out), clones made, spawner copies
import csv, re, sys, collections
rows = list(csv.DictReader(open(sys.argv[1]), delimiter="\t"))
print(sys.argv[1], "scenes", len(rows), "forms", len({r["form"] for r in rows}),
      "with a clone", sum(int(r["clones"]) > 0 for r in rows),
      "spawner copies", sum(int(r["spawner_copies"]) for r in rows),
      "clone children", sum(int(r["clone_children"]) for r in rows))
by = collections.defaultdict(set)
for r in rows:
    if r["outcome"] != "OK":
        msg = re.sub(r"\b[A-Za-z0-9]+_\d+(_\d+)*(_clone\d+)?\b", "#", r["outcome"])
        by[msg].add(r["form"])
for m, f in sorted(by.items(), key=lambda kv: -len(kv[1])):
    print(len(f), "forms |", m[:260], "|", ",".join(sorted(f))[:300])
