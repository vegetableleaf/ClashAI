"""Live card census (owner 10-17): how often each card is PLAYED in live ladder matches, with fights.py's own play detection
(read_match + deployments, no engine) -> the weights of the parity coverage metric (coverage.py).

A fight is cut around each play, so plays are the right unit: a card's share of live plays ~ its share of live fights.
Main-account logs only (read_match's rule); logs without frames are skipped.

  python census_cards.py OUT.json [--workers N] LOG [LOG ...]
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402

FORMS = ('', ' evo', ' hero')


def decision_frames(path, tmp):
    """A log without frame events (most logs before 10-16) -> a copy whose decision events' public raw_bodies stand in as frames
    (same row layout as frame 'ents'). Decisions come every ~20 ticks, not ~2, so a body that lives < ~1 s (kamikaze spirits)
    can fall between two samples: such cards are UNDERCOUNTED in these logs (b)."""
    with open(path, 'rb') as f, open(tmp, 'wb') as out:
        for raw in f:
            if b'"decision"' in raw[:40]:
                j = json.loads(raw); p = j.get('public') or {}
                ents = [[b['side'], b['x'], b['y'], b['card_id'], b['hp'], b['max_hp'], b['kind'], b.get('address', '')]
                        for b in p.get('raw_bodies') or []]
                if ents and p.get('observer_side') is not None:
                    out.write(json.dumps(dict(event='frame', tick=j['tick'], my_side=p['observer_side'], ents=ents)).encode() + b'\n')
            out.write(raw)
    return tmp


def one(path):
    """-> (stem, None, {label: plays}) or (stem, skip reason, None). Labels match ceiling_table's ('own '/'opp ' + name + form)."""
    catalog, _ = F.load_catalog()
    m, reason = F.read_match(path)
    source = 'frames'
    if m is None and reason == 'no_frames':
        import os, tempfile
        fd, tmp = tempfile.mkstemp(suffix='.jsonl'); os.close(fd)
        try:
            m, reason = F.read_match(decision_frames(path, tmp))
        finally:
            os.unlink(tmp)
        reason, source = reason and 'decisions:' + reason, 'decisions'
    if m is None:
        return Path(path).stem, reason, None, None
    plays = Counter()
    events, _ = F.deployments(m, catalog)
    for ev in events:
        if ev.get('kind') == 'play':
            plays[('own ' if ev['side'] == m['side'] else 'opp ') + ev['name'] + FORMS[ev.get('form') or 0]] += 1
    return Path(path).stem, None, dict(plays), source


def main(argv):
    out, workers = Path(argv[0]), 1
    argv = argv[1:]
    if argv and argv[0] == '--workers':
        workers, argv = int(argv[1]), argv[2:]
    per, skipped, sources = {}, Counter(), Counter()
    with ProcessPoolExecutor(workers) as ex:
        for stem, reason, plays, source in ex.map(one, argv, chunksize=4):
            if reason:
                skipped[reason] += 1
            else:
                per[stem] = plays; sources[source] += 1
    plays, matches = Counter(), Counter()
    for p in per.values():
        plays.update(p)
        matches.update(p.keys())
    out.write_text(json.dumps(dict(matches=len(per), sources=dict(sources), skipped=dict(skipped), plays=dict(plays.most_common()),
                                   matches_with=dict(matches.most_common()), per_match=per), indent=1))
    print(f"{len(per)} matches {dict(sources)}, skipped {dict(skipped)}, {sum(plays.values())} plays, {len(plays)} cards -> {out}")


if __name__ == '__main__':
    main(sys.argv[1:])
