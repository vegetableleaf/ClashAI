"""ENG-FIX5 census for SME_ZD_SINGLE: every SME_ZAP_DEAD candidate (ZD_BLDG on) blocked as enemy_targets_victim on the
scored records of dev + FRESH1-8, with its attackers (name, single-target bit), victims and the victims those attackers
target; then the outcome with SME_ZD_SINGLE on (fired / the next block reason). python -I zds_census.py OUT"""
import json, os, sys
os.environ['SME_ZAP_DEAD'] = '1'
os.environ['SME_ZD_BLDG'] = '1'
S = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/crforge/pilot/sme/'
sys.path.insert(0, S)
import mech_rules as M  # noqa: E402
LIVE = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/'
T635 = 'C:/Users/benpe/ClashBot/.foreman/scratch/reader_torn/sme/tables/16.635.3'
T402 = 'C:/Users/benpe/crforge_eval/cache/tables/16.402.22'
files = [(S + 'engfix/r9/%s_on.jsonl' % s, T402 if s == 'dev' else T635) for s in ('dev', 'fresh1', 'fresh2', 'fresh3', 'fresh4', 'fresh5', 'fresh6')]
files += [(S + 'engfix/fresh7/inputs_rngfree.jsonl', T635), (S + 'engfix/fresh8/inputs_rngfree.jsonl', T635)]
out = open(sys.argv[1], 'w')
cnt = {0: {}, 1: {}}
for f, tab in files:
    for l in open(f):
        r = json.loads(l)
        sides = {int(k): v for k, v in r['sides'].items()}
        fr = M.zd_frames(LIVE + r['match'] + '.jsonl')
        res = {}
        for k in (0, 1):
            M.ZD_SINGLE = k
            _, fi, bl = M.zap_dead(fr, r['plays'], sides, tab, r.get('reader_hidden') or ())
            for e in fi:
                res.setdefault((e['side'], e['t']), {})[k] = 'FIRED R %d (%d, %d)' % (e['R'], e['x'], e['y'])
                cnt[k]['FIRED'] = cnt[k].get('FIRED', 0) + 1
            for e in bl:
                res.setdefault((e['side'], e['t']), {})[k] = e['why'] + ' ' + str(e.get('detail'))[:100]
                cnt[k][e['why']] = cnt[k].get(e['why'], 0) + 1
        for key, v in sorted(res.items()):
            if str(v.get(0)).startswith('enemy_targets_victim') or v.get(0) != v.get(1):
                print(f.split('/')[-2] + '/' + f.split('/')[-1], r['match'][10:], key, 'off:', v.get(0), '| on:', v.get(1), file=out)
for k in cnt:
    print('ZD_SINGLE', k, sorted(cnt[k].items()), file=out)
out.close()
print(open(sys.argv[1]).read()[-3000:])
