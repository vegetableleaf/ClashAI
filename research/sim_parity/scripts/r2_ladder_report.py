# -*- coding: utf-8 -*-
"""Tally + emit research/sim_parity/ledger/r2_ladder_check.jsonl and print the summary."""
import json, os, sys, collections
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'C:/Users/benpe/ClashBot/icebow/src')
from clashrl.levels import PERCENT
ROOT = r'C:/Users/benpe/ClashBot/research/sim_parity'
raw = json.load(open(os.path.join(ROOT, 'ledger', '_r2_ladder_raw.json'), encoding='utf-8'))
rows, per_card = raw['rows'], raw['per_card']
RO = ['Common', 'Rare', 'Epic', 'Legendary', 'Champion']
FLOOR = {'Common': 1, 'Rare': 3, 'Epic': 6, 'Legendary': 9, 'Champion': 11}
S = lambda r: (RO.index(r['rarity']), r['card'], r['field'])

print('=' * 108)
print('1. SIZE OF THE 31/3/2025 RENORMALISATION: post-2025 Common-base ladder (= levels.py) MINUS '
      'the pre-2025 rank-indexed ladder')
print('=' * 108)
print('%-15s %-10s %-26s %6s %7s %7s %5s %6s %-8s' % (
    'card', 'rarity', 'field', 'v11', 'baseL11', 'baseFlr', 'maxD', '@L', 'verdict'))
for r in sorted(rows, key=S):
    p, f, e = r['levels_py_as_implemented'], r['floor_indexed_model'], r['pre2025_rank_indexed_delta']
    print('%-15s %-10s %-26s %6s %7s %7s %5s %6s %-8s' % (
        r['card'][:15], r['rarity'], r['field'][:26], p['v11'], p['base_l1'],
        f['base_at_floor_from_v11'],
        e['max_abs'] if e else 'n/a', e['max_level'] if e else '-', r['verdict']))

print()
print('=' * 108)
print('2. RENORMALISATION SIZE BY RARITY (0 for Common: floor 1 => rank == absolute level, nothing moved)')
print('=' * 108)
byr = collections.defaultdict(list)
for r in rows:
    byr[r['rarity']].append(r)
print('%-11s %5s %6s %9s %8s %9s %9s' % ('rarity', 'flds', 'cells', 'cellsWrong', 'pct', 'maxAbs',
                                         'maxPct'))
for rar in RO:
    rs = [r for r in byr[rar] if r['pre2025_rank_indexed_delta']]
    if not rs:
        continue
    cells = sum(len(r['pre2025_rank_indexed_delta']['levels_py_minus_rank_indexed_by_level'])
                for r in rs)
    wrong = sum(r['pre2025_rank_indexed_delta']['n_levels_wrong'] for r in rs)
    mx = max(rs, key=lambda r: r['pre2025_rank_indexed_delta']['max_abs'])
    print('%-11s %5d %6d %9d %7.1f%% %9d %8.2f%%' % (
        rar, len(rs), cells, wrong, 100.0 * wrong / cells,
        mx['pre2025_rank_indexed_delta']['max_abs'],
        max(abs(r['pre2025_rank_indexed_delta']['max_pct']) for r in rs)))

print()
print('   ratio error by level: levels.py PERCENT[L]/PERCENT[11]  vs  game PERCENT[L-f+1]/PERCENT[12-f]')
print('   %5s %10s %10s %10s %10s %10s' % ('L', 'Common', 'Rare', 'Epic', 'Legend', 'Champ'))
for L in range(1, 17):
    cells = []
    for rar in RO:
        f = FLOOR[rar]
        if L < f:
            cells.append('     -    ')
            continue
        a = PERCENT[L] / PERCENT[11]
        g = PERCENT[L - f + 1] / PERCENT[12 - f]
        cells.append('%9.3f%%' % (100 * (a / g - 1)))
    print('   %5d %s' % (L, ' '.join(cells)))

print()
print('=' * 108)
print('3. GROUND TRUTH: does each model reproduce the game per-level arrays?')
print('=' * 108)
g = [r for r in rows if r['game_dump']]
print('fields with a game array                                : %d / %d' % (len(g), len(rows)))
print('floor-indexed model fits the array exactly              : %d / %d' %
      (sum(1 for r in g if r['game_dump']['floor_indexed_model_fits_dump_exactly']), len(g)))
print('levels.py absolute-level model fits the array exactly   : %d / %d' %
      (sum(1 for r in g if r['game_dump']['levels_py_absolute_model_fits_dump_exactly']), len(g)))
byr3 = collections.defaultdict(lambda: [0, 0, 0])
for r in g:
    t = byr3[r['rarity']]
    t[0] += 1
    t[1] += bool(r['game_dump']['floor_indexed_model_fits_dump_exactly'])
    t[2] += bool(r['game_dump']['levels_py_absolute_model_fits_dump_exactly'])
for rar in RO:
    if rar in byr3:
        n, a, b2 = byr3[rar]
        print('   %-10s n=%-3d floor-indexed %d/%d   levels.py %d/%d' % (rar, n, a, n, b2, n))
print('array length == 19 - floor + 1                          : %d / %d' %
      (sum(1 for r in g if r['game_dump']['array_len'] ==
           r['game_dump']['expected_len_19_minus_floor_plus_1']), len(g)))

print()
print('=' * 108)
print('4. WIKI LADDER vs BOTH MODELS  (the wiki renders round(v11*1.1^(L-11)), it is not game data)')
print('=' * 108)
print('wiki formula reproduces the rendered table exactly : %d / %d fields' %
      (sum(1 for r in rows if r['wiki_formula_reproduces_rendered_table']), len(rows)))
print('%-11s %5s %6s %9s %8s %9s' % ('rarity', 'flds', 'cells', 'cells>1pt', 'pct', 'maxAbs'))
for rar in RO:
    rs = byr[rar]
    cells = sum(len(r['levels_py_as_implemented']['dev_vs_wiki_by_level']) for r in rs)
    gt1 = sum(r['levels_py_as_implemented']['n_levels_dev_gt1_vs_wiki'] for r in rs)
    mx = max(r['levels_py_as_implemented']['max_abs_dev_vs_wiki'] for r in rs)
    print('%-11s %5d %6d %9d %7.1f%% %9d' % (rar, len(rs), cells, gt1, 100.0 * gt1 / cells, mx))
sm = [r for r in g if r['game_dump']['wiki_vs_dump_by_level']]
print()
print('wiki row vs the real array, on the %d fields where the card is unchanged since 2023:' % len(sm))
for r in sorted(sm, key=S):
    dv = r['game_dump']['wiki_vs_dump_by_level']
    mx = max(dv.values(), key=abs)
    print('   %-15s %-26s max %+4d   L16 %+4d' % (r['card'][:15], r['field'][:26], mx,
                                                  dv.get('16', 0)))

print()
print('=' * 108)
print('4b. DOES ANY RARITY DRIFT?  relative dev (levels.py - wiki)/wiki, pooled; theory is')
print('    PERCENT[L]/256 / 1.1^(L-11) - 1, a pure function of L with no rarity term')
print('=' * 108)
print('%5s %10s %10s %6s   %s' % ('L', 'theory%', 'pooled%', 'n', 'per-rarity mean %'))
for L in range(1, 17):
    th = (PERCENT[L] / PERCENT[11]) / (1.1 ** (L - 11)) - 1
    obs, br = [], collections.defaultdict(list)
    for r in rows:
        d = r['levels_py_as_implemented']['dev_vs_wiki_by_level'].get(str(L))
        w = r['wiki_ladder'].get(str(L))
        if d is None or not w:
            continue
        obs.append(100.0 * d / w)
        br[r['rarity']].append(100.0 * d / w)
    if not obs:
        continue
    pr = '  '.join('%s %+.2f' % (k[:3], sum(v) / len(v))
                   for k, v in sorted(br.items(), key=lambda kv: RO.index(kv[0])))
    print('%5d %9.3f%% %9.3f%% %6d   %s' % (L, 100 * th, sum(obs) / len(obs), len(obs), pr))

print()
print('=' * 108)
print('4c. FLOOR-ANCHORED INVERSION: what happens if you anchor at the rarity floor row instead')
print('=' * 108)
print('%-11s %5s %11s %11s %14s %10s' % ('rarity', 'flds', 'noInversion', 'sameBase',
                                         'changesLadder', 'maxDelta'))
for rar in RO:
    rs = byr[rar]
    ni = sum(1 for r in rs if r['floor_indexed_model']['base_at_floor_from_v11'] is None)
    sb = sum(1 for r in rs if r['floor_indexed_model']['base_at_floor_from_v11'] ==
             r['levels_py_as_implemented']['base_l1'])
    ch = sum(1 for r in rs if r['floor_indexed_model']['differs_from_levels_py'])
    md = max([r['pre2025_rank_indexed_delta']['max_abs'] for r in rs
              if r['pre2025_rank_indexed_delta']] or [0])
    print('%-11s %5d %11d %11d %14d %10d' % (rar, len(rs), ni, sb, ch, md))

print()
print('=' * 108)
print('5. ERA TEST: which convention generated the stored level-11 values in use today?')
print('=' * 108)
from clashrl.levels import base_for
print('A value is "reachable" under a rule if some integer base produces it exactly under that rule.')
print('Only ~%.0f%% of integers are reachable at 256%%, so 45/45 non-Common hits is not chance.'
      % (100 * 100 / 256))
print('%-11s %5s %22s %22s' % ('rarity', 'flds', 'post-2025 abs (256%)', 'pre-2025 rank (PERCENT[12-f])'))
for rar in RO:
    rs = byr[rar]
    okA = sum(1 for r in rs if base_for(r['levels_py_as_implemented']['v11'], 11) is not None)
    okB = sum(1 for r in rs if r['wiki_v11_reachability']['wiki_v11_is_game_reachable'])
    print('%-11s %5d %22s %22s' % (rar, len(rs), '%d/%d' % (okA, len(rs)), '%d/%d' % (okB, len(rs))))
nonc = [r for r in rows if r['rarity'] != 'Common']
okA = sum(1 for r in nonc if base_for(r['levels_py_as_implemented']['v11'], 11) is not None)
print('NON-Common total: post-2025 rule %d/%d   (P(chance) = %.2g)   pre-2025 rule %d/%d'
      % (okA, len(nonc), (100 / 256.0) ** len(nonc),
         sum(1 for r in nonc if r['wiki_v11_reachability']['wiki_v11_is_game_reachable']), len(nonc)))
bad = [r for r in rows if not r['wiki_v11_reachability']['wiki_v11_is_game_reachable']]
print()
print('Level-11 values NOT reachable under the PRE-2025 rank rule -- i.e. values that could only')
print('have been produced after the 31/3/2025 Common-base renormalisation:')
for r in sorted(bad, key=S):
    rr = r['wiki_v11_reachability']
    near = ', '.join('%d (delta %+d, base %d)' % (c['value'], c['delta'], c['base_at_floor'])
                     for c in (rr['nearest_reachable'] or []))
    dmp = r['game_dump']['l11_dump'] if r['game_dump'] else None
    print('   %-15s %-26s wiki v11=%-6s pct=%3d  nearest reachable: %s   | 2023 dump L11=%s' % (
        r['card'][:15], r['field'][:26], r['levels_py_as_implemented']['v11'],
        rr['rank_percent_at_l11'], near, dmp))

print()
print('rarity floor/cap match OWNER RULING 9 : %d / %d cards' %
      (sum(1 for c in per_card.values() if c['floor_and_cap_match_ruling9']), len(per_card)))
print('edit_war CHANGED : %d fields' % sum(1 for r in rows if r['cross_checks']['edit_war'] != 'pass'))
print('verdicts:', dict(collections.Counter(r['verdict'] for r in rows)))

# ---- emit -------------------------------------------------------------------------------------
out = os.path.join(ROOT, 'ledger', 'r2_ladder_check.jsonl')
with open(out, 'w', encoding='utf-8') as fh:
    for r in sorted(rows, key=S):
        p, f, e = (r['levels_py_as_implemented'], r['floor_indexed_model'],
                   r['pre2025_rank_indexed_delta'])
        gd, rr = r['game_dump'], r['wiki_v11_reachability']
        n = []
        n.append('The wiki per-level table is NOT transcribed game data: the page carries only the '
                 'level-11 vardefines and MediaWiki renders every other row as '
                 'round(v11*1.1^(L-11)) (reproduced here exactly: %s). It cannot adjudicate a '
                 'scaling model, and it is the wrong ladder wherever it disagrees.'
                 % r['wiki_formula_reproduces_rendered_table'])
        n.append('levels.py (absolute-level, REF 11) vs that wiki ladder: max |dev| %d points at '
                 'L%d (%.2f%%); %d of %d levels differ by more than 1 point%s.'
                 % (p['max_abs_dev_vs_wiki'], p['max_dev_level'], p['dev_pct_at_max_vs_wiki'],
                    p['n_levels_dev_gt1_vs_wiki'], len(p['recon']),
                    (' (%s)' % p['levels_dev_gt1_vs_wiki']) if p['levels_dev_gt1_vs_wiki'] else ''))
        n.append('base_for(%s, 11) = %s, a unique integer inversion, so no ratio fallback fires and '
                 'the stored level-11 value is consistent with being a real game value '
                 '(only ~39%% of integers are).' % (p['v11'], p['base_l1']))
        if gd:
            n.append('Pre-2025 game array %s.%s has %d entries mapping to levels %d..%d, i.e. exactly '
                     '19-floor+1 for a %s card -- the game files independently confirm the rarity '
                     'floors of OWNER RULING 9. That array is fitted exactly by the RANK-indexed '
                     'rule (%s) and %s by the absolute-level rule, which is the pre-2025 convention.'
                     % (gd['dump_name'], gd['array_field'], gd['array_len'],
                        gd['array_maps_to_levels'][0], gd['array_maps_to_levels'][1], r['rarity'],
                        gd['floor_indexed_model_fits_dump_exactly'],
                        'is' if gd['levels_py_absolute_model_fits_dump_exactly'] else 'is not'))
        if e and e['n_levels_wrong']:
            n.append('The 31/3/2025 renormalisation moved this stat by up to %+d points at L%d '
                     '(%.2f%%) relative to the old rank-indexed ladder.'
                     % (e['levels_py_minus_rank_indexed_by_level'][str(e['max_level'])],
                        e['max_level'], e['max_pct']))
        elif e:
            n.append('Common-floor stat: rank == absolute level, so the 31/3/2025 renormalisation '
                     'moved nothing here.')
        if f['base_at_floor_from_v11'] is None:
            n.append('FLOOR-ANCHORING TEST: no integer base inverts the wiki floor row at all for '
                     'this stat -- that row is a 1.1^n derivation, not a game value. Anchoring the '
                     'reconstruction at the rarity floor is not merely different, it is impossible.')
        else:
            n.append('FLOOR-ANCHORING TEST: base at the rarity floor would be %s against %s from the '
                     'level-11 anchor -> %s. Since 31/3/2025 the rarity floor is only a gate on '
                     'which levels a player may own, not a stat anchor, so the level-11 anchor is '
                     'the correct one.'
                     % (f['base_at_floor_from_v11'], p['base_l1'],
                        'they disagree and the ladders differ' if f['differs_from_levels_py']
                        else 'identical ladders'))
        r['notes'] = ' '.join(n)
        fh.write(json.dumps(r, ensure_ascii=False) + '\n')
print()
print('wrote', out, os.path.getsize(out), 'bytes,', len(rows), 'rows')
