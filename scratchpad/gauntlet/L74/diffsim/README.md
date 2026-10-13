# DIFFSIM

Offline differential-testing harness for the owner's simulator target: at least
990/1,000 randomized full matches with tick-identical traces and 1,000/1,000
identical results against the real game. This directory does **not** establish
that target. Engine-free tests establish the harness behavior; native and Linux
wheel qualification remain pending. Changes are intentionally uncommitted.

## Run on an offline Linux pod

First have the fork build from `../parity/build_fork.sh` installed and pinned at
`research/ext/Royale-fork/`, and a separate Python environment containing the
cached **royalesim 0.1.33** wheel. No installation or network operation occurs in
this launcher. It holds `/workspace/cpu.lock` and starts only its own workers.

```bash
DIFFSIM_PYTHON=/workspace/venv33/bin/python \
ORACLE_PYTHON=/workspace/venv33/bin/python \
bash scratchpad/gauntlet/L74/diffsim/run_diffsim.sh \
  --full-matches 1000 --skirmishes 100 \
  --out /workspace/results/DIFFSIM_SANITY
```

Using the same interpreter executable is safe: **two different subprocesses**
load the fork's pinned target directory and the interpreter's installed wheel.
No process swaps binary modules. Both use the same explicit card-table option
`client160402017_20261006`. The oracle worker enforces version 0.1.33. Fork
activation verifies the existing build manifest, installed files and compiled
provenance through `pipeline.royale_runtime.activate()`. A candidate `--candidate
wheel --candidate-python ...` can instead use another compatible wheel.

Expected sanity result: 100% exact exposed-state traces and identical completed
results when the fork has the same mechanics/data as 0.1.33. This has **not** been
measured here. Unsupported scenarios, missing form coverage, errors and unfinished
full matches prevent a green sanity verdict. No easy-case replacement sampling.
CLI exits 0 only for an entirely successful cohort, 1 for failed comparisons or
coverage, and a nonzero exception status for invalid configuration/startup.

Smaller first smoke:

```bash
bash scratchpad/gauntlet/L74/diffsim/run_diffsim.sh \
  --cards Tornado,Tesla,IceWizard,Xbow,Rocket,Knight,Log,Skeletons \
  --unit-limit 10 --skirmishes 3 --full-matches 3 \
  --out /workspace/results/DIFFSIM_SMOKE
```

Default card selection is icebow plus the top 60 ranked by summed card frequencies
in the checked-in `../livecal/census_lad.json`. That is a **weighted, truncated
deck census**, not a fresh global usage census. The recipe binds its SHA256 and
the resulting 63-card union. Pass `--census /path/to/census_latest.json` for CRAPI
`tier1_ranked.card_usage`, or a complete project's `{decks:[{engine,sides}]}`
census. Unknown aliases fail; counts are never invented. `--cards` selects an
explicit smaller set. `--apk-snapshot /path/to/apktables/.../snapshot.json`
overlays costs/form availability from the local normalized APK table; its hash
is recorded. The sandbox's local public card catalog supplies IDs and kinds.
Catalogue declarations do not prove an engine implements a card/form: actual
resets and required form/ability observations are checked during execution.

## Adapter contract

`core.Engine` defines:

```python
reset(scenario) -> None
step(n: int) -> None
deploy(side, card, form, x, y, tick) -> {"accepted": bool}
ability(side, card, tick, **kwargs) -> {"accepted": bool}
state() -> dict
can_deploy(side, card, form, x, y) -> bool
close() -> None
```

`FakeEngine`, `ForkEngine`, and `NativeEngine` implement the same interface.
Scenario JSON has `schema_version=1`, `seed`, two eight-card `decks` of
`{card, form, level}`, `arena`, `tower_troops`, `tower_levels`, observer `side`,
`duration_ticks`, `plays`, optional initial `units`, and optional seeded `policy`.
Side 0/1 is always positional blue/red; observer side never rotates coordinates.
Card names are stable internal names, not catalogue indices. Levels are one-based.
`form` is the deck setting (0 base / 1 evolution / 2 hero); evolution cycling is
handled naturally by each engine. No forced evolved spawns or hand edits.

Time is 20 Hz. Coordinates are integer **1/18000 tiles** (RoyaleSim subtiles).
Native input positions must divide by 18 exactly; its observed millitiles are
multiplied by 18. This conversion preserves sub-millitile differences in fork
positions. Elixir is integer 1/10000 units. The fork only publicly exports
millielixir, multiplied by 10; no extra precision is fabricated.

`state()` includes `tick`, `units`, `towers`, `elixir[2]`, `clock`, and `result`
(`terminal`, `winner`: null/0/1/2 for pending/blue/red/draw, `crowns[2]`). Each
entity has `id`, `spawn_order`, `card`, `form`, `side`, `x/y`, `hp/max_hp`, `shield`,
`status` timers/buffs, and `target`. Fork state also retains mount, level, unit
type, public projectiles and every remaining public JSON field. Native state
retains the full native observation under `extra.native_observation` for adapter
inspection. The native comparison projection is narrower, as described below.

Calls apply at the **current** tick; a mismatched requested tick raises.
The runner records tick 0, then every tick after its commands and before the next
step, including the terminal tick. Fixed actions order blue before red and allow
at most one command per side/tick. Generation uses the oracle's public legality
probe (current hand, elixir and placement); accepted actions are frozen to JSON
and replayed exactly on the candidate, even after a mismatch. Rejected random
ability attempts are diagnostic counts and cannot change the frozen replay.
Scripted unit-suite refusals or plays never reached by the oracle are coverage
failures. A frozen repro can include rejected commands to reproduce an acceptance
divergence.

The fork's public reset supports the standard arena and Princess tower troop;
other requested configurations fail explicitly. Native reset maps arena/tower
troop/level into the documented replay template. Initial-unit deletion is
supported by the minimizer and fake/fork reset; the native documented API cannot
inject initial units, so generated shared suites use ordinary deploy plays.

## Suites and artifacts

- Single cards; all ordered pairs (including mirrors) in the chosen set; spells
  on Skeleton/Goblin groups; buildings versus each chosen troop.
- Evolution and hero/champion cases with natural cycling and ability presses.
  Required observed form and accepted ability coverage is checked.
- Deterministic 10–30 second random skirmishes, and full matches up to a 360-second
  safety horizon (regulation, overtime and tiebreak). A full match must actually
  terminate on both engines to count as exact or result-matching.
- Random standard eight-card decks, levels 9–16, up to two evolution slots and
  one hero/champion, and random engine-legal play sequences.

`out/<run>/recipe.json` binds inputs, seeds, scope and tolerances.
`scenarios/` stores requested and frozen JSON. `candidate/` and `oracle/` contain
gzip JSONL traces and worker stderr. Native/common runs additionally preserve
unprojected `.full.jsonl.gz` diagnostic traces for both engines. `cases/` has first-divergence tick, seconds,
field, values, involved cards, coverage and engine provenance. Frames stream to
disk; no full trace is retained in RAM. Engine workers stay alive across cases.

Unit alignment uses birth card + side + per-group spawn ordinal, with a lifetime
raw-ID map that survives deaths. Targets and mounts are remapped as well. Missing
entities, missing fields, missing tail frames and nonconsecutive ticks cannot
pass silently. Exact is the default. `--tolerances path.json` takes absolute
path-glob tolerances, e.g. `{"units.*.x":18}`; it adds a separate tolerant result
and never changes the exact progress numbers.

The minimizer delta-debugs plays and initial units, then finds the shortest
diverging prefix. It repeats until deletions stop helping, preserving the original
cards/field/event signature and replaying the final artifact. The guarantee is
**1-minimal under individual deletion, not global combinatorial optimality**.
Decks, seed, coordinates and levels remain fixed. `repros/<case>.json` is runnable:

```bash
bash scratchpad/gauntlet/L74/diffsim/run_diffsim.sh \
  --repro /workspace/results/DIFFSIM_SANITY/repros/000123.json \
  --out /workspace/results/DIFFSIM_REPRO
```

All divergences are minimized by default; an explicit `--minimize-limit N`
bounds this work and reports the unminimized count. `attribution.json` groups
**minimized repros** by cards + identity-independent field + event type, sorted
by frequency. This is an investigation queue, not proof of a causal mechanic.

`report.json` and `SUMMARY.txt` report per-suite exact %, skirmish exact %, full
trace-exact % and full result-match %, counts and Wilson 95% intervals. Errors,
coverage failures and incomplete matches stay in the requested denominators.
Zero-sized categories are null, never 100%. CIs are descriptive for correlated
unit suites. `history/<UTC-date-time>-<hash>.json` is append-only by unique file;
no previous result is overwritten. Stand-in/fake results never count as native
evidence. `owner_goal_proven` remains false until native qualification can support
that claim. Output directories must be new.

## Native oracle: source-reviewed, VM UNTESTED

Local `bindings/runtime-manifest.json` and `docs/API.md` specify **150535029**.
`bindings/` holds runtime manifests; the actual Python bindings are
`native_core.env.NativeRoyaleEnv`, `native_core.decks.build_replay`, and
`native_core.client.JsonLineClient`. The adapter uses those documented calls:
reset/warmup=0, full observe, step, dry-run probe, act, and use_ability with public
generation handles. It does not start/stop the sandbox, retry ambiguous mutations,
edit RoyaleSim, or interact with game protections or live scripts.

Still needed:

1. A virtualization-capable host, VT-x/AMD-V and the supported Android emulator
   setup described by the sandbox's README; the documented local service running.
2. A legitimate sandbox runtime **160402012** update, matching bindings manifest,
   card catalog, assets and replay template, verified by its own documented checks.
   Merely editing the old manifest's version is not an update. The adapter refuses
   the current old manifest before opening any connection.
3. VM qualification of reset/deal, level/tower mapping, coordinate conversion,
   spawn/card lineage, target references and terminal/tiebreak behavior. Some
   sleeping kings are absent from the current native entity list. The sandbox's
   buffs/area-effect extension is explicitly **unverified**; shield is mapped from
   those buffs and must be checked. Native data build must also be reconciled with
   the fork's named `client160402017_20261006` table before a parity claim.
4. A validated common full-observation contract. The fork exposes rounded status
   timers and elixir; the native adapter exposes additional native timers. Native
   mode currently compares a clearly labeled `common` projection (entities,
   HP/shield, positions, forms, levels, targets, buffs, elixir, tick, results),
   omitting unmatched timers, projectiles and engine-specific extras. This is
   **diagnostic partial-state comparison**, not full-state certification.

After those external prerequisites are supplied, the prepared command is:

```bash
bash scratchpad/gauntlet/L74/diffsim/run_diffsim.sh --oracle native \
  --native-manifest /workspace/native-160402012/bindings/runtime-manifest.json \
  --native-template /workspace/native-160402012/eight-card-bootstrap.json \
  --native-port 37031 --full-matches 1000 \
  --out /workspace/results/DIFFSIM_NATIVE
```

Update the sandbox checkout's bindings/catalog alongside that manifest. Only an
already-running **loopback** service is contacted in native mode. No native
connection, network request, download or VM launch was made in this ticket.

## Verification and files

```powershell
python scratchpad/gauntlet/L74/diffsim/verify.py
```

`tests/test_diffsim.py` covers synthetic comparison/alignment/targets/tolerances,
planted interaction and initial-unit minimization, deterministic generation,
engine-legal policy/replay, attribution, CI/error denominators/history, mocked
public adapter calls, and actual separate-process FakeEngine CLI integration.
`VERIFICATION.json` binds source hashes to the test receipt and explicitly marks
both real adapters untested. Test artifacts stay under ignored `test-output/`.
Python 3.10+ and the standard library suffice for tests and harness orchestration;
engine environments must satisfy their own wheel/bindings requirements.

Files: `core.py` contract/comparison; `adapters.py`; `generators.py`; `runner.py`
execution/isolation; `worker.py`; `analysis.py` minimization/attribution/metrics;
`cli.py`; `run_diffsim.sh`; `tests/`; `verify.py`; `GATES.md`; this README.
The local Bash binary failed to start (Windows CreateFileMapping error 5), so
shell execution/syntax qualification and the wheel sanity run are pending on Linux.

The retained `examples/planted-input.json` and `examples/planted-minimized.json`
demonstrate a measured reduction from four plays/40 ticks to the Knight/Archers
interaction alone at tick 6 (0.3 s). `out/planted-proof/` has the actual traces,
attribution and evidence (20 minimization predicate calls). The first dated
`history/` entry is explicitly `synthetic_fake`, with the planted HP mismatch
99 versus 100; it is a harness demonstration, not a simulator progress result.
