"""Aggregate sme_live.py results: per-match table, D1 SME-pilot row, first-divergence census, over-fit and deal checks.
    python3 agg_live.py RUNDIR [--inputs INPUTS.jsonl]   -> RUNDIR/summary.json, RUNDIR/table.tsv (stdout: the summary)
"""
import collections, json, os, sys


def first_kind(detail):
    """(quantity, card, magnitude) of the first divergence: presence > hp > position > elixir/hand."""
    if not detail:
        return ('none', None, None)
    best = None
    for kind, x, name, near in detail:
        if kind.startswith('S'):
            q, mag = ('elixir' if 'elixir' in kind else 'hand'), [x, near]
            rank = 4
        elif near is None or abs(near[0]) + abs(near[1]) > 1500:
            q, mag, rank = 'presence_' + ('rec_only' if 'rec_only' in kind else 'sim_only'), None, 1
        elif len(near) > 2 and near[2] != 0:
            q, mag, rank = 'hp', near, 2
        else:
            q, mag, rank = 'position', near, 3
        if best is None or rank < best[0]:
            best = (rank, q, name, mag, kind[0])
    return (best[4] + ':' + best[1], best[2], best[3])


def mech(detail, refused):
    """Coarse mechanism of an episode onset (rules from the inspected onsets; SME.md says which are measured)."""
    if refused:
        return 'input: a play the match refused (not in hand / elixir / point)'
    d = detail or []
    names = {str(x[2]).split(':')[-1] for x in d if x[2]}
    if d and all(x[0].startswith('S') and 'elixir' in x[0] for x in d) and all((x[3] - x[1]) % 10000 == 0 for x in d):
        return 'live client: own elixir down a card cost 1 frame before the sim'
    if names & {'Lightning', 'LighningSpell'}:
        return 'Lightning strike timing'
    if any('Earthquake' in n for n in names):
        return 'Earthquake pulse timing'
    if names & {'Poison', 'Freeze', 'Rage', 'Tornado', 'Zap', 'Snowball', 'GiantSnowball'}:
        return 'spell area effect timing'
    body = [x for x in d if x[0][0] in 'TU']
    if body and all(isinstance(x[3], list) and len(x[3]) > 2 and x[3][0] == 0 and x[3][1] == 0 for x in body):
        sim_more = all((x[3][2] < 0) == ('rec_only' in x[0]) for x in body)  # near = sim - rec for rec_only
        return 'hp only: sim %s damage at the same points' % ('more' if sim_more else 'less/mixed')
    if any(x[0].endswith('rec_only') and x[0][0] in 'TU' and (x[3] is None or abs(x[3][0]) + abs(x[3][1]) > 1500) for x in d):
        return 'body in the reader, none near in the sim (play missed / late / unit not made)'
    if any(x[0].endswith('sim_only') and x[0][0] in 'TU' and (x[3] is None or abs(x[3][0]) + abs(x[3][1]) > 1500) for x in d):
        return 'body in the sim, none near in the reader'
    if body:
        return 'body position (movement / collision / targeting)'
    if any(x[0][0] == 'P' for x in d):
        return 'projectile only (launch timing / flight)'
    if any(x[0][0] == 'A' for x in d):
        return 'area effect only (start / end timing)'
    return 'other: ' + ','.join(sorted({x[0] for x in d}))


def main():
    run = sys.argv[1]
    flags = {}
    if '--inputs' in sys.argv:
        for l in open(sys.argv[sys.argv.index('--inputs') + 1]):
            r = json.loads(l)
            flags[r['match']] = r['flags']
    rs = {}
    for l in open(os.path.join(run, 'results.jsonl')):
        r = json.loads(l)
        rs[r['match']] = r
    rows, census, cards = [], collections.Counter(), collections.Counter()
    ep_census, ep_census_heal = collections.Counter(), collections.Counter()
    mech_all, mech_heal, mech_first = collections.Counter(), collections.Counter(), collections.Counter()
    mech_matches = collections.defaultdict(set)
    d1 = {'all': [0, 0], 'unflagged': [0, 0]}
    offs, probe_hits, deal = collections.Counter(), [], collections.Counter()
    torn1 = tornm = frames = exact = 0
    for m, r in sorted(rs.items()):
        if 'error' in r:
            rows.append([m, 'ERROR', r['error'][:120]])
            census[('error', r['error'][:60])] += 1
            for k in ('all',) + (('unflagged',) if not flags.get(m, r.get('flags')) else ()):
                d1[k][1] += 1
            continue
        c = r['counts']
        ok = c.get('div', 0) == 0 and r['missing_in_sim'] == 0
        unfl = not flags.get(m, r['flags'])
        for e in r.get('episodes', []):
            q2, card2, _ = first_kind(e['detail'])
            # an onset right after a play the match refused (card not in hand / too little elixir / bad point)
            refused = any(e['start'] - 30 <= p[1] <= e['start'] for p in r['refused_plays'])
            if refused:
                q2 = 'refused_play>' + q2
            if e['detail'] is not None:
                mk = mech(e['detail'], refused)
                mech_all[mk] += 1
                mech_heal[mk] += e['healed']
                mech_matches[mk].add(m)
                if e is r['episodes'][0]:
                    mech_first[mk] += 1
            ep_census[(q2, card2)] += 1
            ep_census_heal[(q2, card2, e['healed'])] += 1
        for k in ('all',) + (('unflagged',) if unfl else ()):
            d1[k][0] += ok
            d1[k][1] += 1
        q, card, mag = first_kind(r['first_detail'])
        if not ok:
            census[(q, card)] += 1
            cards[card] += 1
        torn1 += c.get('torn_t1', 0); tornm += c.get('torn_mixed', 0); frames += r['frames']; exact += c.get('exact', 0)
        for card_, o in r['nonzero_offset']:
            offs[o] += 1
        probe_hits += [dict(h, match=m) for h in r.get('overfit', [])]
        for x in (r.get('deal_check') or {}).get('identical', []):
            deal[x] += 1
        rows.append([m, ','.join(r['flags']) or '-', r['frames'], '%.4f' % r['exact_share'], c.get('torn_t1', 0),
                     c.get('torn_mixed', 0), c.get('div', 0), r['missing_in_sim'], r['first_div'], q, card,
                     json.dumps(mag), len(r['repair']), len(r['nonzero_offset']), len(r['refused_plays'])])
    cmds = sum(r.get('commands', 0) for r in rs.values())
    summ = {'matches': len(rs), 'd1_sme_pilot': {k: '%d/%d' % tuple(v) for k, v in d1.items()},
            'frames': frames, 'exact_frames': exact, 'torn_t1_frames': torn1, 'torn_mixed_frames': tornm,
            'first_div_census': [[list(k), v] for k, v in census.most_common()],
            'first_div_cards': cards.most_common(), 'commands': cmds,
            'episode_census': [[list(k), v, ep_census_heal[k + (True,)]] for k, v in ep_census.most_common()],
            'episodes': sum(ep_census.values()),
            'mechanisms': [{'mechanism': k, 'onsets_described': v, 'healed': mech_heal[k], 'first_true_div': mech_first[k],
                            'matches': len(mech_matches[k])} for k, v in mech_all.most_common()],
            'nonzero_offset_commands': sum(offs.values()), 'offset_hist': dict(sorted(offs.items())),
            'overfit_probe_hits': probe_hits, 'deal_check': dict(deal),
            'errors': [m for m, r in rs.items() if 'error' in r]}
    json.dump(summ, open(os.path.join(run, 'summary.json'), 'w'), indent=1, default=str)
    with open(os.path.join(run, 'table.tsv'), 'w') as w:
        w.write('\t'.join(['match', 'flags', 'frames', 'exact_share', 'torn_t1', 'torn_mixed', 'div', 'missing_in_sim',
                           'first_div', 'quantity', 'card', 'magnitude', 'repair_rounds', 'nonzero_offsets',
                           'refused_plays']) + '\n')
        for row in rows:
            w.write('\t'.join(map(str, row)) + '\n')
    print(json.dumps(summ, indent=1, default=str)[:6000])


if __name__ == '__main__':
    main()
