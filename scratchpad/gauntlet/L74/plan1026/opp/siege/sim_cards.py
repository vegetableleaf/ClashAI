"""SIM twin of win_cards.py: opponent plays per reach X-Bow window (t, t+200] by card, from out/siege_b_NAME.json made with
SIEGE_ALL=1 (bodiless spells kept) -- recomputed from the records.  python sim_cards.py ROWS_DIR OUT.json"""
import json, os, sys
from collections import Counter
os.environ["SIEGE_ALL"] = "1"
import siege_b as SB
data = SB.sim_xbows(sys.argv[1])
out = {}
recs = [(r, x) for r, xs in data for x in xs]
for lk in (None, 0, 1):
    ks = [(r, x) for r, x in recs if lk is None or x[3] == lk]
    c, any_, indeck = Counter(), Counter(), Counter()
    for r, (t, *_ ) in ks:
        indeck.update({d.replace('_', '-') for d in r['seen']})
        w = Counter(p[1].replace('_', '-') for p in r['plays'] if t < p[0] <= t + SB.T_ALL)
        c.update(w); any_.update(w.keys())
    out["all" if lk is None else ("locked" if lk else "failed")] = {
        "windows": len(ks), "plays_per_window": sum(c.values()) / len(ks),
        "cards": {k: {"per_window": v / len(ks), "share_windows": any_[k] / len(ks), "in_deck": indeck[k],
                                 "p_given_deck": any_[k] / indeck[k] if indeck[k] else None} for k, v in c.most_common()}}
json.dump(out, open(sys.argv[2], 'w'), indent=1)
print({k: (v["windows"], round(v["plays_per_window"], 3)) for k, v in out.items()})
tot, inw, nseat = Counter(), Counter(), Counter()
for r, xs in data:
    if not xs:
        continue
    nseat.update({d.replace('_', '-') for d in r['seen']})
    for p in r['plays']:
        k = p[1].replace('_', '-')
        tot[k] += 1; inw[k] += int(any(t < p[0] <= t + SB.T_ALL for t, *_ in xs))
out["per_match"] = {k: {"seats": nseat[k], "plays_per_seat": tot[k] / nseat[k] if nseat[k] else None, "in_window_share": inw[k] / tot[k]}
                    for k in tot if nseat[k] >= 20}
json.dump(out, open(sys.argv[2], 'w'), indent=1)
