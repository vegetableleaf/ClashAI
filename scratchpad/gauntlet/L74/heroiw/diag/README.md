# IWDIAG

Built diagnostic job; no SIM games have been run for this ticket locally.
The four fresh arms run sequentially, each with at most 25 worker processes.
All use the frozen old live checkpoint, P1/E4 opponent at T=.1, original CAL-c
evo/lad censuses, 480 games per arm, seeds 741200..741439 in each census, alternating
learner side. This is HEROIW's DRIFT design. No network or installation is needed.

| Arm | Runtime | Ice Wizard | Press policy |
|---|---|---|---|
| N0 | 0.1.33 | Hero | Existing v2 generic proximity fallback |
| N1 | 0.1.33 | Normal | Same as N0 |
| N2 | 0.1.33 | Hero | Live geometry and deterministic hazard >= .03 |
| O0 | 0.1.17 | Original forms | Original v2 behavior |

N0 does **not** use an IW ability head: IceWizard is absent from `V2_KEYS`, so
`RoyalePoolEnv._v2_gate` calls `_near`. The supplied prior HEROIW match receipts
also record `ability_fallback_generic.IceWizard`. Both new switches are opt-in:
unset `ROYALE_HEROIW_FORM` preserves hero forcing in the new runtime;
`ROYALE_HEROIW_FORM=normal` removes it only for the icebow deck.
Unset `ROYALE_HEROIW_PRESS` preserves the existing policy;
`ROYALE_HEROIW_PRESS=live` selects the SIM port and requires the new runtime + v2.
The launcher explicitly sets all three runtime/form/press variables for every arm.

N2 uses the same pure live hazard code and fitted coefficients, the live V>=4
clump geometry (two bodies or more), or a win condition on our half while Tesla
is unavailable/under 4 elixir. The threshold is .03, not a randomized per-frame
probability. Hazard features use the whole-second grid since own deployment,
own confirmed play history, and a body/spell-derived public opponent counter.
Only IW changes; other hero/champion policies keep their original paths. SIM
retains its normal decision cadence, 26-tick delay, and engine readiness checks;
UI sampling, no-pending-tap guards and confirmation latency are not simulated.

Run from the synchronized pod checkout, with the existing HEROIW environments:

```bash
WORKERS=25 bash scratchpad/gauntlet/L74/heroiw/diag/run_iwdiag.sh
```

`OLD_PY=/workspace/venv/bin/python` and `NEW_PY=/workspace/venv33/bin/python`
may be overridden to existing provisioned paths. Requires `/workspace/results`.
The script holds `/workspace/cpu.lock` for the entire job and refuses to reuse
`/workspace/results/IWDIAG`, including a failed run. ETA **1.5-3.1 hours** at 25
workers, excluding lock wait; this is 2-4 times the previous 47 games/minute at
28 processes to allow for unbenchmarked per-tick telemetry. It is not a measured
timing promise. Lower worker counts scale the estimate in the final header.

Results: `/workspace/results/IWDIAG/SUMMARY.txt`, `score.json`, `DONE` with an
explicit `exit_code`, frozen inputs/hashes, and per-arm/per-game receipts.
An interrupted/failed job writes FAILED + a nonzero DONE, preserving partial logs.
Successful summary requires all 1,920 outcomes and matching census, seed, deck,
side and opponent hash. CIs resample paired outcome differences within census
and side (10,000 draws); draws count as non-wins.

Ability metrics are accepted presses/game, actual zero-tick elixir debit/game,
and accepted/submitted success rate, with scheduled decisions also reported so
failed landing rechecks remain visible. No attempts yields n/a, not a 100% rate.
X-Bow placements count accepted deployments. All arms receive the same observer
instrumentation; it adds no policy calls or RNG draws.

**X-Bow damage limitation:** the public runtime interface has no source-attributed
damage ledger. The report therefore supplies an explicitly labeled estimate:
tower HP loss on the tick a visible X-Bow bolt is within one catalog-speed step
of its public tower aim. Possible mixed damage is counted separately and raw
impact receipts are saved. This is neither exact source damage nor a guaranteed
bound: simultaneous attacks, same-tick unseen projectiles and modifiers can
confound attribution. `xbow_tower_damage_exact` remains null. No hidden target
IDs, debug combat state, snapshot forks, or counterfactual rollouts are used.
N1/N2 test form/press changes; these arms cannot establish X-Bow mechanics as a
cause from telemetry alone.

Device cost finding: **2 elixir** for `ABILITY.IceWizardHero_ability.ManaCost`
(device-update TOML line 48), **3 elixir** deployment for `IceWizard_hero`
(`spells_hero_form.csv` line 26, APK fallback). `device_cost.json` retains the exact
rows, provenance, extraction fingerprint, and SHA256 hashes. The pinned 0.1.33
source table also says 2; HEROIW's prior smoke observed 2. The adapter submits a
button command and the SIM charges it, without substituting the live supplement.
Thus no table-versus-adapter charging mismatch is evidenced; the supplement's 1
conflicts with the device table and remains untouched. Pod rows independently
record the actual wheel's table cost and actual per-press debit.

Offline verification (no engine package imports allowed):

44 tests passed; source checks and exact archived schedule comparison passed.
Git Bash `-n` was attempted but Windows sandbox `CreateFileMapping` failed with
error 5 before parsing. Static launcher assertions passed; Linux execution and
shell parsing remain unverified locally.

```powershell
icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/heroiw/diag/verify.py --tests
icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/heroiw/diag/verify.py
```

`cost_evidence.py` rebuilds the cost receipt from the local ignored APKTABLES
device extraction and pinned local Git object; it is not required on the pod.
Copy the diag directory, the three changed/added `pipeline/royale_*` modules,
and retain the existing full HEROIW checkout/checkpoints and read-only live
hazard/model/unit-value dependencies listed in the input manifest. No live
scripts or supplement were modified. Changes are left uncommitted.
