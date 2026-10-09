"""Owner 2026-10-09 01:4x: "WHY IS THE MODEL NOT ROCKETING A FULL FUCKING LAVAHOUND PUSH WITH 15+ ELIXIR OF VALUE?"
Per decision in a window: my elixir, hand, the model's play/card choice, and the best Rocket blast on my half
(radius 2.0 tiles, centred on an enemy body) with the enemy elixir inside it. Raw reader bodies, public only."""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from pipeline.obs_contract import _catalog_names   # noqa: E402

N = _catalog_names()
COST = {'LavaHound': 7, 'LavaPups': 7 / 6, 'Balloon': 5, 'MegaMinion': 3, 'SkeletonDragons': 2, 'Minions': 1,
        'MinionHorde': 5 / 6, 'Bats': 0.4, 'InfernoDragon': 4, 'BabyDragon': 4, 'ElectroDragon': 5, 'Phoenix': 4}
R = 2.0
f, t0, t1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
for l in open(f, encoding='utf-8', errors='replace'):
    if l.startswith('{"event": "play"'):
        d = json.loads(l)
        if t0 <= d['tick'] <= t1:
            print(f"   >>> PLAY {d['name']} tick {d['tick']} elixir {d.get('elixir')}")
    if not l.startswith('{"event": "decision"'):
        continue
    d = json.loads(l); p = d['public']
    if not t0 <= p['raw_tick'] <= t1:
        continue
    me = p['observer_side']
    en = []
    for b in p['raw_bodies']:
        if b['side'] == me or b['card_id'] == -1 or b['hp'] <= 0:
            continue
        x, y = b['x'] / 1000, b['y'] / 1000
        if me == 1:
            x, y = 18 - x, 32 - y                      # my frame: my king at y 3
        name = N.get(b['card_id'], str(b['card_id']))
        en.append((name, x, y, COST.get(name, 1.0) * b['hp'] / max(b['max_hp'], 1)))
    best = (0.0, None, [])
    for _, cx, cy, _ in en:
        inside = [e for e in en if (e[1] - cx) ** 2 + (e[2] - cy) ** 2 <= R * R]
        v = sum(e[3] for e in inside)
        if v > best[0]:
            best = (v, (round(cx, 1), round(cy, 1)), sorted({e[0] for e in inside}))
    hand = [h['name'] for h in p['own_hand']]
    dec = d['decision']
    print(f"tick {p['raw_tick']} el {p['own_elixir_raw']} hand {hand} | play {dec.get('play')} p {dec.get('p_play', 0):.2f} "
          f"card {dec.get('name')} | best rocket blast {best[0]:.1f} elixir (hp-weighted) at {best[1]} {best[2]} | "
          f"enemies on my half: {sum(1 for e in en if e[2] < 16)}")
