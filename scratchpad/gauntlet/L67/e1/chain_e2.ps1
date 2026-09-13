# E2 (L67am, owner "yes, test it" 2026-09-12): v6aug_s1 -- the S1 checkpoint trained with degraded rows -- under the LIVE
# rule + live view on held-out 0:100, at tau 0.27 (the live value) and tau 0.083 (the rate-matched tau recorded for s1,
# HANDOFF 5cs.98 A). Paired afterwards (from Bash) against v6lat's live-rule baseline_k0.
# Order: boot only if needed -> liveness -> reproduction of v6lat's live rule on 0:10 -> 2 arms -> stop the VM.
# Traps carried from L67al: never `Start-Process -Wait` (waits for descendants); no in-script scoring (2>&1 lost it).
$Repo    = 'C:\Users\benpe\ClashBot'
Set-Location $Repo
$Py      = "$Repo\icebow\.venv\Scripts\python.exe"
$E1      = "$Repo\scratchpad\gauntlet\L67\e1"
$A       = "$E1\attrib"
$V6lat   = 'icebow\data\pipeline\s1_icebow_v6lat_s0.pt'
$V6aug   = 'icebow\data\pipeline\s1_icebow_v6aug_s1.pt'
$Log     = "$E1\e2.log"
$Sandbox = "$Repo\research\ext\cr-native-sandbox"

function Note([string]$m) { "$(Get-Date -Format s) $m" | Add-Content $Log }

function Run-Worker([string]$Verb, [string]$OutFile) {
  $w = Start-Process powershell.exe -WindowStyle Hidden -PassThru -ArgumentList '-NoProfile', '-Command',
         "Set-Location '$Sandbox'; . .\runtime.env.ps1; .\.venv\Scripts\python.exe -m native_core.worker $Verb --workers 2 *> '$OutFile'"
  Wait-Process -Id $w.Id -Timeout 600 -ErrorAction SilentlyContinue
  if (Test-Path $OutFile) { return (Get-Content $OutFile -Raw) } else { return '' }
}

function Run-Eval([string]$Name, [string]$Ckpt, [string[]]$Extra) {
  $Out = "$A\$Name\slot0"
  New-Item -ItemType Directory -Force (Split-Path $Out) | Out-Null
  if ((Test-Path $Out) -and (Get-ChildItem $Out -ErrorAction SilentlyContinue)) { Note "$Name output not empty -- skipping"; return $false }
  $argv = @('-m', 'pipeline.e1_eval', '--mode', 'eval', '--policy', 'live', '--ckpt', $Ckpt, '--port', '38031', '--shard', '0/1',
            '--split', 'heldout', '--seeds', '0', '--out', $Out) + $Extra
  $p = Start-Process -FilePath $Py -ArgumentList $argv -WorkingDirectory $Repo -WindowStyle Hidden -PassThru `
         -RedirectStandardOutput "$Out.stdout.log" -RedirectStandardError "$Out.stderr.log"
  $null = $p.Handle
  "$(Get-Date -Format s) pid=$($p.Id) e2 $Name port=38031 out=$Out" | Add-Content "$E1\pids.txt"
  Note "$Name launched pid $($p.Id): ckpt $Ckpt $($Extra -join ' ')"
  Wait-Process -Id $p.Id
  $n = if (Test-Path "$Out\matches.jsonl") { (Get-Content "$Out\matches.jsonl").Count } else { 0 }
  $err = Test-Path "$Out\errors.jsonl"
  Note "$Name exited code=$($p.ExitCode) matches=$n errors=$err"
  return (-not $err)
}

function Stop-Engine {
  Note "stopping engine services + VM"
  $null = Run-Worker 'stop --stop-vm' "$E1\status_stop_3.txt"
  Note ("stop done; qemu left={0}; free GB {1:N1}" -f @(Get-Process qemu* -ErrorAction SilentlyContinue).Count, ((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB))
}

Note "e2 start"
$st = Run-Worker 'status' "$E1\status_e2_pre.txt"
if ($st -match '"vm_ready":\s*true' -and $st -match '"services":\s*\[\s*true,\s*true\s*\]') { Note "services already up -- boot skipped" }
else {
  $bl = "$E1\boot_4.log"
  $b = Start-Process powershell.exe -WindowStyle Hidden -PassThru -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
         "$Repo\scratchpad\gauntlet\L63\s0\_boot.ps1" -RedirectStandardOutput $bl -RedirectStandardError "$E1\boot_4.stderr.log"
  "$(Get-Date -Format s) pid=$($b.Id) boot_4" | Add-Content "$E1\pids.txt"
  $t0 = Get-Date
  while (((Get-Date) - $t0).TotalMinutes -lt 45) { if ((Test-Path $bl) -and (Select-String -Path $bl -Pattern '^=== end' -Quiet)) { break }; Start-Sleep -Seconds 10 }
  $boot = if (Test-Path $bl) { Get-Content $bl -Raw } else { '' }
  if ($boot -notmatch 'exit=0') { Note "BOOT FAILED -- see boot_4.log"; Stop-Engine; Note "ALL DONE (boot failed)"; exit 2 }
  Note ("boot ok: " + (($boot -split "`n" | Select-String 'attempt|exit=') -join ' | '))
}

$LOut = "$E1\liveness\p38031_3"
$lp = Start-Process -FilePath $Py -ArgumentList @('-m', 'pipeline.e1_eval', '--mode', 'liveness', '--port', '38031', '--split', 'heldout',
        '--entries', '0:1', '--out', $LOut) -WorkingDirectory $Repo -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput "$LOut.stdout.log" -RedirectStandardError "$LOut.stderr.log"
Wait-Process -Id $lp.Id -Timeout 300 -ErrorAction SilentlyContinue
$live = if (Test-Path "$LOut.stdout.log") { Get-Content "$LOut.stdout.log" -Raw } else { '' }
if ($live -notmatch '"ok": true') { Note "LIVENESS FAILED -- see $LOut.stdout.log"; Stop-Engine; Note "ALL DONE (liveness failed)"; exit 2 }
Note "liveness ok on 38031"

$null = Run-Eval 'e2_repro_v6lat10' $V6lat @('--entries', '0:10')
$null = Run-Eval 'e2_v6aug_s1_tau027' $V6aug @('--entries', '0:100')
$null = Run-Eval 'e2_v6aug_s1_tau0083' $V6aug @('--entries', '0:100', '--tau', '0.083')

Stop-Engine
Note "ALL DONE"
