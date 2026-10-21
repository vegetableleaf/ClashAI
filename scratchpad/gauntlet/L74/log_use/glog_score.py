"""G-LOG1 / G-LOG2 promotion-gate scorer on gap.py eval output dirs (LOG_USE.md section 5).

  python glog_score.py CANDIDATE_DIR [...] --base CLX_DIR [--json out.json]

Each DIR is searched recursively for matches.jsonl (gap.py / e1_eval per-match rows).
- G-LOG1 bait-hold rate: in matches whose opponent played a CORE log-bait card (log_use.CORE), the share with NO Log of
  ours before the opponent's first CORE bait play. Needs `o3_plays` (both seats' plays; the W12 / W7-opponent evals have
  them, D3 E4 evals do not -> G-LOG1 'n/a'). PASS: rate >= HOLD_MIN and the bootstrap 95% CI of (candidate - base) on the
  matches both arms share (same `tag` = seed + opponent) has its low end > 0 (unpaired bootstrap when no tags are shared).
- G-LOG2 guard: Logs per minute >= LPM_MIN (o3_plays learner, else own_plays), so "never Log" cannot pass G-LOG1.
Exit code 0 = every candidate passes both, 1 otherwise.
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import log_use as L                                     # noqa: E402

HOLD_MIN = 0.60      # above the best of 6 tn_base seeds (0.583); CLX 0.516, pros 0.733
LPM_MIN = 1.3        # pros 1.55, CLX SIM 1.62
LOG = 'the_log'


def k(c):
    return str(c).replace('-', '_').lower()


def load(d):
    out = {}
    from playlist import match_files
    for f in match_files(str(Path(d) / '**' / 'matches.jsonl')):
        for line in open(f, encoding='utf-8'):
            j = json.loads(line)
            o3 = j.get('o3_plays')
            if o3:
                own = [(t, k(c)) for t, c in o3['learner']]
                opp = [(t, k(c)) for t, c in o3['opp']]
            else:
                own = [(p[0], k(p[2])) for p in j.get('own_plays') or [] if len(p) > 3 and p[3]]
                opp = None
            logs = [t for t, c in own if c == LOG]
            hold = None
            if opp is not None:
                fb = min((t for t, c in opp if c in L.CORE), default=None)
                if fb is not None:
                    hold = not any(t < fb for t in logs)
            # a tag (s0:gen:SEED) is NOT unique: the same seed meets several census decks / sides
            tag = f"{j.get('tag')}|{j.get('opp_deck_name')}|{j.get('learner_side')}|{j.get('opp')}"
            out[tag] = dict(hold=hold, logs=len(logs), minutes=(j.get('end_tick') or 3600) / 1200, o3=opp is not None)
    return out


def boot(xs, B=2000, seed=0):
    rng = random.Random(seed)
    v = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(B))
    return v[int(.025 * B)], v[int(.975 * B) - 1]


def score(cand, base):
    c_h = [r['hold'] for r in cand.values() if r['hold'] is not None]
    lpm = sum(r['logs'] for r in cand.values()) / max(1e-9, sum(r['minutes'] for r in cand.values()))
    res = dict(matches=len(cand), logs_per_min=round(lpm, 3), g2_pass=lpm >= LPM_MIN)
    if not c_h:
        res.update(hold=None, g1_pass=None, note='no o3_plays: G-LOG1 not computable on this eval')
        return res
    rate = sum(c_h) / len(c_h)
    res.update(hold=round(rate, 4), bait_matches=len(c_h))
    if base:
        common = [t for t in cand if t in base and cand[t]['hold'] is not None and base[t]['hold'] is not None]
        if len(common) >= 100:
            d = [cand[t]['hold'] - base[t]['hold'] for t in common]
            lo, hi = boot(d); diff = sum(d) / len(d); how = f'paired on {len(common)} shared matches'
        else:
            b_h = [r['hold'] for r in base.values() if r['hold'] is not None]
            rng = random.Random(0); v = []
            for _ in range(2000):
                v.append(sum(rng.choice(c_h) for _ in c_h) / len(c_h) - sum(rng.choice(b_h) for _ in b_h) / len(b_h))
            v.sort(); lo, hi = v[50], v[1949]
            diff = rate - sum(b_h) / len(b_h); how = 'unpaired'
        res.update(diff_vs_base=round(diff, 4), ci=[round(lo, 4), round(hi, 4)], ci_method=how)
        res['g1_pass'] = rate >= HOLD_MIN and lo > 0
    else:
        res['g1_pass'] = rate >= HOLD_MIN
    return res


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--base', default=None, help='CLX eval dir (same eval setup / seeds)')
    ap.add_argument('--json', default=None)
    a = ap.parse_args(argv)
    base = load(a.base) if a.base else None
    if base is not None:
        b = score(base, None)
        print(f'BASE {a.base}: {b}')
    out, ok = {}, True
    for d in a.dirs:
        r = score(load(d), base)
        out[d] = r
        ok &= bool(r.get('g1_pass')) and bool(r.get('g2_pass'))
        print(f'{d}: G-LOG1 {"PASS" if r.get("g1_pass") else "FAIL" if r.get("g1_pass") is False else "n/a"} '
              f'G-LOG2 {"PASS" if r["g2_pass"] else "FAIL"} {r}')
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
