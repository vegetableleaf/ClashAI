"""Final tallies from live_results.json + native/sim/counterfactual outputs -> results.json."""
import json, os
from collections import Counter
H = os.path.dirname(os.path.abspath(__file__))
live = json.load(open(os.path.join(H, 'live_results.json')))
logs, flights = live['logs'], live['flights']


def rate(xs):
    xs = [bool(x) for x in xs]
    return dict(n=len(xs), true=sum(xs), rate=round(sum(xs)/len(xs), 3) if xs else None)


fly = [l for l in logs if l['context'] == 'in_flight']
single = [l for l in fly if not l.get('two_lanes') and not l.get('target_center')]
wrong = [l for l in single if not l['lane_vs_target']]
stage = lambda l: 'unknown' if l.get('stage') is None else 'early' if l['stage'] < .33 else 'mid' if l['stage'] < .66 else 'late'
in_flight = dict(
    all=len(fly), two_lane_barrels=sum(bool(l.get('two_lanes')) for l in fly),
    center_target=sum(bool(l.get('target_center')) for l in fly),
    single_lane=rate(l['lane_vs_target'] for l in single),
    single_lane_by_side={s: rate(l['lane_vs_target'] for l in single if l['side'] == s) for s in (0, 1)},
    single_lane_by_stage={k: rate(l['lane_vs_target'] for l in single if stage(l) == k)
                          for k in ('early', 'mid', 'late', 'unknown')},
    single_lane_by_remaining_tiles={k: rate(l['lane_vs_target'] for l in single if lo <= l['remaining_tiles'] < hi)
                                    for k, lo, hi in (('>15', 15, 99), ('8-15', 8, 15), ('<8', 0, 8))},
    target_known=rate(l['target_known'] for l in fly),
    with_matched_landing=rate(l['lane_vs_landing'] for l in single if 'lane_vs_landing' in l),
    would_hit_landing=rate(l['would_hit'] for l in single if 'would_hit' in l),
    wrong_lane_dx_tiles=sorted(round(l['dx_target_tiles'], 1) for l in wrong),
    wrong_cases=[dict(file=l['file'], tick=l['tick'], side=l['side'], log_xy=l['xy'],
                      target_own=[round(v, 3) for v in l['target_own']],
                      model_target_own=[round(v, 3) for v in l.get('model_target_own', [])],
                      model_pos_own=[round(v, 3) for v in l.get('model_pos_own', [])],
                      executed_own_x=round(l['executed_own_x'], 3) if 'executed_own_x' in l else None,
                      stage=None if l.get('stage') is None else round(l['stage'], 2)) for l in wrong])
gnd = [l for l in logs if l['context'] == 'goblins_on_ground']
out = dict(
    live=dict(files=live['summary']['files'], perception={k: live['summary'][k] for k in (
        'flights', 'flights_by_side', 'flights_with_concurrent_targets', 'target_field', 'matched_landing',
        'landing_lane_agree', 'landing_lane_agree_by_side', 'model_rows', 'model_rows_missing',
        'model_target_vs_raw_transform_max_abs', 'normalized_pos_vs_raw_transform_max_abs',
        'model_lane_eq_raw_target_lane', 'lookahead_fraction_along_segment', 'lookahead_perpendicular_offset_max',
        'model_tti_known')},
        target_err_tiles=dict(max=max(live['summary']['target_err_tiles']),
                              median=sorted(live['summary']['target_err_tiles'])[len(live['summary']['target_err_tiles'])//2]),
        logs=dict(total=len(logs), by_context=Counter(l['context'] for l in logs),
                  executed_lane_matches_intent=live['summary']['logs']['exec_lane_matches_intent'],
                  in_flight=in_flight,
                  goblins_on_ground=dict(n=len(gnd), lane=rate(l['lane_vs_goblins'] for l in gnd),
                                         by_side={s: rate(l['lane_vs_goblins'] for l in gnd if l['side'] == s) for s in (0, 1)}))),
    native_training=json.load(open(os.path.join(H, 'native_results.json'))),
    sim=json.load(open(os.path.join(H, 'sim_results.json'))),
    model_counterfactual=json.load(open(os.path.join(H, 'model_counterfactual.json'))),
    model_counterfactual_positive_control=json.load(open(os.path.join(H, 'model_counterfactual_v6.json'))),
    live_fv7_candidate_comparison=(lambda d: dict(files=d['summary']['files'], flights=d['summary']['flights'],
        landing_lane_agree=d['summary']['landing_lane_agree'],
        in_flight_single_lane=rate(l['lane_vs_target'] for l in d['logs'] if l['context'] == 'in_flight'
                                   and not l.get('two_lanes') and not l.get('target_center'))))(
        json.load(open(os.path.join(H, 'live_results_fv7.json')))))
json.dump(out, open(os.path.join(H, 'results.json'), 'w'), indent=1, default=str)
print(json.dumps(out['live']['logs'], indent=1, default=str))
