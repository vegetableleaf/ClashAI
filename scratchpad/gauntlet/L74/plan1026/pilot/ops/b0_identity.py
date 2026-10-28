"""LOOP-OPS 1: B0 == CLXIII at u0 on recorded live decisions (CPU and CUDA).

    python -B scratchpad/gauntlet/L74/plan1026/pilot/ops/b0_identity.py run CKPT DEVICE OUT.pt
    python -B scratchpad/gauntlet/L74/plan1026/pilot/ops/b0_identity.py compare A.pt B.pt
    python -B scratchpad/gauntlet/L74/plan1026/pilot/ops/b0_identity.py all B0 OUTDIR [cpu cuda]   (4+ runs, then compares)

run: test_decide_identity's four recorded CLXIII live matches (1,718 decisions; lethal_rocket, log_air, rocket_tornado,
xbow_dead_lane all fired live) replayed through this tree's live path (live_play.load_pilot with each logged start event's
options, GenPilot.observe / decide / record_play / record_ability), with CKPT and DEVICE swapped in. Per decision it keeps
the decision dict, the tap, the decision-RNG state, every policy head tensor of the ONE trunk pass (_policy_forward: gate,
card, value, ..., g) and every card-conditioned cell-head call, as float64 log-probs: log sigmoid(gate), log_softmax(card),
log_softmax(cell). compare: decisions / taps / RNG states equal, and max |log-prob diff| per head (0.0 = bit-identical).
"""
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(ROOT))
CLXIII = 'icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt'
LOG_ONLY = 'xb_lock_p'     # live_gen_v2.decide adds it for a memory v2 model (frozen lock head P(lock)); live_play only logs it


def pilot_for(start, ckpt, device):
    """= test_decide_identity.live_pilot with CKPT / DEVICE in place of CLXIII / cpu."""
    from pipeline.tests.test_decide_identity import LIVE_DIR
    sys.path.insert(0, str(LIVE_DIR))
    import live_play as lp
    a = SimpleNamespace(device=device, ckpt=str(ckpt), tau=start['tau'], no_opp_counter=not start['opp_counter'],
                        extrapolate=start['extrapolate'], decision_seed=start['decision_seed'], public_audit=False,
                        own_effects=start['own_effects'], hero_ability_spec=start['hero_ability_spec'],
                        identity_ext='on' if start['identity_ext'] in (True, 'on') else 'off', afford_ticks=start['afford_ticks'],
                        cue_inputs='on' if (start.get('cue_inputs') or {}).get('active') else 'off', reader='merged',
                        iw_press=start['iw_press'], iw_press_head_decode=start['iw_press_head_decode'])
    return lp.load_pilot(a, dict(start['decision_options']))[1]


def logp(name, t):
    import torch
    t = t.detach().double().cpu()
    if name == 'gate':
        return torch.nn.functional.logsigmoid(t)
    if name in ('card', 'cell'):
        return torch.log_softmax(t, -1)
    return t                                            # value, g, other heads: raw


def run(ckpt, device, out):
    import torch
    from pipeline.tests.test_decide_identity import LIVE_DIR, LOGS, canon, read_log
    torch.set_num_threads(1)
    if device == 'cuda':
        torch.backends.cudnn.deterministic, torch.backends.cudnn.benchmark = True, False
    rec, heads = [], []
    for name in LOGS:
        start, ev = read_log(LIVE_DIR / name)
        pilot = pilot_for(start, ROOT / ckpt, device)
        cur = {}
        fwd = pilot._policy_forward

        def wrapped(b, fwd=fwd, cur=cur):
            o, cell_head = fwd(b)
            cur['heads'] = {k: logp(k, v) for k, v in o.items() if torch.is_tensor(v)}

            def ch(card, form):
                c = cell_head(card, form)
                cur.setdefault('cell', []).append(logp('cell', c))
                return c
            return o, ch
        pilot._policy_forward = wrapped
        pilot.reset_match()
        f = None
        for e in ev:
            if e[0] == 'frame':
                f = e[1]
                pilot.observe(f)
            elif e[0] == 'decision' and f is not None and f['game_tick'] == e[1]:
                cur.clear()
                d = pilot.decide(f)
                tap = [d['hand_pos'], canon(d['xy']), canon(d.get('follow_ups'))] if d.get('play') else None
                rec.append(dict(log=name, tick=e[1], tap=tap, d=canon(d), rng=canon(pilot.rng_decisions.bit_generator.state)))
                heads.append(dict(cur))
            elif e[0] == 'confirmed' and None not in e[2:]:
                pilot.record_play(e[2], e[3], e[4], e[1] * 0.05)
            elif e[0] == 'ability':
                pilot.record_ability(e[1], e[2])
        print(f'{name}: {sum(r["log"] == name for r in rec)} decisions, memory model: '
              f'{getattr(pilot.model, "mem", None) is not None}', flush=True)
    torch.save({'ckpt': ckpt, 'device': device, 'rec': rec, 'heads': heads}, out)


def compare(pa, pb):
    import torch
    a, b = (torch.load(p, weights_only=False) for p in (pa, pb))
    assert len(a['rec']) == len(b['rec']), (len(a['rec']), len(b['rec']))
    n = len(a['rec'])
    la, lb = (sum(LOG_ONLY in x['d'] for x in r['rec']) for r in (a, b))        # a memory model's lock-head P, log only
    strip = lambda d: {k: v for k, v in d.items() if k != LOG_ONLY}                 # noqa: E731
    same_d = sum(strip(x['d']) == strip(y['d']) for x, y in zip(a['rec'], b['rec']))
    same_tap = sum(x['tap'] == y['tap'] for x, y in zip(a['rec'], b['rec']))
    same_rng = sum(x['rng'] == y['rng'] for x, y in zip(a['rec'], b['rec']))
    plays = sum(x['tap'] is not None for x in a['rec'])
    diff, cnt, cells = {}, {}, 0
    for ha, hb in zip(a['heads'], b['heads']):
        assert ha['heads'].keys() == hb['heads'].keys()
        for k in ha['heads']:
            diff[k] = max(diff.get(k, 0.0), float((ha['heads'][k] - hb['heads'][k]).abs().max()))
            cnt[k] = cnt.get(k, 0) + ha['heads'][k].numel()
        ca, cb = ha.get('cell', []), hb.get('cell', [])
        assert len(ca) == len(cb)
        cells += len(ca)
        for x, y in zip(ca, cb):
            diff['cell'] = max(diff.get('cell', 0.0), float((x - y).abs().max()))
    ok = same_d == same_tap == same_rng == n and all(v == 0.0 for v in diff.values())
    print(f'{a["ckpt"]}@{a["device"]} vs {b["ckpt"]}@{b["device"]}: {n} decisions ({plays} plays); decision dicts '
          f'{same_d}/{n} (log-only {LOG_ONLY} in {la} / {lb}), taps {same_tap}/{n}, RNG states '
          f'{same_rng}/{n}; cell-head calls {cells}; '
          f'max |log-prob diff| ' + ', '.join(f'{k} {v:.3g}' for k, v in sorted(diff.items())) +
          f' -> {"IDENTICAL" if ok else "DIFFERENT"}')
    return ok


def all_(b0, outdir, devices=('cpu', 'cuda')):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for dev in devices:
        for tag, ck in (('clxiii', CLXIII), ('b0', b0)):
            o = outdir / f'{tag}_{dev}.pt'
            if not o.exists():
                subprocess.run([sys.executable, '-B', __file__, 'run', ck, dev, str(o)], cwd=ROOT, check=True)
    ok = [compare(outdir / f'clxiii_{d}.pt', outdir / f'b0_{d}.pt') for d in devices]
    if len(devices) == 2:                               # informational: the device change itself (not a B0 property)
        compare(outdir / 'clxiii_cpu.pt', outdir / 'clxiii_cuda.pt')
    print('B0_IDENTITY', 'PASS' if all(ok) else 'FAIL')
    return all(ok)


if __name__ == '__main__':
    cmd, *args = sys.argv[1:]
    if cmd == 'run':
        run(*args)
    elif cmd == 'compare':
        sys.exit(0 if compare(*args) else 1)
    elif cmd == 'all':
        sys.exit(0 if all_(args[0], args[1], tuple(args[2:]) or ('cpu', 'cuda')) else 1)
