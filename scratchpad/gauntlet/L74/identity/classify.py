"""census.json -> which opponent bodies reach the model as something they are not.

A body is the card's OWN body when its max_hp is the form record's catalog HP at some level (+-2: client rounding);
otherwise it is a different body carried under the card's id (spawn / ability unit / sub-unit). Groups by
(card_id, name, form, model class, reason); prints bodies, decision states, matches, W/L and HP values.
Usage: python classify.py [census.json]  -> classify.out (stdout) + classify.json
"""
import collections, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '../../../..')))
from pipeline import body_identity as BI, vocab

cat, _ = BI._catalog()
REC = {r['name']: r for f in ('cards', 'evolutions', 'hero_forms') for r in cat[f]}
SUFFIX = {0: '', 1: '_EV1', 2: '_hero'}
_PH = {}


def parent_hps(name, form):
    k = (name, form)
    if k not in _PH:
        rec = REC.get(name + SUFFIX[form]) or (REC.get(name) if form == 0 else None)
        rn = rec['name'] if rec else None
        _PH[k] = None if rec is None or rec.get('hitpoints') is None else \
            {h * m // 100 for _, m in BI._levels(rec) for h in BI._hitpoints(rn, rec)}
    return _PH[k]


def own_body(name, form, mhp):
    hs = parent_hps(name, form)
    if hs is None:
        return None
    return any(abs(mhp - h) <= 2 for h in hs)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'census.json')
    d = json.load(open(src))
    g = collections.OrderedDict()
    for r in d['rows']:
        if r['name'] == '-1':
            own = False
        elif r['reason'] in ('parent',):
            own = True
        elif r['reason'] in ('child', 'child_no_class', 'explicit_child', 'unnamed'):
            own = False
        else:
            own = own_body(r['name'], r['form'], r['max_hp']) if r['max_hp'] > 0 else None
        k = (r['card_id'], r['name'], r['form'], r['cls'], r['reason'], own)
        a = g.setdefault(k, dict(bodies=0, states=0, fstates=0, files=set(), hp=collections.Counter(), res=collections.Counter()))
        a['bodies'] += r['bodies']; a['states'] += r['states']; a['fstates'] += r['fstates']
        a['hp'][r['max_hp']] += r['bodies']
        a['files'].update(r['files'])
    out = []
    for k, a in g.items():
        out.append(dict(card_id=k[0], name=k[1], form=k[2], cls=k[3], reason=k[4], own_body=k[5], bodies=a['bodies'],
                        states=a['states'], fstates=a['fstates'], matches=len(a['files']), files=sorted(a['files']),
                        hp=dict(sorted(a['hp'].items()))))
    json.dump(out, open(os.path.join(HERE, 'classify.json'), 'w'), indent=0)
    for title, f in (('DROPPED (model never sees the body)', lambda r: r['cls'] is None),
                     ('NOT the card\'s own body but given the card\'s own class (legacy / unknown_hp / ambiguous)',
                      lambda r: r['cls'] is not None and r['own_body'] is False and r['reason'] not in
                      ('child', 'explicit_child', 'unnamed')),
                     ('own body unknown (no catalog record or unreadable HP)', lambda r: r['cls'] is not None and r['own_body'] is None),
                     ('child_no_class (spawned body, no class of its own, keeps the parent class form 0)',
                      lambda r: r['reason'] == 'child_no_class')):
        print('\n===', title)
        for r in sorted((r for r in out if f(r)), key=lambda r: -r['bodies']):
            if title.startswith('NOT') and r['reason'] == 'child_no_class':
                continue
            print(f"  {r['card_id']:>10} {r['name']:<18} f{r['form']} -> {str(r['cls']):<18} {r['reason']:<14} bodies {r['bodies']:5d} "
                  f"states {r['states']:6d} fstates {r['fstates']:5d} matches {r['matches']:4d} hp {r['hp']}")


if __name__ == '__main__':
    main()
