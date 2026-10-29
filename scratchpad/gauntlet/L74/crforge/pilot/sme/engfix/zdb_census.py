# zdb_census.py OUT -- ENG-FIX4: SME_ZAP_DEAD firings with SME_ZD_BLDG off vs on, dev + FRESH1-6 (r7 OFF inputs; 155749 from
# the TZ_REACH extraction ex/in_1.jsonl); prints every candidate whose outcome differs, then the fired / blocked counts.
import collections, json, os, sys
os.environ['SME_ZAP_DEAD'] = '1'
sys.path.insert(0, os.environ.get("MECH_DIR") or "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/crforge/pilot/sme")
import mech_rules as M  # noqa: E402
H = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/crforge/pilot/sme/engfix/'
LIVE = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/'
TAB = {'dev': 'C:/Users/benpe/crforge_eval/cache/tables/16.402.22'}
T635 = 'C:/Users/benpe/ClashBot/.foreman/scratch/reader_torn/sme/tables/16.635.3'
recs = [(s, json.loads(l)) for s in ('dev', 'fresh1', 'fresh2', 'fresh3', 'fresh4', 'fresh5', 'fresh6') for l in open(H + 'r7/%s_off.jsonl' % s)]
alt = {json.loads(l)['match']: json.loads(l) for l in open('C:/Users/benpe/ClashBot/.foreman/scratch/engfix4/ex/in_1.jsonl')}
out, cnt = open(sys.argv[1], 'w'), {0: collections.Counter(), 1: collections.Counter()}
for s, r in recs:
    if '155749' in r['match']:
        r = alt[r['match']]
    sides = {int(k): v for k, v in r['sides'].items()}
    fr = M.zd_frames(LIVE + r['match'] + '.jsonl')
    res = {}
    for k in (0, 1):
        M.ZD_BLDG = k
        _, f, b = M.zap_dead(fr, r['plays'], sides, TAB.get(s, T635), r.get('reader_hidden') or ())
        for e in f:
            cnt[k]['FIRED'] += 1; res.setdefault((e['side'], e['t']), {})[k] = 'FIRED R %d at (%d, %d)' % (e['R'], e['x'], e['y'])
        for e in b:
            cnt[k][e['why']] += 1; res.setdefault((e['side'], e['t']), {})[k] = e['why'] + ' ' + str(e.get('detail'))[:80]
    for key, v in sorted(res.items()):
        if v.get(0) != v.get(1):
            print(s, r['match'][10:], key, 'off:', v.get(0), '| on:', v.get(1), file=out)
for k in cnt:
    print('ZD_BLDG', k, dict(cnt[k]), file=out)
out.close()
print(open(sys.argv[1]).read())
