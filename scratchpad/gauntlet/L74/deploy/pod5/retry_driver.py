"""Pod 5: shortened Tornado retry (lead 2026-10-12). Same pending-head fine-tune as TORNADO (extra train_pending args from the
retry ladder), then the SAME gate rule on the HARDER opponent only (rdef_e4 graft, T 0.1): 960 paired games pipelining ON and
960 pipelining OFF, fixed vs live. The live arms are the TORNADO run's own (same seeds/opponent/flags, hash-checked by load_group),
linked, not replayed. Writes SUMMARY.txt like the original driver."""
import argparse, importlib.util, json, os, shlex, sys
from pathlib import Path

ROOT = Path('/workspace/wt_tornado')
os.chdir(ROOT); sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('tornado_driver', ROOT / 'scratchpad/gauntlet/L74/tornado/driver.py')
D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)
A = D.A


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--base', type=Path, default=Path('/workspace/results/wk/TORNADO'))
    p.add_argument('--train-args', default='')
    p.add_argument('--workers', type=int, default=20)
    a = p.parse_args()
    out = a.out / 'icebow'; out.mkdir(parents=True, exist_ok=True)
    init, hard = A.OLD, A.CAL_C
    index = a.base / 'icebow/pending.npz'
    dataset = json.loads(index.with_suffix('.json').read_text())
    fixed = out / 'fixed.pt'
    D.run(['bash', '/workspace/retry/train_locked.sh', '--data', A.DATA, '--pending', index, '--init', init, '--out', fixed,
           '--device', 'cuda', *shlex.split(a.train_args)], out / 'train.log')
    import torch
    training = torch.load(fixed, map_location='cpu', weights_only=True)['pending_pretrain']
    if training['ordinary_top_card_drift'] >= .01:
        raise ValueError('selected checkpoint exceeds ordinary drift bound')
    pros = {D.normalize(c): v for c, v in json.loads(D.PRO_FILE.read_text())['second_mix_le_24'].items()}
    hard_sha = D.digest(hard)
    comparisons = {}
    for label, pipeline in (('hard_on', True), ('hard_off', False)):
        ev = out / label; ev.mkdir()
        groups = {}
        for arm, learner in (('live', init), ('fixed', fixed)):
            for census, decks, start in (('evo', A.EVO, 30000), ('lad', A.LAD, 30480)):
                dest = ev / f'{arm}_{census}'
                if arm == 'live':
                    dest.symlink_to((a.base / 'icebow' / label / f'live_{census}').resolve())
                else:
                    D.run(D.eval_command(learner, dest, decks, start, a.workers, hard, .1, pipeline), ev / f'{arm}_{census}.log')
            groups[arm] = D.load_group(ev, arm, pipeline, D.digest(learner), hard_sha, .1)
        comparisons[label] = D.compare(groups['live'], groups['fixed'], pros)
    ok = all(c['non_inferior'] and (not k.endswith('_on') or c['tornado_ok']) for k, c in comparisons.items())
    verdict = 'candidate' if ok else 'not candidate'
    report = dict(verdict=verdict, models={'icebow': dict(verdict=verdict, dataset=dataset, training=training, comparisons=comparisons)},
                  bait_note='Retry: harder opponent only (rdef_e4 graft, T 0.1); live arms reused from the TORNADO run. Train args: ' + a.train_args)
    (a.out / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    (a.out / 'SUMMARY.txt').write_text(D.summary_text(report), encoding='utf-8')


if __name__ == '__main__':
    main()
