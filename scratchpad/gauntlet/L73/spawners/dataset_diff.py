"""Independent recount of Codex's corrected training archive vs the deployed-model archive (read-only, streamed in 1M-row
chunks, ~60 MB per chunk). Counts every (original class -> corrected class) transition of unit tokens and the class totals.
Writes dataset_diff.json."""
import os, sys, json, zipfile, collections
import numpy as np
from numpy.lib import format as F
ROOT = r'C:\Users\benpe\ClashBot'
sys.path.insert(0, ROOT)
from pipeline import vocab
inv = {v: k for k, v in vocab._ID.items()}
A = ROOT + r'\icebow\data\pipeline\gen_dataset_v31_public.npz'
B = ROOT + r'\icebow\data\bench\spawner_identity_20261005\gen_dataset_v5_public.npz'


def stream(path, name='tok.npy', rows=1_000_000):
    z = zipfile.ZipFile(path)
    f = z.open(name)
    v = F.read_magic(f)
    shape, fortran, dt = F.read_array_header_1_0(f) if v == (1, 0) else F.read_array_header_2_0(f)
    width = int(np.prod(shape[1:])) if len(shape) > 1 else 1
    left = shape[0]
    while left:
        n = min(rows, left)
        buf = f.read(n * width * dt.itemsize)
        yield np.frombuffer(buf, dtype=dt).reshape((n,) + tuple(shape[1:]))
        left -= n


trans = collections.Counter(); totals = collections.Counter(); ftrans = collections.Counter()
for a, b, fa, fb in zip(stream(A), stream(B), stream(A, 'unit_form.npy'), stream(B, 'unit_form.npy')):
    ca, cb = a[:, 0].astype(np.int64), b[:, 0].astype(np.int64)
    for c, n in zip(*np.unique(ca, return_counts=True)):
        totals[inv.get(int(c), int(c))] += int(n)
    d = ca != cb
    for (x, y), n in collections.Counter(zip(ca[d].tolist(), cb[d].tolist())).items():
        trans[(inv.get(x, x), inv.get(y, y))] += n
    dfm = (fa != fb) & ~d
    for (x, y, c), n in collections.Counter(zip(fa[dfm].tolist(), fb[dfm].tolist(), ca[dfm].tolist())).items():
        ftrans[(inv.get(c, c), x, y)] += n
out = dict(class_changes=[[a, b, n] for (a, b), n in trans.most_common()],
           form_only_changes=[[c, x, y, n] for (c, x, y), n in ftrans.most_common()],
           original_class_totals={k: totals[k] for k in ('witch', 'night_witch', 'furnace', 'tombstone', 'goblin_hut', 'barbarian_hut',
                                                          'skeletons', 'bats', 'fire_spirit', 'spear_goblins', 'barbarians', 'skeleton_barrel',
                                                          'goblin_drill', 'goblin_giant', 'goblin_cage', 'phoenix', 'mother_witch',
                                                          'mother_witch_hog', 'elixir_golem', 'elixir_golemite', 'elixir_blob')},
           total_changed=sum(trans.values()))
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dataset_diff.json'), 'w'), indent=1)
print(json.dumps(out, indent=0)[:3000])
