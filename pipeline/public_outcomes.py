"""Recording-derived labels and acceptance telemetry, never model inputs.

Lead R2c 2026-10-04: area start or last public aim/catalog-speed landing.
Simultaneous damage remains confounded. Sparse/unobserved impacts are unknown.
"""
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
import math
from .dataset_gen import card_key
from .obs_contract import catalog_card_form
from .opp_elixir_count import card_cost
from .public_geometry import constants, in_xbow_range, defensive_xbow

ROCKET_RADIUS = constants()['rocket_radius']


def normalize(frame, source='native'):
    tick=int(frame['tick']); towers=[]; bodies=[]
    for t in frame.get('towers', frame.get('episode',{}).get('crown_towers', [])):
        if isinstance(t,dict):
            towers.append(dict(side=int(t['side']),kind=t['type'],x=t['x'],y=t['y'],hp=t['hp']))
        else:towers.append(dict(side=int(t[0]),kind=t[1],x=t[3],y=t[4],hp=t[5]))
    crown_positions={(t['side'],t['x'],t['y']) for t in towers}
    for e in frame.get('entities',[]):
        if isinstance(e,dict):
            key=card_key(e.get('name',''))
            bodies.append(dict(side=int(e['side']),id=e.get('entity_id'),card=key,x=e['x'],y=e['y'],hp=e['hp']))
        else:
            # Native entity lists duplicate crown towers (kinds12/13). They
            # already have tower labels and must never become troop hits.
            if len(e)>6 and e[6] in (12,13) and (int(e[0]),e[1],e[2]) in crown_positions:continue
            name,_=catalog_card_form(int(e[-2]))
            bodies.append(dict(side=int(e[0]),id=e[-1],card=card_key(name) if name else None,x=e[1],y=e[2],hp=e[4]))
    objects={}
    for kind,field in [('projectiles','projectiles'),('areas','area_effects' if source=='native' else 'effects')]:
        rows=[]
        for e in frame.get('public_objects',frame).get(field,[]) or []:
            if not isinstance(e,dict):continue
            name=e.get('name') if source=='sim' else catalog_card_form(int(e.get('card_id',-1)))[0]
            if name:
                rows.append(dict(card=card_key(name),side=int(e['side']),x=e['x'],y=e['y'],
                    tx=e.get('target_x'),ty=e.get('target_y'),id=e.get('id'),generation=e.get('generation_key',e.get('category')),
                    start_tick=tick-round(e['source_elapsed_ms']/50) if e.get('source_elapsed_ms') is not None else tick))
        objects[kind]=rows
    return dict(tick=tick,towers=towers,bodies=bodies,**objects)


def distance(a,b):return math.hypot(a['x']-b['x'],a['y']-b['y'])
def tower_id(t):return (t['side'],t['kind'],t['x'],t['y'])


def combo_orders(plays,side,cast_tick,landing_tick,point):
    """Rocket-first covers the entire flight; Nado-first uses the 2.5s prior."""
    nados=[q for q in plays if q['side']==side and card_key(q.get('card') or '')=='tornado' and distance(q,point)<=5500]
    return (any(cast_tick<int(q.get('engine_tick',q['tick']))<=landing_tick+2 for q in nados),
            any(int(q.get('engine_tick',q['tick']))<cast_tick and 0<=landing_tick-int(q.get('engine_tick',q['tick']))<=50 for q in nados))


def label_recording(rec, *, normalized=False, xbow_rule=defensive_xbow, xbow_reach=None, reconstruct_rocket_landing=True):
    frames=rec['frames'] if normalized else [normalize(f) for f in rec['frames']+rec.get('play_frames',[])]
    by_tick={f['tick']:f for f in frames}; ticks=sorted(by_tick); frames=[by_tick[t] for t in ticks]
    plays=[dict(p,card=card_key(p['card']),tick=int(p.get('engine_tick',p['tick']))) for p in rec.get('log',[])
           if p.get('accepted') is True and not p.get('skipped') and not p.get('ability') and p.get('card')]
    plays.sort(key=lambda p:p['tick']); rockets=[]; xbows=[]; previous=defaultdict(list)
    def at(t):
        i=bisect_right(ticks,t)-1
        return frames[i] if i>=0 else None
    final=rec.get('final',{})
    if isinstance(final.get('tiebreaker'),bool):tiebreak=final['tiebreaker']
    elif 'tiebreak' in str(final.get('termination_reason','')).lower():tiebreak=True
    elif final.get('terminated') and final.get('tick',6000)<6000:tiebreak=False
    else:tiebreak=None
    for p in plays:
        if p['card'] not in ('rocket','x-bow'):continue
        tick,side=p['tick'],int(p['side']); before=at(tick)
        row=dict(tag=str(rec.get('tag','')),side=side,tick=tick,card=p['card'],x=p['x'],y=p['y'])
        if p['card']=='x-bow':
            own_y=1-p['y']/32000 if side==0 else p['y']/32000
            own_x=p['x']/18000 if side==0 else 1-p['x']/18000
            lane='left' if own_x<.5 else 'right'
            enemies=[t for t in (before or {}).get('towers',[]) if t['side']!=side]
            target=[t for t in enemies if t['kind']=='princess' and (t['x']<9000)==(p['x']<9000)]
            defensive=(defensive_xbow(p,before,xbow_reach) if xbow_reach is not None else xbow_rule(p,before)) if xbow_rule is not None else None
            # Geometric lock reach, measured cells only; no policy action rule.
            lock=any(t['hp']>0 and in_xbow_range(p,t,xbow_reach) for t in enemies)
            row.update(row_y=own_y,lane=lane,lane_state=('alive' if target[0]['hp']>0 else 'dead') if target else 'unknown',
                       defensive_xbow=defensive,offensive_xbow=lock,
                       enemy_princess_down=any(t['kind']=='princess' and t['hp']<=0 for t in enemies),
                       dead_lane_xbow=bool(defensive and target and target[0]['hp']<=0),
                       offensive_lock_cell=[round(own_x,6),round(own_y,6)] if lock else None)
            row['threat']=any(e['side']!=side and e['hp']>0 and distance(e,p)<=constants()['xbow_range']
                for f in frames[bisect_left(ticks,tick):bisect_right(ticks,tick+100)] for e in f['bodies'])
            xbows.append(row);continue
        next_cast=min([q['tick'] for q in plays if q['card']=='rocket' and q['side']==side and q['tick']>tick]+[tick+300])
        relevant=frames[bisect_left(ticks,tick):bisect_left(ticks,next_cast)]
        flight=[];area=[]
        for f in relevant:
            for q in f['projectiles']:
                if q['card']=='rocket' and q['side']==side and q['tx'] is not None and math.hypot(q['tx']-p['x'],q['ty']-p['y'])<1000:
                    flight.append((f['tick'],q))
            for q in f['areas']:
                if q['card']=='rocket' and q['side']==side and q.get('start_tick',f['tick'])>=tick and distance(q,p)<=ROCKET_RADIUS:area.append((q.get('start_tick',f['tick']),q))
        landing=area[0] if area else flight[-1] if flight else None
        landing_source='area_start' if area else 'last_projectile' if flight else 'unobserved'
        if reconstruct_rocket_landing and flight and not area:
            from .projectile_observation import constant_projectile_speeds
            last,q=flight[-1];speed=constant_projectile_speeds()['rocket']
            landing=(last+math.ceil(math.hypot(q['tx']-q['x'],q['ty']-q['y'])/speed),dict(q,x=q['tx'],y=q['ty']))
            landing_source='public_aim_catalog_speed'
        row.update(landing_tick=landing[0] if landing else None,landing_source=landing_source,
                   tower_rocket=None,defensive_rocket=None,troop_hits=None,nominal_elixir_hit=None,tower_hits=[],
                   rocket_then_tornado=None,tornado_then_rocket=None,tiebreak=tiebreak,
                   phase='overtime' if tick>=3600 else 'regulation',seconds_left=max(0,((6000 if tick>=3600 else 3600)-tick)*.05))
        if landing:
            lt,point=landing; lo=at(lt-1); hi_index=bisect_left(ticks,lt)
            hi=frames[hi_index] if hi_index<len(frames) else None
            row['landing_point']=[point['x'],point['y']]
            # With K>1, do not invent a +/-2-tick HP observation.
            known=lo is not None and hi is not None and hi['tick']-lo['tick']<=10
            row['hp_window_known']=known
            row['hp_confirmation_within_two_ticks']=known and lt-lo['tick']<=2 and hi['tick']-lt<=2
            if known:
                hits=[];after={tower_id(t):t for t in hi['towers']}
                for t in lo['towers']:
                    if t['side']==side or distance(point,t)>ROCKET_RADIUS or t['hp']<=0:continue
                    end=after.get(tower_id(t))
                    if end is not None:
                        key=(side,tower_id(t));prior=previous[key]
                        hits.append(dict(tower=list(tower_id(t)),hp_before=t['hp'],hp_drop=t['hp']-end['hp'],hp_confirmed=end['hp']<t['hp'],
                                         finish=end['hp']<=0,prior_rockets=len(prior),gap_s=(tick-prior[-1])*.05 if prior else None))
                        prior.append(tick)
                bodies={(e['side'],e['id']):e for e in hi['bodies']}; troop=[]
                for e in lo['bodies']:
                    if e['side']==side or e['hp']<=0:continue
                    end=bodies.get((e['side'],e['id']))
                    fraction=(lt-lo['tick'])/(hi['tick']-lo['tick'])
                    position=dict(x=e['x']+fraction*(end['x']-e['x']),y=e['y']+fraction*(end['y']-e['y'])) if end else e
                    if distance(position,point)>ROCKET_RADIUS:continue
                    troop.append(dict(card=e['card'],entity_id=e['id'],hp_drop=e['hp']-end['hp'] if end else None,
                                      disappeared=end is None,position_interpolated=end is not None,
                                      nominal_elixir=card_cost((e['card'] or '').replace('-','_'))))
                row.update(tower_hits=hits,tower_rocket=bool(hits),troop_hits=troop,
                           nominal_elixir_hit=sum(e['nominal_elixir'] or 0 for e in troop),defensive_rocket=bool(troop))
            row['rocket_then_tornado'],row['tornado_then_rocket']=combo_orders(plays,side,tick,lt,point)
        crowns=[sum(t['side']!=s and t['kind']=='princess' and t['hp']<=0 for t in (before or {}).get('towers',[])) for s in (side,1-side)]
        row['crowns_before']=crowns
        row['tiebreak_cycle_context']=crowns[0]==crowns[1] and tick>=3000
        rockets.append(row)
    return dict(rockets=rockets,xbows=xbows,plays=plays)


def summarize(rec, side, *, normalized=False, xbow_rule=defensive_xbow, xbow_reach=None, labels=None):
    if labels is None:labels=label_recording(rec,normalized=normalized,xbow_rule=xbow_rule,xbow_reach=xbow_reach)
    rockets=[r for r in labels['rockets'] if r['side']==side]; bows=[r for r in labels['xbows'] if r['side']==side]
    plays=[p for p in labels['plays'] if p['side']==side]; ticks=max((f['tick'] for f in rec['frames']),default=0)
    def rate(num,den):return dict(n=num,denominator=den,rate=num/den if den else None)
    known=[r for r in rockets if r['tower_rocket'] is not None]
    barrels=[p for p in labels['plays'] if p['side']!=side and p['card'] in ('goblin-barrel','skeleton-barrel')]
    frames=rec['frames'] if normalized else [normalize(f) for f in rec['frames']]
    preempt=0;observed=0
    for barrel in barrels:
        end=min([p['tick'] for p in barrels if p['card']==barrel['card'] and p['tick']>barrel['tick']]+[ticks+1])
        ts=[f['tick'] for f in frames if barrel['tick']<=f['tick']<end and
            (any(q['card']==barrel['card'] and q['side']!=side for q in f['projectiles']) or
             (barrel['card']=='skeleton-barrel' and any(e['card']=='skeleton-barrel' and e['side']!=side and e['hp']>0 for e in f['bodies'])))]
        if ts:
            observed+=1
            preempt+=any(p['card']=='the-log' and min(ts)<=p['tick']<=max(ts)+10 for p in plays)
    diversity={}
    for bow in bows:
        if bow['offensive_lock_cell']:
            group=bow['lane']+':'+bow['lane_state']+':princess_down='+str(bow['enemy_princess_down'])
            diversity.setdefault(group,Counter())[tuple(bow['offensive_lock_cell'])]+=1
    diversity={key:dict(distinct_cells=len(counts),placements=sum(counts.values()),
        entropy_bits=-sum((n/sum(counts.values()))*math.log2(n/sum(counts.values())) for n in counts.values()))
        for key,counts in diversity.items()}
    return dict(schema='public_behaviour_v1',accepted_plays=len(plays),accepted_per_min=len(plays)/(ticks*.05/60) if ticks else None,
        rocket_share=rate(len(rockets),len(plays)),tower_rocket_share=rate(sum(bool(r['tower_rocket']) for r in known),len(known)),
        unknown_rocket_impacts=len(rockets)-len(known),finish_offs=sum(h['finish'] for r in known for h in r['tower_hits']),
        tower_hit_hp_confirmation=rate(sum(h['hp_confirmed'] for r in known for h in r['tower_hits']),sum(len(r['tower_hits']) for r in known)),
        multi_rocket_cycles=sum(h['prior_rockets']>0 for r in known for h in r['tower_hits']),
        defensive_rockets=sum(bool(r['defensive_rocket']) for r in known),
        rocket_then_tornado=sum(bool(r['rocket_then_tornado']) for r in rockets),
        tornado_then_rocket=sum(bool(r['tornado_then_rocket']) for r in rockets),
        xbow_rows=dict(Counter(str(r['row_y']) for r in bows)),xbow_lanes=dict(Counter(r['lane'] for r in bows)),
        xbow_dead_lane=rate(sum(r['dead_lane_xbow'] for r in bows),sum(r['enemy_princess_down'] for r in bows)),
        offensive_lock_cells=sorted({tuple(r['offensive_lock_cell']) for r in bows if r['offensive_lock_cell']}),
        offensive_diversity_by_lane_state=diversity,
        defensive_xbows=sum(bool(r['defensive_xbow']) for r in bows) if xbow_rule else None,
        defensive_xbow_label_status='lead_rule' if xbow_rule else 'awaiting_LEAD_RULINGS',
        preemptive_log=rate(preempt,len(barrels)),barrels_with_observed_flight=observed,
        ability_presses=dict(Counter(p.get('card','unknown') for p in rec.get('log',[]) if p.get('ability') and p.get('accepted') and p['side']==side)),
        label_limitations='Lead R2b interpolated geometry; HP confirmation is reported separately. Disappeared troops use last visible position.')
