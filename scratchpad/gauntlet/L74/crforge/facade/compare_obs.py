"""F1b: plays per side, refusals and near-idle matches (< 20 accepted plays on a side) of accept_f1 obs runs."""
import json
import sys

for path in sys.argv[1:]:
    r = json.load(open(path))["result"]
    rows = r["rows"]
    ref, idle, acc_l, acc_o = {}, [], [], []
    for x in rows:
        for k, v in (x["refuse_reasons"] or {}).items():
            ref[k] = ref.get(k, 0) + v
        a, o = x["plays_accepted"], x["opp_side"]["plays_accepted"]
        acc_l.append(a)
        acc_o.append(o)
        if min(a, o) < 20:
            idle.append((x["tag"], a, o))
    att = sum(x["plays_attempted"] for x in rows) + sum(x["opp_side"]["plays_attempted"] for x in rows)
    print(json.dumps(dict(run=path, matches=len(rows), learner_accepted_mean=round(sum(acc_l) / len(rows), 1),
                          opp_accepted_mean=round(sum(acc_o) / len(rows), 1), learner_attempted=sum(x["plays_attempted"] for x in rows),
                          learner_refusals=ref, near_idle=idle, wins=[x["outcome"] for x in rows].count("win"),
                          all_attempted=att, unmapped=r.get("facade_unmapped"))))
