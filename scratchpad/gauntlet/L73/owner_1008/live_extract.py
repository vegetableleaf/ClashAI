"""Compact per-match live records for the owner 10-08 questions. Read-only on live logs."""
import json, glob, os, pickle, sys
D = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/'

def group(st, f):
    sha = (st.get('ckpt_sha256') or '')[:8]; day = f[10:18]
    aim = (st.get('decision_options') or {}).get('spell_aim')
    if sha == '76fdfaac': return 'R1e' if day in ('20261005', '20261006') else 'R1e_late'
    if sha == 'e7359f2b':
        if aim == 'rocket_area': return 'STACK_RA'
        return 'STACK_ALON' if st.get('anti_leak') else 'STACK_ALOFF'
    return None

def ai(a): return int(a, 16) if isinstance(a, str) else int(a)

def rec(f):
    m = dict(file=os.path.basename(f), dec=[], play=[], conf=[], ab=[], abc=[], frames=[], side=None, start=None)
    with open(f) as fh:
        for l in fh:
            try: d = json.loads(l)
            except Exception: continue
            ev = d.get('event')
            if ev == 'start' and m['start'] is None: m['start'] = d
            elif ev == 'decision':
                p = d.get('public') or {}; dc = d['decision']
                if m['side'] is None and 'observer_side' in p: m['side'] = p['observer_side']
                r = dict(t=d['tick'], play=dc.get('play'), p=dc.get('p_play'), tau=dc.get('gate_tau'), name=dc.get('name'),
                         xy=dc.get('xy'), stalled=dc.get('stalled'), forced=d.get('forced'), el=p.get('own_elixir_raw'),
                         hand=[h['name'] for h in p.get('own_hand', [])], mt=p.get('model_tick'),
                         rb=[(b['side'], b['x'], b['y'], b['card_id'], b['hp'], b.get('kind'), ai(b['address'])) for b in p.get('raw_bodies', [])],
                         rp=[(q['side'], q['x'], q['y'], q['card_id'], q.get('target_x'), q.get('target_y')) for q in p.get('raw_projectiles', [])])
                if dc.get('play'): r['mb'] = [(b['cls'], b['side'], b['x'], b['y']) for b in p.get('model_bodies', [])]
                m['dec'].append(r)
            elif ev == 'play': m['play'].append(dict(t=d['tick'], name=d['name'], xy=d['xy'], el=d.get('elixir'), forced=d.get('forced'), p=d.get('p_play')))
            elif ev == 'confirmed': m['conf'].append(dict(t=d['tick'], name=d['name'], xy=d.get('intended')))
            elif ev == 'ability': m['ab'].append(dict(t=d['tick'], why=d.get('why'), el=d.get('elixir')))
            elif ev == 'ability_confirmed': m['abc'].append(dict(t=d['tick'], drop=d.get('elixir_drop')))
            elif ev == 'frame':
                if m['side'] is None: m['side'] = d.get('my_side')
                m['frames'].append((d['tick'], d.get('elixir'), [(e[0], e[1], e[2], e[3], e[4], e[6], ai(e[7])) for e in d['ents'] if e[3] != -1]))
    return m

if __name__ == '__main__':
    out = {}
    for f in sorted(glob.glob(D + 'live_play_2026100[5678]_*.jsonl')):
        try: st = json.loads(open(f).readline())
        except Exception: continue
        if st.get('event') != 'start': continue
        g = group(st, os.path.basename(f))
        if g is None: continue
        m = rec(f)
        if len(m['dec']) < 50: continue
        out.setdefault(g, []).append(m)
        print(g, m['file'], len(m['dec']), len(m['frames']), flush=True)
    for g, v in out.items():
        pickle.dump(v, open(f'live_{g}.pkl', 'wb'))
    print({g: len(v) for g, v in out.items()})
