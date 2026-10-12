"""NEWSIM paired instrument: search_s0 plain policy, frozen sampled opponents.

The old and new evaluated models both toggle fast plays. The fixed CAL/P2
opponent keeps the same sampled policy in both comparisons, as in LIVECAL.
Public measurement receipts are saved in every match, never fed into policies.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from scratchpad.gauntlet.L74.weekend.adaptive import driver as D
from scratchpad.gauntlet.L74.newsim import metrics

GEN = 'icebow/data/pipeline/gen_v1_s0/gen_s0.pt'


def worker_config(checkpoint, census, pool, fast):
    from pipeline.decision_options import DecisionOptions
    # Frozen S2/CAL live bundle, copied from ADAPT's explicit LIVE_FLAGS.
    opts = DecisionOptions(xbow_class='class_sample', xbow_class_floor=.3, tau_phase=(.35, .45, .55),
        spell_aim='rocket_area', gate_decode='hazard_below_tau', gate_hazard_min_elixir=9,
        log_aim='log_barrel', lethal_rocket='ot_behind', xbow_dead_lane='block', gate_hazard_threatened=2,
        rocket_dead_target='block', tau_threatened=.2, lethal_log='on')
    return dict(threads=1, device='cpu', gen=str(checkpoint), opps=['gen'],
        opp_gen=str(D.CAL_C) if pool == 'CAL' else GEN, opp_policy='sample', opp_T=.1 if pool == 'CAL' else .3,
        tail_cap=7200, forms_mode='deck', tau_plain=.35, decision_options=asdict(opts),
        behaviour_telemetry=True, own_effects=True, pipeline_decisions=fast, pipeline_tau_delta=0.0,
        hero_abilities=True, ability_policy='v2', horizon=100, interval=20, topk=2, cells=2,
        search_min_p=.0, rollout_self='idle', scorer='v1', census=str(census))


def init_worker(cfg):
    from pipeline import search_s0 as S
    S._init_worker(cfg)


def play(job):
    seed, cards = job
    from pipeline import search_s0 as S
    run = S._W['runner']
    match = run.setup('gen', seed, cards)
    result = run.play('plain', match)
    telemetry = match.env.behaviour_telemetry
    result['phase_stats'] = metrics.measure(telemetry.frames, telemetry.plays, match.learner.side)
    if 'pipeline_decisions' in run.last_result:
        result['pipeline_decisions'] = run.last_result['pipeline_decisions']
    return result


def jobs(census, start, games=480):
    import numpy as np
    from pipeline.rl_royale import league_decks, deck_weights
    decks = league_decks(census)
    # Already weighted once to 60%; retain those weights, rather than applying
    # search_s0's sqrt/floor a second time. Fixed decks: no policy-dependent redraw.
    p = deck_weights([d['sides'] for d in decks], 1, 0)
    return [(s, decks[int(np.random.default_rng([s, 69]).choice(len(decks), p=p))]['engine'])
            for s in range(start, start+games)]


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--census', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--pool', choices=['CAL', 'P2'], required=True)
    p.add_argument('--fast', action='store_true')
    p.add_argument('--workers', type=int, required=True)
    p.add_argument('--start', type=int, required=True)
    a = p.parse_args(argv)
    if not 1 <= a.workers <= 24:
        p.error('workers must be 1..24')
    from pipeline.royale_runtime import activate
    stamp = activate()
    if stamp.get('runtime_id') != '20261012-linux':
        raise ValueError('NEWSIM requires the pinned new Linux runtime')
    cfg = worker_config(a.checkpoint, a.census, a.pool, a.fast)
    todo = jobs(a.census, a.start)
    a.out.mkdir(parents=True, exist_ok=False)
    (a.out/'run.json').write_text(json.dumps(dict(config=cfg, runtime=stamp, jobs=todo), indent=2, default=str)+'\n')
    import multiprocessing as mp
    with (a.out/'matches.jsonl').open('w') as f:
        with mp.get_context('spawn').Pool(a.workers, initializer=init_worker, initargs=(cfg,)) as pool:
            for row in pool.imap_unordered(play, todo):
                if row.get('wall_truncated') or row.get('skipped'):
                    raise RuntimeError('incomplete evaluation game')
                f.write(json.dumps(row)+'\n')
                f.flush()
    (a.out/'COMPLETE').write_text('480 games\n')


if __name__ == '__main__':
    main()
