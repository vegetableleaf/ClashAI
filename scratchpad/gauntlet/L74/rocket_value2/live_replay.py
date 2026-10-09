"""Live replay of the rocket_value variants on the logged live decisions (no model, no game: the rule only reads the public board).

  nice python live_replay.py [--logs DIR] [--since 20261005] [--detail FILE T0 T1] [--variants name,name] > live_replay.out

Per live_play log: every `decision` event with a public audit gives the board the pilot decided on (public.model_bodies = the
identity-resolved bodies with hp_frac, already advanced by the live extrapolation; public.model_own_elixir; public.own_hand with
costs; decision.play = whether the model itself played there). The rule's own function (decision_options.rocket_value_choice) is
evaluated on it with a per-match history holder, exactly as GenPilot.rocket_value does. A Rocket in hand and affordable (integer
elixir >= cost) is the trigger the log supports; an EPISODE = a run of firing decisions with no gap of >= 10 s (the rule would
have cast at the first one). Reported per variant: episodes in total and per match, and the model's own behaviour there (a Rocket
play within 2 s of the episode start, and the cards it did play instead).

--detail FILE T0 T1 prints, for the raw tick window, each variant's best blast value, whether it fires, and the bodies."""
import argparse, glob, json, os, sys
from collections import Counter
from types import SimpleNamespace

sys.path.insert(0, os.getcwd())
try:
    import ctypes; ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception:
    pass
import numpy as np
from pipeline import decision_options as D
from pipeline import vocab
from pipeline.obs_contract import Tower, Unit

ap = argparse.ArgumentParser()
ap.add_argument('--logs', default='C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader')
ap.add_argument('--since', default='20261005')
ap.add_argument('--detail', nargs=3, metavar=('FILE', 'T0', 'T1'))
ap.add_argument('--variants', default='')
ap.add_argument('--variants-json', default=None, help='name -> DecisionOptions kwargs (mk_variants.py) instead of the built-in list')
args = ap.parse_args()

R = dict(rocket_value=9.0)
VARIANTS = {
    'it1_cost_centre_V9': dict(R),
    'it1_cost_centre_V11': dict(rocket_value=11.0),
    'dmg_centre_V9': dict(R, rocket_value_mode='damage'),
    'dmg_edge_V9': dict(R, rocket_value_mode='damage', rocket_value_hitbox='edge'),
    'dmg_edge_V11': dict(rocket_value=11.0, rocket_value_mode='damage', rocket_value_hitbox='edge'),
    'dmg_edge_lead_V9': dict(R, rocket_value_mode='damage', rocket_value_hitbox='edge', rocket_value_lead='on'),
    'dmg_edge_V9_el9': dict(R, rocket_value_mode='damage', rocket_value_hitbox='edge', rocket_value_min_elixir=9.0),
    'dmg_edge_V9_idle': dict(R, rocket_value_mode='damage', rocket_value_hitbox='edge', rocket_value_idle='on'),
    'dmg_edge_V9_y21': dict(R, rocket_value_mode='damage', rocket_value_hitbox='edge', rocket_value_min_y=21.0),
    'kill_edge_V7': dict(rocket_value=7.0, rocket_value_mode='kill', rocket_value_hitbox='edge'),
}
if args.variants_json:
    VARIANTS = json.load(open(args.variants_json))
if args.variants:
    VARIANTS = {k: v for k, v in VARIANTS.items() if k in args.variants.split(',')}
OPTS = {k: D.DecisionOptions(**v) for k, v in VARIANTS.items()}
KEYS = {(o.rocket_value_mode, o.rocket_value_hitbox, o.rocket_value_min_y) for o in OPTS.values()}
GAP, WITHIN = 200, 40            # ticks: 10 s ends an episode; 2 s = "the model Rocketed right then"


def load(path):
    dec, plays = [], []
    for line in open(path, encoding='utf-8', errors='replace'):
        if line.startswith('{"event": "decision"'):
            d = json.loads(line)
            if d.get('public') and d['public'].get('model_bodies') is not None:
                dec.append(d)
        elif line.startswith('{"event": "play"'):
            plays.append(json.loads(line))
    return dec, plays


def board(p):
    units = tuple(Unit(**{k: b[k] for k in Unit.__dataclass_fields__ if k in b}) for b in p['model_bodies'])
    towers = tuple(Tower(**{k: t[k] for k in Tower.__dataclass_fields__ if k in t}) for t in p.get('model_towers') or [])
    return SimpleNamespace(units=units, t_sec=float(p['model_tick']) * 0.05, my_elixir=float(p['model_own_elixir']), towers=towers)


def run(path, detail=None):
    dec, plays = load(path)
    if len(dec) < 150:
        return None
    holders = {k: SimpleNamespace() for k in OPTS}
    eps = {k: [] for k in OPTS}
    last = {k: None for k in OPTS}
    n_rocket_hand = 0
    for d in dec:
        p = d['public']
        hand = [h['name'] for h in p['own_hand']]
        cost = {h['name']: h['cost'] for h in p['own_hand']}
        el = p['model_own_elixir']
        allowed = [int(el) >= cost[n] for n in hand]
        bs = board(p)
        in_hand = 'Rocket' in hand
        n_rocket_hand += in_hand
        vals = {}
        if in_hand and allowed[hand.index('Rocket')]:        # one best_rocket_clump per (mode, hitbox, min_y): a variant is only called when it can fire
            for key in KEYS:
                vals[key] = D.best_rocket_clump(D.rocket_bodies(bs, key[0]), 'lattice', key[1], None, key[2])[0]
        for k, o in OPTS.items():
            if o.rocket_value_lead in ('on', 'blend') or o.rocket_value_threat == 'on' or (vals.get((o.rocket_value_mode, o.rocket_value_hitbox, o.rocket_value_min_y), 0.0)
                                                                + 1e-9 >= o.rocket_value) or detail:
                hit = D.rocket_value_choice(o, hand, allowed, bs, 'lattice', holder=holders[k], playing=bool(d['decision'].get('play')))
            else:
                hit = None
            tick = p['raw_tick']
            if hit is not None:
                if last[k] is None or tick - last[k] > GAP:
                    eps[k].append(dict(tick=tick, value=hit[2], el=el, model_play=d['decision'].get('name') if d['decision'].get('play') else None))
                last[k] = tick
            if detail and detail[0] <= tick <= detail[1]:
                bodies = D.rocket_bodies(bs, o.rocket_value_mode)
                v, _ = D.best_rocket_clump(bodies, 'lattice', o.rocket_value_hitbox, None, o.rocket_value_min_y)
                print(f'  {k:22s} tick {tick} el {el:.1f} rocket_in_hand {in_hand} afford {in_hand and allowed[hand.index("Rocket")]} '
                      f'best static blast {v:5.2f} FIRES {hit is not None}' + (f' value {hit[2]:.2f}' if hit else ''))
                if o.rocket_value_hitbox == 'edge' and o.rocket_value_mode == 'damage' and k == next(iter(OPTS)) or k == 'dmg_edge_V9':
                    _, elig = D.best_rocket_clump(bodies, 'lattice', 'edge', None, o.rocket_value_min_y)
                    if elig is not None:
                        xs, ys = D.cell_centres_tiles('lattice')
                        c = int(np.flatnonzero(elig)[len(np.flatnonzero(elig)) // 2])
                        inside = [(vocab.UNIT_VOCAB[int(b[0])], round(b[1], 1), round(b[2], 1), round(b[3], 2)) for b in bodies
                                  if np.hypot(xs[c] - b[1], ys[c] - b[2]) <= 2.0 + b[4]]
                        print(f'      blast near ({xs[c]:.1f},{ys[c]:.1f}) holds (name, x, y, value): {inside}')
    rp = [q for q in plays if q.get('name') == 'Rocket']
    for k in OPTS:
        for e in eps[k]:
            e['model_rocket_2s'] = any(e['tick'] <= q['tick'] <= e['tick'] + WITHIN for q in rp)
    return dict(path=path, n=len(dec), rocket_decisions=n_rocket_hand, eps=eps, model_rockets=len(rp))


if args.detail:
    f = args.detail[0] if os.path.exists(args.detail[0]) else os.path.join(args.logs, args.detail[0])
    print(f)
    run(f, (int(args.detail[1]), int(args.detail[2])))
    sys.exit()

res = []
for path in sorted(glob.glob(os.path.join(args.logs, 'live_play_*.jsonl'))):
    if os.path.basename(path)[10:] < args.since:
        continue
    r = run(path)
    if r and r['rocket_decisions']:
        res.append(r)
print(f'{len(res)} live matches with the Rocket in hand at some decision (>= 150 decisions each), logs since {args.since}; '
      f'{sum(r["n"] for r in res)} decisions; the model played {sum(r["model_rockets"] for r in res)} Rockets '
      f'({sum(r["model_rockets"] for r in res) / max(len(res), 1):.2f}/match)')
for k in OPTS:
    e = [x for r in res for x in r['eps'][k]]
    m = sum(1 for r in res if r['eps'][k])
    cards = Counter(x['model_play'] for x in e)
    print(f'{k:22s} episodes {len(e):4d} = {len(e) / max(len(res), 1):.3f}/match in {m} matches | model Rocketed within 2 s: '
          f'{sum(x["model_rocket_2s"] for x in e)} ({sum(x["model_rocket_2s"] for x in e) / max(len(e), 1):.0%}) | mean value '
          f'{np.mean([x["value"] for x in e]) if e else 0:.1f}, mean elixir {np.mean([x["el"] for x in e]) if e else 0:.1f} | '
          f'model played at the first firing decision: {sum(v for c, v in cards.items() if c)} ({dict(cards.most_common(4))})')
