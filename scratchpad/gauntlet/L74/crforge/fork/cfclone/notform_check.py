# usage: notform_check.py TABLESDIR cp_match.tsv census_decks.tsv -- the EV1 forms a match-mode sweep did not play
# evolved, split by their spells_evolved row's NotInUse, and whether a census deck carries each in an evolution slot
import csv, json, os, sys
rows = json.load(open(os.path.join(sys.argv[1], "spells_evolved.json")))["rows"]
scenes = list(csv.DictReader(open(sys.argv[2]), delimiter="\t"))
census = set()
for line in open(sys.argv[3]):
    f = line.rstrip("\n").split("\t")
    if len(f) < 5:
        continue
    for side in (0, 1):
        d, s = f[1 + 2 * side].split(","), f[2 + 2 * side].split(",")
        census.update(d[i] + "_EV1" for i in range(8) if s[i] == "1")
ev1 = sorted({r["form"] for r in scenes if r["form"].endswith("_EV1")})
notform = {r["form"] for r in scenes if "NOT_FORM" in r["outcome"]}
for label, sel in (("played evolved", [f for f in ev1 if f not in notform]), ("not evolved", sorted(notform))):
    print(label, len(sel))
    for f in sel:
        c = rows.get(f, {}).get("columns", {})
        print("  ", f, "NotInUse" if c.get("NotInUse") else "in use", "census" if f in census else "-")
