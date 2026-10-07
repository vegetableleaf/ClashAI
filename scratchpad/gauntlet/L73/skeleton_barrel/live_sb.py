"""Live: every bot Log cast around an enemy Skeleton Barrel, timed against balloon death, drop and skeleton spawn.

Read-only over scratchpad/gauntlet/L68/live_reader/live_play_2026*.jsonl. Raw reader frame (millitiles, 20 ticks/s).
Snapshots = `frame` events (2-tick cadence) when the log has them, else the public-audit `decision.public.raw_bodies`
(~10-tick cadence). Log roll start t_rs is measured from the own Log projectile rows in the public audit
(rolling rows: t - |y - y0| / 200); logs without the audit use the confirmed tick + the measured median offset.
Per Log x drop: does the rolling hitbox cross the drop BEFORE the skeletons exist (owner's hypothesis), and which
skeletons vanish when the band reaches them (= hit)?
"""
import glob, json, math, os, statistics, sys
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))
from pipeline.obs_contract import _catalog_names
from common import ROOT, SB_IDS, LOG_ID, BALLOON_MIN_HP, ROLL_MT_PER_TICK, ROLL_RANGE, HALF_W, HALF_D

NAMES = _catalog_names()
LIVE = os.path.join(ROOT, 'scratchpad/gauntlet/L68/live_reader')
TOL = 500            # body radius allowance (millitiles) added to the catalog hitbox
CONF_TO_RS = 7       # measured: median t_rs - confirmed tick over the 77 audited Logs (summary key confirmed_to_roll_start_ticks)
OUT = os.path.join(os.path.dirname(__file__), 'live_results.json')


def raw_of_own(x, y, side):
    return (x * 18000, (1 - y) * 32000) if side == 0 else ((1 - x) * 18000, y * 32000)


def load(path):
    ev = [json.loads(l) for l in open(path) if l.strip()]
    st = ev[0] if ev and ev[0].get('event') == 'start' else {}
    frames = [e for e in ev if e.get('event') == 'frame' and e.get('ents') is not None]
    decs = [e for e in ev if e.get('event') == 'decision' and e.get('public')]
    if frames:
        side = frames[0]['my_side']
        snaps = {e['tick']: [tuple(b[:7]) + (b[7],) for b in e['ents']] for e in frames}
        src = 'frame'
    elif decs:
        side = decs[0]['public']['observer_side']
        snaps = {d['tick']: [(b['side'], b['x'], b['y'], b['card_id'], b['hp'], b['max_hp'], b['kind'],
                              f"{b.get('address')}/{b.get('category')}") for b in d['public']['raw_bodies']]
                 for d in decs}
        src = 'decision'
    else:
        return None
    logrows = {d['tick']: [r for r in d['public']['raw_projectiles'] if r.get('card_id') == LOG_ID and r['side'] == side]
               for d in decs}
    model = {d['tick']: d['public'] for d in decs}
    return dict(ev=ev, start=st, side=side, snaps=snaps, ticks=sorted(snaps), src=src, logrows=logrows, model=model,
                ckpt=os.path.basename(str(st.get('ckpt', '')).replace('\\', '/')), fv=st.get('feature_version'))


def tracks(L):
    """address -> list of (tick, x, y, cid, hp, mhp, kind, side)."""
    tr, seg = defaultdict(list), {}
    for t in L['ticks']:
        for s, x, y, cid, hp, mhp, kind, a in L['snaps'][t]:
            if cid in SB_IDS and s != L['side']:
                # reader addresses are reused: a new body = max_hp change or a > 60-tick gap (decision cadence gaps reach ~35)
                k = seg.get(a)
                if k is None or tr[k][-1][5] != mhp or t - tr[k][-1][0] > 60:
                    k = seg[a] = (a, t)
                tr[k].append((t, x, y, cid, hp, mhp, kind))
    return tr


def next_tick(L, t):
    i = L['ticks'].index(t)
    return L['ticks'][i + 1] if i + 1 < len(L['ticks']) else None


def prev_tick(L, t):
    i = L['ticks'].index(t)
    return L['ticks'][i - 1] if i > 0 else None


def episodes(L):
    tr = tracks(L)
    balloons = {a: o for a, o in tr.items() if o[0][5] >= BALLOON_MIN_HP}
    skels = {a: o for a, o in tr.items() if 0 < o[0][5] < BALLOON_MIN_HP}
    used, out = set(), []
    own_towers = [(b[1], b[2]) for b in L['snaps'][L['ticks'][0]] if b[0] == L['side'] and b[6] in (12, 13)]
    for a, o in sorted(balloons.items(), key=lambda kv: kv[1][0][0]):
        t0, tl = o[0][0], o[-1][0]
        lx, ly = o[-1][1], o[-1][2]
        kids = [(k, s) for k, s in skels.items() if k not in used and tl < s[0][0] <= tl + 60
                and math.hypot(s[0][1] - lx, s[0][2] - ly) <= 4500]
        for k, _ in kids:
            used.add(k)
        own_bld = [(b[1], b[2]) for b in L['snaps'][tl] if b[0] == L['side'] and (b[6] in (12, 13) or b[3] // 1000000 == 27)]
        ep = dict(addr=a, cid=o[0][3], first_seen=t0, last_seen=tl, gone_by=next_tick(L, tl),
                  last_hp=o[-1][4], max_hp=o[-1][5], last_pos=(lx, ly),
                  dist_own_building_tiles=round(min((math.hypot(lx - x, ly - y) for x, y in own_bld or own_towers),
                                                    default=99) / 1000, 2),
                  skeletons=[])
        if kids:
            ts_hi = min(s[0][0] for _, s in kids)
            ep['spawn_hi'] = ts_hi
            ep['spawn_lo'] = prev_tick(L, ts_hi)
            ep['drop_to_spawn_ticks'] = [ep['spawn_lo'] - tl, ts_hi - tl]   # bounds incl. sampling cadence
            for k, s in kids:
                nt = next_tick(L, s[-1][0])
                ep['skeletons'].append(dict(addr=k, first=s[0][0], first_pos=s[0][1:3], last=s[-1][0], died_by=nt,
                                            traj=[(t, x, y) for t, x, y, *_ in s]))
        out.append(ep)
    return out, tr


def roll_start(L, tp):
    """(t_rs, x0, y0) for the own Log decided at tp, from its public projectile rows; None without rows.
    Launch rows target the deploy point (< 4 tiles away); rolling rows target deploy + 10.1 tiles."""
    d = -1 if L['side'] == 1 else 1
    rows = [(u, r) for u in sorted(L['logrows']) if tp < u <= tp + 120 for r in L['logrows'][u]
            if r.get('target_y') is not None]
    if not rows:
        return None
    t1 = rows[0][0]
    rows = [(u, r) for u, r in rows if u <= t1 + 70]           # one Log: ~ 5 launch + 51 rolling ticks
    rolling = [(u, r) for u, r in rows if abs(r['target_y'] - r['y']) > 4000 or
               any(abs(r['target_y'] - q['target_y'] - d * ROLL_RANGE) < 300 for _, q in rows)]
    if not rolling:
        return None
    y0 = rolling[0][1]['target_y'] - d * ROLL_RANGE
    t_rs = statistics.median(u - (r['y'] - y0) * d / ROLL_MT_PER_TICK for u, r in rolling)
    return t_rs, rolling[0][1]['x'], y0, t1


def analyse(path, res):
    L = load(path)
    if L is not None:
        analyse_L(L, os.path.basename(path), res)


def analyse_L(L, name, res):
    side = L['side']
    eps, tr = episodes(L)
    plays = [e for e in L['ev'] if e.get('event') == 'play' and e.get('name') == 'Log']
    confirms = [e for e in L['ev'] if e.get('event') == 'confirmed' and e.get('name') == 'Log']
    for ep in eps:
        res['episodes'].append(dict({k: v for k, v in ep.items() if k != 'skeletons'}, file=name, ckpt=L['ckpt'],
                                    fv=L['fv'], src=L['src'], side=side, n_skel=len(ep['skeletons'])))
    for pl in plays:
        tp = pl['tick']
        conf = next((c['tick'] for c in confirms if tp <= c['tick'] <= tp + 80), None)
        rs = roll_start(L, tp)
        rec = dict(file=name, ckpt=L['ckpt'], fv=L['fv'], src=L['src'], side=side, tick=tp, xy=pl['xy'],
                   p_play=pl.get('p_play'), confirmed=conf)
        x0, y0 = raw_of_own(pl['xy'][0], pl['xy'][1], side)
        d = -1 if side == 1 else 1
        if rs:
            rec.update(t_rs=rs[0], first_row=rs[3])
            x0, y0 = rs[1], rs[2]
            if conf is not None:
                res['conf_to_rs'].append(rs[0] - conf)
            res['tp_to_rs'].append(rs[0] - tp)
        elif conf is not None:
            # no public Log rows: confirmed tick + the measured median offset (7 ticks, n=77), deploy = intended xy
            rec.update(t_rs=conf + CONF_TO_RS, first_row=None, roll_from='confirmed+7')
        rec['x0'], rec['y0'] = x0, y0
        res['all_logs'].append(rec)
        # episodes in play: balloon seen before the Log's roll ends, skeletons (if any) spawned not long before tp
        cands = []
        for ep in eps:
            if not (ep['first_seen'] <= tp <= (ep.get('spawn_hi') or ep['gone_by'] or ep['last_seen']) + 100):
                continue
            r = dict(rec, ep_first=ep['first_seen'], balloon_last=ep['last_seen'], gone_by=ep['gone_by'],
                     spawn_lo=ep.get('spawn_lo'), spawn_hi=ep.get('spawn_hi'), last_hp=ep['last_hp'],
                     max_hp=ep['max_hp'], evo=ep['cid'] == 13000056,
                     dist_own_building_tiles=ep['dist_own_building_tiles'], n_skel=len(ep['skeletons']))
            sh = ep.get('spawn_hi')
            r['phase'] = ('balloon_alive' if tp <= ep['last_seen'] else
                          'drop_pending' if sh is None or tp < sh else 'skeletons_on_ground')
            r['tp_minus_balloon_last'] = tp - ep['last_seen']
            if 't_rs' in r:      # phase when the Log starts rolling: comparable across live (decision+34) and native (+9)
                r['phase_at_rs'] = ('balloon_alive' if r['t_rs'] <= ep['last_seen'] else
                                    'drop_pending' if sh is None or r['t_rs'] < sh else 'skeletons_on_ground')
            # aimed at this drop: drop point inside the roll corridor widened by the 1.48-tile skeleton spawn ring
            bx, by = ep['last_pos']
            al = (by - y0) * d
            r['aimed'] = abs(bx - x0) <= HALF_W + TOL + 1480 and -HALF_D - TOL - 1480 <= al <= ROLL_RANGE + HALF_D
            # other enemy bodies (not this card) inside the corridor at the decision snapshot
            snap = L['snaps'].get(tp) or L['snaps'][min(L['ticks'], key=lambda u: abs(u - tp))]
            r['other_enemy_in_corridor'] = sorted({NAMES.get(b[3], str(b[3])) for b in snap if b[0] != side
                                                   and b[3] not in SB_IDS and b[6] not in (12, 13) and b[3] > 0
                                                   and abs(b[1] - x0) <= HALF_W + TOL
                                                   and -HALF_D - TOL <= (b[2] - y0) * d <= ROLL_RANGE + HALF_D})
            if sh is not None:
                r['tp_minus_spawn_hi'] = tp - sh
            # geometry of the drop vs the Log path
            bx, by = ep['last_pos']
            r['drop_along_tiles'] = round((by - y0) * d / 1000, 2)
            r['drop_dx_tiles'] = round(abs(bx - x0) / 1000, 2)
            if 't_rs' in r:
                t_rs = r['t_rs']
                r['rs_minus_balloon_last'] = t_rs - ep['last_seen']
                if sh is not None:
                    r['rs_minus_spawn_hi'] = t_rs - sh
                r['cross_minus_balloon_last'] = t_rs + max((by - y0) * d, 0) / ROLL_MT_PER_TICK - ep['last_seen']
                along = (by - y0) * d
                if -HALF_D <= along <= ROLL_RANGE + HALF_D:
                    r['t_cross_drop'] = t_rs + max(along, 0) / ROLL_MT_PER_TICK
                    if sh is not None:
                        r['cross_minus_spawn_hi'] = r['t_cross_drop'] - sh
                        r['cross_minus_spawn_lo'] = r['t_cross_drop'] - ep['spawn_lo']
                # per skeleton: position near the band crossing (two fixed-point passes), hit = vanished at crossing
                sk_out = []
                for s in ep['skeletons']:
                    traj = s['traj']
                    def pos(t):
                        best = min(traj, key=lambda q: abs(q[0] - t))
                        return best[1], best[2]
                    px, py = traj[0][1], traj[0][2]
                    tc = None
                    for _ in range(3):
                        al = (py - y0) * d
                        if not (-HALF_D - TOL <= al <= ROLL_RANGE + HALF_D + TOL):
                            tc = None
                            break
                        tc = t_rs + max(al, 0) / ROLL_MT_PER_TICK
                        px, py = pos(tc)
                    al = (py - y0) * d
                    in_lat = abs(px - x0) <= HALF_W + TOL
                    q = dict(first=s['first'], last=s['last'], died_by=s['died_by'],
                             along=round(al / 1000, 2), dx=round(abs(px - x0) / 1000, 2))
                    if tc is None or not in_lat:
                        q['outcome'] = 'outside_path' if tc is not None or not in_lat else 'outside_range'
                        if tc is None:
                            q['outcome'] = 'behind_start' if al < -HALF_D - TOL else 'beyond_range'
                        if tc is not None and not in_lat:
                            q['outcome'] = 'lateral_miss'
                    else:
                        q['t_cross'] = tc
                        if tc < s['first'] - 2:
                            q['outcome'] = 'band_passed_before_spawn'
                        elif s['died_by'] is not None and tc - 12 <= s['last'] <= tc + 12:
                            q['outcome'] = 'killed_at_crossing'
                        elif s['last'] < tc - 12:
                            q['outcome'] = 'dead_before_crossing'
                        else:
                            q['outcome'] = 'survived_crossing'
                    sk_out.append(q)
                r['skeletons'] = sk_out
                r['skel_outcomes'] = dict(Counter(q['outcome'] for q in sk_out))
            # what the model saw at the decision (public audit only)
            p = L['model'].get(tp)
            if p is not None:
                ms = [b for b in p['model_bodies'] if b['side'] == 1 and b['cls'] in (111, 162, 7)]
                r['model_sb_tokens'] = [(b['cls'], round(b['x'], 3), round(b['y'], 3), round(b['hp_frac'] or -1, 3)) for b in ms]
                r['model_enemy_tokens'] = len([b for b in p['model_bodies'] if b['side'] == 1])
            cands.append(r)
        aimed = [r for r in cands if r['aimed']]
        res['pairs_unaimed'] += len(cands) - len(aimed)
        if aimed:
            res['logs'].append(min(aimed, key=lambda r: abs(r.get('t_rs', r['tick'] + 34) - r['balloon_last'])))


def log_outcome(l):
    o = l.get('skel_outcomes')
    if o is None:
        return 'no_roll_data'
    if not o:
        return 'no_skeletons_tracked'
    if o.get('killed_at_crossing'):
        return 'killed>=1'
    if o.get('band_passed_before_spawn'):
        return 'band_passed_before_spawn'
    return 'no_kill_other'


def summarise(res):
    logs, eps = res['logs'], res['episodes']
    q = lambda xs: dict(n=len(xs), median=statistics.median(xs) if xs else None,
                        p10=sorted(xs)[len(xs) // 10] if xs else None, p90=sorted(xs)[9 * len(xs) // 10] if xs else None)
    S = dict(files=res['files'], episodes=len(eps), episodes_with_skeletons=sum(e['n_skel'] > 0 for e in eps),
             episodes_by_ckpt=Counter(e['ckpt'] for e in eps), all_bot_logs_in_these_files=len(res['all_logs']),
             log_episode_pairs_not_aimed=res['pairs_unaimed'], aimed_logs=len(logs),
             decision_to_roll_start_ticks=q(res['tp_to_rs']), confirmed_to_roll_start_ticks=q(res['conf_to_rs']))
    fr = [e for e in eps if e['src'] == 'frame' and e.get('spawn_hi') is not None]
    S['balloon_gone_to_skeletons_seen_ticks_2tick_frames'] = dict(
        n=len(fr), last_seen_to_first_skeleton=dict(Counter(e['spawn_hi'] - e['last_seen'] for e in fr)),
        first_absent_to_first_skeleton=dict(Counter(e['spawn_hi'] - e['gone_by'] for e in fr)))
    S['balloon_end_near_own_building_le2tiles'] = dict(n=len(eps), near=sum(e['dist_own_building_tiles'] <= 2.0 for e in eps))
    tab = defaultdict(Counter)
    for l in logs:
        tab[('R1e' if 'r1e31' in l['ckpt'] else 'other') + '|' + l['phase']][log_outcome(l)] += 1
    S['aimed_logs_phase_x_outcome'] = {k: dict(v) for k, v in sorted(tab.items())}
    tab2 = defaultdict(Counter)
    for l in logs:
        if 'phase_at_rs' in l:
            tab2[('R1e' if 'r1e31' in l['ckpt'] else l['ckpt'] if l['ckpt'] == 'native_pro' else 'other') + '|' + l['phase_at_rs']][log_outcome(l)] += 1
    S['aimed_logs_phase_at_roll_start_x_outcome'] = {k: dict(v) for k, v in sorted(tab2.items())}
    for key in ('rs_minus_balloon_last', 'rs_minus_spawn_hi', 'cross_minus_spawn_hi', 'tp_minus_balloon_last'):
        xs = [l[key] for l in logs if l.get(key) is not None and l.get('spawn_hi') is not None]
        S['q_' + key] = q(xs)
    cs = [l['cross_minus_spawn_hi'] for l in logs if l.get('cross_minus_spawn_hi') is not None]
    S['cross_before_spawn'] = dict(n=len(cs), before=sum(c < 0 for c in cs))
    sk = defaultdict(Counter)
    for l in logs:
        for k, v in (l.get('skel_outcomes') or {}).items():
            sk[l['phase']][k] += v
    S['skeleton_level_outcomes_by_phase'] = {k: dict(v) for k, v in sk.items()}
    # timing vs outcome, balloon-alive aimed Logs with roll data
    rows = [l for l in logs if l['phase'] == 'balloon_alive' and l.get('skel_outcomes')]
    S['balloon_alive_timing'] = [dict(file=l['file'][10:25], ckpt=l['ckpt'][:14], src=l['src'],
                                      decision_minus_balloon_last=l['tp_minus_balloon_last'],
                                      cross_minus_balloon_last=round(l.get('cross_minus_balloon_last', float('nan')), 1),
                                      cross_minus_spawn=None if l.get('cross_minus_spawn_hi') is None else round(l['cross_minus_spawn_hi'], 1),
                                      balloon_hp_at_last=f"{l['last_hp']}/{l['max_hp']}", outcome=log_outcome(l),
                                      skel=l['skel_outcomes']) for l in sorted(rows, key=lambda l: l['tp_minus_balloon_last'])]
    cr = [l for l in logs if l.get('cross_minus_spawn_hi') is not None and l.get('skel_outcomes')]
    S['hit_vs_cross_sign'] = {s: dict(Counter(log_outcome(l) for l in cr if (l['cross_minus_spawn_hi'] >= 0) == (s == 'after_spawn')))
                              for s in ('after_spawn', 'before_spawn')}
    return S


def main():
    files = []
    for f in sorted(glob.glob(os.path.join(LIVE, 'live_play_2026*.jsonl'))):
        s = open(f).read()
        if '26000056' in s or '13000056' in s:
            files.append(f)
    res = dict(files=len(files), pairs_unaimed=0, episodes=[], logs=[], all_logs=[], tp_to_rs=[], conf_to_rs=[])
    for f in files:
        analyse(f, res)
    S = summarise(res)
    json.dump(dict(summary=S, logs=res['logs'], episodes=res['episodes']), open(OUT, 'w'), indent=1, default=str)
    print(json.dumps(S, indent=1, default=str))


if __name__ == '__main__':
    main()
