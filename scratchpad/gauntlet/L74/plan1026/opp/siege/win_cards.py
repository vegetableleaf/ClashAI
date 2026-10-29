"""Human opponent plays per reach X-Bow window (rows: every play row, card identity y_card) from a live / HF row dir + its
memory tables: per card, plays in (t_x, t_x + 200] per window, and the share of windows with >= 1 such play, split by lock.
CB=... python win_cards.py ROWS_DIR MEM.npz OUT.json"""
import json, os, sys
from collections import Counter
from pathlib import Path
import numpy as np
CB = Path(os.environ["CB"])
sys.path[:0] = [str(CB), str(Path(__file__).resolve().parent)]
from pipeline.train_gen import load_dir            # noqa: E402
from pipeline.dataset_gen import load_memory_tables  # noqa: E402
import siege_a as SA                                # noqa: E402
arrs, meta = load_dir(Path(sys.argv[1]))
packed, row_tab, _ = load_memory_tables(Path(sys.argv[2]))
tick, row_tab = np.asarray(arrs["tick"]), np.asarray(row_tab)
grp, wid, W = SA.windows(packed, row_tab, tick)
voc = meta["card_vocab"]
play = (np.asarray(arrs["y_gate"]) > 0) & (np.asarray(arrs["y_card"]) > 0)
per = {}
for i in np.where(play & (wid >= 0))[0]:
    per.setdefault(int(wid[i]), Counter())[voc[int(arrs["y_card"][i])]] += 1
deck_of = {}                                       # window -> the seat's deck (deck_card of its first row)
dc = np.asarray(arrs["deck_card"])
for i in np.where(wid >= 0)[0]:
    deck_of.setdefault(int(wid[i]), {voc[int(c)] for c in dc[i] if c > 0})
out = {}
for lk in (None, 0, 1):
    ks = [k for k in range(len(W)) if lk is None or W[k][2] == lk]
    c, any_, indeck = Counter(), Counter(), Counter()
    for k in ks:
        indeck.update(deck_of.get(k, ()))
        for card, n in per.get(k, {}).items():
            c[card] += n; any_[card] += 1
    out["all" if lk is None else ("locked" if lk else "failed")] = {
        "windows": len(ks), "plays_per_window": sum(c.values()) / len(ks),
        "cards": {k: {"per_window": v / len(ks), "share_windows": any_[k] / len(ks), "in_deck": indeck[k],
                                 "p_given_deck": any_[k] / indeck[k] if indeck[k] else None} for k, v in c.most_common()}}
Path(sys.argv[3]).write_text(json.dumps(out, indent=1))
print(json.dumps({k: (v["windows"], round(v["plays_per_window"], 3)) for k, v in out.items()}))
# per card: plays per seat-match (seats with the card in the deck) and the share of them inside reach X-Bow windows
seat_deck = {}
for i in range(len(row_tab)):
    if row_tab[i] >= 0 and int(row_tab[i]) not in seat_deck:
        seat_deck[int(row_tab[i])] = {voc[int(c)] for c in dc[i] if c > 0}
seats_xb = {t for t, _, _ in W}
tot, inw, nseat = Counter(), Counter(), Counter()
for d in (seat_deck[t] for t in seats_xb):
    nseat.update(d)
for i in np.where(play & np.isin(row_tab, list(seats_xb)))[0]:
    k = voc[int(arrs["y_card"][i])]
    tot[k] += 1; inw[k] += int(wid[i] >= 0)
J = json.loads(Path(sys.argv[3]).read_text())
J["per_match"] = {k: {"seats": nseat[k], "plays_per_seat": tot[k] / nseat[k] if nseat[k] else None, "in_window_share": inw[k] / tot[k]}
                  for k in tot if nseat[k] >= 20}
Path(sys.argv[3]).write_text(json.dumps(J, indent=1))
