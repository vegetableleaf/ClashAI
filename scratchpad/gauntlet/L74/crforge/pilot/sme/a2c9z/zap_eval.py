"""A2c-9Z: precision / recall of mech_rules.zap_is_cast over every ZapFreeze buff group of an inputs file's matches.
  negative set: groups whose source deck has no Zap (the battle-log deck), classified as if it held a level-16 Zap;
  positive A:   groups of Zap decks with no Electro card (nothing else in the deck puts ZapFreeze at Zap damage);
  positive B:   groups matched (+-3 ticks of c - 1) to an extracted Zap play (H-ZAP inferences).
  candidates:   groups the rule adds (Zap deck, no Zap play near), with the opponent deal-fit count before / after.
Reads phase-2 unit buffs/names and ents only. python -I zap_eval.py INPUTS.jsonl LOGDIR"""
import collections, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'extract'))
import extract, mech_rules as M  # noqa: E402

inp, logdir = sys.argv[1:3]
c = collections.Counter()
for line in open(inp):
    r = json.loads(line)
    for g in M.zap_groups(os.path.join(logdir, r['match'] + '.jsonl')):
        s = g['s']
        sd = r['sides'].get(str(s))
        if sd is None or not g['hits']:
            c['no_side_or_hits'] += 1
            continue
        deck = sd['deck']
        has = 'Zap' in deck
        lv = sd['levels'][deck.index('Zap')] if has else 16
        z = M.zap_is_cast(g, lv)
        el = any('Electro' in d for d in deck)
        near = [p for p in r['plays'] if p['side'] == s and p['kind'] == 'play' and p['card'] == 'Zap' and abs(p['tick'] - (g['c'] - 1)) <= 3]
        if not has:
            c['neg n'] += 1; c['neg flagged'] += z
            if z:
                print('NEG_FLAGGED', r['match'], g['c'], deck)
            continue
        if not el:
            c['posA n'] += 1; c['posA flagged'] += z
        if near:
            c['posB n'] += 1; c['posB flagged'] += z
            if not z:
                print('POSB_MISSED', r['match'], g['c'], [(h['name'], h['drop']) for h in g['hits'].values()])
        elif z:
            seq = sorted((p for p in r['plays'] if p['side'] == s and p['kind'] == 'play'), key=lambda p: p['tick'])
            base = [p['deck_index'] for p in seq]
            new = [p['deck_index'] for p in seq if p['tick'] < g['c'] - 1] + [deck.index('Zap')] + \
                [p['deck_index'] for p in seq if p['tick'] >= g['c'] - 1]
            n0, n1 = extract.deals_fitting(base)[0], extract.deals_fitting(new)[0]
            c['cand'] += 1; c['cand flagged-match'] += bool(r['flags'])
            c['cand fit 0->n'] += n0 == 0 < n1; c['cand fit n->0'] += n1 == 0 < n0
            print('CAND', r['match'], 'flagged' if r['flags'] else 'clean', 'c', g['c'], 'deal fits', n0, '->', n1,
                  [(h['name'], h['drop']) for h in g['hits'].values()])
print(dict(c))
