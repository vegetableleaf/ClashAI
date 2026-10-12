"""Offline public-only phase measurements. No project-code imports or network.

Run: python phase_stats.py [--since YYYYMMDD]
All output is confined to this script's directory. Standard library only.
See report.md for operational definitions and limitations; report.json and the
three audit JSONL files retain denominators, per-match tags and event receipts.
"""
from __future__ import annotations

import argparse
import bisect
import collections
import datetime as dt
import hashlib
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
import statistics
from urllib.parse import parse_qs, urlparse
import video_metrics as vm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ARCH_ORDER = vm.archetype_order(ROOT)
LIVE = ROOT / 'scratchpad/gauntlet/L68/live_reader'
PRO = Path('C:/Users/benpe/Downloads/raw2/raw')
CATALOG = ROOT / 'research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json'
STATS = ROOT / 'icebow/config/cards_stats.json'
PHASES = ('1x', '2x', '3x')
BOUNDS = (0, 2400, 4800, 6000)
BIG = {'Earthquake', 'Fireball', 'Lightning', 'Poison', 'Rocket'}
SUMMON_SPELLS = {'GoblinBarrel','Graveyard','Clone','Mirror','RoyalDelivery'}
SPELL_RADII = {'Rocket': 2, 'Fireball': 2.5, 'Arrows': 4, 'Tornado': 5.5,
               'Poison': 3.5, 'Earthquake': 3.5, 'Lightning': 3.5,
               'Zap': 2.5, 'Snowball': 2.5, 'Vines': 2.5, 'GoblinCurse': 3,
               'Freeze': 3, 'Rage': 3, 'GoblinBarrel': 1.5, 'Graveyard': 4}
OWN_COST = {'Skeletons': 1, 'Log': 2, 'Knight': 3, 'IceWizard': 3,
            'Tornado': 3, 'Tesla': 4, 'Xbow': 6, 'Rocket': 6}


def phase(tick):
    """Gameplay only; the post-5:00 tiebreak drain is not a fourth combat phase."""
    if tick < 0 or tick >= 6000:
        return None
    return PHASES[0 if tick < 2400 else 1 if tick < 4800 else 2]


def slices(a, b):
    for p, lo, hi in zip(PHASES, BOUNDS, BOUNDS[1:]):
        left, right = max(a, lo), min(b, hi)
        if right > left:
            yield p, left, right


def own_xy(side, x, y):
    return (x / 1000, y / 1000) if side == 1 else (18 - x / 1000, 32 - y / 1000)


def lane(x):
    return 'left' if x < 9 else 'right'


def zone(y):
    if y < 15:
        return 'enemy_side'
    if y <= 18:
        return 'bridge'
    return 'own_front' if y < 24 else 'own_back'


def xbow_class(y):
    return 'unavailable' if y is None else 'bridge' if 16 <= y <= 21 else 'defensive' if y > 21 else 'enemy_side'


def human_xy(p, perspective=None):
    """data-i is the replay team orientation (constant for both teams), not player side."""
    if p['x'] is None or p['y'] is None or p.get('index') not in ('0', '1'):
        return None, None
    side = perspective or p['side']
    rotate = (side == 't') == (p['index'] == '1')
    return (18-p['x'], 32-p['y']) if rotate else (p['x'], p['y'])


def norm(s):
    return re.sub('[^a-z0-9]', '', s.lower())


def load_catalog():
    by_id, by_name = {}, {}
    stats = json.loads(STATS.read_text(encoding='utf8'))['cards']
    counts = {norm(k): v.get('count', 1) for k, v in stats.items()}
    counts.update({norm(v['display']): v.get('count', 1) for v in stats.values()})
    aliases = {'Archer': 'archers', 'Goblin': 'goblins', 'SpearGoblin': 'speargoblins',
               'Minion': 'minions', 'Barbarian': 'barbarians', 'Bat': 'bats',
               'FireSpirits': 'firespirit', 'BarbLog': 'barbarianbarrel', 'Log': 'thelog'}
    for c in json.loads(CATALOG.read_text(encoding='utf8'))['cards']:
        c = dict(c)
        c['count'] = max(1, counts.get(norm(aliases.get(c['display_name'], c['display_name'])), 1))
        by_name[c['display_name']] = c
        for field in ('card_id', 'evolution_form_id', 'hero_form_id'):
            if c.get(field) is not None:
                by_id[c[field]] = c
    # Explicit witnessed public alias documented in pipeline/reader_identity_aliases.py.
    by_id[203000023] = by_name['IceWizard']
    return by_id, by_name


def sample(values):
    values = [float(x) for x in values if x is not None and math.isfinite(x)]
    if not values:
        return {'n': 0, 'mean': None, 'median': None}
    return {'n': len(values), 'mean': statistics.fmean(values), 'median': statistics.median(values),
            'min': min(values), 'max': max(values)}


def rate(counts, seconds):
    """Ratio of sums with match-cluster delta-method 95% CI (not iid plays)."""
    pairs = [(float(c), s / 60) for c, s in zip(counts, seconds) if s > 0]
    n = len(pairs)
    num = sum(c for c, _ in pairs)
    den = sum(e for _, e in pairs)
    if not den:
        return {'n_matches': 0, 'count': num, 'minutes': 0, 'per_minute': None, 'ci95': None}
    r = num / den
    se = math.sqrt(n / (n - 1) * sum((c - r * e) ** 2 for c, e in pairs)) / den if n > 1 else None
    ci = [r - 1.96 * se, r + 1.96 * se] if se is not None else None
    if ci and all(c >= 0 for c, _ in pairs):
        ci[0] = max(0, ci[0])
        # A zero count cannot establish a zero population rate; rule-of-three bound.
        if num == 0:
            ci[1] = -math.log(0.025) / den
    return {'n_matches': n, 'count': num, 'minutes': den, 'per_minute': r, 'ci95': ci}


def wilson(k, n):
    if not n:
        return {'count': k, 'n': n, 'fraction': None, 'ci95': None}
    z = 1.96
    m = (k / n + z*z / (2*n)) / (1 + z*z/n)
    d = z * math.sqrt(k/n*(1-k/n)/n + z*z/(4*n*n)) / (1+z*z/n)
    return {'count': k, 'n': n, 'fraction': k/n, 'ci95': [m-d, m+d]}


def blank_phase():
    return {'seconds': 0.0, 'counts': collections.Counter(), 'samples': collections.defaultdict(list)}


def add(m, p, key, value=1):
    if p:
        m['phases'][p]['counts'][key] += value


def val(m, p, key, value):
    if p and value is not None:
        m['phases'][p]['samples'][key].append(value)


def is_tower(b):
    if b['card_id'] != -1:
        return False
    x,y=b['x'],b['y']
    ky=3000 if b['side']==0 else 29000
    py=6500 if b['side']==0 else 25500
    return (abs(x-9000)<200 and abs(y-ky)<200) or (min(abs(x-3500),abs(x-14500))<200 and abs(y-py)<200)


def tower_slot(b, side):
    x, y = own_xy(side, b['x'], b['y'])
    return ('own_' if b['side'] == side else 'enemy_') + ('king' if abs(x-9) < 1 else lane(x))


def towers(d):
    return {tower_slot(b, d['side']): b['hp'] for b in d['bodies'] if is_tower(b)}


def body_key(b):
    return str(b.get('address', b.get('category', ''))) + ':' + str(b['card_id']) + ':' + str(b['side'])


def units(d, catalog):
    out = []
    bodies = d['bodies']
    for b in bodies:
        cid = b['card_id']
        if is_tower(b) or b['hp'] <= 0:
            continue
        c = catalog.get(cid)
        if c and c['type'] == 'spell':
            continue
        if cid == 203000023 and b.get('category') is not None and any(
                a['card_id'] == cid and a['side'] == b['side'] and
                a.get('category') == b['category'] - 1 and
                abs(a['x']-b['x']) <= 500 and abs(a['y']-b['y']) <= 500 for a in bodies):
            continue  # FloatingCube duplicate; retain actual hero body.
        x, y = own_xy(d['side'], b['x'], b['y'])
        out.append({'key': body_key(b), 'name': c['display_name'] if c else str(cid),
                    'x': x, 'y': y, 'own': b['side'] == d['side'], 'hp': b['hp'],
                    'value': c['elixir'] / c['count'] if c else None,
                    'type': c['type'] if c else 'unknown', 'card_id': cid})
    return out


def public_decision(j):
    """Allowlist projection: no opponent hand, deck or elixir fields are retained."""
    p = j['public']
    return {'tick': j['tick'], 'side': p['observer_side'], 'elixir': p.get('own_elixir_raw'),
            'hand': p.get('own_hand', []), 'bodies': p.get('raw_bodies', []),
            'projectiles': p.get('raw_projectiles', []), 't_dev': j.get('t_dev')}


def read_live(path):
    before = path.stat()
    d = {'decisions': [], 'frames': [], 'plays': [], 'confirmations': [], 'abilities': [],
         'head': {}, 'closed': False, 'stop_reason': None, 'errors': 0, 'events': collections.Counter()}
    sha = hashlib.sha256()
    with path.open('rb') as f:
        for raw in f:
            sha.update(raw)
            # Ignore irrelevant event payloads, including all opponent hidden fields.
            if not any(b'"event": "'+ev+b'"' in raw[:80] for ev in
                       (b'decision', b'frame', b'play', b'confirmed', b'start', b'end', b'stop', b'ability', b'ability_confirmed', b'unconfirmed')):
                continue
            try:
                j = json.loads(raw)
            except (ValueError, UnicodeError):
                d['errors'] += 1
                continue
            ev = j.get('event'); d['events'][ev] += 1
            if ev == 'start':
                d['head'] = {k: j.get(k) for k in ('ckpt', 'ckpt_sha256', 'pipeline_decisions', 'dry_run')}
            elif ev == 'decision' and j.get('public'):
                dec = public_decision(j)
                if not d['decisions']:
                    hp = {b['max_hp'] for b in dec['bodies'] if is_tower(b) and b['side'] == dec['side']}
                    if hp != {4424, 7032}:
                        return None, 'other_account_tower_signature'
                d['decisions'].append(dec)
            elif ev == 'frame':
                # Own elixir and public clock only. Do not retain any other frame keys.
                d['frames'].append((j['tick'], j.get('elixir'), j.get('t_dev')))
            elif ev == 'play':
                d['plays'].append({k: j.get(k) for k in ('tick', 'name', 'xy', 'elixir')})
            elif ev == 'confirmed':
                d['confirmations'].append({k: j.get(k) for k in ('tick', 'name', 'spawn', 'intended')})
            elif ev == 'ability_confirmed':
                d['abilities'].append({k: j.get(k) for k in ('tick', 'drop')})
            elif ev == 'end':
                d['closed'] = True
            elif ev == 'stop':
                d['stop_reason'] = j.get('why')
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        return None, 'changed_while_reading'
    ds = d['decisions']
    if not ds:
        return None, 'no_public_decisions'
    if not any(h.get('name') == 'Xbow' for s in ds for h in s['hand']):
        return None, 'no_xbow_in_own_hand'
    if not d['closed']:
        return None, 'no_end_event'
    if d['head'].get('dry_run'):
        return None, 'dry_run'
    final=towers(ds[-1])
    alive=[sum(v>0 for k,v in final.items() if k.startswith(who+'_')) for who in ('own','enemy')]
    d['early_terminal'] = ds[-1]['tick']<2400 and d['stop_reason']=='battle_over_hands_visible' and min(alive)==0 and max(alive)>=2
    if (ds[-1]['tick'] < 2400 and not d['early_terminal']) or len(final) < 2:
        return None, 'short_nonterminal_or_invalid_scorecard'
    if any(b['tick'] < a['tick'] for a, b in zip(ds, ds[1:])):
        return None, 'clock_reset'
    d['sha256'] = sha.hexdigest()
    d['bytes'] = before.st_size
    return d, None


def match_plays(data):
    """One-to-one latest outstanding same-card confirmation, at most 5 seconds."""
    ps = [dict(p, confirmed=False) for p in data['plays']]
    for c in data['confirmations']:
        candidates = [p for p in ps if not p['confirmed'] and p['name'] == c['name'] and 0 <= c['tick']-p['tick'] <= 100]
        if candidates:
            p = max(candidates, key=lambda a: a['tick'])
            p['confirmed'] = True
            p['confirmation_tick'] = c['tick']
            p['actual_xy'] = (c.get('spawn') or [c.get('intended') or p['xy']])[0]
    return ps


def in_spell(name, aim, target, tower=False):
    x, y = aim; tx, ty = target
    if name in ('Log', 'BarbLog'):
        reach = 10.1 if name == 'Log' else 5
        return abs(tx-x) <= 2 + (1 if tower else 0.5) and y-reach-1 <= ty <= y+1
    r = SPELL_RADII.get(name)
    return None if r is None else math.hypot(x-tx, y-ty) <= r + (1 if tower else 0.5)


def push_crossings(states, unit_states):
    """First observed river crossing per lane, after 3s quiet; sampled elixir, not interpolated."""
    active = {}; pushes = []; prev = {}; intrusions = 0
    for s, us in zip(states, unit_states):
        t = s['tick']
        if not phase(t):
            continue
        enemy = {u['key']: u for u in us if not u['own'] and u['type'] != 'building'}
        for ln in list(active):
            g = active[ln]
            if not any(u['y'] >= 16 and lane(u['x']) == ln for u in enemy.values()):
                if t-g['last_threat_tick'] >= 60:
                    g['end_tick'] = t; g['closed'] = True; del active[ln]
            else:
                g['last_threat_tick'] = t
        for key, u in enemy.items():
            if u['y'] < 16:
                continue
            ln = lane(u['x']); old = prev.get(key)
            crossing = old is not None and old[1]['y'] < 16 and 0 < t-old[0] <= 60
            if old is None:
                intrusions += 1
            if crossing and ln not in active:
                g = {'tick': t, 'previous_tick': old[0], 'lane': ln, 'elixir': s['elixir'],
                     'crossing_interval_seconds': (t-old[0])/20, 'last_threat_tick': t,
                     'end_tick': min(states[-1]['tick'], 6000), 'closed': False, 'entrants': {}, 'plays': []}
                active[ln] = g; pushes.append(g)
            if ln in active:
                active[ln]['entrants'].setdefault(key, u)
        prev = {key: (t, u) for key, u in enemy.items()}
    return pushes, intrusions


def trade_sign(enemy_value, own_spend):
    diff = enemy_value - own_spend
    return ('positive' if diff > 1e-9 else 'negative' if diff < -1e-9 else 'even'), diff


def analyse_live(name, data, catalog, names, play_out, push_out, spell_out):
    ds = data['decisions']; side = ds[0]['side']; ts = [d['tick'] for d in ds]
    tw = towers(ds[-1]); took = 3-sum(v>0 for k,v in tw.items() if k.startswith('enemy_'))
    lost = 3-sum(v>0 for k,v in tw.items() if k.startswith('own_'))
    outcome = 'wins' if took>lost else 'losses' if took<lost else 'draws'
    legacy_towers=[b for b in ds[-1]['bodies'] if b['card_id']==-1]
    legacy_took=3-sum(b['hp']>0 and b['side']!=side for b in legacy_towers)
    legacy_lost=3-sum(b['hp']>0 and b['side']==side for b in legacy_towers)
    m = {'id': name, 'source': 'bot', 'checkpoint': data['head'].get('ckpt'),
         'checkpoint_sha256': data['head'].get('ckpt_sha256'),
         'fast_plays': bool(data['head'].get('pipeline_decisions')), 'fast_flag_recorded':data['head'].get('pipeline_decisions') is not None, 'outcome': outcome,
         'big_loss': lost-took >= 2, 'final_crowns_proxy': [took,lost],
         'early_terminal':data.get('early_terminal',False),
         'legacy_scorecard_crowns':[legacy_took,legacy_lost],
         'legacy_scorecard_outcome':'wins' if legacy_took>legacy_lost else 'losses' if legacy_took<legacy_lost else 'draws',
         'first_tick': ts[0], 'last_tick': ts[-1], 'sha256': data['sha256'], 'bytes': data['bytes'],
         'phases': {p: blank_phase() for p in PHASES}, 'quality': {}, 'regen': {p: [] for p in PHASES},
         'regen_boundary': collections.defaultdict(list)}
    for p,a,b in slices(ts[0], min(ts[-1],6000)):
        m['phases'][p]['seconds'] = (b-a)/20
    unit_states = [units(s,catalog) for s in ds]
    for s in ds:
        val(m,phase(s['tick']),'elixir_at_decisions',s['elixir'])
    # Own elixir intervals: high-frequency frame measurements when present, else decisions.
    frames = sorted({a[0]:a for a in data['frames'] if a[0] >= ts[0] and a[0] <= min(ts[-1],6000)}.values())
    if len(frames)<2:
        frames = [(s['tick'],s['elixir'],s['t_dev']) for s in ds if s['tick']<=6000]
        m['quality']['elixir_source']='decisions'
    else:
        m['quality']['elixir_source']='frames'
    m['quality']['post_300s_decisions'] = sum(t>=6000 for t in ts)
    m['quality']['parse_errors'] = data['errors']
    clock_rates=[(b[0]-a[0])/(b[2]-a[2]) for a,b in zip(frames,frames[1:])
                 if a[2] is not None and b[2] is not None and 0<b[2]-a[2]<=2 and 0<b[0]-a[0]<=40]
    m['quality']['ticks_per_device_second']=sample(clock_rates)
    m['quality']['decision_gaps_gt_2s'] = sum(b-a>40 for a,b in zip(ts,ts[1:]))
    for a,b in zip(frames,frames[1:]):
        ticks=b[0]-a[0]
        if ticks<=0 or ticks>40 or a[1] is None or b[1] is None:
            continue
        r=(b[1]-a[1])*20/ticks
        for p,l,h in slices(a[0],b[0]):
            secs=(h-l)/20
            add(m,p,'elixir_observed_seconds',secs)
            # Conservative sampled cap occupancy: both endpoints at 10, no sampled drop.
            if a[1]>=9.999 and b[1]>=9.999:
                add(m,p,'cap_seconds_lower',secs)
            if a[1]>=9.999 or b[1]>=9.999:
                add(m,p,'cap_seconds_endpoint_upper',secs)
        if 0<ticks<=20 and 0<a[1]<9 and 0<b[1]<9 and 0.1<r<1.5 and phase(a[0])==phase(b[0]):
            p=phase(a[0])
            if p:
                m['regen'][p].append(r)
                if 2380<=a[0]<2420 or 4780<=a[0]<4820:
                    m['regen_boundary'][str(a[0]//20)].append(r)
    # Public tower HP deltas: defer a disappearance until a second missing observation.
    hp = towers(ds[0]); missing=collections.Counter(); damage=[]; crowns={'own':0,'enemy':0}
    last_seen={k:i for i,s in enumerate(ds) for k in towers(s)}
    m['quality']['tower_hp_increases']=0
    for i,s in enumerate(ds[1:],1):
        if s['tick']>=6000:
            break
        curr=towers(s)
        if len(curr)<2:
            continue
        for k,old in list(hp.items()):
            missing[k] = missing[k]+1 if k not in curr else 0
            gone=missing[k]>=2 or (i==len(ds)-1 and data.get('closed',False))
            new=curr.get(k, 0 if gone and last_seen.get(k,-1)<i else old)
            if new>old:
                m['quality']['tower_hp_increases']+=1
            new=min(old,new)
            if new<old:
                role='taken' if k.startswith('own_') else 'dealt'
                king=k.split('_')[0]+'_king'
                # King death auto-removes surviving princess towers. Their residual HP
                # is not damage dealt by attacks, even though all three crowns are lost.
                collateral=not k.endswith('_king') and k not in curr and (curr.get(king)==0 or (king not in curr and last_seen.get(king,-1)<i))
                if collateral:
                    add(m,phase(s['tick']),'terminal_despawn_hp_excluded',old-new)
                else:
                    p=phase(s['tick']); add(m,p,'damage_'+role,old-new)
                    damage.append({'tick':s['tick'],'tower':k,'amount':old-new,'role':role})
            hp[k]=new
        for who,direction in (('own','lost'),('enemy','gained')):
            dead=3 if hp.get(who+'_king',1)<=0 else sum(hp.get(who+'_'+ln,1)<=0 for ln in ('left','right'))
            add(m,phase(s['tick']),'crowns_'+direction,max(0,dead-crowns[who]));crowns[who]=dead
    for p in PHASES:
        c=m['phases'][p]['counts'];c['damage_net']=c['damage_dealt']-c['damage_taken']
    ps=match_plays(data)
    confirmed=[]
    for p in ps:
        ph=phase(p['tick']);add(m,ph,'play_attempts')
        if not p['confirmed']:
            add(m,ph,'unconfirmed_attempts');continue
        if not ph:
            continue
        i=bisect.bisect_right(ts,p['tick'])-1
        if i<0:
            continue
        s=ds[i]; us=unit_states[i]; stale=p['tick']-s['tick']>40
        # Logged normalized/model x is mirrored relative to public raw own-frame x.
        xy=p.get('actual_xy') or p['xy']; x,y=18-xy[0]*18,xy[1]*32
        cost=next((h['cost'] for h in s['hand'] if h['name']==p['name']), OWN_COST.get(p['name'],names.get(p['name'],{}).get('elixir')))
        p.update({'phase':ph,'x':x,'y':y,'lane':lane(x),'zone':zone(y),'cost':cost,
                  'state_age_seconds':(p['tick']-s['tick'])/20,'board_available':not stale,
                  'elixir_public_before':s['elixir'],'tower_hp':towers(s) if not stale else None})
        enemy=[u for u in us if not u['own']];own=[u for u in us if u['own']]
        invaded=[u for u in enemy if u['y']>=16]
        p['enemy_units_on_our_side']=len(invaded) if not stale else None
        p['enemy_nominal_value_on_our_side']=sum(u['value'] or 0 for u in invaded) if not stale else None
        p['enemy_unknown_value_bodies']=sum(u['value'] is None for u in invaded) if not stale else None
        p['own_units_alive']=len(own) if not stale else None
        if p['name'] in ('Xbow','Tesla'):
            j=bisect.bisect_left(ts,p['confirmation_tick'])
            if j<len(ts) and ts[j]-p['confirmation_tick']<=40:
                bodies=[u for u in unit_states[j] if u['own'] and u['name']==p['name']]
                if bodies:
                    p['placement_raw_alignment_tiles']=min(math.hypot(u['x']-x,u['y']-y) for u in bodies)
                    val(m,ph,'placement_raw_alignment_tiles',p['placement_raw_alignment_tiles'])
        p['enemy_board']=[{k:u[k] for k in ('name','x','y','value','hp')} for u in enemy] if not stale else None
        add(m,ph,'plays');add(m,ph,'cards.'+p['name']);add(m,ph,'placements.'+p['lane']+'.'+p['zone'])
        add(m,ph,'elixir_spent',cost or 0)
        val(m,ph,'elixir_at_plays',p['elixir_public_before']);val(m,ph,'elixir_play_event',p['elixir'])
        for key in ('enemy_units_on_our_side','enemy_nominal_value_on_our_side','own_units_alive'):
            val(m,ph,key,p[key])
        if not stale:
            for k,h in p['tower_hp'].items():val(m,ph,'tower_hp_at_play.'+k,h)
        quiet=not stale and not any(u['y']>=12 for u in enemy)
        p['quiet_cycle']=quiet and cost is not None and cost<=3
        if p['quiet_cycle']:add(m,ph,'quiet_cycle_plays')
        p['quiet_defence_proxy']=quiet and p['name'] in ('Tesla','IceWizard','Knight','Skeletons','Tornado') and y>=18
        if p['quiet_defence_proxy']:
            add(m,ph,'quiet_defence_plays');add(m,ph,'quiet_defence_elixir',cost or 0)
        if p['name']=='Xbow':
            p['xbow_class']=xbow_class(y)
            add(m,ph,'xbow_class.'+p['xbow_class']);add(m,ph,f'xbow_cell.{int(x)},{int(y)}')
            val(m,ph,'xbow_elixir',p['elixir_public_before']);val(m,ph,'xbow_enemy_units_on_our_side',p['enemy_units_on_our_side'])
            locks=[]
            end=min(p['tick']+400,6000,ts[-1]);target_windows=[]
            for j in range(i,bisect.bisect_right(ts,end)):
                for q in ds[j]['projectiles']:
                    if q['side']!=side or catalog.get(q['card_id'],{}).get('display_name')!='Xbow' or q.get('target_x') is None:
                        continue
                    qx,qy=own_xy(side,q['target_x'],q['target_y'])
                    targets=[b for b in ds[j]['bodies'] if is_tower(b) and b['side']!=side and b['hp']>0 and
                             math.hypot(q['target_x']-b['x'],q['target_y']-b['y'])<1200]
                    # Projectile has no source address: require exactly one own live X-Bow.
                    bows=[u for u in unit_states[j] if u['own'] and u['name']=='Xbow']
                    if targets and len(bows)==1 and math.hypot(bows[0]['x']-x,bows[0]['y']-y)<1.5:
                        locks.append(ds[j]['tick']);target_windows.extend(tower_slot(b,side) for b in targets)
            p['tower_lock_observed']=bool(locks);p['first_lock_tick']=min(locks) if locks else None
            p['full_20s_followup']=end>=p['tick']+400
            p['tower_damage_next_20s_all_sources']=sum(d['amount'] for d in damage if d['role']=='dealt' and p['tick']<d['tick']<=end)
            p['locked_tower_damage_after_lock_within_20s_all_sources']=sum(d['amount'] for d in damage if locks and d['tower'] in target_windows and min(locks)<=d['tick']<=end)
            add(m,ph,'xbow_lock_observed',bool(locks));add(m,ph,'xbow_full_followup',p['full_20s_followup'])
            val(m,ph,'xbow_damage_next_20s_all_sources',p['tower_damage_next_20s_all_sources'])
        if names.get(p['name'],{}).get('type')=='spell':
            tower_targets=[];unit_targets=[]
            if not stale:
                for b in s['bodies']:
                    if is_tower(b) and b['side']!=side and b['hp']>0 and in_spell(p['name'],(x,y),own_xy(side,b['x'],b['y']),True):
                        tower_targets.append(tower_slot(b,side))
                unit_targets=[u for u in enemy if in_spell(p['name'],(x,y),(u['x'],u['y']))]
            supported=p['name'] in SPELL_RADII or p['name'] in ('Log','BarbLog')
            typ=('both' if tower_targets and unit_targets else 'tower' if tower_targets else 'units' if unit_targets else 'neither') if supported and not stale else 'unknown'
            p['spell_target_proxy']=typ;p['spell_towers']=tower_targets
            p['spell_enemy_nominal_value_in_footprint']=sum(u['value'] or 0 for u in unit_targets)
            p['tower_hp_loss_next_8s_all_sources']=sum(d['amount'] for d in damage if d['tower'] in tower_targets and p['tick']<d['tick']<=p['tick']+160)
            p['enemy_elixir_killed']=None;p['attributable_tower_chip']=None
            add(m,ph,'spell_targets.'+p['name']+'.'+typ)
            if p['name']=='Rocket' and tower_targets:add(m,ph,'rocket_on_tower')
            val(m,ph,'spell_associated_tower_loss.'+p['name'],p['tower_hp_loss_next_8s_all_sources'])
        confirmed.append(p)
        play_out.write(json.dumps({'match':name,**p})+'\n')
    pushes,intrusions=push_crossings(ds,unit_states)
    m['quality']['first_seen_own_side_body_entries']=intrusions
    # Each reactive play may belong to only one overlapping lane engagement.
    for p in confirmed:
        if p['y']<16 or (p['name']=='Xbow' and p.get('xbow_class')=='bridge'):
            continue
        candidates=[g for g in pushes if g['tick']<=p['tick']<=g['end_tick'] and (p['lane']==g['lane'] or abs(p['x']-9)<=2)]
        if candidates:
            g=min(candidates,key=lambda g:(p['lane']!=g['lane'],p['tick']-g['tick']))
            g['plays'].append({'tick':p['tick'],'name':p['name'],'cost':p['cost']})
    for g in pushes:
        ph=phase(g['tick']);add(m,ph,'pushes');val(m,ph,'elixir_at_crossing',g['elixir'])
        val(m,ph,'crossing_uncertainty_seconds',g['crossing_interval_seconds'])
        g['response_seconds']=(g['plays'][0]['tick']-g['tick'])/20 if g['plays'] else None
        g['own_spent']=sum(p['cost'] or 0 for p in g['plays'])
        g['enemy_nominal_committed']=sum(u['value'] or 0 for u in g['entrants'].values())
        g['unknown_value_bodies']=sum(u['value'] is None for u in g['entrants'].values())
        g['trade_sign_proxy'],g['trade_net_proxy']=trade_sign(g['enemy_nominal_committed'],g['own_spent'])
        g['overcommit_proxy']=max(0,g['own_spent']-g['enemy_nominal_committed']-2)
        add(m,ph,'responded_pushes',g['response_seconds'] is not None)
        val(m,ph,'response_seconds',g['response_seconds']);val(m,ph,'defence_spend',g['own_spent'])
        val(m,ph,'enemy_nominal_committed',g['enemy_nominal_committed'])
        # Censored engagements retained, but excluded from completed-trade summaries.
        if g['closed'] and not g['unknown_value_bodies']:
            add(m,ph,'trade_eligible');add(m,ph,'trade_'+g['trade_sign_proxy']);add(m,ph,'trade_net_proxy',g['trade_net_proxy'])
            add(m,ph,'overcommit_engagements',g['overcommit_proxy']>0);add(m,ph,'overcommit_excess_elixir',g['overcommit_proxy'])
        g['entrants']=list(g['entrants'].values());push_out.write(json.dumps({'match':name,**g})+'\n')
    # Enemy spell contact candidates, deduped across decisions by name/lane with <=2s gaps.
    episodes={};all_episodes=[]
    for s in ds:
        if not phase(s['tick']):continue
        sightings=[]
        for q in s['projectiles']:
            c=catalog.get(q['card_id'])
            if q['side']==side or not c or c['type']!='spell' or q.get('target_x') is None:continue
            aim=own_xy(side,q['target_x'],q['target_y'])
            # Flip into spell-caster frame for directional Log/Barrel geometry.
            for b in s['bodies']:
                if not is_tower(b) or b['side']!=side or b['hp']<=0:continue
                tx,ty=own_xy(side,b['x'],b['y'])
                hit=in_spell(c['display_name'],(18-aim[0],32-aim[1]),(18-tx,32-ty),True)
                if hit:sightings.append((c['display_name'],tower_slot(b,side),'projectile_target'))
        for b in s['bodies']:
            c=catalog.get(b['card_id'])
            if b['side']==side or not c or c['type']!='spell':continue
            bx,by=own_xy(side,b['x'],b['y'])
            for tower in s['bodies']:
                if not is_tower(tower) or tower['side']!=side or tower['hp']<=0:continue
                tx,ty=own_xy(side,tower['x'],tower['y'])
                if in_spell(c['display_name'],(18-bx,32-by),(18-tx,32-ty),True):
                    sightings.append((c['display_name'],tower_slot(tower,side),'spell_body'))
        for spell,target,source in set(sightings):
            key=(spell,target)
            if key not in episodes or s['tick']-episodes[key]['last_tick']>40:
                e={'name':spell,'tower':target,'tick':s['tick'],'last_tick':s['tick'],'sources':[]}
                episodes[key]=e;all_episodes.append(e)
            e=episodes[key];e['last_tick']=s['tick']
            if source not in e['sources']:e['sources'].append(source)
    assoc=set()
    for e in all_episodes:
        ph=phase(e['tick']);e['associated_hp_loss']=0
        for j,d in enumerate(damage):
            if d['tower']==e['tower'] and e['tick']<=d['tick']<=e['last_tick']+100:
                e['associated_hp_loss']+=d['amount']
                if e['name'] not in SUMMON_SPELLS:assoc.add(j)
        add(m,ph,('enemy_summon_spell_contact.' if e['name'] in SUMMON_SPELLS else 'enemy_spell_contact.')+e['name'])
        add(m,ph,'enemy_big_spell_contacts' if e['name'] in BIG else 'enemy_summon_spell_contacts' if e['name'] in SUMMON_SPELLS else 'enemy_other_spell_contacts')
        spell_out.write(json.dumps({'match':name,**e})+'\n')
    for j,d in enumerate(damage):
        if d['role']=='taken':add(m,phase(d['tick']),'damage_taken_spell_associated' if j in assoc else 'damage_taken_unattributed',d['amount'])
    m['quality']['confirmed_gameplay_plays']=len(confirmed)
    m['quality']['confirmed_ability_events']=len(data['abilities'])
    m['quality']['ability_spend_not_in_card_trade']=True
    m['quality']['unknown_body_ids']=dict(collections.Counter(str(u['card_id']) for us in unit_states for u in us if u['value'] is None))
    for ph in PHASES:
        for spell in ('Earthquake','Fireball','Lightning','Poison','Rocket','Log','Arrows','BarbLog','Vines','Snowball','Zap'):
            m['phases'][ph]['counts'].setdefault('enemy_spell_contact.'+spell,0)
    vm.bot(m, ds, unit_states, confirmed, damage, all_episodes, catalog, ARCH_ORDER, towers, own_xy, in_spell)
    return m


class ReplayHTML(HTMLParser):
    def __init__(self):
        super().__init__();self.plays=[];self.timeline=[];self.end_seconds=None;self.markers=[];self.attrs=collections.Counter()
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);self.attrs.update(k for k in a if k.startswith('data-'))
        if all(k in a for k in ('data-x','data-y','data-c','data-t','data-s')):
            self.plays.append({'tick':int(a['data-t']),'side':a['data-s'],'card':a['data-c'],
                               'x':float(a['data-x'])/1000 if a['data-x'] not in ('None','null','') else None,
                               'y':float(a['data-y'])/1000 if a['data-y'] not in ('None','null','') else None,'index':a.get('data-i')})
        if tag=='img' and all(k in a for k in ('data-card','data-t','data-s','data-ability')):
            self.timeline.append((int(a['data-t']),a['data-s'],a['data-card'],int(a['data-ability'])))
        if 'end_time' in a.get('class','').split():
            match=re.search(r'left:([0-9.]+)px',a.get('style',''))
            if match:self.end_seconds=float(match[1])/10


def analyse_pro(path,play_out):
    raw=path.read_bytes();j=json.loads(raw);parser=ReplayHTML();parser.feed(j.get('payload',{}).get('html',''))
    if not parser.plays:return [],'no_play_markers',{}
    if parser.end_seconds is None:return [],'no_end_marker',{}
    q=parse_qs(urlparse(j.get('request_url','')).query)
    crowns=[int(q[k][0]) if q.get(k) else None for k in ('team_crowns','opponent_crowns')]
    abilities={(t,'t' if s=='blue' else 'o',c) for t,s,c,a in parser.timeline if a}
    valid=[p for p in parser.plays if (p['tick'],p['side'],p['card']) not in abilities and p['card']!='_invalid']
    out=[]
    for side,idx in [('t',0),('o',1)]:
        plays=[p for p in valid if p['side']==side]
        xbow=any(p['card'] in ('x-bow','xbow') for p in plays)
        a,b=crowns[idx],crowns[1-idx]
        m={'id':path.stem+':'+side,'replay_id':path.stem,'source':'pro','xbow':xbow,
           'outcome':'unknown' if a is None or b is None else 'wins' if a>b else 'losses' if a<b else 'draws',
           'big_loss':a is not None and b is not None and b-a>=2,'final_crowns':[a,b],
           'sha256':hashlib.sha256(raw).hexdigest(),'last_tick':parser.end_seconds*20,
           'phases':{p:blank_phase() for p in PHASES}}
        for ph,lo,hi in slices(0,min(parser.end_seconds*20,6000)):m['phases'][ph]['seconds']=(hi-lo)/20
        oriented=[dict(p,x=human_xy(p,side)[0],y=human_xy(p,side)[1]) for p in valid]
        vm.human(m,[p for p in oriented if p['side']==side],[p for p in oriented if p['side']!=side],ARCH_ORDER)
        for p in plays:
            ph=phase(p['tick'])
            if not ph:continue
            add(m,ph,'plays');add(m,ph,'cards.'+p['card'])
            x,y=human_xy(p)
            if x is None or y is None:
                add(m,ph,'placement_unavailable')
                if p['card'] in ('x-bow','xbow'):add(m,ph,'xbow_class.unavailable')
                play_out.write(json.dumps({'match':m['id'],'tick':p['tick'],'card':p['card'],'x':None,'y':None,'phase':ph})+'\n')
                continue
            # data-i=1: team at y=0; data-i=0: team at y=32.
            add(m,ph,'placements.'+lane(x)+'.'+zone(y))
            if p['card'] in ('x-bow','xbow'):
                cls=xbow_class(y)
                add(m,ph,'xbow_class.'+cls);add(m,ph,f'xbow_cell.{int(x)},{int(y)}')
                old_y=32-p['y'] if side=='t' else p['y']
                add(m,ph,'xbow_old_class.'+xbow_class(old_y))
                add(m,ph,'xbow_orientation.'+str(p.get('index')))
            if p['card']=='rocket' and any(in_spell('Rocket',(x,y),tw,True) for tw in ((3.5,6.5),(14.5,6.5),(9,3))):add(m,ph,'rocket_on_tower_geometry')
            play_out.write(json.dumps({'match':m['id'],'tick':p['tick'],'card':p['card'],'x':x,'y':y,'phase':ph,
                                       'raw_x':p['x'],'raw_y':p['y'],'side':side,'orientation':p.get('index')})+'\n')
        out.append(m)
    return out,None,{'plays':len(parser.plays),'timeline':len(parser.timeline),'attributes':dict(parser.attrs),
                     'orientation_values':sorted({str(p.get('index')) for p in valid})}


def group_summary(matches,cluster_pro=False):
    out={}
    keys=sorted({k for m in matches for ph in PHASES for k in m['phases'][ph]['counts']})
    samples=sorted({k for m in matches for ph in PHASES for k in m['phases'][ph]['samples']})
    for ph in PHASES:
        ms=[m for m in matches if m['phases'][ph]['seconds']>0]
        if cluster_pro:
            clusters=collections.defaultdict(lambda:{'seconds':0,'counts':collections.Counter()})
            for m in ms:
                s=clusters[m['replay_id']];s['seconds']+=m['phases'][ph]['seconds'];s['counts'].update(m['phases'][ph]['counts'])
            rows=list(clusters.values())
        else:rows=[m['phases'][ph] for m in ms]
        out[ph]={'n_matches':len(ms),'n_clusters':len(rows),'seconds':sum(r['seconds'] for r in rows),
                 'rates':{k:rate([r['counts'].get(k,0) for r in rows],[r['seconds'] for r in rows]) for k in keys},
                 'samples':{k:sample([v for m in ms for v in m['phases'][ph]['samples'].get(k,[])]) for k in samples}}
        caps=[m['phases'][ph]['counts'].get('cap_seconds_lower',0) for m in ms]
        observed=[m['phases'][ph]['counts'].get('elixir_observed_seconds',0) for m in ms]
        if sum(observed):out[ph]['cap_fraction_lower']={'fraction':sum(caps)/sum(observed),'n_intervals_seconds':sum(observed),'n_matches':len(ms),'ci95':[x/60 for x in rate(caps,observed)['ci95']] if len(ms)>1 else None}
    return out


def all_splits(ms,pro=False):
    return {label:group_summary(ms if label=='all' else [m for m in ms if m['big_loss']] if label=='big_losses' else [m for m in ms if m['outcome']==label],pro)
            for label in ('all','wins','losses','big_losses','draws')}


def paired_comparison(matches):
    rows=[]
    for m in matches:
        if all(m['phases'][p]['seconds']>=30 for p in PHASES):
            rates={p:m['phases'][p]['counts']['damage_net']*60/m['phases'][p]['seconds'] for p in PHASES}
            rows.append(rates)
    out={'n_matches':len(rows),'minimum_seconds_each_phase':30}
    for a,b in [('1x','2x'),('1x','3x')]:
        diffs=[r[b]-r[a] for r in rows];s=sample(diffs)
        if len(diffs)>1:
            e=1.96*statistics.stdev(diffs)/math.sqrt(len(diffs));s['ci95']=[s['mean']-e,s['mean']+e]
        out[b+'_minus_'+a]=s
    return out


def fmt_rate(summary,ph,key):
    r=summary[ph]['rates'].get(key)
    if not r:
        n=summary[ph]['n_clusters']; secs=summary[ph]['seconds']
        r=rate([0]*n,[secs/n]*n) if n else rate([],[])
    if r['per_minute'] is None:return 'unavailable (n=0; 95% CI not estimable)'
    ci=r['ci95'];digits=4 if ci and 0<ci[1]<0.01 else 2
    c=f" [{ci[0]:.{digits}f}, {ci[1]:.{digits}f}]" if ci else ' [95% CI not estimable]'
    return f"{r['per_minute']:.2f}{c}; total={r['count']:g}, n={r['n_matches']}m"


def fmt_sample(summary,ph,key):
    s=summary[ph]['samples'].get(key,{})
    return f"{s['mean']:.2f} (n={s['n']})" if s.get('mean') is not None else 'unavailable'


def findings(r):
    b=r['bot']['all'];loss=r['bot']['losses'];big=r['bot']['big_losses'];pro=r['pros']['xbow']['all']
    n=r['selection']['included'];w=r['outcomes']
    pairs=r['paired'];d=pairs['3x_minus_1x']
    return [
        f"Selected {n} completed main-account X-Bow matches: {w.get('wins',0)} wins, {w.get('losses',0)} losses, {w.get('draws',0)} tower-state draws; {r['big_losses']} big losses (a subset of losses). This includes {r['early_terminal']['n']} clear terminal defeats before 2:00 that the original scorecard's duration cutoff would discard.",
        'Net tower HP per minute (dealt minus taken): '+ '; '.join(p+' '+fmt_rate(b,p,'damage_net') for p in PHASES)+'.',
        'In eventual losses, net tower HP/minute: '+ '; '.join(p+' '+fmt_rate(loss,p,'damage_net') for p in PHASES)+'.',
        'In big losses, tower HP taken/minute: '+ '; '.join(p+' '+fmt_rate(big,p,'damage_taken') for p in PHASES)+'.',
        (f"Among {pairs['n_matches']} matches with at least 30 seconds in each phase, 3x minus 1x net HP/min averages {d['mean']:.1f} (95% CI {d['ci95'][0]:.1f} to {d['ci95'][1]:.1f}). Later-phase comparisons remain conditional on survival." if d.get('mean') is not None and d.get('ci95') else f"Paired three-phase comparison has n={pairs['n_matches']}; insufficient sample."),
        'Own elixir at confirmed plays: '+ '; '.join(p+' '+fmt_sample(b,p,'elixir_at_plays') for p in PHASES)+'.',
        'Own elixir at observed push crossings: '+ '; '.join(p+' '+fmt_sample(b,p,'elixir_at_crossing') for p in PHASES)+'.',
        'Confirmed bot plays/minute: '+ '; '.join(p+' '+fmt_rate(b,p,'plays') for p in PHASES)+'. Human X-Bow sides: '+ '; '.join(p+' '+fmt_rate(pro,p,'plays') for p in PHASES)+'.',
        'Quiet defensive-spend proxy, elixir/minute: '+ '; '.join(p+' '+fmt_rate(b,p,'quiet_defence_elixir') for p in PHASES)+'. This measures the stated heuristic, not proven waste.',
        'Rocket-on-tower geometry counts/rates per minute: '+ '; '.join(p+' '+fmt_rate(b,p,'rocket_on_tower') for p in PHASES)+'. Actual spell chip and enemy elixir killed are not identifiable from these snapshots.'
    ]


def write_report(r):
    lines=['# X-Bow phase measurement','',f"Offline run: {r['created_utc']}. Since {r['since']}. All rates below have 95% CIs in brackets; total is the numerator and n is the number of independent matches/replay clusters unless stated. Big losses overlap losses. Human exposure sums player-sides; CIs cluster both sides by replay.",'']
    lines+=['## Ten findings','']+[f'{i}. {s}' for i,s in enumerate(r['findings'],1)]
    lines+=['','## Selection and coverage','',f"Selection: {json.dumps(r['selection'],sort_keys=True)}.",
            f"Human corpus: {r['pro_coverage']['files']} files, {r['pro_coverage']['usable_replays']} usable unique replays, {r['pro_coverage']['sides']} player-sides, {r['pro_coverage']['xbow_sides']} sides observed playing X-Bow. Rank/top-100 provenance is owner-supplied, not independently certified by these replay pages.",
            'Main-account proxy: initial own princess maximum HP 4424 and king 7032. Smaller tower signatures are excluded. Nearby ladder trophy reads are attached per match when available; tower signatures do not uniquely prove account identity.',
            'Selection requires an end event, Xbow in the observed OWN hand, and at least two final tower bodies. The scorecard duration rule (last tick >=2400) is retained except for clear early terminal records: battle_over_hands_visible stop, zero surviving towers on one side and at least two on the other. These earlier defeats must not disappear from a study of 1x collapses. Their IDs and a strict scorecard-only sensitivity summary are in report.json. Last-observed tower outcomes can miss a final hit and label a tiebreak loss as a draw. Final crowns in bot metadata are scorecard proxies, not result-screen crowns.',
            'Each selected file has checkpoint path/hash, fast-plays flag, SHA256, observed ticks and account evidence in report.json. Active/changing files are excluded. Metrics use confirmed card plays; unmatched tap attempts and hero abilities are counted separately. Observed exposure starts at the first decision; no unlogged opening is invented. Missing/gapped elixir time is excluded from cap occupancy.','',
            '## Clock verification','',
            '| Phase | Tick interval | Own regen elixir/s, mean [95% CI across match means] | Intervals / matches |',
            '|---|---|---|---|']
    for p,lo,hi in zip(PHASES,BOUNDS,BOUNDS[1:]):
        s=r['regen'][p];ci=s.get('ci95');lines.append(f"| {p} | [{lo}, {hi}) | {s.get('mean',0):.6f} [{ci[0]:.6f}, {ci[1]:.6f}] | {s['n_intervals']} / {s['n_matches']} |" if ci else f'| {p} | [{lo}, {hi}) | unavailable | 0 |')
    lines+=['','Ticks run at 20/s (device-clock interval measurements are retained per match). Positive uncapped own-elixir changes over <=1s verify regeneration; spend/cap intervals are excluded. Baseline-rate estimates retain intervals within 0.02 elixir/s of each phase’s empirical median, removing elixir awards/corrections; rejected counts are retained. Boundary bins around 119/120 and 239/240 seconds retain unfiltered positive rates in report.json. Regulation 2:00 through overtime 4:00 is 2x. The 5:00+ tiebreak drain is excluded from all combat metrics, but the final decision still supplies the scorecard label.','',
            '## Bot versus human plays','', '| Phase | Bot confirmed plays/min | Human all decks plays/min | Human X-Bow plays/min |','|---|---|---|---|']
    for p in PHASES:lines.append('| '+p+' | '+' | '.join(fmt_rate(s,p,'plays') for s in (r['bot']['all'],r['pros']['all_decks']['all'],r['pros']['xbow']['all']))+' |')
    comparable=[('Skeletons','cards.Skeletons','cards.skeletons'),('Log','cards.Log','cards.the-log'),
                ('Knight','cards.Knight','cards.knight'),('Ice Wizard','cards.IceWizard','cards.ice-wizard'),
                ('Tornado','cards.Tornado','cards.tornado'),('Tesla','cards.Tesla','cards.tesla'),
                ('X-Bow','cards.Xbow','cards.x-bow'),('Rocket','cards.Rocket','cards.rocket')]
    # The comparable column order is identical across the three short card tables.
    for ph in PHASES:
        lines+=['',f'### {ph}: card rates, bot versus humans','',
                '| Card, per minute | Bot | Human all decks | Human X-Bow sides |','|---|---|---|---|']
        for label,bkey,pkey in comparable:
            lines.append('| '+label+' | '+fmt_rate(r['bot']['all'],ph,bkey)+' | '+fmt_rate(r['pros']['all_decks']['all'],ph,pkey)+' | '+fmt_rate(r['pros']['xbow']['all'],ph,pkey)+' |')
    lines+=['','### Placement comparisons','',
            'All lane × zone rates and X-Bow cell histograms for both cohorts are in report.json. Below are the placements most directly comparable without board state.','',
            '| Phase / placement, per minute | Bot | Human all decks | Human X-Bow sides |','|---|---|---|---|']
    for ph in PHASES:
        for label,bkey,pkey in [('Bridge X-Bow','xbow_class.bridge','xbow_class.bridge'),('Defensive X-Bow','xbow_class.defensive','xbow_class.defensive'),('Rocket tower geometry','rocket_on_tower','rocket_on_tower_geometry')]:
            lines.append('| '+ph+' '+label+' | '+fmt_rate(r['bot']['all'],ph,bkey)+' | '+fmt_rate(r['pros']['all_decks']['all'],ph,pkey)+' | '+fmt_rate(r['pros']['xbow']['all'],ph,pkey)+' |')
    for split in ('all','wins','losses','big_losses'):
        s=r['bot'][split]
        lines+=['',f'## Bot: {split.replace("_"," ")}','', '| Metric | 1x | 2x | 3x |','|---|---|---|---|']
        lines.append('| Observed minutes (n matches) | '+' | '.join(f"{s[p]['seconds']/60:.1f} (n={s[p]['n_matches']})" for p in PHASES)+' |')
        for label,key in [('Own elixir at decisions','elixir_at_decisions'),('Own elixir at plays','elixir_at_plays'),('Enemy units on our side at play','enemy_units_on_our_side'),('Enemy nominal elixir on our side','enemy_nominal_value_on_our_side'),('Own bodies alive at play','own_units_alive'),('Elixir at push crossing','elixir_at_crossing'),('Response seconds, observed responses','response_seconds'),('X-Bow elixir','xbow_elixir'),('X-Bow following 20s tower damage, all sources','xbow_damage_next_20s_all_sources')]:
            lines.append('| '+label+' | '+' | '.join(fmt_sample(s,p,key) for p in PHASES)+' |')
        for label,key in [('Cap seconds/min, both endpoints at 10','cap_seconds_lower'),('Plays/min','plays'),('Cheap quiet cycles/min','quiet_cycle_plays'),('Quiet defensive plays/min','quiet_defence_plays'),('Quiet defensive elixir/min','quiet_defence_elixir'),('Overcommit engagements/min','overcommit_engagements'),('Overcommit excess elixir/min','overcommit_excess_elixir'),('Tower HP dealt/min','damage_dealt'),('Tower HP taken/min','damage_taken'),('Crowns gained/min','crowns_gained'),('Crowns lost/min','crowns_lost'),('Positive trade PROXY/min','trade_positive'),('Negative trade PROXY/min','trade_negative'),('Net nominal trade PROXY/min','trade_net_proxy'),('X-Bow observed tower locks/min','xbow_lock_observed'),('Rocket tower targets/min','rocket_on_tower'),('Enemy big-spell contact episodes/min','enemy_big_spell_contacts'),('Enemy other-spell contact episodes/min','enemy_other_spell_contacts'),('Spell-associated HP taken/min, not causal','damage_taken_spell_associated'),('Unattributed HP taken/min','damage_taken_unattributed')]:
            lines.append('| '+label+' | '+' | '.join(fmt_rate(s,p,key) for p in PHASES)+' |')
    b=r['bot']['all']
    for title,prefix in [('Cards played per minute','cards.'),('Lane × zone placements per minute','placements.'),('Own spell targeting geometry per minute','spell_targets.'),('Enemy spell tower-contact candidates per minute','enemy_spell_contact.')]:
        lines+=['',f'## {title}','', '| Metric | 1x | 2x | 3x |','|---|---|---|---|']
        for key in sorted({k for p in PHASES for k in b[p]['rates'] if k.startswith(prefix)}):
            lines.append('| '+key[len(prefix):]+' | '+' | '.join(fmt_rate(b,p,key) for p in PHASES)+' |')
    lines+=['','## Definitions and limits','']+['- '+s for s in r['methodology']]
    lines+=['','## What the human HTML supports','',
            'Directly supported: card, tick, side and placement; match end marker; final crowns from captured URL; per-phase plays/card rates, lane/zone, X-Bow cell/bridge/defensive histograms, and Rocket tower-target geometry. Both sides are reported for all decks, X-Bow sides separately, with win/loss/big-loss splits in report.json. Duplicate timeline and map entries are reconciled by using map markers once; ability markers are excluded from card counts.',
            'Unsupported: decision-time or actual play-time elixir; per-phase cap/leak time (HTML has only whole-match aggregate leakage); living units, troop HP and tower HP; push crossings, response timing, defence commitments or trades; X-Bow tower locks and following damage; spell target units/kills/actual chip; threat-conditioned cycling or wasted spend; phase-resolved crowns and damage; enemy spell hits and spell-versus-unit damage. No simulator reconstruction or inferred opponent hidden state was substituted.',
            'The human corpus has no checkpoint or fast-plays flags. X-Bow classification requires an observed X-Bow play and may miss decks that never played it. These opponents, levels, deck mix and selection rules differ from the bot sample; the comparison is descriptive.','',
            '## Audit files','',
            '`report.json` contains all rate denominators/CIs, outcome splits, checkpoint × fast-plays splits, per-match phase summaries, coverage and input hashes. `plays.jsonl` holds confirmed bot play states and X-Bow/spell receipts. `pushes.jsonl` holds engagements. `enemy_spells.jsonl` holds public contact candidates. `pro_plays.jsonl` holds parsed human plays. No opponent hidden state is exported.','',
            'Rerun: `python phase_stats.py --since 20261008`. Tests: use an installed pytest interpreter with `-B -m pytest -q -p no:cacheprovider test_phase_stats.py`; disable plugin autoload.']
    lines=lines[:3]+['']+video_report(r)+['','## Previous-ticket measurements (regenerated)','']+lines[3:]
    (HERE/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf8')


VIDEO_SUPPORT = {
    'a': {'label':'bot only','human':None,'bot':'First-seen enemy body placement and no observed engagement proxy; six-second coverage required.'},
    'b': {'label':'bot vs icebow-like humans','human':'Timing/lane only; exact HTML placements.','bot':'First-seen enemy body placement proxy; own public elixir at onset and response.'},
    'c': {'label':'bot only','human':None,'bot':'Observed tank river crossing, reactive Tesla delay and survival to push end.'},
    'd': {'label':'bot only','human':None,'bot':'Defensive troop lateral offset while a known ground troop is on our side.'},
    'e': {'label':'bot only','human':None,'bot':'Support/tank public body disappearance intervals, with ties and censoring.'},
    'f': {'label':'bot only','human':None,'bot':'Maximum simultaneous clumped bodies per existing enemy spell tower-contact episode.'},
    'g': {'label':'bot vs icebow-like humans','human':'Placements/archetype only; damage unavailable.','bot':'Observed-card census archetype; placements and all-source enemy tower HP loss in full next 20s.'},
    'h': {'label':'bot only','human':None,'bot':'Observed HP-state exposure, offensive commits and all-source own tower HP loss in full next 20s.'}}
VIDEO_METHODS = [
    'Each table labels bot only or bot vs icebow-like humans. If the overlap cohort is smaller than 15 sides, comparison columns explicitly use X-Bow + Tesla fallback; the exact overlap cohort is also retained. Sides qualify from all observed cards, not a reconstructed hidden deck. Big losses overlap losses. Draws remain in all.',
    'All brackets are approximate 95% CIs. Rates use match/replay-cluster ratio-of-sums intervals; means use the same cluster ratio with event counts as denominator. Fractions use a cluster-effective-size Wilson envelope around the sandwich interval, keeping nonzero uncertainty at 0/100%. n is independent clusters for rates, event observations for means/fractions; C states cluster count. No-data and one-cluster continuous/rate intervals are explicitly not estimable. Rates always retain numerator and exposure. Human sides share replay clusters.',
    'Human orientation evidence: data-i is constant across both teams in each HTML replay. Index 1 puts team at raw y<16, index 0 puts team at raw y>16; opponent is opposite. Rotate x and y only when that side is at the top. Raw coordinates, side and orientation are saved in pro_plays.jsonl. Missing/unknown orientation is unavailable, never silently guessed. X-Bow classes bridge (16<=y<=21), defensive (>21), enemy_side (<16), unavailable partition every X-Bow.',
    'Bot enemy placements are first-seen public nonspell bodies, excluding bodies present at the first decision and after >2s gaps; same-card bodies within 1s and 5 tiles are grouped. Spawned tokens, evolution changes, duplicate identities and transforms can still masquerade as placements; spells without a persistent body are absent. This is a lower-coverage placement proxy, not a confirmed enemy card-play feed. Observation intervals and source keys are saved. Human placements are exact HTML markers. No enemy elixir or hand is used.',
    '(a) Cheap play strictly after a first-seen enemy placement by <=4s. Assess only a complete 6s decision window, no gap >2s, fresh board, and an observed spawned troop matched by card, <=3 tiles, <=3s; unmatched troops are unknown. Engagement proxy: matched troop within 2.5 tiles of enemy body/tower; Log swept footprint intersects enemy body/tower. This cannot certify targeting or actual hits. Empty-proxy count and nominal own card elixir use total phase minutes; candidates/assessed counts disclose missing coverage.',
    '(b) Enemy raw placement transformed into our frame must have y<9. First own X-Bow/Knight/Rocket strictly later by <=6s in the other x<9/x>=9 lane is a response. Each enemy placement is an opportunity; overlapping windows may share a response. Fraction excludes incomplete windows; opportunity/rate counts and exclusions are retained. Bot own elixir at first public enemy sighting and last public decision before response are separate. Human elixir is unavailable.',
    '(c) Tank names (catalog IDs resolve to names) include Giant, Golem, Royal/Electro/Goblin Giant, PEKKA, Lava Hound, Hog Rider, Ram Rider/Battle Ram, Balloon, Mega Knight. Same tracked body must cross y<16 to y>=16 within 3s. First-seen intrusions are excluded. Push ends after 3s with no nonbuilding enemy on our side in the crossing lane; gaps >2s/end censor it. First Tesla after crossing, on our side and same lane or within 2 tiles of centre, supplies delay; existing Teslas are flagged separately. Response delays are conditional on observed responses, not zero for missing responses. Newly placed Tesla is matched to a body within 1.5 tiles/3s. Survival requires closed push and matched identity alive at end, or confirmed disappearance before end; unmatched/censored is null.',
    '(d) Own Knight/Ice Wizard/Skeletons at y>=16 with a known enemy ground troop at y>=16. Lateral offset is absolute x minus lane centre 3.5/14.5; signed inward offset is also exported. Centre pull means >=1.5 tiles inward; all other placements are side. Flying catalog aliases are excluded, unknown bodies are excluded, ambiguous transformation forms remain a limitation. Position does not prove a successful pull.',
    '(e) Support set is non-tank enemy troops within 6 tiles of tank at crossing. Public disappearance requires last observed body then two missing decisions within 3s, before tiebreak. Lifespans split after >3s gaps to reduce address reuse. Supports-first requires every support disappearance upper bound <= tank last-visible tick; tank-first requires tank disappearance upper bound <= every support last-visible tick. Overlapping intervals or mixed support order are separate; censored observations are excluded from assessed fraction. Death transforms/visibility gaps are not certified kills.',
    '(f) Existing enemy_spells episodes are tower contacts, not all enemy casts. At each observed matching spell footprint, retain own bodies having another own body within 2.5 tiles inside the footprint. Report maximum simultaneous count and corresponding nominal catalog elixir per episode, excluding towers. Separate clusters may be included; unknown costs are counted, not imputed. A spell touching two towers may appear twice, as in the original episode definition; summons/copy spells remain contact proxies. Counts do not prove damage or deaths.',
    '(g) Read the literal ARCH precedence list from crapi/census.py without executing it; normalize catalog/HTML names. First matching observed card wins, else Other. Bot uses only visible bodies/projectiles; human uses observed cards. Spawned cards can bias bot archetype. Placement rate denominator is phase exposure of matches in that archetype. Damage averages include only full, gap-free next 20s and are all sources, never X-Bow-attributable.',
    '(h) State is sum of public remaining own tower HP minus enemy tower HP, >+1000 ahead, <-1000 behind, otherwise level. Missing towers count zero (public disappearance may flicker); all known king/princess HP is included. State exposure uses only decision intervals <=2s, split at phase boundaries. Commits: bridge X-Bow or Knight (16<=y<=21), Rocket whose geometry touches an enemy tower. Count only commits within a valid observed state interval. Per-state rates divide by time in that state, not all match time. HP taken means own tower HP lost over the next 20s, all sources, only complete windows; overlapping windows can count the same damage.',
    'Video receipts: video_events.jsonl contains event kinds, matches, phases, eligibility, body identities, timing and disappearance intervals. report.json retains all outcome splits and denominators, cohort IDs, observed opponent cards/archetype and per-match state exposure. Older measurements below preserve their original definitions; their broad human cohorts are historical comparison context, not the new icebow comparison.'
]


def vf(s):
    if s['value'] is None:return 'unavailable; n=0; 95% CI not estimable'
    ci=s['ci95']; ci_text=f'[{ci[0]:.3f}, {ci[1]:.3f}]' if ci else '[95% CI not estimable]'
    return f"{s['value']:.3f} {ci_text}; n={s['n']:g}, C={s['n_clusters']}; total={s['numerator']:g}, den={s['denominator']:.3f}"


def video_findings(r):
    b=r['video_metrics']['bot']['all']; h=r['video_metrics']['humans']['all']; c=r['human_comparison']
    def f(k,p='1x'):return vf(b[p]['metrics'][k])
    old=r['pros']['xbow']['all']['1x']['rates'].get('xbow_old_class.enemy_side',{}).get('count',0)
    arch=max((k for k in b['1x']['metrics'] if k.startswith('xbow.')),
             key=lambda k:b['1x']['metrics'][k]['numerator']).split('.',1)[1]
    return [
        f"Bot vs icebow-like humans (placement audit uses all human X-Bow sides): {old:g} first-phase X-Bows were misrotated into enemy_side. Corrected bridge/min {fmt_rate(r['pros']['xbow']['all'],'1x','xbow_class.bridge')}; defensive/min {fmt_rate(r['pros']['xbow']['all'],'1x','xbow_class.defensive')}.",
        f"Bot vs icebow-like humans: {c['icebow_like_n']} sides overlap at least five Icebow cards; {c['xbow_tesla_n']} have X-Bow + Tesla. Selected comparison {c['selected']} has {c['selected_n']} sides.",
        f"Bot only: the largest first-phase X-Bow placement group is observed {arch}: placements/min {f('xbow.'+arch)}; following enemy tower HP loss over a complete 20s {f('xbow_damage.'+arch)}. Damage includes every source.",
        f"Bot only: first-phase active-opponent empty-engagement proxy plays/min {f('cycle_empty')}; nominal elixir/min {f('cycle_empty_elixir')}.",
        f"Bot vs icebow-like humans: first-phase opposite-lane response fraction bot {f('pressure_response_fraction')}; comparison {vf(h['1x']['metrics']['pressure_response_fraction'])}. Enemy bot placements are first-sighting proxies.",
        f"Bot only: first-phase Tesla delay after tank crossing {f('tank_tesla_delay')} seconds; survival fraction among resolved matched Teslas {f('tank_tesla_survival')}.",
        f"Bot only: first-phase defensive troop lateral offset averages {f('pull_offset')} tiles.",
        f"Bot only: first-phase all-supports-before-tank disappearance fraction {f('kill_supports_first_fraction')}.",
        f"Bot only: first-phase enemy spell contacts with clumping/min {f('clump_episodes')}; nominal clustered elixir/min {f('clump_elixir')}.",
        f"Bot only: first-phase offensive commits/min while ahead {f('commit.ahead')}; while behind {f('commit.behind')}. Following own tower HP loss while behind {f('commit_damage.behind')}."
    ]


def video_report(r):
    c=r['human_comparison']; selected='icebow-like humans' if c['selected']=='icebow_like' else 'X-Bow + Tesla fallback humans'
    lines=['## Corrected human X-Bow placement','',
           'Bot vs icebow-like humans — placement audit below uses all observed human X-Bow sides to reconcile the original bug. '+VIDEO_METHODS[2],
           '', '| Phase / histogram class | Bot per minute | Human X-Bow sides per minute |','|---|---|---|']
    for ph in PHASES:
        for cls in ('bridge','defensive','enemy_side','unavailable'):
            lines.append('| '+ph+' '+cls+' | '+fmt_rate(r['bot']['all'],ph,'xbow_class.'+cls)+' | '+fmt_rate(r['pros']['xbow']['all'],ph,'xbow_class.'+cls)+' |')
        lines.append('| '+ph+' total | '+fmt_rate(r['bot']['all'],ph,'cards.Xbow')+' | '+fmt_rate(r['pros']['xbow']['all'],ph,'cards.x-bow')+' |')
    lines+=['','## Video metrics','',
            f"Bot vs icebow-like humans: overlap >=5/8 n={c['icebow_like_n']} sides; X-Bow + Tesla n={c['xbow_tesla_n']} sides. Selected: {selected}, n={c['selected_n']}. "+('The icebow-like cohort is below 15 sides; fallback is mandatory.' if c['icebow_like_n']<15 else 'The minimum 15-side criterion is met.'),
            '',VIDEO_METHODS[1],'','### Top ten follow-up findings','']
    lines += [f'{i}. {text}' for i,text in enumerate(r['video_findings'],1)]
    lines += ['','### Metric support','', '| Metric | Comparison | Public data support |','|---|---|---|']
    for key,s in VIDEO_SUPPORT.items():lines.append(f"| {key} | {s['label']} | {s['bot']} Human: {s['human'] or 'unavailable'} |")
    # Card and placement comparison includes outcomes as well as all sides.
    cards=[('Skeletons','Skeletons','skeletons'),('Log','Log','the-log'),('Knight','Knight','knight'),('Ice Wizard','IceWizard','ice-wizard'),('Tornado','Tornado','tornado'),('Tesla','Tesla','tesla'),('X-Bow','Xbow','x-bow'),('Rocket','Rocket','rocket')]
    for split in ('all','wins','losses','big_losses'):
        bs=r['bot'][split];hs=r['pros']['comparison'][split]
        lines+=['',f'### Bot vs icebow-like humans — {split}; human column = {selected}','',
                '| Phase / card or placement | Bot /min [95% CI] | Human /min [95% CI] |','|---|---|---|']
        keys=[(label,'cards.'+bk,'cards.'+hk) for label,bk,hk in cards]
        keys += [(cls+' X-Bow','xbow_class.'+cls,'xbow_class.'+cls) for cls in ('bridge','defensive','enemy_side','unavailable')]
        keys += [('Rocket tower','rocket_on_tower','rocket_on_tower_geometry')]
        keys += [(ln+' '+z,'placements.'+ln+'.'+z,'placements.'+ln+'.'+z) for ln in ('left','right') for z in ('enemy_side','bridge','own_front','own_back')]
        for ph in PHASES:
            for label,bk,hk in keys:lines.append('| '+ph+' '+label+' | '+fmt_rate(bs,ph,bk)+' | '+fmt_rate(hs,ph,hk)+' |')
    for split in ('all','wins','losses','big_losses'):
        bs=r['video_metrics']['bot'][split];hs=r['video_metrics']['humans'][split]
        lines+=['',f'### Video outcomes: {split}','',
                'Bot only unless the comparison column says bot vs icebow-like humans. Per-minute values use phase minutes except state/archetype rows, which use their own exposure. Means/fractions show event n and cluster C. Human column = '+selected+'.','',
                '| Phase / metric (unit) | Comparison | Bot [95% CI] | Human [95% CI] |','|---|---|---|']
        keys=sorted({k for ph in PHASES for k in bs[ph]['metrics']} | {k for ph in PHASES for k in hs[ph]['metrics']})
        for key in keys:
            comparable=key.startswith('pressure_') and key not in ('pressure_elixir','pressure_response_elixir') or key.startswith('xbow.')
            for ph in PHASES:
                b=bs[ph]['metrics'].get(key);h=hs[ph]['metrics'].get(key)
                label='bot vs icebow-like humans' if comparable else 'bot only'
                lines.append(f"| {ph} {key} ({b['unit'] if b else h['unit']}) | {label} | {vf(b) if b else 'no archetype exposure; n=0'} | {vf(h) if comparable and h else 'unavailable'} |")
    lines+=['','### Video definitions, exclusions and censoring','']+['- '+x for x in VIDEO_METHODS]
    return lines


METHODOLOGY = [
    'Rate CIs: ratio-of-sums, match-cluster delta-method normal 95% intervals; human sides cluster by replay. Nonnegative lower bounds are truncated at zero. Zero events use a rule-of-three-style upper bound. Small groups and rare events have approximate coverage; one-cluster CIs are unavailable. Means have their actual observation n; repeated decisions are not independent matches.',
    'Lane uses own-frame x<9 left, otherwise right. Zones use y<15 enemy side, 15–18 bridge, >18–<24 own front, >=24 own back; own edge is y=32. The broader X-Bow offensive bridge class is y=16–21; deeper bows are defensive. Cells are floor(tile x), floor(tile y). Human coordinates use data-i: rotate team when index=1, opponent when index=0; bot raw bodies rotate only for observer side 0. Bot play/model xy has mirrored x: placement x=18−18*xy[0], y=32*xy[1]. This is checked against actual post-confirmation public X-Bow/Tesla body coordinates; placement alignment errors are reported.',
    'At-play board and elixir use the last PUBLIC decision at or before the confirmed tap attempt, max age 2s for board. Raw elixir is preferred over the play-event forecast; both are retained. Tower HP means include present towers only; destroyed/missing towers are explicit in event receipts. Units are bodies (buildings included at play); Hero Ice Wizard floating-cube duplicates are removed by category/position.',
    'Nominal body elixir = catalog card cost / standard spawn count. It is NOT actual opponent spend: spawned tokens, split cards, evolutions, death spawns, abilities, duplicate identities and transformations can violate it. Unknown IDs are counted and receive no imputed value. Exact enemy committed/killed elixir and exact elixir trades are unavailable.',
    'Push starts when the same observed enemy body moves from y<16 to y>=16 within <=3s, in a lane without an active engagement. Ends after 3s with no enemy on our side in that lane. First-seen intrusions are counted separately and do not masquerade as bridge crossings. Elixir is the first post-crossing public sample, with interval uncertainty exported; flying river crossings are included.',
    'Response = first confirmed own-side card play in that lane (central plays may cover either lane), excluding offensive bridge X-Bows, from crossing until engagement end. Each play goes to at most one engagement. Pre-positioned defence is not a response; no response is censored, not zero. All nominal own spending here excludes abilities. Completed engagements with no unknown entrant value yield trade PROXY = nominal entrant value minus reactive card spend; it does not establish killed value. Engagement totals are assigned to onset phase, so cross-phase spending differs from play-phase totals.',
    'Quiet cycle = cost <=3 and no visible enemy body at y>=12 (our half plus a 4-tile enemy-side buffer). Quiet defence proxy uses that same threat test and an own-side y>=18 Tesla/IceWizard/Knight/Skeletons/Tornado play. Reported elixir is spend flagged by this heuristic, not proven waste. Overcommit proxy = max(0, reactive spend − nominal entrant value − 2); excludes censored/unknown-value engagements.',
    'Tower identification requires card_id=-1 AND fixed tower coordinates within 0.2 tiles; moving unknown bodies also use -1 in these logs. Legacy ID-only scorecard outcomes are retained for comparison. Damage uses monotonically decreasing public HP through tick<6000; absence is accepted only with no later reappearance and two missing decisions (or the terminal closed observation). Remaining princess HP removed automatically after king death is excluded from combat damage. HP increases are flagged. Damage is assigned to the observation phase, so boundary damage may shift by one sampling interval. Crowns derive from princess destruction or three for king destruction. Missing opening/end observations can undercount damage and crowns.',
    'Observed X-Bow lock requires an own X-Bow projectile aimed at a live enemy tower and exactly one own X-Bow alive near that placement. No observed lock means unknown/undetected, not proven no lock. Follow-up damage is total enemy tower HP loss in the next <=20 seconds after placement; locked-target damage is also exported. It includes other attackers/spells and is right-censored near match end. No source-specific damage is claimed.',
    'Own spell target types are deployment-time geometric footprints, not proven targets/hits. Log/Barbarian Barrel use a forward strip; other spells use explicit approximate radii plus tower radius 1 tile or unit margin 0.5. Rocket-on-tower counts include both tower-only and tower+units. Following 8s target tower HP loss is all-source association; true chip and enemy elixir killed are null.',
    'Enemy spell counts are sampled projectile-target/spell-body tower-contact EPISODES, not certified hits or casts. Dedupe same spell/tower until >2s observation gap; multi-tower spells count contacts per tower. Radius/target geometry can misclassify; invisible instant spells can be missed completely. Zero observed Poison/Earthquake/Vines is not zero actual usage. Tower HP drops from first sighting through last sighting+5s are spell-associated; damage intervals are deduplicated across candidates. GoblinBarrel/Graveyard/Clone/Mirror/RoyalDelivery summon/copy contacts are separate and do not qualify damage as direct-spell-associated. Remaining damage is unattributed, NOT certified unit damage. Exact spell-versus-unit damage is unavailable.',
    'Cap occupancy is the observed time with both interval endpoints at >=9.999 elixir and <=2s apart; endpoint-any cap seconds provide a sensitivity measure, not a strict mathematical upper bound if unseen spend/regen happens. No interpolation bridges larger gaps. Multiply by measured phase regen for nominal leaked elixir; no opportunity-cost claim.',
    'The subset surviving to 3x differs from early-ending matches. Paired comparisons require >=30s in each phase and accompany aggregate findings. Checkpoint/fast flags are tags, not randomized treatments. Missing historical pipeline_decisions is interpreted as false by the scorecard convention, with fast_flag_recorded=false explicitly retained. No causal model-quality or policy-change recommendation follows from these measurements.'
]

METRIC_SUPPORT = {
    '1_own_elixir':{'bot':'observed decision/pre-play samples; sampled cap-time bounds and nominal leakage','pro':'whole-match leakage only; no phase elixir observations'},
    '2_cards':{'bot':'confirmed plays per card/minute','pro':'observed plays per card/minute'},
    '3_where':{'bot':'lane/zone and cell placement','pro':'lane/zone and cell placement'},
    '4_board':{'bot':'public bodies, nominal known-card value, tower HP at each play','pro':None},
    '5_push':{'bot':'sampled crossing elixir, response censoring, nominal spend proxy','pro':None},
    '6_xbow':{'bot':'placements; observed projectile lock; all-source following tower damage','pro':'placements only'},
    '7_spells':{'bot':'target geometry and all-source following tower damage','pro':'Rocket tower geometry; card cast rates','actual_tower_chip':None,'enemy_elixir_killed':None},
    '8_cycle':{'bot':'plays/minute and cheap quiet-cycle heuristic','pro':'plays/minute only'},
    '9_waste':{'bot':'quiet-defence and overcommit heuristic counts/spend','pro':None,'proven_wasted_elixir':None},
    '10_tower_damage':{'bot':'public tower HP loss, excluding tiebreak and king-death princess despawn','pro':None},
    '11_trades':{'bot':'nominal crossing-value minus reactive spend proxy','pro':None,'actual_elixir_trades':None},
    '12_crowns':{'bot':'phase destruction observations and final scorecard proxy','pro':'final crowns only'},
    '13_enemy_spells':{'bot':'sampled geometric tower-contact episodes and associated HP loss','pro':'enemy spell cast counts only','certified_hits':None,'spell_damage':None,'unit_damage':None}
}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--since',default='20261008')
    ap.add_argument('--input-manifest',type=Path,help='Reuse the candidate file list from a previous report.json (read-only).')
    args=ap.parse_args()
    dt.datetime.strptime(args.since,'%Y%m%d')
    catalog,names=load_catalog();matches=[];excluded=collections.Counter();input_files=[]
    sources=sorted(p for p in LIVE.glob('live_play_*.jsonl') if p.name[10:18]>=args.since)
    if args.input_manifest:
        manifest=json.loads(args.input_manifest.read_text(encoding='utf8'))
        filenames=[row['file'] for row in manifest['inputs']]
        if any(Path(name).name!=name or not name.startswith('live_play_') for name in filenames):
            raise ValueError('Invalid candidate filename in manifest')
        sources=[LIVE/name for name in filenames]
    # Snapshot list now: files created later belong to the next run.
    with (HERE/'plays.jsonl').open('w',encoding='utf8') as po,(HERE/'pushes.jsonl').open('w',encoding='utf8') as pu,(HERE/'enemy_spells.jsonl').open('w',encoding='utf8') as so:
        for i,f in enumerate(sources):
            data,reason=read_live(f)
            if reason:excluded[reason]+=1;input_files.append({'file':f.name,'excluded':reason});continue
            m=analyse_live(f.name,data,catalog,names,po,pu,so);matches.append(m)
            input_files.append({'file':f.name,'sha256':m['sha256'],'bytes':m['bytes']})
            if i%50==0:print(f'live {i+1}/{len(sources)} selected={len(matches)}',flush=True)
    if not matches:raise RuntimeError('No eligible live matches')
    # Read nearby public trophy observations, without running navigation code.
    trophies=[]
    for f in sorted(LIVE.glob('ladder_nav_*.jsonl')):
        if f.name[11:19]<args.since:continue
        for line in f.open(encoding='utf8',errors='replace'):
            if '"event": "trophies"' not in line:continue
            try:j=json.loads(line)
            except ValueError:continue
            if j.get('trophies_total') is not None:trophies.append((j['t'],j['trophies_total']))
    for m in matches:
        stamp=dt.datetime.strptime(m['id'][10:25],'%Y%m%d_%H%M%S').timestamp()
        near=min(trophies,key=lambda x:abs(x[0]-stamp)) if trophies else None
        m['account_evidence']={'own_tower_max_hp':[4424,7032],'nearby_trophies':near[1] if near and abs(near[0]-stamp)<=7200 else None,'trophy_distance_seconds':abs(near[0]-stamp) if near else None}
    pros=[];pro_errors=collections.Counter();coverage=[];seen=set();pro_files=sorted(PRO.glob('*.json'))
    with (HERE/'pro_plays.jsonl').open('w',encoding='utf8') as po:
        for f in pro_files:
            if f.stem in seen:pro_errors['duplicate_replay']+=1;continue
            try:rows,error,cov=analyse_pro(f,po)
            except (ValueError,KeyError,TypeError) as e:rows=[];error=type(e).__name__;cov={}
            if error:pro_errors[error]+=1
            else:pros.extend(rows);seen.add(f.stem)
            coverage.append({'file':f.name,'error':error,**cov})
    regen={};boundary=collections.defaultdict(list)
    for p in PHASES:
        raw_rates=[v for m in matches for v in m['regen'][p]]
        center=statistics.median(raw_rates) if raw_rates else 0
        # Robust measured baseline, not a hard-coded expected multiplier: remove
        # positive elixir awards/corrections outside 0.02 of the empirical median.
        filtered=[[v for v in m['regen'][p] if abs(v-center)<=0.02] for m in matches]
        means=[statistics.fmean(v) for v in filtered if v]
        s=sample(means);s['n_matches']=len(means);s['n_intervals']=sum(len(v) for v in filtered)
        s['off_baseline_intervals']=len(raw_rates)-s['n_intervals'];s['median_interval_rate']=center if raw_rates else None
        if len(means)>1:
            e=1.96*statistics.stdev(means)/math.sqrt(len(means));s['ci95']=[s['mean']-e,s['mean']+e]
        regen[p]=s
        for m in matches:
            c=m['phases'][p]['counts'];c['nominal_leaked_elixir_lower']=c['cap_seconds_lower']*(s['median_interval_rate'] or 0)
    for m in matches:
        for k,v in m.pop('regen_boundary').items():boundary[k].extend(v)
        m.pop('regen')
    # Reduce per-match samples to sufficient statistics only after aggregate summaries.
    groups=collections.defaultdict(list)
    for m in matches:groups[(m['checkpoint'],m['fast_plays'])].append(m)
    r={'schema_version':1,'created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'since':args.since,
       'selection':{'candidate_files':len(sources),'included':len(matches),'excluded':dict(excluded)},
       'outcomes':dict(collections.Counter(m['outcome'] for m in matches)),'big_losses':sum(m['big_loss'] for m in matches),
       'early_terminal':{'n':sum(m['early_terminal'] for m in matches),'ids':[m['id'] for m in matches if m['early_terminal']]},
       'strict_scorecard_sensitivity':all_splits([dict(m,outcome=m['legacy_scorecard_outcome'],big_loss=m['legacy_scorecard_crowns'][1]-m['legacy_scorecard_crowns'][0]>=2) for m in matches if not m['early_terminal']]),
       'legacy_outcome_disagreements':[{'id':m['id'],'legacy':m['legacy_scorecard_outcome'],'filtered_towers':m['outcome']} for m in matches if m['legacy_scorecard_outcome']!=m['outcome']],
       'bot':all_splits(matches),'pros':{'all_decks':all_splits(pros,True),'xbow':all_splits([m for m in pros if m['xbow']],True)},
       'checkpoint_fast_splits':[{'checkpoint':k[0],'fast_plays':k[1],'n_matches':len(v),'stats':all_splits(v)} for k,v in groups.items()],
       'regen':regen,'boundary_1s_bins':{k:sample(v) for k,v in sorted(boundary.items(),key=lambda kv:int(kv[0]))},
       'paired':paired_comparison(matches),'methodology':METHODOLOGY,'metric_support':METRIC_SUPPORT,
       'pro_coverage':{'files':len(pro_files),'usable_replays':len(seen),'sides':len(pros),'xbow_sides':sum(m['xbow'] for m in pros),'errors':dict(pro_errors),'pages':coverage},
       'inputs':input_files,'data_sources':{'catalog':str(CATALOG),'catalog_sha256':hashlib.sha256(CATALOG.read_bytes()).hexdigest(),'body_counts':str(STATS),'body_counts_sha256':hashlib.sha256(STATS.read_bytes()).hexdigest()}}
    ice=[m for m in pros if m['icebow_like']]
    fallback=[m for m in pros if m['xbow_tesla']]
    comparison=ice if len(ice)>=15 else fallback
    r['pros']['icebow_like']=all_splits(ice,True)
    r['pros']['xbow_tesla']=all_splits(fallback,True)
    r['pros']['comparison']=all_splits(comparison,True)
    r['human_comparison']={'icebow_like_n':len(ice),'xbow_tesla_n':len(fallback),
                           'selected_n':len(comparison),'selected':'icebow_like' if len(ice)>=15 else 'xbow_tesla',
                           'minimum_overlap':5,'minimum_sides':15,'ids':[m['id'] for m in comparison]}
    r['video_metrics']={'bot':vm.summarize(matches),'humans':vm.summarize(comparison,True),
                        'icebow_like_humans':vm.summarize(ice,True),
                        'support':VIDEO_SUPPORT,'methodology':VIDEO_METHODS}
    archetype_path=ROOT/'scratchpad/gauntlet/L74/crapi/census.py'
    r['data_sources']['archetype_mapping']={'path':str(archetype_path),'sha256':hashlib.sha256(archetype_path.read_bytes()).hexdigest(),'order':ARCH_ORDER}
    r['input_snapshot']={'manifest':str(args.input_manifest) if args.input_manifest else None,'candidate_files':len(sources)}
    with (HERE/'video_events.jsonl').open('w',encoding='utf8') as vo:
        for m in matches+pros:
            for e in m['video']['events']:
                vo.write(json.dumps({'match':m['id'],'source':m['source'],**e})+'\n')
            m['video_event_counts']=dict(collections.Counter(e['kind'] for e in m['video']['events']))
            m['video_exposure']=m['video']['exposure']
    r['findings']=findings(r)
    r['video_findings']=video_findings(r)
    for m in matches+pros:m.pop('video')
    for m in matches+pros:
        for s in m['phases'].values():s['samples']={k:sample(v) for k,v in s['samples'].items()}
    r['matches']=matches;r['pro_matches']=pros
    (HERE/'report.json').write_text(json.dumps(r,indent=2,allow_nan=False),encoding='utf8');write_report(r)
    print('PHASE_STATS_OK',len(matches),'bot matches;',len(pros),'human sides',flush=True)
    print('\n'.join(r['findings']),flush=True)


if __name__=='__main__':main()
