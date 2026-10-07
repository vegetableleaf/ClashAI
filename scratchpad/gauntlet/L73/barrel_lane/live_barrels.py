"""Live Goblin Barrel perception vs landing, and the bot's Logs (read-only over live public audits).

Inputs: every R1e (rseries_r1e31_u0155, feature_version 4, public_audit) live log of Oct 4-6.
Coordinates: raw = reader millitiles. own = model frame, exactly projectile_observation._xy:
  side 0 -> (x/18000, 1 - y/32000); side 1 -> (1 - x/18000, y/32000).
Play/decision xy are own frame (verified: play.xy == decision.xy at the same tick, 1594/1594).
Screen x = 1 - own x on both sides (live_play.py Layout.board), so 'own left' is the player's screen RIGHT.
Lane = own x < 0.5 -> 'L' else 'R' (own frame). Ground truth landing = centroid of the first NEW enemy
barrel goblins (body card_id == barrel card id) seen after the flight's last sighting.
"""
import glob, json, math, os, sys
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
BARREL = {28000004, 13000081}
LOG = 28000011
GB_GID, LOG_GID = 42, 111          # gid in the public audit rows (vocab index; the 285 matched rows confirm)
# default = the live R1e; --fv7 re-runs the same instrument on the tower_spatial_v7 candidate logs (comparison only)
FV, CKPT, OUT = (7, 'tower_spatial_v7', 'live_results_fv7.json') if '--fv7' in sys.argv else (4, 'rseries_r1e31_u0155', 'live_results.json')


def own(x, y, side):
    x, y = x / 18000, y / 32000
    return (x, 1 - y) if side == 0 else (1 - x, y)


def lane(ox):
    return 'L' if ox < .5 else 'R'


def r1e_logs():
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'scratchpad/gauntlet/L68/live_reader/live_play_2026100[456]_*.jsonl'))):
        with open(f) as fh:
            s = json.loads(fh.readline())
        if s.get('event') == 'start' and s.get('feature_version') == FV and s.get('public_audit') \
                and CKPT in s.get('ckpt', ''):
            out.append(f)
    return out


def analyse(path, res):
    ev = [json.loads(l) for l in open(path)]
    dec = [d for d in ev if d.get('event') == 'decision' and d.get('public')]
    if not dec:
        return
    side = dec[0]['public']['observer_side']
    name = os.path.basename(path)
    seen_bodies = set()
    # ---- flights tracked per target key (side, target_x, target_y); absence from one audit ends a flight
    active, flights = {}, []
    for i, d in enumerate(dec):
        p = d['public']
        rows = [r for r in p['raw_projectiles'] if r.get('card_id') in BARREL and r['side'] != side]
        for r in p['raw_projectiles']:
            if r.get('card_id') in BARREL:
                res['target_field'][('missing' if r.get('target_x') is None else
                                     'zero' if (r.get('target_x'), r.get('target_y')) == (0, 0) else 'present')] += 1
        keys = Counter((r.get('target_x'), r.get('target_y')) for r in rows)
        for k, fl in list(active.items()):
            if k not in keys:
                fl['end_i'] = i            # first audit without this barrel
                flights.append(active.pop(k))
        for r in rows:
            k = (r.get('target_x'), r.get('target_y'))
            fl = active.get(k)
            if fl is None:
                fl = active[k] = dict(obs=[], same_target_dup=False, concurrent=0)
            if fl['obs'] and fl['obs'][-1][0] == d['tick']:
                fl['same_target_dup'] = True   # two barrels to one target in one frame
                continue
            fl['obs'].append((d['tick'], r, i))
            fl['concurrent'] = max(fl['concurrent'], len(keys))
        # model rows for every enemy barrel sighting: model target vs transformed raw target
        m_all = [v for v in p['model_projectiles'] if int(v[0]) == GB_GID and int(v[1]) == 1]
        n_all = [v for v in p['normalized_current_projectiles'] if int(v[0]) == GB_GID and int(v[1]) == 1]
        if len(m_all) != len(rows):
            res['model_rows_missing'] += abs(len(m_all)-len(rows))
        for r in rows:
            if r.get('target_x') is None:
                continue
            tx, ty = own(r['target_x'], r['target_y'], side)
            cx, cy = own(r['x'], r['y'], side)
            res['model_rows'] += 1
            m = min(m_all, key=lambda v: abs(v[4]-tx)+abs(v[5]-ty), default=None)
            n = min(n_all, key=lambda v: abs(v[2]-cx)+abs(v[3]-cy)+abs(v[4]-tx)+abs(v[5]-ty), default=None)
            if m is None:
                continue
            res['model_target_err_max'] = max(res['model_target_err_max'], abs(m[4]-tx), abs(m[5]-ty))
            if n is not None:
                res['norm_pos_err_max'] = max(res['norm_pos_err_max'], abs(n[2]-cx), abs(n[3]-cy))
            if len(rows) == 1:   # look-ahead geometry only on unambiguous frames
                mx, my = m[2], m[3]
                seg = (tx-cx, ty-cy); L2 = seg[0]**2+seg[1]**2
                t = ((mx-cx)*seg[0]+(my-cy)*seg[1])/L2 if L2 else 1.0
                off = abs((mx-cx)*seg[1]-(my-cy)*seg[0])/math.sqrt(L2) if L2 else 0
                res['lookahead_t'].append(t); res['lookahead_offline_max'] = max(res['lookahead_offline_max'], off)
            res['model_tti_known'][int(m[7])] += 1
            res['model_lane_eq_raw_target_lane'][lane(m[4]) == lane(tx)] += 1
    for fl in active.values():
        fl['end_i'] = len(dec)
        flights.append(fl)

    # ---- ground truth: new enemy barrel goblins in the first audit (<= 60 ticks) after a flight ends; each
    # goblin is assigned to the nearest target among flights ending at that audit (two barrels split cleanly)
    body_first = {}
    for i, d in enumerate(dec):
        for b in d['public']['raw_bodies']:
            body_first.setdefault((b.get('address'), b.get('category')), i)
    ending = defaultdict(list)
    for fl in flights:
        ending[fl['end_i']].append(fl)
    out = []
    for end_i, group in ending.items():
        assign = defaultdict(list)
        land_tick = None
        last = max(f['obs'][-1][0] for f in group)
        for j in range(end_i, min(end_i+5, len(dec))):
            d = dec[j]
            if d['tick'] - last > 60:
                break
            new = [b for b in d['public']['raw_bodies'] if b.get('card_id') in BARREL and b['side'] != side
                   and body_first[(b.get('address'), b.get('category'))] == j]
            if new:
                land_tick = d['tick']
                for b in new:
                    fl = min(group, key=lambda f: math.hypot(b['x']-(f['obs'][-1][1].get('target_x') or 0),
                                                             b['y']-(f['obs'][-1][1].get('target_y') or 0)))
                    assign[id(fl)].append(b)
                break
        for fl in group:
            t0, r0, i0 = fl['obs'][0]
            t1, r1, i1 = fl['obs'][-1]
            rec = dict(file=name, side=side, first_tick=t0, last_tick=t1, n_obs=len(fl['obs']),
                       concurrent_targets=fl['concurrent'], same_target_dup=fl['same_target_dup'],
                       target_raw=(r1.get('target_x'), r1.get('target_y')), first_pos_raw=(r0['x'], r0['y']))
            new = assign.get(id(fl))
            rec['landing'] = None if not new else dict(
                tick=land_tick, n=len(new), kinds=sorted({b['kind'] for b in new}),
                centroid=(sum(b['x'] for b in new)/len(new), sum(b['y'] for b in new)/len(new)))
            tx, ty = rec['target_raw']
            if new and tx is not None:
                cx, cy = rec['landing']['centroid']
                rec['target_err_tiles'] = math.hypot(cx-tx, cy-ty)/1000
                rec['target_lane_own'] = lane(own(tx, ty, side)[0])
                rec['landing_lane_own'] = lane(own(cx, cy, side)[0])
                rec['lane_agree'] = rec['target_lane_own'] == rec['landing_lane_own']
                rec['target_center'] = abs(tx-9000) < 1500
            out.append(rec)
    out.sort(key=lambda r: r['first_tick'])
    res['flights'] += out

    # ---- Logs
    plays = [d for d in ev if d.get('event') == 'play' and d.get('name') == 'Log']
    by_tick = {d['tick']: (i, d) for i, d in enumerate(dec)}
    for pl in plays:
        if pl['tick'] not in by_tick:
            res['log_no_audit'] += 1
            continue
        i, d = by_tick[pl['tick']]
        p = d['public']
        lx, ly = pl['xy']
        enemy_barrels = [r for r in p['raw_projectiles'] if r.get('card_id') in BARREL and r['side'] != side]
        gob = [b for b in p['raw_bodies'] if b.get('card_id') in BARREL and b['side'] != side and b['hp'] > 0]
        rec = dict(file=name, side=side, tick=pl['tick'], xy=pl['xy'], log_lane=lane(lx))
        # executed Log: own-side Log projectile in the next audits
        for j in range(i+1, min(i+8, len(dec))):
            logs = [r for r in dec[j]['public']['raw_projectiles'] if r.get('card_id') == LOG and r['side'] == side]
            if logs:
                ex = own(logs[0]['x'], logs[0]['y'], side)
                rec['executed_own_x'] = ex[0]
                rec['exec_err_x_tiles'] = abs(ex[0]-lx)*18
                break
        if enemy_barrels:
            rec['context'] = 'in_flight'
            lanes = {lane(own(r['target_x'], r['target_y'], side)[0]) for r in enemy_barrels if r.get('target_x') is not None}
            rec['n_barrels'] = len(enemy_barrels)
            rec['two_lanes'] = len(lanes) > 1
            # pair the Log with the barrel whose target is laterally closest (most charitable pairing)
            r = min(enemy_barrels, key=lambda r: abs(own(r.get('target_x') or 0, 0, side)[0]-lx))
            fl = next((f for f in out if f['first_tick'] <= pl['tick'] <= f['last_tick']
                       and tuple(f['target_raw']) == (r.get('target_x'), r.get('target_y'))), None)
            rec['target_known'] = r.get('target_x') is not None and (r.get('target_x'), r.get('target_y')) != (0, 0)
            if rec['target_known']:
                tx, ty = own(r['target_x'], r['target_y'], side)
                rec['target_own'] = (tx, ty)
                rec['lane_vs_target'] = lane(tx) == lane(lx)
                rec['target_center'] = abs(r['target_x']-9000) < 1500
                rec['dx_target_tiles'] = abs(tx-lx)*18
                cx, cy = own(r['x'], r['y'], side)
                rec['remaining_tiles'] = math.hypot((tx-cx)*18, (ty-cy)*32)
                m = [v for v in p['model_projectiles'] if int(v[0]) == GB_GID and int(v[1]) == 1]
                if m:
                    rec['model_target_own'] = m[0][4:6]
                    rec['model_pos_own'] = m[0][2:4]
                    rec['model_tti_s'] = m[0][6] if m[0][7] else None
            if fl:
                rec['flight_first_tick'] = fl['first_tick']
                if fl.get('landing'):
                    L = fl['landing']
                    span = L['tick'] - fl['first_tick']
                    rec['stage'] = (pl['tick'] - fl['first_tick'])/span if span > 0 else None
                    gx, gy = own(*L['centroid'], side)
                    rec['landing_own'] = (gx, gy)
                    rec['lane_vs_landing'] = lane(gx) == lane(lx)
                    rec['dx_landing_tiles'] = abs(gx-lx)*18
                    # Log rolls ~10.1 tiles toward the enemy (decreasing own y): does its path cover the landing y?
                    rec['landing_in_roll_y'] = (ly - 10.5/32) <= gy <= ly + 1/32
                    rec['would_hit'] = rec['dx_landing_tiles'] <= 2.5 and rec['landing_in_roll_y']
        elif gob:
            rec['context'] = 'goblins_on_ground'
            gx = sum(b['x'] for b in gob)/len(gob); gy = sum(b['y'] for b in gob)/len(gob)
            ox, oy = own(gx, gy, side)
            rec['goblins_own'] = (ox, oy)
            rec['n_goblins'] = len(gob)
            rec['lane_vs_goblins'] = lane(ox) == lane(lx)
            # nearest goblin lateral distance
            rec['dx_nearest_goblin_tiles'] = min(abs(own(b['x'], b['y'], side)[0]-lx)*18 for b in gob)
        else:
            rec['context'] = 'other'
        # confirmation
        nxt = next((e for e in ev if e.get('event') in ('confirmed', 'unconfirmed') and e.get('name') == 'Log'
                    and e['tick'] >= pl['tick']), None)
        rec['confirmed'] = bool(nxt and nxt['event'] == 'confirmed')
        res['logs'].append(rec)


def rate(xs):
    xs = list(xs)
    return dict(n=len(xs), true=sum(bool(x) for x in xs), rate=round(sum(bool(x) for x in xs)/len(xs), 3) if xs else None)


def main():
    res = dict(flights=[], logs=[], target_field=Counter(), model_rows=0, model_rows_missing=0, model_target_err_max=0.,
               norm_pos_err_max=0., lookahead_t=[], lookahead_offline_max=0., model_tti_known=Counter(),
               model_lane_eq_raw_target_lane=Counter(), log_no_audit=0)
    files = r1e_logs()
    for f in files:
        analyse(f, res)
    fl = res['flights']
    matched = [f for f in fl if f.get('landing') and f['target_raw'][0] is not None]
    summ = dict(files=len(files), flights=len(fl), flights_with_concurrent_targets=sum(f['concurrent_targets'] > 1 for f in fl),
                same_target_duplicates=sum(f['same_target_dup'] for f in fl),
                flights_by_side=Counter(f['side'] for f in fl),
                target_field=dict(res['target_field']),
                matched_landing=len(matched),
                landing_lane_agree=rate(f['lane_agree'] for f in matched),
                landing_lane_agree_noncenter=rate(f['lane_agree'] for f in matched if not f['target_center']),
                landing_lane_agree_by_side={s: rate(f['lane_agree'] for f in matched if f['side'] == s) for s in (0, 1)},
                target_err_tiles=sorted(round(f['target_err_tiles'], 3) for f in matched),
                center_targets=sum(f['target_center'] for f in matched),
                model_rows=res['model_rows'], model_rows_missing=res['model_rows_missing'],
                model_target_vs_raw_transform_max_abs=res['model_target_err_max'],
                normalized_pos_vs_raw_transform_max_abs=res['norm_pos_err_max'],
                model_lane_eq_raw_target_lane=dict(res['model_lane_eq_raw_target_lane']),
                lookahead_fraction_along_segment=dict(min=min(res['lookahead_t'], default=None),
                                                      max=max(res['lookahead_t'], default=None),
                                                      median=sorted(res['lookahead_t'])[len(res['lookahead_t'])//2] if res['lookahead_t'] else None),
                lookahead_perpendicular_offset_max=res['lookahead_offline_max'],
                model_tti_known=dict(res['model_tti_known']))
    logs = res['logs']
    L = dict(total=len(logs), no_audit=res['log_no_audit'], by_context=Counter(l['context'] for l in logs),
             executed_found=sum('exec_err_x_tiles' in l for l in logs),
             exec_err_x_tiles_max=max((l['exec_err_x_tiles'] for l in logs if 'exec_err_x_tiles' in l), default=None),
             exec_lane_matches_intent=rate(lane(l['executed_own_x']) == l['log_lane'] for l in logs if 'executed_own_x' in l))
    fly = [l for l in logs if l['context'] == 'in_flight']
    known = [l for l in fly if l.get('target_known')]
    L['in_flight'] = dict(n=len(fly), target_known=len(known),
                          lane_vs_target=rate(l['lane_vs_target'] for l in known),
                          lane_vs_target_noncenter=rate(l['lane_vs_target'] for l in known if not l['target_center']),
                          lane_vs_target_by_side={s: rate(l['lane_vs_target'] for l in known if l['side'] == s and not l['target_center']) for s in (0, 1)},
                          lane_vs_landing=rate(l['lane_vs_landing'] for l in fly if 'lane_vs_landing' in l),
                          lane_vs_landing_by_side={s: rate(l['lane_vs_landing'] for l in fly if 'lane_vs_landing' in l and l['side'] == s) for s in (0, 1)},
                          would_hit=rate(l['would_hit'] for l in fly if 'would_hit' in l),
                          by_stage={k: rate(l['lane_vs_target'] for l in known if not l['target_center'] and l.get('stage') is not None and lo <= l['stage'] < hi)
                                    for k, lo, hi in (('early<0.33', -1, .33), ('mid', .33, .66), ('late>=0.66', .66, 9))},
                          by_remaining_tiles={k: rate(l['lane_vs_target'] for l in known if not l['target_center'] and lo <= l['remaining_tiles'] < hi)
                                              for k, lo, hi in (('>15', 15, 99), ('8-15', 8, 15), ('<8', 0, 8))},
                          dx_target_tiles_wrong=sorted(round(l['dx_target_tiles'], 1) for l in known if not l['lane_vs_target']),
                          two_lane_barrels=sum(l.get('two_lanes', False) for l in fly),
                          confirmed=rate(l['confirmed'] for l in fly))
    gnd = [l for l in logs if l['context'] == 'goblins_on_ground']
    L['goblins_on_ground'] = dict(n=len(gnd), lane_vs_goblins=rate(l['lane_vs_goblins'] for l in gnd),
                                  by_side={s: rate(l['lane_vs_goblins'] for l in gnd if l['side'] == s) for s in (0, 1)},
                                  dx_nearest_goblin_tiles=sorted(round(l['dx_nearest_goblin_tiles'], 1) for l in gnd))
    summ['logs'] = L
    out = os.path.join(os.path.dirname(__file__), OUT)
    json.dump(dict(summary=summ, flights=fl, logs=logs), open(out, 'w'), indent=1, default=str)
    print(json.dumps(summ, indent=1, default=str))


if __name__ == '__main__':
    main()
