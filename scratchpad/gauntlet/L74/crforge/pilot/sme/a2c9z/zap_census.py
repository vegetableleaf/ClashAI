"""A2c-9Z census: every ZapFreeze buff group (made tick c, source side s) in the raw live logs of an inputs file, with
the public evidence that tells a Zap cast from an Electro unit: the caster's deck (battle log), the hit bodies (buff
holders) with their hp drop and position, the caster side's electro bodies alive around c and their distance to the
hits, and the extracted Zap play of s near c (if any). Reads phase-2 unit buffs/names and ents only (never the
opponent elixir estimate). python3 zap_census.py INPUTS.jsonl LOGDIR OUT.jsonl"""
import collections, json, math, os, sys

ELECTRO = ('Electro', 'Zapp', 'ZapMachine', 'Sparky')   # electro body names (ZapMachine = Sparky; checked, not assumed)


def frames(path):
    for line in open(path, 'rb'):
        if b'"frame"' in line[:30]:
            yield json.loads(line)


def groups(path):
    """{(c, s): dict(hits=[...], electro=[...])} for one raw log."""
    last, G, hist = {}, collections.defaultdict(lambda: dict(hits={}, electro=set())), []
    pend = []
    for d in frames(path):
        t = d['tick']
        ents = {e[7]: e for e in d.get('ents', [])}
        units = (d.get('phase2') or {}).get('units', [])
        hist.append((t, ents, units))
        for u in units:
            for b in u['buffs']:
                if b['name'] != 'ZapFreeze':
                    continue
                k = (u['generation'], b['address'])
                rem, dur = b['remaining_ms_raw'], b['duration_ms_raw']
                if k not in last or rem > last[k]:
                    c = t - (dur - rem) // 50
                    pend.append((c, b.get('source_side_cached'), u, t))
                last[k] = rem
        for c, s, u, t1 in pend:
            g = G[(c, s)]
            # hp before c (last frame < c) and at the first frame >= c
            pre = next((h for h in reversed(hist) if h[0] < c), None)
            post = next((h for h in hist if h[0] >= c), None)
            a = u['address']
            e1 = (post[1] if post else {}).get(a) or ents.get(a)
            e0 = (pre[1] if pre else {}).get(a)
            g['hits'].setdefault(a, dict(side=u['side'], name=u['name'], x=e1[1] if e1 else None, y=e1[2] if e1 else None,
                                         drop=(e0[4] - e1[4]) if e0 and e1 else None, seen=t1))
        pend = []
        if len(hist) > 40:
            hist.pop(0)
    return G


def electro_near(path, G):
    """For each group: source-side electro bodies alive in frames [c-4, c+1], (name, min distance to a hit)."""
    want = collections.defaultdict(list)
    for (c, s), g in G.items():
        for t in range(c - 4, c + 2):
            want[t].append((c, s))
    for d in frames(path):
        t = d['tick']
        if t not in want:
            continue
        ents = {e[7]: e for e in d.get('ents', [])}
        for c, s in want[t]:
            g = G[(c, s)]
            for u in (d.get('phase2') or {}).get('units', []):
                if u['side'] != s or not any(k in u['name'] for k in ELECTRO):
                    continue
                e = ents.get(u['address'])
                dist = min((math.hypot(e[1] - h['x'], e[2] - h['y']) for h in g['hits'].values() if h['x'] is not None),
                           default=None) if e else None
                g['electro'].add((u['name'], None if dist is None else int(dist)))


def main():
    inp, logdir, out = sys.argv[1:4]
    with open(out, 'w') as w:
        for line in open(inp):
            r = json.loads(line)
            p = os.path.join(logdir, r['match'] + '.jsonl')
            G = groups(p)
            electro_near(p, G)
            for (c, s), g in sorted(G.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
                sd = r['sides'].get(str(s)) if s is not None else None
                deck = sd['deck'] if sd else []
                zl = sd['levels'][deck.index('Zap')] if 'Zap' in deck else None
                zf = sd['slot_flags'][deck.index('Zap')] if 'Zap' in deck else None
                zp = [dict(tick=q['tick'], x=q.get('x'), y=q.get('y'), inferred=q.get('inferred', False), mech=q.get('mech'))
                      for q in r['plays'] if q['card'] == 'Zap' and q['kind'] == 'play' and q['side'] == s and abs(q['tick'] - (c - 1)) <= 3]
                w.write(json.dumps(dict(match=r['match'], flagged=bool(r['flags']), my_side=r['my_side'], c=c, s=s,
                                        deck_zap=zl is not None, zap_level=zl, zap_flag=zf,
                                        deck_electro=sorted(x for x in deck if any(k in x for k in ELECTRO)),
                                        hits=list(g['hits'].values()), electro=sorted(g['electro'], key=str),
                                        zap_play=zp)) + '\n')


if __name__ == '__main__':
    main()
