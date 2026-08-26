# -*- coding: utf-8 -*-
"""CROSS-CHECK 3 -- level-ladder integrity per rarity.

Four ladders are compared per card and per per-level stat column:

  W   wiki rendered ladder      round(v11 * 1.1^(L-11))                     [live revid, archived]
  P   levels.py as implemented  floor(base_for(v11,11) * PERCENT[L]/100)    [absolute-level index]
  Pf  floor-indexed percent     floor(base_floor * PERCENT[L-floor+1]/100)  [game's actual rule]
  G   game per-level array      cr-api-data 2023-10-18 dump, arr[i] = level floor+i

G is the adjudicator. It fits Pf exactly for all 405 arrays in the dump and fits P only for
Common cards, whose floor is 1 so the two indexings coincide.
"""
import json, re, os, sys, math
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'C:/Users/benpe/ClashBot/icebow/src')
from clashrl.levels import PERCENT, at_level, base_for, _pct

ROOT  = r'C:/Users/benpe/ClashBot/research/sim_parity'
CACHE = os.path.join(ROOT, 'webcache')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from r2_ladder_extract import stat_table

FLOOR = {'Common': 1, 'Rare': 3, 'Epic': 6, 'Legendary': 9, 'Champion': 11}
CAP   = 16
META  = json.load(open(os.path.join(ROOT, 'ledger', 'r2_ladder_fetchmeta.json'), encoding='utf-8'))

_d = json.load(open(r'C:/Users/benpe/ClashBot/icebow/data/webcache/4d3032da0d552e2dd7bc.json',
                    encoding='utf-8'))
_b = json.loads(_d['body']) if isinstance(_d['body'], str) else _d['body']
DUMP = {c['name']: c for c in _b['characters'] if c.get('name')}
DUMP_SRC = ('RoyaleAPI/cr-api-data commit d5461b0 2023-10-18 '
            '(cached icebow/data/webcache/4d3032da0d552e2dd7bc.json)')

DUMPNAME = {
 'Knight': 'Knight', 'Archers': 'Archer', 'Skeletons': 'Skeleton', 'Bomber': 'Bomber',
 'Musketeer': 'Musketeer', 'Hog Rider': 'HogRider', 'Valkyrie': 'Valkyrie', 'Wizard': 'Wizard',
 'P.E.K.K.A.': 'Pekka', 'Witch': 'Witch', 'Golem': 'Golem', 'Baby Dragon': 'BabyDragon',
 'Princess': 'Princess', 'Miner': 'Miner', 'Sparky': 'ZapMachine',
 'Electro Wizard': 'ElectroWizard', 'Mighty Miner': 'MightyMiner',
 'Archer Queen': 'ArcherQueen', 'Golden Knight': 'GoldenKnight', 'Skeleton King': 'SkeletonKing',
}
# (card, column-slug prefix) -> dump name for a SPAWNED sub-unit. `not_` excludes prefixes that
# merely share the same first word -- skeleton_king_* is the champion himself, not his Skeletons.
SUBUNIT = {('Golem', 'golemite', ()): 'Golemite',
           ('Witch', 'skeleton', ()): 'Skeleton',
           ('Skeleton King', 'skeleton', ('skeleton_king',)): 'SkeletonKingSkeleton'}
SUBUNIT_RARITY = {'SkeletonKingSkeleton': 'Common', 'Skeleton': 'Common'}   # spawned units

# The dump carries only hitpoints_per_level / damage_per_level. Map a wiki column to an array
# ONLY where it is genuinely that array; secondary damages (death, crown-tower, zap, dash,
# escape, later attack stages) have no per-level array in the dump and must not borrow one.
PRIMARY_DAMAGE_SLUGS = {'damage', 'area_damage', 'golem_damage', 'golemite_damage',
                        'skeleton_damage', 'skeleton_king_damage', '1_stage_damage'}


def php_round(x):
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


def slug(s):
    s = s.lower().replace('.', '').replace('(', '').replace(')', '')
    return re.sub(r'[^a-z0-9]+', '_', s).strip('_')


def first_int(cell):
    m = re.search(r'-?\d[\d,]*', cell.replace('\u2009', ''))
    return int(m.group(0).replace(',', '')) if m else None


def rank_pct(L, floor):
    """The percent slot the game uses for level L of a card whose rarity floor is `floor`."""
    return PERCENT[max(1, min(19, L - floor + 1))]


def base_at_floor(v, L, floor):
    """Unique integer base (the value at the rarity floor) with floor(b*PERCENT[rank]/100)==v."""
    if v != int(v) or v <= 0:
        return None
    v, p = int(v), rank_pct(L, floor)
    lo = -(-v * 100 // p)
    hi = -(-(v + 1) * 100 // p)
    hits = [b for b in range(lo, hi) if b * p // 100 == v]
    return hits[0] if len(hits) == 1 else None


rows, per_card = [], {}
for title, meta in META.items():
    if 'rendered_file' not in meta:
        continue
    rarity = meta['rarity']
    floor = FLOOR[rarity]
    hdr, table = stat_table(os.path.join(CACHE, meta['rendered_file']))
    lv_rows = {}
    for r in table:
        L = first_int(r[0])
        if L is not None:
            lv_rows[L] = r
    levels = sorted(lv_rows)
    key = slug(title)
    per_card[key] = {'card': title, 'rarity': rarity, 'floor_level': floor, 'levels': levels,
                     'floor_and_cap_match_ruling9': levels[0] == floor and levels[-1] == CAP,
                     'revid': meta.get('revid_rendered'), 'n_fields': 0}

    for ci, colname in enumerate(hdr):
        if ci == 0 or 'per second' in colname.lower():
            continue
        cslug = slug(colname)

        # spawned sub-units carry their own (Common) rarity floor, not the parent card's
        dname = None
        for (card, pref, notpref), nm in SUBUNIT.items():
            if card == title and cslug.startswith(pref)                     and not any(cslug.startswith(x) for x in notpref):
                dname = nm
        sub = dname is not None
        if dname is None:
            dname = DUMPNAME.get(title)
        f_eff = FLOOR[SUBUNIT_RARITY[dname]] if (sub and dname in SUBUNIT_RARITY) else floor

        ladder = {}
        ok = True
        for L in levels:
            cells = lv_rows[L]
            v = first_int(cells[ci]) if ci < len(cells) else None
            if v is None:
                ok = False
                break
            ladder[L] = v
        if not ok or 11 not in ladder:
            continue
        v11 = ladder[11]

        # ---- W ---------------------------------------------------------------------------
        wiki_repro = all(php_round(v11 * 1.1 ** (L - 11)) == ladder[L] for L in levels)

        # ---- P : levels.py exactly as implemented today -----------------------------------
        b11 = base_for(v11, 11)
        rec_P = ({L: at_level(b11, L) for L in levels} if b11 is not None
                 else {L: v11 * (_pct(L) / _pct(11)) for L in levels})

        # ---- Pf : the game's floor-indexed rule, anchored on the same stored v11 -----------
        bf = base_at_floor(v11, 11, f_eff)
        rec_Pf = ({L: int(bf * rank_pct(L, f_eff) // 100) for L in levels}
                  if bf is not None else None)

        dev_PW = {L: rec_P[L] - ladder[L] for L in levels}
        gt1_PW = sorted(L for L in levels if abs(dev_PW[L]) > 1)
        mxPW = max(levels, key=lambda L: abs(dev_PW[L]))

        if rec_Pf is not None:
            dev_PPf = {L: rec_P[L] - rec_Pf[L] for L in levels}
            gt1_PPf = sorted(L for L in levels if abs(dev_PPf[L]) > 1)
            mxPPf = max(levels, key=lambda L: abs(dev_PPf[L]))
            sim_err = {
                'what_this_is': ('the size of the 31/3/2025 renormalisation for this stat: how far '
                                 'the pre-2025 rank-indexed ladder sat from the post-2025 '
                                 'Common-base ladder that levels.py implements. NOT a current '
                                 'sim error -- the game moved to the levels.py convention.'),
                'levels_py_minus_rank_indexed_by_level': {str(L): dev_PPf[L] for L in levels},
                'max_abs': abs(dev_PPf[mxPPf]), 'max_level': mxPPf,
                'max_pct': round(100.0 * dev_PPf[mxPPf] / max(1, rec_Pf[mxPPf]), 3),
                'levels_wrong': sorted(L for L in levels if dev_PPf[L] != 0),
                'n_levels_wrong': sum(1 for L in levels if dev_PPf[L] != 0),
                'levels_wrong_gt1': gt1_PPf,
            }
        else:
            sim_err = None

        # ---- G ------------------------------------------------------------------------------
        arr_key = ('hitpoints_per_level' if cslug.endswith('hitpoints') else
                   'damage_per_level' if cslug in PRIMARY_DAMAGE_SLUGS else None)
        ent = DUMP.get(dname)
        arr = ent.get(arr_key) if (ent and arr_key) else None
        game = None
        if arr:
            g = {f_eff + i: arr[i] for i in range(len(arr)) if f_eff + i <= CAP}
            base_dump = arr[0]
            fitPf = all(int(base_dump * rank_pct(L, f_eff) // 100) == g[L] for L in g)
            bA = base_for(g[11], 11) if 11 in g else None
            fitP = (bA is not None and all(at_level(bA, L) == g[L] for L in g))
            same_era = (g.get(11) == v11)
            game = {
                'source': DUMP_SRC, 'dump_name': dname, 'array_field': arr_key,
                'array_maps_to_levels': [min(g), max(g)],
                'array_len': len(arr), 'expected_len_19_minus_floor_plus_1': 19 - f_eff + 1,
                'base_at_floor_dump': base_dump, 'l11_dump': g.get(11),
                'dump_ladder': {str(L): g[L] for L in sorted(g)},
                'floor_indexed_model_fits_dump_exactly': fitPf,
                'levels_py_absolute_model_fits_dump_exactly': fitP,
                'l11_dump_equals_wiki_l11': same_era,
                'levels_py_vs_dump_by_level': ({str(L): at_level(bA, L) - g[L] for L in g}
                                               if bA is not None else None),
                'levels_py_vs_dump_max_abs': (max(abs(at_level(bA, L) - g[L]) for L in g)
                                              if bA is not None else None),
                'wiki_vs_dump_by_level': ({str(L): ladder[L] - g[L] for L in g if L in ladder}
                                          if same_era else None),
                'stale_note': ('dump is 2023-10-18. INDEXING and STRUCTURE conclusions are '
                               'era-independent; absolute-value comparisons are only quoted where '
                               'l11_dump_equals_wiki_l11 is true.'),
            }

        # ---- is the wiki level-11 value even a value the game can emit? ---------------------
        reach = {
            'rank_percent_at_l11': rank_pct(11, f_eff),
            'base_at_floor_from_wiki_v11': bf,
            'wiki_v11_is_game_reachable': bf is not None,
            'nearest_reachable': None,
        }
        if bf is None:
            cands = []
            for delta in (1, -1, 2, -2, 3, -3):
                bb = base_at_floor(v11 + delta, 11, f_eff)
                if bb is not None:
                    cands.append({'value': v11 + delta, 'delta': delta, 'base_at_floor': bb})
            reach['nearest_reachable'] = cands[:2]

        # ---- verdict -------------------------------------------------------------------------
        ew = meta.get('edit_war', 'pass')
        if ew == 'CHANGED':
            verdict = 'escalate'
        elif b11 is None:
            # levels.py would silently fall back to float ratio scaling for this stat
            verdict = 'escalate'
        elif gt1_PW:
            # levels.py is right and the wiki ladder is a 1.1^n artifact that disagrees by >1 point:
            # pin our value so a later wiki scrape does not "correct" it back to the artifact
            verdict = 'pin'
        else:
            verdict = 'match'

        rows.append({
            'key': key, 'field': cslug + '_ladder', 'card': title, 'rarity': rarity,
            'floor_level': floor, 'effective_floor_for_this_stat': f_eff, 'cap_level': levels[-1],
            'wiki_ladder': {str(L): ladder[L] for L in levels},
            'wiki_formula': 'round(v11 * 1.1^(L-11))  [MediaWiki #expr round 0]',
            'wiki_formula_reproduces_rendered_table': wiki_repro,
            'levels_py_as_implemented': {
                'rule': 'floor(base_for(v11,11) * PERCENT[L]/100)',
                'v11': v11, 'base_l1': b11, 'inversion_unique': b11 is not None,
                'recon': {str(L): rec_P[L] for L in levels},
                'dev_vs_wiki_by_level': {str(L): dev_PW[L] for L in levels},
                'max_abs_dev_vs_wiki': abs(dev_PW[mxPW]), 'max_dev_level': mxPW,
                'dev_pct_at_max_vs_wiki': round(100.0 * dev_PW[mxPW] / ladder[mxPW], 3),
                'levels_dev_gt1_vs_wiki': gt1_PW, 'n_levels_dev_gt1_vs_wiki': len(gt1_PW),
            },
            'floor_indexed_model': {
                'rule': 'floor(base_at_floor * PERCENT[L-floor+1]/100)',
                'floor_level_used': f_eff,
                'base_at_floor_from_v11': bf,
                'recon': ({str(L): rec_Pf[L] for L in levels} if rec_Pf else None),
                'differs_from_levels_py': (sim_err['n_levels_wrong'] > 0) if sim_err else None,
            },
            'pre2025_rank_indexed_delta': sim_err,
            'era': {
                'renormalisation_date': '2025-03-31',
                'patch_note_verbatim': ('All troop stats have now been defined with Common Rarity '
                                        'as the base, solving many level scaling inconsistencies.'),
                'meaning': ('before 31/3/2025 the game indexed the percent table by RANK within '
                            'rarity (slot = level - floor + 1); after it, every card has a '
                            'Common-style level-1 base and the table is indexed by ABSOLUTE level, '
                            'which is exactly what levels.py implements.'),
                'source': {'url': 'https://clashroyale.fandom.com/wiki/Version_History/2025',
                           'revid': 436887, 'fetched': '2026-08-26',
                           'archive': 'research/sim_parity/webcache/Version_History_2025.wikitext'},
            },
            'wiki_v11_reachability': reach,
            'game_dump': game,
            'sources': [{
                'url': 'https://clashroyale.fandom.com/wiki/' + title.replace(' ', '_'),
                'revid': meta.get('revid_live'), 'revid_rendered': meta.get('revid_rendered'),
                'revid_cached_0825_26': meta.get('revid_cached'), 'fetched': '2026-08-26',
                'raw': 'rendered #unit-statistics-table L%s..L%s' % (levels[0], levels[-1]),
                'archive': 'research/sim_parity/webcache/' + meta['rendered_file'],
            }, {
                'url': 'https://github.com/RoyaleAPI/cr-api-data (commit d5461b0, 2023-10-18)',
                'revid': 'd5461b0a59bff33c4da2fc845b07275b66b2d6ff', 'fetched': '2026-08-16',
                'raw': ('%s.%s = %s' % (dname, arr_key, arr[:6]) if arr else 'no array'),
                'archive': 'icebow/data/webcache/4d3032da0d552e2dd7bc.json',
            }],
            'cross_checks': {'edit_war': ew},
            'verdict': verdict,
        })
        per_card[key]['n_fields'] += 1

json.dump({'rows': rows, 'per_card': per_card},
          open(os.path.join(ROOT, 'ledger', '_r2_ladder_raw.json'), 'w'), indent=1)
print('rows', len(rows), 'cards', len(per_card))
