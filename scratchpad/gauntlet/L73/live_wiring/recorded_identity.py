"""L73 live wiring, Part B evidence on RECORDED live reader frames with the real live checkpoint (R1e u0155):
  1. default byte-identity: the pre-change live pilot (live_gen_v2.py at git HEAD 821ac34, = the main checkout's) and
     the new one, both with options unset, decide every recorded frame identically (all decision fields, exact floats);
  2. pre-change vs new with --tau-phase .35 .45 .55 --xbow-class class_sample --xbow-class-floor .3: the old pilot
     raised on X-Bow decisions and ignored tau_phase (plays with p <= the phase threshold); the new one does neither.
Frames: re_v2xb.jsonl (10-03, 975) + passive_v2_raw.jsonl (10-06, 120), main checkout, read-only.
Writes results_recorded_identity.json. Run via decode_options/lowprio.py."""
import argparse, importlib.util, json, subprocess, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
WT = HERE.parents[3]
sys.path[:0] = [str(WT), str(WT / 'scratchpad/gauntlet/L68/live_reader')]
sys.path.insert(0, str(HERE))
from partA_probe import CKPTS, FRAMES, frames  # noqa: E402
import live_play  # noqa: E402
from pipeline import live_gen_v2  # noqa: E402
from pipeline.decision_options import add_arguments, config_from_args, phase_index, is_xbow  # noqa: E402

KEYS = ('play', 'p_play', 'no_affordable', 'hand_pos', 'deck_index', 'card', 'form', 'name', 'xy', 'el_int')
OPTS = ['--tau-phase', '0.35', '0.45', '0.55', '--xbow-class', 'class_sample', '--xbow-class-floor', '0.3']


def head_module():
    src = subprocess.run(['git', '-C', str(WT), 'show', '821ac34:pipeline/live_gen_v2.py'], capture_output=True,
                         text=True, check=True).stdout
    path = Path(__import__('tempfile').mkdtemp()) / 'live_gen_v2_head.py'
    path.write_text(src, encoding='utf-8')
    spec = importlib.util.spec_from_file_location('pipeline._live_gen_v2_head', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load(cls, options=()):
    ap = argparse.ArgumentParser()
    add_arguments(ap)
    cfg = config_from_args(ap.parse_args(list(options)))
    a = argparse.Namespace(ckpt=str(CKPTS['R1e_fv4']), device='cpu', tau=0.35, no_opp_counter=False, extrapolate=26,
                           decision_seed=cfg['decision_seed'], public_audit=True)
    live_play.GenPilot = cls                      # live_play.load_pilot builds whatever GenPilot it imported
    return live_play.load_pilot(a, cfg)[1]


def summary(d):
    out = {k: d[k] for k in KEYS if k in d}
    if 'xy' in out:
        out['xy'] = [float(v) for v in out['xy']]
    return out


def main():
    old_cls = head_module().GenPilot
    pilots = dict(old_default=load(old_cls), new_default=load(live_gen_v2.GenPilot),
                  old_options=load(old_cls, OPTS), new_options=load(live_gen_v2.GenPilot, OPTS))
    st = {k: dict(decisions=0, plays=0, errors={}, xbow_plays=0, plays_p_le_phase_tau=0, phase_rows=[0, 0, 0])
          for k in pilots}
    mismatch, compared = [], 0
    for path in FRAMES:
        for p in pilots.values():
            p.reset_match()
        for f in frames(path):
            got = {}
            for name, p in pilots.items():
                p.observe(f)
                if int(f['game_tick']) < live_play.UI_READY_MIN_TICK:
                    continue
                s = st[name]
                try:
                    d = p.decide(f)
                except ValueError as exc:
                    s['errors'][str(exc)] = s['errors'].get(str(exc), 0) + 1
                    continue
                got[name] = summary(d)
                s['decisions'] += 1
                s['plays'] += bool(d['play'])
                ph = int(phase_index(d['bs'].t_sec))
                s['phase_rows'][ph] += 1
                if d['play'] and d.get('name') and is_xbow(d['name']):
                    s['xbow_plays'] += 1
                if d['play'] and d['p_play'] <= (.35, .45, .55)[ph]:
                    s['plays_p_le_phase_tau'] += 1
            if 'old_default' in got:
                compared += 1
                if got['old_default'] != got.get('new_default'):
                    mismatch.append(dict(tick=f['game_tick'], old=got['old_default'], new=got.get('new_default')))
    out = dict(checkpoint=str(CKPTS['R1e_fv4']), frames=[str(p) for p in FRAMES], default_compared=compared,
               default_mismatches=len(mismatch), first_mismatches=mismatch[:5], options=OPTS, pilots=st)
    (HERE / 'results_recorded_identity.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
