"""Owner 2026-10-09 01:3x: "why is the model playing a knight in response to a singular balloon?" -- every Knight play in
the given live logs: what the model saw (model_bodies decoded through pipeline.vocab.UNIT_VOCAB), the decision fields,
hand, elixir; flags plays where an enemy air unit was on my half."""
import glob, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from pipeline import vocab   # noqa: E402

NAME = {i: n for i, n in enumerate(vocab.UNIT_VOCAB)} if isinstance(vocab.UNIT_VOCAB, (list, tuple)) else \
    {i: n for n, i in vocab.UNIT_VOCAB.items()}
files = sorted(glob.glob(sys.argv[1] if len(sys.argv) > 1 else
                         'scratchpad/gauntlet/L68/live_reader/live_play_20261009_*.jsonl'))
for f in files:
    last = None
    for line in open(f, encoding='utf-8', errors='replace'):
        if line.startswith('{"event": "decision"'):
            last = json.loads(line)
        elif line.startswith('{"event": "play"') and last is not None:
            d = json.loads(line)
            if d.get('name') != 'Knight':
                continue
            p = last['public']
            enemy = [(NAME.get(int(b['cls']), b['cls']), round(b['x'] * 18, 1), round(b['y'] * 32, 1), b.get('form'))
                     for b in p['model_bodies'] if b.get('side') == 1]
            dec = {k: last['decision'].get(k) for k in ('p_play', 'why', 'hazard_play', 'xy') if k in last['decision']}
            print(f.split('live_play_')[-1][:15], 'tick', d.get('tick'), 'knight at (tiles, my frame y up)',
                  [round(d['xy'][0] * 18, 1), round((1 - d['xy'][1]) * 32, 1)], '| elixir', d.get('elixir'),
                  '| hand', [h.get('name') for h in p['own_hand']], '\n   decision', dec,
                  '\n   enemy bodies the model saw (name, x, y model frame, form):', enemy)
