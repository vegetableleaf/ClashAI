"""ENG-FIX (091720@3517): Boss Bandit ability casts: per Boss Bandit generation, each state-10 rise (ents_state) and the
phase-2 cast_timer, vs the start of its BossBandit_ability_buff (first sighting - (duration - remaining) / 50).
    python -I bb_census.py LIVE_DIR LIST..."""
import json, os, sys
live = sys.argv[1]
for f in sys.argv[2:]:
    ms = [json.loads(l)['match'] for l in open(f)] if f.endswith('.jsonl') else \
        [l.split('\t')[0].strip() for l in open(f) if l.strip() and not l.startswith('#')]
    for m in ms:
        bb, st, rises, buffs, last = set(), {}, [], {}, {}
        for line in open(os.path.join(live, m + '.jsonl'), 'rb'):
            if b'"frame"' not in line[:40] or b'BossBandit' not in line:
                continue
            d = json.loads(line)
            t = d['tick']
            if t is None or t < 0:
                continue
            for u in d['phase2']['units']:
                if u.get('name') == 'BossBandit':
                    g = u['generation']; bb.add(g); last[g] = t
                    for b in u.get('buffs') or []:
                        if isinstance(b, dict) and b.get('name') == 'BossBandit_ability_buff' and b.get('remaining_ms_raw') is not None:
                            buffs.setdefault((g, b.get('address')), t - (b['duration_ms_raw'] - b['remaining_ms_raw']) // 50)
                    ct = (u.get('ability') or {}).get('cast_timer_ms_raw')
                    if ct:
                        last[g, 'ct'] = (t, ct)
            for s, _, _, g in d.get('ents_state') or []:
                if g in bb:
                    if s == 10 and st.get(g) != 10:
                        rises.append((g, t, (d['phase2'] and next((u['ability'] for u in d['phase2']['units'] if u.get('generation') == g), None))))
                    st[g] = s
        for g, t, ab in rises:
            b = sorted(v for (gg, _), v in buffs.items() if gg == g and v >= t - 10)
            print(m[10:], g, 'rise', t, 'ab', ab, 'buff_start', b[:1], 'bb_last', last.get(g))
