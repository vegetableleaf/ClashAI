# E1 option B -- baseline runbook (S1 v6lat_s0 vs held-out ghosts, live rule)

Owner ruling 2026-09-12 "go with B": measure `icebow/data/pipeline/s1_icebow_v6lat_s0.pt` against the 293 HELD-OUT
ghosts of pool v1 in the local engine under the LIVE deploy rule. A baseline only: NO training.
Tooling: `pipeline/e1_view.py`, `pipeline/e1_pool.py`, `pipeline/e1_eval.py`, `pipeline/e1_score.py`
(build log `scratchpad/gauntlet/L67/e1_baseline_build.md`; design `scratchpad/gauntlet/L67/e1_engine_rl_design.md`).
Run ONLY when the owner says the box is free. Windows PowerShell 5.1, one window per step unless stated.

Rules that apply to every step (HANDOFF traps):
- Services are booted ONLY by `scratchpad/gauntlet/L63/s0/_boot.ps1` in its OWN PowerShell window -- never from
  inside a python process tree (tree-killing a python parent took the in-guest services down, HANDOFF l.1956-1960).
- Only the direct doors 38031 / 38032 are used. Nothing else may connect to 37031/37032/38031/38032 while a step runs
  (no `engine_play`, no viewer, no probe -- a second client hangs 120 s, design 5.5).
- Kill a stuck eval with `taskkill /PID <pid> /F` WITHOUT `/T`. Never kill the boot window's tree.
- `runtime.env.ps1` is dot-sourced, never printed or copied.
- `worker stop` keeps the VM unless `--stop-vm` is passed (HANDOFF l.2714).

## 0. Session variables (paste once per PowerShell window you launch evals from)

```powershell
$Repo = 'C:\Users\benpe\ClashBot'
Set-Location $Repo
$Py   = "$Repo\icebow\.venv\Scripts\python.exe"
$E1   = "$Repo\scratchpad\gauntlet\L67\e1"
$Ckpt = 'icebow\data\pipeline\s1_icebow_v6lat_s0.pt'
$Screen = 'scratchpad\gauntlet\L67\e1\screen60_heldout_tags.txt'   # the fixed 60 lowest-crc32 held-out tags (built offline)

function Start-E1([int]$Port, [string]$Shard, [string]$Out, [string[]]$Extra) {
  New-Item -ItemType Directory -Force (Split-Path $Out) | Out-Null
  $argv = @('-m', 'pipeline.e1_eval', '--port', "$Port", '--shard', $Shard, '--out', $Out) + $Extra
  $p = Start-Process -FilePath $Py -ArgumentList $argv -WorkingDirectory $Repo -WindowStyle Hidden -PassThru `
         -RedirectStandardOutput "$Out.stdout.log" -RedirectStandardError "$Out.stderr.log"
  $null = $p.Handle                                   # cache the handle so ExitCode is readable later
  "$(Get-Date -Format s) pid=$($p.Id) port=$Port shard=$Shard out=$Out" | Add-Content "$E1\pids.txt"
  return $p
}

function Get-E1Status([string]$Name) {                # worker status in a CHILD powershell, env file never printed
  $f = "$E1\status_$Name.txt"
  Start-Process powershell.exe -Wait -WindowStyle Hidden -ArgumentList '-NoProfile', '-Command',
    "Set-Location '$Repo\research\ext\cr-native-sandbox'; . .\runtime.env.ps1; .\.venv\Scripts\python.exe -m native_core.worker status --workers 2 *> '$f'"
  Get-Content $f
}

function Count-E1([string]$Out) { if (Test-Path "$Out\matches.jsonl") { (Get-Content "$Out\matches.jsonl").Count } else { 0 } }
```

## 1. Preflight (box must be free; ~3 min)

```powershell
# 1a. free RAM >= ~10 GB (VM ~4 GB + 2 eval processes ~2 GB each incl. the SimMatchEnv EngineMatchEnv still builds)
[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB, 1)
# 1b. no live bot / detector / trainer / other engine client: expect NO 'run.py play', detector, engine_play,
#     e1_eval, replay_batch, train_* in this list
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Select-Object ProcessId, CommandLine | Format-Table -Wrap
Get-NetTCPConnection -RemotePort 37031,37032,38031,38032 -ErrorAction SilentlyContinue   # expect nothing
# 1c. offline tests + frozen split (pool sha, rule re-derived, 293/1505/12, no held-out group leak)
& $Py -m unittest pipeline.tests.test_e1_baseline
& $Py -m pipeline.e1_pool verify
```
Proceed only if 1a >= 10, 1b/1c clean, tests `OK`, verify prints `"sha_ok": true, "rule_mismatch": 0`.

## 2. Boot the engine services (own window; ~2-8 min)

```powershell
Start-Process powershell.exe -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-NoExit', '-File', "$Repo\scratchpad\gauntlet\L63\s0\_boot.ps1"
```
Wait in that window for `exit=0` (up to 6 attempts; the DataTables pump segfaults ~1 boot in 10). Then, from the eval window:
```powershell
Get-E1Status 'after_boot'          # expect services [true, true]
```

## 3. Liveness through the caller's own path (~1 min)

`PoolV1Env(port).reset(held-out entry 0)` + 10 ticks on each door (never a bare `observe()` probe -- false deaths, HANDOFF l.1966-1969):
```powershell
& $Py -m pipeline.e1_eval --mode liveness --port 38031 --split heldout --entries 0:1 --out "$E1\liveness\p38031_1"
& $Py -m pipeline.e1_eval --mode liveness --port 38032 --split heldout --entries 0:1 --out "$E1\liveness\p38032_1"
```
Expect on both: `"ok": true`, `tick_after_reset` 90, `towers` 6, `opening_hash_match` true. If `opening_hash_match` is
false on a door that is otherwise ok, STOP: the build or level/seed differs from the corpus drive.
(If a door is rerun, use a new `--out` such as `p38031_2`; eval refuses a non-empty dir.)

## 4. Pool v1 parity -- 20 held-out entries, 10 per slot (~2 min; GATE)

The corpus's own commands for BOTH sides are driven through `PoolV1Env` (retry set = replay_drive's `(1050,)`) to the
corpus final tick; the final `state_hash` must equal the corpus record.
```powershell
$Par = @('--mode', 'parity', '--split', 'heldout', '--entries', '0:20')
$a = Start-E1 38031 '0/2' "$E1\parity20\slot0" $Par
$b = Start-E1 38032 '1/2' "$E1\parity20\slot1" $Par
Wait-Process -Id $a.Id, $b.Id; "exit codes: $($a.ExitCode) $($b.ExitCode)"
& $Py -m pipeline.e1_score "$E1\parity20\slot0" "$E1\parity20\slot1" --out "$E1\score_parity20" --title "E1 pool v1 parity (20 held-out)"
```
GATE (design 6.2): `hash_match` >= 19/20 -> continue. Otherwise STOP and report the mismatch list in
`score_parity20.md` (pool v1 is not proven faithful; the v0 fallback is not part of this tooling).

## 5. Baseline -- held-out 293 x k=0, live rule, sharded over both slots (~52 min)

```powershell
$Base = @('--mode', 'eval', '--policy', 'live', '--ckpt', $Ckpt, '--split', 'heldout', '--entries', '0:293', '--seeds', '0')
$a = Start-E1 38031 '0/2' "$E1\baseline_k0\slot0" $Base
$b = Start-E1 38032 '1/2' "$E1\baseline_k0\slot1" $Base
# progress (repeat as needed); the first lines' wall_s says whether the 21 s/match estimate holds
Count-E1 "$E1\baseline_k0\slot0"; Count-E1 "$E1\baseline_k0\slot1"
Get-Content "$E1\baseline_k0\slot0.stdout.log" -Tail 3
Wait-Process -Id $a.Id, $b.Id; "exit codes: $($a.ExitCode) $($b.ExitCode)"
& $Py -m pipeline.e1_score "$E1\baseline_k0\slot0" "$E1\baseline_k0\slot1" --out "$E1\score_baseline_k0"
$P = (Get-Content "$E1\score_baseline_k0.json" -Raw | ConvertFrom-Json).run.suggested_p_random
$PStr = ([double]$P).ToString('0.0000', [Globalization.CultureInfo]::InvariantCulture); $PStr
```
Checks in `score_baseline_k0.md`: 293 matches / 293 entries, both slots present with similar winrates, "degraded count
!= decisions" = 0.

## 6. Controls on the fixed 60-entry screen subset (~15 min)

```powershell
$None = @('--mode', 'eval', '--policy', 'none', '--ckpt', $Ckpt, '--split', 'heldout', '--entries', $Screen, '--seeds', '0')
$a = Start-E1 38031 '0/2' "$E1\ctrl_none60\slot0" $None
$b = Start-E1 38032 '1/2' "$E1\ctrl_none60\slot1" $None
Wait-Process -Id $a.Id, $b.Id; "exit codes: $($a.ExitCode) $($b.ExitCode)"

# rate-matched random: p = the baseline's attempted plays per decision that had an affordable in-hand slot
$Rand = @('--mode', 'eval', '--policy', 'random', '--p-random', $PStr, '--ckpt', $Ckpt, '--split', 'heldout', '--entries', $Screen, '--seeds', '0')
$a = Start-E1 38031 '0/2' "$E1\ctrl_random60\slot0" $Rand
$b = Start-E1 38032 '1/2' "$E1\ctrl_random60\slot1" $Rand
Wait-Process -Id $a.Id, $b.Id; "exit codes: $($a.ExitCode) $($b.ExitCode)"

& $Py -m pipeline.e1_score "$E1\baseline_k0\slot0" "$E1\baseline_k0\slot1" `
    --control "none=$E1\ctrl_none60\slot0,$E1\ctrl_none60\slot1" `
    --control "random=$E1\ctrl_random60\slot0,$E1\ctrl_random60\slot1" `
    --out "$E1\score_baseline_k0_vs_controls"
```
Read the paired blocks (60 pairs each). Also compare `plays/min` of `random` against the baseline's on the same pairs;
if it is off by more than ~20%, say so in the report rather than re-running with a new p (one change per experiment).

## 7. OPTIONAL -- section 5cs.66 continuity rule on held-out 0:100 (~18 min; only if the box is still free)

tau 0.5, no affordability mask, no anti-stall, clean observations -- the rule behind "72.3", on the SAME first 100
held-out entries the baseline already covers, paired against the live rule:
```powershell
$Cont = @('--mode', 'eval', '--policy', 'live', '--tau', '0.5', '--no-afford-mask', '--stall-elixir', 'none', '--obs', 'clean',
          '--ckpt', $Ckpt, '--split', 'heldout', '--entries', '0:100', '--seeds', '0')
$a = Start-E1 38031 '0/2' "$E1\cont66_100\slot0" $Cont
$b = Start-E1 38032 '1/2' "$E1\cont66_100\slot1" $Cont
Wait-Process -Id $a.Id, $b.Id; "exit codes: $($a.ExitCode) $($b.ExitCode)"
& $Py -m pipeline.e1_score "$E1\cont66_100\slot0" "$E1\cont66_100\slot1" `
    --control "liverule=$E1\baseline_k0\slot0,$E1\baseline_k0\slot1" --out "$E1\score_cont66_vs_liverule_100" `
    --title "5cs.66 rule (tau .5, no mask, clean obs) vs live rule, held-out 0:100"
```
Interpretation note: "the same 100 entries" is read as held-out 0:100 of pool v1 (pool v0's 100 cannot be replayed
by the v1 env, and a paired rule contrast needs the same ghosts).

## 8. If a slot fails mid-run

A shard that hits an engine/socket/timeout error writes `<out>\errors.jsonl` and exits 3; finished matches stay in
`matches.jsonl`.
```powershell
Get-Content "$E1\baseline_k0\slot1\errors.jsonl"
Get-E1Status 'after_error'          # a slot showing false -> rerun section 2 in its own window, then section 3 for that door
# relaunch ONLY the failed shard, same args + --resume (skips the (tag, k) already written)
$b = Start-E1 38032 '1/2' "$E1\baseline_k0\slot1" ($Base + @('--resume'))
```
`Start-E1` writes new `.stdout.log/.stderr.log` files over the old ones; copy them first if they matter.
Hang (no new line in `matches.jsonl` for 5 min while the process lives): `taskkill /PID <pid from pids.txt> /F`
(no `/T`), then `Get-E1Status`, then resume as above.

## 9. Stop (always)

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Select-Object ProcessId, CommandLine | Format-Table -Wrap   # no e1_eval left
Start-Process powershell.exe -Wait -WindowStyle Hidden -ArgumentList '-NoProfile', '-Command',
  "Set-Location '$Repo\research\ext\cr-native-sandbox'; . .\runtime.env.ps1; .\.venv\Scripts\python.exe -m native_core.worker stop --workers 2 --stop-vm *> '$E1\status_stop.txt'"
Get-Content "$E1\status_stop.txt"
Get-Process qemu* -ErrorAction SilentlyContinue                                    # expect nothing (VM stopped)
[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB, 1)
```
Close the boot window afterwards.

## 10. Expected box time (b -- from the measured ~21 s/match per slot, design 1.6, NOT yet measured on the live rule)

| step | matches | per slot | wall |
|---|---|---|---|
| 1 preflight + tests | -- | -- | ~3 min |
| 2 boot (73 s per attempt, up to 6) | -- | -- | ~2-8 min |
| 3 liveness | 2 resets | -- | ~1 min |
| 4 parity 20 (no model; corpus drives took ~8 s) | 20 | 10 | ~2 min |
| 5 baseline 293 x k0 | 293 | 147 / 146 | ~51 min (147 x 21 s) |
| 6 none control 60 (8.7 s/match measured for no-plays) | 60 | 30 | ~5 min |
| 6 random control 60 (<= 21 s/match) | 60 | 30 | <= ~11 min |
| scoring | -- | -- | ~1 min |
| 9 stop | -- | -- | ~2 min |
| **core total** | 433 | | **~1 h 20 min - 1 h 25 min** |
| 7 optional continuity 100 | 100 | 50 | +~18 min (**~1 h 45 min** with it) |

The live rule adds `degrade` + the view rules per decision and plays more often than tau 0.5 (anti-stall), so the
first baseline lines' `wall_s` are the real number; if they exceed ~30 s/match, the baseline alone is ~75 min.

## 11. What to report (labels)

(a) from `score_baseline_k0.md`: W/D/L, winrate with the entry-clustered 95% CI, per-slot winrates, winrate decided
before the script ended, the delivered/distinct buckets, wins where the real pro lost, plays/min, accepted fraction,
stall fires/match; `score_baseline_k0_vs_controls.md`: paired deltas vs none and random. One seed (k=0) of one
checkpoint is a SCREEN-sized baseline for the held-out set (n_eff = 293 entries), not a verdict on RL.
