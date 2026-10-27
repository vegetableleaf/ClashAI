"""Reader target rows for the body-position dossier (ticket A2c round 4). Laptop side.
    python -I tgt_frames.py --live-dir scratchpad/gauntlet/L68/live_reader --list bp41.txt --out DIR
One DIR/<match>.jsonl per match, one line per frame tick (first sample kept):
  {"t": tick, "G": [[side, x, y, card, gen, target_gen, state]...]}  (state = ents_state[i][2]; target from phase3 attack)
Reads only the board rows (ents / ents_state / phase2 unit addresses / phase3 attack targets); never the opponent's
hand or elixir."""
import argparse, json, os


def convert(path):
    out = {}
    for line in open(path, 'rb'):
        if b'"frame"' not in line[:40]:
            continue
        d = json.loads(line)
        t = d['tick']
        if t is None or t < 0 or t in out:
            continue
        gen_of = {u['address']: u['generation'] for u in (d.get('phase2') or {}).get('units', [])}
        tgt = {b['generation']: (b.get('attack') or {}).get('target_gen') for b in (d.get('phase3') or {}).get('bodies', [])}
        st = d.get('ents_state') or []
        rows = []
        for i, e in enumerate(d['ents']):
            g = gen_of.get(e[7])
            s = st[i] if i < len(st) else None
            if g is None and s:
                g = s[3]
            rows.append([e[0], e[1], e[2], e[3], g, tgt.get(g), s[2] if s else None])
        out[t] = {'t': t, 'G': rows}
    return [out[t] for t in sorted(out)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--live-dir', required=True); ap.add_argument('--list', required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for m in [l.split()[0] for l in open(a.list) if l.strip()]:
        fr = convert(os.path.join(a.live_dir, m + '.jsonl'))
        with open(os.path.join(a.out, m + '.jsonl'), 'w') as w:
            for f in fr:
                w.write(json.dumps(f, separators=(',', ':')) + '\n')
        print(m, len(fr))


if __name__ == '__main__':
    main()
