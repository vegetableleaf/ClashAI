# Plan after the REB verdict (lead, 2026-10-18 evening; owner-approved scope: a little now, the rest Tuesday)

Inputs: doctrine check (L74/doctrine/DOCTRINE_MEASURED.md, bcac5e4), FIN13 parity (parity/diag_night/R7_SUMMARY.md),
step-d arms (stepd/STATUS.md). Roles: Claude (lead or API worker) decides; Codex executes mapped steps only.

## What the doctrine check means
- Owner claim CONFIRMED and X-Bow-specific: pros at 1-1 in overtime win 29.9% vs 52.7% from 0-0 (-22.9 pp); losing the
  FIRST princess is near-fatal for X-Bow (pros <= 2.5%; ours 1.4-3.6%).
- Our bot does NOT lose towers more than pros (47-55% vs 48%). Its gap is GIVING A LEAD BACK: after 1-0 it loses a tower
  back in 15-20% of matches vs <= 5% for icebow pros; both-crown games 14-20% vs 2%.
- Root cause = the SIM: its opponents take a princess in 31.6% of games (live 47-55%) and 1-1 costs only -8 pp there
  (live -28..-39). Training never learns that towers matter. Same root as the parity / habits findings.
- Style gaps confirmed: cheap-only answers to heavy pushes 42% vs 28%; Rocket on heavy pushes 0.4-2.2% vs 8.3%; tower Rockets
  0.4-0.6 vs 1.6 per match. NOT gaps: elixir trades by spend, X-Bow volume. "Early X-Bow loses" contradicted in its simple
  form (early-X-Bow pros win +5.4 pp).

## NOW (tonight; small)
1. Takeover watch on the overnight API orchestrator (lead session; armed).
2. REB verdict + auto-promote: per overnight1018/TICKET.md (orchestrator).
3. After the verdict, Codex (mapped task): add the doctrine's crown + style SLICES to stepd/readout.py and the live monitor,
   score every REB arm, CLIII and cue_ab2 (SIM and live): P(lose princess), both-crown rate, give-back after 1-0,
   P(win | OT 1-1), P(win | lost first), cheap-only on heavy pushes, Rocket in heavy answers, tower Rockets / match,
   first bridge X-Bow time. Report only, no gate change. Targets = pro icebow values (48% / <= 2-4% / <= 5% / ... / 1.6 / 75 s).

## TUESDAY (full execution, one change per experiment)
A. SIM parity (the root of everything above). Now FIN13: raw 0.926 [0.920, 0.932], 403 matches; tier-B coverage 0.278;
   goal: lower CI >= 0.975 overall and >= 0.90 of tier-B plays meeting per card.
   - Next levers by gap map: timing (162), movement (86), target picks (61), setup state (43).
   - Why the 139 new captures score lower (0.926 vs 0.930 on the old ones).
   - Land H-PREROLL once it has more data; the reader fix H-NEGHP needs.
   - NEW parity metric from the doctrine: SIM vs live princess-loss rate and 1-1 penalty.
B. Opponent curriculum C1: gate the Stage-2 / exploiter opponent mix on CROWN statistics, not just win %. Keep a mix only if
   CLIII's P(lose a princess) against it is ~0.5 and P(win | 1-1) ~0.2-0.3, as live.
C. RL arms on the REB winner (or CLIII if REB fails), one change each:
   - R1 lead-protection penalty (~0.2 x the win reward; guard against passivity with the tower-Rocket / bridge-X-Bow slices);
   - C2 crown-state starts at 1-0 / 1-1 (needs engine support for initial tower HP: check first);
   - R3 re-grade the Rocket arms on the tower-Rocket slices.
D. Gates: the crown slices are reported beside the CI gate (not a replacement) for every candidate.
E. Live: the cue_ab2 trial readout at the same trophy level as CLIII; REB's live trial if it passes; finish the 16-run
   factorial analysis (15/16 in; analyze.py refuses with one run missing).
