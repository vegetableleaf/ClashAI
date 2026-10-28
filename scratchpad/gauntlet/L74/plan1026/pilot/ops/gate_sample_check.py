"""LOOP-OPS: live --gate-sample vs the trainer's sampled gate on the same recorded live states.

    python -B gate_sample_check.py CKPT T SEEDS OUT.json      (e.g. CLXIII 0.1 0,1,2)

Per decision seed: test_decide_identity's 4 recorded CLXIII live matches through live_play.load_pilot with --gate-sample T
(every other option = the logged start event's). At each decision the live draw (GenPilot.last_gate_draw: z, tau, p_b, fire)
is recorded, and the SAME row goes through the trainer's gate: decision_options.decide(decode='sample', sampler T_gate = T,
tau_r = that row's phase tau, a separate seeded rng) on the row's gate logit. Reports: max |p_b live - p_b trainer|, both
fire rates, the expected rate mean(p_b) and z-scores (binomial: var = sum p_b (1 - p_b)).
"""
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(ROOT))


def trainer_gate(z, tau_r, T, rng):
    """The trainer's gate on one row: decision_options.decide decode 'sample' (no rules), card / cell stubs."""
    import torch
    from pipeline.decision_options import DecisionOptions, decide, sample_rules
    heads = {'gate': torch.tensor([z], dtype=torch.float32), 'card': torch.zeros(1, 4)}
    out = decide(heads, np.array([1 / (1 + math.exp(-z))]), np.array([[True, False, False, False]]), np.array([False]),
                 tau=float(tau_r), options=sample_rules(DecisionOptions()), rngs=[None], decode='sample',
                 sampler={'tau_r': np.array([tau_r]), 'T': 0.5, 'T_gate': float(T), 'heads': frozenset(('gate',)),
                          'rngs': [rng]},
                 cell_logits=lambda ids, slots: torch.zeros(len(ids), 2304))[0]
    return bool(out['play']), float(out['p_gate']) if 'p_gate' in out else None


def main(ckpt, T, seeds, out):
    import torch
    from pipeline.tests.test_decide_identity import LIVE_DIR, LOGS, read_log
    torch.set_num_threads(1)
    sys.path.insert(0, str(LIVE_DIR))
    import live_play as lp
    T, rows = float(T), []
    for seed in [int(s) for s in seeds.split(',')]:
        trng = np.random.default_rng([seed, 0x7A1])               # the trainer arm's own stream
        for name in LOGS:
            start, ev = read_log(LIVE_DIR / name)
            a = SimpleNamespace(device='cpu', ckpt=str(ROOT / ckpt), tau=start['tau'], no_opp_counter=not start['opp_counter'],
                                extrapolate=start['extrapolate'], decision_seed=seed, public_audit=False,
                                own_effects=start['own_effects'], hero_ability_spec=start['hero_ability_spec'],
                                identity_ext='on' if start['identity_ext'] in (True, 'on') else 'off',
                                afford_ticks=start['afford_ticks'], reader='merged', gate_sample=T,
                                cue_inputs='on' if (start.get('cue_inputs') or {}).get('active') else 'off',
                                iw_press=start['iw_press'], iw_press_head_decode=start['iw_press_head_decode'])
            pilot = lp.load_pilot(a, dict(start['decision_options']))[1]
            pilot.reset_match()
            f = None
            for e in ev:
                if e[0] == 'frame':
                    f = e[1]
                    pilot.observe(f)
                elif e[0] == 'decision' and f is not None and f['game_tick'] == e[1]:
                    pilot.decide(f)
                    g = pilot.last_gate_draw
                    if g is not None:
                        fire_t, _ = trainer_gate(g['z'], g['tau'], T, trng)
                        z_tau = (g['z'] - math.log(g['tau'] / (1 - g['tau']))) / T
                        rows.append(dict(seed=seed, log=name, tick=e[1], p_b=g['p_b'], fire=g['fire'], fire_t=fire_t,
                                         p_b_formula=1 / (1 + math.exp(-z_tau)) if z_tau > -700 else 0.0))
                elif e[0] == 'confirmed' and None not in e[2:]:
                    pilot.record_play(e[2], e[3], e[4], e[1] * 0.05)
                elif e[0] == 'ability':
                    pilot.record_ability(e[1], e[2])
    p = np.array([r['p_b'] for r in rows])
    n, var = len(rows), float((p * (1 - p)).sum())
    fl, ft = sum(r['fire'] for r in rows), sum(r['fire_t'] for r in rows)
    res = dict(ckpt=ckpt, T=T, seeds=seeds, draws=n, expected_fires=float(p.sum()), live_fires=fl, trainer_fires=ft,
               live_rate=fl / n, trainer_rate=ft / n, expected_rate=float(p.mean()),
               z_live=(fl - p.sum()) / math.sqrt(var), z_trainer=(ft - p.sum()) / math.sqrt(var),
               z_live_minus_trainer=(fl - ft) / math.sqrt(2 * var),
               max_abs_pb_vs_formula=max(abs(r['p_b'] - r['p_b_formula']) for r in rows),
               rows_with_0_01_lt_pb_lt_0_99=int(((p > .01) & (p < .99)).sum()))
    Path(out).write_text(json.dumps(dict(summary=res, rows=rows)), encoding='utf-8')
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main(*sys.argv[1:])
