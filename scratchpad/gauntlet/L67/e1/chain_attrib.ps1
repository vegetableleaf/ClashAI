# E1 A1 attribution screen (L67al, owner "yes, run it" 2026-09-12): the LIVE rule with ONE change per arm on held-out
# 0:100 (the same entries as score_cont66_vs_liverule_100), paired against the live-rule baseline (baseline_k0).
# Order: boot (skipped if both services answer) -> liveness -> reproduction of the live rule on 0:20 (engine determinism
# across boots) -> 4 arms -> scores -> stop the VM. One engine client at a time, door 38031.
#
# TRAP (L67al, first run of this script): `Start-Process -Wait` waits for the process AND ITS DESCENDANTS. _boot.ps1
# starts the emulator, which lives until the VM stops, so `-Wait` never returned (hung 23 min after a successful boot).
# Every helper process here is started with -PassThru and awaited with `Wait-Process -Id <that pid>` only.
$Repo   = 'C:\Users\benpe\ClashBot'
Set-Location $Repo
$Py     = "$Repo\icebow\.venv\Scripts\python.exe"
$E1     = "$Repo\scratchpad\gauntlet\L67\e1"
$A      = "$E1\attrib"
$Ckpt   = 'icebow\data\pipeline\s1_icebow_v6lat_s0.pt'
$Log    = "$E1\attrib.log"
$Live   = "liverule=$E1\baseline_k0\slot0,$E1\baseline_k0\slot1"
$Sandbox = "$Repo\research\ext\cr-native-sandbox"

function Note([string]$m) { "$(Get-Date -Format s) $m" | Add-Content $Log }

function Run-Worker([string]$Verb, [string]$OutFile) {
  # native_core.worker <verb> in a child PowerShell; the env file is dot-sourced there and never printed
  $w = Start-Process powershell.exe -WindowStyle Hidden -PassThru -ArgumentList '-NoProfile', '-Command',
         "Set-Location '$Sandbox'; . .\runtime.env.ps1; .\.venv\Scripts\python.exe -m native_core.worker $Verb --workers 2 *> '$OutFile'"
  Wait-Process -Id $w.Id -Timeout 600 -ErrorAction SilentlyContinue
  if (Test-Path $OutFile) { return (Get-Content $OutFile -Raw) } else { return '' }
}

function Run-Eval([string]$Name, [string[]]$Extra) {
  $Out = "$A\$Name\slot0"
  New-Item -ItemType Directory -Force (Split-Path $Out) | Out-Null
  if ((Test-Path $Out) -and (Get-ChildItem $Out -ErrorAction SilentlyContinue)) { Note "$Name output not empty -- skipping"; return $false }
  $argv = @('-m', 'pipeline.e1_eval', '--mode', 'eval', '--policy', 'live', '--ckpt', $Ckpt, '--port', '38031', '--shard', '0/1',
            '--split', 'heldout', '--seeds', '0', '--out', $Out) + $Extra
  $p = Start-Process -FilePath $Py -ArgumentList $argv -WorkingDirectory $Repo -WindowStyle Hidden -PassThru `
         -RedirectStandardOutput "$Out.stdout.log" -RedirectStandardError "$Out.stderr.log"
  $null = $p.Handle
  "$(Get-Date -Format s) pid=$($p.Id) attrib $Name port=38031 out=$Out" | Add-Content "$E1\pids.txt"
  Note "$Name launched pid $($p.Id): $($Extra -join ' ')"
  Wait-Process -Id $p.Id
  $n = if (Test-Path "$Out\matches.jsonl") { (Get-Content "$Out\matches.jsonl").Count } else { 0 }
  $err = Test-Path "$Out\errors.jsonl"
  Note "$Name exited code=$($p.ExitCode) matches=$n errors=$err"
  return (-not $err)
}

function Score([string]$Name, [string]$Title) {
  $o = & $Py -m pipeline.e1_score "$A\$Name\slot0" '--control' $Live '--out' "$E1\score_attrib_$Name" '--title' $Title 2>&1
  $o | Select-Object -Last 2 | ForEach-Object { Note "score ${Name}: $_" }
}

function Stop-Engine {
  Note "stopping engine services + VM"
  $null = Run-Worker 'stop --stop-vm' "$E1\status_stop_2.txt"
  Note ("stop done; qemu left={0}; free GB {1:N1}" -f @(Get-Process qemu* -ErrorAction SilentlyContinue).Count, ((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB))
}

Note "attrib (re)start"
# 1. boot only if needed
$st = Run-Worker 'status' "$E1\status_attrib_pre.txt"
if ($st -match '"vm_ready":\s*true' -and $st -match '"services":\s*\[\s*true,\s*true\s*\]') { Note "services already up -- boot skipped" }
else {
  $bl = "$E1\boot_3.log"
  $b = Start-Process powershell.exe -WindowStyle Hidden -PassThru -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
         "$Repo\scratchpad\gauntlet\L63\s0\_boot.ps1" -RedirectStandardOutput $bl -RedirectStandardError "$E1\boot_3.stderr.log"
  "$(Get-Date -Format s) pid=$($b.Id) boot_3" | Add-Content "$E1\pids.txt"
  $t0 = Get-Date
  while (((Get-Date) - $t0).TotalMinutes -lt 45) { if ((Test-Path $bl) -and (Select-String -Path $bl -Pattern '^=== end' -Quiet)) { break }; Start-Sleep -Seconds 10 }
  $boot = if (Test-Path $bl) { Get-Content $bl -Raw } else { '' }
  if ($boot -notmatch 'exit=0') { Note "BOOT FAILED -- see boot_3.log"; Stop-Engine; Note "ALL DONE (boot failed)"; exit 2 }
  Note ("boot ok: " + (($boot -split "`n" | Select-String 'attempt|exit=') -join ' | '))
}

# 2. liveness on the door we use
$LOut = "$E1\liveness\p38031_2"
$lp = Start-Process -FilePath $Py -ArgumentList @('-m', 'pipeline.e1_eval', '--mode', 'liveness', '--port', '38031', '--split', 'heldout',
        '--entries', '0:1', '--out', $LOut) -WorkingDirectory $Repo -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput "$LOut.stdout.log" -RedirectStandardError "$LOut.stderr.log"
Wait-Process -Id $lp.Id -Timeout 300 -ErrorAction SilentlyContinue
$live = if (Test-Path "$LOut.stdout.log") { Get-Content "$LOut.stdout.log" -Raw } else { '' }
if ($live -notmatch '"ok": true') { Note "LIVENESS FAILED -- see $LOut.stdout.log"; Stop-Engine; Note "ALL DONE (liveness failed)"; exit 2 }
Note "liveness ok on 38031"

# 3. reproduction: the live rule on held-out 0:20 must reproduce baseline_k0 exactly (0 discordant pairs)
if (Run-Eval 'repro_live20' @('--entries', '0:20')) { Score 'repro_live20' 'A1 reproduction: live rule, held-out 0:20, new boot vs baseline_k0' }

# 4. the four arms, one change each from the live rule
if (Run-Eval 'arm1_clean_obs' @('--entries', '0:100', '--obs', 'clean'))          { Score 'arm1_clean_obs' 'A1 arm 1: live rule + CLEAN observations (vs live rule), held-out 0:100' }
if (Run-Eval 'arm2_tau05'     @('--entries', '0:100', '--tau', '0.5'))            { Score 'arm2_tau05'     'A1 arm 2: live rule + tau 0.5 (vs live rule), held-out 0:100' }
if (Run-Eval 'arm3_no_mask'   @('--entries', '0:100', '--no-afford-mask'))        { Score 'arm3_no_mask'   'A1 arm 3: live rule + NO affordability mask (vs live rule), held-out 0:100' }
if (Run-Eval 'arm4_no_stall'  @('--entries', '0:100', '--stall-elixir', 'none'))  { Score 'arm4_no_stall'  'A1 arm 4: live rule + NO anti-stall (vs live rule), held-out 0:100' }

# 5. stop
Stop-Engine
Note "ALL DONE"
