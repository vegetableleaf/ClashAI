"""Parity COVERAGE + the step-d trigger (owner 10-17).

Coverage = the share of LIVE plays (census_cards.py over our ladder matches) whose card meets the per-card goal (ceiling_table
flag MEETS: raw lower 95% CI >= GOAL_CARD with n >= GOAL_N). A card with too few parity fights counts as NOT meeting (unproven).
Tiers = our whole deck + the opponent cards with at least that share of all live plays:
  B (step d starts): opp >= 0.3% of plays;  C (the ultimate goal, keep tracking): opp >= 0.2%.
STEP-D TRIGGER (owner): overall raw lower CI >= GOAL_ALL (0.975) AND cards carrying >= 90% of tier B's live plays meet.

  python coverage.py CEILING_JSON CENSUS_JSON        (python coverage.py --selftest)
"""
from __future__ import annotations

import json
import sys

TIERS = {'B': .003, 'C': .002}
TIER_SHARE = .90          # share of a tier's live plays whose card must meet (owner accepted with option B)
GOAL_ALL = .975
# Owner 10-17: grade on UPGRADED matches only (fights.py score --stamped: phase-3b creation ticks), "just make sure there is
# enough matches": the trigger needs the stamped cohort with at least MIN_MATCHES scored matches (a bootstrap over a handful of
# matches is not trustworthy, whatever its CI says). ponytail: a fixed floor; raise it if the CIs at 100 look unstable.
MIN_MATCHES = 100


def table(ceiling, census):
    rows = {r['card']: r for r in ceiling['cards']}
    total = sum(census['plays'].values())
    out = []
    for card, plays in sorted(census['plays'].items(), key=lambda kv: -kv[1]):
        r = rows.get(card) or {}
        out.append(dict(card=card, share=plays/total, in_matches=census['matches_with'].get(card, 0)/census['matches'],
                        n=r.get('n', 0), raw=r.get('agree'), raw_ci=r.get('agree_ci'), flag=r.get('flag', 'not in cohort')))
    return out, total


def tier(out, thr):
    """-> (cards in the tier, their share of all plays, the share of the tier's plays whose card MEETS)."""
    t = [r for r in out if r['card'].startswith('own ') or r['share'] >= thr]
    s = sum(r['share'] for r in t)
    return t, s, (sum(r['share'] for r in t if r['flag'] == 'MEETS')/s if s else 0.)


def report(ceiling, census):
    out, total = table(ceiling, census)
    ov = ceiling.get('overall') or {}
    lo = (ov.get('agree_ci') or (None, None))[0]
    cohort, nm = ceiling.get('cohort', 'all'), ov.get('matches') or 0
    valid = cohort == 'stamped' and nm >= MIN_MATCHES
    lines = [f"live census: {census['matches']} matches, {total} plays, {len(out)} cards",
             f"graded cohort: {cohort}, {nm} matches -> " + ('valid for the trigger' if valid else
             f"NOT valid for the trigger (needs the stamped cohort with >= {MIN_MATCHES} matches)"),
             f"overall raw {ov.get('agree')} lower CI {lo} (goal {GOAL_ALL}): {'MET' if lo is not None and lo >= GOAL_ALL else 'not met'}",
             f"COVERAGE (all live plays on a card that MEETS): {sum(r['share'] for r in out if r['flag'] == 'MEETS'):.3f}"]
    for name, thr in TIERS.items():
        t, s, met = tier(out, thr)
        ok = valid and lo is not None and lo >= GOAL_ALL and met >= TIER_SHARE
        lines.append(f"tier {name} (own deck + opp >= {thr:.1%} of plays): {len(t)} cards = {s:.3f} of live plays; "
                     f"{met:.3f} of its plays meet (need {TIER_SHARE}) -> {'TRIGGER MET' if ok else 'not yet'}"
                     + (' [STEP D]' if name == 'B' else ' [ultimate goal]'))
    t, _, _ = tier(out, min(TIERS.values()))
    lines += ['', 'work queue (tier C cards not meeting, by live play share):',
              'card | live play share | in % of matches | parity n | raw [95% CI] | flag | tier']
    lines += [f"{r['card']} | {r['share']:.4f} | {r['in_matches']:.3f} | {r['n']} | {r['raw']} {r['raw_ci']} | {r['flag']} | "
              f"{'B' if r['card'].startswith('own ') or r['share'] >= TIERS['B'] else 'C'}" for r in t if r['flag'] != 'MEETS']
    return lines


if __name__ == '__main__':
    if sys.argv[1:2] == ['--selftest']:
        ce = dict(cohort='stamped', overall=dict(agree=.98, agree_ci=(.976, .984), matches=150),
                  cards=[dict(card='own A', n=400, agree=.99, agree_ci=(.97, 1), flag='MEETS'),
                         dict(card='opp B', n=40, agree=.99, agree_ci=(.96, 1), flag='MEETS'),
                         dict(card='opp C', n=40, agree=.80, agree_ci=(.7, .9), flag='below (floor met)')])
        cs = dict(matches=10, plays={'own A': 900, 'opp B': 40, 'opp C': 25, 'opp D': 35}, matches_with={'own A': 10, 'opp B': 5, 'opp C': 3, 'opp D': 2})
        out, total = table(ce, cs)
        tb, sb, mb = tier(out, TIERS['B'])            # B: own A + opp B (4%) + opp C (2.5%) + opp D (3.5%), all >= 0.3%
        assert total == 1000 and len(tb) == 4 and abs(mb - .94) < 1e-9   # meets: own A 0.90 + opp B 0.04 of 1.0
        assert [r['flag'] for r in out if r['card'] == 'opp D'] == ['not in cohort']       # an unproven card never counts
        assert any('TRIGGER MET' in x and '[STEP D]' in x for x in report(ce, cs))
        ce['overall']['matches'] = 60                                                      # too few stamped matches blocks it
        assert not any('TRIGGER MET' in x for x in report(ce, cs))
        ce['overall']['matches'], ce['cohort'] = 150, 'all'                                # the full cohort never triggers
        assert not any('TRIGGER MET' in x for x in report(ce, cs))
        ce['cohort'] = 'stamped'
        ce['overall']['agree_ci'] = (.970, .984)                                           # overall below 0.975 blocks it
        assert not any('TRIGGER MET' in x for x in report(ce, cs))
        print('COVERAGE_SELFTEST_OK')
    else:
        ceiling, census = (json.load(open(p, encoding='utf-8')) for p in sys.argv[1:3])
        print('\n'.join(report(ceiling, census)))
