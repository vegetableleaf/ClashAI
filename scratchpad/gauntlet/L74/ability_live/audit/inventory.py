"""Pass A over the 10-16/17 live logs: per match, the ckpt, my side, every non-frame event the press audit needs, and
the own-side 203000023 objects per frame tick (regex on the raw frame line, no json parse of frames).
Out: audit/inventory.json. Read-only; single thread."""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
LIVE = ROOT / 'scratchpad/gauntlet/L68/live_reader'
P3 = ROOT / 'icebow/data/p3_captures'
OUT = Path(__file__).with_name('inventory.json')
MARKS = {'rlarm_gae_cue_u250_u0130_grafted.pt': 'CXXXVIII', 'rlarm_gae_u0250_grafted.pt': 'CXXIV'}
KEEP = tuple('{' + k for k in ('"event": "ability', '"event": "button"', '"event": "play"', '"event": "confirmed"', '"event": "stop"',
        '"event": "end"', '"event": "unconfirmed"'))
EV = re.compile(rb'^\{"event": "([a-z_]+)"')
TICK = re.compile(rb'"tick": (\d+)')
SIDE = re.compile(rb'"my_side": (\d)')
ELX = re.compile(rb'"elixir": ([0-9.]+)')
HERO = re.compile(rb'\[(\d), (-?\d+), (-?\d+), 203000023, (-?\d+)')


def scan(p):
    m = {'log': p.name, 'events': [], 'hero': {}, 'elixir': {}, 'frames': 0, 'side': None}
    with open(p, 'rb') as f:
        for raw in f:
            g = EV.match(raw)
            if not g:
                continue
            ev = g.group(1)
            if ev == b'frame':
                m['frames'] += 1
                t = int(TICK.search(raw).group(1))
                if m['side'] is None:
                    s = SIDE.search(raw)
                    m['side'] = int(s.group(1)) if s else None
                e = ELX.search(raw)
                if e and t % 10 == 0:
                    m['elixir'][t] = float(e.group(1))
                h = [[int(a), int(b), int(c), int(d)] for a, b, c, d in HERO.findall(raw)]
                if h:
                    m['hero'][t] = h
                continue
            if ev == b'start':
                j = json.loads(raw)
                m['ckpt'] = Path(j.get('ckpt') or '').name
                m['mark'] = MARKS.get(m['ckpt'], 'other')
                m['pstar'] = (j.get('live_options') or {}).get('from_file', {}).get('iw_press_pstar')
                m['iw_press'] = j.get('iw_press') or (j.get('live_options') or {}).get('from_file', {}).get('iw_press')
                continue
            s = raw.decode('utf-8', 'replace')
            if s.startswith(KEEP):
                j = json.loads(s)
                if j['event'] in ('play', 'confirmed') and j.get('name') != 'IceWizard':
                    continue
                j.pop('t_dev', None)
                m['events'].append(j)
    m['p3'] = (P3 / p.stem / 'run.json').exists()
    return m


def main():
    logs = sorted(LIVE.glob('live_play_2026101[67]_*.jsonl'))
    out = []
    for i, p in enumerate(logs):
        out.append(scan(p))
        if i % 50 == 0:
            print(i, p.name, file=sys.stderr, flush=True)
    OUT.write_text(json.dumps(out))
    from collections import Counter
    c = Counter((m.get('mark'), m['frames'] > 500, m['p3']) for m in out)
    for k, v in sorted(c.items(), key=str):
        print(k, v)


if __name__ == '__main__':
    main()
