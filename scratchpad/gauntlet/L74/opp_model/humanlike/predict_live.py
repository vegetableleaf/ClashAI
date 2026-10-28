"""P2-SCORE split item (d), plan1026 level D1: a per-match P_hat for live matches = 64 SIM games of the deployed Mark (CLXIII,
gap.py D3 live stack, G2 on) vs the opponent model with that match's BATTLE-LOG decks and levels (both sides) and tower troop.

    python -I predict_live.py jobs --block calibration [--games 64] [--limit N] --out JOBS.jsonl     # laptop or pod, light
    python -I pairs.py run --jobs JOBS.jsonl --out DIR --opp-ckpt OPP --g2 [--opp-extra ...]         # pod: the games
    python -I predict_live.py predict --jobs JOBS.jsonl --rows DIR --out PRED.json                   # P_hat per match + sha256
    python -I predict_live.py grade --pred PRED.json                                                 # outcomes, only now

Blindness (the pre-registration rule): `jobs` and `predict` read ONLY decks, levels, tower troops and the battle time from
crapi/data/own_battlelog.jsonl (BLIND_KEYS); outcomes (crowns, trophy change, tower HP) are read by `grade` alone, which refuses
unless PRED.json's sha256 is already in data/predict_log.jsonl (written by `predict`, append-only).  The SEALED block is used
only with --block sealed (level D, read last); everything else defaults to the calibration block.
Card names: API display name -> alnum key -> engine name through newsim/census.aliases over mix/live_pool.engine_names();
evolutionLevel 1 -> '@evolution', 2 -> '@hero'; level -> display scale level + (16 - maxLevel), clamped (rl_royale.card_level)."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zlib
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import card as CD  # noqa: E402

BL = CD.L74 / 'crapi/data/own_battlelog.jsonl'
LOG = HERE / 'data' / 'predict_log.jsonl'
TYPES = ('pathOfLegend', 'PvP')            # Ranked + ladder 1v1 against humans
UTC_OFFSET = timedelta(hours=-4)            # live_split.json is local EDT (UTC-4 until 2026-11-01)
TOWERS = {'daggerduchess': 'DaggerDuchess', 'cannoneer': 'Cannoneer', 'royalchef': 'ChefTower'}
BLIND_KEYS = ('battleTime', 'type', 'leagueNumber')
SIDE_KEYS = ('tag', 'cards', 'supportCards', 'startingTrophies')


def _key(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def battles(block):
    """[(key, local stem time, blind battle dict)] of OUR 1v1 human battles in the block, oldest first. Outcome fields are
    dropped here, before anything else sees the record."""
    out, seen = [], set()
    for line in open(BL, encoding='utf-8'):
        b = json.loads(line)['battle']
        if b.get('type') not in TYPES or len(b.get('team') or []) != 1 or len(b.get('opponent') or []) != 1:
            continue
        t = datetime.strptime(b['battleTime'][:15], '%Y%m%dT%H%M%S') + UTC_OFFSET
        stem = t.strftime('%Y%m%d_%H%M%S')
        if CD.block_of(stem) != block:
            continue
        blind = {k: b.get(k) for k in BLIND_KEYS}
        for s in ('team', 'opponent'):
            blind[s] = {k: b[s][0].get(k) for k in SIDE_KEYS}
        key = f"{b['battleTime']}:{blind['opponent']['tag']}"
        if key not in seen:
            seen.add(key)
            out.append((key, stem, blind))
    return sorted(out, key=lambda x: x[1])


_MAP = None


def deck_of(side):
    """API side -> ([engine names in battle order], [display levels], tower troop or None, unmapped names)."""
    global _MAP
    if _MAP is None:
        sys.path[:0] = [str(CD.L74 / 'mix'), str(CD.ROOT)]
        import live_pool as LP
        from scratchpad.gauntlet.L74.newsim import census
        _MAP = (census.aliases(LP.engine_names()), census.key)
    mapping, key = _MAP
    from pipeline.rl_royale import card_level
    names, levels, bad = [], [], []
    for c in side['cards']:
        nm = mapping.get(key(c['name'])) or mapping.get(_key(c['name']))
        if nm is None:
            bad.append(c['name'])
            continue
        ev = int(c.get('evolutionLevel') or 0)
        names.append(nm + ('@hero' if ev >= 2 else '@evolution' if ev == 1 else ''))
        levels.append(card_level(nm, int(c['level']) + 16 - int(c['maxLevel'])))
    tw = [s for s in side.get('supportCards') or []]
    tower = int(tw[0]['level']) + 16 - int(tw[0]['maxLevel']) if tw else 16
    troop = TOWERS.get(_key(tw[0]['name'])) if tw else None
    return names, levels, tower, troop, bad


def jobs(a):
    rows, skipped = [], defaultdict(int)
    bs = battles(a.block)[: a.limit or None]
    for i, (key, stem, b) in enumerate(bs):
        on, ol, ot, otroop, ob = deck_of(b['opponent'])
        mn, ml, mt, _, mb = deck_of(b['team'])
        if ob or mb or len(on) != 8 or len(mn) != 8:
            skipped['unmapped:' + ','.join(ob + mb)] += 1
            continue
        if sorted(n.split('@')[0] for n in mn) != sorted(n.split('@')[0] for n in CD_ICE()):
            skipped['not_icebow'] += 1                         # our deck must be the deployed icebow
            continue
        order = {n.split('@')[0]: j for j, n in enumerate(mn)}
        ice = CD_ICE()
        lcards = [ml[order[n.split('@')[0]]] for n in ice]     # our levels in the engine deck order
        for g in range(a.games):
            rows.append(dict(key=key, stem=stem, seed=int(zlib.crc32(key.encode()) % 10_000_000) * 100 + g, learner_side=g % 2,
                             learner_deck=None, opp_deck=on, opp_tower=otroop,
                             levels={'learner': {'cards': lcards, 'tower': mt}, 'opp': {'cards': ol, 'tower': ot}},
                             league=b.get('leagueNumber'), opp_trophies=b['opponent'].get('startingTrophies'),
                             arch=CD.arch2([n.split('@')[0] for n in on])))
    Path(a.out).write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
    sha = hashlib.sha256(Path(a.out).read_bytes()).hexdigest()
    print(json.dumps(dict(block=a.block, battles=len(bs), matches=len({r['key'] for r in rows}), rows=len(rows), skipped=dict(skipped),
                          jobs_sha256=sha)))


def CD_ICE():
    sys.path.insert(0, str(CD.ROOT))
    from pipeline import e1_eval as E
    return list(E.ICEBOW_ENGINE_DECK)


def predict(a):
    sys.path.insert(0, str(HERE))
    import pairs
    jr = [json.loads(x) for x in open(a.jobs, encoding='utf-8') if x.strip()]
    res = defaultdict(lambda: [0.0, 0])
    for r in pairs.rows_of(a.rows):
        i = int(r['tag'].split(':')[1])
        k = jr[i]['key']
        res[k][0] += 1.0 if r['outcome'] == 'win' else 0.5 if r['outcome'] == 'draw' else 0.0
        res[k][1] += 1
    meta = {jr[i]['key']: jr[i] for i in range(len(jr))}
    pred = {k: dict(p_hat=w / n, n=n, arch=meta[k]['arch'], stem=meta[k]['stem']) for k, (w, n) in sorted(res.items())}
    run = json.loads((Path(a.rows) / 'run.json').read_text())
    doc = dict(jobs_sha256=hashlib.sha256(Path(a.jobs).read_bytes()).hexdigest(), run=run, n_matches=len(pred),
               games=sum(v['n'] for v in pred.values()), predictions=pred)
    Path(a.out).write_text(json.dumps(doc, indent=1), encoding='utf-8')
    sha = hashlib.sha256(Path(a.out).read_bytes()).hexdigest()
    LOG.parent.mkdir(exist_ok=True)
    with open(LOG, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(dict(when=datetime.now().isoformat(timespec='seconds'), pred=str(a.out), sha256=sha,
                                 n=len(pred))) + '\n')
    print('predictions', len(pred), 'sha256', sha, '(logged in', LOG, ')')


def grade(a):
    raw = Path(a.pred).read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    logged = {json.loads(x)['sha256'] for x in open(LOG, encoding='utf-8')} if LOG.exists() else set()
    if sha not in logged:
        raise SystemExit('refusing: the predictions are not in data/predict_log.jsonl (write them with `predict` first)')
    pred = json.loads(raw)['predictions']
    out = {}
    for line in open(BL, encoding='utf-8'):
        b = json.loads(line)['battle']
        k = f"{b['battleTime']}:{b['opponent'][0]['tag']}" if b.get('opponent') else None
        if k in pred:
            c, o = b['team'][0].get('crowns', 0), b['opponent'][0].get('crowns', 0)
            out[k] = 1.0 if c > o else 0.0 if c < o else 0.5
    ks = [k for k in pred if k in out]
    n = len(ks)
    p = [pred[k]['p_hat'] for k in ks]
    y = [out[k] for k in ks]
    mu = (sum(p) - sum(y)) / n
    import math
    sd = math.sqrt(sum((a_ - b_ - mu) ** 2 for a_, b_ in zip(p, y)) / max(1, n - 1))
    mp, my = sum(p) / n, sum(y) / n
    sxx = sum((x - mp) ** 2 for x in p)
    slope = sum((x - mp) * (z - my) for x, z in zip(p, y)) / sxx if sxx else float('nan')
    by = defaultdict(list)
    for k, x, z in zip(ks, p, y):
        by[pred[k]['arch']].append(x - z)
    print(json.dumps(dict(n=n, live_win=my, mean_p_hat=mp, resid_pp=100 * mu,
                          ci90_pp=(100 * (mu - 1.645 * sd / math.sqrt(n)), 100 * (mu + 1.645 * sd / math.sqrt(n))),
                          recal_slope=slope, arch={a_: (len(v), 100 * sum(v) / len(v)) for a_, v in by.items()}), indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('jobs', 'predict', 'grade'))
    ap.add_argument('--block', default='calibration', choices=('train', 'calibration', 'sealed'))
    ap.add_argument('--games', type=int, default=64)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--jobs')
    ap.add_argument('--rows')
    ap.add_argument('--pred')
    ap.add_argument('--out')
    a = ap.parse_args()
    {'jobs': jobs, 'predict': predict, 'grade': grade}[a.cmd](a)


if __name__ == '__main__':
    main()
