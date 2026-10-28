"""SME-F1FIX: extract.reader_hidden with the raw-address key (v29) vs the generation key (SME_HIDDEN_GEN=1) on every match
of the given inputs files, plus every hero Mini PEKKA ability cast: is its body unlisted while projectiles target it, and
does each rule cover that window. python -I hidden_census.py INPUTS.jsonl ..."""
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'extract'))
import extract  # noqa: E402

cat, _ = extract.load_catalog()
MP = next(k for k, c in cat.items() if k == c.get('hero_form_id') and c.get('hero_character') == 'MiniPekkaHero')


def raw_windows(path):
    """Per hero Mini PEKKA generation (address + first listed tick): listed ticks, and projectile ticks at its address
    while it is unlisted before the address is listed again."""
    ents_at, proj_at = {}, {}
    seen = set()
    for line in open(path, 'rb'):
        if b'"frame"' not in line[:40]:
            continue
        d = json.loads(line); t = d['tick']
        if t is None or t < 0 or t in seen:
            continue
        seen.add(t)
        ents_at[t] = {e[7]: e for e in d['ents']}
        proj_at[t] = {p[9] for p in d['proj'] if len(p) > 9 and p[9]}
    ts = sorted(ents_at)
    out = []
    for i, t in enumerate(ts):
        for a, e in ents_at[t].items():
            if e[3] != MP or (i and a in ents_at[ts[i - 1]] and ents_at[ts[i - 1]][a][3] == MP):
                continue
            j = i
            while j + 1 < len(ts) and a in ents_at[ts[j + 1]] and ents_at[ts[j + 1]][a][3] == MP:
                j += 1
            hid = []
            for u in ts[j + 1:]:
                if a in ents_at[u]:
                    break
                if a in proj_at[u]:
                    hid.append(u)
            out.append(dict(side=e[0], first=t, last=ts[j], hidden=(hid[0], hid[-1], len(hid)) if hid else None))
    return out


tot = dict(casts=0, old=0, new=0)
for f in sys.argv[1:]:
    for l in open(f):
        r = json.loads(l)
        p = extract.LIVE / (r['match'] + '.jsonl')
        os.environ['SME_HIDDEN_GEN'] = '0'; old = extract.reader_hidden(p, cat)
        os.environ['SME_HIDDEN_GEN'] = '1'; new = extract.reader_hidden(p, cat)
        casts = [q for q in r['plays'] if q['card'] == 'MiniPekka' and q['kind'] == 'ability']
        if not (old or new or casts):
            continue
        print('==', r['match'], 'v29 key == gen key' if old == new else 'DIFFERENT')
        for lab, hs in (('v29', old), ('gen', new)):
            for h in hs:
                tr = sorted(map(int, h['track']))
                print('  %s side %d %-16s last %5d end %5d track %d pts %s..%s' % (lab, h['side'], h['name'], h['last'], h['end'],
                      len(tr), tr[:1], tr[-1:]))
        wins = raw_windows(p)
        for q in casts:
            tot['casts'] += 1
            w = [x for x in wins if x['side'] == q['side'] and x['first'] <= q['tick'] <= x['last'] + 2]
            hid = w[0]['hidden'] if w else None
            cov = {lab: bool(hid) and any(h['name'] == 'MiniPekkaHero' and h['side'] == q['side'] and h['last'] < hid[0] <= h['end']
                                          for h in hs) for lab, hs in (('v29', old), ('gen', new))}
            tot['old'] += cov['v29'] and bool(hid); tot['new'] += cov['gen'] and bool(hid)
            print('  cast side %d tick %5d body listed %s unlisted-but-targeted %s covered v29 %s gen %s' % (
                q['side'], q['tick'], (w[0]['first'], w[0]['last']) if w else None, hid, cov['v29'], cov['gen']))
print('hero Mini PEKKA casts', tot['casts'], '| hidden windows covered: v29', tot['old'], 'gen', tot['new'])
