"""plan1026 Pillar 3 P1 (ticket B): ONE ``decision_options.decide`` for SIM eval / forks (decide_batch), training rollouts
(e1_eval.sample_decide_batch) and live (live_gen_v2.GenPilot.decide). Identity against BASE = the decision stack the
running live process imported (pipeline/{decision_options,e1_eval,live_gen_v2}.py at BASE):

  * live: recorded CLXIII live matches (reader frames rebuilt from the --log-frames log, the logged hands, the real
    checkpoint, the logged decision options / seed) through BASE's and this tree's GenPilot.decide -> every decision
    dict (taps: play, hand_pos, xy, follow_ups) and the decision-RNG state identical. BASE runs the whole model twice
    per aimed decision, this tree once (GenPilot._policy_forward): identity proves the single pass bit-identical.
    Also a 'stress' pass of the same
    frames (gate logit +3, overtime, enemy princesses at <= 60 HP) that drives the rule paths.
  * rollouts: e1_eval.sample_decide_batch BASE vs this tree on random batches (gate / card / cell draws, log-probs, the
    record fields, rng_behave states) identical.
  * SIM greedy: decide_batch BASE vs this tree: identical decisions and RNG states on rows no rule fires on; identical
    actions on rule rows (the rule now runs before the model's card / cell, as live, so those rows draw no RNG).
  * cross-path: one live row's decide() inputs through decide_batch -> the same action; a sampled decide with the
    finishers on marks forced rows.

    icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_decide_identity.py
Subprocess modes (each loads BASE's or this tree's stack before anything imports it):
    python pipeline/tests/test_decide_identity.py live base|new OUT.json [stress] LOG...
    python pipeline/tests/test_decide_identity.py sim base|new OUT.json
"""
import json
import os
import subprocess
import sys
import tempfile
import types
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BASE = 'a76f57e'                  # main when ticket B started (10-27): the live run's decision stack
MODS = ('decision_options', 'e1_eval', 'live_gen_v2')
LIVE_DIR = ROOT / 'scratchpad/gauntlet/L68/live_reader'
CKPT = ROOT / 'icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt'
LOGS = ('live_play_20261026_161448.jsonl', 'live_play_20261026_000924.jsonl', 'live_play_20261026_182408.jsonl',
        'live_play_20261027_033228.jsonl')   # lethal_rocket, log_air, rocket_tornado, xbow_dead_lane all fired live
DECK = ['Xbow', 'Tesla', 'IceWizard', 'Tornado', 'Rocket', 'Knight', 'Log', 'Skeletons']   # icebow (unseen-slot filler)


def load_base():
    """BASE's decision stack as the pipeline modules, before anything imports them."""
    import pipeline
    for mod in MODS:
        src = subprocess.run(['git', 'show', f'{BASE}:pipeline/{mod}.py'], cwd=ROOT, capture_output=True, text=True,
                             encoding='utf-8', check=True).stdout
        m = types.ModuleType(f'pipeline.{mod}')
        m.__package__, m.__file__ = 'pipeline', str(ROOT / 'pipeline' / f'{mod}.py')
        sys.modules[m.__name__] = m
        setattr(pipeline, mod, m)
        exec(compile(src, f'<{BASE} {mod}>', 'exec'), m.__dict__)


def canon(x):
    import numpy as np
    import torch
    if isinstance(x, dict):
        return {str(k): canon(v) for k, v in sorted(x.items(), key=lambda kv: str(kv[0]))
                if k not in ('bs', 'public_audit')}
    if isinstance(x, (list, tuple)):
        return [canon(v) for v in x]
    if torch.is_tensor(x) or isinstance(x, np.ndarray):
        return canon(x.tolist())
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return repr(float(x))
    if isinstance(x, set):
        return sorted(canon(v) for v in x)
    return x


# ---------------------------------------------------------------------------------------------------- live replay
def read_log(path, stress=False):
    """-> (start event, [('frame', frame) | ('decision', tick) | ('confirmed', tick, card, form, xy) | ('ability', name,
    tick)]) from a --log-frames live log: reader-shaped frames (entities + their reader category, projectiles, effects,
    phase2 / phase3; my hand = the next logged decision's public hand, my deck in the logged deck order)."""
    from pipeline.obs_contract import _catalog_names
    native = {}
    for cid, n in sorted(_catalog_names().items()):     # the live catalog id whose name the reader logged
        native.setdefault(n, cid)
    rows = [json.loads(s) for s in open(path, encoding='utf-8')]
    start = next(r for r in rows if r['event'] == 'start')
    deck, forms, hands = [None] * 8, [0] * 8, {}
    for r in rows:
        if r['event'] == 'decision' and r.get('public'):
            hands[r['tick']] = [h['deck_index'] for h in r['public']['own_hand']]
            for h in r['public']['own_hand']:
                deck[h['deck_index']] = native[h['name']]
                forms[h['deck_index']] = int(h['form'])
    spare = iter(native[n] for n in DECK if native[n] not in deck)   # a deck slot no logged hand showed
    ids = [next(spare) if d is None else d for d in deck]
    ticks = sorted(hands)
    shift = 3000 if stress else 0                    # stress: overtime (lethal_rocket / lethal_log fire)
    ev, plays = [], {}
    for r in rows:
        e = r['event']
        if e == 'frame':
            side, tick = r['my_side'], r['tick']
            nxt = next((t for t in ticks if t >= tick), ticks[-1] if ticks else None)
            hand = hands.get(nxt, [0, 1, 2, 3])
            st = r.get('ents_state') or []
            ents = []
            for i, x in enumerate(r['ents']):
                hp = x[4]
                if stress and x[6] == 13 and x[0] != side:
                    hp = min(hp, 60)                 # stress: enemy princesses in finisher range
                ents.append(dict(side=x[0], x=x[1], y=x[2], card_id=x[3], hp=hp, max_hp=x[5], kind=x[6], address=x[7],
                                 **({'category': st[i][3]} if i < len(st) else {})))
            me = dict(side=side, hand_deck_indices=list(hand), next_deck_index=next(i for i in range(8) if i not in hand),
                      deck_card_ids=list(ids), deck_form_flags=list(forms), elixir_raw=round(float(r['elixir']) * 1e4))
            f = dict(game_tick=tick + shift, sample_monotonic_us=round(r['t_dev'] * 1e6), entities=ents,
                     projectiles=[dict(side=p[0], x=p[1], y=p[2], card_id=p[3], target_x=p[4], target_y=p[5])
                                  for p in r.get('proj') or []],
                     effects=[dict(side=x[0], x=x[1], y=x[2], card_id=x[3], remaining_ms=x[4]) for x in r.get('fx') or []],
                     players=[me, dict(side=1 - side, hand_deck_indices=[-1] * 4, next_deck_index=-1, elixir_raw=0,
                                       deck_card_ids=[-1] * 8)])
            for k in ('phase2', 'phase3'):
                if r.get(k) is not None:
                    f[k] = r[k]
            ev.append(('frame', f))
        elif e == 'decision':
            d = r.get('decision') or {}
            if d.get('play'):
                plays[d.get('name')] = (d.get('card'), d.get('form'), d.get('xy'))
            ev.append(('decision', r['tick'] + shift))
        elif e in ('confirmed', 'late_landing') and r.get('name') in plays:
            ev.append(('confirmed', r['tick'] + shift, *plays[r['name']]))
        elif e == 'ability_confirmed':
            ev.append(('ability', r.get('name') or 'IceWizard', r['tick'] + shift))
    return start, ev


def live_pilot(start):
    """live_play.load_pilot with the logged start event's options (device cpu)."""
    sys.path.insert(0, str(LIVE_DIR))
    import live_play as lp
    a = SimpleNamespace(device='cpu', ckpt=str(CKPT), tau=start['tau'], no_opp_counter=not start['opp_counter'],
                        extrapolate=start['extrapolate'], decision_seed=start['decision_seed'], public_audit=False,
                        own_effects=start['own_effects'], hero_ability_spec=start['hero_ability_spec'],
                        identity_ext='on' if start['identity_ext'] in (True, 'on') else 'off', afford_ticks=start['afford_ticks'],
                        cue_inputs='on' if (start.get('cue_inputs') or {}).get('active') else 'off', reader='merged',
                        iw_press=start['iw_press'], iw_press_head_decode=start['iw_press_head_decode'])
    return lp.load_pilot(a, dict(start['decision_options']))[1]


def live_main(out, stress, logs):
    import torch
    torch.set_num_threads(1)
    rec = []
    for name in logs:
        start, ev = read_log(LIVE_DIR / name, stress)
        pilot = live_pilot(start)
        if stress:                                   # the gate logit + 3 (rows play); the model object unchanged
            pilot.model.gate_head.register_forward_hook(lambda mod, inp, out: out + 3.0)
        pilot.reset_match()
        f = None
        for e in ev:
            if e[0] == 'frame':
                f = e[1]
                pilot.observe(f)
            elif e[0] == 'decision' and f is not None and f['game_tick'] == e[1]:
                d = pilot.decide(f)
                tap = [d['hand_pos'], canon(d['xy']), canon(d.get('follow_ups'))] if d.get('play') else None
                rec.append(dict(log=name, tick=e[1], tap=tap, d=canon(d), rng=canon(pilot.rng_decisions.bit_generator.state)))
            elif e[0] == 'confirmed' and None not in e[2:]:
                pilot.record_play(e[2], e[3], e[4], e[1] * 0.05)
            elif e[0] == 'ability':
                pilot.record_ability(e[1], e[2])
    Path(out).write_text(json.dumps(rec), encoding='utf-8')


# ---------------------------------------------------------------------------------------------------- SIM rows
def sim_main(out):
    import numpy as np
    import torch
    torch.set_num_threads(1)
    from pipeline import e1_eval as E
    from pipeline.decision_options import DecisionOptions, decide_batch
    from pipeline.tests.test_lethal_rocket import towers
    live = dict(xbow_class='class_sample', xbow_class_floor=.3, tau_phase=(.35, .45, .55), spell_aim='rocket_area',
                log_aim='log_barrel', barrel_lane='on', lethal_rocket='ot_behind', xbow_dead_lane='block', lethal_log='on',
                tau_threatened=.2, log_air='off')
    option_sets = [live, dict(live, lethal_rocket='off'), dict(live, gate_decode='hazard_below_tau', gate_hazard_min_elixir=9.0),
                   dict(card_choice='filtered'), dict(lethal_rocket='ot'), dict(xbow_class='class_sample', xbow_class_floor=.2)]
    names_pool = [['knight', 'xbow', 'rocket', 'tesla'], ['the-log', 'Xbow', 'Rocket', 'tornado'],
                  ['skeletons', 'ice-wizard', 'x_bow', 'log'], ['Log', 'Rocket', 'Knight', 'IceWizard']]
    rec = []
    for oi, kw in enumerate(option_sets):
        options = DecisionOptions(**kw)
        for trial in range(20):
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
            gob = [tuple((float(nrng.random() * 18), float(17 + nrng.random() * 14)) for _ in range(int(nrng.integers(0, 2))))
                   for _ in range(B)]
            names = [names_pool[int(nrng.integers(0, 4))] for _ in range(B)]
            rngs = [np.random.default_rng([oi, trial, r]) for r in range(B)]
            d = decide_batch(M(), {'i': torch.arange(B)}, heads, p, allowed, stalled, tau=.35, device='cpu',
                             options=options, rngs=rngs, card_names=names, t_sec=list(t_sec), enemy_alive=alive,
                             grid='lattice', projectiles=proj, step_s=.5, elixir=list(nrng.random(B) * 10),
                             enemy_units=list(nrng.integers(0, 3, B)), lethal=lethal, barrel_goblins=gob,
                             tau_threat=list(nrng.random(B) < .3))
            rec.append(dict(kind='greedy', options=oi, trial=trial, d=canon(d), rng=[canon(r.bit_generator.state) for r in rngs]))
    for trial in range(40):                          # the rollout sampler (no rule in cfg: the training path today)
        g = torch.Generator().manual_seed(77 + trial)
        nrng = np.random.default_rng(77 + trial)
        B = 12
        heads = {'card': torch.randn(B, 8, generator=g) * 2, 'gate': torch.randn(B, generator=g) * 2}
        cells = torch.randn(B, 8, 2304, generator=g) * 3

        class S:
            def cell_logits(self, enc, slot):
                return cells[enc['i'].long(), slot]
        cfg = dict(tau=.35, T=float(nrng.choice([.1, .5, 1.])))
        if trial % 2:
            cfg['tau_phase'] = [.27, .35, .45]
        if trial % 3 == 1:
            cfg['T_gate'] = .1
        if trial % 5 == 2:
            cfg['sample_heads'] = ('gate', 'cell')
        matches = [SimpleNamespace(rng_behave=np.random.default_rng([trial, r]),
                                   _cur=(0, SimpleNamespace(t_sec=float(nrng.choice([10., 150., 200.]))))) for r in range(B)]
        allowed = nrng.random((B, 8)) < .6
        stalled = nrng.random(B) < .1
        p = torch.sigmoid(heads['gate']).numpy()
        d = E.sample_decide_batch(S(), {'i': torch.arange(B)}, heads, p, allowed, stalled, matches, cfg)
        rec.append(dict(kind='sample', trial=trial, d=canon(d), rng=[canon(m.rng_behave.bit_generator.state) for m in matches]))
    Path(out).write_text(json.dumps(rec), encoding='utf-8')


def run_mode(*args):
    with tempfile.TemporaryDirectory() as tmp:
        outs = []
        for which in ('base', 'new'):
            out = Path(tmp) / f'{which}.json'
            r = subprocess.run([sys.executable, '-B', str(Path(__file__)), args[0], which, str(out), *args[1:]], cwd=ROOT,
                               capture_output=True, text=True, encoding='utf-8', timeout=3600,
                               env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
            assert r.returncode == 0, r.stderr[-4000:]
            outs.append(json.loads(out.read_text(encoding='utf-8')))
        return outs


# ---------------------------------------------------------------------------------------------------- tests
def _need_live():
    import pytest
    missing = [n for n in LOGS if not (LIVE_DIR / n).is_file()]
    if not CKPT.is_file() or missing:
        pytest.skip(f'recorded live logs / checkpoint not in this checkout: {missing or CKPT}')


def _compare_live(base, new):
    assert len(base) == len(new) and len(new) > 0
    taps = [(a['log'], a['tick']) for a, b in zip(base, new) if a['tap'] != b['tap']]
    diffs = [(a['log'], a['tick']) for a, b in zip(base, new) if a != b]
    assert not taps and not diffs, (taps[:5], diffs[:5])
    return sum(a['tap'] is not None for a in base)


def test_live_recorded_decisions_identical_to_base():
    _need_live()
    base, new = run_mode('live', *LOGS)
    plays = _compare_live(base, new)
    print(f'live recorded: {len(new)} decisions, {plays} taps, all identical to {BASE}')


def test_live_stress_rule_paths_identical_to_base():
    _need_live()
    base, new = run_mode('live', 'stress', *LOGS)
    plays = _compare_live(base, new)
    whys = sorted({r['d'].get('why') for r in new if r['d'].get('why')})
    assert {'lethal_rocket', 'lethal_log'} & set(whys), whys       # the finishers ran
    print(f'live stress: {len(new)} decisions, {plays} taps, whys {whys}: all identical to {BASE}')


def test_sim_rows_identical_to_base():
    base, new = run_mode('sim')
    assert len(base) == len(new)
    rule = ('lethal_rocket', 'lethal_log')
    n_rule = 0
    for a, b in zip(base, new):
        assert a['kind'] == b['kind']
        if a['kind'] == 'sample':
            assert a == b, a['trial']                                 # draws, log-probs, records, rng_behave
            continue
        for r, (x, y) in enumerate(zip(a['d'], b['d'])):
            assert x == y, (a['options'], a['trial'], r)              # the same action and label on every row
            if x['why'] in rule:
                n_rule += 1
            else:
                assert a['rng'][r] == b['rng'][r], (a['options'], a['trial'], r)
    assert n_rule > 0


def test_one_live_row_through_decide_batch_gives_the_same_action(monkeypatch):
    import numpy as np
    import torch
    from pipeline import live_gen_v2
    from pipeline.decision_options import DecisionOptions, decide_batch
    from pipeline.tests.test_live_decision_options import icebow_frame, pilot
    opts = DecisionOptions(xbow_class='class_sample', xbow_class_floor=.3, tau_phase=(.35, .45, .55), spell_aim='rocket_area',
                           lethal_rocket='ot_behind', xbow_dead_lane='block', tau_threatened=.2)
    seen = []
    real = live_gen_v2.decide

    def spy(heads, p, allowed, stalled, **kw):
        seen.append((heads, p, allowed, stalled, kw))
        return real(heads, p, allowed, stalled, **kw)
    monkeypatch.setattr(live_gen_v2, 'decide', spy)
    n = 0
    for tick in (1000, 2600, 3700):
        for side in (0, 1):
            for gate_p in (.2, .6, .9):
                g = torch.Generator().manual_seed(tick + side + int(gate_p * 10))
                q = pilot(opts, gate_p, cell=torch.randn(2304, generator=g) * 3, seed=5)
                q.legal_guard = False
                seen.clear()
                d = q.decide(icebow_frame(tick, side))
                heads, p, allowed, stalled, kw = seen[0]
                logits = q.model.cell[None]

                class M:
                    def cell_logits(self, enc, slot):
                        return logits.expand(len(slot), -1)
                ctx = {k: v for k, v in kw.items() if k not in ('options', 'rngs', 'cell_logits', 'card_names', 'cell_guard',
                                                                'follow_up', 'trace', 'choose', 'tau')}
                s = decide_batch(M(), {'i': torch.zeros(1)}, heads, p, allowed, stalled, tau=kw['tau'], device='cpu',
                                 options=opts, rngs=[np.random.default_rng(5)], card_names=kw['card_names'], **ctx)[0]
                assert (s['play'], s['slot']) == (d['play'], d['hand_pos']), (tick, side, gate_p)
                if d['play']:
                    from pipeline.model_v3 import cell_xy
                    assert cell_xy(s['cell'], 'lattice') == d['xy']
                    n += 1
    assert n > 0


def test_sampled_decide_runs_the_finishers_and_marks_forced_rows():
    import numpy as np
    import torch
    from pipeline import e1_eval as E
    from pipeline.tests.test_lethal_rocket import towers
    B = 6
    g = torch.Generator().manual_seed(3)
    heads = {'card': torch.randn(B, 8, generator=g), 'gate': torch.full((B,), -4.0)}
    cells = torch.randn(B, 8, 2304, generator=g)

    class S:
        def cell_logits(self, enc, slot):
            return cells[enc['i'].long(), slot]
    cfg = dict(tau=.35, T=.5, lethal_rocket='ot', grid='lattice', decide_every=10)
    deck = SimpleNamespace(cards=['Xbow', 'Tesla', 'IceWizard', 'Tornado', 'Rocket', 'Knight', 'Log', 'Skeletons'])
    ms = [SimpleNamespace(rng_behave=np.random.default_rng(r), cfg=cfg, tag=f't{r}', k=r, deck=deck, side=0, pend=None,
                          pending=None, done_plays=[], _cur=(4000, SimpleNamespace(t_sec=200.0, my_elixir=9.0, units=(),
                                                                                   towers=())),
                          state={'episode': {'crown_towers': towers(0, 400 if r < 3 else 4000, 4000)}}) for r in range(B)]
    allowed = np.ones((B, 8), bool)
    out = E.sample_decide_batch(S(), {'i': torch.arange(B)}, heads, torch.sigmoid(heads['gate']).numpy(), allowed,
                                np.zeros(B, bool), ms, cfg)
    for r, d in enumerate(out):
        assert d['forced'] is (r < 3), r
        if r < 3:                                   # the lethal Rocket: gate overridden, card / cell not drawn
            assert d['play'] and d['slot'] == 4 and d['why'] == 'lethal_rocket' and d['lp_card'] == d['lp_cell'] == 0.0
        else:
            assert not d['play']                    # gate logit -4 vs tau .35: the sampled WAIT
    rows = E.Match._traj_arrays(SimpleNamespace(traj=[]))
    assert 'forced' not in rows


if __name__ == '__main__':
    mode, which, out = sys.argv[1:4]
    if which == 'base':
        load_base()
    if mode == 'live':
        rest = sys.argv[4:]
        live_main(out, bool(rest) and rest[0] == 'stress', rest[1:] if rest and rest[0] == 'stress' else rest)
    else:
        sim_main(out)
