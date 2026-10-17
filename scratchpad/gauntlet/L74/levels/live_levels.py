"""Live card / tower levels (L74 factor D, 10-17): the table rl_royale ``live_levels`` and search_s0 ``--live-levels`` draw from.

Source: the parity harness's per-match summaries (scratchpad/gauntlet/L74/parity/fights.py run_match: every body's max_hp
matched exactly to one (card, level) by the SIM's own unit_hitpoints; own spells by their exact damage drops; each side's
tower level from its king + princess max_hp, a tower troop at its own level). Kept: ranked main-account matches = the
harness kept the match (frames, main account) AND our tower is level 15 (the 5 level-11 matches are dry runs). Newest
harness run wins when a match is in several. '*' (a side's modal level for cards never seen) is not a measurement: dropped.

    python live_levels.py OUT.json SUMMARY_DIR [SUMMARY_DIR ...]     (each dir holds matches/live_play_*.json; newest last)
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

OWN_TOWER = 15


def main(out, dirs):
    summ = {}
    for d in dirs:                                    # later dirs overwrite: pass the newest harness run last
        for f in sorted(Path(d, 'matches').glob('live_play_*.json')):
            s = json.loads(f.read_text(encoding='utf-8'))['summary']
            summ[s['match']] = s
    kept, skipped = [], Counter()
    for name in sorted(summ):
        s = summ[name]
        if 'skipped' in s:
            skipped[s['skipped']] += 1
        elif s['tower_levels'][s['side']] != OWN_TOWER:
            skipped['own_tower_not_15'] += 1
        else:
            kept.append(s)
    own, profiles, own_tower = defaultdict(Counter), [], Counter()
    for s in kept:
        me = s['side']
        own_tower[s['tower_levels'][me]] += 1
        cards = []
        for k, v in sorted(s['levels'].items()):
            side, card = k.split(':', 1)
            if card == '*':
                continue
            if int(side) == me:
                own[card][v] += 1
            else:
                cards.append(int(v))
        profiles.append([s['match'], int(s['tower_levels'][1 - me]), cards])
    modal = Counter(v for c in own.values() for v in c.elements()).most_common(1)[0][0]
    table = {'schema': 1, 'source': [str(d) for d in dirs], 'n_matches': len(kept), 'skipped': dict(skipped),
             'first': kept[0]['match'], 'last': kept[-1]['match'],
             'own': {'tower': OWN_TOWER, 'cards': {c: n.most_common(1)[0][0] for c, n in sorted(own.items())},
                     'default': modal, 'counts': {c: dict(sorted(n.items())) for c, n in sorted(own.items())}},
             'opp_profiles': profiles}
    Path(out).write_text(json.dumps(table, indent=1) + '\n', encoding='utf-8')
    n = len(kept)
    tw = Counter(p[1] for p in profiles)
    cl = Counter(v for p in profiles for v in p[2])
    dl = Counter(v - p[1] for p in profiles for v in p[2])
    print(f'kept {n} ranked main-account matches ({table["first"]} .. {table["last"]}); skipped {dict(skipped)}')
    print(f'own tower {dict(own_tower)}; own cards (modal): {table["own"]["cards"]}; default {modal}')
    print('opp tower level:', ', '.join(f'{k}: {v} ({100 * v / n:.1f}%)' for k, v in sorted(tw.items())))
    m = sum(cl.values())
    print(f'opp card level ({m} card-level readings):', ', '.join(f'{k}: {v} ({100 * v / m:.1f}%)' for k, v in sorted(cl.items())))
    print('opp card - opp tower level:', ', '.join(f'{k:+d}: {v} ({100 * v / m:.1f}%)' for k, v in sorted(dl.items())))
    print('cards read per opponent: median', sorted(len(p[2]) for p in profiles)[n // 2],
          '; with none:', sum(not p[2] for p in profiles))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
