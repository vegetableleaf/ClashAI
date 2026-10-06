"""Live reader frames: non-tower bodies with card_id -1 (dropped by live_mem.to_observe and public_frame), by side/kind/max_hp."""
import json, glob, collections
c = collections.Counter(); logs = collections.Counter(); mw_logs = set()
for p in sorted(glob.glob(r'C:\Users\benpe\ClashBot\scratchpad\gauntlet\L68\live_reader\live_play_*.jsonl')):
    seen = set(); my = None
    with open(p, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            if not line.startswith('{"event": "frame"'): continue
            d = json.loads(line); my = d['my_side']
            for e in d.get('ents') or []:
                s, x, y, cid, hp, mhp, kind, addr = e[:8]
                if cid == 26000083: mw_logs.add(p)
                if cid < 0 and kind not in (12, 13) and (addr, mhp) not in seen:
                    seen.add((addr, mhp)); c[('opp' if s != my else 'mine', kind, mhp)] += 1; logs[p] += 1
print('distinct unnamed non-tower bodies:', sum(c.values()), 'in logs:', len(logs))
print(c.most_common(25)); print('logs with Mother Witch:', len(mw_logs))
json.dump(dict(bodies=[list(k) + [v] for k, v in c.most_common()], logs=len(logs), mw_logs=sorted(mw_logs)), open('live_unnamed.json', 'w'), indent=1)
