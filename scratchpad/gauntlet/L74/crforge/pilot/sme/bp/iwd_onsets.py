"""Divergence episodes of a run that start within 3 ticks after a hero IW deploy (iwdeploy output), with details.
python3 iwd_onsets.py IWD.jsonl RUNDIR"""
import json, os, sys
iw = [json.loads(l) for l in open(sys.argv[1])]
res = {json.loads(l)['match']: json.loads(l) for l in open(os.path.join(sys.argv[2], 'results.jsonl'))}
for d in iw:
    r = res.get(d['match'], {})
    for e in r.get('episodes', []):
        if d['R'] < e['start'] <= d['R'] + 3:
            det = [x for x in (e.get('detail') or []) if 'only' in x[0]][:4]
            sim = {int(t): v for t, v in d['sim'].items()}
            print(d['match'][10:], 'R', d['R'], 'onset', e['start'], 'frames', e['frames'], 'healed', e['healed'],
                  'simR+1', sim.get(d['R'] + 1), 'rec', {t: v for t, v in d['rec'].items() if int(t) <= d['R'] + 3}, json.dumps(det)[:300])
