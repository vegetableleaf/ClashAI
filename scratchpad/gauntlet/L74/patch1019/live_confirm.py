"""PATCH1019 LIVE CONFIRMATION (W23, 2026-10-22): is the 2026-10-19 balance update visible in the live reader logs?

Public bodies only (positions, hp, max_hp of every body on the board); no hand / deck / elixir is read.
  1. SKELETON RING: every group of exactly 3 Skeleton bodies (card 26000010) first seen together (same side, within 2
     ticks, all deploying) -> its ring radius (mean member distance to the members' centroid). The fork's law
     (formation.rs scale_radius) puts 3 members at SummonRadius x 577 / 500: 400 -> 461, 500 -> 577.
  2. DAMAGE PER HIT on crown towers: a tower hp drop between consecutive frames that equals a present enemy card's
     old or new damage at that body's level (level read from its max_hp on the unified ladder). Only values where old
     and new differ count. Skeleton Barrel: the death damage of the falling barrel, credited to a balloon of the
     attacking side seen in the last 40 ticks.
  python live_confirm.py OUT.json LOG_OR_GLOB [...]      (file names live_play_YYYYMMDD_HHMMSS.jsonl; era by name)"""
import glob
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict

PATCH_STAMP = '20261019_0603'          # the device's update folder mtime (EDT, the laptop's clock); logs start 05:58 / 06:03
MULT = [100, 110, 121, 133, 146, 160, 176, 193, 212, 233, 256, 281, 309, 339, 372, 409]   # unified level 1..16, percent
SKEL = 26000010
# card id -> (name, level-1 hp of the body, old level-1 damage, new level-1 damage)   [fork table / device diff]
HIT = {26000040: ('Dart Goblin', 102, 59, 56), 26000054: ('Cannon Cart', 707, 83, 79),
       26000107: ('Minion Giant', 710, 66, 60), 26000057: ('Flying Machine', 240, 67, 70)}
BALLOON = (26000056, 208, 57, 64)      # Skeleton Barrel: balloon hp, SkeletonContainer death damage old -> new
TOWER_SLOTS = ((9000, 3000), (3500, 6500), (14500, 6500), (9000, 29000), (3500, 25500), (14500, 25500))


def level(hp1, mx):
    return next((lv for lv in range(1, 17) if hp1 * MULT[lv - 1] // 100 == mx), None)


def scan(path, out):
    era = 'post' if re.search(r'(\d{8}_\d{4})', path).group(1) >= PATCH_STAMP else 'pre'
    seen = {}                              # (addr, cid) -> last tick
    group = None                           # open skeleton group: [tick, side, [(x, y, kind)]]
    tower_hp = {}
    balloon = {}                           # side -> (tick, level)
    radii = []

    def close():
        if group and len(group[2]) == 3 and all(k in (12, 14) for _, _, k in group[2]):
            cx = sum(p[0] for p in group[2]) / 3
            cy = sum(p[1] for p in group[2]) / 3
            radii.append(sum(math.hypot(p[0] - cx, p[1] - cy) for p in group[2]) / 3)

    with open(path, 'rb') as f:
        for raw in f:
            if b'"frame"' not in raw[:40]:
                continue
            j = json.loads(raw)
            t = j['tick']
            ents = j['ents']
            present = defaultdict(list)    # side -> [(cid, max_hp)]
            for s, x, y, cid, hp, mx, kind, addr in ents:
                if cid == -1:
                    if any(abs(x - tx) < 600 and abs(y - ty) < 600 for tx, ty in TOWER_SLOTS):
                        key = (s, round(x / 1000), round(y / 1000))
                        prev = tower_hp.get(key)
                        tower_hp[key] = (t, hp)
                        if prev and 0 < t - prev[0] <= 2 and prev[1] > hp > 0:
                            out['_pending'].append((s, prev[1] - hp, t))
                    continue
                if cid in HIT:
                    present[s].append((cid, mx))
                if cid == BALLOON[0]:
                    lv = level(BALLOON[1], mx)
                    if lv:
                        balloon[s] = (t, lv)
                if cid == SKEL:
                    last = seen.get((addr, cid))
                    seen[(addr, cid)] = t
                    if last is not None and t - last <= 60:
                        continue
                    if group and (t - group[0] > 2 or s != group[1]
                                  or math.hypot(x - group[2][0][0], y - group[2][0][1]) > 2500):
                        close()
                        group = None
                    if group is None:
                        group = [t, s, []]
                    group[2].append((x, y, kind))
            for s_tower, drop, td in out.pop('_pending', []):
                attacker = 1 - s_tower
                for cid, mx in present[attacker]:
                    name, hp1, d0, d1 = HIT[cid]
                    lv = level(hp1, mx)
                    if lv is None:
                        out['nolevel'][name] += 1
                        continue
                    old, new = d0 * MULT[lv - 1] // 100, d1 * MULT[lv - 1] // 100
                    if old != new and drop in (old, new):
                        out['hits'][f'{name}|{era}|{"old" if drop == old else "new"}'] += 1
                b = balloon.get(attacker)
                if b and td - b[0] <= 40:
                    old, new = BALLOON[2] * MULT[b[1] - 1] // 100, BALLOON[3] * MULT[b[1] - 1] // 100
                    if drop in (old, new):
                        out['hits'][f'Skeleton Barrel death|{era}|{"old" if drop == old else "new"}'] += 1
            out['_pending'] = []
    close()
    out['skel'].append((path.replace('\\', '/').rsplit('/', 1)[-1], era, radii))


def main():
    dst = sys.argv[1]
    files = sorted(p for a in sys.argv[2:] for p in (glob.glob(a) or [a]))   # globs expanded here (Windows arg limit)
    out = dict(hits=Counter(), nolevel=Counter(), skel=[], _pending=[])
    for i, p in enumerate(files):
        try:
            scan(p, out)
        except (ValueError, KeyError) as e:
            print('skip', p, e, file=sys.stderr)
        if i % 50 == 0:
            print(i, len(files), file=sys.stderr, flush=True)
    by_era = defaultdict(list)
    for _, era, r in out['skel']:
        by_era[era] += r
    summary = {'files': len(files), 'hits': dict(out['hits']), 'nolevel': dict(out['nolevel'])}
    for era, r in sorted(by_era.items()):
        bins = Counter('<430' if x < 430 else '430-520' if x < 520 else '520-640' if x < 640 else '>=640' for x in r)
        summary[f'skel_{era}'] = dict(n=len(r), median=round(statistics.median(r), 1) if r else None, bins=dict(bins),
                                      exact_577_ring=round(sum(576 <= x <= 580 for x in r) / max(1, len(r)), 3),
                                      top=Counter(round(x) for x in r).most_common(8))
    summary['skel_by_file'] = [(f, era, round(statistics.median(r), 1), len(r)) for f, era, r in out['skel'] if r]
    json.dump(summary, open(dst, 'w', encoding='utf-8'), indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k != 'skel_by_file'}, indent=1))


if __name__ == '__main__':
    main()
