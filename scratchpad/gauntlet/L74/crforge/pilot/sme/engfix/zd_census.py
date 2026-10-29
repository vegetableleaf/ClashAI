# zd_census.py OUT -- ENG-FIX3: SME_ZAP_DEAD firings + blocked candidates on dev + FRESH1-5 (r6 ON records' plays / sides)
import json, glob, sys, os
os.environ['SME_ZAP_DEAD'] = '1'
R = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/'
sys.path.insert(0, R + 'crforge/pilot/sme')
import mech_rules  # noqa: E402
T = 'C:/Users/benpe/ClashBot/.foreman/scratch/reader_torn/sme/tables/16.635.3'
out = open(sys.argv[1], 'w')
nf = nb = 0
for f in sorted(glob.glob(R + 'crforge/pilot/sme/engfix/r6/*_on.jsonl')):
    for l in open(f):
        x = json.loads(l)
        sides = {int(k): v for k, v in x['sides'].items()}
        _, fired, blocked = mech_rules.zap_dead(mech_rules.zd_frames(R + "../L68/live_reader/" + x['match'] + '.jsonl'),
                                               x['plays'], sides, T, x.get('reader_hidden') or ())
        for e in fired:
            nf += 1; print('FIRE', os.path.basename(f), x['match'][-15:], x['flags'], json.dumps(e), file=out)
        for e in blocked:
            nb += 1; print('BLOCK', os.path.basename(f), x['match'][-15:], e['why'], json.dumps(e)[:400], file=out)
        out.flush()
print('fired', nf, 'blocked', nb, file=out)
print('ZD_CENSUS_DONE', nf, nb)
