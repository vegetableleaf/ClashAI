# Tower troops in SIM training (10-17) -- worker report (DONE_WITH_CONCERNS), saved by the lead

## 1. Live troop rates (measured)
222 capture folders, 218 usable; each princess-slot max_hp matched exactly (+-1) to one (tower, level) of a table built from the
fork; 218 / 218 matched exactly one entry. Wilson 95% CIs.

| ranked main account (own princess 4424), n = 214 | count | rate [95% CI] |
|---|---|---|
| opponent Dagger Duchess | 6 | 2.8% [1.3, 6.0] |
| opponent Cannoneer | 6 | 2.8% [1.3, 6.0] |
| opponent Royal Chef | 3 | 1.4% [0.5, 4.0] |
| opponent, any troop | 15 | 7.0% [4.3, 11.2] |
| our side, any troop | 0 | 0.0% [0.0, 1.8] |

Rates used (yaml + RATES): Duchess 0.028, Cannoneer 0.028, Chef 0.014. Arm C drew a troop in 259 / 4,160 matchups (6.2%).

## 2. Engine: fork clashbot36 bc2bf9d (preferred engine; no fallback needed)
Wheel built once (sha db2476f3...), identical on all pods; royalegym 0.1.23 + trainer + eval work unchanged. New runtime id
`fork36-linux` (pipeline/royale_runtime.py) -> venv files + build_manifest_fork36.json (30 files pinned by sha256, versions,
provenance bc2bf9d clean, embedded card table; freeze_fork36.py). pipeline/royale_heroiw.py must list fork36-linux in ENABLED or
the runtime silently loses the card-table override and the Hero IW form. Traps: the fork reads <build dir>/data/derived/cards.json
whenever it exists (build folder renamed so the embedded table is used); a fresh pod needs research/ext/Royale/RoyaleSim/data
(rsdata.tgz) or every actor dies with FileNotFoundError.

## 3. Files
pipeline/royale_runtime.py, royale_heroiw.py (runtime); royale_env.py (reset(..., tower_troops=None)); e1_eval.py (SelfPlayMatch:
troop on the opponent's side only); rl_royale.py (optional `opp_tower_troops`, validated, dropped from the config sha when absent;
drawn from its own stream keyed on the matchup seed + tag; logged per update); search_s0.py (`--opp-tower-troops Name:rate,...`,
drawn per (seed, opponent deck), via live_eval_pod.sh EXTRA). This folder: live_rates.py / live_towers.json / live_rates.txt /
tower_table.json; freeze_fork36.py / build_manifest_fork36.json / setup_troops.sh / constraints_1012.txt; check_env.py /
eval_check.py / checks.sh; gae_f36_u250.yaml / gae_f36tt_u250.yaml / RATES / run_pod.sh / pull.sh / cmp_tt.py.

## 4. Option off = unchanged
pyflakes clean (laptop + pod). Smoke with the option absent, HEAD vs edited files (B config, fork36-linux): config sha
48c1874834a9 in all three runs, identical pro-agreement / screen / u0000 / u0001 / resume lines, SMOKE PASS x3. Arm C config
SMOKE PASS (its 8 matchups drew no troop). Forced troops SMOKE PASS with changed results. Eval on 6 seeds: option absent rows
byte-identical old vs new code; forced troops change 3 / 6 outcomes. check_env.py PASS (tower hp = live values; only the
opponent's princess slots change; a later reset returns the Princess; 200,000 draws within 0.2 pp of the rates). Copies:
pod_backup_weekend/pod1017_troops/checks_pod23363/checks/.

## 5. Arms (seed 74, init u250 raw 0f1a1748, the gae control yaml, 65 updates, Hero IW)
| arm | run | trained on | checkpoint sha raw / grafted |
|---|---|---|---|
| A | rlarm_gae_ctl_u250 (reused, pod8_cues) | PyPI 0.1.35 | eaa5ea80 / 0a8a4753 |
| B | rlarm_gae_f36_u250 | fork36, no troops | c195f632 / 4ac98b6b |
| C | rlarm_gae_f36tt_u250 | fork36 + opponent troops at live rates | ff813982 / bd55328d |

## 6. Evals (fork36-linux, D3, 960 paired; main = troops at live rates, 63 / 960 games had one; slice = every opponent has one)
| win rate | main | slice |
|---|---|---|
| A | 635 (66.1%) | 643 (67.0%) |
| B | 628 (65.4%) | 638 (66.5%) |
| C | 603 (62.8%) | 600 (62.5%) |
| u250 | 548 (57.1%) | 590 (61.5%) |

| comparison | main | slice |
|---|---|---|
| B - A (engine) | -0.73 [-4.58, +3.02] | -0.52 [-4.38, +3.44] |
| C - B (troops) | -2.60 [-6.35, +1.15] | -3.96 [-7.71, -0.10] |
| A - u250 | +9.06 [+5.21, +12.92] | +5.52 [+1.77, +9.38] |
| B - u250 | +8.33 [+4.48, +12.19] | +5.00 [+1.15, +8.85] |
| C - u250 | +5.73 [+1.98, +9.48] | +1.04 [-2.71, +5.00] |

- Engine (B - A): measured null at 65 updates.
- "Troop training helps": contradicted on this sample; "troop training hurts": not established (C is also weaker in Princess
  games, 63.0% vs 65.4%; one run per arm, CIs cover eval noise only; seed spread ~+-3 pp). Fair reading: null.
- Troops are not a large weakness for any checkpoint in the SIM (B 65.1% troop games vs 65.4% Princess; u250 55.6% vs 57.2%).
- The eval engine changes the ranking: A - u250 is +9.06 here vs +3.44 [-0.42, +7.50] on the 0.1.35 live pool.

## 7. Open for the owner
1. Which engine sets the promotion bar (fork + troops eval: A, B, C all beat u250 with CI lower > 0; 0.1.35 pool: none did).
2. Keep `opp_tower_troops` (off by default, safe) -- no evidence it helps; settling it needs 2-3 seeds per arm.
3. SIM TRAINING USES LEVEL-11 TOWERS (princess 3052) on both sides; live is L15 vs opponents L14-16. Not changed (one change
   per arm).
