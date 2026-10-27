"""Reader detail rows per frame for the body-position work (A2c-BP). Laptop side; board rows only (never the
opponent's hand or elixir). python -I rdet.py LIVE_DIR LIST OUTDIR
One OUTDIR/<match>.jsonl per match, one line per frame tick (first sample kept):
  {"t": tick, "G": [[side, x, y, card, hp, gen, target_gen, state, [seq_idx, progress, load, pre, activation], buffs]...]}"""
import json, os, sys


def convert(path):
    out = {}
    for line in open(path, 'rb'):
        if b'"frame"' not in line[:40]:
            continue
        d = json.loads(line)
        t = d['tick']
        if t is None or t < 0 or t in out:
            continue
        p2 = {u['address']: u for u in (d.get('phase2') or {}).get('units', [])}
        att = {b['generation']: b.get('attack') for b in (d.get('phase3') or {}).get('bodies', [])}
        st = d.get('ents_state') or []
        rows = []
        for i, e in enumerate(d['ents']):
            u = p2.get(e[7]) or {}
            s = st[i] if i < len(st) else None
            g = u.get('generation') if u else None
            if g is None and s:
                g = s[3]
            a = att.get(g) or {}
            rows.append([e[0], e[1], e[2], e[3], e[4], g, a.get('target_gen'), s[2] if s else None,
                         [a.get('seq_idx'), a.get('progress_raw'), a.get('load_raw'), a.get('pre_raw'), a.get('activation_raw')] if a else None,
                         [b.get('name') if isinstance(b, dict) else b for b in (u.get('buffs') or [])]])
        out[t] = {'t': t, 'G': rows}
    return [out[t] for t in sorted(out)]


live, lst, outd = sys.argv[1:4]
os.makedirs(outd, exist_ok=True)
for m in [l.split()[0] for l in open(lst) if l.strip()]:
    fr = convert(os.path.join(live, m + '.jsonl'))
    with open(os.path.join(outd, m + '.jsonl'), 'w') as w:
        for f in fr:
            w.write(json.dumps(f, separators=(',', ':')) + '\n')
