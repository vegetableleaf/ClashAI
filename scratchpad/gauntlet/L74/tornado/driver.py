"""Gated pod experiment; planning and reporting are testable without a simulator."""
from __future__ import annotations

import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from pipeline.pending_states import digest

# Reuse the pinned CAL/S2 flags, checkpoint paths and census files of run_wk.
spec = importlib.util.spec_from_file_location('tornado_adaptive', Path(__file__).parents[1]/'weekend/adaptive/driver.py')
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)
GEN1 = Path('icebow/data/pipeline/gen_v1_s0/gen_s0.pt')
ICEBOW = ['ice-wizard', 'knight', 'the-log', 'rocket', 'skeletons', 'tesla', 'tornado', 'x-bow']
BAIT = ['dart-goblin', 'skeleton-army', 'valkyrie', 'goblin-barrel', 'princess', 'cannon', 'wall-breakers', 'ice-spirit']
PRO_FILE = Path('scratchpad/gauntlet/L74/pipeline_decisions/pro_pairs24.json')


def normalize(card):
    card = str(card).split('@')[0].replace('_', '-').lower()
    return {'log': 'the-log', 'icewizard': 'ice-wizard', 'xbow': 'x-bow'}.get(card, card)


def eval_command(ck, out, census, start, workers, opp, temperature, pipeline, bait=False):
    cmd = A.eval_command(ck, out, census, start, workers, 480)
    cmd[cmd.index('--opp-gen')+1] = str(opp)
    cmd[cmd.index('--opp-T')+1] = str(temperature)
    if bait:
        cmd[1:3] = ['scratchpad/gauntlet/L74/weekend/logbait_s0.py']
    cmd += ['--record-plays']
    if pipeline:
        cmd += ['--pipeline-decisions', '--pipeline-tau-delta', '0']
    return cmd


def interval(values, seed=74):
    """Seeded percentile bootstrap, 95% CI; paired contrasts resample differences."""
    values = np.asarray(values, dtype=float)
    if not len(values) or not np.isfinite(values).all():
        raise ValueError('empty/nonfinite confidence sample')
    rng = np.random.default_rng(seed)
    means = np.concatenate([rng.choice(values, (100, len(values))).mean(1) for _ in range(100)])
    lo, hi = np.quantile(means, [.025, .975])
    return dict(mean=float(values.mean()), low=float(lo), high=float(hi))


def profile(rows):
    second, plays, gaps, fast, elixir = Counter(), 0, 0, 0, []
    for row in rows:
        if 'own_plays' not in row:
            raise ValueError('missing play telemetry')
        accepted = sorted((q for q in row['own_plays'] if q[3]), key=lambda q: q[1])
        if len(accepted) != row['plays_accepted']:
            raise ValueError('incomplete accepted play telemetry')
        plays += len(accepted)
        for q in accepted:
            if q[1] < q[0] or q[4] is None or not np.isfinite(q[4]):
                raise ValueError('invalid play timing/elixir telemetry')
            elixir.append(q[4])
        for first, follow in zip(accepted, accepted[1:]):
            gaps += 1
            if follow[1] - first[1] <= 24:
                fast += 1
                second[normalize(follow[2])] += 1
    return dict(plays=plays, second_cards=fast, second_card_counts=dict(second),
                second_card_mix={c: n/fast for c, n in sorted(second.items())},
                share_plays_within_24_ticks=fast/plays if plays else None,
                share_consecutive_gaps_within_24_ticks=fast/gaps if gaps else None,
                elixir_at_play=float(np.mean(elixir)) if elixir else None,
                elixir_definition='raw observed own elixir at decision for accepted plays (existing record-plays telemetry)')


def compare(live, fixed, pro_mix, require_tornado=True, expected=960):
    if len(live) != expected or live.keys() != fixed.keys():
        raise ValueError('missing or unmatched paired games')
    keys = sorted(live)
    for key in keys:
        for field in ('seed', 'learner_side', 'opp_deck', 'opp_gen_sha256'):
            if live[key][field] != fixed[key][field]:
                raise ValueError(f'paired setup mismatch: {field}')
    win = lambda row: float(row['outcome'] == 'win')
    b = np.array([win(live[k]) for k in keys])
    c = np.array([win(fixed[k]) for k in keys])
    bp, cp = profile(live.values()), profile(fixed.values())
    delta = interval(c-b)
    tornado = cp['second_card_mix'].get('tornado', 0.)
    tornado_ok = (cp['second_cards'] > 0 and tornado <= 2*pro_mix['tornado']) if require_tornado else True
    return dict(n=expected, live_wins=int(b.sum()), fixed_wins=int(c.sum()),
                live_draws=sum(r['outcome'] == 'draw' for r in live.values()),
                fixed_draws=sum(r['outcome'] == 'draw' for r in fixed.values()),
                live_win_ci=interval(b), fixed_win_ci=interval(c), paired_win_delta_ci=delta,
                live_profile=bp, fixed_profile=cp, pro_second_card_mix=pro_mix,
                tornado_applicable=require_tornado, tornado_ok=tornado_ok,
                non_inferior=delta['low'] > -.03)


def load_group(out, arm, pipeline, init_sha, opp_sha, temperature, games=480):
    records = {}
    for census in ('evo', 'lad'):
        directory = out / f'{arm}_{census}'
        run = json.loads((directory/'run.json').read_text())
        if (run['gen_sha256'] != init_sha or run['opp_gen_sha256'] != opp_sha or
                run['opp_T'] != temperature or bool(run.get('pipeline_decisions')) != pipeline or
                run.get('pipeline_tau_delta', 0) != 0 or not run.get('record_plays')):
            raise ValueError('evaluation configuration or checkpoint mismatch')
        rows = [json.loads(s) for s in (directory/'matches.jsonl').read_text().splitlines()]
        if len(rows) != games:
            raise ValueError('incomplete census evaluation')
        for r in rows:
            key = (census, r.get('tag'))
            if (not r.get('tag') or key in records or r.get('skipped') or r.get('wall_truncated')
                    or r.get('outcome') not in ('win', 'draw', 'loss') or r.get('arm') != 'plain'
                    or not r.get('opp_deck') or r.get('opp_gen_sha256') != opp_sha
                    or ('pipeline_decisions' in r) != pipeline):
                raise ValueError('invalid, skipped, duplicate or truncated game')
            records[key] = r
    return records


def verdict(comparisons):
    required = {'hard_on', 'hard_off', 'old_on', 'old_off'}
    if comparisons.keys() != required:
        raise ValueError('all opponent/mode comparisons required')
    return 'candidate' if all(c['non_inferior'] and (not k.endswith('_on') or c['tornado_ok'])
                              for k, c in comparisons.items()) else 'not candidate'


def run(command, log):
    print('RUN ' + ' '.join(map(str, command)), flush=True)
    with Path(log).open('w', encoding='utf-8') as f:
        subprocess.run(list(map(str, command)), cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, check=True)


def summary_text(report):
    lines = ['VERDICT: '+report['verdict'], 'Nothing deployed. Wins count wins only; draws are reported separately.',
             '95% bootstrap CIs; paired differences in percentage points. Non-inferior requires lower bound > -3 pp.',
             'Second cards: consecutive accepted landings <=24 ticks; zero fast-follow observations cannot pass the Tornado gate.']
    for name, result in report['models'].items():
        dataset_summary = {k: result['dataset'][k] for k in (
            'source_sha256', 'source_rows', 'rows', 'train_rows', 'val_rows', 'all_deck_pending_rows', 'second_card_mix')}
        lines += ['', name+': '+result['verdict'], 'Dataset: '+json.dumps(dataset_summary),
                  'Selected training checkpoint: '+json.dumps(result['training'])]
        for label, c in result['comparisons'].items():
            lines.append(label + f": paired n={c['n']}")
            for arm in ('live', 'fixed'):
                ci = c[arm+'_win_ci']
                lines.append(f"  {arm}: wins={c[arm+'_wins']}, draws={c[arm+'_draws']}; "
                             f"win rate {100*ci['mean']:.2f}% [{100*ci['low']:.2f}, {100*ci['high']:.2f}]")
                lines.append('  '+arm+' profile: '+json.dumps(c[arm+'_profile'], sort_keys=True))
            ci = c['paired_win_delta_ci']
            lines.append(f"  fixed-live {100*ci['mean']:+.2f} pp [{100*ci['low']:+.2f}, {100*ci['high']:+.2f}]; "
                         f"non-inferior={c['non_inferior']}; Tornado gate={c['tornado_ok']}")
            lines.append('  Pros full second-card mix: '+json.dumps(c['pro_second_card_mix'], sort_keys=True))
    if report.get('bait_note'):
        lines.append(report['bait_note'])
    return '\n'.join(lines)+'\n'


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--data', type=Path, default=A.DATA)
    p.add_argument('--init', type=Path, default=A.OLD)
    p.add_argument('--hard', type=Path, default=A.CAL_C)
    p.add_argument('--old', type=Path, default=GEN1)
    p.add_argument('--bait-init', type=Path, help='optional generalist checkpoint for the existing S8 bait deck')
    p.add_argument('--workers', type=int, default=20)
    a = p.parse_args(argv)
    if a.workers < 1 or a.workers > 28:
        raise ValueError('workers must be 1..28 on the shared pod')
    a.out.mkdir(parents=True, exist_ok=True)
    manifest = a.out/'manifest.json'
    if manifest.exists():
        raise FileExistsError('fresh results directory required')
    paths = [a.data, a.init, a.hard, a.old, A.EVO, A.LAD, PRO_FILE]
    if a.bait_init:
        paths.append(a.bait_init)
    hashes = {str(path): digest(path) for path in paths}
    sources = [Path(__file__), Path(__file__).with_name('run_tornado_fix.sh')]
    sources += [ROOT/'pipeline'/name for name in ('pending_states.py', 'train_pending.py',
                'dataset_gen.py', 'model_gen.py', 'e1_eval.py', 'search_s0.py')]
    manifest.write_text(json.dumps(dict(args={k: str(v) for k, v in vars(a).items()}, sha256=hashes,
                                       source_sha256={str(p): digest(p) for p in sources}), indent=2)+'\n')
    pros = {normalize(c): v for c, v in json.loads(PRO_FILE.read_text())['second_mix_le_24'].items()}
    report = dict(verdict='not candidate', models={}, bait_note=(
        'S8 bait has no Tornado. Optional --bait-init enables the same pending-head/ordinary regression experiment '
        'from its generalist base; Tornado criterion is inapplicable to that deck.' if not a.bait_init else ''))
    models = [('icebow', a.init, ICEBOW)]
    if a.bait_init:
        models.append(('bait', a.bait_init, BAIT))
    for name, init, cards in models:
        out = a.out/name
        out.mkdir()
        index, fixed = out/'pending.npz', out/'fixed.pt'
        run([sys.executable, '-m', 'pipeline.pending_states', '--data', a.data, '--out', index, '--deck', *cards], out/'dataset.log')
        dataset = json.loads(index.with_suffix('.json').read_text())
        run([sys.executable, '-m', 'pipeline.train_pending', '--data', a.data, '--pending', index,
             '--init', init, '--out', fixed, '--device', 'cuda'], out/'train.log')
        import torch
        training = torch.load(fixed, map_location='cpu', weights_only=True)['pending_pretrain']
        if training['ordinary_top_card_drift'] >= .01:
            raise ValueError('selected checkpoint exceeds ordinary drift bound')
        comparisons = {}
        for opponent, ck, temperature in [('hard', a.hard, .1), ('old', a.old, .3)]:
            for pipelining in (True, False):
                label = opponent + ('_on' if pipelining else '_off')
                ev = out/label
                ev.mkdir()
                groups = {}
                for arm, learner in [('live', init), ('fixed', fixed)]:
                    for census, decks, start in [('evo', A.EVO, 30000), ('lad', A.LAD, 30480)]:
                        dest = ev/f'{arm}_{census}'
                        run(eval_command(learner, dest, decks, start, a.workers, ck, temperature,
                                         pipelining, name == 'bait'), ev/f'{arm}_{census}.log')
                    groups[arm] = load_group(ev, arm, pipelining, digest(learner), hashes[str(ck)], temperature)
                comparisons[label] = compare(groups['live'], groups['fixed'],
                    pros if name == 'icebow' else dataset['second_card_mix'], require_tornado=name == 'icebow')
        report['models'][name] = dict(verdict=verdict(comparisons), dataset=dataset, training=training, comparisons=comparisons)
        (a.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    report['verdict'] = 'candidate' if all(m['verdict'] == 'candidate' for m in report['models'].values()) else 'not candidate'
    (a.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    (a.out/'SUMMARY.txt').write_text(summary_text(report), encoding='utf-8')


if __name__ == '__main__':
    main()
