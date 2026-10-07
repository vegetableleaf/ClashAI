"""Offline expert exposure mixtures; never imported by a live policy."""
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np

from .rocket_teaching import sha

MIXTURES = {
    'uniform': {'pool': 1.0},
    'rocket': {'pool': .8, 'opportunity': .1, 'sequence': .1},
    'rocket_xbow': {'pool': .75, 'opportunity': .1, 'sequence': .1, 'xbow': .05},
    'rocket_barrel': {'pool': .75, 'opportunity': .1, 'sequence': .1, 'barrel': .05},
    'rocket_both': {'pool': .7, 'opportunity': .1, 'sequence': .1, 'xbow': .05, 'barrel': .05},
}


def probabilities(cohorts, split, arm):
    if arm not in MIXTURES:
        raise ValueError('Unknown predeclared arm')
    split = np.asarray(split)
    pool = np.asarray(cohorts['pool'])
    if pool.dtype != bool or pool.shape != split.shape:
        raise ValueError('Invalid pool')
    probability = np.zeros(len(split), np.float64)
    for name, mass in MIXTURES[arm].items():
        mask = np.asarray(cohorts[name])
        if mask.dtype != bool or mask.shape != pool.shape or (mask & ~pool).any():
            raise ValueError('Invalid cohort ' + name)
        eligible = mask & pool & (split == 0)
        if not eligible.any():
            raise ValueError('Empty required train cohort ' + name)
        probability[eligible] += mass / eligible.sum()
    if abs(probability.sum()-1) > 1e-12 or probability[split != 0].sum() != 0:
        raise ValueError('Invalid training distribution')
    return probability


def load_contexts(path, dataset, source_dataset, corrected_manifest=None):
    """Bind original cohorts to exact data; v5 may change only body class/form.

    The independent reconstruction verifier proves the corrected token columns;
    this loader additionally checks every untouched NPZ member on each run.
    """
    path, dataset, source_dataset = Path(path), Path(dataset), Path(source_dataset)
    manifest = json.loads((path/'manifest.json').read_text())
    if not manifest.get('trainable') or not manifest.get('public_only') or not manifest.get('training_split_only'):
        raise ValueError('Invalid expert-context provenance')
    if manifest['source_dataset_sha256'] != sha(source_dataset) or manifest['cohorts_sha256'] != sha(path/'cohorts.npz'):
        raise ValueError('Expert-context source changed')
    with np.load(dataset) as z:
        meta = json.loads(str(z['meta']))
    version = int(meta.get('feature_version', 1))
    binding = dict(dataset_sha256=sha(dataset), source_dataset_sha256=manifest['source_dataset_sha256'])
    if version == 4:
        if binding['dataset_sha256'] != manifest['source_dataset_sha256']:
            raise ValueError('v4 dataset differs from the cohort source')
    elif version == 5:
        if corrected_manifest is None:
            raise ValueError('Corrected dataset requires reconstruction manifest')
        correction = json.loads(Path(corrected_manifest).read_text())
        if (not correction.get('trainable') or correction['output_sha256'] != binding['dataset_sha256'] or
                correction['hashes']['dataset'] != manifest['source_dataset_sha256'] or
                meta.get('body_identity_contract') not in ('catalog_spawner_bodies_v1', 'catalog_spawner_bodies_v2_l73') or
                correction['stats']['reproduced_rows'] != correction['expected_affected_rows']):
            raise ValueError('Incomplete or mismatched corrected dataset')
        with ZipFile(source_dataset) as original, ZipFile(dataset) as new:
            if set(original.namelist()) != set(new.namelist()):
                raise ValueError('Changed dataset members')
            for name in set(original.namelist()) - {'tok.npy','unit_form.npy','meta.npy'}:
                a, b = original.getinfo(name), new.getinfo(name)
                if (a.CRC,a.file_size) != (b.CRC,b.file_size):
                    raise ValueError('Expert target or other input changed: ' + name)
        binding['correction_manifest_sha256'] = sha(corrected_manifest)
    else:
        raise ValueError('Unsupported context dataset version')
    with np.load(path/'cohorts.npz') as z:
        cohorts = {k:z[k] for k in z.files}
    return cohorts, manifest, meta, binding
