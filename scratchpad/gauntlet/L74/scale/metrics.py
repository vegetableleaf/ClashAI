"""Per-row sufficient statistics, globally weighted losses, replay-paired CIs."""
import numpy as np
import torch
import torch.nn.functional as F
from pipeline.model_v3 import cell_label

METRICS = ('card_top1', 'cell_top1', 'cell_top5', 'gate_acc')


def phase(tick):
    # Standard ladder schedule: 1x until 120s, 2x until 240s, then 3x.
    return np.where(np.asarray(tick) < 2400, 1, np.where(np.asarray(tick) < 4800, 2, 3))


def row_metrics(out, b, grid='lattice'):
    n = len(b['gate'])
    play = b['gate'] > .5
    for key in ('cell', 'gate', 'value'):
        if not torch.isfinite(out[key]).all():
            raise ValueError('Nonfinite evaluation head: '+key)
    # Card/wait heads may have legitimate -inf padding, but each row needs
    # a finite candidate and NaN/+inf are never acceptable.
    for key in ('card', 'wait'):
        v = out[key]
        if torch.isnan(v).any() or torch.isposinf(v).any() or not torch.isfinite(v).any(-1).all():
            raise ValueError('Invalid evaluation candidates: '+key)
    result = {k: torch.full((n,), float('nan'), device=play.device) for k in METRICS}
    result['gate_acc'] = ((out['gate'] > 0) == play).float()
    valid_card = play & (b['slot'] >= 0)
    result['card_top1'][valid_card] = (out['card'][valid_card].argmax(-1) == b['slot'][valid_card]).float()
    targets = cell_label(b['xy'][play], grid)
    result['cell_top1'][play] = (out['cell'][play].argmax(-1) == targets).float()
    result['cell_top5'][play] = (out['cell'][play].topk(min(5, out['cell'].shape[-1]), -1).indices == targets[:, None]).any(-1).float()
    # NaN means excluded, not zero. Summarization averages each head over its
    # own eligible rows, exactly matching train_gen's five-head objective.
    for key, logits, mask, target, weight in (
        ('card', out['card'], valid_card, b['slot'][valid_card], 1.),
        ('cell', out['cell'], play, targets, 1.),
        ('wait', out['wait'], ~play & (b['wait'] >= 0), b['wait'][~play & (b['wait'] >= 0)], .5),
        ('value', out['value'], torch.ones_like(play), b['value'], .5),
    ):
        v = torch.full((n,), float('nan'), device=play.device)
        if mask.any():
            v[mask] = weight * F.cross_entropy(logits[mask], target, reduction='none')
        result['loss_'+key] = v
    result['loss_gate'] = F.binary_cross_entropy_with_logits(out['gate'], b['gate'], reduction='none')
    return {k: v.detach().cpu().numpy() for k, v in result.items()}


def summarize(stats, mask):
    result = {'rows': int(np.count_nonzero(mask))}
    for k, values in stats.items():
        if k not in METRICS and not k.startswith('loss_'):
            continue
        v = np.asarray(values)[mask]
        v = v[np.isfinite(v)]
        result[k] = float(v.mean(dtype=np.float64)) if len(v) else None
        result[k+'_n'] = len(v)
    result['loss'] = sum(result[k] or 0. for k in result if k.startswith('loss_') and not k.endswith('_n')) if result['rows'] else None
    return result


def group_masks(phases, bridge, icebow):
    all_rows = np.ones(len(phases), bool)
    groups = {}
    for scope, subset in (('all_decks', all_rows), ('icebow', icebow)):
        groups[scope+'/overall'] = subset
        groups[scope+'/bridge'] = subset & bridge
        for p in (1, 2, 3):
            groups[f'{scope}/{p}x'] = subset & (phases == p)
            groups[f'{scope}/bridge/{p}x'] = subset & bridge & (phases == p)
    return groups


def paired_ci(a, b, rep, *, seed=740, draws=4000, confidence=.95):
    """Row-weighted paired difference; resample entire replay clusters, both sides together."""
    a, b, rep = np.asarray(a), np.asarray(b), np.asarray(rep)
    if a.shape != b.shape or rep.shape != a.shape:
        raise ValueError('Paired arrays must have identical shapes')
    if not np.array_equal(np.isfinite(a), np.isfinite(b)):
        raise ValueError('Arm metric eligibility differs')
    valid = np.isfinite(a)
    diff = (b[valid]-a[valid]).astype(np.float64)
    labels, inverse = np.unique(rep[valid], return_inverse=True)
    n = len(labels)
    if n < 2:
        return {'delta': float(diff.mean()) if len(diff) else None, 'lo': None, 'hi': None, 'replays': n, 'rows': len(diff)}
    totals = np.bincount(inverse, weights=diff)
    counts = np.bincount(inverse)
    rng, samples = np.random.default_rng(seed), np.empty(draws)
    for i in range(draws):
        picked = rng.integers(n, size=n)
        samples[i] = totals[picked].sum()/counts[picked].sum()
    tail = (1-confidence)/2
    lo, hi = np.quantile(samples, [tail, 1-tail])
    return {'delta': float(diff.mean()), 'lo': float(lo), 'hi': float(hi), 'replays': n, 'rows': len(diff), 'confidence': confidence}


def helps(comparison):
    return all(comparison[k].get('lo') is not None and comparison[k]['lo'] > 0 for k in ('card_top1', 'cell_top1'))
