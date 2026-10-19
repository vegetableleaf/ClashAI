# Codex ticket L16 FOLLOW-ON (lead Claude, 10-19). Keep the 4 pods busy until the lead takes over (~04:00 EDT 10-20).
Same repo, pods, rules and AUTHORITY as l16/TICKET.md (fix mechanical problems yourself; STOP only on design questions or
failing tests). Log everything with timestamps in l16/STATUS.md. Never deploy, never touch live, never stop a pod.

A. 15617 and 19899 (REF chains clx_l16 / cliii_l16): poll <= 9 min. When each REF chain is DONE:
   1. pull its rows sha-verified (pull_stepd.sh pattern; pod_backup_weekend/stepd/<name>/);
   2. then start on that pod a new seed of the SAME successor arm, staged exactly like 13396's stepd_l16_s74:
      15617 -> stepd_l16_s76, 19899 -> stepd_l16_s77 (yaml = stepd_l16_s74's with ONLY the seed changed;
      GO EVAL_LEVELS=all16, same DECODE; NO36=1 if that pod lacks fork36);
   3. verify SMOKE PASS and u1.
B. 13396 and 14009 (arms stepd_l16_s74 / s75): poll <= 9 min. When each chain is DONE:
   1. pull sha-verified;
   2. score with readout.py / pair_cmp.py on the fin13 all16 rows:
      - vs clx_l16 (ICEBOW Mark CLX at level 16): std, fresh, pooled, paired 95% CI;
      - vs cliii_l16: same;
   3. append the numbers to l16/RESULTS.md (one block per arm, with the checkpoint path + sha256 of the grafted u130);
   4. start the next seed on that pod (13396 -> stepd_l16_s78, 14009 -> stepd_l16_s79; staged the same way; verify SMOKE PASS + u1).
   If readout.py lacks the new arm names, add them as the lead did for nos2_s77/s78 (ARMS tuple + pairs vs the l16 REF),
   run readout.py --selftest, commit.
C. EXIT as soon as BOTH stepd_l16_s74 and stepd_l16_s75 are scored in RESULTS.md, leaving the new seeds running. Last lines:
   one line per scored arm: std / fresh / pooled vs CLX-l16 with CIs, and "PASS" if BOTH std and fresh CI lows are > 0, else "no pass".
Commit l16/STATUS.md, l16/RESULTS.md, new yamls and any readout.py edit (explicit paths); push.
