"""V1-LIVEROWS step 0: which live logs give opponent-seat rows (metadata only; the sealed block is never opened).

    python -I select.py            -> select.json (one entry per candidate log) + a summary on stdout

Sources: P2-SCORE's live_meta.jsonl (start-event metadata of every non-sealed log: mark, deck, dry, size), overnight.out
(per match: the '[ladder] result:' line after the match's summary JSON; 'trophies n/a' = Ranked (Path of Legends), a number =
ladder; trophies before = live_table.trophy_track). Kept: block train / calibration by NAME (live_split.json), icebow deck,
not dry, a result line (graded), and a band: R = Ranked, L = ladder 12,000-12,999, M = ladder >= 13,000 (other ladder
matches have no band and are left out). The 2-tick frame cadence and the account (tower level) are checked per log later."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
L74 = HERE.parents[2]
sys.path[:0] = [str(L74 / 'opp_model'), str(L74 / 'opp_model/humanlike')]
SPLIT = json.loads((HERE.parent / 'live_split.json').read_text())
META = L74 / 'opp_model/humanlike/data/live_meta.jsonl'
OVN = L74.parents[1] / 'gauntlet/L70/live/overnight.out'
RES = re.compile(r'\[ladder\] result: (\w+).*?trophies (n/a|[+-]?\d+)')


def block_of(stem):
    s = stem[len('live_play_'):]
    return 'train' if s < SPLIT['train_before'] else 'sealed' if s >= SPLIT['sealed_from'] else 'calibration'


def results():
    """{log name: (result, delta or None for Ranked)} -- card_use.results' pairing rule (summary JSON, then the next result)."""
    out, last = {}, None
    for line in OVN.read_text(encoding='utf-8', errors='replace').splitlines():
        if line.startswith('{') and '"log"' in line:
            try:
                last = Path(json.loads(line)['log'].replace(chr(92), '/')).name
            except (ValueError, KeyError):
                pass
        elif line.startswith('[ladder] result:') and last:
            m = RES.match(line)
            if m:
                out[last] = (m[1], None if m[2] == 'n/a' else int(m[2]))
            last = None
    return out


def band(ranked, tro):
    if ranked:
        return 'R'
    if tro is None:
        return None
    return 'M' if tro >= 13000 else 'L' if tro >= 12000 else None


def main():
    import live_table as LT                     # trophy_track only (overnight.out); never LT.main (it reads every log)
    res = results()
    _, before = LT.trophy_track()
    sel, why = [], Counter()
    for line in open(META, encoding='utf-8'):
        m = json.loads(line)
        st = m['stem']
        b = block_of(st)
        if b == 'sealed' or m['block'] == 'sealed':
            why['sealed'] += 1
            continue
        if m['deck'] != 'icebow' or m['dry'] or not m['has_start']:
            why['not_icebow_or_dry'] += 1
            continue
        r = res.get(st + '.jsonl')
        if r is None:
            why['no_result_line'] += 1
            continue
        tro = (before.get(st + '.jsonl') or (None, None))[0]
        bd = band(r[1] is None, tro)
        if bd is None:
            why['no_band'] += 1
            continue
        sel.append(dict(stem=st, block=b, band=bd, res=r[0], tro=tro, mark=m['mark'], sha=m['sha'], size=m['size'],
                        reader=m['reader']))
    (HERE / 'select.json').write_text(json.dumps(dict(split=SPLIT['blocks'], skipped=dict(why), logs=sel), indent=0))
    c = Counter((x['block'], x['band']) for x in sel)
    print(json.dumps(dict(selected=len(sel), skipped=dict(why), by_block_band={f'{k[0]}/{k[1]}': v for k, v in sorted(c.items())},
                          gb=round(sum(x['size'] for x in sel) / 1e9, 1))))


if __name__ == '__main__':
    main()
