import json, collections, sys
rows = [json.loads(l) for l in open(sys.argv[1])]
d = [x for x in rows if x["pre"] and x["clean"] and x["out"] in ("crforge", "alt0") and x.get("x")]
print("deciding clean with rpx", len(d), "chk ok", sum(1 for x in d if x["chk"]))
for nm in ("e1", "e2", "e3", "e4", "e5", "e6", "acq"):
    c = collections.Counter((x["out"], x["x"][nm] == x["held"]) for x in d if x["x"][nm] != -2)
    print("%-4s crforge&changes %6d  alt0&keeps %d  | contradicted: crforge but keeps %6d, alt0 but changes %d" % (nm, c[("crforge", False)], c[("alt0", True)], c[("crforge", True)], c[("alt0", False)]))
c = collections.Counter((min(x["acq_age"], 9), x["out"], x["x"]["acq"] == x["held"]) for x in d)
for k in sorted(c): print("acq_age", k, c[k])
