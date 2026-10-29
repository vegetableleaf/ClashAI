"""ENG-FIX4: SME_TZ_REACH census -- SME_TOWER_ZAP on every scored record of dev + FRESH1-6, flat TZ_BODY vs per-body reach
(mech_rules.tz_reach). The record's plays minus its own tower_zap firings = the extractor's input to tower_zaps. Prints
each candidate whose outcome differs, then the reason counts both ways.
    python -I tzr_census.py OUT.txt   (MECH_DIR=dir imports mech_rules from there; default the sme dir)"""
import collections, json, os, sys
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get('MECH_DIR') or os.path.dirname(H))
import mech_rules as M  # noqa: E402
LIVE = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/'
TAB = {'dev': 'C:/Users/benpe/crforge_eval/cache/tables/16.402.22'}
T635 = 'C:/Users/benpe/ClashBot/.foreman/scratch/reader_torn/sme/tables/16.635.3'
SETS = [(s, H + '/r6/%s_on.jsonl' % s) for s in ('dev', 'fresh1', 'fresh2', 'fresh3', 'fresh4', 'fresh5')] + \
       [('fresh6', H + '/fresh6/inputs_rngfree.jsonl')]
out = open(sys.argv[1], 'w')
cnt = {'flat': collections.Counter(), 'reach': collections.Counter()}
nrec = ndiff = 0
for s, f in SETS:
    for line in open(f):
        r = json.loads(line)
        nrec += 1
        sides = {int(k): v for k, v in r['sides'].items()}
        plays = [p for p in r['plays'] if p.get('mech') != 'tower_zap']
        fr, hid = M.raw_frames(LIVE + r['match'] + '.jsonl'), r.get('reader_hidden') or ()
        a = M.tower_zaps(fr, plays, sides, hid)
        b = M.tower_zaps(fr, plays, sides, hid, names=M.tz_names(LIVE + r['match'] + '.jsonl'), tables=TAB.get(s, T635))
        res = {}
        for k, (_, fired, blocked) in (('flat', a), ('reach', b)):
            for e in fired:
                cnt[k]['FIRED'] += 1
                res.setdefault(tuple(e['tower']) + (e['t'],), {})[k] = 'FIRED R %d' % e['R']
            for e in blocked:
                cnt[k][e['why']] += 1
                res.setdefault(tuple(e['tower']) + (e['t'],), {})[k] = e['why']
        for key, v in sorted(res.items(), key=lambda kv: kv[0][3]):
            if v.get('flat') != v.get('reach'):
                ndiff += 1
                print(s, r['match'], 'tower', key[:3], 't', key[3], 'flat', v.get('flat'), '-> reach', v.get('reach'), file=out)
print('records', nrec, 'changed candidates', ndiff, file=out)
for k in cnt:
    print(k, dict(cnt[k]), file=out)
out.close()
print(open(sys.argv[1]).read())
