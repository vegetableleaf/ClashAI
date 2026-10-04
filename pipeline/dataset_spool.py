"""Disk-backed intermediates for the single-worker version-4 dataset build.

Keeps at most one replay and a few final scalar arrays in resident memory. The
intermediate directory is unique to this invocation and retained for diagnosis.
No sampling, precision or ordering change is made.
"""
import pickle
from pathlib import Path
import numpy as np


def load_mapped(path, cache):
    """Extract an immutable NPZ into a fresh cache, validating member names/CRC.

    Exclusive writes refuse stale/reused caches. NumPy arrays remain file-backed
    instead of retaining multi-GB projectile padding on the Python heap.
    """
    import hashlib
    import json
    import shutil
    import zipfile
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=False)
    arrays = {}
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate dataset member')
        for name in names:
            if Path(name).name != name or not name.endswith('.npy'):
                raise ValueError('Unsafe dataset member')
            with archive.open(name) as src, (cache/name).open('xb') as dst:
                shutil.copyfileobj(src, dst, length=1048576)
            arrays[name[:-4]] = np.load(cache/name, mmap_mode='c', allow_pickle=False)
    meta = json.loads(str(arrays.pop('meta')))
    if meta.get('feature_version') != 4:
        raise ValueError('Memory-mapped training is scoped to version4')
    return arrays, meta


class ReplaySpool:
    def __init__(self, root):
        self.root = Path(root)
        self.count = 0

    def append(self, row):
        with (self.root / f'replay_{self.count}.pickle').open('xb') as f:
            pickle.dump(row, f, protocol=5)
        self.count += 1

    def __len__(self):
        return self.count

    def __iter__(self):
        for i in range(self.count):
            with (self.root / f'replay_{i}.pickle').open('rb') as f:
                yield pickle.load(f)


class ArraySpool:
    def __init__(self, root):
        self.root = Path(root)
        self.fields = {}

    def append(self, name, array):
        a = np.ascontiguousarray(array)
        path = self.root / (name + '.bin')
        if name not in self.fields:
            self.fields[name] = [a.dtype, a.shape[1:], 0]
        dtype, tail, n = self.fields[name]
        if dtype != a.dtype or tail != a.shape[1:]:
            raise ValueError('Inconsistent spooled array: ' + name)
        with path.open('ab') as f:
            a.tofile(f)
        self.fields[name][2] += len(a)

    def arrays(self):
        return {name: np.memmap(self.root / (name + '.bin'), mode='r',
                               dtype=dtype, shape=(n, *tail))
                if n else np.empty((0, *tail), dtype=dtype)
                for name, (dtype, tail, n) in self.fields.items()}
