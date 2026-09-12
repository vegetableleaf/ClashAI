# E1 option B, after the baseline (L67ak): score, controls on the fixed 60-entry screen, the 5cs.66-rule contrast on
# held-out 0:100 (skip with a SKIP_STEP7 file), then stop the engine VM. One engine client at a time, door 38031.
$Repo   = 'C:\Users\benpe\ClashBot'
Set-Location $Repo
$Py     = "$Repo\icebow\.venv\Scripts\python.exe"
$E1     = "$Repo\scratchpad\gauntlet\L67\e1"
$Ckpt   = 'icebow\data\pipeline\s1_icebow_v6lat_s0.pt'
$Screen = 'scratchpad\gauntlet\L67\e1\screen60_heldout_tags.txt'
$Log    = "$E1\chain_after.log"

function Note([string]$m) { "$(Get-Date -Format s) $m" | Add-Content $Log }

function Run-Eval([string]$Name, [string[]]$Extra) {
  $Out = "$E1\$Name\slot0"
  New-Item -ItemType Directory -Force (Split-Path $Out) | Out-Null
  if ((Test-Path $Out) -and (Get-ChildItem $Out -ErrorAction SilentlyContinue)) { Note "$Name output not empty -- skipping"; return $false }
  $argv = @('-m', 'pipeline.e1_eval', '--mode', 'eval', '--ckpt', $Ckpt, '--port', '38031', '--shard', '0/1',
            '--split', 'heldout', '--seeds', '0', '--out', $Out) + $Extra
  $p = Start-Process -FilePath $Py -ArgumentList $argv -WorkingDirectory $Repo -WindowStyle Hidden -PassThru `
         -RedirectStandardOutput "$Out.stdout.log" -RedirectStandardError "$Out.stderr.log"
  $null = $p.Handle
  "$(Get-Date -Format s) pid=$($p.Id) $Name port=38031 out=$Out" | Add-Content "$E1\pids.txt"
  Note "$Name launched pid $($p.Id): $($Extra -join ' ')"
  Wait-Process -Id $p.Id
  $n = if (Test-Path "$Out\matches.jsonl") { (Get-Content "$Out\matches.jsonl").Count } else { 0 }
  $err = Test-Path "$Out\errors.jsonl"
  Note "$Name exited code=$($p.ExitCode) matches=$n errors=$err"
  return (-not $err)
}

function Score([string[]]$ArgList) {
  $o = & $Py -m pipeline.e1_score @ArgList 2>&1
  $o | Select-Object -Last 3 | ForEach-Object { Note "score: $_" }
}

Note "chain_after start; waiting for CHAIN DONE"
while ($true) {
  if (Test-Path "$E1\chain.log") {
    $c = Get-Content "$E1\chain.log" -Raw
    if ($c -match 'CHAIN DONE') { break }
    if ($c -match 'NOT starting|-- stop') { Note "chain.log reports a stop -- exiting, VM left up"; exit 3 }
  }
  Start-Sleep -Seconds 20
}
if (Test-Path "$E1\baseline_k0\slot1\errors.jsonl") { Note "shard 1/2 has errors.jsonl -- exiting so it can be resumed; VM left up"; exit 3 }

# 1. baseline score (both halves)
Score @("$E1\baseline_k0\slot0", "$E1\baseline_k0\slot1", '--out', "$E1\score_baseline_k0")
$P = $null
if (Test-Path "$E1\score_baseline_k0.json") {
  $j = Get-Content "$E1\score_baseline_k0.json" -Raw | ConvertFrom-Json
  $P = $j.run.suggested_p_random
}
if ($null -eq $P) { Note "suggested_p_random not found in score_baseline_k0.json -- controls skipped"; }
else {
  $PStr = ([double]$P).ToString('0.0000', [Globalization.CultureInfo]::InvariantCulture)
  Note "rate-matched p_random = $PStr"
  # 2. controls on the fixed 60-entry screen
  $ok1 = Run-Eval 'ctrl_none60' @('--policy', 'none', '--entries', $Screen)
  $ok2 = Run-Eval 'ctrl_random60' @('--policy', 'random', '--p-random', $PStr, '--entries', $Screen)
  Score @("$E1\baseline_k0\slot0", "$E1\baseline_k0\slot1",
          '--control', "none=$E1\ctrl_none60\slot0", '--control', "random=$E1\ctrl_random60\slot0",
          '--out', "$E1\score_baseline_k0_vs_controls")
}

# 3. the 5cs.66 rule (tau 0.5, no affordability mask, no anti-stall, clean obs) on held-out 0:100, paired vs the live rule
if (Test-Path "$E1\SKIP_STEP7") { Note "SKIP_STEP7 present -- step 7 skipped" }
else {
  $ok3 = Run-Eval 'cont66_100' @('--policy', 'live', '--tau', '0.5', '--no-afford-mask', '--stall-elixir', 'none', '--obs', 'clean',
                                 '--entries', '0:100')
  Score @("$E1\cont66_100\slot0", '--control', "liverule=$E1\baseline_k0\slot0,$E1\baseline_k0\slot1",
          '--out', "$E1\score_cont66_vs_liverule_100",
          '--title', 'E1 5cs.66 rule (tau .5, no mask, clean obs) vs live rule, held-out 0:100')
}

# 4. stop the engine VM (env file dot-sourced in a child, never printed)
Note "stopping engine services + VM"
Start-Process powershell.exe -Wait -WindowStyle Hidden -ArgumentList '-NoProfile', '-Command',
  "Set-Location '$Repo\research\ext\cr-native-sandbox'; . .\runtime.env.ps1; .\.venv\Scripts\python.exe -m native_core.worker stop --workers 2 --stop-vm *> '$E1\status_stop.txt'"
$q = @(Get-Process qemu* -ErrorAction SilentlyContinue).Count
Note ("stop done; qemu processes left={0}; free GB {1:N1}" -f $q, ((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB))
Note "ALL DONE"
