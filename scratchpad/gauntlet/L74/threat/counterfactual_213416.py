"""What would --gate-hazard-threatened have done on live match 213416? Replays the LOGGED per-decision gate p, tau,
own elixir, model towers and model bodies through the shipped helpers (decision_options.tower_threat / gate_rate) and
reports exact P(no play yet) per arm (the hazard draw is the only randomness). Step = logged tick gap (live accrues the
same game time over its finer frames; p held over the gap). Run from the repo root:
    python scratchpad/gauntlet/L74/threat/counterfactual_213416.py <live_play.jsonl>"""
import json, math, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from pipeline.decision_options import DecisionOptions, gate_rate, tower_threat  # noqa: E402
from pipeline.obs_contract import Tower, Unit  # noqa: E402


class B:  # the three BoardState fields tower_threat reads
    def __init__(self, t, towers, units):
        self.t_sec, self.towers, self.units = t, towers, units


decs = []
for line in open(sys.argv[1]):
    d = json.loads(line)
    if d.get('event') != 'decision':
        continue
    pub, dec = d['public'], d['decision']
    bs = B(pub['model_tick'] * 0.05, tuple(Tower(**t) for t in pub['model_towers']),
           tuple(Unit(**u) for u in pub['model_bodies']))
    decs.append((int(d['tick']), bs, dec, float(pub['model_own_elixir'] or 0)))

ARMS = {'deployed (elixir>=9)': DecisionOptions(gate_decode='hazard_below_tau', gate_hazard_min_elixir=9),
        '+threatened T=2s': DecisionOptions(gate_decode='hazard_below_tau', gate_hazard_min_elixir=9,
                                            gate_hazard_threatened=2.0),
        '+threat radius 4 tiles': DecisionOptions(gate_decode='hazard_below_tau', gate_hazard_min_elixir=9,
                                                  gate_hazard_threat_radius=4.0)}
T0 = int(sys.argv[2]) if len(sys.argv) > 2 else 2268        # first logged decision with my KING tower losing HP
T1 = int(sys.argv[3]) if len(sys.argv) > 3 else 2480        # last: all my towers down (3-crown loss)
print(f'match {Path(sys.argv[1]).name}: window ticks {T0}..{T1}; logged p in window '
      f'{min(x[2]["p_play"] for x in decs if T0 <= x[0] <= T1):.2f}..'
      f'{max(x[2]["p_play"] for x in decs if T0 <= x[0] <= T1):.2f}; no play was made by the bot in the window')
for arm, opt in ARMS.items():
    state, prev, surv, rows, cards = None, None, 1.0, [], {}
    for tick, bs, dec, el in decs:
        state, thr = tower_threat(opt, state, bs)
        step = 0.0 if prev is None else min((tick - prev) * 0.05, 2.0)
        prev = tick
        if not (T0 <= tick <= T1) or dec.get('no_affordable') or dec['play']:
            continue
        scope = el >= opt.gate_hazard_min_elixir or thr
        q = -math.expm1(-float(gate_rate(dec['p_play'])) * step) if scope else 0.0
        cards[dec['name']] = cards.get(dec['name'], 0.0) + surv * q
        surv *= 1 - q
        rows.append((tick, thr, round(dec['p_play'], 3), round(float(gate_rate(dec['p_play'])), 3), round(1 - surv, 3)))
    played = 1 - surv
    print(f'\n== {arm}: P(play before all towers fell) = {played:.2f}; card if played '
          f'{ {k: round(v / max(played, 1e-9), 2) for k, v in cards.items() if v > 1e-6} }')
    for s in (2, 4, 6, 8, 10):
        tt = [r for r in rows if r[0] <= T0 + 20 * s]
        print(f'   P(played within {s:>2} s of tick {T0}) = {tt[-1][4] if tt else 0:.2f}')
    print('   tick threatened p rate/s P(played by now):', rows[::4])
