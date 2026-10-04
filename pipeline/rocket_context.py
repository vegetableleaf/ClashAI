"""IL row weighting from a learned PUBLIC joint Rocket/X-Bow context probability.

This module contains no Rocket action rule or HP/elixir threshold. Probabilities
are loss-only annotations, never policy inputs. The data producer must attach
replay-disjoint fit/tune/test evidence before full version-4 training is allowed.
The historical rocket_context_probability field carries the joint probability;
it must cover the owner's X-Bow amendment too, not a finish-only/Rocket-only fit.
"""
import math
import numpy as np
import torch
import torch.nn.functional as F


def load_weight_artifact(path, dataset):
    import hashlib
    import json
    from pathlib import Path
    def sha(p):
        h = hashlib.sha256()
        with Path(p).open('rb') as f:
            for block in iter(lambda: f.read(1048576), b''): h.update(block)
        return h.hexdigest()
    path = Path(path)
    evidence = json.loads(path.read_text())
    files = {'dataset': Path(dataset), 'classifier': path.parent/'classifier.pt',
             'heldout_report': path.parent/'heldout_report.json', 'probability': path.parent/'probability.npy'}
    for name, source in files.items():
        if sha(source) != evidence.get(name+'_sha256'):
            raise ValueError('Context artifact provenance mismatch: '+name)
    return np.load(files['probability'], mmap_mode='r', allow_pickle=False), evidence


def row_weights(probability, weight):
    if not math.isfinite(weight) or weight < 1:
        raise ValueError('Rocket context weight must be finite and >= 1')
    if not torch.isfinite(probability).all() or ((probability < 0) | (probability > 1)).any():
        raise ValueError('Context probabilities must be finite and in [0, 1]')
    return 1 + (weight - 1) * probability.detach()


def mean_loss(loss, weights):
    return (loss*weights).sum()/weights.sum().clamp(min=1)


def weighted_ce(logits, target, weights):
    ok = target >= 0
    if not ok.any():
        return logits.new_zeros(())
    return mean_loss(F.cross_entropy(logits[ok], target[ok], reduction='none'), weights[ok])


def require_weight_artifact(arrays, meta, weight, *, exclude_defensive_xbow=False, inputs_only=False):
    if inputs_only:
        if weight != 1:
            raise ValueError('Inputs-only deadline fallback requires explicit weight 1')
        return
    p = np.asarray(arrays.get('rocket_context_probability', []))
    evidence = meta.get('rocket_context', {})
    if p.shape != np.asarray(arrays['y_gate']).shape or not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
        raise ValueError('Missing or invalid learned Rocket context probabilities')
    groups = [set(evidence.get(k, [])) for k in ('fit_tags', 'tune_tags', 'test_tags')]
    if any(not g for g in groups) or any(groups[i] & groups[j] for i in range(3) for j in range(i)):
        raise ValueError('Rocket context fit/tune/test replay groups must be nonempty and disjoint')
    if (evidence.get('public_only') is not True or not evidence.get('classifier_sha256') or
            not evidence.get('heldout_report_sha256') or weight is None or
            evidence.get('selected_weight') != weight or weight <= 1):
        raise ValueError('Missing public-context classifier or held-out weight selection evidence')
    required = {'tower_rocket', 'xbow_lane', 'defensive_xbow_rocket_cycle',
                'defensive_rocket', 'rocket_then_tornado', 'tornado_then_rocket'}
    if exclude_defensive_xbow:
        if evidence.get('defensive_xbow_excluded') is not True:
            raise ValueError('Missing explicit defensive-X-Bow exclusion in artifact')
        required.remove('defensive_xbow_rocket_cycle')
    if not required.issubset(set(evidence.get('context_targets', []))):
        raise ValueError('Joint Rocket/X-Bow and BOTH Tornado-order context targets are required by the amended contract')
