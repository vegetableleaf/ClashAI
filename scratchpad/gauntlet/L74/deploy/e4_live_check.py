"""Owner 10-10 complaints about the E4 live model, measured per match from live logs (E4 = ckpt path contains rdef_e4):
tower lost in the first 60 s, seconds at full elixir (leak), Tornado plays per match and the share with no enemy body
within 6 tiles of our half (a 'pull for nothing' proxy), win. Old = towerref_w2 logs from 10-09/10."""
import glob, json, sys
import numpy as np
D = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/'
res = {'E4': [], 'OLD': []}
for f in sorted(glob.glob(D + 'live_play_2026100[9]_*.jsonl') + glob.glob(D + 'live_play_20261010_*.jsonl')):
    head = open(f, encoding='utf-8', errors='replace').readline()
    arm = 'E4' if 'rdef_e4' in head else ('OLD' if 'towerref_w2' in head else None)
    if arm is None: continue
    first_loss, leak, torn, torn_far, prev_t, won, last = None, 0.0, 0, 0, None, None, None
    for l in open(f, encoding='utf-8', errors='replace'):
        if l.startswith('{"event": "decision"'):
            d = json.loads(l); p = d['public']; t = p['model_tick']
            el = p.get('own_elixir_raw')
            me_ = p['observer_side']; push = any(b['side'] != me_ and b['card_id'] != -1 and (b['y'] / 1000 if me_ == 0 else 32 - b['y'] / 1000) > 16 for b in p['raw_bodies'])
            if prev_t is not None and el is not None and el >= 9.95 and push: leak += (t - prev_t) / 20
            prev_t = t; last = p
            mine = [b for b in p['raw_bodies'] if b['card_id'] == -1 and b['side'] == p['observer_side']]
            if first_loss is None and len(mine) < 3 and t <= 1200: first_loss = t
        elif l.startswith('{"event": "play"'):
            d = json.loads(l)
            if d['name'] == 'Tornado':
                torn += 1
                if last is not None:
                    me = last['observer_side']
                    near = [b for b in last['raw_bodies'] if b['side'] != me and b['card_id'] != -1
                            and (b['y'] / 1000 if me == 0 else 32 - b['y'] / 1000) > 15]
                    torn_far += not near
        elif l.startswith('{"event": "result"') or l.startswith('{"event": "end"'):
            try: won = json.loads(l).get('won')
            except ValueError: pass
    if prev_t is None: continue
    res[arm].append((first_loss is not None, leak, torn, torn_far, won))
for arm, r in res.items():
    if not r: continue
    a = np.array([[x[0], x[1], x[2], x[3]] for x in r], float)
    w = [x[4] for x in r if x[4] is not None]
    print(f'{arm}: matches {len(r)} | tower lost <60s {a[:,0].mean():.0%} | s at full elixir with an enemy on our half {a[:,1].mean():.1f} | Tornados {a[:,2].mean():.2f}/match, with no enemy on our half {a[:,3].sum() / max(a[:,2].sum(), 1):.0%}')
