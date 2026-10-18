"""Live: when does the Hero IW button become pressable after the IW play, and when is it pressed?
Per confirmed IceWizard play (play + confirmed events): ticks to the first button state 'ready' (button events), to the
press ('ability' event) and press-confirm. Only grep-prefiltered event lines are parsed (frames skipped)."""
import glob
import json
import statistics as st
import sys

KEEP = (b'"play"', b'"confirmed"', b'"button"', b'"ability"', b'"start"')
ready_d, press_d, n_play = [], [], 0
states = {}
for f in sorted(glob.glob(sys.argv[1])):
    last_iw = None
    with open(f, 'rb') as fh:
        for raw in fh:
            h = raw[:40]
            if not any(k in h for k in KEEP):
                continue
            e = json.loads(raw)
            ev = e.get('event')
            if ev == 'start':
                last_iw = None
            elif ev == 'play' and e.get('name') == 'IceWizard':
                last_iw = dict(tick=e['tick'], ready=None, press=None)
                n_play += 1
            elif ev == 'button' and last_iw:
                states[e['state']] = states.get(e['state'], 0) + 1
                if e['state'] == 'ready' and last_iw['ready'] is None and e['tick'] >= last_iw['tick']:
                    last_iw['ready'] = e['tick']
                    ready_d.append(e['tick'] - last_iw['tick'])
            elif ev == 'ability' and last_iw and last_iw['press'] is None:
                last_iw['press'] = e['tick']
                press_d.append(e['tick'] - last_iw['tick'])
q = lambda v: [round(x) for x in st.quantiles(v, n=10)]
print('IW plays', n_play, 'button states', states)
print('play tap -> first ready (ticks): n', len(ready_d), 'min', min(ready_d), 'median', st.median(ready_d), 'deciles', q(ready_d))
print('play tap -> press (ticks): n', len(press_d), 'min', min(press_d), 'median', st.median(press_d), 'deciles', q(press_d))
