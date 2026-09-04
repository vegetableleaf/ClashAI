"""One instrument for every live-obs session: play rate, elixir profile, per-card presence/plays,
missing-slot and deadlock shares. argv: one or more npz paths."""
import sys, numpy as np
DECK = ['tornado','tesla','tesla_evo','ice_wizard','x_bow','rocket','knight','knight_evo','the_log','skeletons']
SPELL = {'tornado','rocket','the_log'}
for p in sys.argv[1:]:
    d = np.load(p); hand = d['hand']; ch = d['chosen']; el = d['elixir_vec'][:, 0] * 10.0  # policy-facing value (d['elixir'] is capped at 9; same field the s6 read used); m = d['match']
    m = d['match']
    n = len(el); play = ch[:, 0] == 1
    # hand rows are card-index one-hot-ish counts per deck slot; a "missing slot" = fewer than 4 cards known
    known = (hand > 0).sum(1)
    print(p)
    print(f"n {n} plays {play.sum()} ({play.mean():.3f}) elixir mean {el.mean():.2f} >=9 share {(el>=9).mean():.3f} hand size {known.mean():.2f}")
    for mi in np.unique(m):
        s = m == mi
        print(f"  match {mi}: n {s.sum():3d} plays {play[s].sum():3d} ({play[s].mean():.3f}) elixir {el[s].mean():.2f} >=9 {(el[s]>=9).mean():.2f} hand size {known[s].mean():.2f}")
    for lo, hi in ((0,4),(4,7),(7,9),(9,11)):
        s = (el >= lo) & (el < hi)
        if s.sum(): print(f"  elixir [{lo},{hi}): n {s.sum():3d} play share {play[s].mean():.3f}")
    pres = {DECK[i]: round(float((hand[:, i] > 0).mean()), 2) for i in range(10)}
    print("  present:", pres)
    pc = {}; 
    for i in range(10):
        c = int(((ch[:, 1] == i) & play).sum())
        if c: pc[DECK[i]] = c
    print("  plays by card:", pc)
    per100 = {k: round(100.0 * pc.get(k, 0) / max(1e-9, (hand[:, DECK.index(k)] > 0).sum()), 1) for k in DECK}
    print("  plays per 100 in-hand:", per100)
    miss = known < 4
    nonspell_vis = np.array([any(hand[r, i] > 0 and DECK[i] not in SPELL for i in range(10)) for r in range(n)])
    dead = miss & ~nonspell_vis
    print(f"  missing-slot share {miss.mean():.2f}  deadlock share {dead.mean():.2f}  (at >=9: {dead[el>=9].mean() if (el>=9).any() else float('nan'):.2f})")
