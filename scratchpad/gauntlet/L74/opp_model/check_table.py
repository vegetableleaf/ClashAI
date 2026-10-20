"""Self-check of out/live_matches.jsonl.gz: rows per Mark, trophy coverage, and the crown timeline vs the logged end-of-match
crowns + graded result (the doctrine's own validation: 737 / 739 matched).  python check_table.py"""
import gzip
import sys
from collections import Counter, defaultdict
from pathlib import Path

import orjson

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crowns as C  # noqa: E402

rows = [orjson.loads(l) for l in gzip.open(Path(__file__).resolve().parent / 'out/live_matches.jsonl.gz')]
by = defaultdict(list)
for r in rows:
    by[(r['deck'], r['mark'])].append(r)
print(len(rows), 'rows')
for (d, m), rs in sorted(by.items(), key=lambda kv: min(r['ts'] for r in kv[1])):
    tro = sorted(r['tro'] for r in rs if r['tro'] is not None)
    q = (lambda p: tro[int(p * (len(tro) - 1))]) if tro else (lambda p: None)
    print(f"{len(rs):5d} {d:6s} {m[:34]:34s} {min(r['ts'] for r in rs)} {max(r['ts'] for r in rs)} win {sum(r['win'] for r in rs) / len(rs):.3f}"
          f" tro p10/50/90 {q(.1)}/{q(.5)}/{q(.9)} exact-reading share {sum(r['tro_gap'] == 0 for r in rs) / len(rs):.2f}"
          f" plays/match {sum(len(r['plays']) for r in rs) / len(rs):.1f} towers6 {sum(r['towers_seen'] == 6 for r in rs) / len(rs):.2f}")
chk = Counter()
for r in rows:
    rec = C.live_rec(r)
    e = (r.get('end_evt') or {}).get('towers')
    if e and e.get('crowns_me') is not None:
        chk['end_evt ' + ('match' if (rec['c_all'], rec['oc_all']) == (e['crowns_me'], e['crowns_opp']) else 'mismatch')] += 1
    if rec['c_all'] != rec['oc_all'] and r['res'] in ('WIN', 'LOSS'):
        chk['result ' + ('match' if (rec['c_all'] > rec['oc_all']) == (r['res'] == 'WIN') else 'mismatch')] += 1
print(dict(chk))

# SIM telemetry rows: crowns from the exact tower frames vs the row's final crowns
import sim_sets as S  # noqa: E402
for k in [k for k in S.SETS if k[1].startswith(('tel_', 'c_hog'))]:
    ok = Counter()
    for r in S.rows(k):
        if r['falls'] is None:
            ok['no telemetry'] += 1
            continue
        c, oc = C._crowns(r['falls'], 'opp'), C._crowns(r['falls'], 'own')
        ok['match' if (c, oc) == (r['crowns_for'], r['crowns_against']) else 'mismatch'] += 1
    print(k, dict(ok))
