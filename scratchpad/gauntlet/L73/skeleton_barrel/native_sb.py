"""Pros: when do pros' Logs roll relative to the Skeleton Barrel balloon's death and the skeleton spawn?

Read-only over the native re-drive corpora behind gen_dataset_v31_public (the fv4 BC corpus; meta 'corpora').
Same instrument as live_sb.py (episodes, roll start from the Log projectile rows, per-skeleton band crossing),
applied per (replay, defending side). Native frames: 10-tick cadence + play frames.
Caveat: the re-drive replays the pro's command ticks into a re-simulated battle; the balloon's death there can
differ from the original match, so the pro timing below is relative to the re-drive the model trains on.
"""
import glob, json, os, statistics, sys
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, SB_IDS
import live_sb as LS

OUT = os.path.join(os.path.dirname(__file__), 'native_results.json')


def own_xy(x, y, side):
    return (x / 18000, 1 - y / 32000) if side == 0 else (1 - x / 18000, y / 32000)


def build(rec, side):
    frames = {}
    for f in sorted(rec['frames'] + rec.get('play_frames', []), key=lambda f: int(f['tick'])):
        frames[int(f['tick'])] = f
    snaps, logrows = {}, {}
    for t, f in frames.items():
        snaps[t] = [(e[0], e[1], e[2], int(e[7]), e[4], e[5], e[6], e[8]) for e in f['entities']]
        po = (f.get('public_objects') or {}).get('projectiles') or []
        logrows[t] = [dict(side=p['side'], x=p['x'], y=p['y'], target_x=p.get('target_x'), target_y=p.get('target_y'),
                           card_id=p['card_id']) for p in po if p.get('card_id') == LS.LOG_ID and p['side'] == side]
    ev = [dict(event='play', name='Log', tick=int(p['tick']), xy=list(own_xy(p['x'], p['y'], side)))
          for p in rec['log'] if p.get('accepted') and p['card'] == 'the-log' and int(p['side']) == side]
    return dict(ev=ev, start={}, side=side, snaps=snaps, ticks=sorted(snaps), src='native', logrows=logrows, model={},
                ckpt='native_pro', fv=None)


def main():
    meta = json.load(open(os.path.join(ROOT, 'icebow/data/pipeline/gen_dataset_v31_public.json')))
    files = [f for c in meta['corpora'] for f in glob.glob(os.path.join(ROOT, c, 'j*', 'replay_*.json'))]
    res = dict(files=0, pairs_unaimed=0, episodes=[], logs=[], all_logs=[], tp_to_rs=[], conf_to_rs=[])
    scanned = 0
    for f in files:
        scanned += 1
        s = open(f, encoding='utf-8').read()
        if '"skeleton-barrel"' not in s or '"the-log"' not in s:
            continue
        rec = json.loads(s)
        sb_sides = {int(p['side']) for p in rec['log'] if p['card'] == 'skeleton-barrel' and p.get('accepted')}
        log_sides = {int(p['side']) for p in rec['log'] if p['card'] == 'the-log' and p.get('accepted')}
        for side in (0, 1):
            if (1 - side) in sb_sides and side in log_sides:
                res['files'] += 1
                LS.analyse_L(build(rec, side), os.path.basename(f), res)
        if scanned % 2000 == 0:
            print('scanned', scanned, 'pairs', res['files'], 'aimed logs', len(res['logs']), flush=True)
    S = LS.summarise(res)
    S['scanned_replays'] = scanned
    json.dump(dict(summary=S, logs=res['logs'], episodes=res['episodes']), open(OUT, 'w'), indent=1, default=str)
    print(json.dumps({k: v for k, v in S.items() if k != 'balloon_alive_timing'}, indent=1, default=str))


if __name__ == '__main__':
    main()
