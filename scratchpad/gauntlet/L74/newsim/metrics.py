"""Measurements from SIM public telemetry only; never policy inputs or rewards.

Uses phase_stats' phase boundaries, tank set, coordinate/lane definitions and
crossing -> same-lane/central Tesla response rule. Unlike decision snapshots,
SIM telemetry has per-tick frames. Records retain missing phases and censored
crossings; post-6000 tiebreak HP drain is excluded.
"""
from collections import defaultdict
from statistics import mean

from pipeline import vocab
from scratchpad.gauntlet.L74.phase_stats import video_metrics as V


def measure(frames, plays, side):
    frames = sorted((f for f in frames if 0 <= f['tick'] < 6000), key=lambda f: f['tick'])
    if not frames:
        return dict(available=False, missing='No public frame history in eval record')
    def hp(f, team):
        return sum(max(0, t['hp']) for t in f['towers'] if t['side'] == team)
    phases = {}
    for name, lo, hi in zip(V.PHASES, V.BOUNDS, V.BOUNDS[1:]):
        before = [f for f in frames if f['tick'] <= lo]
        during = [f for f in frames if lo <= f['tick'] < hi]
        if not before or not during:
            phases[name] = None
            continue
        a, b = before[-1], during[-1]
        start = hp(a, side) - hp(a, 1-side)
        end = hp(b, side) - hp(b, 1-side)
        phases[name] = dict(start_tick=a['tick'], end_tick=b['tick'], net_hp_start=start,
                            net_hp_end=end, net_damage=end-start)
    buildings = {V.canonical(vocab.base_key(n)) for n in vocab.BUILDING_CLASSES}
    def own(e):
        return dict(e, name=V.canonical(e.get('card') or ''),
                    x=e['x']/1000 if side == 1 else 18-e['x']/1000,
                    y=e['y']/1000 if side == 1 else 32-e['y']/1000)
    boards = [[own(e) for e in f['bodies'] if e['hp'] > 0] for f in frames]
    deployments = [own(p) for p in plays if p['side'] == side and p.get('accepted')
                   and not p.get('ability') and V.canonical(p['card']) == 'tesla']
    segments = defaultdict(list)
    for i, board in enumerate(boards):
        for e in board:
            if e['id'] is not None and e['side'] != side and e['name'] in V.TANKS:
                segments[(e['side'], e['id'])].append((i, e))
    events = []
    for ident, rows in segments.items():
        crossing = next(((a, b) for a, b in zip(rows, rows[1:]) if a[1]['y'] < 16 <= b[1]['y']
                         and 0 < frames[b[0]]['tick']-frames[a[0]]['tick'] <= 60), None)
        if crossing is None:
            continue
        (prev, _), (i, tank) = crossing
        tick, lane = frames[i]['tick'], V.lane(tank['x'])
        quiet, complete, finish = None, False, frames[-1]['tick']
        for j in range(i, len(frames)):
            t = frames[j]['tick']
            if j > i and t - frames[j-1]['tick'] > 40:
                finish = frames[j-1]['tick']
                break
            threat = any(e['side'] != side and e['name'] not in buildings and e['y'] >= 16
                         and V.lane(e['x']) == lane for e in boards[j])
            quiet = None if threat else t if quiet is None else quiet
            if quiet is not None and t-quiet >= 60:
                finish, complete = t, True
                break
        matching = lambda e: V.lane(e['x']) == lane or abs(e['x']-9) <= 2
        tesla = next((p for p in sorted(deployments, key=lambda p: p['tick'])
                      if tick <= p['tick'] <= finish and p['y'] >= 16 and matching(p)), None)
        events.append(dict(tank=tank['name'], entity_id=ident[1], crossing_tick=tick,
                           previous_tick=frames[prev]['tick'], end_tick=finish, complete=complete,
                           preexisting_tesla=any(e['side'] == side and e['name'] == 'tesla' and matching(e)
                                                for e in boards[prev]),
                           tesla_tick=tesla['tick'] if tesla else None,
                           delay_s=(tesla['tick']-tick)/20 if tesla else None))
    return dict(available=True, phases=phases, tank_crossings=events)


def table(rows):
    observations = [r.get('phase_stats', {}) for r in rows]
    present = [r for r in observations if r.get('available')]
    lines = [f'Public phase records: {len(present)}/{len(rows)} games (no tiebreak drain).']
    if len(present) != len(rows):
        lines.append('Missing public frame history: phase HP and crossing delay cannot be recovered from final tower HP/own plays alone.')
    for phase in V.PHASES:
        points = [p['phases'][phase] for p in present if p['phases'][phase] is not None]
        if points:
            lines.append(f"{phase}: n={len(points)}, mean end net tower HP={mean(p['net_hp_end'] for p in points):+.1f}, "
                         f"mean phase net damage={mean(p['net_damage'] for p in points):+.1f}")
        else:
            lines.append(f'{phase}: unavailable (0 observed games)')
    events = [e for p in present for e in p['tank_crossings']]
    delays = [e['delay_s'] for e in events if e['delay_s'] is not None]
    lines.append(f"Tank crossings={len(events)}, Tesla responses={len(delays)}, "
                 f"preexisting Tesla={sum(e['preexisting_tesla'] for e in events)}, "
                 f"censored={sum(not e['complete'] for e in events)}, "
                 f"mean response delay seconds={mean(delays) if delays else 'unavailable'}")
    return '\n'.join(lines)
