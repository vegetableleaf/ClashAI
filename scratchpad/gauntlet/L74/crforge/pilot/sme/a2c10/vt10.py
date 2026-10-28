"""python vt10.py LIVE_LOG SIDE T0 T1 -- runs of frames where SIDE's hero Ice Wizard ability has a valid target (an enemy
carrying IceWizardHeroCold / IceWizardHeroSlow from SIDE; the rule of 9N's sme_live.iw_valid_ticks)."""
import json, sys
f, s, t0, t1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
runs, cur = [], None
for l in open(f, 'rb'):
    if b'"frame"' not in l[:40]:
        continue
    d = json.loads(l)
    t = d.get('tick')
    if t is None or not t0 <= t <= t1:
        continue
    v = any(b.get('name') in ('IceWizardHeroCold', 'IceWizardHeroSlow') and b.get('source_side_cached') == s and u.get('side') != s
            for u in (d.get('phase2') or {}).get('units', []) for b in u.get('buffs') or [] if isinstance(b, dict))
    if v and cur is None:
        cur = [t, t]
    elif v:
        cur[1] = t
    elif cur is not None:
        runs.append(cur)
        cur = None
print(runs + ([cur] if cur else []))
