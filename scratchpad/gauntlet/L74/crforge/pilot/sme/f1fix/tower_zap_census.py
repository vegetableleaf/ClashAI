"""ENG-SME: SME_TOWER_ZAP's decision on every low-hp princess-tower removal of extracted inputs (made with the flag OFF):
mech_rules.tower_zaps on the raw live log + the record's plays / sides / reader_hidden, the same call the extractor makes
(plays only reordered there). Prints each candidate fired or blocked with its reason. A no_zap_in_deck candidate is
re-judged with a Zap added to that deck ('as if Zap'): how often a low-hp tower leaves with nothing visible WITHOUT a
Zap in the deck (the rule's premise: 'nothing visible' points to an unseen Zap).
    python -I tower_zap_census.py INPUTS.jsonl ..."""
import collections, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'extract'))
import extract  # noqa: E402
import mech_rules as M  # noqa: E402

why = collections.Counter()
for f in sys.argv[1:]:
    for line in open(f):
        r = json.loads(line)
        sides = {int(k): v for k, v in r['sides'].items()}
        _, fired, blocked = M.tower_zaps(M.raw_frames(extract.LIVE / (r['match'] + '.jsonl')), r['plays'], sides,
                                         r.get('reader_hidden') or [])
        for z in fired:
            why['FIRED'] += 1
            print(r['match'][10:], 'FIRED', z)
        for z in blocked:
            why[z['why']] += 1
            alt = ''
            if z['why'] == 'no_zap_in_deck':
                o = 1 - z['tower'][0]
                s2 = {**sides, o: dict(sides[o], deck=sides[o]['deck'] + ['Zap'], levels=sides[o]['levels'] + [16])}
                f2, b2 = M.tower_zaps(M.raw_frames(extract.LIVE / (r['match'] + '.jsonl')), r['plays'], s2,
                                      r.get('reader_hidden') or [])[1:]
                w = [b['why'] for b in b2 if b['t'] == z['t']] or ['WOULD_FIRE' for x in f2 if x['t'] == z['t']]
                alt = 'as if Zap: ' + w[0]
                why['no_zap/' + w[0]] += 1
            print(r['match'][10:], 'blocked', z['why'], {k: z[k] for k in ('tower', 'hp', 'tp', 't')}, z['plays'], alt)
print('candidates (0 < hp <= Zap crown damage, princess tower gone):', dict(why))
