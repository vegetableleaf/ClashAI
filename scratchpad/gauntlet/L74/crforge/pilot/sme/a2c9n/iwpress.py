"""iwpress.py INPUTS.jsonl -- A2c-9N census: every hero Ice Wizard press (both sides) against the ability's valid-target test.
The game's IceWizardHero ability, once pressed, waits (ActionWaitToActivate, checked every 50 ms) for a target from
IceWizardHero_target_resolver: an enemy character anywhere (Global shape) that carries the hero's IceWizardHeroCold /
IceWizardHeroSlow buff. So a press at P with a valid target fires at P; a press with none fires on the first valid tick.
Per press: tick (R), source, the hero play's tick, the last reader frame < R with a valid target (lastv), whether the frame
just before R had one, and the first frame >= R with one."""
import json, sys
LIVE = r'C:\Users\benpe\ClashBot\scratchpad\gauntlet\L68\live_reader\%s.jsonl'
BUFFS = ('IceWizardHeroCold', 'IceWizardHeroSlow')


def valid_ticks(match):
    out, seen = {}, set()
    for line in open(LIVE % match, 'rb'):
        if b'"frame"' not in line[:40]:
            continue
        d = json.loads(line)
        t = d.get('tick')
        if t is None or t < 0 or t in seen:
            continue
        seen.add(t)
        v = {0: False, 1: False}   # v[s]: side s's hero has a valid target (an enemy of s carries s's cold/slow)
        for u in (d.get('phase2') or {}).get('units', []):
            for b in u.get('buffs') or []:
                if isinstance(b, dict) and b.get('name') in BUFFS and b.get('source_side_cached') in (0, 1) \
                        and b['source_side_cached'] != u.get('side'):
                    v[b['source_side_cached']] = True
        out[t] = v
    return out


rows = []
for l in open(sys.argv[1]):
    rec = json.loads(l)
    pr = [p for p in rec['plays'] if p['kind'] == 'ability' and p['card'] == 'IceWizard']
    if not pr:
        continue
    vt = valid_ticks(rec['match'])
    ts = sorted(vt)
    for p in pr:
        R, s = p['tick'], p['side']
        hero = max((q['tick'] for q in rec['plays'] if q['kind'] == 'play' and q['card'] == 'IceWizard' and q['side'] == s
                    and q['tick'] < R), default=None)
        before = [t for t in ts if t < R and (hero is None or t > hero)]
        lastv = max((t for t in before if vt[t][s]), default=None)
        prev = before[-1] if before else None
        firstv = min((t for t in ts if t >= R and vt[t][s]), default=None)
        rows.append(dict(m=rec['match'][10:], side=s, own=s == rec['my_side'], R=R, src=p.get('source'), lo=p['run_ticks'][0],
                         hi=p['run_ticks'][1], hero=hero, lastv=lastv, prev_valid=bool(prev and vt[prev][s]), firstv=firstv))
for r in rows:
    print(json.dumps(r))
import collections
c = collections.Counter((r['own'], r['src'], r['prev_valid'], r['firstv'] is not None and r['firstv'] - r['R'] <= 4) for r in rows)
for k, v in sorted(c.items(), key=str):
    print('own=%s src=%s valid_on_frame_before=%s valid_by_R+4=%s: %d' % (k + (v,)))
