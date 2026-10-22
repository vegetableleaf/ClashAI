"""split_export.py LOGDIR OUTROOT TAG N ATT1 BUF1 [ATT2 BUF2 ...]: merge phase-3 / phase-2 exports (fights.py attacks / buffs
files: '_births' and '_shields' rows included) and split them with their logs into N chunk dirs
OUTROOT/TAG_<k>/{live/<log symlinks>, attacks.json, buffs.json}, so each fights.py run loads a small export
(a worker re-reads PARITY_ATTACKS three times a match: one 378 MB file x 48 workers does not fit in 80 GB)."""
import json
import os
import sys
from pathlib import Path

logdir, root, tag, n = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], int(sys.argv[4])
att, buf, births, shields = {}, {}, {}, {}
for a, b in zip(sys.argv[5::2], sys.argv[6::2]):
    x = json.loads(Path(a).read_text())
    births.update(x.pop('_births', {})); shields.update(x.pop('_shields', {}))
    att.update(x)
    buf.update(json.loads(Path(b).read_text()))
logs = sorted(k for k in att if (logdir / k).exists())
print(tag, 'logs', len(logs), 'missing log files', len(att) - len(logs), 'births', len(births), flush=True)
for k in range(n):
    part = logs[k::n]
    d = root / f'{tag}_{k:02d}'
    (d / 'live').mkdir(parents=True, exist_ok=True)
    for p in part:
        q = d / 'live' / p
        if not q.exists():
            os.symlink(logdir / p, q)
    a = {p: att[p] for p in part}
    a['_births'] = {p: births[p] for p in part if p in births}
    a['_shields'] = {p: shields[p] for p in part if p in shields}
    (d / 'attacks.json').write_text(json.dumps(a, separators=(',', ':')))
    (d / 'buffs.json').write_text(json.dumps({p: buf.get(p, {}) for p in part}))
    print(d, len(part), flush=True)
