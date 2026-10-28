"""Re-run the self-check of finished chunks (their corpus is kept in SRC/work/<sid>/corpus) with the current selfcheck.py.
    python -I diag_chunk.py SRC LOGS sid [sid ...]   -> SRC/selfcheck_diag/<sid>.json (+ examples on stdout)"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_rows as LR  # noqa: E402

src, logs = Path(sys.argv[1]), Path(sys.argv[2])
DG = LR._patch()
import slot_redrive  # noqa: E402,F401  (wait_stride 10, play_window 0)
import selfcheck as SC  # noqa: E402

(src / 'selfcheck_diag').mkdir(exist_ok=True)
for sid in sys.argv[3:]:
    w = src / 'work' / sid
    npz = w / 'rows_diag.npz'
    DG.build([w / 'corpus'], npz, grid='lattice', workers=1, val_pct=0, v3val_npz=Path('/nonexistent.npz'), feature_version=5, log=None)
    r = SC.check_npz(npz, logs)
    npz.unlink()
    (src / 'selfcheck_diag' / f'{sid}.json').write_text(json.dumps(r))
    c = r['c']
    print(sid, {k: v for k, v in sorted(c.items()) if k.startswith('opp_')})
    for e in r['ex']:
        print('  ', json.dumps(e)[:300])
