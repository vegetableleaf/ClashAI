"""Replay check: DropTracker over the live 2-tick frame logs the Skeleton Barrel audit used (live_sb.py: every
live_play_2026*.jsonl of the MAIN checkout that mentions a Skeleton Barrel and carries `frame` events).

Per predicted drop (balloon vanished from the observed board): predicted skeleton appearance tick T + 12 vs the first
frame with new barrel-skeleton bodies near the drop point; predicted ring vs the real children's first-seen positions;
predicted hp vs real. Also false positives (a drop with no children) and misses (children groups with no drop).
Read-only. Usage: replay_check.py [--out replay_check.json]
"""
import glob, json, math, os, statistics, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import common                                                    # noqa: E402  (4 threads, below-normal priority)
sys.path.insert(0, common.ROOT)
from pipeline import extrapolate as X                            # noqa: E402

MAIN = r'C:\Users\benpe\ClashBot'
LIVE = os.path.join(MAIN, 'scratchpad', 'gauntlet', 'L68', 'live_reader')
OUT = os.path.join(HERE, 'replay_check.json')


def ents_of(row):
    return [dict(side=b[0], x=b[1], y=b[2], card_id=b[3], hp=b[4], max_hp=b[5], kind=b[6], address=b[7]) for b in row]


def load(path):
    out, side = [], None
    for line in open(path, encoding='utf-8'):
        if '"event": "frame"' not in line[:30]:
            continue
        e = json.loads(line)
        if e.get('ents') is None:
            continue
        side = e['my_side']
        out.append((int(e['tick']), ents_of(e['ents'])))
    return side, out


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else None


def check(path, res):
    side, frames = load(path)
    if not frames:
        return
    tr = X.DropTracker()
    events = []
    for i, (tick, ents) in enumerate(frames):
        obs = dict(game_tick=tick, entities=ents)
        tr.observe(obs, side)
        for d in tr.pending:
            if '_seen' not in d:
                d['_seen'] = True
                events.append(dict(d, frame_i=i))
    name = os.path.basename(path)
    ticks = [t for t, _ in frames]
    fresh_by_frame = []              # per frame: new barrel-skeleton bodies vs the previous frame
    for i, (tick, ents) in enumerate(frames):
        before = {e['address'] for e in frames[i - 1][1]} if i else set()
        fresh_by_frame.append([e for e in ents if e['address'] not in before and X._is_sb(e) and not X._is_balloon(e)])
    explained = set()
    for ev in events:
        t0, x, y, par = ev['t0'], ev['x'], ev['y'], ev['parent']
        kid, ta = [], None
        for j in range(ev['frame_i'], len(frames)):
            tj = frames[j][0]
            if tj > t0 + 60:
                break
            near = [e for e in fresh_by_frame[j] if e['side'] == par['side'] and math.hypot(e['x'] - x, e['y'] - y) <= 4500]
            if near and tj > t0:
                ta = tj
                kid, jj = near, j
                for jj in range(j + 1, len(frames)):          # children trickle in over a few frames
                    if frames[jj][0] > ta + 4:
                        break
                    kid = kid + [e for e in fresh_by_frame[jj] if e['side'] == par['side'] and math.hypot(e['x'] - x, e['y'] - y) <= 4500]
                explained.update(range(j, jj + 1))
                break
        gone_back = any(X._sig(e) == X._sig(par) for _, ents in frames[ev['frame_i']:ev['frame_i'] + 6]
                        for e in ents if X._eid(e) == X._eid(par))
        r = dict(file=name, t0=t0, x=x, y=y, max_hp=par['max_hp'], cid=par['card_id'], predicted_tick=t0 + X.DROP_DELAY,
                 balloon_reappeared=gone_back)
        if ta is None:
            r['status'] = 'no_children'
        else:
            pred = X.predicted_children(dict(ev, parent=par), max(ta - (t0 + X.DROP_DELAY), 0))
            cx, cy = sum(e['x'] for e in kid) / len(kid), sum(e['y'] for e in kid) / len(kid)
            near_pred = [min(math.hypot(e['x'] - p['x'], e['y'] - p['y']) for p in pred) for e in kid]
            r.update(status='ok', actual_tick=ta, tick_error=ta - (t0 + X.DROP_DELAY), n_children=len(kid),
                     centroid_err=math.hypot(cx - x, cy - y),
                     mean_radius=statistics.mean(math.hypot(e['x'] - x, e['y'] - y) for e in kid),
                     child_to_nearest_pred=statistics.mean(near_pred), max_child_to_nearest_pred=max(near_pred),
                     pred_hp=pred[0]['max_hp'], pred_kind=pred[0]['kind'], pred_radius=math.hypot(pred[0]['x'] - x, pred[0]['y'] - y), actual_hp=Counter(e['max_hp'] for e in kid).most_common(1)[0][0],
                     kinds=dict(Counter(e['kind'] for e in kid)))
        res['events'].append(r)
    # misses: groups of >= 4 fresh children in one frame with no drop event in t0 .. t0 + 60 within 4.5 tiles
    for j, fr in enumerate(fresh_by_frame):
        if len(fr) >= 4 and j not in explained:
            tj = frames[j][0]
            cx, cy = sum(e['x'] for e in fr) / len(fr), sum(e['y'] for e in fr) / len(fr)
            near_ev = any(ev['t0'] < tj <= ev['t0'] + 60 and math.hypot(ev['x'] - cx, ev['y'] - cy) <= 4500 for ev in events)
            balloon_present = any(X._is_balloon(e) and e['side'] == fr[0]['side'] and math.hypot(e['x'] - cx, e['y'] - cy) <= 4500
                                  for e in frames[j][1])
            res['child_groups'].append(dict(file=name, tick=tj, n=len(fr), side=fr[0]['side'], my_side=side,
                                            covered_by_event=near_ev, balloon_body_still_on_board=balloon_present))
    res['files'] += 1


def main():
    res = dict(files=0, events=[], child_groups=[])
    for f in sorted(glob.glob(os.path.join(LIVE, 'live_play_2026*.jsonl'))):
        s = open(f, encoding='utf-8').read()
        if ('26000056' in s or '13000056' in s) and '"event": "frame"' in s:
            check(f, res)
    ev = res['events']
    ok = [e for e in ev if e['status'] == 'ok']
    S = dict(files=res['files'], drops_predicted=len(ev), with_children=len(ok), no_children=sum(e['status'] == 'no_children' for e in ev),
             balloon_reappeared_within_5_frames=sum(e['balloon_reappeared'] for e in ev))
    te = [e['tick_error'] for e in ok]
    S['tick_error (actual first-seen tick - (T+12))'] = dict(hist=dict(sorted(Counter(te).items())), median=statistics.median(te) if te else None,
                                                             exact=sum(t == 0 for t in te), within_2=sum(abs(t) <= 2 for t in te), n=len(te))
    for k in ('centroid_err', 'mean_radius', 'child_to_nearest_pred', 'max_child_to_nearest_pred'):
        xs = [e[k] for e in ok]
        S[k + '_millitiles'] = dict(n=len(xs), median=round(statistics.median(xs)), p10=round(pct(xs, .1)), p90=round(pct(xs, .9)), max=round(max(xs))) if xs else None
    exact = [e for e in ok if e['tick_error'] == 0]
    for k in ('centroid_err', 'child_to_nearest_pred'):
        xs = [e[k] for e in exact]
        S['tick_exact_only_' + k] = dict(n=len(xs), median=round(statistics.median(xs)), p90=round(pct(xs, .9))) if xs else None
    rr = [abs(e['mean_radius'] - e['pred_radius']) for e in ok]
    S['abs(mean actual radius - predicted radius)_millitiles'] = dict(median=round(statistics.median(rr)), p90=round(pct(rr, .9)))
    S['kind_match'] = dict(match=sum(e['kinds'] == {e['pred_kind']: e['n_children']} for e in ok), n=len(ok))
    S['n_children'] = dict(Counter(e['n_children'] for e in ok))
    S['hp_match'] = dict(match=sum(e['pred_hp'] == e['actual_hp'] for e in ok), n=len(ok),
                         mismatches=[(e['max_hp'], e['pred_hp'], e['actual_hp']) for e in ok if e['pred_hp'] != e['actual_hp']])
    S['first_seen_kinds'] = dict(sum((Counter(e['kinds']) for e in ok), Counter()))
    enemy = [g for g in res['child_groups'] if g['side'] != g['my_side']]
    S['enemy child groups with no predicted drop (misses)'] = dict(
        n=len(enemy), balloon_body_still_on_board_when_they_appeared=sum(g['balloon_body_still_on_board'] for g in enemy))
    S['recall: enemy drops predicted / (predicted with children + misses)'] = f"{len(ok)} / {len(ok) + len(enemy)}"
    json.dump(dict(summary=S, events=ev, child_groups=res['child_groups']), open(OUT, 'w'), indent=1, default=str)
    print(json.dumps(S, indent=1, default=str))


if __name__ == '__main__':
    main()
