# Battery watchdog for a detector training run.
#
# PAUSE / SIT / AUTO-RESUME (owner spec, 2026-09-02 gauntlet). Earlier versions only KILLED the run
# at the threshold and left a manual `--resume` for a human to notice. Board training is a ~24 h job
# that nobody is watching, so a kill was in practice the end of the run. This version:
#
#   battery <= Threshold  ->  stop the detector training (checkpoint is last.pt, written every epoch)
#                         ->  SIT for SitMinutes (default 90) so the machine can charge
#                         ->  RESUME `tools\detect\train.py --resume <Run>` and keep watching
#                         ->  repeat, up to MaxCycles times
#
# Deliberately narrow, and the reasons are the same as before:
#   * kills ONLY the detector training (the GPU job), never train-sim-ppo.
#   * refuses to stop if last.pt is missing -- without it the run is NOT resumable and stopping
#     would throw the work away, which is worse than letting the battery decide.
#   * exits by itself when training finishes, so it leaves nothing running.
#
# New refusals, each because the alternative silently destroys a run:
#   * refuses to RESUME a STRIPPED last.pt (no optimizer/epoch state). Ultralytics does not raise on
#     that -- it starts a BRAND-NEW coco8 training that looks like a normal log. train.py guards this
#     too; the watchdog checks first so it does not burn the sit-cycle discovering it.
#   * refuses to resume while still at or below the threshold (no point re-entering the same stop),
#     and waits for AC if the battery is discharging.
#
# Usage:
#   powershell -File tools\battery_watchdog.ps1 -Run board-27 [-Threshold 10] [-SitMinutes 90]
param(
    [int]$Threshold = 10,
    [int]$PollSeconds = 60,
    [string]$Run = "board-27",
    [int]$SitMinutes = 90,          # owner spec: "allowed to sit for 1-2 hours"
    [int]$MaxCycles = 12,
    [int]$ResumeAtPct = 25          # do not resume below this, or we stop again almost immediately
)

$ErrorActionPreference = "SilentlyContinue"
$root = "c:\Users\benpe\ClashBot\icebow"
$log  = "$root\data\battery_watchdog.log"
$last = "$root\runs\detect\$Run\weights\last.pt"
$py   = "$root\.venv\Scripts\python.exe"

function Note($m) {
    $line = "{0}  {1}" -f (Get-Date -Format "MM-dd HH:mm:ss"), $m
    Add-Content -Path $log -Value $line
}

function Get-TrainProcs {
    @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
      Where-Object { $_.CommandLine -like '*detect*train*' })
}

# A finished/stripped checkpoint carries no optimizer state; resuming it starts a new coco8 run.
function Test-Resumable($path) {
    if (-not (Test-Path $path)) { return $false }
    $probe = @"
import sys, torch
try:
    ck = torch.load(sys.argv[1], map_location='cpu', weights_only=False)
    ok = isinstance(ck, dict) and ck.get('optimizer') is not None and ck.get('epoch', -1) >= 0
except Exception:
    ok = False
print('YES' if ok else 'NO')
"@
    $probe | & $py - $path 2>$null | Select-Object -Last 1
}

Note "watchdog START  run=$Run  threshold=$Threshold%  sit=${SitMinutes}m  resume_at=$ResumeAtPct%  poll=${PollSeconds}s"

$cycles = 0
while ($true) {
    $procs = Get-TrainProcs
    if ($procs.Count -eq 0) {
        Note "training no longer running -- watchdog exiting, nothing to do"
        break
    }

    $bat = Get-CimInstance Win32_Battery
    if ($null -eq $bat) { Note "no battery reported (desktop/AC-only?) -- watchdog exiting"; break }
    $pct = [int]$bat.EstimatedChargeRemaining
    $st  = [int]$bat.BatteryStatus          # 1 = discharging, 2 = on AC

    if ($pct -le $Threshold -and $st -eq 1) {
        if (-not (Test-Path $last)) {
            Note "battery $pct% but NO last.pt at $last -- NOT stopping (run would be unrecoverable)"
            Start-Sleep -Seconds $PollSeconds
            continue
        }
        if ($cycles -ge $MaxCycles) {
            Note "battery $pct% but MaxCycles ($MaxCycles) reached -- stopping for good, resume by hand"
            foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force }
            break
        }
        $cycles++
        Note "battery $pct% (discharging) <= $Threshold% -- PAUSE cycle $cycles of ${MaxCycles} -- stopping $Run"
        foreach ($p in $procs) { Note "  stopping PID $($p.ProcessId)"; Stop-Process -Id $p.ProcessId -Force }
        Start-Sleep -Seconds 10
        Note "  paused. sitting ${SitMinutes} min to charge"

        # SIT, then wait for a sane charge level before resuming.
        Start-Sleep -Seconds ($SitMinutes * 60)
        while ($true) {
            $b2 = Get-CimInstance Win32_Battery
            $p2 = [int]$b2.EstimatedChargeRemaining
            $s2 = [int]$b2.BatteryStatus
            if ($p2 -ge $ResumeAtPct) { Note "  battery $p2% >= $ResumeAtPct% -- resuming"; break }
            Note "  battery $p2% (status $s2) still below $ResumeAtPct% -- waiting another 15 min"
            Start-Sleep -Seconds 900
        }

        $resumable = Test-Resumable $last
        if ($resumable -ne "YES") {
            Note "  last.pt is STRIPPED or unreadable ('$resumable') -- refusing to resume (would start a NEW coco8 run). Watchdog exiting."
            break
        }
        Note "  RESUMING: $py tools\detect\train.py --resume $Run"
        Start-Process -FilePath $py -ArgumentList "tools\detect\train.py","--resume",$Run `
                      -WorkingDirectory $root -WindowStyle Hidden `
                      -RedirectStandardOutput "$root\data\board_resume_$Run.log" `
                      -RedirectStandardError  "$root\data\board_resume_$Run.err"
        Start-Sleep -Seconds 120
        $n = (Get-TrainProcs).Count
        Note "  resume issued; detect-train procs now $n"
        if ($n -eq 0) { Note "  RESUME FAILED (no process) -- see data\board_resume_$Run.err. Watchdog exiting."; break }
    }

    Start-Sleep -Seconds $PollSeconds
}
Note "watchdog END"
