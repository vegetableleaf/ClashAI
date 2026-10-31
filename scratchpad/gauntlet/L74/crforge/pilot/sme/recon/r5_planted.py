"""RECON-5 planted recall of the deck-constrained cycle repair (laptop, no engine):
  python -I recon/r5_planted.py INPUTS.jsonl [INPUTS2.jsonl ...] --out PLANTED.json [--records N]
For every record whose opponent play sequence FITS a deal (the cycle rule is trusted there), delete each SPELL play in turn (one
plant per play; the deck is the battle-log deck) and ask cyc.repairs for the optimal repairs with spell insertions only:
  invisible  the plant still fits a deal (the cycle cannot see the missing play)
  restored   an optimal repair inserts exactly the deleted card at the deleted position (a gap-equivalent insert counts: the same
             card inserted before an adjacent observed play of another card is a different history, so it is NOT counted)
  unique     restored and the only optimal repair
  missed     detected but the truth is not among the optimal repairs (cost > 1 or a different insert)
and the number of optimal repairs (the engine's candidate list) per detected plant. A wrong deck must be rejected:
deck_conflicts() on the real battle-log deck must be 0 for every record, and a deck with one played card swapped out must be flagged."""
import argparse, json, os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recon  # noqa: E402
import cyc  # noqa: E402


def opp_seq(r):
    opp = 1 - r['my_side']
    pl = sorted((p for p in r['plays'] if p['side'] == opp and p['kind'] == 'play'), key=lambda p: p['tick'])
    return opp, pl


def deck_conflicts(deck, plays):
    """Observed plays whose card is not one of the side's 8 deck cards (a wrong deck, or a mislabelled play)."""
    return [p for p in plays if p['card'] not in deck]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('inputs', nargs='+'); ap.add_argument('--out', required=True); ap.add_argument('--records', type=int, default=0)
    a = ap.parse_args()
    tab = recon.Tab()
    recs = [json.loads(l) for f in a.inputs for l in open(f)]
    if a.records:
        recs = recs[:a.records]
    rows, conf, swapped = [], 0, [0, 0]
    for r in recs:
        opp, pl = opp_seq(r)
        deck = r['sides'][str(opp)]['deck']
        conf += bool(deck_conflicts(deck, pl))
        played = [p['card'] for p in pl if p['card'] in deck]
        if played:   # planted wrong deck: swap one PLAYED card for a card that is not in the deck -> must be flagged
            bad = list(deck); bad[deck.index(played[0])] = 'Zzz'
            swapped[0] += 1; swapped[1] += bool(deck_conflicts(bad, pl))
        seq = [p['deck_index'] for p in pl]
        if not cyc.fits(seq):
            continue
        spells = [i for i, c in enumerate(deck) if c and tab.is_spell(c)]
        for j, p in enumerate(pl):
            if p['deck_index'] not in spells:
                continue
            cut = seq[:j] + seq[j + 1:]
            if cyc.fits(cut):
                rows.append(dict(match=r['match'], j=j, card=p['card'], v='invisible')); continue
            cost, reps = cyc.repairs(cut, ins_cards=spells, cap=3000, max_cost=2)
            truth = [(j, p['deck_index'])]
            hit = [x for x in reps if x[0] == truth and not x[1]]
            rows.append(dict(match=r['match'], j=j, card=p['card'], v='unique' if hit and len(reps) == 1 else 'restored' if hit else 'missed',
                             cost=cost, n=len(reps)))
    json.dump(rows, open(a.out, 'w'))
    c = collections.Counter(x['v'] for x in rows)
    det = [x for x in rows if x['v'] != 'invisible']
    print('records', len(recs), 'plants', len(rows), dict(c))
    print('detected %d: restored (incl. unique) %d = %.3f; unique %d; missed %d' % (
        len(det), c['restored'] + c['unique'], (c['restored'] + c['unique']) / max(len(det), 1), c['unique'], c['missed']))
    ns = sorted(x['n'] for x in det if x['v'] in ('restored', 'unique'))
    if ns:
        print('optimal repairs per restored plant: median %d, p90 %d, max %d' % (ns[len(ns) // 2], ns[int(len(ns) * .9)], ns[-1]))
    print('real deck conflicts (must be 0): %d of %d records; planted wrong deck flagged: %d of %d' % (conf, len(recs), swapped[1], swapped[0]))


if __name__ == '__main__':
    main()
