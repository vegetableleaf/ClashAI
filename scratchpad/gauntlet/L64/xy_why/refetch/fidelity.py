"""engine-vs-real fidelity from a replay_batch summary.jsonl (winner agreement, crowns, timing)."""
import json, sys, collections, statistics as st
def win(c):  # crowns [s0, s1] -> winner label
    if c is None: return None
    a, b = c[0], c[1]
    return 's0' if a > b else 's1' if b > a else 'draw'
for p in sys.argv[1:]:
    r = [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]
    ok = [x for x in r if x.get('ok')]
    pairs = collections.Counter((win(x['expected_crowns']), win(x['crowns'])) for x in ok)
    match = sum(c for (e, g), c in pairs.items() if e == g)
    acc = sum(x['accepted'] for x in ok) / max(1, sum(x['plays_driven'] for x in ok))
    tv = [x['terminal_vs_last_play'] for x in ok]
    print(f"{p}: {len(ok)} ok / {len(r)} rows; winner match {match}/{len(ok)} = {match/len(ok):.3f}; acc {acc:.4f}; exact crowns {sum(x['crowns_match'] for x in ok)/len(ok):.3f}")
    print("   (expected, engine):", dict(pairs))
    print(f"   terminal_vs_last_play median {st.median(tv):.0f} mean {st.mean(tv):.0f} neg {sum(t<0 for t in tv)}/{len(tv)}; final_tick median {st.median(x['final_tick'] for x in ok):.0f}")
    print("   term", dict(collections.Counter(x['termination_reason'] for x in ok)), "outcome", dict(collections.Counter(x['outcome'] for x in ok)))
    e1 = sum(win(x['expected_crowns']) == 's1' for x in ok); g1 = sum(win(x['crowns']) == 's1' for x in ok)
    print(f"   expected s1 wins {e1}/{len(ok)}  engine s1 wins {g1}")
