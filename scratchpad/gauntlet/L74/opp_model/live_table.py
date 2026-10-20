"""L74/opp_model: one table of every graded live ladder match (both decks), with the trophy level, an exact crown timeline and the
opponent's detected plays.  Single process, below-normal priority, reads local files only (never touches the live process).

    icebow/.venv/Scripts/python.exe -I scratchpad/gauntlet/L74/opp_model/live_table.py [--limit N]
      -> opp_model/cache/<log stem>.json.gz (one per log, re-used on re-runs; NOT committed)
      -> opp_model/out/live_matches.jsonl.gz (one row per graded match; NOT committed, rebuilt in ~30-60 min cold, seconds warm)

Sources (all the same code the existing tools use, so numbers are comparable):
  result + trophy delta: monitor/card_use.results() (overnight.out, incl. its trophy-total fallback);
  trophies BEFORE the match: the '[ladder] trophies: N total' readings of overnight.out (a reading = the total after the
      previous match) carried forward with each match's delta; `tro_gap` = matches since the last reading (0 = exact);
  Mark: the start event's ckpt_sha256 through models/registry.json (as habits/index.py), else the checkpoint file name;
  opponent plays: human/opp_behaviour.plays_of = pipeline.opp_elixir_count.PlayDetector on the decision events' public
      raw_bodies (the live counter's own detector; bodiless spells are invisible) + pre_est (the public counter before each);
  towers: crown towers (card_id -1 at the six slots) in the same raw_bodies; a tower FALLS at the first decision after which it
      stays missing / <= 0 for the rest of the match (doctrine/measure.load_live's rule, at decision resolution ~10 ticks);
  clock = game tick - 78 (doctrine: live regulation-end frames sit at 3676-3681)."""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import time
from pathlib import Path

import orjson


def loads(raw):
    """orjson, falling back to json for the odd line it rejects (NaN / Infinity)."""
    try:
        return orjson.loads(raw)
    except orjson.JSONDecodeError:
        return json.loads(raw)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(ROOT / 'scratchpad/gauntlet/L74/human'), str(ROOT / 'scratchpad/gauntlet/L74/monitor'),
                str(ROOT / 'scratchpad/gauntlet/L74/weekend')]
import opp_behaviour as OB  # noqa: E402  (sets below-normal priority on import)
import card_use  # noqa: E402
import archetypes as A  # noqa: E402
from pipeline.obs_contract import catalog_card_form  # noqa: E402

LOGS = ROOT / 'scratchpad/gauntlet/L68/live_reader'
OVN = ROOT / 'scratchpad/gauntlet/L70/live/overnight.out'
REG = ROOT / 'scratchpad/gauntlet/L74/models/registry.json'
CACHE, OUT = HERE / 'cache', HERE / 'out'
LIVE_OFF = 78
SLOTS = ((9000, 3000), (3500, 6500), (14500, 6500), (9000, 29000), (3500, 25500), (14500, 25500))
PARSER_VERSION = 2
MAX_DELTA = 100       # card_use.results' trophy-total fallback across an ACCOUNT SWITCH yields +-7,000..10,000 deltas (29 matches):
                      # those grades are not real -> res 'BADDELTA' (excluded), and the delta is not carried into the trophy track


def trophy_track():
    """{log: (trophies before the match, matches since the last exact reading)} in overnight.out order."""
    res = card_use.results()
    before, cur, since = {}, None, 0
    for line in OVN.read_text(encoding='utf-8', errors='replace').splitlines():
        if line.startswith('{') and '"log"' in line:
            try:
                log = Path(json.loads(line)['log']).name
            except (ValueError, KeyError):
                continue
            if log in before:
                continue
            before[log] = (cur, since)
            if cur is not None and log in res and abs(res[log][1]) <= MAX_DELTA:
                cur += res[log][1]
            since += 1
        elif line.startswith('[ladder] trophies:'):
            m = re.match(r'\[ladder\] trophies: (\d+) total', line)
            if m:
                cur, since = int(m[1]), 0
    return res, before


def slot(x, y):
    for k, (sx, sy) in enumerate(SLOTS):
        if abs(x - sx) < 600 and abs(y - sy) < 600:
            return k
    return None


def parse_log(path):
    """One pass over a live_play log -> dict (or None when it has < 20 decisions with public bodies)."""
    side, frames, est, mine, tow, ticks, seen = None, [], [], [], {}, [], set()
    start = end = None
    own_conf = []
    with open(path, 'rb') as fh:
        for raw in fh:
            if raw.startswith(b'{"event": "decision"'):
                d = loads(raw)
                p = d.get('public') or {}
                if 'observer_side' not in p or 'raw_bodies' not in p:
                    continue
                side = int(p['observer_side'])
                t = int(d['tick'])
                bodies = p['raw_bodies']
                ticks.append(t)
                for b in bodies:
                    if b.get('card_id') == -1:
                        k = slot(b['x'], b['y'])
                        if k is not None:
                            tow.setdefault(k, {})[t] = (b['side'], b.get('hp') or 0, b.get('max_hp') or 0)
                    elif b.get('side') != side and b.get('card_id') is not None and b['card_id'] >= 0:
                        seen.add(b['card_id'])
                frames.append((t, bodies))
                if p.get('opponent_elixir_estimate') is not None:
                    est.append((t, float(p['opponent_elixir_estimate'])))
            elif raw.startswith(b'{"event": "play"'):
                mine.append(int(loads(raw)['tick']))
            elif raw.startswith(b'{"event": "confirmed"'):
                j = loads(raw)
                own_conf.append((j.get('tick') or 0, j.get('name')))
            elif raw.startswith(b'{"event": "start"') and start is None:
                j = loads(raw)
                start = dict(ckpt=j.get('ckpt'), sha=j.get('ckpt_sha256'), dry=bool(j.get('dry_run')))
            elif raw.startswith(b'{"event": "end"'):
                j = loads(raw)
                end = dict(seconds=j.get('seconds'), towers=j.get('towers'))
    if side is None or len(frames) < 20:
        return None
    plays = OB.pre_est(OB.plays_of(frames, side), est)
    last = ticks[-1]
    falls, hp0 = {}, {}
    for k, ser in tow.items():
        s_ = next(iter(ser.values()))[0]
        who = 'own' if s_ == side else 'opp'
        name = who + '_' + ('K' if k in (0, 3) else 'P%d' % k)
        alive = [t for t, (_, hp, _) in ser.items() if hp > 0]
        hp0[name] = max(m for _, _, m in ser.values())
        if alive and max(alive) < last:
            falls[name] = next(t for t in ticks if t > max(alive)) - LIVE_OFF
        elif not alive:
            falls[name] = ticks[0] - LIVE_OFF
    names = {A.canon(catalog_card_form(c)[0]) for c in seen if catalog_card_form(c)[0]} | {A.canon(p[1]) for p in plays}
    return dict(v=PARSER_VERSION, side=side, t0=ticks[0], end=last, plays=plays, mine=mine, own_conf=own_conf,
                falls=falls, tower_maxhp=hp0, seen=sorted(names), start=start, end_evt=end, n_dec=len(frames),
                towers_seen=len(tow))


def cached(path):
    c = CACHE / (path.stem + '.json.gz')
    if c.exists():
        try:
            with gzip.open(c, 'rb') as fh:
                d = orjson.loads(fh.read())
            if d.get('v') == PARSER_VERSION or d.get('none'):
                return None if d.get('none') else d
        except (OSError, ValueError):
            pass
    d = parse_log(path)
    CACHE.mkdir(exist_ok=True)
    tmp = c.with_suffix('.tmp')
    with gzip.open(tmp, 'wb') as fh:
        fh.write(orjson.dumps(d if d is not None else {'none': True, 'v': PARSER_VERSION}))
    tmp.replace(c)
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0, help='parse only the newest N graded logs (testing)')
    a = ap.parse_args()
    reg = json.loads(REG.read_text(encoding='utf-8'))
    sha2mark = {f['sha256']: m['name'] for m in reg['marks'] for f in m.get('files', []) if f.get('sha256')}
    res, before = trophy_track()
    names = sorted(n for n in res if (LOGS / n).exists())
    if a.limit:
        names = names[-a.limit:]
    OUT.mkdir(exist_ok=True)
    t0, n_ok, n_none = time.time(), 0, 0
    with gzip.open(OUT / 'live_matches.jsonl.gz', 'wb') as out:
        for i, n in enumerate(names):
            d = cached(LOGS / n)
            if d is None or d['start'] is None or d['start']['dry']:
                n_none += 1
                continue
            ck = d['start']['ckpt'] or ''
            mark = sha2mark.get(d['start']['sha']) or Path(ck.replace('\\', '/')).name
            deck = 'bait' if (mark.startswith('Bait') or 'bait' in ck.lower()) else 'icebow'
            r, td = res[n]
            if abs(td) > MAX_DELTA:
                r = 'BADDELTA'
            tb, gap = before.get(n, (None, None))
            row = dict(log=n, ts=n[10:25], deck=deck, mark=mark, sha=d['start']['sha'], res=r,
                       win=1.0 if r == 'WIN' else 0.0 if r == 'LOSS' else 0.5, tro_d=td, tro=tb, tro_gap=gap,
                       arch=A.classify(d['seen']), **{k: d[k] for k in ('side', 't0', 'end', 'plays', 'mine', 'own_conf', 'falls',
                                                                    'tower_maxhp', 'seen', 'end_evt', 'n_dec', 'towers_seen')})
            out.write(orjson.dumps(row) + b'\n')
            n_ok += 1
            if i % 200 == 0:
                print(i, len(names), n, round(time.time() - t0), 's', flush=True)
    print('rows', n_ok, 'skipped (no public frames / dry / no start)', n_none, round(time.time() - t0), 's')


if __name__ == '__main__':
    main()
