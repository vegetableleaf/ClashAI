"""Per card: P(played in window | in deck) in locked vs failed X-Bow windows (live rows, win_cards output). python lk_cards.py WC.json"""
import json, sys
J = json.load(open(sys.argv[1]))
lo, fa = J["locked"]["cards"], J["failed"]["cards"]
print(f"windows locked {J['locked']['windows']} failed {J['failed']['windows']}")
for k in sorted(set(lo) & set(fa), key=lambda k: -(lo[k]["in_deck"] + fa[k]["in_deck"])):
    if lo[k]["in_deck"] + fa[k]["in_deck"] >= 300:
        print(f"{k:16s} locked {lo[k]['p_given_deck']:.2f} (deck {lo[k]['in_deck']}) failed {fa[k]['p_given_deck']:.2f} (deck {fa[k]['in_deck']})")
