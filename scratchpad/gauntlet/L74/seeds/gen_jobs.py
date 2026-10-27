"""G1 job builder: own battle log (opponent tags + both decks in slot order) x our live logs -> SeedSearch jobs.

    python -I gen_jobs.py --tables <crforge tables/16.402.22> --out <dir>

Per Ranked battle-log entry it finds the live log that played it (file-name start time, EDT, before the UTC battle end),
then writes <out>/<stem>.txt for SeedSearch and one row of <out>/census_decks.tsv for `Census decks`:
  our order  = own_hand deck_index at the first decision (hand slots 0-3), then each new deck_index as it enters (queue);
  opp plays  = opponent cards (deck slot indices) in first-seen order: a new body / projectile / effect of a deck card id,
               bodies of one card born within 40 ticks = one play; a spell = a new projectile / effect after 40 ticks unseen.
Words: the low word of the account id from the tag (base 14 over 0289PYLQGRJCUV; id = low << 8 | high) -- (b), the
community decoding; G1 on the replay recording is the only check (CRFORGE_S0.md).
"""
import argparse, datetime as dt, json, os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BATTLELOG = ROOT / 'scratchpad/gauntlet/L74/crapi/data/own_battlelog.jsonl'
LIVE = ROOT / 'scratchpad/gauntlet/L68/live_reader'
ALPHA = '0289PYLQGRJCUV'
GROUP = 40


def word(tag):
    n = 0
    for c in tag.lstrip('#').upper():
        n = n * 14 + ALPHA.index(c)
    lo = (n >> 8) & 0xffffffff
    return lo - (1 << 32) if lo >= 1 << 31 else lo


def id_names(tables):
    out = {}
    for f in ('spells_characters', 'spells_buildings', 'spells_other', 'spells_evolved', 'spells_hero_form'):
        j = json.load(open(Path(tables) / f'{f}.json'))
        for name, row in j['rows'].items():
            out[j['id'] * 1000000 + row['index']] = re.sub(r'_(EV1|hero)$', '', name)
    return out


def own_order(path):
    """Deal order from the decision events, or None when fewer than 4 queue cards were seen."""
    order = []
    for raw in open(path, 'rb'):
        if b'"decision"' not in raw[:40]:
            continue
        hand = [h['deck_index'] for h in (json.loads(raw).get('public') or {}).get('own_hand', [])]
        if not order:
            if len(hand) == 4:
                order = hand[:]
            continue
        for d in hand:
            if d not in order:
                order.append(d)
        if len(order) == 8:
            return order
    return None


def opp_plays(path, my_side, deck_ids, spells):
    """Opponent deck indices in first-seen order (bodies, projectiles, effects whose card id is a deck card)."""
    # Troops / buildings: a NEW body (address unseen, gone > 40 ticks, or another card) of a deck card; bodies of one card
    # born within GROUP ticks are one play (Skeleton Army, Wall Breakers). Spells (28xxxxxx ids and their forms): a new
    # projectile / effect. A troop's own shots carry the troop's id, so projectiles count only for spell cards.
    addr, last, plays = {}, {}, []
    for raw in open(path, 'rb'):
        if b'"frame"' not in raw[:40]:
            continue
        j = json.loads(raw)
        t = j['tick']
        for e in j['ents']:
            if e[0] == my_side or e[3] not in deck_ids:
                continue
            a0 = addr.get(e[7])
            if a0 is None or t - a0[0] > GROUP or a0[1] != deck_ids[e[3]]:       # a body born: last = its card's last birth
                k = deck_ids[e[3]]
                if k not in last or t - last[k] > GROUP:
                    plays.append((t, k))
                last[k] = t
            addr[e[7]] = (t, deck_ids[e[3]])
        for q in (j.get('proj') or []) + (j.get('fx') or []):     # a spell seen: last = its last sighting
            k = deck_ids.get(q[3])
            if q[0] != my_side and k in spells:
                if k not in last or t - last[k] > GROUP:
                    plays.append((t, k))
                last[k] = t
    return [k for _, k in sorted(plays)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tables', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    names = id_names(a.tables)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    logs = {}
    for p in LIVE.glob('live_play_202610*.jsonl'):
        m = re.match(r'live_play_(\d{8}_\d{6})', p.name)
        logs[p] = dt.datetime.strptime(m.group(1), '%Y%m%d_%H%M%S') + dt.timedelta(hours=4)   # EDT -> UTC
    seen, man, census = set(), [], []
    for line in open(BATTLELOG):
        b = json.loads(line)['battle']
        if b['type'] != 'pathOfLegend' or (b['battleTime'], b['opponent'][0]['tag']) in seen:
            continue
        seen.add((b['battleTime'], b['opponent'][0]['tag']))
        end = dt.datetime.strptime(b['battleTime'][:15], '%Y%m%dT%H%M%S')
        decks = [b['team'][0]['cards'], b['opponent'][0]['cards']]
        row = dict(battle=b['battleTime'], opp=b['opponent'][0]['tag'])
        if any(len(d) != 8 for d in decks):
            man.append(dict(row, skip='deck_size')); continue
        cn = [[names.get(c['id'], '?' + c['name']) for c in d] for d in decks]
        sl = [[{1: 1, 2: 2}.get(c.get('evolutionLevel') or 0, 0) for c in d] for d in decks]
        census.append('\t'.join([b['battleTime'], ','.join(cn[0]), ','.join(map(str, sl[0])), ','.join(cn[1]),
                                 ','.join(map(str, sl[1]))]))
        cand = [(end - t0).total_seconds() for t0 in logs.values()]
        best = min(((s, p) for p, s in zip(logs, cand) if 60 <= s <= 600), default=None)
        if best is None:
            man.append(dict(row, skip='no_live_log')); continue
        path = best[1]
        my_side = None
        for raw in open(path, 'rb'):
            if b'"frame"' in raw[:40]:
                my_side = json.loads(raw)['my_side']; break
        if my_side is None:
            man.append(dict(row, live=path.name, skip='no_frames')); continue
        order = own_order(path)
        if order is None:
            man.append(dict(row, live=path.name, skip='own_order_incomplete')); continue
        opp_ids = {}
        for k, c in enumerate(decks[1]):
            opp_ids[c['id']] = k
            for cid, n in names.items():          # evo / hero rows of the same card
                if n == cn[1][k] and cid // 1000000 in (13, 203):
                    opp_ids[cid] = k
        plays = opp_plays(path, my_side, opp_ids, {k for k, c in enumerate(decks[1]) if c["id"] // 1000000 == 28})
        w = [word(b['team'][0]['tag']), word(b['opponent'][0]['tag'])]
        side = {my_side: 0, 1 - my_side: 1}          # battle side -> index into decks / words (0 = us)
        lines = []
        for s in (0, 1):
            k = side[s]
            lines += [f'deck{s}=' + ','.join(cn[k]), f'word{s}={w[k]}']
            lines.append(f'order{s}=' + ','.join(map(str, order)) if k == 0 else f'plays{s}=' + ','.join(map(str, plays)))
        stem = path.stem
        (out / f'{stem}.txt').write_text('\n'.join(lines) + '\n')
        man.append(dict(row, live=path.name, my_side=my_side, order=order, opp_plays=len(plays), job=f'{stem}.txt',
                        gap_s=best[0]))
    (out / 'manifest.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in man))
    (out / 'census_decks.tsv').write_text('\n'.join(census) + '\n')
    n = sum('job' in r for r in man)
    print(f'ranked entries {len(man)}, jobs {n}, skips', {k: sum(r.get("skip") == k for r in man) for k in
                                                          {r.get("skip") for r in man if r.get("skip")}})


if __name__ == '__main__':
    main()
