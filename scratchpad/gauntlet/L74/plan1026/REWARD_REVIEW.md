# Reward architecture review (2026-10-28, lead)

Scope: plan1026 Pillar 3, R = R_win + R_exchange + R_fork, plus the gates (X1-X4, L1b) and the parked fork-credit code
(`plan1026/wip_cf_credit/`). Labels: (a) measured or read in code/data, (b) plausible, untested, (c) contradicted.
Owner instruction: review the whole architecture and move on only when nothing else is needed.

## 1. Critical: the accepted "destroyed - committed" term rewards banking and leaking
The X1 candidate `a_lin` (rx/candidates.py) is (destroyed by us - committed by us) - (destroyed by them - committed by
them) = (D_opp - D_own) + (C_opp - C_own).
Both sides get the same elixir income G, so over a match, committed C = 5 + G - leak - stock. Therefore
**C_opp - C_own = (leak_own + stock_own) - (leak_opp + stock_opp)** (a, an identity up to Elixir Golem / pump effects).
With its fitted weight > 0, the term pays us for **holding elixir and for leaking it**: the hold-to-10 exploit (A3) and
the banked-elixir term the plan forbids, in disguise. It is also the most likely reason `a_lin` passed X1 on HF: the
X1 worker's own hypothesis was that the elixir STOCK predicts wins.
**Do not adopt `a_lin`.** If a linear form stays, the trade term must be elixir destroyed only (`ref_elixir`, which
also passed X1 on HF: +.005 AUC at 60 s, positive in all phases).

## 2. Recommended change: make R_exchange potential-based shaping on fitted win probability
Proposed: r_t = gamma * Phi(s_t+1) - Phi(s_t), with Phi(s) = P_hat(win | features(s), time to go) - 0.5, and
Phi(terminal) = 0; R_win unchanged.
Why:
- It keeps the dense, early credit that R_exchange exists for (win-only signal-to-noise ~0.2, credit over ~20
  decisions too thin).
- Potential-based shaping provably leaves the optimal policy unchanged (Ng, Harada & Russell 1999): the optimum is
  "maximise P(win)". No exploit can out-score winning, so the 0.5 cap and the unit mismatch between logistic
  coefficients (log-odds) and R_win (+-1) disappear.
- **The linear form changes the optimum toward tower-HP MARGIN**, capped at 0.5 of a win. That conflicts with the
  owner's own doctrine ("ahead 1-0: defend out; no risk when ahead"): extra chip damage while ahead is paid even when
  it lowers P(win). Under Phi = P(win), chip while already winning is worth little, exactly as the doctrine says.
- Phi may safely include the elixir STOCK, board value, cycle facts: a telescoping shaping term cannot create a
  hold-to-10 exploit. This settles the banked-elixir question without its risk.
- X1 becomes "Phi is calibrated and discriminating on held-out real matches". The tower-only model already reaches
  AUC .67 / .79 / .89 at 60 / 120 / 180 s with ECE .03-.08 (a).
Required details:
- Time to go must be a smooth input (no jumps at the 1x / 2x / OT boundaries, or every boundary pays a spurious reward).
- Use the same gamma per tick as GAE (0.99994); exact terminal handling (Phi(terminal) = 0).
- Fit Phi on exact-state data (HF re-driven on crforge), because training reads exact SIM state; check its calibration
  on SIM outcomes (X3). A miscalibrated Phi cannot change the optimum but slows learning.
- Drop the plan's stated intent "a deliberate change of the optimum (win the exchange the way winning humans do)": X1
  found that trades add nothing beyond tower damage (a), and Ranked rating counts only wins.

## 3. R_win: keep
+1 / -1 / 0 by the real tiebreak rule. No change.

## 4. R_fork (counterfactual fork credit): keep, with four fixes
1. Value forks in the same shaped return (window Phi plus critic), consistent with 2.
2. **Baselines.** The parked code appends alternative rows with advantage cf_w * clip(dQ / sd), dQ = V(alt) -
   V(baseline fork), while the real row keeps its GAE advantage against V(s). Two different baselines on one decision
   can double-count or cancel the real action's credit (b). Proposal: at a trigger row, all candidates (chosen +
   alternatives) get Q_i - mean_j Q_j from the same K = 2 common-random-number forks, replacing the real row's GAE
   advantage there. Unit-test it on a toy where the right answer is known.
3. **Coverage.** Credit only flows at hand-picked triggers. Add a small share of forks at random decision states with
   policy-sampled alternatives (e.g. 5% of decisions, inside the fork budget), so habits nobody named also get
   counterfactual credit, and the trigger list can be audited for what it misses.
4. Forks must use the Pillar 2 human-like opponents (L1b audits this), and the parked code must be finished and
   reviewed (it is a WIP patch, not in pipeline/).

## 5. Remove
- The `committed` term (section 1).
- The separate leak term: not predictive (X1), and unnecessary under potential shaping (leaking is priced through
  P(win) where it matters).
- The 0.5 cap (unneeded under potential shaping).

## 6. Add / specify
- An explicit entropy term (or confirm the current one) in the PPO objective: with no KL leash, the plan relies on
  clip + the KL early stop for step size, but nothing keeps exploration once the policy sharpens (b).
- Reward scale and critic target: R_win +-1, Phi in probability units (|Phi| <= 0.5); the critic predicts the shaped
  return.

## 7. Gates under the revised form
- X1: Phi calibration (ECE) and AUC on held-out real matches (HF + live, exact where possible).
- X2: still run, as an implementation check (it should pass by construction; a failure is a bug, e.g. terminal handling).
- X3: Phi calibrated on SIM outcomes (crforge plus the human-like opponents): the key fidelity check.
- X4: incentive-audit signs under the shaped return.

## 8. What runs now (owner instruction: send to X2 and X3)
X2 and X3 run on three variants side by side, so the owner can choose on evidence:
(i) the accepted linear form (towers + `a_lin`); (ii) linear towers + destroyed only; (iii) potential Phi (towers +
destroyed + stock + time). Plus a numeric check of the section-1 identity on HF traces.
