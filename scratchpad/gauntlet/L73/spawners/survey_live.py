"""Survey live_play logs: which spawner-family card ids appear (opponent side), body counts by max_hp. Read-only."""
import json, glob, collections, os, sys
ROOT = r'C:\Users\benpe\ClashBot'
FAM = {26000007:'Witch',13000007:'Witch@evo',26000048:'NightWitch',27000010:'Furnace',13000106:'Furnace@evo',
       26000083:'MotherWitch',27000009:'Tombstone',27000001:'GoblinHut',27000005:'BarbarianHut',28000010:'Graveyard',
       27000013:'GoblinDrill',13000108:'GoblinDrill@evo',26000056:'SkeletonBarrel',13000056:'SkeletonBarrel@evo',
       27000012:'GoblinCage',13000107:'GoblinCage@evo',26000087:'Phoenix',26000099:'Goblinstein',26000069:'SkeletonKing',
       26000009:'Golem',26000029:'LavaHound',26000067:'ElixirGolem',28000004:'GoblinBarrel',13000081:'GoblinBarrel@evo',
       26000060:'GoblinGiant',13000060:'GoblinGiant@evo',28000015:'BarbLog',26000095:'GoblinDemolisher',26000097:'SuspiciousBush'}
logs = sorted(glob.glob(ROOT + r'\scratchpad\gauntlet\L68\live_reader\live_play_*.jsonl'))
out = {'logs': len(logs), 'logs_with_frames': 0, 'frames': 0, 'by_card': {}, 'logs_by_card': collections.Counter(), 'ckpt_fv': collections.Counter()}
per = collections.defaultdict(lambda: collections.Counter())
for p in logs:
    seen = {}; nfr = 0; fv = None; ck = None
    with open(p, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            if '"frame"' not in line[:30] and '"start"' not in line[:30]:
                continue
            try: d = json.loads(line)
            except Exception: continue
            if d.get('event') == 'start':
                fv = d.get('feature_version'); ck = os.path.basename(os.path.dirname(str(d.get('ckpt'))))+'/'+os.path.basename(str(d.get('ckpt')))
                continue
            if d.get('event') != 'frame': continue
            nfr += 1; ms = d.get('my_side')
            for e in d.get('ents') or []:
                if len(e) < 8: continue
                s, x, y, cid, hp, mhp, kind, addr = e[:8]
                if cid in FAM and s != ms:
                    seen.setdefault((cid, addr), mhp)
    out['ckpt_fv'][f'{ck}|fv{fv}'] += 1
    if nfr: out['logs_with_frames'] += 1
    out['frames'] += nfr
    cards = set()
    for (cid, addr), mhp in seen.items():
        per[FAM[cid]][mhp] += 1; cards.add(FAM[cid])
    for c in cards: out['logs_by_card'][c] += 1
out['by_card'] = {k: dict(sorted(v.items())) for k, v in per.items()}
json.dump(out, open('survey_live.json', 'w'), indent=1, default=str)
print(json.dumps({k: out[k] for k in ('logs', 'logs_with_frames', 'frames')}), dict(out['logs_by_card']))
for k, v in out['by_card'].items(): print(k, v)
print(out['ckpt_fv'].most_common(12))
