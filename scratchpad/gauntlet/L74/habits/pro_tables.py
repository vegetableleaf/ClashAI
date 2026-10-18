"""L74/habits pro tables from pro_sides.jsonl (pro_extract.py): the same A / B (play-based) / C rules as live_tables.
Opponent elixir for pros = OppElixirCounter over ALL the opponent's plays (spells included: near the truth; hero/champion
ability costs and Elixir Collector production not modelled).
    python pro_tables.py [--json pro_rows.json]"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hablib as H  # noqa: E402
import live_tables as LT  # noqa: E402


def group(r):
    if r['src'] == 'crawl2':
        return 'pro icebow crawl2'
    return 'pro icebow8 HF' if r['icebow8'] else 'pro other X-Bow HF'


def load():
    out = []
    for l in open(HERE / 'pro_sides.jsonl', encoding='utf-8'):
        r = json.loads(l)
        own = [dict(tick=t, card=H.norm(c), x=x, y=y, why=None) for t, w, c, ab, x, y in r['ev'] if w == 'me' and not ab]
        opp = [dict(tick=t, card=H.norm(c), x=x, y=y) for t, w, c, ab, x, y in r['ev'] if w == 'op' and not ab]
        if not own:
            continue
        out.append(dict(src='pro', group=group(r), key=f"{r['src']}:{r['tag']}", win=r['win'], own=own, opp=opp,
                        mode=r['mode'], rocket_deck='rocket' in r['deck']))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', default=str(HERE / 'pro_rows.json'))
    a = ap.parse_args()
    ms = load()
    groups = ['pro icebow crawl2', 'pro icebow8 HF', 'pro other X-Bow HF']
    print('sides:', Counter(m['group'] for m in ms))
    X = [r for m in ms for r in H.xbow_events(m)]
    P = [r for m in ms for r in H.push_events(m)]
    K = [r for m in ms for r in H.rocket_uses(m)]
    LT.timing(ms, groups)
    LT.table_xbow(X, groups, 'A-pro. Bridge X-Bows (16 <= y <= 20.5)')
    LT.table_push(P, groups, 'B-pro. Heavy pushes, PLAY-based (>= 10 elixir of opponent troops played in 15 s)')
    LT.table_rocket([m for m in ms if m['rocket_deck']], K, groups)
    json.dump(dict(xbow=X, push_play=P, rocket=K), open(a.json, 'w'), default=str)


if __name__ == '__main__':
    main()
