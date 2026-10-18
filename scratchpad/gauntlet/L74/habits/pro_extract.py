"""Pro X-Bow sides for L74/habits -> pro_sides.jsonl, one line per X-Bow player-side:
  {src, tag, mode, win, crowns, opp_crowns, dur, deck (base keys), icebow8 (bool), ev: [[tick, who 'me'|'op', card base key,
   ability 0/1, X, Y]]}  positions in the X-Bow player's OWN frame (tiles, own king y 29, enemy king y 3).
Sources:
  crawl2  icebow/data/royaleapi/crawl2 (battles.csv + plays_ext_i1.csv): blue = the crawled icebow player; rows with attr_i 1
          are rotated (18000 - x, 32000 - y) (L64 _handoff_5cs67/68), after which blue sits at HIGH y (its X-Bows at 19.5).
  hf      scratchpad/gauntlet/L67/hf/replays/part-*.parquet: native_world_units, team at LOW y, opponent HIGH (pro_xbow_lanes.py);
          a team X-Bow player is rotated (18 - x, 32 - y), an opponent one kept.
    icebow/.venv/Scripts/python.exe -I pro_extract.py   (run at idle priority)"""
import csv
import glob
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ICEBOW8 = {"tornado", "tesla", "ice-wizard", "x-bow", "rocket", "knight", "the-log", "skeletons"}


def base(k):
    for s in ("-ev1", "-ev2", "-hero"):
        if k.endswith(s):
            return k[: -len(s)]
    return k


def crawl2(out):
    D = REPO / 'icebow/data/royaleapi/crawl2'
    bat = {r['replay_tag']: r for r in csv.DictReader(open(D / 'battles.csv', encoding='utf-8'))}
    ev = defaultdict(list)
    for r in csv.DictReader(open(D / 'plays_ext_i1.csv', encoding='utf-8')):
        if r['x_units'] in ('', 'None') or r['y_units'] in ('', 'None'):
            continue
        x, y = int(r['x_units']), int(r['y_units'])
        if r['attr_i'] == '1':
            x, y = 18000 - x, 32000 - y
        ev[r['replay_tag']].append([int(r['tick']), 'me' if r['attr_s'] == 'blue' else 'op', base(r['attr_card']),
                                    int(r['attr_ability'] or 0), x / 1000, y / 1000])
    n = 0
    for tag, es in ev.items():
        b = bat.get(tag)
        if b is None:
            continue
        deck = sorted(base(k) for k in b['team_deck'].split(','))
        win = 1.0 if b['result'] == 'win' else 0.0 if b['result'] == 'loss' else 0.5
        out.write(json.dumps(dict(src='crawl2', tag=tag, mode=b['battle_type'], win=win, crowns=int(b['team_crowns']),
                                  opp_crowns=int(b['opponent_crowns']), dur=None, deck=deck, opp_deck=sorted(
                                      base(k) for k in b['opponent_deck'].split(',')),
                                  icebow8=set(deck) == ICEBOW8, rating=b.get('rating'), ev=sorted(es))) + '\n')
        n += 1
    return n


def hf(out):
    import polars as pl
    n = 0
    for f in sorted(glob.glob(str(REPO / 'scratchpad/gauntlet/L67/hf/replays/part-*.parquet'))):
        df = pl.read_parquet(f, columns=['replay_tag', 'battle_type', 'game_mode', 'payload_json'])
        df = df.filter(pl.col('payload_json').str.contains('"x-bow', literal=True))
        for tag, bt, gm, pj in df.iter_rows():
            p = json.loads(pj)
            b = p['battle']
            if len(b['team']['players']) != 1 or len(b['opponent']['players']) != 1:
                continue
            dur = p.get('replay', {}).get('duration', {}).get('timeline_seconds')
            for side, oth in (('team', 'opponent'), ('opponent', 'team')):
                keys = [c['card_key'] for c in b[side]['players'][0]['deck']]
                if not any(base(k) == 'x-bow' for k in keys):
                    continue
                res = b['result']
                win = 0.5 if res == 'draw' else 1.0 if (res == 'victory') == (side == 'team') else 0.0
                es = []
                for e in p['events']:
                    if e.get('kind') not in ('play_card', 'activate_ability'):
                        continue
                    nw = (e.get('coordinates') or {}).get('native_world_units')
                    x, y = (nw['x'] / 1000, nw['y'] / 1000) if nw else (None, None)
                    if nw and side == 'team':
                        x, y = 18 - x, 32 - y
                    es.append([e['replay_tick_20hz'], 'me' if e.get('side') == side else 'op', base(e.get('card_key') or '?'),
                               int(e['kind'] == 'activate_ability'), None if x is None else round(x, 3),
                               None if y is None else round(y, 3)])
                deck = sorted(base(k) for k in keys)
                out.write(json.dumps(dict(src='hf', tag=tag, mode=f'{bt}/{gm}', win=win, crowns=b[side]['crowns'],
                                          opp_crowns=b[oth]['crowns'], dur=dur, deck=deck,
                                          opp_deck=sorted(base(c['card_key']) for c in b[oth]['players'][0]['deck']),
                                          icebow8=set(deck) == ICEBOW8, ev=sorted(es))) + '\n')
                n += 1
        print('hf', Path(f).name, n, flush=True)
    return n


if __name__ == '__main__':
    with open(HERE / 'pro_sides.jsonl', 'w', encoding='utf-8') as out:
        print('crawl2', crawl2(out), flush=True)
        print('hf', hf(out), flush=True)
