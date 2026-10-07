"""Combine results_partA.json + results_recorded_identity.json + tests.out into results.json."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
a = json.loads((HERE / 'results_partA.json').read_text())
b = json.loads((HERE / 'results_recorded_identity.json').read_text())
lat = {k: v['latency_ms'] for k, v in a['checkpoints'].items()}
r1e = lat['R1e_fv4']['median']
C = a['checkpoints']
out = dict(
    note='Probe machine loaded (GPU chain running); below-normal priority, 4 threads, pilots interleaved per frame: '
         'read latencies RELATIVE to R1e.',
    partA=dict(
        frames=a['frames'], latency_ms=lat, median_ratio_vs_R1e={k: round(v['median'] / r1e, 3) for k, v in lat.items()},
        live_reference_20261006_logs=dict(logs=99, decisions=30821, median=44.0, p95=144.0, max=3319),
        fv5_identity=dict(
            from_engine_feature_versions={k: v['from_engine_feature_versions'] for k, v in C.items()},
            injected_card_id_minus1_cursed_hog=a['injected_cursed_hog_opponent_units_at_x_0_5'],
            raw_hero_duplicate_objects=a['raw_hero_duplicate_objects'],
            hero_duplicates_reaching_from_engine={k: v['hero_dupes_reaching_to_observe'] for k, v in C.items()},
            hero_duplicates_reaching_public_observer={k: v['hero_dupes_reaching_public_observer'] for k, v in C.items()},
            residual='21/1095 frames (passive_v2_raw 10-06, ticks 3148+) hold two same-side 203000023 objects ~2.8 tiles '
                     'apart (hp 482/911 and 911/911, kind 15/14): outside the 500-unit dedupe radius; one pair came '
                     'within 500 after extrapolation'),
        fv6_projectiles={k: {x: v[x] for x in (
            'decisions_with_raw_projectiles', 'decisions_with_raw_named_projectiles',
            'decisions_with_model_projectile_tokens', 'decisions_with_known_target_tokens',
            'decisions_branch_saw_valid_projectiles', 'decisions_branch_valid_count_equals_known_target_tokens',
            'spread_weight_abs_sum')} for k, v in C.items() if v['feature_version'] >= 6}),
    partB_recorded=dict(default_compared=b['default_compared'], default_mismatches=b['default_mismatches'],
                        options=b['options'], pilots=b['pilots'],
                        note='old = live_gen_v2.py at 821ac34 (= main checkout); recorded frames hold only 2x/OT ticks '
                             '(phase_rows); 1x is covered by unit tests'),
    tests=(HERE / 'tests.out').read_text().strip().splitlines()[-3:])
(HERE / 'results.json').write_text(json.dumps(out, indent=1))
print(json.dumps(out['partA']['median_ratio_vs_R1e']))
