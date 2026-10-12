"""Public-observation video-note proxies. Standard library, CPU, offline only.

No simulator, runtime imports or hidden opponent fields. Events retain exclusions
and censoring; aggregation uses independent match/replay clusters.
"""
import bisect
import collections
import math
import re
from pathlib import Path

PHASES = ('1x', '2x', '3x')
BOUNDS = (0, 2400, 4800, 6000)
ICEBOW = {'xbow', 'tesla', 'knight', 'icewizard', 'skeletons', 'log', 'tornado', 'rocket'}
TANKS = {'giant', 'golem', 'royalgiant', 'electrogiant', 'goblingiant', 'pekka',
         'lavahound', 'hogrider', 'ramrider', 'battleram', 'balloon', 'megaknight'}
# Public catalog's internal names differ from the census's API card labels.
ALIASES = {'thelog': 'log', 'hog': 'hogrider', 'ram': 'battleram',
           'darkwitch': 'nightwitch', 'zapmachine': 'sparky', 'giantbuffer': 'runegiant',
           'skeletonballoon': 'skeletonbarrel', 'dartbarrell': 'flyingmachine'}
AIR = {'lavahound', 'lavapups', 'balloon', 'babydragon', 'electrodragon', 'infernodragon',
       'skeletondragons', 'minion', 'minions', 'minionhorde', 'bat', 'bats',
       'flyingmachine', 'megaminion', 'skeletonbarrel', 'phoenix', 'superlavahound',
       'mergemaidenmounted'}


def canonical(s):
    s = re.sub('[^a-z0-9]', '', s.lower())
    return ALIASES.get(s, s)


def phase(t):
    return PHASES[0 if t < 2400 else 1 if t < 4800 else 2] if 0 <= t < 6000 else None


def lane(x):
    return 'left' if x < 9 else 'right'


def archetype_order(root):
    # Read only the literal ARCH assignment. Never import/execute census.py.
    import ast
    path = Path(root) / 'scratchpad/gauntlet/L74/crapi/census.py'
    tree = ast.parse(path.read_text(encoding='utf8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'ARCH' for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError('census ARCH mapping missing')


def archetype(cards, order):
    cards = {canonical(c) for c in cards}
    return next((a for a in order if canonical(a) in cards), 'Other')


def covered(ts, a, b, max_gap=40):
    """Require both endpoints within 2s and no internal decision gaps >2s."""
    if not ts or a < ts[0] or b > min(ts[-1], 5999):
        return False
    i = max(0, bisect.bisect_right(ts, a)-1)
    j = bisect.bisect_left(ts, b)
    return j < len(ts) and all(0 < y-x <= max_gap for x, y in zip(ts[i:j], ts[i+1:j+1]))


def state_label(hp):
    delta = sum(v for k, v in hp.items() if k.startswith('own_')) - sum(v for k, v in hp.items() if k.startswith('enemy_'))
    return 'ahead' if delta > 1000 else 'behind' if delta < -1000 else 'level'


def new_video():
    return {'events': [], 'exposure': {p: collections.Counter() for p in PHASES}}


def emit(v, kind, tick, **kw):
    if phase(tick):
        v['events'].append(dict(kind=kind, tick=tick, phase=phase(tick), **kw))


def pressure(v, own, enemy, end, ts=None, states=None):
    for e in enemy:
        if e.get('y') is None or e['y'] >= 9 or not phase(e['tick']):
            continue
        t = e['tick']
        responses = [p for p in own if t < p['tick'] <= t+120 and p.get('x') is not None
                     and canonical(p.get('name', p.get('card', ''))) in ('xbow', 'knight', 'rocket')
                     and lane(p['x']) != lane(e['x'])]
        response = min(responses, key=lambda p: p['tick']) if responses else None
        full = t+120 <= end and (ts is None or covered(ts, t, t+120))
        idx = bisect.bisect_right(ts, t)-1 if ts else -1
        emit(v, 'pressure', t, enemy=e, complete=full, response=response is not None,
             response_tick=response['tick'] if response else None,
             elixir=states[idx]['elixir'] if states and idx >= 0 else None,
             response_elixir=response.get('elixir_public_before') if response else None)


def human(m, own, enemy, order):
    v = new_video()
    m['observed_cards'] = sorted({canonical(p['card']) for p in own})
    m['icebow_overlap'] = len(set(m['observed_cards']) & ICEBOW)
    m['icebow_like'] = m['icebow_overlap'] >= 5
    m['xbow_tesla'] = {'xbow', 'tesla'} <= set(m['observed_cards'])
    m['opponent_archetype'] = archetype([p['card'] for p in enemy], order)
    pressure(v, own, enemy, min(m['last_tick'], 6000))
    for p in own:
        if canonical(p['card']) == 'xbow':
            emit(v, 'xbow', p['tick'], archetype=m['opponent_archetype'], damage=None, complete=False)
    m['video'] = v


def bot(m, ds, uss, plays, damage, episodes, catalog, order, tower_fn, xy_fn, spell_fn):
    v = new_video(); ts = [s['tick'] for s in ds]; end = min(ts[-1], 5999)
    tracks = collections.defaultdict(list)
    for i, us in enumerate(uss):
        if ts[i] >= 6000:
            break
        for u in us:
            tracks[u['key']].append((i, u))
    # A body address may be recycled. Split observations after >3s absence, and
    # give every lifespan an identity so later bodies cannot count as survival.
    segments = {}; index_keys = {}
    for key, rows in tracks.items():
        seq = -1; previous = None
        for i, u in rows:
            if previous is None or ts[i]-ts[previous] > 60:
                seq += 1
            ident = key+'#'+str(seq)
            segments.setdefault(ident, []).append((i, u)); index_keys[i, key] = ident
            previous = i
    enemy = []
    for ident, rows in sorted(segments.items(), key=lambda kv: kv[1][0][0]):
        i, u = rows[0]
        if u['own'] or i == 0 or ts[i]-ts[i-1] > 40:
            continue
        # Spawned tokens/transforms cannot be certified as card placements.
        # Keep first sightings explicitly named as a placement proxy; group
        # same-card swarm bodies appearing together within 1s / 5 tiles.
        near = next((e for e in reversed(enemy) if 0 <= ts[i]-e['tick'] <= 20
                     and e['name'] == u['name'] and math.hypot(e['x']-u['x'], e['y']-u['y']) <= 5), None)
        if near:
            near['body_keys'].append(ident)
        else:
            enemy.append(dict(tick=ts[i], previous_tick=ts[i-1], name=u['name'], x=u['x'], y=u['y'],
                              body_keys=[ident], source='first_seen_body_proxy'))
    enemy.sort(key=lambda e: e['tick'])
    observed_cards = {u['name'] for us in uss for u in us if not u['own'] and u['type'] != 'unknown'}
    for s in ds:
        for q in s['projectiles'] + s['bodies']:
            c = catalog.get(q['card_id'])
            if q['side'] != s['side'] and c:
                observed_cards.add(c['display_name'])
    m['observed_opponent_cards'] = sorted(observed_cards)
    m['opponent_archetype'] = archetype(observed_cards, order)
    pressure(v, plays, enemy, end, ts, ds)
    for e in enemy:
        emit(v, 'enemy_placement_proxy', e['tick'], **{k: a for k, a in e.items() if k != 'tick'})

    def at(t):
        return max(0, bisect.bisect_right(ts, t)-1)

    def follow(t, role):
        return sum(d['amount'] for d in damage if d['role'] == role and t < d['tick'] <= min(t+400, end))

    # Actual observed state exposure, splitting phase boundaries, no gap filling.
    for i, (a, b) in enumerate(zip(ts, ts[1:])):
        if not 0 < b-a <= 40:
            continue
        state = state_label(tower_fn(ds[i]))
        for ph, lo, hi in zip(PHASES, BOUNDS, BOUNDS[1:]):
            secs = max(0, min(b, hi)-max(a, lo))/20
            v['exposure'][ph][state] += secs
    known_names = {c['display_name'] for c in catalog.values()}
    for p in plays:
        t = p['tick']; i = at(t); name = canonical(p['name'])
        board_ok = t-ts[i] <= 40
        recent = [e for e in enemy if 0 < t-e['tick'] <= 80]
        if (name in ('skeletons', 'log') or (p.get('cost') is not None and p['cost'] <= 2)) and recent:
            full = covered(ts, t, t+120)
            engaged = False; matched = []
            if name == 'log':
                # Swept spell geometry is an engagement proxy, not a hit claim.
                for j in range(i, bisect.bisect_right(ts, min(t+120, end))):
                    if ts[j] < t:
                        continue
                    if any(not u['own'] and spell_fn('Log', (p['x'], p['y']), (u['x'], u['y'])) for u in uss[j]):
                        engaged = True
            else:
                for ident, rows in segments.items():
                    k, u = rows[0]
                    if u['own'] and canonical(u['name']) == name and t <= ts[k] <= t+60 and math.hypot(u['x']-p['x'], u['y']-p['y']) <= 3:
                        matched.append(ident)
                        for j, a in rows:
                            if not t <= ts[j] <= t+120:
                                continue
                            if any(not b['own'] and math.hypot(a['x']-b['x'], a['y']-b['y']) <= 2.5 for b in uss[j]):
                                engaged = True
                            # Enemy tower contact also counts as engagement.
                            for b in ds[j]['bodies']:
                                if b['side'] != ds[j]['side'] and b['card_id'] == -1 and b['hp'] > 0:
                                    bx, by = xy_fn(ds[j]['side'], b['x'], b['y'])
                                    if ((abs(bx-9) < .2 and abs(by-3) < .2) or
                                        (min(abs(bx-3.5), abs(bx-14.5)) < .2 and abs(by-6.5) < .2)) and math.hypot(a['x']-bx, a['y']-by) <= 2.5:
                                        engaged = True
            if name == 'log' and any(spell_fn('Log', (p['x'], p['y']), xy_fn(ds[i]['side'], b['x'], b['y']), True)
                                     for b in ds[i]['bodies'] if b['card_id'] == -1 and b['side'] != ds[i]['side'] and b['hp'] > 0):
                engaged = True
            assessed = full and board_ok and (name == 'log' or bool(matched))
            emit(v, 'cycle', t, complete=assessed, empty=not engaged if assessed else None,
                 cost=p['cost'], elixir=p.get('elixir_public_before'), card=p['name'],
                 body_keys=matched, enemy_tick=recent[-1]['tick'])
        ground = [u for u in uss[i] if not u['own'] and u['y'] >= 16 and u['type'] == 'troop'
                  and canonical(u['name']) not in AIR and u['name'] in known_names]
        if name in ('knight', 'icewizard', 'skeletons') and p['y'] >= 16 and ground and board_ok:
            center = 3.5 if lane(p['x']) == 'left' else 14.5
            inward = (p['x']-center)*(1 if center == 3.5 else -1)
            emit(v, 'pull', t, offset=abs(p['x']-center), inward_offset=inward,
                 placement='centre' if inward >= 1.5 else 'side', card=p['name'], x=p['x'], y=p['y'])
        if name == 'xbow':
            emit(v, 'xbow', t, archetype=m['opponent_archetype'], complete=covered(ts, t, t+400),
                 damage=follow(t, 'dealt'), x=p['x'], y=p['y'])
        offensive = (name == 'xbow' and p.get('xbow_class') == 'bridge') or (name == 'rocket' and bool(p.get('spell_towers'))) or (name == 'knight' and 16 <= p['y'] <= 21)
        if offensive and board_ok and i+1 < len(ts) and 0 < ts[i+1]-ts[i] <= 40 and t < ts[i+1]:
            emit(v, 'commit', t, state=state_label(tower_fn(ds[i])), card=p['name'],
                 complete=covered(ts, t, t+400), damage_taken=follow(t, 'taken'))

    def disappearance(ident):
        rows = segments[ident]; j = rows[-1][0]
        if j+2 < len(ts) and ts[j+2] < 6000 and ts[j+2]-ts[j] <= 60:
            return [ts[j], ts[j+1]]
        return None

    # One event per observed tank bridge crossing, not first-seen intrusions.
    for ident, rows in segments.items():
        if rows[0][1]['own'] or canonical(rows[0][1]['name']) not in TANKS:
            continue
        crossing = next(((a, b) for a, b in zip(rows, rows[1:])
                         if a[1]['y'] < 16 <= b[1]['y'] and 0 < ts[b[0]]-ts[a[0]] <= 60), None)
        if crossing is None:
            continue
        (previous, _), (i, tank) = crossing; t = ts[i]; ln = lane(tank['x'])
        quiet = None; finish = end; closed = False
        for j in range(i, len(ts)):
            if ts[j] > end:
                finish = min(end, ts[j-1])
                break
            if j > i and ts[j]-ts[j-1] > 40:
                finish = ts[j-1]
                break
            threat = any(not u['own'] and u['type'] != 'building' and u['y'] >= 16 and lane(u['x']) == ln for u in uss[j])
            quiet = None if threat else ts[j] if quiet is None else quiet
            if quiet is not None and ts[j]-quiet >= 60:
                finish = ts[j]; closed = True; break
        teslas = [p for p in plays if p['name'] == 'Tesla' and t <= p['tick'] <= finish and p['y'] >= 16
                  and (lane(p['x']) == ln or abs(p['x']-9) <= 2)]
        tesla = min(teslas, key=lambda p: p['tick']) if teslas else None
        existing = any(u['own'] and u['name'] == 'Tesla' and (lane(u['x']) == ln or abs(u['x']-9) <= 2) for u in uss[previous])
        tesla_id = None
        if tesla:
            candidates = [(math.hypot(u['x']-tesla['x'], u['y']-tesla['y']), key)
                          for key, rs in segments.items() for k, u in rs[:1]
                          if u['own'] and u['name'] == 'Tesla' and tesla['tick'] <= ts[k] <= tesla['tick']+60
                          and math.hypot(u['x']-tesla['x'], u['y']-tesla['y']) <= 1.5]
            if candidates:
                tesla_id = min(candidates)[1]
        survives = None
        if closed and tesla_id:
            last = ts[segments[tesla_id][-1][0]]
            if last >= finish:
                survives = True
            elif disappearance(tesla_id):
                survives = False
        emit(v, 'tank', t, tank=tank['name'], tank_key=ident, previous_tick=ts[previous],
             crossing_uncertainty_seconds=(t-ts[previous])/20, end_tick=finish, complete=closed,
             preexisting_tesla=existing, tesla_tick=tesla['tick'] if tesla else None,
             delay=(tesla['tick']-t)/20 if tesla else None, tesla_key=tesla_id, survives=survives)
        # Support = non-tank enemy troop within 6 tiles of the tank at crossing.
        supports = [index_keys[i, u['key']] for u in uss[i] if not u['own'] and u['type'] == 'troop'
                    and canonical(u['name']) not in TANKS and math.hypot(u['x']-tank['x'], u['y']-tank['y']) <= 6]
        if supports:
            td = disappearance(ident); sd = [disappearance(k) for k in supports]
            eligible = td is not None and all(d is not None for d in sd) and covered(ts, t, max([td[1]]+[d[1] for d in sd if d]))
            before = max(d[1] for d in sd) <= td[0] if eligible else None
            tank_first = td[1] <= min(d[0] for d in sd) if eligible else None
            emit(v, 'kill', t, tank_key=ident, support_keys=supports, tank_disappearance=td,
                 support_disappearances=sd, complete=eligible,
                 order='supports_first' if before else 'tank_first' if tank_first else 'overlap_or_mixed' if eligible else 'censored')

    for e in episodes:
        best = []; best_tick = None; best_aim = None
        for j in range(bisect.bisect_left(ts, e['tick']), bisect.bisect_right(ts, e['last_tick'])):
            s = ds[j]
            aims = []
            for q in s['projectiles'] + s['bodies']:
                if q['side'] == s['side'] or catalog.get(q['card_id'], {}).get('display_name') != e['name']:
                    continue
                x, y = (q.get('target_x'), q.get('target_y')) if 'target_x' in q else (q.get('x'), q.get('y'))
                if x is not None and y is not None:
                    aims.append(xy_fn(s['side'], x, y))
            tower_xy = (9, 29) if e['tower'].endswith('king') else (3.5 if e['tower'].endswith('left') else 14.5, 25.5)
            for x, y in aims:
                if not spell_fn(e['name'], (18-x, 32-y), (18-tower_xy[0], 32-tower_xy[1]), True):
                    continue
                hit = [u for u in uss[j] if u['own'] and spell_fn(e['name'], (18-x, 32-y), (18-u['x'], 32-u['y']))]
                clump = [u for u in hit if any(a['key'] != u['key'] and math.hypot(a['x']-u['x'], a['y']-u['y']) <= 2.5 for a in hit)]
                if len(clump) > len(best):
                    best = clump; best_tick = ts[j]; best_aim = [x, y]
        emit(v, 'clump', e['tick'], spell=e['name'], tower=e['tower'], contact_last_tick=e['last_tick'],
             bodies=len(best), nominal_elixir=sum(u['value'] or 0 for u in best),
             unknown_values=sum(u['value'] is None for u in best), body_keys=[u['key'] for u in best],
             snapshot_tick=best_tick, aim=best_aim)
    m['video'] = v


def estimate(rows, mode='rate'):
    """Cluster ratio CI, with a conservative effective-n Wilson CI for fractions."""
    pairs = [(a, b) for a, b in rows if b > 0]; n = len(pairs)
    a = sum(x for x, _ in pairs); b = sum(y for _, y in pairs)
    if not b:
        return dict(value=None, ci95=None, n=0, n_clusters=0, numerator=a, denominator=b)
    value = a/b
    se = math.sqrt(n/(n-1)*sum((x-value*y)**2 for x, y in pairs))/b if n > 1 else None
    ci = [value-1.96*se, value+1.96*se] if se is not None else None
    if mode == 'fraction':
        # Effective independent cluster count, not iid events. Conservative at
        # 0/100% and for unequal event counts; take envelope with sandwich CI.
        neff = b*b/sum(y*y for _, y in pairs); z = 1.96
        mid = (value+z*z/(2*neff))/(1+z*z/neff)
        half = z*math.sqrt(value*(1-value)/neff+z*z/(4*neff*neff))/(1+z*z/neff)
        ci = [min(ci[0], mid-half), max(ci[1], mid+half)] if ci else [mid-half, mid+half]
        ci = [max(0, ci[0]), min(1, ci[1])]
    elif ci and all(x >= 0 for x, _ in pairs):
        ci[0] = max(0, ci[0])
        if a == 0 and mode == 'rate':
            ci[1] = -math.log(.025)/b
    return dict(value=value, ci95=ci, n=b if mode != 'rate' else n, n_clusters=n, numerator=a, denominator=b)


def summarize(matches, human=False):
    """All stats declare denominator; full receipts supply exclusions/censoring."""
    result = {}
    arches = sorted({m['opponent_archetype'] for m in matches})
    for split in ('all', 'wins', 'losses', 'big_losses'):
        ms = [m for m in matches if split == 'all' or (m['big_loss'] if split == 'big_losses' else m['outcome'] == split)]
        result[split] = {}
        for ph in PHASES:
            rows = [m for m in ms if m['phases'][ph]['seconds'] > 0]
            def calc(kind, field=None, predicate=lambda e: True, mode='rate', state=None, arch=None):
                clusters = collections.defaultdict(lambda: [0., 0.])
                for m in rows:
                    if arch and m['opponent_archetype'] != arch:
                        continue
                    es = [e for e in m['video']['events'] if e['phase'] == ph and e['kind'] == kind and predicate(e)]
                    if mode == 'rate':
                        a = sum(e.get(field, 0) for e in es) if field else len(es)
                        b = (m['video']['exposure'][ph].get(state, 0) if state else m['phases'][ph]['seconds'])/60
                    else:
                        values = [e.get(field) for e in es if e.get(field) is not None]
                        a, b = sum(values), len(values)
                    c = clusters[m.get('replay_id', m['id'])]; c[0] += a; c[1] += b
                s = estimate(list(clusters.values()), mode)
                s['unit'] = 'per_minute' if mode == 'rate' else mode
                return s
            full = lambda e: e.get('complete', False)
            empty = lambda e: full(e) and e.get('empty')
            r = {'pressure_windows': calc('pressure'),
                 'pressure_complete': calc('pressure', predicate=full),
                 'pressure_responses': calc('pressure', predicate=lambda e: full(e) and e['response']),
                 'pressure_response_fraction': calc('pressure', 'response', full, 'fraction')}
            if not human:
                r.update(cycle_candidates=calc('cycle'), cycle_assessed=calc('cycle', predicate=full),
                         cycle_empty=calc('cycle', predicate=empty), cycle_empty_elixir=calc('cycle', 'cost', empty),
                         cycle_elixir_at_play=calc('cycle', 'elixir', empty, 'mean'),
                         pressure_elixir=calc('pressure', 'elixir', full, 'mean'),
                         pressure_response_elixir=calc('pressure', 'response_elixir', full, 'mean'),
                         tank_crossings=calc('tank'), tank_complete=calc('tank', predicate=full),
                         tank_tesla_delay=calc('tank', 'delay', mode='mean'),
                         tank_tesla_response=calc('tank', predicate=lambda e: e['delay'] is not None),
                         tank_preexisting_tesla=calc('tank', 'preexisting_tesla', mode='fraction'),
                         tank_tesla_survival=calc('tank', 'survives', mode='fraction'),
                         pull_placements=calc('pull'), pull_offset=calc('pull', 'offset', mode='mean'),
                         pull_inward_offset=calc('pull', 'inward_offset', mode='mean'),
                         pull_centre=calc('pull', predicate=lambda e: e['placement'] == 'centre'),
                         pull_side=calc('pull', predicate=lambda e: e['placement'] == 'side'),
                         kill_pushes=calc('kill'), kill_assessed=calc('kill', predicate=full),
                         kill_supports_first=calc('kill', predicate=lambda e: e['order'] == 'supports_first'),
                         clump_contacts=calc('clump'), clump_episodes=calc('clump', predicate=lambda e: e['bodies'] >= 2),
                         clump_bodies=calc('clump', 'bodies'), clump_elixir=calc('clump', 'nominal_elixir'),
                         clump_unknown_values=calc('clump', 'unknown_values'))
                # Fraction derived without changing original receipts.
                for m in rows:
                    for e in m['video']['events']:
                        if e['kind'] == 'kill':
                            e['supports_first'] = e['order'] == 'supports_first' if e['complete'] else None
                r['kill_supports_first_fraction'] = calc('kill', 'supports_first', full, 'fraction')
                for state in ('ahead', 'level', 'behind'):
                    pred = lambda e, s=state: e['state'] == s
                    r['commit.'+state] = calc('commit', predicate=pred, state=state)
                    r['commit_damage.'+state] = calc('commit', 'damage_taken', lambda e, s=state: full(e) and e['state'] == s, 'mean')
                    r['commit_full.'+state] = calc('commit', predicate=lambda e, s=state: full(e) and e['state'] == s, state=state)
            for arch in arches:
                r['xbow.'+arch] = calc('xbow', arch=arch)
                if not human:
                    r['xbow_damage.'+arch] = calc('xbow', 'damage', full, 'mean', arch=arch)
                    r['xbow_full.'+arch] = calc('xbow', predicate=full, arch=arch)
            result[split][ph] = {'n_sides_or_matches': len(rows), 'metrics': r}
    return result
