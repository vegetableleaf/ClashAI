## 2026-10-13 ~16:30 EDT -- 3 owner pods: DIFFSIM self-check green except forms coverage, PARITY own-timing fix, Hero IW N3 arm

Pods (key `~/.ssh/runpod_clashbot`, NOT id_ed25519; 27 effective cores each, L40): A `-p 43696 root@64.247.206.120`,
B `-p 15199 root@64.247.206.79` (STOPPED 20:28 UTC after verified copy), C `-p 13124 root@64.247.206.79`.
Setup: `L74/deploy/pod_setup_l74.sh` (repo archive + venv33 + fork cacb700 build, FORK_BUILD_VERIFIED on all 3).
Relays (WMI, outside the session; `pod_relay2.sh`, BUSY now env-overridable): A Windows PID 36676 -> `pod_backup_weekend/
pod1013a`, C PID 81260 -> `pod1013c`; each copies + verifies, posts Discord, stops its pod after 2 h idle (KEEP file blocks).
- **DIFFSIM (pod A):** the pod-D 79.8% was harness errors, 0 divergences. Two generator bugs fixed (`generators.py`
  random_scenario: a replacement champion was appended to the list being iterated -> duplicate deck card; champions given
  levels < 11) + regression test. SANITY2: errors 0; full 1000/1000, skirmish 100/100, duel 3969/3969, building, single,
  spell 100%; forms 27/35 = coverage gaps only (expensive evos never evolved, Hero Tombstone never pressed in 150 s:
  cheap fillers starved the focus card). Fix: forms 300 s + focus side banks elixir. SANITY3 running (relay A).
- **PARITY (pod B; `parity/run_timing_arms.sh`, results `pod_backup_weekend/pods1013/parity/`):** new opt-in
  `--own-timing spawn|spawn_mid` and `--pair-swarms-by-position`. Arm A reproduces pod D exactly (1.2885). Spawn timing:
  unit MAE 1.289 -> 0.882 tiles, unit HP 250 -> 195, tower HP 389 -> 338; own Knight 2.0-2.5 s 1.04 -> 0.14, Skeletons
  1.99 -> 0.39. spawn_mid worse (1.07). Swarm pairing ~no effect: CONTRADICTED that Skeletons are mis-paired (first-sight
  median 0.10 tiles, 0.6% > 1.5). Skeletons residual is real, sim ahead +0.2-0.3 tiles (Knight not); untested candidate:
  per-member spawn stagger.
- **Hero IW (pod C):** RoyaleSim's ice cube (fit on 34 live cubes) matches the device toml rule by rule (cost 2, target
  = closest marked enemy, cube radius+1000 behind, freeze r 2.5 / dmg 18 (tower 15), 5 s life, 2 s linger, then 30% slow
  2 s). New `ROYALE_HEROIW_PRESS=never` + IWDIAG arm N3 + `--arms`; IWDIAG3 = N0/N1/N3, 480 paired each (relay C).
  **IWDIAG3 RESULT (480 paired/arm; N0/N1 reproduce the 10-13 run exactly):** N0 35.42%, N1 51.46%, **N3 (hero, never
  pressed) 48.12% = +12.71 pp vs N0 [+7.50, +17.71]; N3 vs N1 -3.33 [-9.17, +2.50]**. So ~12.7 of the 16 pp SIM gap is
  the presses (N0: 6.58/game, 13.2 elixir) displacing X-Bows (placements 3.64 vs 4.10, X-Bow tower dmg 1,325 vs 1,742/game);
  the hero body's -3.3 is not established. Earlier N2 (live rule, 2.36 presses) 40.0% = still ~-8 vs never pressing.
  Open: does a press cost the same live? Live median elixir drop/press 1.143 (n 763) vs device cost 2, and the device
  ability has RefundWindow = 50 -- untested refund hypothesis; check the live drop distribution offline. test_iwdiag 24/25 (the failing
  `test_device_evidence_matches_local_sources` is stale since this morning's supplement 1 -> 2 change).
- v8: owner reports a rebuilt run; I did not verify or advise on it (safety stops). oracle-2 kept warm per owner.

