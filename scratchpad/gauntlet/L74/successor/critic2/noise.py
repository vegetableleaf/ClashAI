"""Critic lens 2: run-to-run noise from HANDOFF's arm-minus-twin paired deltas (960-game D3 evals), and what it implies for
power (bar: paired 95% lower bound > 0) and for the plan's lucky-pass and replicate-trigger numbers."""
import math, statistics as st
from statistics import NormalDist
N = NormalDist()
# (label, delta pp) -- HANDOFF 10-15..10-17 entries; same-seed twins unless noted
D = [("gae_live s74", 4.79), ("gae_live s75", -2.60), ("gae_live s76", 2.71), ("C1 s74", 4.79), ("C1 s75", 0.42),
     ("C1 s76", -0.21), ("exploit s74", 1.56), ("exploit s75", 2.29), ("exploit s76", -1.25), ("lam98 s74", 0.42),
     ("lam98 s75", -2.19), ("F6' s74", 3.33), ("F6' s75", -1.25), ("cue65", 0.31), ("cue130 (inert cues)", 5.10),
     ("exu250", -2.50), ("gae_ab", -1.15), ("gae_tower s74", 2.50), ("gae_tower s75", -2.60), ("gae_solv", 2.81),
     ("gae_opp", -1.25), ("F1 s75 vs s74 (same recipe)", 2.81), ("F1 s76 vs s74 (same recipe)", 2.92)]
x = [d for _, d in D]
sd = st.stdev(x); m = st.mean(x)
SE = 1.87                                   # measured paired SE on the promotion eval (fact02 / fact03 vs CXXXVIII rows)
tau = math.sqrt(max(0.0, (sd ** 2 - SE ** 2) / 2))
print(f"n {len(x)}  mean {m:+.2f}  SD of arm-minus-twin {sd:.2f} pp  -> per-run training SD tau ~ {tau:.2f} pp (if all null)")
bar = 1.96 * SE
for t in (tau, 2.5):
    tot = math.hypot(SE, t)
    print(f"tau {t:.2f}: P(pass | true 0) {1 - N.cdf(bar / tot):.3f}; >=1 of 4 {1 - N.cdf(bar / tot) ** 0 * 0 + 1 - (N.cdf(bar / tot)) ** 4 - 1 + 1:.3f}"
          .replace(" + 1 - 1 + 1", ""))
for d in (0, 1, 2, 3, 5):
    print(f"true +{d} vs CXXXVIII: P(bar pass) eval-noise only {1 - N.cdf((bar - d) / SE):.2f}; with tau {tau:.2f} {1 - N.cdf((bar - d) / math.hypot(SE, tau)):.2f}")
print(f"MDE (80% power) vs fixed reference: {(1.96 + 0.84) * SE:.1f} pp; arm vs ctl (one pair, SD {sd:.2f}): {(1.96 + 0.84) * sd:.1f} pp; two seed pairs: {(1.96 + 0.84) * sd / math.sqrt(2):.1f} pp")
# replicate trigger: best of 3 arm-minus-ctl >= +2 under the global null; arms share one ctl -> correlation 0.5
import random
random.seed(1); hits = 0; R = 200000
for _ in range(R):
    c = random.gauss(0, sd / math.sqrt(2)); a = [random.gauss(0, sd / math.sqrt(2)) - c for _ in range(3)]
    hits += max(a) >= 2
print(f"P(best of 3 arm-minus-ctl >= +2 | all null, shared ctl) = {hits / R:.2f}")
# live check: successor n=100 at p vs CXXXVIII 14/39
p0, n0 = 14 / 39, 39
for p1, n1 in ((0.50, 100), (0.50, 200)):
    se = math.sqrt(p0 * (1 - p0) / n0 + p1 * (1 - p1) / n1)
    print(f"live: successor {p1:.0%} on {n1} vs 14/39: diff SE {100*se:.1f} pp, 95% half-width {196*se:.1f}, power at +14 pp {1 - N.cdf(1.96 - (p1 - p0) / se):.2f}")
