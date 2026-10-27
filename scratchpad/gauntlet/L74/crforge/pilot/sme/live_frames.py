"""Live log -> compact reader frames for the SME scorer (ticket A2b-3b). Laptop side.

    python -I live_frames.py --inputs inputs_rngfree.jsonl --live-dir scratchpad/gauntlet/L68/live_reader --out DIR

One DIR/<match>.jsonl per match, one line per frame tick (first sample kept):
  {"t": tick, "E": [[side,x,y,card_id,hp,kind]...], "P": [[side,x,y,card_id]...], "A": [[side,x,y,card_id]...],
   "el": our elixir_raw (live 'elixir' x 1e4), "hand": our 4 hand deck indices from a decision at this tick, or null}
Live frame formats (read on live_play_20261026_130453): ents [side,x,y,card,hp,max_hp,kind,addr], proj [side,x,y,card,tx,ty,
addr,gen,source,target], fx [side,x,y,card,remaining_ms,level,addr,gen]; decision.public.own_hand[i].deck_index.
"""
import argparse, json, os


def convert(path):
    frames, hands = {}, {}
    for line in open(path, 'rb'):
        head = line[:40]
        if b'"frame"' in head:
            d = json.loads(line)
            t = d['tick']
            if t is None or t < 0 or t in frames:
                continue
            frames[t] = {'t': t, 'E': [[e[0], e[1], e[2], e[3], e[4], e[6]] for e in d['ents']],
                         'P': [[p[0], p[1], p[2], p[3]] for p in d['proj']],
                         'A': [[a[0], a[1], a[2], a[3]] for a in d['fx']],
                         'el': int(round(d['elixir'] * 10000)), 'hand': None}
        elif b'"decision"' in head:
            d = json.loads(line)
            pub = d.get('public') or {}
            h = [x['deck_index'] for x in pub.get('own_hand') or []]
            if len(h) == 4 and pub.get('raw_tick') is not None:
                hands.setdefault(pub['raw_tick'], h)
    for t, h in hands.items():
        if t in frames:
            frames[t]['hand'] = h
    return [frames[t] for t in sorted(frames)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--inputs', required=True); ap.add_argument('--live-dir', required=True)
    ap.add_argument('--out', required=True); ap.add_argument('--also', nargs='*', default=[])
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    names = [json.loads(l)['match'] for l in open(a.inputs)] + a.also
    for m in names:
        fr = convert(os.path.join(a.live_dir, m + '.jsonl'))
        with open(os.path.join(a.out, m + '.jsonl'), 'w') as w:
            for f in fr:
                w.write(json.dumps(f, separators=(',', ':')) + '\n')
        print(m, len(fr), sum(f['hand'] is not None for f in fr))


if __name__ == '__main__':
    main()
