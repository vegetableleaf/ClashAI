"""Offline public-body inference. Estimates are never certified deploy timestamps.

Uses future PUBLIC observations to reconstruct a replay, not as model inputs.
No game state, opponent hand, opponent elixir or network is consulted.
"""
from collections import defaultdict
from math import hypot

# These cards expose child bodies under the parent's public card ID. Relative HP
# separates roles, not levels: require a >2.2x difference within this match/side.
PARENTS = {'GoblinDrill', 'GoblinHut', 'Tombstone', 'GoblinGiant', 'Witch',
           'DarkWitch', 'Golem', 'LavaHound', 'BarbarianHut', 'SkeletonBalloon',
           'BattleRam', 'GoblinCage', 'Goblinstein', 'RamRider', 'FirespiritHut',
           'ElixirGolem'}
TOKEN_PARENTS = {'Skeletons': {'Tombstone', 'Witch', 'SkeletonBalloon', 'SkeletonKing'},
                 'Goblins': {'GoblinDrill', 'GoblinGiant'},
                 'SpearGoblins': {'GoblinHut', 'GoblinGiant'},
                 'Bats': {'DarkWitch', 'SkeletonKing'},
                 'Barbarians': {'BarbarianHut', 'BattleRam'},
                 'FireSpirits': {'FirespiritHut'}}
CHARGERS = {'Prince', 'DarkPrince', 'BattleRam', 'RamRider'}


def distance(a, b):
    return hypot(a['x']-b['x'], a['y']-b['y'])


def public_tracks(source, catalog):
    tracks, last, counts = {}, {}, defaultdict(int)
    previous = None
    for frame in source['frames']:
        tick = frame['tick']
        for b in frame['bodies']:
            if b.get('tower'):
                continue
            local = (b['card_id'], b['side'], b['key'])
            if local not in last or tick-last[local][0] > 60:
                counts[local] += 1
                key = ':'.join(map(str, local))+':'+str(counts[local])
                c = catalog.get(b['card_id'], {})
                tracks[key] = dict(key=key, name=c.get('display_name', str(b['card_id'])),
                                   card_id=b['card_id'], side=b['side'], previous_tick=previous,
                                   rows=[])
            else:
                key = last[local][1]
            tracks[key]['rows'].append(dict(tick=tick, **b))
            last[local] = (tick, key)
        previous = tick
    return list(tracks.values())


def stationary_start(track):
    rows = track['rows']
    return len(rows) > 1 and rows[1]['tick']-rows[0]['tick'] <= 40 and distance(rows[0], rows[1]) <= 80


def fast_travel(track):
    return any(distance(a, b)/(b['tick']-a['tick']) > 150
               for a, b in zip(track['rows'][:8], track['rows'][1:8]))


def role_limits(source, catalog):
    """Public within-match HP scale for broad parent/child matching roles.

    Not a level estimator. A full parent/child mechanic test still needs native
    character identity, which v2 sanitized away. Do not fit on SIM error/HP.
    """
    maxima = defaultdict(int)
    for frame in source['frames']:
        for b in frame['bodies']:
            name = catalog.get(b['card_id'], {}).get('display_name')
            if not b.get('tower') and name in PARENTS:
                maxima[name, b['side']] = max(maxima[name, b['side']], b['max_hp'])
    return {(cid, side): (c['display_name'], maxima[c['display_name'], side])
            for cid, c in catalog.items() for side in (0, 1)
            if maxima.get((c['display_name'], side))}


def repair_injections(source, catalog):
    """Return row-indexed replacements and auditable exclusions for saved proxies.

    The original extractor's point is the first body, NOT a formation centroid.
    Rejoin it exactly (within 2 millitiles for coordinate rounding); do not attach
    an arbitrary nearest older body. Non-identifiable states are quarantined.
    """
    tracks = public_tracks(source, catalog)
    maxima = defaultdict(int)
    for t in tracks:
        k = t['side'], t['name']
        maxima[k] = max(maxima[k], max(b['max_hp'] for b in t['rows']))
    replacements, receipts = {}, []
    used_diggers = set()
    for i, play in enumerate(source['plays']):
        if play['side'] == source['observer_side']:
            continue
        receipt = dict(row=i, name=play['name'], original={k: play[k] for k in ('tick', 'x', 'y')},
                       status='excluded', reason=None)
        receipts.append(receipt)
        candidates = [t for t in tracks if t['side']==play['side'] and t['name']==play['name']
                      and t['rows'][0]['tick']==play['tick'] and distance(t['rows'][0], play)<=2]
        if len(candidates) != 1:
            receipt['reason'] = 'proxy_body_not_uniquely_identified'; continue
        t = candidates[0]; first = t['rows'][0]
        receipt.update(track=t['key'], observed_card_id=t['card_id'], first_seen_tick=first['tick'])
        name = t['name']; c = catalog.get(t['card_id'], {})
        if name in PARENTS and first['max_hp'] < .45*maxima[t['side'], name]:
            receipt['reason'] = 'parent_id_child_body'; continue
        if name.startswith('MergeMaiden_'):
            receipt['reason'] = 'variant_or_transform_not_certified_play'; continue
        if c.get('type') == 'building' and name != 'GoblinDrill' and not stationary_start(t):
            receipt['reason'] = 'moving_or_unresolved_building_body'; continue
        parents = TOKEN_PARENTS.get(name, set())
        if any(p['side']==t['side'] and p['name'] in parents and
               any(0 <= first['tick']-b['tick'] <= 40 and distance(first, b)<=2500 for b in p['rows'])
               for p in tracks):
            receipt['reason'] = 'spawn_or_play_ambiguous_near_parent'; continue
        timing_track, target = t, first
        reason = 'visibility_interval_midpoint'
        if name == 'GoblinDrill':
            if not fast_travel(t):
                receipt['reason'] = 'drill_surface_or_child_not_new_deploy'; continue
            # Traveler -> first immobile intermediate-HP body. A goblin (low HP)
            # and a later evolved re-burrow are not new card deployments.
            if t['key'] in used_diggers:
                receipt['reason'] = 'drill_relocation_not_new_deploy'; continue
            surfaces = [p for p in tracks if p['side']==t['side'] and p['name']==name
                        and 0 < p['rows'][0]['tick']-t['rows'][-1]['tick'] <= 40
                        and .45*first['max_hp'] <= p['rows'][0]['max_hp'] < .8*first['max_hp']
                        and stationary_start(p) and distance(t['rows'][-1], p['rows'][0])<=6000]
            if len(surfaces) != 1:
                receipt['reason'] = 'drill_destination_unresolved'; continue
            surface = surfaces[0]; target = surface['rows'][0]
            receipt['surface_tick'] = target['tick']
            receipt['surface_track'] = surface['key']
            # Evolution relocation within the same surface lifespan is excluded.
            for p in tracks:
                if p['name']==name and p['side']==t['side'] and fast_travel(p) and p is not t:
                    start = p['rows'][0]
                    if 0 <= start['tick']-surface['rows'][-1]['tick'] <= 40 and distance(start, surface['rows'][-1])<=2500:
                        used_diggers.add(p['key'])
            reason = 'drill_travel_to_surface_target'
        elif name == 'Miner':
            # An emerged miner alone gives neither launch time nor tunnel delay.
            receipt['reason'] = 'miner_tunnel_deploy_unobserved'; continue
        elif name in CHARGERS and not stationary_start(t):
            receipt['reason'] = 'charger_initial_motion_or_charge_unresolved'; continue
        prev = timing_track['previous_tick']
        if prev is None or first['tick']-prev > 40:
            receipt['reason'] = 'opening_or_gap_deploy_unbounded'; continue
        low, high = prev+1, first['tick']
        tick = (low+high)//2
        form = 2 if t['card_id']==c.get('hero_form_id') else int(t['card_id']==c.get('evolution_form_id'))
        repaired = dict(play, tick=tick, x=target['x'], y=target['y'], observed_form=form,
                        inference=dict(method=reason, visibility_tick_interval=[low, high],
                                       first_seen_tick=first['tick'], public_track=t['key'],
                                       deploy_tick_exact=False, initial_state_exact=False))
        receipt.update(status='retained', reason=reason, replacement={k: repaired[k] for k in ('tick','x','y')},
                       observed_form=form, visibility_tick_interval=[low, high])
        replacements[i] = repaired
    return replacements, receipts
