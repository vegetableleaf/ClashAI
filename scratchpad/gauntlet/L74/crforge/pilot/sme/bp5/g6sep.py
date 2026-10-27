import json, collections
rows = [json.loads(l) for l in open("goal6_bp4R0.jsonl")]
d = [x for x in rows if x["pre"] and x["clean"] and x["out"] in ("crforge", "alt0") and x.get("x")]
sub = [x for x in d if 1 <= x["acq_age"] <= 3 and x["x"]["acq"] == x["held"]]
print(len(d), len(sub))
F = {"ref_before": lambda x: x["ref_before"], "ref_rp": lambda x: x["ref_rp"], "ref_since": lambda x: min(x["ref_since"], 9),
     "mutual": lambda x: x["mutual"], "age": lambda x: x["acq_age"], "u_state": lambda x: x["u_c"] and x["u_c"][0], "r_state": lambda x: x["r_c"] and x["r_c"][0],
     "u_tm": lambda x: x["u_c"] and x["u_c"][2], "r_tm": lambda x: x["r_c"] and x["r_c"][2], "same_t_acq": lambda x: x["ref_since"] == x["acq_age"],
     "uidx<ridx": lambda x: x["u_c"] and x["r_c"] and x["u_c"][3] < x["r_c"][3], "e1keep": lambda x: x["x"]["e1"] == x["held"]}
for nm, f in F.items():
    c = collections.Counter((f(x), x["out"]) for x in sub)
    print(nm, sorted(c.items(), key=str))
for x in sub:
    if x["out"] == "alt0": print({k: f(x) for k, f in F.items()})
