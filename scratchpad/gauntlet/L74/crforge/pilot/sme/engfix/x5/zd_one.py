"""ENG-FIX5: SME_ZAP_DEAD (+ ZD_BLDG) fired / blocked candidates of one inputs record near a tick.
python -I zd_one.py INPUTS.jsonl MATCH T W"""
import json, os, sys
os.environ['SME_ZAP_DEAD'] = '1'
os.environ['SME_ZD_BLDG'] = '1'
sys.path.insert(0, 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/crforge/pilot/sme')
import mech_rules as M  # noqa: E402
T635 = 'C:/Users/benpe/ClashBot/.foreman/scratch/reader_torn/sme/tables/16.635.3'
m, T, W = sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
for l in open(sys.argv[1]):
    r = json.loads(l)
    if not r['match'].endswith(m):
        continue
    sides = {int(k): v for k, v in r['sides'].items()}
    M.ZD_BLDG = 1
    _, fired, blocked = M.zap_dead(M.zd_frames('C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/' + r['match'] + '.jsonl'),
                                   r['plays'], sides, T635, r.get('reader_hidden') or ())
    print('decks', {s: sides[s]['deck'] for s in sides})
    for e in fired:
        if abs(e['t'] - T) <= W:
            print('FIRE', json.dumps(e)[:600])
    for e in blocked:
        if abs(e['t'] - T) <= W:
            print('BLOCK', e['why'], json.dumps(e)[:600])
