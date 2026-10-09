"""L74 identity census: every OPPONENT raw reader body in all live logs -> what the CURRENT model input path makes of it.

Mirrors GenPilot.row for feature_version >= 5 (dedupe_hero_bodies -> live_mem.to_observe -> obs_contract.from_engine):
card_id -> catalog name/form, towers -> per-side level factor, body_identity.resolve_board, the from_engine drop rules.
Sources: decision.public.raw_bodies (logs 10-05+; 'states' = decision states) and, for logs without them, every 6th
'frame' event ('fstates'). Distinct bodies by (log, address). Results: L74/runover/matches.jsonl, then overnight.out /
nav outcomes (L74/loss_review/review.py). Single process, below-normal priority. Usage (from the worktree):
  python scratchpad/gauntlet/L74/identity/census.py [--ext]      (--ext = with body_identity.EXTENSION on)
Writes census[_ext].json next to this file. Sanity: enemy class multiset vs model_bodies on states with no look-ahead.
"""
import collections, glob, json, os, sys, time
try:
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception:
    pass
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '../../../..')))
from pipeline.obs_contract import _catalog_names, catalog_card_form
from pipeline.reader_identity_aliases import dedupe_hero_bodies
from pipeline import vocab, body_identity as BI

LOG = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/'
MAIN = 'C:/Users/benpe/ClashBot/'
NAMES = _catalog_names()
EXT = '--ext' in sys.argv


def results():
    out = {}
    for l in open(MAIN + 'scratchpad/gauntlet/L74/runover/matches.jsonl'):
        m = json.loads(l); out[m['file']] = m['result']
    sys.path.insert(0, MAIN + 'scratchpad/gauntlet/L74/loss_review')
    try:
        import review as V
        for f, (r, _) in V.ladder_results().items():
            out.setdefault(f, r)
    except Exception as e:
        print('ladder results unavailable:', e)
    return out


_RES = {}


def identities(ents, observer):
    """ents: dicts side/x/y/card_id/hp/max_hp/kind -> [(body, Identity or None=dropped before identity)] for enemies."""
    fac, enemy = {}, []
    for b in ents:
        cid = int(b['card_id'])
        if cid < 0 and b['kind'] in (12, 13):           # live_mem.to_observe: towers
            if b['max_hp']:
                king = abs(float(b['x']) - 9000.0) < 1500.0
                fac.setdefault(int(b['side']), float(b['max_hp']) / (4824.0 if king else 3052.0))
            continue
        if int(b['side']) == observer:
            continue
        unnamed = cid < 0
        hp, mhp = b['hp'], b['max_hp']
        if (hp <= 0 and (mhp > 0 or unnamed)):           # from_engine fv5 drop rule (towers handled above)
            continue
        name = '-1' if unnamed else NAMES.get(cid, str(cid))
        form = 0 if unnamed else catalog_card_form(cid)[1]
        enemy.append((b, (int(b['side']), name, float(mhp), form, unnamed)))
    # resolve_board sees the whole board (both sides) in from_engine; parent levels are per side, so enemy-only is equal
    key = (tuple(e[1] for e in enemy), tuple(sorted(fac.items())))
    ids = _RES.get(key)
    if ids is None:
        ids = BI.resolve_board([e[1] for e in enemy], fac) if enemy else []
        if len(_RES) < 300000:
            _RES[key] = ids
    return [(e[0], e[1], i) for e, i in zip(enemy, ids)]


def main():
    if EXT:
        BI.EXTENSION = True
    res = results()
    agg = {}            # key -> dict
    sanity = collections.Counter()
    files = sorted(glob.glob(LOG + 'live_play_2026*.jsonl'))
    t0 = time.time()
    for n, f in enumerate(files):
        b = os.path.basename(f)
        if time.time() - os.path.getmtime(f) < 120:
            continue                                     # the log live is writing right now
        has_dec, fi = False, 0
        seen_keys = set()
        for l in open(f, encoding='utf8', errors='replace'):
            if l.startswith('{"event": "decision"') and '"raw_bodies"' in l:
                try:
                    d = json.loads(l)
                except ValueError:
                    continue
                p = d['public']
                if 'observer_side' not in p:
                    continue
                has_dec, src = True, 'states'
                obs = int(p['observer_side'])
                ents = dedupe_hero_bodies({'entities': p['raw_bodies']})['entities']
                mb = p.get('model_bodies')
            elif l.startswith('{"event": "frame"') and not has_dec:
                fi += 1
                if fi % 6:
                    continue
                try:
                    d = json.loads(l)
                except ValueError:
                    continue
                if 'ents' not in d or d.get('my_side') is None:
                    continue
                src, obs, mb = 'fstates', int(d['my_side']), None
                ents = [dict(side=e[0], x=e[1], y=e[2], card_id=e[3], hp=e[4], max_hp=e[5], kind=e[6], address=e[7])
                        for e in d['ents']]
                ents = dedupe_hero_bodies({'entities': ents})['entities']
            else:
                continue
            out = identities(ents, obs)
            mine = collections.Counter()
            for body, (_s, name, mhp, form, unnamed), ident in out:
                cls = None if ident.cls is None else vocab.UNIT_VOCAB[ident.cls]
                if cls is not None:
                    mine[cls] += 1
                k = (int(body['card_id']), name, form, int(mhp), cls, ident.reason)
                a = agg.get(k)
                if a is None:
                    a = agg[k] = dict(states=0, fstates=0, bodies=set(), files=set(), kinds=collections.Counter())
                a[src] += 1
                a['bodies'].add((b, body.get('address')))
                a['files'].add(b)
                a['kinds'][int(body.get('kind', -1))] += 1
            if mb is not None:
                got = collections.Counter(vocab.UNIT_VOCAB[m['cls']] for m in mb if m.get('side') == 1)
                la = 'same_tick' if p.get('raw_tick') == p.get('model_tick') else 'lookahead'
                sanity[la + (':equal' if got == mine else ':differ')] += 1
        if n % 50 == 0:
            print(f'[{n}/{len(files)}] {b} {time.time() - t0:.0f}s keys {len(agg)}', flush=True)
    rows = []
    for k, a in agg.items():
        fl = sorted(a['files'])
        r = collections.Counter(res.get(x, 'unknown') for x in fl)
        rows.append(dict(card_id=k[0], name=k[1], form=k[2], max_hp=k[3], cls=k[4], reason=k[5], states=a['states'],
                         fstates=a['fstates'], bodies=len(a['bodies']), matches=len(fl), results=dict(r),
                         kinds=dict(a['kinds']), files=fl))
    rows.sort(key=lambda r: (-r['bodies']))
    out = os.path.join(HERE, 'census_ext.json' if EXT else 'census.json')
    json.dump(dict(sanity=dict(sanity), n_files=len(files), results_known=len(res), rows=rows), open(out, 'w'), indent=0)
    print('sanity (enemy class multiset == model_bodies, no-look-ahead states):', dict(sanity))
    print('wrote', out, len(rows), 'keys', f'{time.time() - t0:.0f}s')


if __name__ == '__main__':
    main()
