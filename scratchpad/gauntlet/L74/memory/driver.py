"""Four pod phases. Pure plans and report validation are testable without SIM."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

REPO = Path(__file__).resolve().parents[4]
WEEKEND = REPO / 'scratchpad/gauntlet/L74/weekend'
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(WEEKEND))
spec = importlib.util.spec_from_file_location('memory_adaptive_driver', WEEKEND / 'adaptive/driver.py')
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)


def plans(prefix='wk_memory'):
    out = A.cycle_plan(prefix, cycles=3, main_updates=20, exploiter_updates=15)
    for plan in out:
        plan['exploiter_init'] = plan['frozen']  # memory-enabled learner snapshot
    return out


def config(base, phase, plan, deck, external, init, data, cap):
    c = A.config_for(base, phase, plan, deck, external)
    c.update(history_events=True, history_cap=cap, proagree_data_gen=str(data))
    if phase == 'main':
        c['init'] = str(init)
    # No decision_options / LIVE_OPTIONS: inherited adaptive training is plain.
    return c


def ablate(source, destination):
    import torch
    ck = torch.load(source, map_location='cpu', weights_only=True)
    if 'history.cfg' not in ck['model']:
        raise ValueError('ablation requires a memory checkpoint')
    ck['args'] = dict(ck['args'], history_zero=True)
    A.save_checkpoint(destination, ck)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def recipe(a):
    # Refuse to resume a run under changed source, base, or dataset recipe.
    sources = [Path(__file__), Path(__file__).with_name('run_memory.sh'),
               WEEKEND/'adaptive/driver.py', WEEKEND/'graft_generic.py']
    sources += [REPO/'pipeline'/name for name in (
        'match_memory.py', 'history_encoder.py', 'model_gen.py', 'model_v3.py', 'public_observation.py',
        'dataset_gen.py', 'dataset_spool.py', 'add_memory.py', 'train_memory.py',
        'e1_eval.py', 'rl_royale.py', 'adaptive_opponents.py', 'rl_royale.yaml')]
    return dict(args={k: str(v) for k, v in vars(a).items()}, init=digest(a.init),
                template=digest(a.template), sources={str(p): digest(p) for p in sources})


def report(ev, games=480):
    import wk_compare as W
    pairs = {}
    for arm in ('old', 'memory', 'zero'):
        pairs[arm] = {}
        for census in ('evo', 'lad'):
            rows = [json.loads(s) for s in (ev / f'{arm}_{census}' / 'matches.jsonl').read_text().splitlines()]
            if len(rows) != games or any(r.get('skipped') or r.get('outcome') not in ('win', 'draw', 'loss') for r in rows):
                raise ValueError(f'incomplete evaluation: {arm}_{census}')
            for r in rows:
                key = (census, r['tag'])
                if key in pairs[arm] or not r.get('opp_deck'):
                    raise ValueError('duplicate pair or absent deck')
                pairs[arm][key] = r['opp_deck']
    if not (pairs['old'] == pairs['memory'] == pairs['zero']):
        raise ValueError('pairing or opponent decks differ')
    comparisons = [('old', 'memory'), ('zero', 'memory')]
    lines = []
    for base, candidate in comparisons:
        n, _, _, mu, lo, hi = W.diff(str(ev), base, candidate)
        if n != games*2:
            raise ValueError('incorrect paired total')
        label = 'Improvement' if base == 'old' else 'Memory benefit'
        lines.append(f'{label}: ' + ('shown' if lo > 0 else 'negative' if hi < 0 else 'not established'))
        lines.extend([W.line(str(ev), base, candidate), W.arch_table(str(ev), base, candidate)])
    return ('VERDICT: Measurements complete; nothing deployed.\n' + '\n'.join(lines) +
            '\nFixed opponent E4 u20, T=0.1; census evo/lad; CAL/S2 live evaluation flags.\n'
            'Zero arm retains identical weights and zeros only history inputs.\n')


def execute(a):
    import numpy as np
    import torch
    import yaml
    out = a.results / ('MEM'+a.phase)
    out.mkdir(parents=True, exist_ok=True)
    data = a.results / 'MEMP1/pro_memory.npz'
    pretrained = a.results / 'MEMP2/memory_pretrained.pt'
    if a.phase != 'P1':
        previous = a.results / ('MEMP'+str(int(a.phase[1])-1))
        if not (previous / 'SUCCESS').exists():
            raise ValueError(f'previous phase did not succeed: {previous}')
    current = recipe(a)
    receipt = out / 'recipe.json'
    if receipt.exists() and json.loads(receipt.read_text()) != current:
        raise ValueError('phase recipe changed; use a fresh --results and --prefix')
    A.atomic_json(receipt, current)
    complete = out / 'COMPLETE.json'
    if complete.exists():
        for path, expected in json.loads(complete.read_text()).items():
            if digest(path) != expected:
                raise ValueError(f'completed phase artifact changed: {path}')
        return
    artifacts = []
    if a.phase == 'P1':
        ck = torch.load(a.init, map_location='cpu', weights_only=True)
        with np.load(a.template, allow_pickle=False) as z:
            meta = json.loads(str(z['meta']))
        corpora = a.corpus or [Path(c) for c in meta['corpora']]
        for path in corpora:
            if not path.is_dir():
                raise FileNotFoundError(f'{path}: provide pod-local --corpus paths')
        fv = int(ck['args']['feature_version'])
        fv = 5 if fv == 6 else fv
        cmd = [sys.executable, '-m', 'pipeline.dataset_gen', '--corpus', *corpora, '--out', data,
               '--feature-version', str(fv), '--history-events', '--history-cap', str(a.cap), '--workers', '1',
               '--wait-stride', str(meta.get('wait_stride', 40)), '--play-window', str(meta.get('play_window', 20)),
               '--val-pct', str(meta.get('val_pct', 10)), '--grid', ck['args'].get('grid', 'lattice'),
               '--shift-ticks', str(meta.get('shift_ticks', 0))]
        A.run(cmd, out / 'dataset.log')
        built = json.loads(data.with_suffix('.json').read_text())
        if built['card_vocab'] != ck['card_vocab'] or not built.get('history_events'):
            raise ValueError('rebuilt corpus vocabulary/history differs from checkpoint')
        summary = f'VERDICT: pro dataset rebuilt with public histories (cap {a.cap}).\n{data}\n'
        artifacts = [data, data.with_suffix('.json')]
    elif a.phase == 'P2':
        from pipeline.add_memory import convert
        init = out / 'memory_zero_init.pt'
        torch.manual_seed(74)
        convert(a.init, init, cap=a.cap)
        A.run([sys.executable, '-m', 'pipeline.train_memory', '--init', init, '--data', data,
               '--out', pretrained, '--epochs', str(a.epochs), '--kl', str(a.kl), '--device', 'cuda'], out / 'pretrain.log')
        summary = 'VERDICT: memory-only imitation complete; base frozen and KL anchored.\n' + pretrained.with_suffix('.metrics.json').read_text()
        artifacts = [pretrained, pretrained.with_suffix('.metrics.json')]
    elif a.phase == 'P3':
        base = yaml.safe_load((REPO / 'pipeline/rl_royale.yaml').read_text())
        deck = out / 'decks_rl.json'
        if not deck.exists():
            A.run([sys.executable, WEEKEND / 'mk_weighted_decks.py', A.EVO, deck, '1.0', '0'], out / 'decks.log')
            A.atomic_json(deck, A.weighted_sixty(json.loads(deck.read_text())))
        path = out / 'cycles.json'
        state = json.loads(path.read_text()) if path.exists() else dict(completed=[], external=[])
        for plan in plans(a.prefix):
            if plan['cycle'] in state['completed']:
                continue
            c = config(base, 'main', plan, deck, state['external'], pretrained, data, a.cap)
            main = A.train(c, plan['main_run'], out)
            frozen = REPO / plan['frozen']
            weights = {k: v for k, v in main.items() if k != 'rl'}
            if frozen.exists():
                prior = torch.load(frozen, map_location='cpu', weights_only=True)
                if prior['model'].keys() != weights['model'].keys() or any(not torch.equal(prior['model'][k], v) for k, v in weights['model'].items()):
                    raise ValueError('immutable learner snapshot changed')
            else:
                A.save_checkpoint(frozen, weights)
            frozen_digest = digest(frozen)
            c = config(base, 'exploiter', plan, deck, [], pretrained, data, a.cap)
            A.train(c, plan['exploiter_run'], out)
            if digest(frozen) != frozen_digest:
                raise ValueError('frozen opponent changed')
            exp = A.CKROOT / plan['exploiter_run'] / f"{plan['exploiter_run']}_u{plan['exploiter_target']:04d}.pt"
            if not (REPO / exp).is_file():
                raise FileNotFoundError(exp)
            main = A.enroll(main, exp)
            A.save_checkpoint(REPO / A.checkpoint(plan['main_run']), main)
            state['external'] = main['rl']['league']['external']
            state['completed'].append(plan['cycle'])
            state.setdefault('snapshots', []).append(dict(path=str(frozen), sha256=frozen_digest))
            A.atomic_json(path, state)
        # Train once more against all three enrolled exploiters, including cycle 3.
        final = dict(plans(a.prefix)[-1], main_target=80)
        c = config(base, 'main', final, deck, state['external'], pretrained, data, a.cap)
        A.train(c, final['main_run'], out)
        summary = 'VERDICT: adaptive memory league complete: 80 main updates, 3 x 15 exploiter updates.\n' + json.dumps(state, indent=2)
        artifacts = [REPO/A.checkpoint(final['main_run']), path]
    else:
        final = out / 'memory_grafted.pt'
        A.run([sys.executable, WEEKEND / 'graft_generic.py', A.checkpoint(a.prefix+'_main'), A.OLD, final], out / 'graft.log')
        zero = out / 'memory_zero_history.pt'
        ablate(final, zero)
        ev = out / 'eval'
        ev.mkdir(exist_ok=True)
        for arm, ck in (('old', A.OLD), ('memory', final), ('zero', zero)):
            for census, decks, start in (('evo', A.EVO, 30000), ('lad', A.LAD, 30480)):
                dest = ev / f'{arm}_{census}'
                if dest.exists():
                    dest.rename(ev / f'{arm}_{census}.prior_{time.time_ns()}')
                A.run(A.eval_command(ck, dest, decks, start, a.workers, 480), ev / f'{arm}_{census}.log')
        summary = report(ev)
        artifacts = [final, zero, *ev.glob('*/matches.jsonl')]
    (out / 'SUMMARY.txt').write_text(summary+'\n', encoding='utf-8')
    artifacts.append(out/'SUMMARY.txt')
    A.atomic_json(complete, {str(path): digest(path) for path in artifacts})


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase', choices=('P1', 'P2', 'P3', 'P4'), required=True)
    p.add_argument('--results', type=Path, default=Path('/workspace/results/wk'))
    p.add_argument('--init', type=Path, default=A.FAST)
    p.add_argument('--template', type=Path, default=A.DATA)
    p.add_argument('--corpus', type=Path, nargs='+')
    p.add_argument('--cap', type=int, default=256)
    p.add_argument('--epochs', type=int, default=3)
    p.add_argument('--kl', type=float, default=1.0)
    p.add_argument('--workers', type=int, default=20)
    p.add_argument('--prefix', default='wk_memory')
    a = p.parse_args(argv)
    a.results = a.results.resolve()
    execute(a)


if __name__ == '__main__':
    main()
