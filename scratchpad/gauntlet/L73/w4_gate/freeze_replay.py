"""W4: replay a live match's logged decision stream (p_play per decision) through hazard_below_tau, Monte Carlo.
  python freeze_replay.py <live_play_*.jsonl> [t0 t1 [min_elixir [quiet]]]"""
import json, sys, os
import numpy as np
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))
from pipeline.decision_options import gate_rate

f = sys.argv[1]; t0, t1 = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (0, 10 ** 9)
MIN_EL = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0; QUIET = len(sys.argv) > 5 and sys.argv[5] == "quiet"
D = []
for l in open(f):
    d = json.loads(l)
    if d.get("event") != "decision": continue
    dc, p = d["decision"], d.get("public") or {}
    me = p.get("observer_side")
    n_en = sum(b["side"] != me and b["card_id"] != -1 for b in p.get("raw_bodies", []))   # towers carry card_id -1
    D.append((d["tick"], dc.get("p_play"), dc.get("gate_tau"), dc.get("name"), dc.get("play"), dc.get("no_affordable"), p.get("own_elixir_raw"), n_en))
W = [x for x in D if t0 <= x[0] <= t1]
gaps = np.diff([x[0] for x in W])
print(f"{len(W)} decisions in [{t0},{t1}], tick gap median {np.median(gaps):.0f} mean {gaps.mean():.1f} max {gaps.max()}; real plays {sum(bool(x[4]) for x in W)}")
print("p_play min/median/max %.3f/%.3f/%.3f" % tuple(np.percentile([x[1] for x in W], [0, 50, 100])))
for x in W[:6] + W[-3:]: print("  ", x)
RATE = [float(gate_rate(x[1])) if x[1] is not None else 0.0 for x in W]   # one inversion per decision
rng = np.random.default_rng(0); N = 20000; first = []; cards = {}
for _ in range(N):
    hit = None
    for i, x in enumerate(W):
        if x[1] is None or x[5] or x[4]: continue           # no model output / nothing affordable / a real (threshold) play here
        if (x[6] or 0) < MIN_EL or (QUIET and x[7]): continue
        dt = ((W[i + 1][0] if i + 1 < len(W) else x[0] + 2) - x[0]) * 0.05   # seconds this decision governs
        if rng.random() < -np.expm1(-RATE[i] * dt):
            hit = x; break
    first.append((hit[0] - t0) / 20 if hit else np.inf)
    if hit: cards[hit[3]] = cards.get(hit[3], 0) + 1
first = np.array(first)
print(f"hazard_below_tau from tick {t0}: P(play) within 5 s {np.mean(first <= 5):.2f}, 10 s {np.mean(first <= 10):.2f}, "
      f"20 s {np.mean(first <= 20):.2f}, ever {np.mean(np.isfinite(first)):.3f}; median {np.median(first):.1f} s")
print("card at that decision:", {k: round(v / N, 3) for k, v in sorted(cards.items(), key=lambda kv: -kv[1])})
