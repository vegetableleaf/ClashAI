# L16 successor arms vs ICEBOW Mark CLX at level 16 (clx_l16: std 693/960, fresh 687/960) -- lead, 10-20 ~05:00
Paired by (seed, tag, side, opp deck, occurrence); C:/Users/benpe/AppData/Local/Temp/claude/paircmp.py.
- stepd_l16_s74: std 689/960, fresh 652/960 (counts; std -0.4, fresh -3.6 pp) -> no pass.
- stepd_l16_s75: std 729 vs 693 = +3.75 pp [+0.18, +7.32]; fresh 701 vs 687 = +1.46 pp [-2.13, +5.04] -> NO PASS (fresh CI low < 0).
- CLX vs CLIII at level 16 (counts): std 693 vs 673, fresh 687 vs 648.
- stepd_l16_s76: std 676 vs 693 = -1.77 [-5.43, +1.89]; fresh 676 vs 687 = -1.15 [-4.80, +2.51] -> no pass.
- stepd_l16_s77: std 726 vs 693 = +3.44 [-0.14, +7.01]; fresh 706 vs 687 = +1.98 [-1.54, +5.50] -> no pass.
=> L16 recipe (CLX recipe + all-16 levels), 4 seeds: 0 passes; about level with CLX. No promotion.
Next on the pods (10-20 ~06:30): reward arms stepd_l16_redirect (13396), stepd_l16_lead (14009), stepd_l16_tornado (15617);
crown baseline stepd_l16_s74_crown (19899). O0 opponent-model check passed (opp_model/OPP_MODEL.md 6.1); O1 started (laptop).
# Reward arms (W6) -- lead, 10-20 15:40
- stepd_l16_lead (lead_protect, seed 74) vs CLX l16: std 692 vs 693 = -0.10 [-3.88, +3.67]; fresh 711 vs 687 = +2.50 [-1.01, +6.01] -> NO PASS.
  vs its control stepd_l16_s74_crown (same seed, --crown-log; win rows identical to s74 = crown log does not change play):
  std +0.31 [-3.34, +3.96], fresh +6.15 [+2.53, +9.76] (inconsistent across seed sets).
  Crown slices (1,920 SIM games): lost a princess 0.291 vs 0.318; gave back a 1-0 lead 2.6% vs 1.9% of matches; king_end 0.900 vs 0.907.
  NOTE: in this SIM (E4 opponents) give-backs happen in ~2% of games, so the penalty barely fires (live: 15-20%). Re-test on the
  calibrated-opponent base (both-crown 10.9%) -> tonight's lineup.
- stepd_l16_redirect (princess_redirect penalty, seed 74) vs CLX l16: std 690 vs 693 = -0.31 [-3.94, +3.31]; fresh 710 vs 687 = +2.40 [-1.21, +6.01] -> NO PASS.
  vs control: std +0.10 [-3.47, +3.68], fresh +6.04 [+2.35, +9.73]. Crown: lost a princess 0.292 vs 0.318; gave back 2.1% vs 1.9%; king_end 0.918 vs 0.907.
  Both reward arms show the SAME pattern (std ~0, fresh ~+6 vs control): the control's fresh set (652) is low against CLX (687) and
  the other seeds -> read it as control noise, not a reward effect. Neither term moves much in the old SIM; re-test both on the new base.
