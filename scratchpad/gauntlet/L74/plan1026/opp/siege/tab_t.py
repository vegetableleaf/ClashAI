"""Compact side-by-side of siege_t tables.  python -I tab_t.py NAME [NAME ...]  (out/siege_t_<NAME>.json)"""
import json, sys
T = {n: json.load(open(f'out/siege_t_{n}.json'))['table'] for n in sys.argv[1:]}
f = lambda v: '-' if v is None else f'{v:.2f}' if isinstance(v, float) else str(v)  # noqa: E731
print('| fact |', ' | '.join(T), '|')
print('|---|' + '---|' * len(T))
print('| reach X-Bows / lock |', ' | '.join(f"{t['xbows']} / {f(t['lock'])}" for t in T.values()), '|')
for g in ('all', 'ontime_unit'):
    for k in ('first_tower', 'first_answer', 'first_other'):
        print(f'| {g}: first target {k[6:]} share (lock) |', ' | '.join(f"{f(t[g][k]['share'])} ({f(t[g][k]['lock'])}, n {t[g][k]['n']})" for t in T.values()), '|')
    for k in ('n_xb_targets_mean', 'plays_in_range_after_mean', 'xb_ever_tower', 'lock_if_never_tower', 'tower_dt_median', 'tower_share_of_life_mean', 'xb_life_median', 'xb_died_share'):
        print(f'| {g}: {k} |', ' | '.join(f(t[g][k]) for t in T.values()), '|')
g = 'ontime_unit'
for k in ('own_bodies_t0_mean', 'opp_bodies_t0_mean', 'answer_bodies_found'):
    print(f'| {g}: {k} |', ' | '.join(f(t[g][k]) for t in T.values()), '|')
for k in ('xb_hit_ans', 'ans_hits_xb', 'ans_alive_end', 'def_unit', 'def_tower'):
    print(f'| {g}: {k} share (lock if / if not) |', ' | '.join(f"{f(t[g][k]['share'])} ({f(t[g][k]['lock_if'])} / {f(t[g][k]['lock_ifnot'])})" for t in T.values()), '|')
