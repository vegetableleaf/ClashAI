# usage: sweep_sum2.py cp_X.tsv... -- CloneProbe runs: scenes, scenes with a clone, every Clone refusal (a message naming
# a clone or a Clone) in full, and the other failures grouped by kind with their forms; census = the census-deck forms
import csv, re, sys, collections
census = None
for path in sys.argv[1:]:
    rows = list(csv.DictReader(open(path), delimiter="\t"))
    bad = [r for r in rows if r["outcome"] != "OK"]
    clone = [r for r in bad if re.search(r"clone", r["outcome"], re.I) and "slot, a" not in r["outcome"] and "evolution or hero slot" not in r["outcome"]]
    print(f"{path}: scenes {len(rows)}, forms {len({r['form'] for r in rows})}, with a clone "
          f"{sum(int(r['clones']) > 0 for r in rows)}, spawner copies {sum(int(r['spawner_copies']) for r in rows)}, "
          f"not OK {len(bad)}, Clone refusals {len(clone)}")
    for r in clone:
        print("   CLONE", r["form"], r["T"], r["outcome"][:200])
    kinds = collections.defaultdict(set)
    for r in bad:
        if r in clone:
            continue
        o = r["outcome"]
        if "in a hero slot" in o or "in an evolution or hero slot" in o:
            k = "slot holds no such form (a non-form row of the sweep)"
        elif "outside a match" in o:
            k = "refused outside a match"
        else:
            k = re.sub(r"\b[A-Za-z0-9]+_\d+(_\d+)*\b", "#", o)[:110]
        kinds[k].add(r["form"])
    for k, f in sorted(kinds.items(), key=lambda kv: -len(kv[1])):
        fs = sorted(f)
        print(f"   other ({len(fs)} forms) {k}: {', '.join(fs[:12])}{' ...' if len(fs) > 12 else ''}")
