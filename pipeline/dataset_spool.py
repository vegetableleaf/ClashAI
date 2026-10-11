"""Disk-backed intermediates for the single-worker version-4 dataset build.

Keeps at most one replay and a few final scalar arrays in resident memory. The
intermediate directory is unique to this invocation and retained for diagnosis.
No sampling, precision or ordering change is made.
"""
import pickle
from pathlib import Path
import numpy as np


def select_npz_rows(path, key, indices):
    """Stream selected rows of a large, C-order numeric NPZ member.

    Pro-agreement must not inflate the entire padded match history into RAM.
    Sorted replay row indexes permit forward-only decompression.
    """
    import zipfile
    indices = np.asarray(indices, dtype=np.int64)
    if len(indices) > 1 and np.any(np.diff(indices) <= 0):
        raise ValueError('row indices must be strictly increasing')
    with zipfile.ZipFile(path) as archive, archive.open(key+'.npy') as f:
        version = np.lib.format.read_magic(f)
        if version == (1, 0):
            shape, fortran, dtype = np.lib.format.read_array_header_1_0(f)
        elif version == (2, 0):
            shape, fortran, dtype = np.lib.format.read_array_header_2_0(f)
        else:
            raise ValueError('unsupported npy header')
        if fortran or dtype.hasobject or not shape:
            raise ValueError('requires a C-order numeric row array')
        if len(indices) and (indices[0] < 0 or indices[-1] >= shape[0]):
            raise IndexError('dataset row out of range')
        out = np.empty((len(indices), *shape[1:]), dtype=dtype)
        width = int(np.prod(shape[1:]))*dtype.itemsize
        position = 0
        for i, row in enumerate(indices):
            remaining = (int(row)-position)*width
            while remaining:
                chunk = f.read(min(remaining, 1024*1024))
                if not chunk:
                    raise ValueError('truncated history array')
                remaining -= len(chunk)
            data = f.read(width)
            if len(data) != width:
                raise ValueError('truncated history row')
            out[i] = np.frombuffer(data, dtype=dtype).reshape(shape[1:])
            position = int(row)+1
    return out


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
    if meta.get('feature_version') not in (4, 5, 6):
        raise ValueError('Memory-mapped training requires public feature version 4, 5 or 6')
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
