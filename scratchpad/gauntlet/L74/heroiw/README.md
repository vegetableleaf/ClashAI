# HEROIW — opt-in Royale runtime and pod validation

Implemented offline; wheel compatibility and gameplay results are UNMEASURED until the pod job completes.
Nothing is deployed. The changes are deliberately uncommitted. Existing live scripts and LIVE_OPTIONS are untouched.

## Run on the pod

From the checkout containing these changes and LIVECAL's checkpoint/data inputs:

```bash
WORKERS=25 bash scratchpad/gauntlet/L74/heroiw/run_heroiw.sh
```

`OLD_PY` defaults to `/workspace/venv/bin/python`. `INCLUDE_P3=1` adds P3.
`LIVECAL_OLD=/path/to/old/results` can name a compatible archived baseline with a
`runtime.json` proving `20261006-linux`; without that evidence a fresh old baseline
is run under `HEROIW/LIVECAL_OLD`. A complete older all-pools run can supply the requested subset.

The launcher holds `/workspace/cpu.lock` across preflight, install and all children;
uses at most 25 single-thread workers; never contacts or reconfigures a live bot.
It refuses a used output directory or an existing `/workspace/venv33` instead of
deleting or mutating either. Use a fresh pod/output after reviewing a failed run.
Ordinary failures and INT/TERM write `/workspace/results/HEROIW/SUMMARY.txt` and
`DONE` (nonzero exit code); an existing run's refusal preserves its receipts.
SIGKILL, disk failure and machine loss cannot guarantee an EXIT trap.

The new venv has its own wheels. A `.pth` references the old environment's heavy
dependencies read-only. Pip uses `--ignore-installed --no-deps`, so it never
uninstalls or writes the old wheels. The job checks the new Gym's dependency
requirements, hashes Gym Python sources against the fetched release, verifies
engine clean-build provenance and embedded data, and records its runtime stamp.
The original venv's full file inventory and old runtime stamp must remain unchanged.
Missing dependency versions cause failure; there is no silent runtime fallback.
Python 3.12 or newer is required by RoyaleGym 0.1.23.

Inputs: the unchanged LIVECAL `manifest.json`, `truth.json`, `census_evo.json`,
`census_lad.json`, all checkpoint files listed in `livecal/NEEDED_FILES.txt`, both
original census paths in `livecal.CENSUS`, and the pipeline/source support files.
The driver checks checkpoint hashes against that frozen manifest, then writes a
new support-code manifest under `HEROIW/inputs`. Do not refresh live truth during
this comparison. The job assumes the old runtime is already installed and verified.

At LIVECAL's recorded estimate of 47 games/minute with 28 processes, scaled to 25,
the default 10 groups x 3 pools x 480 games take about 5.7 hours per runtime.
Smoke + 960 drift games add roughly 25 minutes. Allow **6–7 hours** with a reusable
old baseline, or **12–13 hours** with a fresh one, plus install/lock wait. These are
estimates, not measurements of 0.1.33. P3 adds about 1.9 hours per runtime.

## What is checked

1. Eight full games: legal 3-elixir Hero IW deployment, production v2 ability path,
   a 2-elixir press, refusal of a second press from the same deployment, cube body
   in the public observation with identity 203000023, and engine game-over without
   a crash. Scenario cards are placed in the opening hands by setup order; no
   debug-spawns or state injections. Receipts: `smoke.json`.
2. 480 matched OLD/NEW CAL-c games (960 games total): the old live checkpoint
   `rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt`, rdef_e4 graft at T=.1,
   240 games per original EVO/ladder census, seed range 741200..741439, alternating
   seats. Same checkpoint hashes, opponent decks, seats and seeds must match.
   Win-rate change is NEW minus OLD, with a 95% paired bootstrap CI (10,000 draws,
   stratified by census and side; draws are non-wins). Missing or mismatched pairs
   fail instead of being discarded. Receipts: `DRIFT_*/`, `drift.json`.
3. Existing LIVECAL scheduling/scoring under NEW for P1/P2/P5, optionally P3,
   into `/workspace/results/LIVECAL_NEW`. It keeps the frozen weighted censuses,
   all 10 checkpoint/fast arms, 480 games per arm/pool, seeds and S2/CAL settings.
   Comparison reports both `old > E4` and `fast-off > fast-on`, with each runtime's
   paired contrast CIs. The verdict compares descriptive sign counts, not a claim
   of statistically significant improvement. `comparison.json` retains both reports.

This is the combined effect of the engine release, current card table and Hero IW.
It cannot isolate the hero's effect, and LIVECAL remains a standardized surrogate
for observational live results. No training, checkpoint edits or deployment.

## Adapter and upstream API

Both fetched `origin/HEAD` refs equal their release tags:

- RoyaleSim v0.1.33: `cacb7005f0e441797c533e91ab4f44820f9919d4`, incorporating
  `6bb7b62` (Hero IW) and subsequent release fixes/review cleanups.
- RoyaleGym v0.1.23: `a7deb6e48c3580fe2cd7d856b7c7d19ce67f02f9`.

Reviewed via `git show origin/HEAD:...`, without fetching or installing:
`royalegym/rust_engine.py`, `royalegym/protocol.py`, both CHANGELOGs,
`crates/royalesim/src/{card,state,py}.rs`, `crates/royalesim/tests/hero_ice_wizard.rs`,
`data/calibration.json`, and the old/current derived card tables.

`ROYALE_RUNTIME=20261012-linux` uses the active venv; `20261012` uses
`research/ext/Royale-20261012/runtime` (a separately provisioned Windows target).
Both select `RustEngine(calibration_overrides={'cards.CARD_TABLE':
'client160402017_20261006'})`. RustEngine JSON-encodes the values; direct
`royalesim.Battle` takes JSON text instead. Merely installing 0.1.33 does not
select this table: upstream still defaults to 15.535.

Under the new pin the SIM uses deck forms and promotes IceWizard to form 2 in
the exact icebow card set, on either side. Engine refusal of this form is fatal,
not a silent base-card fallback. Other explicit hero decks remain supported.
Unset/20261006(-linux) keep their previous paths, manifests, table, forms and stamps.

Commands still use `MatchSetup.forms` and `DeployCommand(side, HAND_SIZE+button,
0, 0)`. Engine button cost/readiness and `check_deploy` are authoritative; the
engine deducts mana and consumes the charge. The selected embedded card table
says 3 deployment elixir, 2 ability elixir, one charge, no recharge (`cooldown_ms:
null`), and 1000 ms deployment. Own model ability tokens use that same selected
table plus own accepted action history; no opposing hand, elixir or readiness is
added to model inputs. Champions retain their button path after 0.1.20 removed
their hero status bit.

Hero IW has no calibrated per-ability v2 model here. It enters the existing v2
generic public range fallback, tracked by `ability_fallback_generic`; this ticket
does not invent a trained press model or port live's `iw_press_pstar 0.03` rule.
The model's existing ability observations and queued button command path are used.

Public `unit_type` names come from `RustEngine.unit_types()`, whose source is
`CardDef.unit_name` (the hero body is `IceWizardHero`, not the internal card-row
name `IceWizard_hero`). Body, `IceWizardHeroFloatingCube` and
`IceWizardHero_IceCube` map to live reader id 203000023 / IceWizard / form 2.
The cube's actual engine status flags are preserved. Upstream has a gameplay cube;
no cosmetic FloatingCube is fabricated. Its public alias is supported if emitted.

## 0.1.18 → 0.1.33 changes relevant to icebow and common opponents

The existing pin is actually 0.1.17; 0.1.18 adds measurement switches but changes
no default battle behavior. The full source default diff is preserved in
`calibration_changes.json`; a missing old key means the switch did not yet exist,
not that the old engine had no mechanic. The release includes many targeting,
collision and timing fixes, not only Hero IW.

- **X-Bow:** buildings now release an out-of-range target using its position after
  movement following the shot. This can change locks and retargets. In the current
  table selected by this adapter, X-Bow's base damage/projectile damage is 24
  instead of the old table's 23 (before level scaling). That stat change comes
  from selecting the table; upgrading the wheel alone keeps the old default table.
- **Tesla and building deployment:** only Tesla can target/attack on the final
  deployment countdown tick in 0.1.33; X-Bow, Cannon, Inferno Tower, Mortar and
  other buildings wait until deployment finishes. 0.1.30 briefly enabled this
  early tick for every building. A deploying Tesla that acquires a target stays
  up. Existing attackers can retain a Tesla through hiding, and a shot already
  fired at that Tesla can land after it hides. New targets cannot acquire it
  underground. Evo Goblin Drill's disappearing building has its own shot rule.
- **Log and troop placement:** a fallen enemy princess opens that lane's bridge
  for troops and Log; the intact lane and off-bridge water remain closed.
  Gym 0.1.23 turns illegal-tap clamping on: a troop or restricted spell such as
  Log tapped beyond its allowed territory is moved back along its column.
  The legality mask still excludes those taps. Building overlap relocation and
  equal-distance choices now follow the measured client order, including seat
  asymmetries. Pull/knockback and retarget fixes can also change what the Log hits.
- **Tornado:** pull starts one tick after the area's tick and finishes one tick
  later; when troops touch, the pull participates in their contact average.
  Ground troops pulled toward water stop at the water edge. The extra final
  Poison pulse does **not** extend every-tick or pulling areas such as Tornado.
- **Rocket:** no direct Rocket cost, damage, range or timing row change was found
  between these two selected source tables. Its outcomes can change because
  targets move, get pushed, select targets and die on different ticks. Do not
  interpret the runtime upgrade as a measured Rocket buff.
- **Knight and general troop combat:** no direct base Knight stat change was
  found in the compared tables. Target ties now prefer the later-created target;
  reach checks, chase/knockback retargeting, post-kill waits, swing preservation,
  death pushes and stun/freeze reload holds have changed. Hit-delivered freezes
  and stuns let reload run one more tick before the hold. These common rules
  affect Knight, Skeletons and their opponents as well as ranged troops.
- **Skeletons:** the selected current table has a 400-unit summon ring versus
  the old table's 700. 0.1.27 specifically fixes the October 6 Evo Skeletons ring
  extraction. Evo copies appear on the tick after their hit, count the cap at
  hit time, and use the corrected/clamped spawn point. Waiting formation members
  cannot take attacks or area hits before appearing.
- **Poison and pulsing areas:** Poison's first pulse is 25 ticks after cast;
  slower non-pulling pulsing areas receive their last update at the end of life,
  so a unit still inside Poison takes an additional pulse. A strike scheduled
  exactly at an area's end now lands. Offsetless hero areas have corrected first
  update timing too.
- **Line territory:** Royal Hogs and Royal Recruits placed in an opened pocket
  stand there instead of being dragged back to their own half. They keep the lane
  of where they actually stand. Line center search, orientation, back-row access,
  and placement tie rules also changed; seats are not perfectly symmetric.
- **Other common opponents:** Little Prince guard birth/charge/landing and hold
  timings changed; Golden Knight can chain to ground buildings/towers; Electro
  Spirit continues a chain after its target dies; Evo Electro Dragon delays each
  hop; Dagger Duchess now uses her burst/recharge; Evo Witch wave ordering and
  Evo Battle Ram contact with waiting troops are corrected. Flying units can be
  pushed over the river while deploying; deploying ground units stop at the bank.
  The current table includes the October 6 balance values; level 17 and Mirror
  from level 16 are supported. Neither extra levels nor new tower troops are
  silently selected by this job.
- **Hero IW itself:** its button waits for the closest enemy marked by its deploy
  chill or shots, creates a cube behind it, freezes/damages nearby enemies, and
  releases them with a slow when the cube disappears. Maximum cube life is five
  seconds; empty cubes end earlier. Upstream reports 34 measured live cubes.
  The hero-kills-target and hero-dies-while-waiting branches are data-derived,
  explicitly not measured upstream.

## Offline verification and remaining evidence

```powershell
research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L74/heroiw/verify_offline.py
```

The wrapper runs pytest and refuses success if either engine package was imported.
Measured 2026-10-12: **70 passed**, one existing PyTorch nested-tensor warning,
13.37 seconds, `HEROIW_OFFLINE_OK`. `VERIFICATION.json` records the source hashes.
Tests exercise runtime selection against the pre-ticket source, form requests,
fail-closed hero loading, production controller scans with a fake protocol,
public cube identity through the actual observation reducers, existing reader/live
identity regressions, own ability tokens and paired scoring failure controls.

No wheels were downloaded or installed here, no SIM game ran here, and no pod
was launched. The pod must confirm exact wheel Python API, compiled provenance,
selected table construction, real hero/cube/cost/charge behavior and all numerical
drift/LIVECAL results. Local `bash -n` was attempted but Git Bash failed before
parsing with Windows CreateFileMapping access denied; shell syntax was reviewed
offline and must also be checked by the pod's Bash. Do not report gameplay parity
or a better calibration ordering until the job's results exist.
