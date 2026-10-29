"""Print siege_b tables side by side: python tab_b.py NAME [NAME ...] (out/siege_b_NAME.json)."""
import json, sys
T = {n: json.load(open(f'out/siege_b_{n}.json'))['table'] for n in sys.argv[1:]}
ks = sorted({k for t in T.values() for k in t['classes']})
print('| class | ' + ' | '.join(f'{n} n (share, lock)' for n in T) + ' |')
print('|---|' + '---|' * len(T))
print('| reach X-Bows (lock rate) | ' + ' | '.join(f"{t['xbows']} ({t['lock_rate']:.3f})" for t in T.values()) + ' |')
for k in ks:
    print(f'| {k} | ' + ' | '.join((lambda c: f"{c['n']} ({c['share']:.3f}, {c['lock_rate']:.2f})" if c else '-')(t['classes'].get(k)) for t in T.values()) + ' |')
for k in ('starved_spent_ge4', 'not_starved'):
    print(f'| {k} share (lock, none+elsewhere) | ' + ' | '.join(f"{t[k]['share']:.3f} ({t[k]['lock_rate']:.2f}, {t[k]['none_or_elsewhere']:.2f})" for t in T.values()) + ' |')
print('| on-time answer dt median (ticks) | ' + ' | '.join(str(t['ontime_answer_dt_median']) for t in T.values()) + ' |')
for n, t in T.items():
    print(n, 'on-time answer cards:', t['ontime_answer_cards_top12'][:10])
