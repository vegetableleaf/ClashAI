# R_exchange gate X1 failed: decision request (2026-10-28)

Labels: (a) measured, (b) plausible but untested, (c) contradicted. "AUC gain" = how much better a win predictor
gets when the term is added to the tower-only predictor (princess HP, king HP, king activation, crowns), on matches it
never saw (held out by date for live, by replay tag for HF). 95% CIs by resampling matches.

## What failed
The plan prices elixir trades through R_exchange, with weights fitted on real results (gate X1 = the terms must
predict wins on unseen matches, with the expected signs). **On our live matches they do not (a).** Elixir destroyed and
elixir leaked add no held-out AUC over tower damage, and their weights are not distinguishable from 0.

## Evidence
| data | matches (train / held-out) | AUC 60 / 120 / 180 s | gain over tower-only at 60 s | elixir weight > 0? | leak weight as expected? | elixir per princess tower (1x / 2x / OT) |
|---|---|---|---|---|---|---|
| live, 2-tick frames | 1,863 / 1,133 | .668 / .789 / .887 | +.004 [-.001, +.009] | no (CI spans 0, all phases) | no | 186 / 840 / 554 (CIs up to 1,500-4,900) |
| live, + per-decision logs | 3,978 / 1,137 | .667 / .788 / .886 | +.001 [-.003, +.005] | no | no (2x significantly wrong way) | 441 / -1,097 / 1,095 |
| HF pros, re-driven on crforge, exact elixir | 11,867 / 2,978 | .658 / .809 / .912 | +.003 [-.003, +.008] | **yes, all phases** | 1x only | **125 / 240 / 309** [95-434] |

- The earlier "22-25 elixir per princess" (c) does not hold for elixir *destroyed*. It came from SIM matches and a
  different quantity (elixir in hand + on board, with the opponent's TRUE elixir). Real games price a princess tower at
  125-840 elixir of trades, i.e. trades are 5-30x cheaper than towers.
- We out-trade opponents by about 19 elixir per match in wins AND losses (18.4 vs 19.1) (a).
- Own leak goes slightly WITH winning on live (we sit at 10 when the opponent is passive); leak while under threat has
  the expected sign once overall leak is controlled (live + per-decision logs, 2x: +.080 [+.023, +.145]) but adds no AUC (a).
- Data checks (a): our leak vs the battle log r .986; the public opponent-elixir counter's leak r .90 but +4.0 per match
  too high; HF re-drive committed elixir vs HF's own stats r .97; 95% of log labels agree with the battle log.

## Revision candidates (all zero-sum, public, no banked term); kept only if AUC gain CI > 0 AND sign as expected
| candidate | live frames: gain 60 / 120 / 180 s | HF: gain 60 / 120 / 180 s | kept? |
|---|---|---|---|
| (ref) elixir destroyed, running | +.003 [-.001,+.008] / +.001 / +.001 | +.005 [+.000,+.009] / +.001 / +.001 | live no / **HF yes** (sign + all phases) |
| (a) destroyed - committed, running | +.005 [-.002,+.012] / +.001 / +.000 | **+.006 [+.002,+.011]** / +.001 / +.001 | live no / **HF yes** (sign + all phases) |
| (a) per engagement, tanh(trade/4) | +.002 [-.003,+.007] / .000 / .000 | +.000 / +.001 [-.000,+.003] / +.001 | no |
| (b) efficiency (destroyed / their committed) | +.002 [-.000,+.006] / +.001 / +.001 | +.003 [-.001,+.008] / -.000 / +.001 | no (HF sign + all phases, no gain) |
| (c) leak only under threat | +.002 [-.001,+.005] / .000 / .000 | +.000 / -.000 / +.000 | no (HF OT sign wrong) |
| (d) tower damage x net trade in last 10 / 20 s | +.001 / +.003 [-.000,+.006] at 60 s | +.001 / +.001 [-.001,+.003] at 60 s | no (HF sign + all phases, no gain) |

## What this means
- (a) Tower damage already carries what trades predict: a good trade matters through the tower damage it later causes
  or prevents. A dense elixir term mostly re-pays the same thing.
- (a) Only two terms pass, and only on HF (12k pro matches, exact elixir): elixir destroyed (+.005 AUC at 60 s) and
  destroyed - committed (+.006 at 60 s); both add nothing by 120 s. Live (3k matches, our own games) does not confirm
  them: same direction, CIs span 0. Whether that is sample size or our deck / opponents is (b) untested.
- (b) Even where it passes, the weights make a princess worth 125-309 elixir: as a reward it is a small tie-breaker, not
  the "win the exchange" driver the plan wants.

## The banked-elixir option (needs your decision; not implemented)
The quantity that DID predict in the SIM (A3') is the elixir stock: elixir in hand + value on board. The plan forbids
a banked term because of a known exploit:
- **hold-to-10:** a stock term pays for sitting on elixir. A3 failed exactly this way (hold-to-10 and never-spell
  out-scored the imitation policy), and LIVEPHI with own elixir raised P(win) .39 -> .60 by banking (a).
- Live, the opponent's stock is only an estimate (public counter, +4 elixir/match biased), so a live-fitted stock
  term would also reward fooling our own counter (b).
- If allowed, the guard is gate X2 (farm audit: hold-to-10 and never-spell must not out-score CLXIII) plus the leak
  term; the fit would have to come from HF/SIM where both stocks are exact.

## Decision request
1. Accept R_exchange = tower terms + the HF-fitted destroyed - committed term (passes X1 on HF, not confirmed live), and
   send it to X2 (farm audit) and X3 (SIM calibration)?
2. Or allow an elixir-STOCK term (fitted on HF/SIM, exact both sides) with the hold-to-10 risk, X2 first?
3. Or keep R_exchange to tower terms only and leave trade credit to the fork credit (P3), which compares two actions on
   the same objective and cannot pay a term for its own sake?
Files: `rx/out/` (all numbers), `rx/candidates.py`, `rx/fit.py`, `rx/hf_traces.py`; commit after this page.
