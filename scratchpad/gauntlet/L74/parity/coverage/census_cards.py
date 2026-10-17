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


def one(path):
    """-> (stem, None, {label: plays}) or (stem, skip reason, None). Labels match ceiling_table's ('own '/'opp ' + name + form)."""
    catalog, _ = F.load_catalog()
    m, reason = F.read_match(path)
    if m is None:
        return Path(path).stem, reason, None
    plays = Counter()
    events, _ = F.deployments(m, catalog)
    for ev in events:
        if ev.get('kind') == 'play':
            plays[('own ' if ev['side'] == m['side'] else 'opp ') + ev['name'] + FORMS[ev.get('form') or 0]] += 1
    return Path(path).stem, None, dict(plays)


def main(argv):
    out, workers = Path(argv[0]), 1
    argv = argv[1:]
    if argv and argv[0] == '--workers':
        workers, argv = int(argv[1]), argv[2:]
    per, skipped = {}, Counter()
    with ProcessPoolExecutor(workers) as ex:
        for stem, reason, plays in ex.map(one, argv, chunksize=4):
            if reason:
                skipped[reason] += 1
            else:
                per[stem] = plays
    plays, matches = Counter(), Counter()
    for p in per.values():
        plays.update(p)
        matches.update(p.keys())
    out.write_text(json.dumps(dict(matches=len(per), skipped=dict(skipped), plays=dict(plays.most_common()),
                                   matches_with=dict(matches.most_common()), per_match=per), indent=1))
    print(f"{len(per)} matches, skipped {dict(skipped)}, {sum(plays.values())} plays, {len(plays)} cards -> {out}")


if __name__ == '__main__':
    main(sys.argv[1:])
