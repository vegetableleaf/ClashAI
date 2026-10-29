"""Side by side: per-window card rates, live rows vs SIM (win_cards / sim_cards outputs). python cmp_cards.py LIVE.json SIM.json"""
import json, sys
L, S = (json.load(open(f))['all'] for f in sys.argv[1:3])
print(f"plays per 10-s window: live {L['plays_per_window']:.2f} SIM {S['plays_per_window']:.2f}  (windows {L['windows']} / {S['windows']})")
ks = sorted(set(L['cards']) | set(S['cards']), key=lambda k: -(L['cards'].get(k, {}).get('per_window', 0)))
g = lambda d, k: d['cards'].get(k, {}).get('p_given_deck') or 0
n = lambda d, k: d['cards'].get(k, {}).get('in_deck', 0)
print('| card | live P(played in window / in deck) (windows with it in deck) | SIM | SIM - live |')
print('|---|---|---|---|')
for k in [k for k in ks if n(L, k) >= 60 and n(S, k) >= 60][:35]:
    print(f'| {k} | {g(L, k):.3f} ({n(L, k)}) | {g(S, k):.3f} ({n(S, k)}) | {g(S, k) - g(L, k):+.3f} |')
