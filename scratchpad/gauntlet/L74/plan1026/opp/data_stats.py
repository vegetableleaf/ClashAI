"""Facts about a rows_to_npz file: in-slot tick histogram, card_ok share, ability labels, deck ids, context tokens, and a
LOWER bound on the right-censored slots the builder drops (no rows after a side's last play: wait rows need a later play).
usage: python data_stats.py ROWS.npz"""
import json
import sys
from collections import Counter

import numpy as np

z = np.load(sys.argv[1], allow_pickle=False)
meta = json.loads(str(z["meta"]))
g, s_ok, ev, st = z["y_gate"], z["slot_ok"] > 0, z["slot_ev"] > 0, z["slot_tick"]
w = z["row_w"]
rep, side, tick = z["rep"].astype(np.int64), z["side"].astype(np.int64), z["tick"].astype(np.int64)
out = {"rows": int(len(g)), "play_rows": int((g == 1).sum()), "slot_rows": int(s_ok.sum()),
       "slot_rows_weighted": float(w[s_ok].sum()), "events": int((s_ok & ev).sum()),
       "event_rate_weighted": float((w[s_ok] * ev[s_ok]).sum() / w[s_ok].sum()),
       "slot_tick_hist": {int(k): int(v) for k, v in sorted(Counter(st[s_ok & ev].tolist()).items())},
       "card_ok_share_of_play_rows": float((z["card_ok"][g == 1] > 0).mean()),
       "ab_slots": int((z["ab_ok"] > 0).sum()), "ab_events": int((z["ab_ev"] > 0).sum()),
       "deck_ids": int(z["deck_gid"].max()), "rows_with_deck_id": float((z["deck_gid"] > 0).mean()),
       "ctx_band": dict(Counter(z["ctx_band"].tolist())), "ctx_mode": dict(Counter(z["ctx_mode"].tolist())),
       "split": dict(Counter(z["split"].tolist())), "replays": int(len(z["tags"]))}
# censoring lower bound: per match, end >= the last row tick of either side; a side's slots after its last grid row are
# missing (each would be a no-play slot)
key = rep * 2 + side
last_side = {}
for k, t in zip(key[s_ok], tick[s_ok]):
    last_side[k] = max(last_side.get(k, -1), t)
end = {}
for r, t in zip(rep, tick):
    end[r] = max(end.get(r, -1), t)
miss = sum(max(0, (end[k // 2] - t) // 10) for k, t in last_side.items())
out["censored_slots_lower_bound"] = int(miss)
out["censored_share_of_slots_lower_bound"] = float(miss / max(out["slot_rows_weighted"] + miss, 1))
out["meta_stats"] = meta.get("stats")
print(json.dumps({k: (v if not isinstance(v, dict) else {str(a): b for a, b in v.items()}) for k, v in out.items()}, indent=1))
