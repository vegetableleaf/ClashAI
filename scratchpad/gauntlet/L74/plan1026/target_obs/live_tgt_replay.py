"""LIVE-TGT (10-31): recorded CLXIII live logs through the live path (b0_identity.run) with switches -- the evidence for
TARGET_OBS.md section LIVE-TGT (target_obs live wiring + the TARGET-VAL acquired-target rule).

    PY=icebow/.venv/Scripts/python.exe; T=scratchpad/gauntlet/L74/plan1026/target_obs/live_tgt_replay.py
    $PY -B $T mkckpt CLXIII.pt ZERO.pt PLANTED.pt          # CLXIII + zero / planted (normal 0, .05, seed 1) target layers
    [FORCE_ACQ=live|engine] [HEAD_CODE=<commit>] $PY -B $T run CKPT OUT.pt [LOG ...]
    $PY -B scratchpad/gauntlet/L74/plan1026/pilot/ops/b0_identity.py compare A.pt B.pt
    $PY -B $T diff A.pt B.pt                               # compare: dicts / taps / RNG / log-probs, which keys
    $PY -B $T pytest_head <commit> -q TEST...             # pytest with that commit's live path (pre-existing failure?)

run: LOGs default = test_decide_identity.LOGS (4 logs, 1,718 decisions). FORCE_ACQ overrides the LiveCues acq_rule that
live_play.load_pilot picks (CLXIII "live", a target-layer checkpoint "engine"); HEAD_CODE runs that commit's
live_unit_state / live_gen / live_gen_v2 / live_play instead of the working tree (the absent-path reference)."""
import collections
import os
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path[:0] = [str(ROOT), str(ROOT / 'scratchpad/gauntlet/L74/plan1026/pilot/ops'), str(ROOT / 'scratchpad/gauntlet/L68/live_reader')]
HEAD_MODS = (('pipeline.live_unit_state', 'pipeline/live_unit_state.py'), ('pipeline.live_gen', 'pipeline/live_gen.py'),
             ('pipeline.live_gen_v2', 'pipeline/live_gen_v2.py'),
             ('live_play', 'scratchpad/gauntlet/L68/live_reader/live_play.py'))


def load_head(head):
    """That commit's live path as the modules, before anything imports them (also: pytest_head)."""
    import pipeline
    for mod, path in HEAD_MODS:
        src = subprocess.run(['git', 'show', f'{head}:{path}'], cwd=ROOT, capture_output=True, text=True,
                             encoding='utf-8', check=True).stdout
        m = types.ModuleType(mod)
        m.__file__ = str(ROOT / path)
        if mod.startswith('pipeline.'):
            m.__package__ = 'pipeline'
            setattr(pipeline, mod.split('.')[1], m)
        sys.modules[mod] = m
        exec(compile(src, f'<{head} {path}>', 'exec'), m.__dict__)


def pytest_head(head, *argv):
    """pytest ARGV with that commit's live path loaded first (is a failing test pre-existing?)."""
    import pytest
    load_head(head)
    sys.exit(pytest.main(list(argv)))


def run(ckpt, out, *logs):
    if os.environ.get('HEAD_CODE'):
        load_head(os.environ['HEAD_CODE'])
    import b0_identity as B
    from pipeline.tests import test_decide_identity as D
    if logs:
        D.LOGS = tuple(logs)
    rule = os.environ.get('FORCE_ACQ')
    if rule:
        from pipeline import live_unit_state as L
        init = L.LiveCues.__init__
        L.LiveCues.__init__ = lambda self, table=None, acq_rule='live': init(self, table, rule)
    B.run(ckpt, 'cpu', out)


def mkckpt(src, out0, out1):
    import torch
    st = torch.load(src, map_location='cpu', weights_only=False)
    d = int(st['args']['d'])
    assert 'tgt_in.weight' not in st['model']
    z = {'tgt_in.weight': torch.zeros(d, 8), 'tgt_out.weight': torch.zeros(d, d), 'tgt_back.weight': torch.zeros(d, d)}
    g = torch.Generator().manual_seed(1)
    torch.save({**st, 'model': {**st['model'], **z}}, out0)
    torch.save({**st, 'model': {**st['model'], **{k: torch.randn(v.shape, generator=g) * 0.05 for k, v in z.items()}}}, out1)


def diff(pa, pb):
    import torch
    a, b = (torch.load(p, weights_only=False) for p in (pa, pb))
    keys, taps = collections.Counter(), []
    for x, y in zip(a['rec'], b['rec']):
        keys.update(k for k in set(x['d']) | set(y['d']) if x['d'].get(k) != y['d'].get(k) and k != 'tgt')
        if x['tap'] != y['tap']:
            taps.append((x['log'], x['tick'], x['d'].get('play'), y['d'].get('play'), x['d'].get('name'), y['d'].get('name'),
                         x['d'].get('p_play'), y['d'].get('p_play')))
    pp = [abs(float(x['d']['p_play']) - float(y['d']['p_play'])) for x, y in zip(a['rec'], b['rec'])]
    strip = lambda d: {k: v for k, v in d.items() if k not in ('xb_lock_p', 'tgt')}   # noqa: E731 -- log-only keys
    same_d = sum(strip(x['d']) == strip(y['d']) for x, y in zip(a['rec'], b['rec']))
    same_rng = sum(x['rng'] == y['rng'] for x, y in zip(a['rec'], b['rec']))
    hd, nohead = {}, 0                    # the legacy decide (options inactive) never calls _policy_forward: no heads kept
    for ha, hb in zip(a['heads'], b['heads']):
        if 'heads' not in ha or 'heads' not in hb:
            nohead += 1
            continue
        for k in ha['heads']:
            hd[k] = max(hd.get(k, 0.0), float((ha['heads'][k] - hb['heads'][k]).abs().max()))
        for x, y in zip(ha.get('cell', []), hb.get('cell', [])):
            hd['cell'] = max(hd.get('cell', 0.0), float((x - y).abs().max()))
    print(f'{len(pp)} decisions; dicts same {same_d}, taps differing {len(taps)}, RNG same {same_rng}; keys differing: '
          f'{dict(keys)}; p_play |diff| max {max(pp):.4f}, > 0.01: {sum(v > .01 for v in pp)}, > 0: {sum(v > 0 for v in pp)}; '
          f'max |log-prob diff| ' + ', '.join(f'{k} {v:.3g}' for k, v in sorted(hd.items())) +
          f' ({nohead} decisions without heads: legacy decide path)')
    for t in taps:
        print('  tap', t)


if __name__ == '__main__':
    cmd, *args = sys.argv[1:]
    {'run': run, 'mkckpt': mkckpt, 'diff': diff, 'pytest_head': pytest_head}[cmd](*args)
