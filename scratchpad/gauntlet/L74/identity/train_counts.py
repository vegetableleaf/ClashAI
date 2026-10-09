"""Training distribution of every (body class, side, unit_form) in gen_dataset_v32_fv5 (the live model's data).
Streams tok.npy / unit_form.npy out of the npz in chunks (adapted from L74/runover/train_ids.py). Single process,
below-normal priority.  python train_counts.py  -> train_counts.json
"""
import collections, json, os, sys, zipfile
try:
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception:
    pass
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '../../../..')))
from pipeline import vocab

NPZ = 'C:/Users/benpe/ClashBot/icebow/data/pipeline/gen_dataset_v32_fv5.npz'


def stream(zf, name):
    fh = zf.open(name)
    ver = np.lib.format.read_magic(fh)
    shape, fortran, dt = (np.lib.format.read_array_header_1_0 if ver == (1, 0) else np.lib.format.read_array_header_2_0)(fh)
    assert not fortran
    return fh, shape, dt


def main():
    zf = zipfile.ZipFile(NPZ)
    ft, shape, dt = stream(zf, 'tok.npy')
    ff, fshape, fdt = stream(zf, 'unit_form.npy')
    assert fshape[0] == shape[0] and shape[1] == 14, (shape, fshape)
    cnt = collections.Counter()
    done, k_ = 0, 1_000_000
    while done < shape[0]:
        k = min(k_, shape[0] - done)
        a = np.frombuffer(ft.read(k * 14 * dt.itemsize), dtype=dt).reshape(k, 14)
        f = np.frombuffer(ff.read(k * fdt.itemsize), dtype=fdt)
        body = a[:, 13] < 0.5
        cls = a[body, 0].astype(np.int64); enemy = (a[body, 1] < 0.5).astype(np.int64); fo = f[body].astype(np.int64)
        key = (cls * 2 + enemy) * 4 + fo
        u, c = np.unique(key, return_counts=True)
        for kk, cc in zip(u.tolist(), c.tolist()):
            cnt[kk] += cc
        done += k
    out = collections.defaultdict(dict)
    for kk, cc in cnt.items():
        cls, rest = divmod(kk, 8); enemy, fo = divmod(rest, 4)
        out[vocab.UNIT_VOCAB[cls]][f"{'enemy' if enemy else 'mine'}_f{fo}"] = cc
    json.dump(dict(npz=NPZ, rows_tok=int(shape[0]), counts=out), open(os.path.join(HERE, 'train_counts.json'), 'w'), indent=0)
    print('tokens', shape[0], 'classes', len(out))


if __name__ == '__main__':
    main()
