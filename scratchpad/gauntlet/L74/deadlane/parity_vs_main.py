"""NEW-vs-main default parity for --xbow-dead-lane (allow = byte-identical). Two processes, one per code version:

    python scratchpad/gauntlet/L74/deadlane/parity_vs_main.py new  OUT_NEW.json
    python scratchpad/gauntlet/L74/deadlane/parity_vs_main.py main OUT_MAIN.json   # main = git 0a777d5 sources
    python scratchpad/gauntlet/L74/deadlane/parity_vs_main.py compare OUT_NEW.json OUT_MAIN.json

'main' execs main's pipeline/decision_options.py and pipeline/live_gen_v2.py (git show) as those modules before
anything imports them; every other module is shared (unchanged by this branch). Records: SIM decide_batch on random
batches (deployed bundle and other option sets, enemy princesses alive/dead, lethal states, Goblin Barrel tokens)
and live GenPilot.decide on the real reader frame (both observer sides, dead princesses, 1x/2x/OT), each with the final
decision-RNG states."""
import json, os, subprocess, sys, types

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
sys.path.insert(0, ROOT)
MAIN = '0a777d5'


def load_main():
    import pipeline
    for mod in ('decision_options', 'live_gen_v2'):
        src = subprocess.run(['git', 'show', f'{MAIN}:pipeline/{mod}.py'], cwd=ROOT, capture_output=True, text=True,
                             check=True).stdout
        m = types.ModuleType(f'pipeline.{mod}'); m.__package__ = 'pipeline'; m.__file__ = f'<main {mod}>'
        sys.modules[m.__name__] = m; setattr(pipeline, mod, m)
        exec(compile(src, m.__file__, 'exec'), m.__dict__)


def canon(x):
    import numpy as np, torch
    if isinstance(x, dict):
        return {str(k): canon(v) for k, v in sorted(x.items(), key=lambda kv: str(kv[0])) if k != 'bs'}
    if isinstance(x, (list, tuple)):
        return [canon(v) for v in x]
    if torch.is_tensor(x):
        return canon(x.tolist())
    if isinstance(x, np.ndarray):
        return canon(x.tolist())
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return repr(float(x))
    return x


def sim_cases():
    import numpy as np, torch
    from pipeline.decision_options import DecisionOptions, decide_batch
    from pipeline.tests.test_lethal_rocket import towers
    bundle = dict(xbow_class='class_sample', xbow_class_floor=.3, tau_phase=(.35, .45, .55), spell_aim='rocket_area',
                  gate_decode='hazard_below_tau', gate_hazard_min_elixir=9.0, log_aim='log_barrel', lethal_rocket='ot')
    option_sets = [bundle, dict(bundle, xbow_class='argmax'), dict(xbow_class='class_sample', xbow_class_floor=.2),
                   dict(spell_aim='rocket_area'), dict(card_choice='filtered'), dict(lethal_rocket='ot')]
    names_pool = [['knight', 'xbow', 'rocket', 'tesla'], ['the-log', 'Xbow', 'Rocket', 'tornado'],
                  ['skeletons', 'ice-wizard', 'x_bow', 'log']]
    out = []
    for oi, kw in enumerate(option_sets):
        options = DecisionOptions(**kw)
        for trial in range(25):
            g = torch.Generator().manual_seed(1000 * oi + trial)
            B = 16
            nrng = np.random.default_rng(1000 * oi + trial)
            heads = {'card': torch.randn(B, 4, generator=g) * 2}
            cells = torch.randn(B, 4, 2304, generator=g) * 3

            class M:
                gid = {'goblin-barrel': 7}

                def cell_logits(self, enc, slot):
                    return cells[enc['i'].long(), slot]
            p = nrng.random(B)
            allowed = nrng.random((B, 4)) < .8
            stalled = nrng.random(B) < .1
            t_sec = nrng.choice([10., 119.9, 120., 150., 179.99, 180., 230.], B)
            alive = [tuple(bool(a) for a in (True, nrng.random() < .7, nrng.random() < .7)) for _ in range(B)]
            lethal = [(towers(int(s), int(nrng.choice([0, 300, 453, 1092, 4000])), int(nrng.choice([0, 453, 4000]))),
                       int(s), bool(nrng.random() < .2)) for s in nrng.integers(0, 2, B)]
            proj = [np.array([[7, 1, .3, .4, nrng.random(), nrng.random(), 0, 0]] * int(nrng.integers(0, 2)) +
                             [[3, 0, .5, .5, -1, -1, 0, 0]], dtype=np.float32) for _ in range(B)]
            names = [names_pool[int(nrng.integers(0, 3))] for _ in range(B)]
            rngs = [np.random.default_rng([oi, trial, r]) for r in range(B)]
            d = decide_batch(M(), {'i': torch.arange(B)}, heads, p, allowed, stalled, tau=.35, device='cpu',
                             options=options, rngs=rngs, card_names=names, t_sec=list(t_sec), enemy_alive=alive,
                             grid='lattice', projectiles=proj, step_s=.5, elixir=list(nrng.random(B) * 10),
                             enemy_units=list(nrng.integers(0, 3, B)), lethal=lethal)
            out.append(dict(kind='sim', options=oi, trial=trial, decisions=canon(d),
                            rng=[canon(r.bit_generator.state) for r in rngs]))
    return out


def live_cases():
    import numpy as np, torch
    from pipeline.decision_options import DecisionOptions
    from pipeline.tests.test_live_decision_options import icebow_frame, pilot
    bundle = dict(xbow_class='class_sample', xbow_class_floor=.3, tau_phase=(.35, .45, .55), spell_aim='rocket_area',
                  gate_decode='hazard_below_tau', gate_hazard_min_elixir=9.0, lethal_rocket='ot')   # log_aim: no fv>=4 stub
    out = []
    for oi, kw in enumerate([bundle, {}, dict(xbow_class='class_sample', xbow_class_floor=.2)]):
        for side in (0, 1):
            for drop in (None, 3500, 14500):
                for tick in (1000, 2600, 3700):
                    for gate_p in (.2, .4, .6):
                        for seed in range(3):
                            g = torch.Generator().manual_seed(seed * 7 + int(gate_p * 10))
                            cell = torch.randn(2304, generator=g) * 3
                            q = pilot(DecisionOptions(**kw), gate_p, cell=cell, seed=seed)
                            q._hazard_prev = (tick - 40, True)
                            d = q.decide(icebow_frame(tick, side, drop))
                            out.append(dict(kind='live', options=oi, side=side, drop=drop, tick=tick, p=gate_p,
                                            seed=seed, decision=canon(d), rng=canon(q.rng_decisions.bit_generator.state)))
    return out


def main():
    mode = sys.argv[1]
    if mode == 'compare':
        a, b = (json.load(open(f)) for f in sys.argv[2:4])
        diff = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        print(f'records new {len(a)} main {len(b)}; sim {sum(r["kind"] == "sim" for r in a)} live '
              f'{sum(r["kind"] == "live" for r in a)}; plays {sum(d["play"] for r in a if r["kind"] == "sim" for d in r["decisions"]) + sum(r["decision"]["play"] for r in a if r["kind"] == "live")}; '
              f'differing {len(diff)} {diff[:5]}')
        return 0 if len(a) == len(b) and not diff else 1
    if mode == 'main':
        load_main()
    import torch
    torch.set_num_threads(1)
    rows = sim_cases() + live_cases()
    json.dump(rows, open(sys.argv[2], 'w'))
    print(mode, len(rows), 'records ->', sys.argv[2])


if __name__ == '__main__':
    sys.exit(main())
