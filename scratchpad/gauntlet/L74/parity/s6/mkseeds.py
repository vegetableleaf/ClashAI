"""PARITY_ATTACKS / PARITY_BUFFS files for the S6 logs from the live reader's cue blocks (live log inline blocks, else the
phase-3 capture), so fights.py seeds every log's t0 attack state and buffs the same way (the new icebow/data captures are
not in fights.py's P3_DIR). Formats are fights.py's: {log file name: {tick: {generation: [...]}}}.

    python mkseeds.py OUT_DIR STEM [STEM ...]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_cues as LC   # noqa: E402

out, stems = Path(sys.argv[1]), sys.argv[2:]
att, buf = {}, {}
for stem in stems:
    src, n = LC.load(stem)
    a, b = {}, {}
    for t, row in LC.CUES.items():
        a[t] = {g: [c['att']['target_gen'], c['att']['prev_target_gen'], c['att']['progress_raw'], c['att']['load_raw'],
                    c['att']['pre_raw'], c['att']['seq_idx']] for g, c in row.items() if c['att']}
        b[t] = {g: [[x['name'], x['remaining_ms_raw']] for x in c['buffs']] for g, c in row.items() if c['buffs']}
    att[stem + '.jsonl'], buf[stem + '.jsonl'] = a, b
    print(stem, src, n)
out.mkdir(parents=True, exist_ok=True)
(out / 'attacks.json').write_text(json.dumps(att, separators=(',', ':')))
(out / 'buffs.json').write_text(json.dumps(buf, separators=(',', ':')))
