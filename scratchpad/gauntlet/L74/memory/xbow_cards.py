"""Per-opponent-card X-Bow counters from the pro memory tables (owner 10-25: analyse by card, not archetype).

For every OWN reach X-Bow whose lock window closed (xb_done): locked = princess -5 % in 600 ticks (habit_terms rule).
  answer view : X-Bows answered by card c (the opponent's first on-time play in the lane within 4 s / 12 tiles) -> lock rate
  deck view   : X-Bows in matches where the opponent played c at any time (whole match; NOT causal, a prior only)
Lift = lock rate with c - lock rate of all X-Bows. 95 % Wilson intervals.
Usage: python xbow_cards.py <memory_tables.npz> <dataset.npz (for card_vocab)> [min_n]
"""
import json
import math
import sys
import zipfile

import numpy as np

sys.path.insert(0, __file__.rsplit("scratchpad", 1)[0])
from pipeline.match_memory import _COL  # noqa: E402


def wilson(k, n, z=1.96):
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def main():
    mem, ds = sys.argv[1], sys.argv[2]
    min_n = int(sys.argv[3]) if len(sys.argv) > 3 else 200
    z = np.load(mem)
    off, vals, card, flag, ans = z["tab_off"], z["tab_vals"], z["tab_card"], z["tab_flag"], z["tab_ans_card"]
    with zipfile.ZipFile(ds) as zf:                 # meta only; the npz arrays stay unread
        meta = json.loads(str(np.load(zf.open("meta.npy"), allow_pickle=False)))
    vocab = meta["card_vocab"]
    name = (lambda i: vocab[i] if isinstance(vocab, list) else {v: k for k, v in vocab.items()}.get(i, str(i)))
    mine, reach, done, locked = (vals[:, _COL[k]] for k in ("mine", "xb_reach", "xb_done", "xb_locked"))
    is_play = vals[:, _COL["is_play"]] > 0
    tot = [0, 0]
    by_ans, by_deck = {}, {}
    for j in range(len(off) - 1):
        a, b = int(off[j]), int(off[j + 1])
        # xb_done is the RESOLVED value (the table stores final values; res says when they become visible)
        xb = [i for i in range(a, b) if flag[i] & 1 and reach[i] > 0]
        if not xb:
            continue
        opp = {int(card[i]) for i in range(a, b) if is_play[i] and mine[i] == 0 and card[i] > 0}
        for i in xb:
            if not done[i]:
                continue
            L = int(locked[i] > 0)
            tot[0] += L
            tot[1] += 1
            key = int(ans[i]) if flag[i] & 4 else 0
            s = by_ans.setdefault(key, [0, 0])
            s[0] += L
            s[1] += 1
            for c in opp:
                s = by_deck.setdefault(c, [0, 0])
                s[0] += L
                s[1] += 1
    base = tot[0] / tot[1]
    print(f"pro tables: {tot[1]} resolved own reach X-Bows, lock {base:.3f} {wilson(*tot)}")
    print(f"unanswered: n {by_ans.get(0, [0, 0])[1]} lock {by_ans.get(0, [0, 1])[0] / max(by_ans.get(0, [0, 1])[1], 1):.3f}")
    for title, d in (("ANSWER view (X-Bow answered by the card)", by_ans), ("DECK view (opponent played the card)", by_deck)):
        print(f"\n{title}, n >= {min_n}, sorted by lift (most X-Bow-denying first)")
        print(f"{'card':28s} {'n':>7s} {'lock':>6s} {'95% CI':>15s} {'lift':>7s}")
        rows = [(c, k, n) for c, (k, n) in d.items() if c and n >= min_n]
        for c, k, n in sorted(rows, key=lambda r: r[1] / r[2]):
            lo, hi = wilson(k, n)
            print(f"{name(c):28s} {n:7d} {k / n:6.3f} [{lo:.3f}, {hi:.3f}] {k / n - base:+7.3f}")


if __name__ == "__main__":
    main()
