"""Parity COVERAGE (owner 10-17): the share of LIVE fights whose card meets the parity goal, weighted by how often each card
is played in our live ladder matches (census_cards.py), plus the "commonly faced" card set that gates step d.

A card counts as meeting only with its ceiling_table flag MEETS (raw lower 95% CI >= GOAL_CARD with n >= GOAL_N); a card the
parity cohort has too few fights of counts as not meeting (unproven), never as meeting.

  python coverage.py CEILING_JSON CENSUS_JSON [--common SHARE]   (SHARE: the live play share a card needs to be "commonly
  faced", default 0.005 = 0.5% of all plays)
"""
from __future__ import annotations

import json
import sys


def table(ceiling, census, common):
    rows = {r['card']: r for r in ceiling['cards']}
    total = sum(census['plays'].values())
    out = []
    for card, plays in sorted(census['plays'].items(), key=lambda kv: -kv[1]):
        r = rows.get(card) or {}
        out.append(dict(card=card, share=plays/total, in_matches=census['matches_with'].get(card, 0)/census['matches'],
                        n=r.get('n', 0), raw=r.get('agree'), raw_ci=r.get('agree_ci'), flag=r.get('flag', 'not in cohort'),
                        common=plays/total >= common))
    return out, total


def summary(out, total, census):
    cov = lambda rs: sum(r['share'] for r in rs if r['flag'] == 'MEETS')
    com = [r for r in out if r['common']]
    lines = [f"live census: {census['matches']} matches, {total} plays, {len(out)} cards",
             f"COVERAGE (all live plays whose card MEETS): {cov(out):.3f}",
             f"commonly faced: {len(com)} cards = {sum(r['share'] for r in com):.3f} of plays; of those MEET {sum(r['flag'] == 'MEETS' for r in com)}"
             f" cards, {cov(com) / max(1e-9, sum(r['share'] for r in com)):.3f} of their plays",
             '', 'card | live play share | in % of matches | parity n | raw [95% CI] | flag | common']
    lines += [f"{r['card']} | {r['share']:.4f} | {r['in_matches']:.3f} | {r['n']} | {r['raw']} {r['raw_ci']} | {r['flag']} | "
              f"{'yes' if r['common'] else ''}" for r in out]
    return lines


def main(argv):
    common = float(argv[argv.index('--common')+1]) if '--common' in argv else .005
    ceiling, census = (json.load(open(p, encoding='utf-8')) for p in argv[:2])
    out, total = table(ceiling, census, common)
    print('\n'.join(summary(out, total, census)))


if __name__ == '__main__':
    if sys.argv[1:2] == ['--selftest']:
        ce = dict(cards=[dict(card='opp A', n=40, agree=.99, agree_ci=(.96, 1), flag='MEETS'),
                         dict(card='opp B', n=40, agree=.80, agree_ci=(.7, .9), flag='below (floor met)')])
        cs = dict(matches=10, plays={'opp A': 6, 'opp B': 3, 'opp C': 1}, matches_with={'opp A': 10, 'opp B': 5, 'opp C': 1})
        o, t = table(ce, cs, .2)
        assert t == 10 and [r['card'] for r in o] == ['opp A', 'opp B', 'opp C']
        assert abs(sum(r['share'] for r in o if r['flag'] == 'MEETS') - .6) < 1e-9          # coverage = A's 6 of 10 plays
        assert o[2]['flag'] == 'not in cohort' and not o[2]['common'] and o[1]['common']   # unproven card never counts
        print('COVERAGE_SELFTEST_OK')
    else:
        main(sys.argv[1:])
